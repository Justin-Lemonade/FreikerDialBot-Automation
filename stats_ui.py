"""Telegram commands for session and statistics reporting."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from session_manager import SessionManager
from statistics_engine import StatisticsEngine


def statistics_from_context(context: ContextTypes.DEFAULT_TYPE) -> StatisticsEngine:
    return context.application.bot_data["statistics_engine"]


def session_manager_from_context(context: ContextTypes.DEFAULT_TYPE) -> SessionManager:
    return context.application.bot_data["session_manager"]


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    statistics = statistics_from_context(context)
    await update.effective_message.reply_text(statistics.render_statistics())


async def session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    manager = session_manager_from_context(context)
    await update.effective_message.reply_text(manager.render_current_session())
