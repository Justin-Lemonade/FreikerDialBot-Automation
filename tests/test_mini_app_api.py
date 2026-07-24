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


def _request_json(server, path: str, method: str = "GET", payload: dict | None = None):
    host, port = server.server_address
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
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

    status, current_session = _request_json(server, "/session/current")
    assert status == 200
    assert current_session["customerCount"] >= 1

    status, current_customer = _request_json(server, "/customer/current")
    assert status == 200
    assert current_customer["loan_number"] == "loan-001"

    status, started = _request_json(server, "/call/start", method="POST", payload={"customerId": current_customer["id"]})
    assert status == 200
    assert started["ok"] is True

    status, result = _request_json(
        server,
        "/call/result",
        method="POST",
        payload={"customerId": current_customer["id"], "outcome": "answered"},
    )
    assert status == 200
    assert result["outcome"] == "answered"

    status, stats = _request_json(server, "/statistics")
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
        status, customer = _request_json(server, "/customer/current")
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

    _, current = _request_json(server, "/customer/current")
    assert current["loan_number"] == "dur-1"

    status, result = _request_json(
        server,
        "/call/result",
        method="POST",
        payload={"customerId": current["id"], "outcome": "answered", "duration": 42},
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
    _, current = _request_json(server, "/customer/current")
    _request_json(
        server, "/call/result", method="POST",
        payload={"customerId": current["id"], "outcome": "did_not_answer"},
    )
    assert service.database.status_counts()["call_later"] == 1

    status, _result = _request_json(server, "/queue/call-back", method="POST")
    assert status == 200
    assert service.database.status_counts()["call_later"] == 0
    assert service.database.status_counts()["waiting"] == 1


def test_export_requires_admin_authorization(authenticated_api_server):
    """SECURITY regression test: anonymous requests, and requests from a
    validated-but-non-admin Telegram user, must both be rejected. This
    endpoint hands out every customer's PII -- it needs the same gate
    Telegram's /export command has always had. See BACKLOG.md."""
    server, service = authenticated_api_server
    service.database.insert_customers(
        [{"loan_number": "exp-1", "first_name": "Ex", "last_name": "Port",
          "phone_numbers": ["+15550000006"], "balance": "10", "days_overdue": "1"}]
    )
    host, port = server.server_address

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"http://{host}:{port}/export?format=csv", timeout=5)
    assert exc_info.value.code == 403

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
    status, result = _request_json(server, "/queue/pause", method="POST")
    assert status == 200
    assert result["paused"] is True
    assert service.database.get_queue_session()["is_paused"] == 1


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

    status, customer = _request_json(server, "/customer/current")
    assert status == 200
    assert customer["loanNumber"] == "bl-b"

    status, session = _request_json(server, "/session/current")
    assert session["currentCustomer"]["loanNumber"] == "bl-b"


def test_mini_app_phone_blacklist_falls_back_like_telegram_does(api_server):
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "fb-1", "first_name": "Fall", "last_name": "Back",
          "phone_numbers": ["111", "222"], "balance": "10", "days_overdue": "1"}]
    )
    service.database.blacklist_phone("111")

    status, customer = _request_json(server, "/customer/current")
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
    _, current = _request_json(server, "/customer/current")
    _request_json(server, "/call/start", method="POST", payload={"customerId": current["id"]})

    status, upcoming = _request_json(server, "/queue/upcoming")
    assert status == 200
    assert upcoming["loanNumber"] == "up-2"


def test_customer_search_endpoint(api_server):
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "srch-1", "first_name": "Sasha", "last_name": "One",
          "phone_numbers": ["+15550000010"], "balance": "10", "days_overdue": "1"}]
    )
    status, result = _request_json(server, "/customer/search?q=Sasha")
    assert status == 200
    assert [r["loan_number"] for r in result["results"]] == ["srch-1"]


def test_customer_record_endpoint(api_server):
    server, service = api_server
    service.database.insert_customers(
        [{"loan_number": "rec-1", "first_name": "Rex", "last_name": "One",
          "phone_numbers": ["+15550000011"], "balance": "10", "days_overdue": "1"}]
    )
    customer_id = service.database.get_customer(1)["id"]

    status, record = _request_json(server, f"/customer/record?id={customer_id}")
    assert status == 200
    assert record["loan_number"] == "rec-1"
    assert record["history"] == []
    assert record["notes"] == []


def test_customer_record_endpoint_404_for_missing_customer(api_server):
    server, _service = api_server
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}/customer/record?id=9999")
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
    )
    assert status == 200
    assert result["customer"]["isBlacklisted"] is True

    status, result = _request_json(
        server, "/customer/blacklist", method="POST",
        payload={"customerId": customer_id, "blacklisted": False},
    )
    assert result["customer"]["isBlacklisted"] is False


def test_phone_blacklist_endpoint(api_server):
    server, service = api_server
    status, result = _request_json(
        server, "/phone/blacklist", method="POST",
        payload={"phone": "+15550009999", "blacklisted": True, "reason": "abuse"},
    )
    assert status == 200
    assert result["blacklisted"] is True
    assert service.database.is_phone_blacklisted("+15550009999") is True

    status, result = _request_json(
        server, "/phone/blacklist", method="POST",
        payload={"phone": "+15550009999", "blacklisted": False},
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
    _, current = _request_json(server, "/customer/current")
    status, result = _request_json(
        server, "/call/result", method="POST",
        payload={"customerId": current["id"], "outcome": "answered"},
    )
    assert status == 200
    assert result["session"]["completed"] is True

    with service.database.connect() as conn:
        row = conn.execute("SELECT status FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
    assert row["status"] == "completed"

    for _ in range(3):
        _request_json(server, "/session/current")

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
    _, current = _request_json(server, "/customer/current")

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


def test_missing_credentials_are_still_allowed_through(api_server):
    """Anonymous requests (no Authorization header at all) are still
    permitted for now -- see MINI_APP_API.md for the plan to make
    initData mandatory once the real frontend always sends it."""
    server, _service = api_server
    status, result = _request_json(server, "/statistics")
    assert status == 200
    assert "today" in result


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
        status, result = _request_json(server, "/session/current")
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
    session_before = _request_json(server, "/session/current")[1]
    first_customer_id = session_before["currentCustomer"]["id"]

    first_status, first_result = _request_json(
        server,
        "/call/result",
        method="POST",
        payload={"customerId": first_customer_id, "outcome": "contacted", "duration": 10},
    )
    assert first_status == 200
    assert first_result["ok"] is True

    second_status, second_result = _request_json(
        server,
        "/call/result",
        method="POST",
        payload={"customerId": first_customer_id, "outcome": "contacted", "duration": 999},
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
