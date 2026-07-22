"""Telegram bot entry point for the customer importer module."""

from __future__ import annotations

import asyncio
import time

from telegram import (
    Bot,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonCommands,
    MenuButtonWebApp,
    Update,
    WebAppInfo,
)
from telegram.error import InvalidToken, NetworkError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from admin_commands import clear, export, reset, summary
from ai_parser import AIParser
from config import DATA_DIR, load_settings
from customer_ui import (
    blacklist_command,
    blacklist_phone_command,
    customer_command,
    edit_command,
    handle_customer_callback,
    unblacklist_command,
    unblacklist_phone_command,
)
from database import Database
from importer import Importer
from logger import log
from queue_engine import QueueEngine
from queue_ui import (
    handle_queue_callback,
    pause,
    resume,
    status,
)
from session_manager import SessionManager
from statistics_engine import StatisticsEngine
from stats_ui import session, stats
from telegram_ui import (
    handle_button,
    handle_image,
    handle_json_file,
    handle_text,
    handle_unsupported_document,
    handle_xlsx_file,
    help_command,
    ignore_unsupported,
    rename,
    start,
    upload,
)


# Commands shown in Telegram's floating "/" suggestion menu above the text box.
BOT_COMMANDS = [
    BotCommand("start", "Show status and quick actions"),
    BotCommand("app", "Open the Mini App"),
    BotCommand("upload", "Reminder of how to bring in customer data"),
    BotCommand("resume", "Start or continue the calling queue"),
    BotCommand("pause", "Pause the calling queue"),
    BotCommand("status", "Show queue progress"),
    BotCommand("session", "Show current session details"),
    BotCommand("rename", "Give the current session a custom name"),
    BotCommand("stats", "Show today's and lifetime statistics"),
    BotCommand("customer", "Search for a customer by name, loan #, or phone"),
    BotCommand("edit", "Edit a customer's fields"),
    BotCommand("blacklist", "Blacklist a customer"),
    BotCommand("unblacklist", "Remove a customer from the blacklist"),
    BotCommand("blacklist_phone", "Blacklist a phone number"),
    BotCommand("unblacklist_phone", "Remove a phone number from the blacklist"),
    BotCommand("help", "Show all available commands"),
    BotCommand("summary", "Full session summary (admin)"),
    BotCommand("reset", "Reset the queue, reuse the same import (admin)"),
    BotCommand("clear", "Completely clear the current queue (admin)"),
    BotCommand("export", "Export customer records as CSV, JSON, or XLSX (admin)"),
]


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(BOT_COMMANDS)

    mini_app_url = application.bot_data["settings"].mini_app_url
    if mini_app_url:
        # Persistent Telegram menu button that opens the Mini App
        # directly, alongside the /app command below -- this is what
        # start_mini_app.py's own comments already describe as the
        # intended behavior ("falling back to MenuButtonCommands" when
        # no URL is configured), just not previously wired up anywhere.
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Open App", web_app=WebAppInfo(url=mini_app_url))
        )
    else:
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())


async def open_app(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/app -- explicit command alternative to the menu button, for
    clients/situations where the persistent menu button isn't visible."""
    settings = context.application.bot_data["settings"]
    if not settings.mini_app_url:
        await update.effective_message.reply_text(
            "The Mini App isn't configured yet -- MINI_APP_URL is not set. "
            "Ask an admin to set it in .env and restart the bot."
        )
        return
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📱 Open App", web_app=WebAppInfo(url=settings.mini_app_url))]]
    )
    await update.effective_message.reply_text(
        "Tap below to open the calling queue in the Mini App.", reply_markup=keyboard
    )


async def _verify_telegram_connectivity(token: str) -> None:
    """Validate the Telegram token and ensure the API is reachable."""
    if not token or not token.strip():
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing or empty. Add a valid bot token to .env.")

    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        log.info("Telegram connectivity check passed for bot %s", me.username or me.first_name or "unknown")
    except InvalidToken as exc:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is invalid. Confirm the token in .env.") from exc
    except NetworkError as exc:
        raise RuntimeError(f"Telegram connectivity check failed: {exc}") from exc


def build_application() -> Application:
    settings = load_settings()
    if not settings.telegram_bot_token or not settings.telegram_bot_token.strip():
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing or empty. Add a valid bot token to .env.")

    database = Database()
    statistics = StatisticsEngine(database)
    session_manager = SessionManager(database, statistics)
    parser = AIParser(settings)
    importer = Importer(parser, database, session_manager=session_manager)
    queue_engine = QueueEngine(
        database,
        statistics=statistics,
        session_manager=session_manager,
    )

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .build()
    )
    application.bot_data["settings"] = settings
    application.bot_data["database"] = database
    application.bot_data["importer"] = importer
    application.bot_data["queue_engine"] = queue_engine
    application.bot_data["statistics_engine"] = statistics
    application.bot_data["session_manager"] = session_manager
    application.bot_data["runtime_dir"] = DATA_DIR

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("app", open_app))
    application.add_handler(CommandHandler("upload", upload))
    application.add_handler(CommandHandler("pause", pause))
    application.add_handler(CommandHandler("resume", resume))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("session", session))
    application.add_handler(CommandHandler("rename", rename))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("clear", clear))
    application.add_handler(CommandHandler("summary", summary))
    application.add_handler(CommandHandler("export", export))
    application.add_handler(CommandHandler("customer", customer_command))
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CommandHandler("blacklist", blacklist_command))
    application.add_handler(CommandHandler("unblacklist", unblacklist_command))
    application.add_handler(CommandHandler("blacklist_phone", blacklist_phone_command))
    application.add_handler(CommandHandler("unblacklist_phone", unblacklist_phone_command))
    application.add_handler(CallbackQueryHandler(handle_queue_callback, pattern=r"^queue_"))
    application.add_handler(CallbackQueryHandler(handle_customer_callback, pattern=r"^customer_view:"))
    application.add_handler(CallbackQueryHandler(handle_button))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(
        MessageHandler(filters.Document.FileExtension("json"), handle_json_file)
    )
    application.add_handler(
        MessageHandler(filters.Document.FileExtension("xlsx"), handle_xlsx_file)
    )
    application.add_handler(MessageHandler(filters.Document.ALL, handle_unsupported_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.ALL, ignore_unsupported))
    return application


def main() -> None:
    log.info("Starting importer bot")

    retries = 0
    consecutive_network_failures = 0
    while True:
        try:
            application = build_application()
            asyncio.run(_verify_telegram_connectivity(application.bot_data["settings"].telegram_bot_token))
            application.run_polling()
            break
        except KeyboardInterrupt:
            log.info("Bot stopped by user")
            break
        except RuntimeError as exc:
            log.error("Bot startup failed: %s", exc)
            raise
        except NetworkError as exc:
            consecutive_network_failures += 1
            retries += 1
            delay = min(5 * retries, 60)
            log.warning(
                "Telegram network error (%s consecutive), retrying in %ss: %s",
                consecutive_network_failures,
                delay,
                exc,
            )
            time.sleep(delay)
        except Exception as exc:
            consecutive_network_failures += 1
            retries += 1
            delay = min(10 * retries, 60)
            log.exception("Bot crashed, restarting in %ss: %s", delay, exc)
            time.sleep(delay)


if __name__ == "__main__":
    main()
