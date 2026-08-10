"""Telegram UI handlers for the importer module."""

from __future__ import annotations

import json
import time
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ai_parser import AI_PROMPT
from customer_ui import handle_potential_edit_block
from importer import ImporterError, ImportResult, Importer
from logger import log
from queue_ui import completion_keyboard, resume as queue_resume


PROGRESS_STAGES = [
    "Receiving data...",
    "Processing data...",
    "Saving data...",
    "Revising customer base...",
    "Selecting first customer...",
]

# How long to wait for a "continuation" message before giving up on merging
# a split paste back together. Telegram clients auto-split anything typed
# past ~4096 characters into separate messages sent back-to-back, so a
# short window is enough to catch genuine continuations.
FRAGMENT_MERGE_WINDOW_SECONDS = 5.0

HELP_TEXT = (
    "Available Commands\n"
    "--------------\n"
    "/start - Show status and quick actions\n"
    "/app - Open the Mini App\n"
    "/upload - Reminder of how to bring in customer data\n"
    "/resume - Start or continue the calling queue\n"
    "/pause - Pause the calling queue\n"
    "/status - Show queue progress\n"
    "/session - Show current session details\n"
    "/rename <name> - Give the current session a custom name\n"
    "/stats - Show today's and lifetime statistics\n"
    "/customer <query> - Search for a customer by name, loan #, or phone\n"
    "/edit <loan #> field=value ... - Edit a customer's fields\n"
    "/blacklist <loan #> - Blacklist a customer\n"
    "/unblacklist <loan #> - Remove a customer from the blacklist\n"
    "/blacklist_phone <phone> [reason] - Blacklist a phone number\n"
    "/unblacklist_phone <phone> - Remove a phone number from the blacklist\n"
    "/help - Show this list\n\n"
    "Bringing in customers: paste text, paste JSON, upload a .json file, "
    "or upload a CRM screenshot -- all work without needing /upload first.\n\n"
    "Administrative (authorized users only)\n"
    "--------------\n"
    "/summary - Full session summary, including completion details\n"
    "/reset - Reset the queue and reuse the same import\n"
    "/clear - Completely clear the current queue\n"
    "/export [csv|json] - Export customer records as a file"
)


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------

def no_customers_keyboard() -> InlineKeyboardMarkup:
    """Shown when nothing is loaded (fresh start, or right after /clear)."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📷 Upload Screenshot", callback_data="upload_screenshot")],
            [InlineKeyboardButton("📋 Paste Customer Text", callback_data="paste_text")],
            [InlineKeyboardButton("📄 Copy AI Prompt", callback_data="copy_ai_prompt")],
            [
                InlineKeyboardButton("📊 View Stats", callback_data="view_stats"),
                InlineKeyboardButton("❓ Help", callback_data="view_help"),
            ],
        ]
    )


def ready_to_call_keyboard() -> InlineKeyboardMarkup:
    """Shown when customers are loaded and waiting to be called."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("▶️ Start Calling", callback_data="start_calling")],
            [
                InlineKeyboardButton("📷 Upload More", callback_data="upload_screenshot"),
                InlineKeyboardButton("📊 Status", callback_data="view_status"),
            ],
        ]
    )


def idle_keyboard(total_customers: int, waiting: int) -> InlineKeyboardMarkup:
    """Pick the right contextual keyboard for the current queue state."""
    if total_customers == 0:
        return no_customers_keyboard()
    if waiting > 0:
        return ready_to_call_keyboard()
    return completion_keyboard(has_call_backs=False)


def importer_from_context(context: ContextTypes.DEFAULT_TYPE) -> Importer:
    return context.application.bot_data["importer"]


# ---------------------------------------------------------------------------
# /start, /help, /upload, /rename
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    database = context.application.bot_data["database"]
    total = await database.async_count_customers()

    if total == 0:
        message = "No customer list loaded.\nUpload a CRM screenshot or paste customer text to get started."
        waiting = 0
    else:
        waiting = await database.async_count_by_status("waiting")
        if waiting > 0:
            message = f"{total} customers loaded — {waiting} waiting to be called."
        else:
            message = f"{total} customers loaded. Everyone has been called."

    await update.effective_message.reply_text(
        message, reply_markup=idle_keyboard(total, waiting)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT)


async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # NOTE: this command doesn't do anything by itself -- importing already
    # happens automatically whenever a screenshot, pasted text, or a .json
    # file is sent, whether or not /upload was run first. It exists purely
    # as a discoverability aid for people who aren't sure how to start.
    await update.effective_message.reply_text(
        "You don't need to run this first -- just send one of the following "
        "any time:\n\n"
        "\U0001f4f7 A CRM screenshot\n"
        "\U0001f4cb Pasted customer text\n"
        "\U0001f4c4 A .json file (best for long lists -- avoids Telegram's message length limit)\n"
        "\U0001f4ca An Excel .xlsx file\n\n"
        "All of these work without needing /upload first."
    )


