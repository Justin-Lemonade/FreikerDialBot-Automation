"""Shared, frontend-agnostic formatting helpers.

Extracted because the same two duration-formatting rules had been
copy-pasted -- in slightly different styles, but behaviorally identical
-- into statistics_engine.py, session_manager.py, admin_commands.py, and
mini_app_api.py independently. Both Telegram and the Mini App should
render "how long did this take" the same way; this is the one place that
decides that, instead of four.

This module has no dependencies on anything else in the project (no
Database, no Settings) -- it's pure formatting, safe for any frontend or
backend module to import without creating a dependency cycle.
"""

from __future__ import annotations


def format_duration_fine(seconds: int) -> str:
    """Seconds-aware duration text: '0s', '45s', '2m', '2m 18s'.

    Used wherever the duration is often well under a minute -- e.g.
    average time per customer, individual call durations.
    """
    if seconds < 60:
        return f"{seconds}s" if seconds else "0s"
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}m {secs}s" if secs else f"{minutes}m"


def format_duration_coarse(seconds: int) -> str:
    """Minute-granularity duration text: 'less than 1 minute',
    '1 minute', '14 minutes'.

    Used for elapsed/session-level durations where second-level
    precision isn't meaningful to an operator.
    """
    minutes = seconds // 60
    if minutes < 1:
        return "less than 1 minute"
    if minutes == 1:
        return "1 minute"
    return f"{minutes} minutes"


def format_currency(value: str | None) -> str:
    """Render a stored money-ish string (e.g. '784234385.32', already
    cleaned by validation.normalize_money) with thousands separators for
    display: '784234385.32' -> '784,234,385.32'.

    Deliberately display-only: the stored value is never rewritten, so
    this is safe to apply anywhere a customer's balance/monthly
    payment/overdue amount/original loan amount is shown, without
    touching what's actually persisted. Falls back to the raw value
    unchanged for anything that isn't a plain, optionally-decimal
    number (never crashes on messy import data).
    """
    if not value:
        return "—"
    stripped = value.strip()
    negative = stripped.startswith("-")
    body = stripped[1:] if negative else stripped
    if "." in body:
        whole, _, frac = body.partition(".")
    else:
        whole, frac = body, ""
    if not whole.isdigit():
        return value
    grouped = f"{int(whole):,}"
    result = f"{grouped}.{frac}" if frac else grouped
    return f"-{result}" if negative else result


def format_phone_display(phone: str | None) -> str:
    """Render a stored, already-digits-normalized phone number for
    display: '15551234567' -> '+1 (555) 123-4567' for 11-digit US/CA
    numbers, '5551234567' -> '(555) 123-4567' for 10-digit numbers.
    Anything else (international, extensions, malformed) is shown as-is
    -- this is cosmetic only, never a validation step."""
    if not phone:
        return ""
    digits = phone[1:] if phone.startswith("+") else phone
    if not digits.isdigit():
        return phone
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
        return f"+1 ({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
    return phone


def format_loan_number(loan_number: str | None) -> str:
    """Loan numbers are opaque identifiers (see validation.normalize_loan_number)
    -- this exists only so every surface that displays one goes through
    the same (currently pass-through) place, rather than each frontend
    deciding independently whether to reformat it later."""
    return loan_number or "—"


def format_date(iso_timestamp: str | None) -> str:
    """Render a stored ISO 8601 timestamp (e.g. import_timestamp,
    last_edited_timestamp) as a short human date: 'Jul 18, 2026'.
    Returns an em-dash placeholder for missing/unparseable values rather
    than raising, since these fields are often optional."""
    if not iso_timestamp:
        return "—"
    try:
        from datetime import datetime

        return datetime.fromisoformat(iso_timestamp).strftime("%b %d, %Y")
    except ValueError:
        return iso_timestamp
