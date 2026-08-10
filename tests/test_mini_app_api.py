import hashlib
import hmac
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

import pytest

import mini_app_api
from backend import build_backend
from config import Settings
from database import Database
from mini_app_api import MiniAppAPI, MiniAppService, create_service

TEST_BOT_TOKEN = "123456:TEST-TOKEN-FOR-AUTH-TESTS-ONLY"
TEST_ADMIN_USER_ID = 999999001


@pytest.fixture()
def authenticated_api_server(tmp_path: Path):
    """Like api_server, but with a known bot_token AND a known admin
    allowlist configured directly (bypassing create_service()'s
    real-settings load), so auth/authorization tests are self-contained
    and don't depend on real environment values."""
    db_path = tmp_path / "mini_app_auth.db"
    database = Database(path=db_path)
    settings = Settings(
        telegram_bot_token=TEST_BOT_TOKEN,
        openai_api_key=None,
        admin_user_ids=frozenset({TEST_ADMIN_USER_ID}),
    )
    backend = build_backend(settings=settings, database=database)
    service = MiniAppService(backend=backend)
    api = MiniAppAPI(service)
    server = api.create_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield server, service
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture()
def api_server(tmp_path: Path):
    db_path = tmp_path / "mini_app.db"
    database = Database(path=db_path)
    backend = build_backend(database=database)
    service = create_service(backend=backend)
    api = MiniAppAPI(service)
    server = api.create_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield server, service
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _request_json(
    server,
    path: str,
    method: str = "GET",
    payload: dict | None = None,
    service=None,
    authenticated: bool = True,
):
    """authenticated=True (the default) signs a valid initData header
    using service.bot_token, since every endpoint now requires one --
    see the security remediation pass in MINI_APP_API.md. Pass
    service=None (or authenticated=False) for the handful of tests that
    specifically exercise unauthenticated/anonymous behavior."""
    host, port = server.server_address
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if authenticated and service is not None:
        fields = {
            "query_id": "test-query",
            "user": json.dumps({"id": 900000001, "first_name": "Test"}, separators=(",", ":")),
            "auth_date": str(int(time.time())),
        }
        headers["Authorization"] = f"tma {_sign_init_data(service.bot_token, fields)}"
    req = urllib.request.Request(
        f"http://{host}:{port}{path}",
        method=method,
        data=data,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        body = response.read().decode("utf-8")
        return response.status, json.loads(body)


def test_minimal_mini_app_flow(api_server):
    server, service = api_server
    service.database.insert_customers(
        [
            {
                "loan_number": "loan-001",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "phone_numbers": ["+15550000001"],
                "balance": "100",
                "days_overdue": "3",
            }
        ]
    )

    status, current_session = _request_json(server, "/session/current", service=service)
    assert status == 200
    assert current_session["customerCount"] >= 1

    status, current_customer = _request_json(server, "/customer/current", service=service)
    assert status == 200
    assert current_customer["loan_number"] == "loan-001"

    status, started = _request_json(server, "/call/start", method="POST", payload={"customerId": current_customer["id"]}, service=service)
    assert status == 200
    assert started["ok"] is True

    status, result = _request_json(
        server,
        "/call/result",
        method="POST",
        payload={"customerId": current_customer["id"], "outcome": "answered"},
    service=service,
    )
    assert status == 200
    assert result["outcome"] == "answered"

    status, stats = _request_json(server, "/statistics", service=service)
    assert status == 200
    assert stats["today"]["customers_contacted"] >= 1


def test_get_endpoints_do_not_mutate_queue_state(api_server):
    """GET requests are display-only: repeatedly polling /customer/current
    must not advance the queue or commit a 'current' customer. Regression
    test for the bug where get_current_customer/get_current_session used
    to call the committing next_customer() as their fallback."""
    server, service = api_server
    service.database.insert_customers(
        [
            {"loan_number": "peek-1", "first_name": "Pat", "last_name": "One",
             "phone_numbers": ["+15550000001"], "balance": "10", "days_overdue": "1"},
            {"loan_number": "peek-2", "first_name": "Pat", "last_name": "Two",
             "phone_numbers": ["+15550000002"], "balance": "20", "days_overdue": "2"},
        ]
    )

    for _ in range(3):
        status, customer = _request_json(server, "/customer/current", service=service)
        assert status == 200
        assert customer["loan_number"] == "peek-1"

    queue_state = service.database.get_queue_session()
    assert queue_state["current_customer_id"] is None


def test_call_result_advances_queue_exactly_once_and_persists_duration(api_server):
    """A single /call/result should both apply the outcome AND surface the
    next customer, so the frontend never needs a separate advance call
    that would otherwise skip an extra customer."""
    server, service = api_server
    service.database.insert_customers(
        [
            {"loan_number": "dur-1", "first_name": "Dee", "last_name": "One",
             "phone_numbers": ["+15550000003"], "balance": "10", "days_overdue": "1"},
            {"loan_number": "dur-2", "first_name": "Dee", "last_name": "Two",
             "phone_numbers": ["+15550000004"], "balance": "20", "days_overdue": "2"},
        ]
    )

    _, current = _request_json(server, "/customer/current", service=service)
    assert current["loan_number"] == "dur-1"

    status, result = _request_json(
        server,
        "/call/result",
        method="POST",
        payload={"customerId": current["id"], "outcome": "answered", "duration": 42},
    service=service,
    )
    assert status == 200
    assert result["nextCustomer"]["loan_number"] == "dur-2"

    with service.database.connect() as conn:
        row = conn.execute(
            "SELECT duration_seconds FROM customer_events WHERE event_type = 'customer_warned'"
        ).fetchone()
    assert row["duration_seconds"] == 42


def test_call_back_requeues_did_not_answer_customers(api_server):
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "cb-1", "first_name": "Cal", "last_name": "Back",
          "phone_numbers": ["+15550000005"], "balance": "10", "days_overdue": "1"}]
    )
    _, current = _request_json(server, "/customer/current", service=service)
    _request_json(
        server, "/call/result", method="POST",
        payload={"customerId": current["id"], "outcome": "did_not_answer"},
    service=service,
    )
    assert service.database.status_counts()["call_later"] == 1

    status, _result = _request_json(server, "/queue/call-back", method="POST", service=service)
    assert status == 200
    assert service.database.status_counts()["call_later"] == 0
    assert service.database.status_counts()["waiting"] == 1


