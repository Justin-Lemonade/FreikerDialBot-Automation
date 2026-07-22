"""Authorization policy shared by every frontend.

This is the single place that decides "is this person allowed to do
this," so Telegram and the Mini App enforce the exact same rule instead
of each frontend needing its own copy. Before this module existed,
admin_commands.py had its own is_authorized() check for Telegram, and
the Mini App's /export endpoint had no equivalent check AT ALL -- the
same data one surface protected, the other handed out to anyone who
could reach the port. See BACKLOG.md.

Distinct from telegram_auth.py: that module only answers "did Telegram
really sign this initData" (a low-level protocol/crypto question).
This module answers the actual policy question -- "given a known
Telegram user id, are they allowed to do admin-level things" -- which
both frontends need answered the same way.
"""

from __future__ import annotations

from config import Settings


def is_admin(telegram_user_id: int | None, settings: Settings) -> bool:
    """Deny by default: if no ADMIN_TELEGRAM_USER_IDS are configured, or
    the caller's identity isn't known, nobody is authorized. This is the
    exact rule Telegram's admin commands have always used -- now
    available to any frontend, not just Telegram.
    """
    if telegram_user_id is None or not settings.admin_user_ids:
        return False
    return telegram_user_id in settings.admin_user_ids
