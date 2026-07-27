"""Telegram UI for the customer-record surface: search, view (More Info),
edit, and blacklist actions.

Kept separate from queue_ui.py deliberately -- queue_ui.py's job is the
lightweight active-call card (Phase 5 of this pass says don't clutter
it); this module's job is the detailed view a "More Info" tap or a
/customer search opens into. Every mutating action here goes through
QueueEngine (edit_customer/blacklist_customer/blacklist_phone/
unblacklist_phone), which is where the actual business rules and audit
trail live -- this module is rendering and command parsing only, same
division of responsibility queue_ui.py already has with queue_engine.py.
"""

from __future__ import annotations

from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import Database
from formatting import format_currency, format_date, format_loan_number
from logger import log
from queue_engine import QueueEngine
from queue_ui import queue_keyboard, render_customer
from validation import normalize_phone_number


EDITABLE_TEXT_FIELDS = {
    "first_name",
    "last_name",
    "balance",
    "days_overdue",
    "monthly_payment",
    "current_overdue_amount",
    "original_loan_amount",
}
EDITABLE_FIELDS = EDITABLE_TEXT_FIELDS | {"phone_numbers"}

EDIT_USAGE = (
    "Usage:\n"
    "  /edit <loan number>  -- shows the record as an editable block; "
    "edit any line, paste the whole thing back to save\n"
    "  /edit <loan number> <field> <value>  -- change just that one field\n"
    "  /edit <loan number> field=value [field2=value2 ...]  -- same, "
    "original syntax, supports multiple fields at once\n\n"
    "Editable fields: first_name, last_name, balance, days_overdue, monthly_payment, "
    "current_overdue_amount, original_loan_amount, phone_numbers\n"
    "For phone_numbers, separate multiple numbers with commas."
)

# Human-readable label <-> internal field name, one line per field in the
# copy-pasteable edit block. Order here is the order the block is
# rendered in; EDIT_BLOCK_FIELD_BY_LABEL is the reverse lookup used to
# parse a pasted-back block.
EDIT_BLOCK_FIELDS: list[tuple[str, str]] = [
    ("first_name", "First Name"),
    ("last_name", "Last Name"),
    ("balance", "Balance"),
    ("monthly_payment", "Monthly Payment"),
    ("current_overdue_amount", "Amount Overdue"),
    ("original_loan_amount", "Original Loan Amount"),
    ("days_overdue", "Days Overdue"),
    ("phone_numbers", "Phone Numbers"),
]
EDIT_BLOCK_FIELD_BY_LABEL = {label: field for field, label in EDIT_BLOCK_FIELDS}
EDIT_BLOCK_HEADER_PREFIX = "✏️ EDIT CUSTOMER"


def render_editable_block(customer: dict) -> str:
    """The copy-paste-edit surface: every editable field as a plain
    'Label: value' line, using RAW field values (not the currency/date
    formatting render_customer_record uses for display) so a pasted-back
    block can be diffed exactly against what's actually stored, with no
    formatting round-trip ambiguity. The header line embeds the loan
    number so a plain pasted-back message can be matched to the right
    customer without any conversation-state tracking.
    """
    lines = [
        f"{EDIT_BLOCK_HEADER_PREFIX} — Loan #{customer.get('loan_number', '')}",
        "(Edit any line below, then paste this entire message back to save. "
        "Unchanged lines are left alone.)",
        "",
    ]
    for field, label in EDIT_BLOCK_FIELDS:
        if field == "phone_numbers":
            value = ", ".join(customer.get("phone_numbers") or [])
        else:
            value = customer.get(field)
            value = "" if value is None else str(value)
        lines.append(f"{label}: {value}")
    return "\n".join(lines)