def test_settings_endpoint_defaults_to_unlimited_and_auto_advance_on(api_server):
    """No setting has ever been written -- must report the same defaults
    the app has always behaved as (unlimited attempts, auto-advance on),
    not None/undefined."""
    server, service = api_server
    status, settings = _request_json(server, "/settings", service=service)
    assert status == 200
    assert settings == {"maxCallAttempts": None, "autoAdvance": True}


def test_settings_endpoint_persists_max_call_attempts(api_server):
    server, service = api_server
    status, result = _request_json(
        server, "/settings", method="POST", payload={"maxCallAttempts": 2}, service=service
    )
    assert status == 200
    assert result == {"ok": True, "settings": {"maxCallAttempts": 2, "autoAdvance": True}}

    # Persists across a fresh read, not just the response echo.
    status, settings = _request_json(server, "/settings", service=service)
    assert status == 200
    assert settings["maxCallAttempts"] == 2


def test_settings_endpoint_rejects_invalid_max_call_attempts(api_server):
    server, service = api_server
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _request_json(server, "/settings", method="POST", payload={"maxCallAttempts": 0}, service=service)
    assert exc_info.value.code == 400

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _request_json(
            server, "/settings", method="POST", payload={"maxCallAttempts": "not-a-number"}, service=service
        )
    assert exc_info.value.code == 400


def test_settings_endpoint_can_set_unlimited_again(api_server):
    server, service = api_server
    _request_json(server, "/settings", method="POST", payload={"maxCallAttempts": 1}, service=service)
    status, result = _request_json(
        server, "/settings", method="POST", payload={"maxCallAttempts": None}, service=service
    )
    assert status == 200
    assert result["settings"]["maxCallAttempts"] is None


def test_call_back_respects_max_call_attempts_limit(api_server):
    """Core enforcement: once a customer's attempt_count reaches the
    configured cap, "Call Back" must stop requeuing them -- they stay
    call_later (exhausted) instead of cycling forever."""
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "attempt-cap-1", "first_name": "Max", "last_name": "Attempts",
          "phone_numbers": ["+15550000099"], "balance": "10", "days_overdue": "1"}]
    )
    _request_json(server, "/settings", method="POST", payload={"maxCallAttempts": 2}, service=service)

    def mark_did_not_answer():
        _, current = _request_json(server, "/customer/current", service=service)
        _request_json(
            server, "/call/result", method="POST",
            payload={"customerId": current["id"], "outcome": "did_not_answer"},
            service=service,
        )

    # Attempt 1: call_later, then requeued by Call Back (1 < 2).
    mark_did_not_answer()
    assert service.database.status_counts()["call_later"] == 1
    status, _ = _request_json(server, "/queue/call-back", method="POST", service=service)
    assert status == 200
    assert service.database.status_counts()["waiting"] == 1
    assert service.database.status_counts()["call_later"] == 0

    # Attempt 2 reaches the cap (attempt_count == 2 == max): Call Back
    # must NOT requeue this customer again.
    mark_did_not_answer()
    assert service.database.status_counts()["call_later"] == 1
    status, _ = _request_json(server, "/queue/call-back", method="POST", service=service)
    assert status == 200
    assert service.database.status_counts()["call_later"] == 1
    assert service.database.status_counts()["waiting"] == 0


def test_customer_payload_exposes_every_phone_number(api_server):
    """UI pass 3: the main call workflow needs access to both phone
    numbers, not just the single first-non-blacklisted one `phone` has
    always carried. `phones` must list every number on file, in stored
    order, each with its own blacklist status."""
    server, service = api_server
    service.database.insert_customers(
        [
            {
                "loan_number": "two-phones-1",
                "first_name": "Two",
                "last_name": "Phones",
                "phone_numbers": ["+15550001111", "+15550002222"],
                "balance": "100",
                "days_overdue": "3",
            }
        ]
    )
    status, current = _request_json(server, "/customer/current", service=service)
    assert status == 200
    assert current["phones"] == [
        {"number": "+15550001111", "isBlacklisted": False},
        {"number": "+15550002222", "isBlacklisted": False},
    ]
    # Backward-compatible single-phone field is unchanged.
    assert current["phone"] == "+15550001111"


