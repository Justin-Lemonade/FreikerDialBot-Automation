"""Administrative Commands module.

Provides operator/administrator control over the workflow:
/reset, /clear, /summary, /export.

This module only integrates with existing modules (Database,
SessionManager, StatisticsEngine) and does not modify their behavior.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from config import Settings
from database import Database
from export_engine import EXPORTERS, ExportError, export_customers
from formatting import format_duration_coarse, format_duration_fine
from logger import log
import security
from session_manager import SessionManager
from statistics_engine import StatisticsEngine
from telegram_ui import no_customers_keyboard


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

def is_authorized(update: Update, settings: Settings) -> bool:
    """Return True if the update's sender is an authorized administrator.

    Thin Telegram-specific wrapper: extracts the Telegram user id from
    the Update and defers the actual decision to security.is_admin, the
    one shared rule both Telegram and the Mini App use.
    """
    user = update.effective_user
    return security.is_admin(user.id if user else None, settings)


async def _deny(update: Update) -> None:
    await update.effective_message.reply_text("Permission denied.")


def _record_admin_action(
    statistics: StatisticsEngine, action: str, telegram_user_id: int | None
) -> None:
    """Audit trail for admin-level actions (reset/clear/export), reusing
    the same customer_events history everything else already writes to
    -- no new table, no new mechanism, just a new event_type. Logged
    only on successful completion of the action, not on denied attempts
    (see BACKLOG.md for that as a follow-up)."""
    statistics.record_event("admin_action", telegram_user_id=telegram_user_id, notes=action)


# ---------------------------------------------------------------------------
# Context accessors (mirrors the pattern used in queue_ui.py / stats_ui.py)
# ---------------------------------------------------------------------------

def _settings_from_context(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _database_from_context(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.application.bot_data["database"]


def _session_manager_from_context(context: ContextTypes.DEFAULT_TYPE) -> SessionManager:
    return context.application.bot_data["session_manager"]


def _statistics_from_context(context: ContextTypes.DEFAULT_TYPE) -> StatisticsEngine:
    return context.application.bot_data["statistics_engine"]


# ---------------------------------------------------------------------------
# /reset
# ---------------------------------------------------------------------------

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset customer statuses, queue position, and progress.

    Keeps the current session, and preserves history, statistics,
    original imports, and customer records so the same import can be
    processed again.
    """
    settings = _settings_from_context(context)
    if not is_authorized(update, settings):
        await _deny(update)
        return

    database = _database_from_context(context)
    try:
        if database.count_customers() == 0:
            await update.effective_message.reply_text("No customers loaded.")
            return
        database.reset_queue()
        _record_admin_action(
            _statistics_from_context(context), "reset", update.effective_user.id if update.effective_user else None
        )
        await update.effective_message.reply_text("Queue Reset Complete")
    except Exception:
        log.exception("Queue reset failed")
        await update.effective_message.reply_text(
            "Reset failed due to a database error. Please try again."
        )


