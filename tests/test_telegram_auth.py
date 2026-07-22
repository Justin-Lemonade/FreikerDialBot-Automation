from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import quote

import pytest

from telegram_auth import TelegramAuthError, extract_user_id, validate_init_data


BOT_TOKEN = "123456:FAKE-TOKEN-FOR-TESTS-ONLY"


def _sign(fields: dict[str, str], bot_token: str = BOT_TOKEN) -> str:
    """Build a correctly-signed initData string the way a real Telegram
    client would produce one, so tests exercise the exact same algorithm
    validate_init_data implements (rather than a simplified stand-in)."""
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    all_fields = {**fields, "hash": computed_hash}
    return "&".join(f"{key}={quote(str(value), safe='')}" for key, value in all_fields.items())


def _base_fields(auth_date: int | None = None) -> dict[str, str]:
    user = {"id": 279058397, "first_name": "Ada", "username": "ada_lovelace"}
    return {
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user, separators=(",", ":")),
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
    }


def test_valid_init_data_is_accepted_and_user_id_extracted():
    init_data = _sign(_base_fields())

    result = validate_init_data(init_data, BOT_TOKEN)

    assert result["user"]["id"] == 279058397
    assert extract_user_id(result) == 279058397


def test_tampered_field_is_rejected():
    fields = _base_fields()
    init_data = _sign(fields)
    # Flip a byte in the signed payload after signing -- simulates a
    # client (or attacker) trying to alter data without re-signing it.
    tampered = init_data.replace("query_id=AAHdF6IQAAAAAN0XohDhrOrc", "query_id=AAHdF6IQAAAAAN0XohDhZZZZ")

    with pytest.raises(TelegramAuthError, match="signature is invalid"):
        validate_init_data(tampered, BOT_TOKEN)


def test_wrong_bot_token_is_rejected():
    init_data = _sign(_base_fields())

    with pytest.raises(TelegramAuthError, match="signature is invalid"):
        validate_init_data(init_data, "999999:SOME-OTHER-TOKEN")


def test_missing_hash_is_rejected():
    with pytest.raises(TelegramAuthError, match="missing the 'hash'"):
        validate_init_data("query_id=abc&auth_date=123", BOT_TOKEN)


def test_empty_init_data_is_rejected():
    with pytest.raises(TelegramAuthError, match="empty"):
        validate_init_data("", BOT_TOKEN)


def test_expired_auth_date_is_rejected_when_max_age_set():
    stale_timestamp = int(time.time()) - 10_000
    init_data = _sign(_base_fields(auth_date=stale_timestamp))

    with pytest.raises(TelegramAuthError, match="expired"):
        validate_init_data(init_data, BOT_TOKEN, max_age_seconds=3600)


def test_old_auth_date_is_accepted_when_freshness_check_disabled():
    stale_timestamp = int(time.time()) - 10_000
    init_data = _sign(_base_fields(auth_date=stale_timestamp))

    result = validate_init_data(init_data, BOT_TOKEN, max_age_seconds=None)

    assert result["auth_date"] == str(stale_timestamp)


def test_extract_user_id_returns_none_when_no_user_field():
    fields = {"query_id": "abc", "auth_date": str(int(time.time()))}
    init_data = _sign(fields)

    result = validate_init_data(init_data, BOT_TOKEN)

    assert extract_user_id(result) is None