def test_customer_payload_flags_blacklisted_phones_individually(api_server):
    server, service = api_server
    service.database.insert_customers(
        [
            {
                "loan_number": "two-phones-2",
                "first_name": "Partly",
                "last_name": "Blacklisted",
                "phone_numbers": ["+15550003333", "+15550004444"],
                "balance": "100",
                "days_overdue": "3",
            }
        ]
    )
    service.database.blacklist_phone("+15550003333")

    status, current = _request_json(server, "/customer/current", service=service)
    assert status == 200
    assert current["phones"] == [
        {"number": "+15550003333", "isBlacklisted": True},
        {"number": "+15550004444", "isBlacklisted": False},
    ]
    # The single `phone` field skips the blacklisted number.
    assert current["phone"] == "+15550004444"


def test_export_requires_admin_authorization(authenticated_api_server):
    """SECURITY regression test: anonymous requests (401, no credentials
    at all -- caught by the general auth gate before /export's own admin
    check even runs) and requests from a validated-but-non-admin
    Telegram user (403, real credentials but the wrong role) must both
    be rejected. This endpoint hands out every customer's PII -- it
    needs the same gate Telegram's /export command has always had.
    See BACKLOG.md."""
    server, service = authenticated_api_server
    service.database.insert_customers(
        [{"loan_number": "exp-1", "first_name": "Ex", "last_name": "Port",
          "phone_numbers": ["+15550000006"], "balance": "10", "days_overdue": "1"}]
    )
    host, port = server.server_address

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"http://{host}:{port}/export?format=csv", timeout=5)
    assert exc_info.value.code == 401

    fields = {
        "query_id": "q",
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": 1010101, "first_name": "NotAdmin"}, separators=(",", ":")),
    }
    init_data = _sign_init_data(service.bot_token, fields)
    req = urllib.request.Request(
        f"http://{host}:{port}/export?format=csv",
        headers={"Authorization": f"tma {init_data}"},
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    assert exc_info.value.code == 403


def test_denied_export_is_audit_logged(authenticated_api_server):
    """Mirrors admin_commands.py's own denied-attempt logging for the
    Telegram bot's /export -- the Mini App's export gate previously
    only logged a successful export, leaving repeated unauthorized
    attempts from the Mini App side with no trace at all."""
    server, service = authenticated_api_server
    host, port = server.server_address
    fields = {
        "query_id": "q",
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": 2020202, "first_name": "StillNotAdmin"}, separators=(",", ":")),
    }
    init_data = _sign_init_data(service.bot_token, fields)
    req = urllib.request.Request(
        f"http://{host}:{port}/export?format=csv",
        headers={"Authorization": f"tma {init_data}"},
    )
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(req, timeout=5)

    with service.database.connect() as conn:
        latest_event = conn.execute(
            "SELECT event_type, telegram_user_id, notes FROM customer_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert latest_event["event_type"] == "admin_action_denied"
    assert latest_event["telegram_user_id"] == 2020202
    assert latest_event["notes"] == "export"


def test_export_succeeds_for_authenticated_admin_and_is_audited(authenticated_api_server):
    server, service = authenticated_api_server
    service.database.insert_customers(
        [{"loan_number": "exp-1", "first_name": "Ex", "last_name": "Port",
          "phone_numbers": ["+15550000006"], "balance": "10", "days_overdue": "1"}]
    )
    fields = {
        "query_id": "q",
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": TEST_ADMIN_USER_ID, "first_name": "Admin"}, separators=(",", ":")),
    }
    init_data = _sign_init_data(service.bot_token, fields)
    host, port = server.server_address
    req = urllib.request.Request(
        f"http://{host}:{port}/export?format=csv",
        headers={"Authorization": f"tma {init_data}"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        assert response.status == 200
        assert "csv" in response.headers.get("Content-Type", "")
        body = response.read().decode("utf-8")
        assert "exp-1" in body

    with service.database.connect() as conn:
        row = conn.execute(
            "SELECT telegram_user_id, notes FROM customer_events WHERE event_type = 'admin_action'"
        ).fetchone()
    assert row["telegram_user_id"] == TEST_ADMIN_USER_ID
    assert row["notes"] == "export:csv"


def test_pause_endpoint_pauses_the_queue(api_server):
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "pause-1", "first_name": "Pau", "last_name": "Se",
          "phone_numbers": ["+15550000007"], "balance": "10", "days_overdue": "1"}]
    )
    status, result = _request_json(server, "/queue/pause", method="POST", service=service)
    assert status == 200
    assert result["paused"] is True
    assert service.database.get_queue_session()["is_paused"] == 1


def test_resume_endpoint_resumes_the_queue(api_server):
    """POST /queue/resume was added because QueueEngine.resume() already
    existed but had no Mini App route -- Commands' Pause Queue had
    nothing to toggle back to."""
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "resume-1", "first_name": "Re", "last_name": "Sume",
          "phone_numbers": ["+15550000008"], "balance": "10", "days_overdue": "1"}]
    )
    _request_json(server, "/queue/pause", method="POST", service=service)
    assert service.database.get_queue_session()["is_paused"] == 1

    status, result = _request_json(server, "/queue/resume", method="POST", service=service)
    assert status == 200
    assert result["paused"] is False
    assert service.database.get_queue_session()["is_paused"] == 0