# ---------------------------------------------------------------------------
# /clear
# ---------------------------------------------------------------------------

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Completely clear the active working session.

    Deletes the current queue, temporary customer rows, and queue
    session state. Leaves sessions, customer_events, daily_statistics,
    logs, and original imports untouched. Reuses Database.clear_customers,
    which already implements exactly this behavior.
    """
    settings = _settings_from_context(context)
    if not is_authorized(update, settings):
        await _deny(update)
        return

    database = _database_from_context(context)
    try:
        database.clear_customers()
        _record_admin_action(
            _statistics_from_context(context), "clear", update.effective_user.id if update.effective_user else None
        )
        await update.effective_message.reply_text(
            "Current Queue Cleared\nNo customer list loaded.\n"
            "Upload a screenshot or paste customer text to start a new list.",
            reply_markup=no_customers_keyboard(),
        )
    except Exception:
        log.exception("Queue clear failed")
        await update.effective_message.reply_text(
            "Clear failed due to a database error. Please try again."
        )


# ---------------------------------------------------------------------------
# /summary
# ---------------------------------------------------------------------------

def render_summary(database: Database, session: dict[str, Any]) -> str:
    """Render the human-readable /summary text for the current session."""
    counts = database.status_counts()
    total = session["total_customers"] or sum(counts.values())
    handled = total - counts["waiting"]
    percent = int(round((handled / total) * 100)) if total else 0

    started_at = session.get("started_at")
    if started_at:
        started_dt = datetime.fromisoformat(started_at)
        elapsed_seconds = max(
            0, int((datetime.now(timezone.utc) - started_dt).total_seconds())
        )
        elapsed = format_duration_coarse(elapsed_seconds)
        started = started_at
    else:
        elapsed_seconds = 0
        elapsed = "0 minutes"
        started = "Not started"

    # Average time per customer for THIS session: use the final duration
    # once completed, otherwise elapsed-so-far divided by customers handled.
    handled_count = counts["warned"] + counts["call_later"]
    if session["status"] == "completed":
        basis_seconds = int(session.get("duration_seconds") or 0)
    else:
        basis_seconds = elapsed_seconds
    average_seconds_per_customer = (
        round(basis_seconds / handled_count) if handled_count else 0
    )

    lines = [
        f"Session Name\n{session['session_name']}",
        f"Started\n{started}",
        f"Elapsed Time\n{elapsed}",
        f"Imported\n{total}",
        f"Remaining\n{counts['waiting']}",
        f"Contacted\n{counts['warned']}",
        f"Didn't Answer\n{counts['call_later']}",
        f"Completion %\n{percent}%",
        f"Average Time Per Customer\n{format_duration_fine(average_seconds_per_customer)}",
    ]

    if session["status"] == "completed":
        duration_seconds = int(session.get("duration_seconds") or 0)
        lines.extend(
            [
                "Completed\nYes",
                f"Completion Time\n{session.get('finished_at') or 'Unknown'}",
                f"Duration\n{format_duration_coarse(duration_seconds)}",
            ]
        )

    return "\n\n".join(lines)


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return a human-readable summary of the current session."""
    settings = _settings_from_context(context)
    if not is_authorized(update, settings):
        await _deny(update)
        return

    database = _database_from_context(context)
    session_manager = _session_manager_from_context(context)
    try:
        # Prefer the active session, but fall back to the most recently
        # completed one so /summary still works right after a session
        # finishes (current_session() only returns in-progress sessions).
        session = session_manager.current_session() or session_manager.most_recent_session()
        if not session:
            await update.effective_message.reply_text("No active session.")
            return
        await update.effective_message.reply_text(render_summary(database, session))
        log.info("Summary Generated")
    except Exception:
        log.exception("Summary generation failed")
        await update.effective_message.reply_text(
            "Could not generate summary due to an error. Please try again."
        )


# ---------------------------------------------------------------------------
# /export
# ---------------------------------------------------------------------------

async def export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export current customer records to CSV or JSON and return the file."""
    settings = _settings_from_context(context)
    if not is_authorized(update, settings):
        await _deny(update)
        return

    export_format = "csv"
    if context.args:
        export_format = context.args[0].lower().strip()
    if export_format not in EXPORTERS:
        supported = ", ".join(sorted(EXPORTERS))
        await update.effective_message.reply_text(
            f"Unsupported format. Supported formats: {supported}."
        )
        return

    database = _database_from_context(context)
    session_manager = _session_manager_from_context(context)

    try:
        customers = database.get_all_customers()
        if not customers:
            await update.effective_message.reply_text("No customers loaded.")
            return

        session = session_manager.current_session()
        session_id = session["id"] if session else None

        file_path: Path = export_customers(customers, session_id, export_format)
        _record_admin_action(
            _statistics_from_context(context),
            f"export:{export_format}",
            update.effective_user.id if update.effective_user else None,
        )
    except ExportError as exc:
        log.exception("Export failed")
        await update.effective_message.reply_text(f"Export failed: {exc}")
        return
    except Exception:
        log.exception("Export failed")
        await update.effective_message.reply_text(
            "Export failed due to an unexpected error. Please try again."
        )
        return

    try:
        with file_path.open("rb") as handle:
            await update.effective_message.reply_document(
                document=handle, filename=file_path.name
            )
        await update.effective_message.reply_text("Export Ready")
    except Exception:
        log.exception("Sending export file failed")
        await update.effective_message.reply_text(
            "The export file was created but could not be sent. "
            f"It is saved at {file_path}."
        )
