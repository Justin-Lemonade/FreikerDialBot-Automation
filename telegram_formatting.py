"""Centralized Telegram presentation layer.

All user-facing Telegram message text is built here so that customer,
imported, and database values are HTML-escaped exactly once, in one place,
and so presentation logic is not scattered through queue/database/session
modules.

This module is intentionally pure: it only renders given data to HTML
strings and has no database or queue access. The only project dependency
is ``formatting`` (itself dependency-free), which means business modules
can delegate their render methods here without pulling in
``python-telegram-bot``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from formatting import (
    format_currency,
    format_date,
    format_duration_coarse,
    format_duration_fine,
)


# ---------------------------------------------------------------------------
# Escaping and small building blocks
# ---------------------------------------------------------------------------

def esc(value) -> str:
    """HTML-escape a dynamic value for safe insertion into a message.

    Tags only ever originate from the trusted templates in this module;
    every dynamic field (names, phone numbers, loan values, imported text,
    notes, error text) must pass through this before being inserted.
    """
    if value is None:
        return ""
    return escape(str(value), quote=False)


def section(title: str) -> str:
    """A bold section heading."""
    return f"<b>{esc(title)}</b>"


def field(label: str, value, *, code: bool = False, strong: bool = False) -> str:
    """``<b>Label:</b> value`` pair used for leading section facts."""
    value_text = esc(value)
    if code:
        value_text = f"<code>{value_text}</code>"
    elif strong:
        value_text = f"<b>{value_text}</b>"
    return f"<b>{esc(label)}:</b> {value_text}"


def stat_line(
    label: str,
    value,
    *,
    code: bool = False,
    strong: bool = False,
    raw: bool = False,
) -> str:
    """A ``• <b>Label:</b> value`` bullet for compact metric lists.

    ``raw`` marks a value that is already escaped, trusted HTML (built by
    this module's own helpers) so it is not escaped a second time.
    """
    if raw:
        value_text = str(value)
    else:
        value_text = esc(value)
    if code:
        value_text = f"<code>{value_text}</code>"
    elif strong:
        value_text = f"<b>{value_text}</b>"
    return f"• <b>{esc(label)}:</b> {value_text}"


def command_line(command: str, description: str) -> str:
    """A help entry: ``• <code>/cmd</code> — description``."""
    return f"• <code>{esc(command)}</code> — {esc(description)}"


def _phone_links(phones: list[str]) -> str:
    """Phone numbers as tap-to-call tel: hyperlinks in the message text."""
    if not phones:
        return "No phone on file"
    return ", ".join(f'<a href="tel:{esc(p)}">{esc(p)}</a>' for p in phones)


# ---------------------------------------------------------------------------
# Customer messages
# ---------------------------------------------------------------------------

def render_customer_card(customer: dict, progress) -> str:
    """The lightweight active-call card shown while working the queue.

    Deliberately scannable (name / contact / loan / queue position) --
    the full detail view lives in ``render_customer_record`` and is one
    "More Info" tap away. Only fields that actually exist are rendered.
    """
    first = customer.get("first_name", "")
    last = customer.get("last_name", "")
    full_name = f"{first} {last}".strip() or "(name missing)"
    loan_number = customer.get("loan_number")
    phones = customer.get("phone_numbers") or []
    balance = format_currency(customer.get("balance"))
    monthly_payment = format_currency(customer.get("monthly_payment"))
    overdue_amount = format_currency(customer.get("current_overdue_amount"))
    days_overdue = customer.get("days_overdue")
    warning_note = customer.get("warning_note")

    body = [f"<b>{esc(full_name)}</b>"]
    if loan_number:
        body.append(f"<code>{esc(loan_number)}</code>")
    body.extend(["", section("Contact"), stat_line("Phone", _phone_links(phones), raw=True)])

    body.extend(["", section("Loan"), stat_line("Balance", balance, strong=True)])
    if monthly_payment and monthly_payment != "—":
        body.append(stat_line("Monthly payment", monthly_payment, strong=True))
    if overdue_amount and overdue_amount != "—":
        body.append(stat_line("Amount overdue", overdue_amount, strong=True))
    if days_overdue not in (None, ""):
        body.append(stat_line("Days overdue", days_overdue))

    position = getattr(progress, "current_position", None)
    total = getattr(progress, "total_customers", None)
    percent = getattr(progress, "percent", None)
    if position is not None and total is not None:
        body.extend(
            [
                "",
                section("Queue"),
                stat_line("Position", f"{position} / {total}"),
            ]
        )
        if percent is not None:
            body.append(stat_line("Progress", f"{percent}%"))

    if warning_note:
        body.extend(["", f"⚠️ {esc(warning_note)}"])

    body.append("")
    body.append("Choose an action. Tap ℹ️ More Info for full loan details and history.")
    return "\n".join(body)


def render_customer_record(record: dict) -> str:
    """Full customer detail view: identity, blacklist state, notes, and
    history. Capped to a readable length rather than dumping unbounded
    history. Phone numbers are NOT hyperlinked here -- this is a detail
    reference, not the call card.
    """
    first = record.get("first_name", "")
    last = record.get("last_name", "")
    full_name = f"{first} {last}".strip() or "(name missing)"
    phones = record.get("phone_numbers") or []
    blacklisted_phones = set(record.get("blacklisted_phones") or [])

    def phone_line(phone: str) -> str:
        marked = f"{phone} 🚫" if phone in blacklisted_phones else phone
        return f"{marked} (primary)" if phones and phone == phones[0] else marked

    body = [f"<b>{esc(full_name)}</b>"]
    if record.get("is_blacklisted"):
        body.append("🚫 <b>CUSTOMER BLACKLISTED</b>")

    loan_number = record.get("loan_number")
    if loan_number:
        body.append(f"<code>{esc(loan_number)}</code>")

    body.extend(
        [
            "",
            section("Record"),
            stat_line("Loan", loan_number) if loan_number else None,
            stat_line("Status", record.get("status", "unknown")),
            stat_line("Balance (remaining)", format_currency(record.get("balance"))),
            stat_line("Monthly payment", format_currency(record.get("monthly_payment"))),
            stat_line("Amount overdue", format_currency(record.get("current_overdue_amount"))),
            stat_line("Original loan amount", format_currency(record.get("original_loan_amount"))),
            stat_line("Days overdue", record.get("days_overdue") or "—"),
            stat_line("Phone", ", ".join(phone_line(p) for p in phones) if phones else "None on file"),
        ]
    )
    body = [line for line in body if line is not None]

    imported = format_date(record.get("import_timestamp"))
    last_edited = format_date(record.get("last_edited_timestamp"))
    body.append(stat_line("Imported", imported))
    body.append(stat_line("Last edited", last_edited))

    if record.get("warning_note"):
        body.append(f"⚠️ {esc(record['warning_note'])}")

    notes = record.get("notes") or []
    if notes:
        body.extend(["", section(f"Notes ({len(notes)})")])
        for note in notes[:5]:
            body.append(f"• {esc(note.get('text', ''))}")
        if len(notes) > 5:
            body.append(f"...and {len(notes) - 5} more.")

    history = record.get("history") or []
    if history:
        body.extend(["", section(f"History ({len(history)})")])
        for event in history[:8]:
            timestamp = (event.get("event_timestamp") or "?").split("T")[0]
            event_text = f"{timestamp}  {event.get('event_type', '')}"
            body.append(f"• {esc(event_text)}")
        if len(history) > 8:
            body.append(f"...and {len(history) - 8} more.")

    return "\n".join(body)


# ---------------------------------------------------------------------------
# Queue / status messages
# ---------------------------------------------------------------------------

def render_queue_status(progress) -> str:
    body = [section("Calling Queue")]
    remaining = getattr(progress, "remaining", None)
    contacted = getattr(progress, "contacted", None)
    did_not_answer = getattr(progress, "did_not_answer", None)
    percent = getattr(progress, "percent", None)
    for label, value in (
        ("Remaining", remaining),
        ("Contacted", contacted),
        ("Didn't answer", did_not_answer),
        ("Progress", f"{percent}%" if percent is not None else None),
    ):
        if value is not None:
            body.append(field(label, value))
    return "\n".join(body)


# ---------------------------------------------------------------------------
# Statistics / session messages
# ---------------------------------------------------------------------------

def render_statistics(snapshot) -> str:
    today = snapshot.today
    lifetime = snapshot.lifetime
    body = [
        section("Today's Statistics"),
        "",
        section("Today"),
        stat_line("Imported", today.get("customers_loaded", 0)),
        stat_line("Contacted", today.get("customers_contacted", 0)),
        stat_line("Didn't answer", today.get("customers_not_answered", 0)),
        stat_line("Sessions completed", today.get("sessions_completed", 0)),
        "",
        section("Lifetime"),
        stat_line("Imported", lifetime.get("customers_loaded", 0)),
        stat_line("Contacted", lifetime.get("customers_contacted", 0)),
        stat_line("Didn't answer", lifetime.get("customers_not_answered", 0)),
        stat_line("Sessions", lifetime.get("sessions", 0)),
        stat_line("Avg contacts per session", snapshot.average_contacts_per_session),
        stat_line(
            "Average Time Per Customer",
            format_duration_fine(snapshot.average_seconds_per_customer),
        ),
    ]
    return "\n".join(body)


def render_current_session(session: dict, counts: dict) -> str:
    if not session:
        return "No active session."

    started = session.get("started_at") or "Not started"
    elapsed = _elapsed_text(session.get("started_at"))
    status = session.get("status", "unknown")
    body = [
        section("Session"),
        stat_line("Name", session.get("session_name", "")),
        stat_line("Status", status),
        "",
        stat_line("Started", started),
        stat_line("Elapsed time", elapsed),
        stat_line("Imported", session.get("total_customers", 0)),
        stat_line("Remaining", counts.get("waiting", 0)),
        stat_line("Contacted", counts.get("warned", 0)),
        stat_line("Didn't answer", counts.get("call_later", 0)),
    ]
    return "\n".join(body)


def render_completion_summary(summary) -> str:
    if summary is None:
        return section("Session Complete")
    body = [
        section("Session Complete"),
        stat_line("Imported", summary.imported),
        stat_line("Contacted", summary.contacted),
        stat_line("Didn't answer", summary.did_not_answer),
        stat_line("Duration", format_duration_coarse(summary.duration_seconds)),
        stat_line(
            "Average Time Per Customer",
            format_duration_fine(summary.average_seconds_per_customer),
        ),
    ]
    return "\n".join(body)


def render_completion_details(counts: dict, contacted_names: list[str], not_answered_names: list[str]) -> str:
    """The detailed end-of-queue summary (names of who was reached)."""
    body = [section("Session Complete")]
    if counts:
        body.extend(
            [
                "",
                section("Outcome"),
                stat_line("Contacted", counts.get("warned", 0)),
                stat_line("Didn't answer", counts.get("call_later", 0)),
                stat_line("Remaining", counts.get("waiting", 0)),
            ]
        )
    body.extend(["", section("Contacted")])
    if contacted_names:
        body.extend(f"• {esc(name)}" for name in contacted_names)
    else:
        body.append("• None")
    body.extend(["", section("Didn't Answer")])
    if not_answered_names:
        body.extend(f"• {esc(name)}" for name in not_answered_names)
    else:
        body.append("• None")
    return "\n".join(body)


def render_summary(values: dict) -> str:
    """Admin /summary, built from already-computed key/value pairs."""
    body = [section("Session Summary")]
    for label, value in values:
        body.append(stat_line(label, value))
    return "\n".join(body)


# ---------------------------------------------------------------------------
# Help / instructions / import messages
# ---------------------------------------------------------------------------

def render_help_text() -> str:
    groups = [
        (
            "Calling",
            [
                ("/start", "Show status and quick actions"),
                ("/app", "Open the Mini App"),
                ("/resume", "Start or continue the calling queue"),
                ("/pause", "Pause the calling queue"),
                ("/status", "Show queue progress"),
                ("/upload", "Reminder of how to bring in customer data"),
            ],
        ),
        (
            "Customers",
            [
                ("/customer <query>", "Search for a customer by name, loan #, or phone"),
                ("/edit <loan #> field=value ...", "Edit a customer's fields"),
                ("/blacklist <loan #>", "Blacklist a customer"),
                ("/unblacklist <loan #>", "Remove a customer from the blacklist"),
                ("/blacklist_phone <phone> [reason]", "Blacklist a phone number"),
                ("/unblacklist_phone <phone>", "Remove a phone number from the blacklist"),
            ],
        ),
        (
            "Session & Stats",
            [
                ("/session", "Show current session details"),
                ("/rename <name>", "Give the current session a custom name"),
                ("/stats", "Show today's and lifetime statistics"),
            ],
        ),
        (
            "General",
            [
                ("/help", "Show this list"),
            ],
        ),
        (
            "Administration",
            [
                ("/summary", "Full session summary, including completion details"),
                ("/reset", "Reset the queue and reuse the same import"),
                ("/clear", "Completely clear the current queue"),
                ("/export [csv|json]", "Export customer records as a file"),
            ],
        ),
    ]

    body = [section("Available Commands")]
    for title, commands in groups:
        body.extend(["", section(title)])
        body.extend(command_line(cmd, desc) for cmd, desc in commands)

    body.extend(
        [
            "",
            "To bring in customers: paste text, paste JSON, upload a .json file, "
            "an Excel .xlsx file, or a CRM screenshot — no need to run /upload first.",
            "",
            "Administrative commands are restricted to authorized users.",
        ]
    )
    return "\n".join(body)


def render_import_result(result) -> str:
    body = [
        "Importer initialized successfully.",
        section("Import complete"),
        field("Customers imported", result.imported_count),
    ]

    if result.flagged_count:
        body.append(
            stat_line(
                "Flagged for review",
                f"{result.flagged_count} record(s) missing name or phone. "
                "They appear in the queue — Skip or Delete them there.",
            )
        )

    if result.errors:
        body.append("")
        body.append(f"⛔ {len(result.errors)} row(s) were dropped and NOT saved:")
        for error in result.errors[:5]:
            body.append(f"• {esc(error)}")
        if len(result.errors) > 5:
            body.append(f"...and {len(result.errors) - 5} more. Use /export to see all.")

    if result.verification_warnings:
        body.append("")
        body.append(f"⚠️ {len(result.verification_warnings)} record(s) need a second look:")
        for warning in result.verification_warnings[:5]:
            body.append(f"• {esc(warning)}")
        if len(result.verification_warnings) > 5:
            body.append(f"...and {len(result.verification_warnings) - 5} more.")
        body.append("Use /export to review, or /clear and re-import if needed.")

    body.extend(["", "Tip: use /rename <name> to give this session a custom name.", "Ready when you are."])
    return "\n".join(body)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

def render_error(title: str, explanation: str, action: str) -> str:
    body = [
        section(title),
        "",
        esc(explanation),
        "",
        field("What to do", action),
    ]
    return "\n".join(body)


# ---------------------------------------------------------------------------
# Long-message handling
# ---------------------------------------------------------------------------

def split_html(text: str, limit: int = 4000) -> list[str]:
    """Split an oversized HTML message at safe logical boundaries.

    Splits on paragraph (blank-line) boundaries first so a chunk never
    breaks an HTML tag: our templates never let tags span a blank line.
    A single paragraph longer than the limit is then split at line
    boundaries (tags never span a line either). No customer data is
    silently dropped or truncated by this helper.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        if not paragraph:
            continue
        candidate = paragraph if not current else current + "\n\n" + paragraph
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= limit:
            current = paragraph
            continue

        # A single over-long paragraph: split at line boundaries first.
        # Templates never let tags span a line, so a tag can't be broken
        # this way; imported text lines are already escaped (tag-free).
        buffer = ""
        for line in paragraph.split("\n"):
            piece = line if not buffer else buffer + "\n" + line
            if len(piece) <= limit:
                buffer = piece
                continue
            if buffer:
                chunks.append(buffer)
                buffer = ""
            if len(line) <= limit:
                buffer = line
                continue
            # Pathological single line longer than the limit (e.g. a huge
            # pasted note with no newlines): hard-split into limit-sized
            # pieces. Safe for this module's templates because such lines
            # are escaped, tag-free imported/note text.
            while line:
                chunks.append(line[:limit])
                line = line[limit:]
        if buffer:
            current = buffer

    if current:
        chunks.append(current)
    return chunks


def _elapsed_text(started_at: str | None) -> str:
    if not started_at:
        return "0 minutes"
    try:
        start = datetime.fromisoformat(started_at)
    except ValueError:
        return "0 minutes"
    seconds = max(0, int((datetime.now(timezone.utc) - start).total_seconds()))
    return format_duration_coarse(seconds)