async def rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.effective_message.reply_text(
            "Usage: /rename <new name>\nExample: /rename Morning Batch"
        )
        return

    new_label = " ".join(context.args).strip()
    session_manager = context.application.bot_data["session_manager"]
    renamed = session_manager.rename_session(new_label)
    if renamed:
        await update.effective_message.reply_text(f'Session renamed to "{new_label}".')
    else:
        await update.effective_message.reply_text(
            "No session to rename yet. Import customers first."
        )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kept for backward compatibility. The live /clear command is now
    admin_commands.clear, which is authorization-gated and reuses
    Database.clear_customers exactly as this function does."""
    database = context.application.bot_data["database"]
    await database.async_clear_customers()
    await update.effective_message.reply_text(
        "Customer records cleared. Logs and originals were kept.",
        reply_markup=no_customers_keyboard(),
    )


# ---------------------------------------------------------------------------
# Inline button handling
# ---------------------------------------------------------------------------

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "copy_ai_prompt":
        await query.message.reply_text(AI_PROMPT)
    elif query.data == "upload_screenshot":
        await query.message.reply_text(
            "Upload a CRM screenshot, or send a .json file for long lists."
        )
    elif query.data == "paste_text":
        await query.message.reply_text(
            "Paste customer text or JSON. For very long lists, upload a "
            ".json file instead -- Telegram's message length limit doesn't "
            "apply to files."
        )
    elif query.data == "view_help":
        await query.message.reply_text(HELP_TEXT)
    elif query.data == "view_stats":
        statistics = context.application.bot_data["statistics_engine"]
        await query.message.reply_text(statistics.render_statistics())
    elif query.data == "view_status":
        queue_engine = context.application.bot_data["queue_engine"]
        from queue_ui import render_status

        await query.message.reply_text(render_status(queue_engine.status()))
    elif query.data == "start_calling":
        await queue_resume(update, context)
    elif query.data == "new_call_list":
        await query.message.reply_text(
            "Ready for a new call list. Upload a screenshot, paste customer "
            "text, or send a .json file below.\n\nTip: if you still need "
            "this session's data, run /export before /clear — starting "
            "fresh doesn't erase old records on its own, but /clear does.",
            reply_markup=no_customers_keyboard(),
        )


# ---------------------------------------------------------------------------
# Import pipeline (shared by pasted text, JSON files, and images)
# ---------------------------------------------------------------------------

async def _edit_progress(message, stage: str) -> None:
    await message.edit_text(f"⏳ {stage}")


async def run_progress(message) -> None:
    for stage in PROGRESS_STAGES:
        await _edit_progress(message, stage)


def _looks_like_incomplete_json(text: str) -> bool:
    """True if text starts like JSON but doesn't actually parse.

    Used to detect a message that's really the first half of a paste
    Telegram auto-split at its ~4096-character limit.
    """
    stripped = text.strip()
    if not (stripped.startswith("[") or stripped.startswith("{")):
        return False
    try:
        json.loads(stripped)
        return False
    except json.JSONDecodeError:
        return True


async def _report_import_result(progress_message, result: ImportResult) -> None:
    """Report success only after a round-trip verification pass, and
    surface any anomalies instead of blindly saying everything is fine.
    """
    lines = [
        "Importer initialized successfully.",
        "Import complete.",
        f"{result.imported_count} customers imported.",
    ]

    if result.flagged_count:
        lines.append(
            f"\u26a0\ufe0f {result.flagged_count} record(s) flagged for review "
            "(missing name or phone). They appear in the queue — Skip or Delete them there."
        )

    if result.errors:
        lines.append("")
        lines.append(f"\U0001f6ab {len(result.errors)} row(s) were dropped and NOT saved:")
        for error in result.errors[:5]:
            lines.append(f"- {error}")
        if len(result.errors) > 5:
            lines.append(f"...and {len(result.errors) - 5} more. Use /export to see all.")

    if result.verification_warnings:
        lines.append("")
        lines.append(f"\u26a0\ufe0f {len(result.verification_warnings)} record(s) need a second look:")
        for warning in result.verification_warnings[:5]:
            lines.append(f"- {warning}")
        if len(result.verification_warnings) > 5:
            lines.append(f"...and {len(result.verification_warnings) - 5} more.")
        lines.append("Use /export to review, or /clear and re-import if needed.")

    lines.append("")
    lines.append("Tip: use /rename <name> to give this session a custom name.")
    lines.append("Ready when you are.")

    await progress_message.edit_text("\n".join(lines), reply_markup=ready_to_call_keyboard())


async def _run_text_import(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    progress = await update.effective_message.reply_text("⏳ Receiving data...")
    importer = importer_from_context(context)

    try:
        await _edit_progress(progress, "Processing data...")
        result = await importer.import_text(text)
        await _edit_progress(progress, "Saving data...")
        await _edit_progress(progress, "Revising customer base...")
        await _edit_progress(progress, "Selecting first customer...")
        await _report_import_result(progress, result)
    except ImporterError as exc:
        log.exception("Text import failed")
        await progress.edit_text(f"Could not import this data: {exc}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text

    # A pasted-back edit block (see customer_ui.render_editable_block) is
    # never valid JSON/import content, but check for it explicitly and
    # first anyway, rather than relying on it merely failing to parse as
    # an import -- that would produce a confusing "couldn't understand
    # this" error instead of actually applying the edit.
    if await handle_potential_edit_block(update, context):
        return

    pending = context.chat_data.get("pending_text_fragment")
    now = time.monotonic()

    if pending and (now - pending["timestamp"]) <= FRAGMENT_MERGE_WINDOW_SECONDS:
        context.chat_data.pop("pending_text_fragment", None)
        combined = pending["text"] + text

        if not _looks_like_incomplete_json(combined):
            # The two messages together form valid JSON -- this really was
            # a split paste. Process the merged text instead of either half.
            await _run_text_import(update, context, combined)
            return

        # Merging didn't produce valid JSON either. Report the earlier
        # fragment as unresolved and fall through to process this message
        # on its own, rather than waiting silently forever.
        await update.effective_message.reply_text(
            "The earlier message looked like part of a longer paste but "
            "couldn't be completed, so I'm processing this message on its "
            "own instead.\n\nTip: for long customer lists, upload a .json "
            "file instead of pasting text -- it isn't limited by "
            "Telegram's message length."
        )

    if _looks_like_incomplete_json(text):
        context.chat_data["pending_text_fragment"] = {"text": text, "timestamp": now}
        await update.effective_message.reply_text(
            "⏳ Got part of your message -- send the rest and I'll combine "
            "them automatically.\n\n(If this wasn't meant to continue, "
            "upload a .json file instead -- it's not limited by Telegram's "
            "message length.)"
        )
        return

    await _run_text_import(update, context, text)


async def handle_json_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Import from an uploaded .json file -- sidesteps Telegram's message
    length limit entirely, which is the real fix for long customer lists.

    Delegates to importer.import_text(), which routes JSON-formatted input
    through _import_json (raising ImporterError for malformed JSON) while
    non-JSON input falls through to the AI text parser. Validation is
    centralized in the importer so inline JSON-parsing logic isn't
    duplicated here.
    """
    progress = await update.effective_message.reply_text("\u23f3 Receiving data...")

    try:
        document = update.effective_message.document
        telegram_file = await document.get_file()
        raw_bytes = await telegram_file.download_as_bytearray()
        text = bytes(raw_bytes).decode("utf-8")
    except UnicodeDecodeError:
        await progress.edit_text(
            "Could not read this file -- make sure it's UTF-8 encoded JSON."
        )
        return
    except Exception:
        log.exception("JSON file download failed")
        await progress.edit_text("Could not download this file. Please try again.")
        return

    importer = importer_from_context(context)
    try:
        await _edit_progress(progress, "Processing data...")
        result = await importer.import_text(text)
        await _edit_progress(progress, "Saving data...")
        await _edit_progress(progress, "Revising customer base...")
        await _edit_progress(progress, "Selecting first customer...")
        await _report_import_result(progress, result)
    except ImporterError as exc:
        log.exception("JSON file import failed")
        await progress.edit_text(f"Could not import this file: {exc}")


