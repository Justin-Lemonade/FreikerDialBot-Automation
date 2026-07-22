from __future__ import annotations

from config import Settings
from security import is_admin


def _settings(admin_user_ids: frozenset[int] = frozenset()) -> Settings:
    return Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=admin_user_ids)


def test_denies_when_no_admins_configured():
    assert is_admin(123, _settings(admin_user_ids=frozenset())) is False


def test_denies_unknown_identity():
    assert is_admin(None, _settings(admin_user_ids=frozenset({123}))) is False


def test_denies_user_not_in_allowlist():
    assert is_admin(999, _settings(admin_user_ids=frozenset({123}))) is False


def test_allows_user_in_allowlist():
    assert is_admin(123, _settings(admin_user_ids=frozenset({123, 456}))) is True


def test_same_rule_works_regardless_of_which_frontend_calls_it():
    """The whole point of this module: Telegram (via admin_commands.py)
    and the Mini App (via mini_app_api.py) both call this exact same
    function with just a plain int -- neither needs Telegram-specific
    or Mini-App-specific logic to answer 'is this an admin'."""
    settings = _settings(admin_user_ids=frozenset({42}))
    assert is_admin(42, settings) is True
    assert is_admin(43, settings) is False
