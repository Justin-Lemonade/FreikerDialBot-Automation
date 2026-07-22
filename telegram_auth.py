"""Validation of Telegram Mini App (WebApp) initData.

Implements Telegram's official signature-check algorithm exactly as
documented at https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
This is the ONLY authentication mechanism used for the Mini App API --
no custom sessions, tokens, or passwords are introduced. A request is
authenticated if and only if it carries an initData string that was
signed by Telegram using the bot's own token, and that signature is
verified here, not trusted from the client.

Algorithm summary:
1. Parse initData as a query string; pull out and remove the 'hash' field.
2. Build data_check_string: remaining fields as "key=value", sorted by
   key, joined with '\\n'.
3. secret_key = HMAC_SHA256(key=b"WebAppData", msg=bot_token)
4. computed_hash = HMAC_SHA256(key=secret_key, msg=data_check_string), hex-encoded.
5. Compare computed_hash to the received hash (constant-time).
6. Optionally reject if auth_date is older than max_age_seconds.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl


class TelegramAuthError(Exception):
    """Raised when initData is missing required fields, has an invalid
    signature, or has expired. Callers should treat this as a hard
    rejection (401), never as "fall back to anonymous" -- claiming to be
    Telegram-authenticated with bad credentials is always an error."""


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int | None = 86400,
) -> dict[str, Any]:
    """Validate a Telegram WebApp initData string and return its parsed
    fields, with 'user' (if present) decoded from JSON into a dict.

    Raises TelegramAuthError if the signature is invalid, required
    fields are missing, or (when max_age_seconds is set) auth_date is
    older than max_age_seconds. Pass max_age_seconds=None to skip the
    freshness check entirely.
    """
    if not init_data:
        raise TelegramAuthError("initData is empty.")
    if not bot_token:
        raise TelegramAuthError("No bot token configured to validate against.")

    pairs = parse_qsl(init_data, strict_parsing=False, keep_blank_values=True)
    data = dict(pairs)

    received_hash = data.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("initData is missing the 'hash' field.")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise TelegramAuthError("initData signature is invalid.")

    if max_age_seconds is not None:
        auth_date = data.get("auth_date")
        if not auth_date:
            raise TelegramAuthError("initData is missing 'auth_date'.")
        try:
            age = time.time() - int(auth_date)
        except ValueError as exc:
            raise TelegramAuthError("initData has a malformed 'auth_date'.") from exc
        if age > max_age_seconds:
            raise TelegramAuthError("initData has expired.")

    result: dict[str, Any] = dict(data)
    result["hash"] = received_hash
    if "user" in data:
        try:
            result["user"] = json.loads(data["user"])
        except json.JSONDecodeError as exc:
            raise TelegramAuthError("initData 'user' field is not valid JSON.") from exc

    return result


def extract_user_id(validated_data: dict[str, Any]) -> int | None:
    """Pull the Telegram user id out of already-validated initData, if
    present. Returns None rather than raising -- a validated initData
    with no 'user' field (e.g. a startup-context init) is still valid,
    just anonymous with respect to per-user attribution."""
    user = validated_data.get("user")
    if isinstance(user, dict) and "id" in user:
        try:
            return int(user["id"])
        except (TypeError, ValueError):
            return None
    return None
