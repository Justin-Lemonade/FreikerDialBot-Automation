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
    "Usage: /edit <loan number> field=value [field2=value2 ...]\n"
    "Editable fields: first_name, last_name, balance, days_overdue, monthly_payment, "
    "current_overdue_amount, original_loan_amount, phone_numbers\n"
    "For phone_numbers, separate multiple numbers with commas."
)


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
    """/edit <loan number> field=value [field2=value2 ...]"""
    if len(context.args) < 2:
        await update.effective_message.reply_text(EDIT_USAGE)
        return

    database = _database_from_context(context)
    queue_engine = _queue_engine_from_context(context)
    identifier, *assignments = context.args

    customer = await _resolve_customer_by_identifier(database, identifier)
    if customer is None:
        await update.effective_message.reply_text(f'No customer found matching "{identifier}".')
        return

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
# More Info action keyboard / action callbacks
# ---------------------------------------------------------------------------

def more_info_keyboard(record: dict) -> InlineKeyboardMarkup:
    """Returns the action panel shown beneath a full customer record view.

    Adapts to the current blacklist state so the right toggle is always
    visible, and exposes edit, phone management, history, and queue
    shortcuts from the same surface.
    """
    cid = record["id"]
    rows: list[list[InlineKeyboardButton]] = []

    if record.get("is_blacklisted"):
        rows.append([InlineKeyboardButton("✅ Unblacklist Customer", callback_data=f"cx:unbl:{cid}")])
    else:
        rows.append([InlineKeyboardButton("🚫 Blacklist Customer", callback_data=f"cx:bl:{cid}")])

    rows.append([
        InlineKeyboardButton("✏️ Edit Record", callback_data=f"cx:edit:{cid}"),
        InlineKeyboardButton("📞 Phone Menu", callback_data=f"cx:phones:{cid}"),
    ])
    rows.append([
        InlineKeyboardButton("🕘 Full History", callback_data=f"cx:hist:{cid}"),
        InlineKeyboardButton("▶️ Load Into Queue", callback_data=f"cx:queue:{cid}"),
    ])
    rows.append([InlineKeyboardButton("↩️ Return to Queue", callback_data=f"cx:return:{cid}")])
    return InlineKeyboardMarkup(rows)


def phone_menu_keyboard(record: dict) -> InlineKeyboardMarkup:
    """Returns a per-phone action keyboard so the operator can blacklist or
    delete individual phone numbers directly from the More Info view."""
    cid = record["id"]
    phones = record.get("phone_numbers") or []
    rows: list[list[InlineKeyboardButton]] = []
    for phone in phones:
        rows.append([
            InlineKeyboardButton(f"🚫 Blacklist {phone}", callback_data=f"cx:blphone:{cid}:{phone}"),
            InlineKeyboardButton(f"🗑 Delete {phone}", callback_data=f"cx:delphone:{cid}:{phone}"),
        ])
    if not rows:
        rows.append([InlineKeyboardButton("No phones on file", callback_data=f"cx:noop:{cid}")])
    return InlineKeyboardMarkup(rows)


async def handle_customer_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles all cx:<action>:<customer_id>[:<extra>] callbacks.

    Action matrix:
      bl        -- blacklist the customer
      unbl      -- remove from blacklist
      edit      -- reply with a pre-filled /edit command hint
      phones    -- show the phone menu keyboard
      blphone   -- blacklist a specific phone number
      delphone  -- remove a specific phone number from the customer record
      hist      -- reply with the customer's full history
      queue     -- load the customer as the active queue entry
      return    -- show the currently active queue card (or 'no active')
    """
    query = update.callback_query
    database = _database_from_context(context)
    queue_engine = _queue_engine_from_context(context)

    try:
        await query.answer()
        parts = query.data.split(":", 3)  # cx, action, cid[, extra]
        if len(parts) < 3:
            await query.message.reply_text("Invalid action.")
            return

        _prefix, action, raw_cid, *rest = parts
        extra = rest[0] if rest else None
        customer_id = int(raw_cid)

        if action == "bl":
            queue_engine.blacklist_customer(customer_id, True, telegram_user_id=_user_id(update))
            record = await database.async_get_customer_record(customer_id)
            await query.message.edit_text(render_customer_record(record), reply_markup=more_info_keyboard(record))

        elif action == "unbl":
            queue_engine.blacklist_customer(customer_id, False, telegram_user_id=_user_id(update))
            record = await database.async_get_customer_record(customer_id)
            await query.message.edit_text(render_customer_record(record), reply_markup=more_info_keyboard(record))

        elif action == "edit":
            customer = await database.async_get_customer(customer_id)
            if customer is None:
                await query.message.reply_text("Customer not found.")
                return
            await query.message.reply_text(
                f"Use the /edit command to update this record, for example:\n"
                f"/edit {customer['loan_number']} balance=<value>"
            )

        elif action == "phones":
            record = await database.async_get_customer_record(customer_id)
            if record is None:
                await query.message.reply_text("Customer not found.")
                return
            await query.message.reply_text("Phone numbers:", reply_markup=phone_menu_keyboard(record))

        elif action == "blphone":
            if extra:
                queue_engine.blacklist_phone(extra, telegram_user_id=_user_id(update))
                await query.message.reply_text(f"🚫 Blacklisted {extra}.")
            else:
                await query.message.reply_text("No phone specified.")

        elif action == "delphone":
            if extra:
                customer = await database.async_get_customer(customer_id)
                if customer is None:
                    await query.message.reply_text("Customer not found.")
                    return
                phones = [p for p in (customer.get("phone_numbers") or []) if p != extra]
                queue_engine.edit_customer(customer_id, telegram_user_id=_user_id(update), phone_numbers=phones)
                await query.message.reply_text(f"Removed {extra}.")
            else:
                await query.message.reply_text("No phone specified.")

        elif action == "hist":
            record = await database.async_get_customer_record(customer_id)
            if record is None:
                await query.message.reply_text("Customer not found.")
                return
            history = record.get("history") or []
            if not history:
                await query.message.reply_text("No history on record.")
                return
            lines = ["🕘 Full history:"]
            for event in history:
                ts = (event.get("event_timestamp") or "?").split("T")[0]
                lines.append(f"- {ts}  {event['event_type']}")
            await query.message.reply_text("\n".join(lines))

        elif action == "queue":
            customer = await database.async_get_customer(customer_id)
            if customer is None or customer.get("is_blacklisted"):
                # Fall through to whoever IS eligible
                selection = queue_engine.next_customer()
                if selection.customer:
                    customer = selection.customer
                else:
                    await query.message.reply_text("No eligible customers in queue.")
                    return
            from queue_ui import queue_keyboard, render_customer
            progress = queue_engine.status()
            await query.message.reply_text(
                render_customer(customer, progress),
                reply_markup=queue_keyboard(customer),
            )

        elif action == "return":
            from database import Database as _Db  # already imported
            queue_state = database.get_queue_session()
            current_id = queue_state.get("current_customer_id")
            if not current_id:
                await query.message.reply_text("No active customer in queue right now.")
                return
            customer = await database.async_get_customer(int(current_id))
            if customer is None:
                await query.message.reply_text("No active customer in queue right now.")
                return
            from queue_ui import queue_keyboard, render_customer
            progress = queue_engine.status()
            await query.message.reply_text(
                render_customer(customer, progress),
                reply_markup=queue_keyboard(customer),
            )

        else:
            await query.message.reply_text(f"Unknown action: {action}")

    except Exception:
        log.exception("Customer action callback failed")
        await query.message.reply_text("Something went wrong.")