def parse_editable_block(text: str) -> tuple[str, dict[str, str]] | None:
    """Parses a pasted-back edit block. Returns (loan_number, {field:
    raw_value}) for every recognized line, or None if the text doesn't
    start with the expected header -- callers should fall through to
    normal message handling (e.g. import) in that case, not treat this
    as an error.

    Deliberately strict about the header (so a random message never gets
    misinterpreted as an edit) but lenient about which lines are present
    -- a user might trim blank/instruction lines when pasting back, and
    only the recognized "Label: value" lines matter.
    """
    stripped = text.strip()
    if not stripped.startswith(EDIT_BLOCK_HEADER_PREFIX):
        return None

    header_line = stripped.splitlines()[0]
    if "Loan #" not in header_line:
        return None
    loan_number = header_line.split("Loan #", 1)[1].strip()
    if not loan_number:
        return None

    fields: dict[str, str] = {}
    for line in stripped.splitlines()[1:]:
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        label = label.strip()
        field = EDIT_BLOCK_FIELD_BY_LABEL.get(label)
        if field:
            fields[field] = value.strip()
    return loan_number, fields


def _database_from_context(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.application.bot_data["database"]


def _queue_engine_from_context(context: ContextTypes.DEFAULT_TYPE) -> QueueEngine:
    return context.application.bot_data["queue_engine"]


def _user_id(update: Update) -> int | None:
    return update.effective_user.id if update.effective_user else None


async def _resolve_customer_by_identifier(database: Database, identifier: str) -> dict | None:
    """Precise, non-fuzzy lookup for MUTATING commands (/edit, /blacklist)
    -- accepts either the internal numeric id or an exact loan_number.
    Deliberately not fuzzy like /customer's search, to avoid editing or
    blacklisting the wrong person from an ambiguous partial match."""
    identifier = identifier.strip()
    if identifier.isdigit():
        customer = await database.async_get_customer(int(identifier))
        if customer:
            return customer
    matches = await database.async_search_customers(identifier, limit=5)
    exact = [c for c in matches if c["loan_number"] == identifier]
    return exact[0] if exact else None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _search_results_keyboard(results: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for customer in results[:10]:
        name = f"{customer['first_name']} {customer['last_name']}".strip() or "(name missing)"
        label = f"{name} — {customer['loan_number']}"
        rows.append([InlineKeyboardButton(label[:64], callback_data=f"customer_view:{customer['id']}")])
    return InlineKeyboardMarkup(rows)


def more_info_keyboard(record: dict) -> InlineKeyboardMarkup:
    """Action panel shown alongside a full customer record (render_customer_record):
    edit, blacklist/unblacklist, per-phone management, queue-this-customer,
    return-to-queue, and full history. Every button here maps to a
    cx:<action>:<id>[:<extra>] callback handled by
    handle_customer_action_callback -- kept separate from queue_keyboard's
    lightweight active-call-card buttons (queue_ui.py), which is
    deliberately NOT cluttered with these less-frequently-used actions.
    """
    customer_id = record["id"]
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton("✏️ Edit Customer", callback_data=f"cx:edit:{customer_id}")],
    ]
    if record.get("is_blacklisted"):
        rows.append([InlineKeyboardButton("✅ Unblacklist Customer", callback_data=f"cx:unbl:{customer_id}")])
    else:
        rows.append([InlineKeyboardButton("🚫 Blacklist Customer", callback_data=f"cx:bl:{customer_id}")])
    rows.append([InlineKeyboardButton("📞 Manage Phones", callback_data=f"cx:phones:{customer_id}")])
    rows.append([InlineKeyboardButton("➡️ Queue This Customer", callback_data=f"cx:queue:{customer_id}")])
    rows.append([InlineKeyboardButton("↩️ Return to Queue", callback_data=f"cx:return:{customer_id}")])
    rows.append([InlineKeyboardButton("🕘 Full History", callback_data=f"cx:hist:{customer_id}")])
    return InlineKeyboardMarkup(rows)


def phone_menu_keyboard(record: dict) -> InlineKeyboardMarkup:
    """One row per phone number, each with Blacklist/Unblacklist and
    Delete actions -- opened from more_info_keyboard's "Manage Phones"
    button. Callback data carries the phone digits directly (cx:<action>:
    <customer_id>:<phone>) since phones aren't independently identified
    the way customers are."""
    customer_id = record["id"]
    phones = record.get("phone_numbers") or []
    blacklisted_phones = set(record.get("blacklisted_phones") or [])
    rows: list[list[InlineKeyboardButton]] = []
    for phone in phones:
        if phone in blacklisted_phones:
            blacklist_button = InlineKeyboardButton(
                f"✅ Unblacklist {phone}", callback_data=f"cx:unblphone:{customer_id}:{phone}"
            )
        else:
            blacklist_button = InlineKeyboardButton(
                f"🚫 Blacklist {phone}", callback_data=f"cx:blphone:{customer_id}:{phone}"
            )
        delete_button = InlineKeyboardButton(
            f"🗑️ Delete {phone}", callback_data=f"cx:delphone:{customer_id}:{phone}"
        )
        rows.append([blacklist_button, delete_button])
    return InlineKeyboardMarkup(rows)