async def handle_xlsx_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Import from an uploaded .xlsx (Excel) file."""
    progress = await update.effective_message.reply_text("\u23f3 Receiving data...")

    try:
        document = update.effective_message.document
        telegram_file = await document.get_file()
        raw_bytes = await telegram_file.download_as_bytearray()
        # Save to a temp file so openpyxl can open it
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(raw_bytes)
            tmp_path = Path(tmp.name)
    except Exception:
        log.exception("Excel file download failed")
        await progress.edit_text("Could not download this file. Please try again.")
        return

    importer = importer_from_context(context)
    try:
        await _edit_progress(progress, "Processing data...")
        result = await importer.import_xlsx(tmp_path)
        await _edit_progress(progress, "Saving data...")
        await _edit_progress(progress, "Revising customer base...")
        await _edit_progress(progress, "Selecting first customer...")
        await _report_import_result(progress, result)
    except ImporterError as exc:
        log.exception("Excel file import failed")
        await progress.edit_text(f"Could not import this file: {exc}")
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


async def handle_unsupported_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "This file type isn't supported yet. Please upload a .json or .xlsx file, "
        "paste customer text directly, or upload a CRM screenshot."
    )


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    progress = await update.effective_message.reply_text("⏳ Receiving data...")
    importer = importer_from_context(context)

    try:
        photo = update.effective_message.photo[-1]
        telegram_file = await photo.get_file()
        temp_path = Path(context.application.bot_data["runtime_dir"]) / f"{photo.file_unique_id}.jpg"
        await telegram_file.download_to_drive(custom_path=temp_path)

        await _edit_progress(progress, "Processing data...")
        result = await importer.import_image(temp_path)
        await _edit_progress(progress, "Saving data...")
        await _edit_progress(progress, "Revising customer base...")
        await _edit_progress(progress, "Selecting first customer...")
        await _report_import_result(progress, result)
    except Exception as exc:
        log.exception("Image import failed")
        await progress.edit_text(f"Could not import this image: {exc}")


async def ignore_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.info("Ignored unsupported Telegram message")