def test_session_current_reports_is_paused(api_server):
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "is-paused-1", "first_name": "Is", "last_name": "Paused",
          "phone_numbers": ["+15550000009"], "balance": "10", "days_overdue": "1"}]
    )
    status, session = _request_json(server, "/session/current", service=service)
    assert status == 200
    assert session["isPaused"] is False

    _request_json(server, "/queue/pause", method="POST", service=service)
    status, session = _request_json(server, "/session/current", service=service)
    assert status == 200
    assert session["isPaused"] is True


def test_mini_app_never_surfaces_a_blacklisted_customer(api_server):
    """The Mini App must never show a blacklisted customer as current/
    next -- it calls the exact same QueueEngine.peek_next_customer()
    Telegram uses, so there's no separate filtering path to get wrong."""
    server, service = api_server
    service.database.insert_customers(
        [
            {"loan_number": "bl-a", "first_name": "First", "last_name": "Blocked",
             "phone_numbers": ["+15550000020"], "balance": "10", "days_overdue": "1"},
            {"loan_number": "bl-b", "first_name": "Second", "last_name": "Ok",
             "phone_numbers": ["+15550000021"], "balance": "10", "days_overdue": "1"},
        ]
    )
    blocked_id = service.database.get_customer(1)["id"]
    service.database.set_customer_blacklisted(blocked_id, True)

    status, customer = _request_json(server, "/customer/current", service=service)
    assert status == 200
    assert customer["loanNumber"] == "bl-b"

    status, session = _request_json(server, "/session/current", service=service)
    assert session["currentCustomer"]["loanNumber"] == "bl-b"


def test_mini_app_phone_blacklist_falls_back_like_telegram_does(api_server):
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "fb-1", "first_name": "Fall", "last_name": "Back",
          "phone_numbers": ["111", "222"], "balance": "10", "days_overdue": "1"}]
    )
    service.database.blacklist_phone("111")

    status, customer = _request_json(server, "/customer/current", service=service)
    assert status == 200
    assert customer["phone"] == "222"


def test_queue_upcoming_endpoint_previews_next_customer(api_server):
    server, service = api_server
    service.database.insert_customers(
        [
            {"loan_number": "up-1", "first_name": "First", "last_name": "One",
             "phone_numbers": ["+15550000030"], "balance": "10", "days_overdue": "1"},
            {"loan_number": "up-2", "first_name": "Second", "last_name": "Two",
             "phone_numbers": ["+15550000031"], "balance": "10", "days_overdue": "1"},
        ]
    )
    _, current = _request_json(server, "/customer/current", service=service)
    _request_json(server, "/call/start", method="POST", payload={"customerId": current["id"]}, service=service)

    status, upcoming = _request_json(server, "/queue/upcoming", service=service)
    assert status == 200
    assert upcoming["loanNumber"] == "up-2"


def test_customer_search_endpoint(api_server):
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "srch-1", "first_name": "Sasha", "last_name": "One",
          "phone_numbers": ["+15550000010"], "balance": "10", "days_overdue": "1"}]
    )
    status, result = _request_json(server, "/customer/search?q=Sasha", service=service)
    assert status == 200
    assert [r["loan_number"] for r in result["results"]] == ["srch-1"]


def test_customer_record_endpoint(api_server):
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "rec-1", "first_name": "Rex", "last_name": "One",
          "phone_numbers": ["+15550000011"], "balance": "10", "days_overdue": "1"}]
    )
    customer_id = service.database.get_customer(1)["id"]

    status, record = _request_json(server, f"/customer/record?id={customer_id}", service=service)
    assert status == 200
    assert record["loan_number"] == "rec-1"
    assert record["history"] == []
    assert record["notes"] == []


def test_customer_record_endpoint_404_for_missing_customer(api_server):
    server, service = api_server
    fields = {"query_id": "q", "auth_date": str(int(time.time())),
              "user": json.dumps({"id": 900000002, "first_name": "T"}, separators=(",", ":"))}
    init_data = _sign_init_data(service.bot_token, fields)
    host, port = server.server_address
    req = urllib.request.Request(
        f"http://{host}:{port}/customer/record?id=9999",
        headers={"Authorization": f"tma {init_data}"},
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    assert exc_info.value.code == 404


def test_customer_edit_endpoint(api_server):
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "edit-1", "first_name": "Ed", "last_name": "One",
          "phone_numbers": ["+15550000012"], "balance": "10", "days_overdue": "1"}]
    )
    customer_id = service.database.get_customer(1)["id"]

    status, result = _request_json(
        server, "/customer/edit", method="POST",
        payload={"customerId": customer_id, "fields": {"balance": "500"}},
    service=service,
    )
    assert status == 200
    assert result["ok"] is True
    assert result["customer"]["balance"] == "500"
    assert service.database.get_customer(customer_id)["balance"] == "500"


