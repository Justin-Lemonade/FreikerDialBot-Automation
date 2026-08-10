"""Tests for the Mini App launch wiring added to bot.py.

bot.py previously never referenced Settings.mini_app_url anywhere --
these lock in the two behaviors that make the Mini App reachable from
Telegram: the /app command's fallback message when unconfigured vs. its
WebApp button when configured, and _post_init setting the appropriate
chat menu button, and _should_skip_mini_app correctly honoring the
documented --no-mini-app flag / DISABLE_MINI_APP env override.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import MenuButtonCommands, MenuButtonWebApp

from bot import _post_init, _should_skip_mini_app, app_command
from config import Settings


def _settings(mini_app_url: str | None) -> Settings:
    return Settings(
        telegram_bot_token="123456:TEST",
        openai_api_key=None,
        mini_app_url=mini_app_url,
    )


@pytest.mark.asyncio
async def test_app_command_replies_with_button_when_configured():
    update = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {"settings": _settings("https://example.com/miniapp")}

    await app_command(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    _args, kwargs = update.effective_message.reply_text.call_args
    keyboard = kwargs["reply_markup"]
    button = keyboard.inline_keyboard[0][0]
    assert button.web_app.url == "https://example.com/miniapp"


@pytest.mark.asyncio
async def test_app_command_explains_when_not_configured():
    update = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {"settings": _settings(None)}

    await app_command(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    args, kwargs = update.effective_message.reply_text.call_args
    assert "not" in args[0].lower() or "isn't" in args[0].lower()
    assert "reply_markup" not in kwargs


@pytest.mark.asyncio
async def test_app_command_explains_when_url_is_not_https():
    """Telegram requires HTTPS for web_app URLs -- a misconfigured
    http:// or bare-host value must get a clear, specific error instead
    of failing inside Telegram's own API call with an opaque exception.
    """
    update = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {"settings": _settings("http://localhost:5173")}

    await app_command(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    args, kwargs = update.effective_message.reply_text.call_args
    assert "https" in args[0].lower()
    assert "reply_markup" not in kwargs


@pytest.mark.asyncio
async def test_post_init_sets_web_app_menu_button_when_configured():
    application = MagicMock()
    application.bot.set_my_commands = AsyncMock()
    application.bot.set_chat_menu_button = AsyncMock()
    application.bot_data = {"settings": _settings("https://example.com/miniapp")}

    await _post_init(application)

    application.bot.set_chat_menu_button.assert_awaited_once()
    _args, kwargs = application.bot.set_chat_menu_button.call_args
    assert isinstance(kwargs["menu_button"], MenuButtonWebApp)
    assert kwargs["menu_button"].web_app.url == "https://example.com/miniapp"


@pytest.mark.asyncio
async def test_post_init_falls_back_to_commands_menu_when_unconfigured():
    application = MagicMock()
    application.bot.set_my_commands = AsyncMock()
    application.bot.set_chat_menu_button = AsyncMock()
    application.bot_data = {"settings": _settings(None)}

    await _post_init(application)

    _args, kwargs = application.bot.set_chat_menu_button.call_args
    assert isinstance(kwargs["menu_button"], MenuButtonCommands)


@pytest.mark.asyncio
async def test_post_init_falls_back_to_commands_menu_when_url_is_not_https():
    """Same rationale as the /app command test: a non-HTTPS MINI_APP_URL
    must fall back safely rather than being handed to Telegram's API,
    which would reject it -- previously surfacing only as a silent,
    repeating crash-and-retry loop in bot.py's main().
    """
    application = MagicMock()
    application.bot.set_my_commands = AsyncMock()
    application.bot.set_chat_menu_button = AsyncMock()
    application.bot_data = {"settings": _settings("http://localhost:5173")}

    await _post_init(application)

    _args, kwargs = application.bot.set_chat_menu_button.call_args
    assert isinstance(kwargs["menu_button"], MenuButtonCommands)


# --- DLG-009: --no-mini-app flag acceptance ---


def test_should_skip_mini_app_with_documented_hyphen_flag():
    """The documented flag is --no-mini-app (hyphen), exactly as passed
    by start_mini_app.py. It must actually be recognized, unlike the
    previously-buggy underscore spelling it was checking for.
    """
    assert _should_skip_mini_app(["bot.py", "--no-mini-app"]) is True


def test_should_not_skip_mini_app_without_flag():
    """Default behavior: no flag, no env override -> Mini App starts."""
    assert _should_skip_mini_app(["bot.py"]) is False


def test_should_skip_mini_app_with_disable_env_var(monkeypatch):
    """DISABLE_MINI_APP=1 env override must also skip the Mini App
    stack, for CI and minimal deployments that can't pass CLI flags.
    """
    monkeypatch.setenv("DISABLE_MINI_APP", "1")
    assert _should_skip_mini_app(["bot.py"]) is True


def test_should_not_skip_mini_app_with_env_var_unset(monkeypatch):
    monkeypatch.delenv("DISABLE_MINI_APP", raising=False)
    assert _should_skip_mini_app(["bot.py"]) is False


def test_should_not_skip_mini_app_with_env_var_zero(monkeypatch):
    """DISABLE_MINI_APP=0 must NOT skip the Mini App stack."""
    monkeypatch.setenv("DISABLE_MINI_APP", "0")
    assert _should_skip_mini_app(["bot.py"]) is False


def test_old_underscore_form_is_not_a_skip_flag(monkeypatch):
    """The old buggy check looked for --no-mini_app (underscore), which
    is never produced by any other call site. It must NOT be treated as
    a valid skip flag, so that the real documented flag is tested in
    isolation.
    """
    monkeypatch.delenv("DISABLE_MINI_APP", raising=False)
    assert _should_skip_mini_app(["bot.py", "--no-mini_app"]) is False