def render_customer_record(record: dict) -> str:
    """Full customer detail view: identity, blacklist state, notes, and
    history -- everything the "understand what happened without digging
    through raw backend records" goal asks for, capped to a readable
    length rather than dumping unbounded history."""
    full_name = f"{record['first_name']} {record['last_name']}".strip() or "(name missing)"
    phones = record.get("phone_numbers") or []
    blacklisted_phones = set(record.get("blacklisted_phones") or [])

    def phone_line(phone: str) -> str:
        marked = f"{phone} 🚫" if phone in blacklisted_phones else phone
        return f"{marked} (primary)" if phones and phone == phones[0] else marked

    lines = [f"👤 {escape(full_name)}"]
    if record.get("is_blacklisted"):
        lines.append("🚫 CUSTOMER BLACKLISTED")
    lines.extend(
        [
            f"Loan #: {escape(format_loan_number(record.get('loan_number')))}",
            f"Status: {record.get('status', 'unknown')}",
            f"Balance (Remaining): {escape(format_currency(record.get('balance')))}",
            f"Monthly Payment: {escape(format_currency(record.get('monthly_payment')))}",
            f"Amount Overdue: {escape(format_currency(record.get('current_overdue_amount')))}",
            f"Original Loan Amount: {escape(format_currency(record.get('original_loan_amount')))}",
            f"Days Overdue: {escape(record.get('days_overdue') or '—')}",
            "Phone: " + (", ".join(phone_line(p) for p in phones) if phones else "None on file"),
            f"Imported: {escape(format_date(record.get('import_timestamp')))}",
            f"Last Edited: {escape(format_date(record.get('last_edited_timestamp')))}",
        ]
    )
    if record.get("warning_note"):
        lines.append(f"⚠️ {escape(record['warning_note'])}")

    notes = record.get("notes") or []
    if notes:
        lines.append("")
        lines.append(f"📝 Notes ({len(notes)}):")
        for note in notes[:5]:
            lines.append(f"- {escape(note['text'])}")
        if len(notes) > 5:
            lines.append(f"...and {len(notes) - 5} more.")

    history = record.get("history") or []
    if history:
        lines.append("")
        lines.append(f"🕘 History ({len(history)}):")
        for event in history[:8]:
            timestamp = (event.get("event_timestamp") or "?").split("T")[0]
            lines.append(f"- {timestamp}  {event['event_type']}")
        if len(history) > 8:
            lines.append(f"...and {len(history) - 8} more.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Search / view (More Info)
# ---------------------------------------------------------------------------

async def customer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/customer <query> -- fuzzy search by name, loan number, or phone.
    Shows the record directly on a single match, or a tappable list."""
    if not context.args:
        await update.effective_message.reply_text("Usage: /customer <name, loan number, or phone>")
        return

    database = _database_from_context(context)
    query = " ".join(context.args)
    results = await database.async_search_customers(query, limit=10)

    if not results:
        await update.effective_message.reply_text(f'No customers found matching "{query}".')
        return

    if len(results) == 1:
        record = await database.async_get_customer_record(results[0]["id"])
        await update.effective_message.reply_text(render_customer_record(record))
        return

    await update.effective_message.reply_text(
        f'{len(results)} matches for "{query}" — tap one to view:',
        reply_markup=_search_results_keyboard(results),
    )


async def handle_customer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles customer_view:<id> -- fired either from /customer's search
    results or from the "ℹ️ More Info" button on the active call card
    (queue_ui.queue_keyboard). Same handler either way; the card doesn't
    need to know or care where the tap came from."""
    query = update.callback_query
    database = _database_from_context(context)
    try:
        await query.answer()
        _action, raw_id = query.data.split(":", 1)
        record = await database.async_get_customer_record(int(raw_id))
        if record is None:
            await query.message.reply_text("Customer not found.")
            return
        await query.message.reply_text(render_customer_record(record))
    except Exception:
        log.exception("Customer callback failed")
        await query.message.reply_text("Something went wrong loading that record.")


# ---------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/edit with no args -- usage. /edit <identifier> alone -- shows the
    editable block (paste it back, changed, to save). /edit <identifier>
    <field> <value> or /edit <identifier> field=value [...] -- changes
    just the given field(s) directly, same as before.
    """
    if not context.args:
        await update.effective_message.reply_text(EDIT_USAGE)
        return

    database = _database_from_context(context)
    identifier, *rest = context.args

    customer = await _resolve_customer_by_identifier(database, identifier)
    if customer is None:
        await update.effective_message.reply_text(f'No customer found matching "{identifier}".')
        return

    if not rest:
        # Identifier only: hand back the full editable block (Option A)
        # rather than a generic usage message -- this is what makes
        # "copy, change one thing, paste back" possible without the
        # operator needing to already know the field names.
        await update.effective_message.reply_text(render_editable_block(customer))
        return

    # Forgiving shorthand: `/edit <id> <field> <value>` (exactly one
    # field, space-separated, no '=') is accepted as equivalent to
    # `/edit <id> field=value` -- most single-field edits are exactly
    # this shape, and remembering to type a literal '=' is friction for
    # no real benefit when there's only one field being changed.
    assignments = rest
    if len(rest) >= 2 and "=" not in rest[0]:
        assignments = [f"{rest[0]}={' '.join(rest[1:])}"]

    await _apply_field_assignments(update, context, customer, assignments)


async def _apply_field_assignments(
    update: Update, context: ContextTypes.DEFAULT_TYPE, customer: dict, assignments: list[str]
) -> None:
    """Shared by both /edit's field=value path and the paste-a-block path
    below -- parses `field=value` assignments (or a pre-built dict, see
    handle_potential_edit_block) against EDITABLE_TEXT_FIELDS, applies
    only what's valid, and reports the result the same way either path."""
    queue_engine = _queue_engine_from_context(context)

    fields: dict = {}
    errors: list[str] = []
    for assignment in assignments:
        if "=" not in assignment:
            errors.append(f"Ignored (expected field=value): {assignment}")
            continue
        key, _, value = assignment.partition("=")
        key = key.strip()
        if key == "phone_numbers":
            raw_numbers = [p.strip() for p in value.split(",") if p.strip()]
            fields[key] = [normalize_phone_number(p) for p in raw_numbers]
        elif key in EDITABLE_TEXT_FIELDS:
            fields[key] = value.strip()
        else:
            errors.append(f"Unknown field: {key}")

    if not fields:
        message = "Nothing to update."
        if errors:
            message += "\n" + "\n".join(errors)
        await update.effective_message.reply_text(message)
        return

    updated = queue_engine.edit_customer(customer["id"], telegram_user_id=_user_id(update), **fields)
    lines = [f"Updated {updated['first_name']} {updated['last_name']} (Loan #{updated['loan_number']})."]
    if errors:
        lines.append("")
        lines.extend(errors)
    await update.effective_message.reply_text("\n".join(lines))


async def handle_potential_edit_block(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks whether an incoming plain text message is a pasted-back
    edit block (see render_editable_block/parse_editable_block above).
    If so, diffs it against the customer's actual current values,
    applies only the fields that changed, and returns True. Returns
    False for any message that doesn't match the expected header, so
    the caller (telegram_ui.handle_text) can fall through to its normal
    handling (e.g. import) unaffected.

    Diffing against RAW stored values (not display-formatted ones) is
    what makes "leave everything unchanged except the one line I
    edited" work correctly -- comparing formatted strings would flag
    every line as "changed" the moment formatting differs even slightly
    from what the user retyped.
    """
    text = update.effective_message.text or ""
    parsed = parse_editable_block(text)
    if parsed is None:
        return False

    loan_number, submitted_fields = parsed
    database = _database_from_context(context)
    queue_engine = _queue_engine_from_context(context)

    customer = await _resolve_customer_by_identifier(database, loan_number)
    if customer is None:
        await update.effective_message.reply_text(
            f'This looks like an edit block, but no customer matches Loan #{loan_number} '
            f"anymore -- nothing was changed."
        )
        return True

    changed: dict = {}
    for field, submitted_value in submitted_fields.items():
        if field == "phone_numbers":
            raw_numbers = [p.strip() for p in submitted_value.split(",") if p.strip()]
            normalized = [normalize_phone_number(p) for p in raw_numbers]
            if normalized != (customer.get("phone_numbers") or []):
                changed[field] = normalized
            continue

        current_value = customer.get(field)
        current_str = "" if current_value is None else str(current_value)
        if submitted_value != current_str:
            changed[field] = submitted_value

    if not changed:
        await update.effective_message.reply_text("No changes detected -- nothing to update.")
        return True

    updated = queue_engine.edit_customer(customer["id"], telegram_user_id=_user_id(update), **changed)
    changed_labels = [label for field, label in EDIT_BLOCK_FIELDS if field in changed]
    lines = [
        f"Updated {updated['first_name']} {updated['last_name']} (Loan #{updated['loan_number']}).",
        "",
        "Changed: " + ", ".join(changed_labels),
    ]
    await update.effective_message.reply_text("\n".join(lines))
    return True


# ---------------------------------------------------------------------------
# Blacklist
# ---------------------------------------------------------------------------

async def blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/blacklist <loan number> [reason]"""
    if not context.args:
        await update.effective_message.reply_text("Usage: /blacklist <loan number>")
        return
    database = _database_from_context(context)
    queue_engine = _queue_engine_from_context(context)
    customer = await _resolve_customer_by_identifier(database, context.args[0])
    if customer is None:
        await update.effective_message.reply_text(f'No customer found matching "{context.args[0]}".')
        return
    updated = queue_engine.blacklist_customer(customer["id"], True, telegram_user_id=_user_id(update))
    await update.effective_message.reply_text(
        f"🚫 Blacklisted {updated['first_name']} {updated['last_name']} (Loan #{updated['loan_number']})."
    )


async def unblacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/unblacklist <loan number>"""
    if not context.args:
        await update.effective_message.reply_text("Usage: /unblacklist <loan number>")
        return
    database = _database_from_context(context)
    queue_engine = _queue_engine_from_context(context)
    customer = await _resolve_customer_by_identifier(database, context.args[0])
    if customer is None:
        await update.effective_message.reply_text(f'No customer found matching "{context.args[0]}".')
        return
    updated = queue_engine.blacklist_customer(customer["id"], False, telegram_user_id=_user_id(update))
    await update.effective_message.reply_text(
        f"Removed {updated['first_name']} {updated['last_name']} (Loan #{updated['loan_number']}) from the blacklist."
    )


async def blacklist_phone_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/blacklist_phone <phone> [reason]"""
    if not context.args:
        await update.effective_message.reply_text("Usage: /blacklist_phone <phone number> [reason]")
        return
    queue_engine = _queue_engine_from_context(context)
    phone = normalize_phone_number(context.args[0])
    reason = " ".join(context.args[1:]) or None
    queue_engine.blacklist_phone(phone, reason=reason, telegram_user_id=_user_id(update))
    message = f"🚫 Blacklisted phone {phone}."
    if reason:
        message += f" Reason: {reason}"
    await update.effective_message.reply_text(message)


async def unblacklist_phone_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/unblacklist_phone <phone>"""
    if not context.args:
        await update.effective_message.reply_text("Usage: /unblacklist_phone <phone number>")
        return
    queue_engine = _queue_engine_from_context(context)
    phone = normalize_phone_number(context.args[0])
    queue_engine.unblacklist_phone(phone, telegram_user_id=_user_id(update))
    await update.effective_message.reply_text(f"Removed {phone} from the blacklist.")


# ---------------------------------------------------------------------------
# More Info action panel callbacks (cx:<action>:<id>[:<extra>])
# ---------------------------------------------------------------------------

async def handle_customer_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatches every button on more_info_keyboard / phone_menu_keyboard.
    Callback data shape: cx:<action>:<customer_id>[:<extra>]. Each branch
    delegates to the same QueueEngine methods /edit, /blacklist, etc.
    already use, so there's one audited code path per action regardless
    of which surface (command or button) triggered it.
    """
    query = update.callback_query
    database = _database_from_context(context)
    queue_engine = _queue_engine_from_context(context)
    telegram_user_id = _user_id(update)

    try:
        await query.answer()
        parts = query.data.split(":")
        action = parts[1]
        customer_id = int(parts[2]) if len(parts) > 2 else None
        extra = parts[3] if len(parts) > 3 else None

        if action == "bl":
            queue_engine.blacklist_customer(customer_id, True, telegram_user_id=telegram_user_id)
            await query.message.edit_text("🚫 Customer blacklisted.")
            return

        if action == "unbl":
            queue_engine.blacklist_customer(customer_id, False, telegram_user_id=telegram_user_id)
            await query.message.edit_text("Customer removed from blacklist.")
            return

        if action == "edit":
            customer = await database.async_get_customer(customer_id)
            if customer is None:
                await query.message.reply_text("Customer not found.")
                return
            await query.message.reply_text(
                f"To edit this customer, send:\n"
                f"/edit {customer['loan_number']}\n"
                f"(shows an editable copy — change a line, paste it back)\n\n"
                f"or for a quick single-field change:\n"
                f"/edit {customer['loan_number']} <field> <value>"
            )
            return

        if action == "phones":
            record = await database.async_get_customer_record(customer_id)
            if record is None:
                await query.message.reply_text("Customer not found.")
                return
            await query.message.reply_text(
                "Select a phone action:", reply_markup=phone_menu_keyboard(record)
            )
            return

        if action == "delphone":
            customer = await database.async_get_customer(customer_id)
            if customer is None:
                await query.message.reply_text("Customer not found.")
                return
            remaining = [p for p in (customer.get("phone_numbers") or []) if p != extra]
            queue_engine.edit_customer(
                customer_id, telegram_user_id=telegram_user_id, phone_numbers=remaining
            )
            await query.message.reply_text(f"Removed {extra} from this customer's phone numbers.")
            return

        if action == "blphone":
            queue_engine.blacklist_phone(extra, telegram_user_id=telegram_user_id)
            await query.message.reply_text(f"🚫 Blacklisted phone {extra}.")
            return

        if action == "unblphone":
            queue_engine.unblacklist_phone(extra, telegram_user_id=telegram_user_id)
            await query.message.reply_text(f"Removed {extra} from the blacklist.")
            return

        if action == "queue":
            customer = await database.async_get_customer(customer_id)
            if customer is not None and not customer.get("is_blacklisted"):
                database.update_queue_session(current_customer_id=customer_id)
                progress = queue_engine.status()
                await query.message.reply_text(
                    render_customer(customer, progress),
                    reply_markup=queue_keyboard(customer),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                return
            # Blacklisted (or missing) -- fall through to whoever IS
            # eligible next, same rule the mutating queue path enforces,
            # rather than silently queueing someone who shouldn't be called.
            fallback = queue_engine.peek_next_customer()
            if fallback is None:
                await query.message.reply_text("No eligible customer to queue.")
                return
            database.update_queue_session(current_customer_id=fallback["id"])
            progress = queue_engine.status()
            await query.message.reply_text(
                render_customer(fallback, progress),
                reply_markup=queue_keyboard(fallback),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return

        if action == "return":
            queue_state = database.get_queue_session()
            active_id = queue_state.get("current_customer_id")
            if not active_id:
                await query.message.reply_text("No active customer to return to the queue.")
                return
            active = await database.async_get_customer(int(active_id))
            if active is None:
                await query.message.reply_text("No active customer to return to the queue.")
                return
            progress = queue_engine.status()
            await query.message.reply_text(
                render_customer(active, progress),
                reply_markup=queue_keyboard(active),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return

        if action == "hist":
            record = await database.async_get_customer_record(customer_id)
            if record is None:
                await query.message.reply_text("Customer not found.")
                return
            await query.message.reply_text(render_customer_record(record))
            return

    except Exception:
        log.exception("Customer action callback failed")
        await query.message.reply_text("Something went wrong with that action.")