def test_customer_blacklist_endpoint(api_server):
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "bl-1", "first_name": "Bea", "last_name": "One",
          "phone_numbers": ["+15550000013"], "balance": "10", "days_overdue": "1"}]
    )
    customer_id = service.database.get_customer(1)["id"]

    status, result = _request_json(
        server, "/customer/blacklist", method="POST",
        payload={"customerId": customer_id, "blacklisted": True},
    service=service,
    )
    assert status == 200
    assert result["customer"]["isBlacklisted"] is True

    status, result = _request_json(
        server, "/customer/blacklist", method="POST",
        payload={"customerId": customer_id, "blacklisted": False},
    service=service,
    )
    assert result["customer"]["isBlacklisted"] is False


def test_phone_blacklist_endpoint(api_server):
    server, service = api_server
    status, result = _request_json(
        server, "/phone/blacklist", method="POST",
        payload={"phone": "+15550009999", "blacklisted": True, "reason": "abuse"},
    service=service,
    )
    assert status == 200
    assert result["blacklisted"] is True
    assert service.database.is_phone_blacklisted("+15550009999") is True

    status, result = _request_json(
        server, "/phone/blacklist", method="POST",
        payload={"phone": "+15550009999", "blacklisted": False},
    service=service,
    )
    assert service.database.is_phone_blacklisted("+15550009999") is False


def test_session_completes_automatically_and_does_not_spawn_a_new_one(api_server):
    """Regression test: completing a session via the Mini App must
    finalize it (duration_seconds, status='completed') AND must not
    cause the next poll to spin up a brand-new session just because
    total_customers is still > 0."""
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "fin-1", "first_name": "Fin", "last_name": "Ish",
          "phone_numbers": ["+15550000008"], "balance": "10", "days_overdue": "1"}]
    )
    _, current = _request_json(server, "/customer/current", service=service)
    status, result = _request_json(
        server, "/call/result", method="POST",
        payload={"customerId": current["id"], "outcome": "answered"},
    service=service,
    )
    assert status == 200
    assert result["session"]["completed"] is True

    with service.database.connect() as conn:
        row = conn.execute("SELECT status FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
    assert row["status"] == "completed"

    for _ in range(3):
        _request_json(server, "/session/current", service=service)

    with service.database.connect() as conn:
        session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert session_count == 1


def _sign_init_data(bot_token: str, fields: dict[str, str]) -> str:
    """Build a correctly-signed initData string using the real algorithm
    (see telegram_auth.py), so these HTTP-level tests exercise the actual
    wire format instead of a simplified stand-in."""
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    all_fields = {**fields, "hash": computed_hash}
    return "&".join(f"{key}={quote(str(value), safe='')}" for key, value in all_fields.items())


def test_authenticated_request_threads_telegram_user_id_into_events(authenticated_api_server):
    server, service = authenticated_api_server
    service.database.insert_customers(
        [{"loan_number": "auth-1", "first_name": "Au", "last_name": "Then",
          "phone_numbers": ["+15550000009"], "balance": "10", "days_overdue": "1"}]
    )
    _, current = _request_json(server, "/customer/current", service=service)

    fields = {
        "query_id": "test-query",
        "user": json.dumps({"id": 42424242, "first_name": "Op"}, separators=(",", ":")),
        "auth_date": str(int(time.time())),
    }
    init_data = _sign_init_data(service.bot_token, fields)

    host, port = server.server_address
    req = urllib.request.Request(
        f"http://{host}:{port}/call/result",
        method="POST",
        data=json.dumps({"customerId": current["id"], "outcome": "answered"}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"tma {init_data}"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        assert response.status == 200

    with service.database.connect() as conn:
        row = conn.execute(
            "SELECT telegram_user_id FROM customer_events WHERE event_type = 'customer_warned'"
        ).fetchone()
    assert row["telegram_user_id"] == 42424242


def test_invalid_init_data_is_rejected_with_401(authenticated_api_server):
    server, service = authenticated_api_server
    host, port = server.server_address
    req = urllib.request.Request(
        f"http://{host}:{port}/statistics",
        headers={"Authorization": "tma bogus=data&hash=deadbeef"},
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    assert exc_info.value.code == 401


def test_missing_credentials_are_rejected_by_default(api_server):
    """As of the security remediation pass: a request with no
    Authorization header at all gets a hard 401 by default. See
    MINI_APP_API.md -- the frontend was confirmed to always send the
    header when running inside real Telegram (client.ts), and the
    startup-timing race this used to be deferred for doesn't actually
    exist given index.html's script ordering (telegram-web-app.js loads
    synchronously in <head>, before the app's own module script)."""
    server, _service = api_server
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}/statistics")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    assert exc_info.value.code == 401


def test_anonymous_access_allowed_only_when_explicitly_enabled(tmp_path: Path):
    """mini_app_allow_anonymous is an explicit, off-by-default escape
    hatch for local browser testing outside a real Telegram client (no
    initData exists at all in that case). It must be opted into, not
    just assumed -- this test builds a service with it turned on and
    confirms *that* is what lets an unauthenticated request through,
    not some accidental default."""
    db_path = tmp_path / "mini_app_anon.db"
    database = Database(path=db_path)
    settings = Settings(
        telegram_bot_token=TEST_BOT_TOKEN,
        openai_api_key=None,
        mini_app_allow_anonymous=True,
    )
    backend = build_backend(settings=settings, database=database)
    service = MiniAppService(backend=backend)
    api = MiniAppAPI(service)
    server = api.create_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, result = _request_json(server, "/statistics", service=service)
        assert status == 200
        assert "today" in result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_verified_init_data_without_user_field_is_still_allowed(authenticated_api_server):
    """A signed, cryptographically-valid initData payload with no "user"
    field (a legitimate startup-context init, per extract_user_id's own
    docstring) proves the request genuinely came from Telegram even
    though it can't be attributed to a specific user -- it must NOT be
    treated the same as a request with no Authorization header at all."""
    server, service = authenticated_api_server
    fields = {"query_id": "test-query", "auth_date": str(int(time.time()))}
    init_data = _sign_init_data(service.bot_token, fields)

    host, port = server.server_address
    req = urllib.request.Request(
        f"http://{host}:{port}/statistics",
        headers={"Authorization": f"tma {init_data}"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        assert response.status == 200


def test_export_still_requires_admin_even_with_anonymous_allowed(tmp_path: Path):
    """mini_app_allow_anonymous must only widen the default-deny
    endpoints, never bypass /export's separate, stricter admin check --
    the dev convenience flag for local testing shouldn't accidentally
    reopen the admin-only export hole this same remediation pass would
    otherwise be closing everywhere else."""
    db_path = tmp_path / "mini_app_anon_export.db"
    database = Database(path=db_path)
    settings = Settings(
        telegram_bot_token=TEST_BOT_TOKEN,
        openai_api_key=None,
        mini_app_allow_anonymous=True,
    )
    backend = build_backend(settings=settings, database=database)
    service = MiniAppService(backend=backend)
    api = MiniAppAPI(service)
    server = api.create_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        req = urllib.request.Request(f"http://{host}:{port}/export?format=json")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        assert exc_info.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_static_frontend_and_api_are_served_from_the_same_origin(tmp_path: Path):
    """Confirmed live during the launch-path fix: mini_app_api.py must
    serve the built frontend (via MINI_APP_STATIC_DIR) AND the API from
    the same process/port -- this is what makes the single ngrok tunnel
    (see start_mini_app.py) actually work as a Mini App, since Telegram
    only gets one URL. Builds a minimal fake 'dist' dir rather than
    running a real `npm run build` (which the frontend test suite,
    if one existed, would own) -- this test is specifically about
    mini_app_api.py's _serve_static, not the frontend build itself.
    """
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text(
        "<!doctype html><html><body><div id='root'>REAL_BUILT_APP_MARKER</div></body></html>"
    )

    db_path = tmp_path / "static_test.db"
    database = Database(path=db_path)
    settings = Settings(
        telegram_bot_token=TEST_BOT_TOKEN,
        openai_api_key=None,
        mini_app_static_dir=dist_dir,
    )
    backend = build_backend(settings=settings, database=database)
    service = MiniAppService(backend=backend)
    api = MiniAppAPI(service)
    server = api.create_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        with urllib.request.urlopen(f"http://{host}:{port}/", timeout=5) as resp:
            assert resp.status == 200
            body = resp.read().decode("utf-8")
            assert "REAL_BUILT_APP_MARKER" in body

        # Same server, same port: confirm the API still works too --
        # this IS the same-origin proof, not a separate concern.
        status, result = _request_json(server, "/session/current", service=service)
        assert status == 200
        assert "customerCount" in result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_duplicate_call_result_submission_does_not_double_record(api_server):
    """Confirmed live this pass: submitting the same outcome twice for a
    customer who's already been handled (e.g. a double-tap, or a retry
    after a slow/uncertain network response) must not double-count
    statistics or record a second event. This works today because
    QueueEngine.apply_action() only processes customers whose status is
    still 'waiting'/'needs_review' -- once handled, a repeat call is a
    safe no-op that just returns the current queue state again, not
    because of any explicit idempotency-key mechanism.
    """
    server, service = api_server
    service.database.insert_customers(
        [
            {
                "loan_number": "loan-dup-001",
                "first_name": "Nora",
                "last_name": "Newton",
                "phone_numbers": ["+15550009001"],
                "balance": "500",
                "days_overdue": "5",
            }
        ]
    )
    session_before = _request_json(server, "/session/current", service=service)[1]
    first_customer_id = session_before["currentCustomer"]["id"]

    first_status, first_result = _request_json(
        server,
        "/call/result",
        method="POST",
        payload={"customerId": first_customer_id, "outcome": "contacted", "duration": 10},
    service=service,
    )
    assert first_status == 200
    assert first_result["ok"] is True

    second_status, second_result = _request_json(
        server,
        "/call/result",
        method="POST",
        payload={"customerId": first_customer_id, "outcome": "contacted", "duration": 999},
    service=service,
    )
    assert second_status == 200
    assert second_result["ok"] is True
    # Critically: the duplicate must NOT re-advance or double-count --
    # both responses must agree on who's current now.
    assert second_result["session"]["currentCustomerIndex"] == first_result["session"]["currentCustomerIndex"]
    assert second_result["session"]["progress"]["contacted"] == first_result["session"]["progress"]["contacted"]

    events = service.database.get_customer_events(int(first_customer_id))
    warned_events = [e for e in events if e["event_type"] == "customer_warned"]
    assert len(warned_events) == 1
    assert warned_events[0]["duration_seconds"] == 10  # the FIRST duration, not the duplicate's 999


def test_customer_payload_skips_blacklisted_phone(api_server):
    """_customer_payload must return a non-blacklisted phone when the
    customer's primary phone is blacklisted -- the Mini App should never
    show a blacklisted number as the contact phone."""
    server, service = api_server
    service.database.insert_customers(
        [
            {
                "loan_number": "loan-bl-001",
                "first_name": "Blake",
                "last_name": "Listed",
                "phone_numbers": ["+15550009991", "+15550009992"],
                "balance": "200",
                "days_overdue": "10",
            }
        ]
    )
    # Blacklist the primary phone
    service.database.blacklist_phone("+15550009991")

    # Get the customer payload via the API
    status, session = _request_json(server, "/session/current", service=service)
    assert status == 200
    customer = session["currentCustomer"]
    assert customer is not None
    # The payload should show the non-blacklisted phone, not the blacklisted one
    assert customer["phone"] == "+15550009992"
    assert customer["phone"] != "+15550009991"


def _request_with_origin(server, path: str, origin: str | None, service=None):
    """Raw request (bypassing _request_json) so the test can set an
    Origin header and inspect the response's own headers -- what CORS
    restriction actually needs to verify."""
    host, port = server.server_address
    headers = {}
    if origin is not None:
        headers["Origin"] = origin
    if service is not None:
        fields = {
            "query_id": "test-query",
            "user": json.dumps({"id": 900000001, "first_name": "Test"}, separators=(",", ":")),
            "auth_date": str(int(time.time())),
        }
        headers["Authorization"] = f"tma {_sign_init_data(service.bot_token, fields)}"
    req = urllib.request.Request(f"http://{host}:{port}{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=5) as response:
        return response, response.headers.get("Access-Control-Allow-Origin")


class TestCorsRestriction:
    """Access-Control-Allow-Origin used to be an unconditional '*'.
    settings.mini_app_allowed_origins (config.py) now scopes it to the
    Mini App's own real URL plus the Vite dev server -- these tests
    verify the header is only ever echoed for an allowed Origin, and
    omitted (not '*', not silently allowed) for anything else."""

    def test_allowed_origin_is_echoed_back(self, api_server):
        server, service = api_server
        # http://localhost:5173 (the Vite dev server) is always in the
        # default allowlist regardless of mini_app_url -- see
        # Settings.mini_app_allowed_origins.
        _response, cors_header = _request_with_origin(server, "/session/current", "http://localhost:5173", service=service)
        assert cors_header == "http://localhost:5173"

    def test_disallowed_origin_gets_no_cors_header(self, api_server):
        server, service = api_server
        _response, cors_header = _request_with_origin(server, "/session/current", "http://evil.example.com", service=service)
        assert cors_header is None

    def test_no_origin_header_gets_no_cors_header(self, api_server):
        server, service = api_server
        _response, cors_header = _request_with_origin(server, "/session/current", None, service=service)
        assert cors_header is None

    def test_cors_header_is_never_a_wildcard(self, api_server):
        server, service = api_server
        _response, cors_header = _request_with_origin(server, "/session/current", "http://localhost:5173", service=service)
        assert cors_header != "*"

    def test_allowed_origin_response_has_vary_origin(self, api_server):
        """Whenever a specific (non-'*') origin is echoed, the response
        must also carry Vary: Origin so a shared cache cannot serve one
        origin's CORS-enabled, customer-data response to a different
        origin -- the ACAO header is origin-dependent, and caches key on
        Vary to keep that true."""
        server, service = api_server
        response, cors_header = _request_with_origin(server, "/session/current", "http://localhost:5173", service=service)
        assert cors_header == "http://localhost:5173"
        assert response.headers.get("Vary") == "Origin"

    def test_disallowed_origin_gets_no_cors_or_vary_header(self, api_server):
        """No ACAO means no Vary: Origin either -- both are only emitted
        together when an origin is actually echoed."""
        server, service = api_server
        response, cors_header = _request_with_origin(server, "/session/current", "http://evil.example.com", service=service)
        assert cors_header is None
        assert response.headers.get("Vary") is None


class TestAllowedOriginsSetting:
    def test_defaults_include_the_vite_dev_server(self):
        settings = Settings(telegram_bot_token=TEST_BOT_TOKEN, openai_api_key=None)
        assert "http://localhost:5173" in settings.mini_app_allowed_origins
        assert "http://127.0.0.1:5173" in settings.mini_app_allowed_origins

    def test_includes_the_configured_mini_app_url(self):
        settings = Settings(
            telegram_bot_token=TEST_BOT_TOKEN,
            openai_api_key=None,
            mini_app_url="https://example.ngrok-free.app/some/path",
        )
        assert "https://example.ngrok-free.app" in settings.mini_app_allowed_origins

    def test_includes_extra_configured_origins(self):
        settings = Settings(
            telegram_bot_token=TEST_BOT_TOKEN,
            openai_api_key=None,
            mini_app_extra_allowed_origins=frozenset({"https://custom.example.com"}),
        )
        assert "https://custom.example.com" in settings.mini_app_allowed_origins

    def test_does_not_include_an_arbitrary_origin(self):
        settings = Settings(telegram_bot_token=TEST_BOT_TOKEN, openai_api_key=None)
        assert "https://evil.example.com" not in settings.mini_app_allowed_origins


class TestImportEndpoint:
    """POST /import -- the Mini App previously had no import capability
    of its own (importing was Telegram-only). This runs the same real
    Importer pipeline (self.backend.importer) as the bot's /upload,
    JSON-file, and Excel-file handlers, not a separate reimplementation.
    """

    def test_import_json_inserts_customers(self, api_server):
        server, service = api_server
        payload = {
            "format": "json",
            "data": json.dumps(
                [
                    {"loan_number": "mi-1", "first_name": "Mini", "last_name": "App",
                     "phone_numbers": ["+15550001111"], "balance": "100", "days_overdue": "5"},
                ]
            ),
        }
        status, result = _request_json(server, "/import", method="POST", payload=payload, service=service)
        assert status == 200
        assert result["ok"] is True
        assert result["importedCount"] == 1
        assert service.database.count_customers() == 1

    def test_import_json_creates_a_session(self, api_server):
        server, service = api_server
        payload = {
            "format": "json",
            "data": json.dumps(
                [{"loan_number": "mi-2", "first_name": "Sess", "last_name": "Ion",
                  "phone_numbers": ["+15550002222"], "balance": "50", "days_overdue": "2"}]
            ),
        }
        status, result = _request_json(server, "/import", method="POST", payload=payload, service=service)
        assert status == 200
        assert result["sessionId"] is not None

    def test_import_json_rejects_malformed_json(self, api_server):
        server, service = api_server
        payload = {"format": "json", "data": "{not valid json"}
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _request_json(server, "/import", method="POST", payload=payload, service=service)
        assert exc_info.value.code == 400

    def test_import_rejects_unsupported_format(self, api_server):
        server, service = api_server
        payload = {"format": "yaml", "data": "loan_number: X"}
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _request_json(server, "/import", method="POST", payload=payload, service=service)
        assert exc_info.value.code == 400
        body = json.loads(exc_info.value.read().decode("utf-8"))
        assert "Unsupported import format" in body["error"]

    def test_import_rejects_missing_data_field(self, api_server):
        server, service = api_server
        payload = {"format": "json"}
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _request_json(server, "/import", method="POST", payload=payload, service=service)
        assert exc_info.value.code == 400

    def test_import_xlsx_inserts_customers(self, api_server):
        import base64
        import io

        import openpyxl

        server, service = api_server
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Loan Number", "First Name", "Last Name", "Phone"])
        ws.append(["mi-xlsx-1", "Xena", "Row", "+15550003333"])
        buffer = io.BytesIO()
        wb.save(buffer)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

        payload = {"format": "xlsx", "data": encoded}
        status, result = _request_json(server, "/import", method="POST", payload=payload, service=service)
        assert status == 200
        assert result["ok"] is True
        assert result["importedCount"] == 1
        assert service.database.count_customers() == 1

    def test_import_xlsx_rejects_invalid_base64(self, api_server):
        server, service = api_server
        payload = {"format": "xlsx", "data": "not-valid-base64!!!"}
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _request_json(server, "/import", method="POST", payload=payload, service=service)
        assert exc_info.value.code == 400

    def test_import_does_not_require_admin(self, api_server):
        """Mirrors the Telegram bot: /upload has no admin gate, unlike
        /export. A regular authenticated (non-admin) user can import."""
        server, service = api_server
        payload = {
            "format": "json",
            "data": json.dumps(
                [{"loan_number": "mi-noadmin", "first_name": "No", "last_name": "Admin",
                  "phone_numbers": ["+15550004444"], "balance": "10", "days_overdue": "1"}]
            ),
        }
        status, result = _request_json(server, "/import", method="POST", payload=payload, service=service)
        assert status == 200
        assert result["ok"] is True

    def test_import_requires_authentication(self, api_server):
        server, service = api_server
        payload = {"format": "json", "data": "[]"}
        status_or_error = None
        try:
            _request_json(server, "/import", method="POST", payload=payload, service=None, authenticated=False)
        except urllib.error.HTTPError as exc:
            status_or_error = exc.code
        assert status_or_error == 401


class TestAuthBoundaryCoversAllRoutes:
    """Every route in _API_PATHS is a security boundary (see
    SECURITY_AUDIT_REPORT.md's 'any route added later must be added to
    the auth gate list' rule). The auth gate in mini_app_api.py's
    _api_request fires before any method dispatch -- it checks only the
    path -- so an unauthenticated request to ANY of these paths must get
    a hard 401, regardless of which HTTP method a client happens to use.
    This parametrized test locks that boundary to the literal route set,
    so adding a route to _API_PATHS without putting it behind the gate
    fails loudly instead of silently widening the surface."""

    @pytest.mark.parametrize("api_path", sorted(mini_app_api._API_PATHS))
    def test_unauthenticated_request_is_rejected_on_every_api_path(self, api_server, api_path):
        server, _service = api_server
        # The gate is method-independent; use POST for write-ish paths and
        # GET otherwise so the test never depends on handler internals.
        method = "POST" if api_path not in {"/session/current", "/customer/current", "/statistics", "/queue/upcoming", "/customer/search", "/customer/record", "/settings", "/export"} else "GET"
        req = urllib.request.Request(
            f"http://{server.server_address[0]}:{server.server_address[1]}{api_path}",
            method=method,
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        assert exc_info.value.code == 401, f"{api_path} must require authentication"
