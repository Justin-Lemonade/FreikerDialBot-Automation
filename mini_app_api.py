"""Minimal HTTP API for the Telegram Mini App to drive the existing queue."""

from __future__ import annotations

import json
import mimetypes
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs

from config import BASE_DIR, Settings
from backend import Backend, build_backend
from database import Database
from export_engine import export_customers, ExportError
from telegram_auth import validate_init_data, extract_user_id, TelegramAuthError

# Where the built frontend (index.html + /assets/*) lives. The compiled
# bundle already exists at BASE_DIR (index.html, index-*.js, index-*.css)
# -- this just serves it from the same process/port as the API instead
# of requiring a separate static file server, so a single
# `python mini_app_api.py` is enough to make the Mini App reachable.
FRONTEND_DIR = BASE_DIR


class MiniAppService:
    """Thin adapter over the existing queue/session/statistics classes.

    Wired to the shared Backend (backend.py) rather than constructing
    Database/StatisticsEngine/SessionManager/QueueEngine itself -- this
    used to duplicate exactly the sequence bot.py builds too, which is
    the duplication backend.py exists to eliminate. A `database`/`db_path`
    override is still accepted (tests want an isolated temp-file
    Database), in which case a matching Backend is built around it.
    """
    bot_token: str | None

    def __init__(
        self,
        database: Database | None = None,
        db_path: str | Path | None = None,
        bot_token: str | None = None,
        settings: Settings | None = None,
    ):
        if database is None and db_path is not None:
            database = Database(Path(db_path))
        backend: Backend = build_backend(settings=settings, database=database)
        self.backend = backend
        self.database = backend.database
        self.statistics = backend.statistics
        self.session_manager = backend.session_manager
        self.queue_engine = backend.queue_engine
        self.bot_token = bot_token or (backend.settings.telegram_bot_token if backend.settings else None)

    def _format_duration(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s" if seconds else "0s"
        minutes, secs = divmod(seconds, 60)
        if secs:
            return f"{minutes}m {secs}s"
        return f"{minutes}m"

    def _customer_payload(self, customer: dict[str, Any] | None) -> dict[str, Any] | None:
        if not customer:
            return None
        phone_numbers = customer.get("phone_numbers") or []
        phone = ""
        if isinstance(phone_numbers, list):
            for p in phone_numbers:
                if not self.database.is_phone_blacklisted(p):
                    phone = p
                    break
        notes = []
        if customer.get("warning_note"):
            notes.append(customer["warning_note"])
        return {
            "id": str(customer["id"]),
            "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            "loanNumber": customer.get("loan_number", ""),
            "balance": customer.get("balance", ""),
            "daysLate": customer.get("days_overdue", ""),
            "monthlyPayment": customer.get("monthly_payment", ""),
            "currentOverdueAmount": customer.get("current_overdue_amount", ""),
            "originalLoanAmount": customer.get("original_loan_amount", ""),
            "phone": phone,
            "notes": notes,
            "loan_number": customer.get("loan_number", ""),
            "first_name": customer.get("first_name", ""),
            "last_name": customer.get("last_name", ""),
            "status": customer.get("status", "waiting"),
        }

    def _active_customer(self) -> dict[str, Any] | None:
        queue_state = self.database.get_queue_session()
        current_id = queue_state.get("current_customer_id")
        if current_id:
            customer = self.database.get_customer(int(current_id))
            if customer:
                return customer
        return None

    def get_current_session(self) -> dict[str, Any]:
        progress = self.queue_engine.status()
        session = self.session_manager.current_session()
        customer = self._active_customer()
        if customer is None and progress.total_customers:
            customer = self.database.get_next_actionable_customer()

        snapshot = self.statistics.snapshot()
        today_stats = snapshot.today
        total_customers = progress.total_customers if progress.total_customers else int(session["total_customers"]) if session else 0
        session_id = int(session["id"]) if session else None
        if session_id is None and total_customers and progress.remaining > 0:
            self.session_manager.start_current_session()
            session = self.session_manager.current_session()
            session_id = int(session["id"]) if session else None
        average_seconds = snapshot.average_seconds_per_customer
        completed = bool(session and session.get("status") == "completed") or (progress.total_customers and progress.remaining == 0)

        return {
            "sessionId": session_id,
            "currentCustomerIndex": max(1, progress.current_position),
            "customerCount": total_customers,
            "answeredToday": today_stats.get("customers_contacted", 0),
            "estimatedRemaining": progress.remaining,
            "averageCallTime": self._format_duration(average_seconds),
            "completed": completed,
            "currentCustomer": self._customer_payload(customer),
            "progress": {
                "remaining": progress.remaining,
                "contacted": progress.contacted,
                "didNotAnswer": progress.did_not_answer,
                "percent": progress.percent,
            },
        }

    def get_current_customer(self) -> dict[str, Any] | None:
        """Peek at the next customer without committing anything to DB."""
        customer = self._active_customer()
        if customer is None:
            customer = self.database.get_next_actionable_customer()
        return self._customer_payload(customer)

    def start_call(self, customer_id: int | None = None, telegram_user_id: int | None = None) -> dict[str, Any]:
        if customer_id is None:
            customer = self.get_current_customer()
            if customer is None:
                return {"ok": False, "error": "No customer available"}
            customer_id = int(customer["id"])

        self.session_manager.start_current_session()
        self.database.update_queue_session(current_customer_id=customer_id)
        self.statistics.record_event("queue_started", session_id=self.session_manager.current_session()["id"] if self.session_manager.current_session() else None, customer=self.database.get_customer(customer_id), telegram_user_id=telegram_user_id)
        return {"ok": True, "customerId": customer_id, "startedAt": datetime.now(timezone.utc).isoformat()}

    def submit_call_result(self, customer_id: int | None, outcome: str, duration: int | None = None, telegram_user_id: int | None = None) -> dict[str, Any]:
        if customer_id is None:
            return {"ok": False, "error": "customerId is required"}

        status = self._map_outcome(outcome)
        self.session_manager.start_current_session()
        self.database.update_customer_status(int(customer_id), status)
        self.database.update_queue_session(current_customer_id=int(customer_id))
        event_type = "customer_warned" if status == "warned" else "customer_call_later" if status == "call_later" else "customer_marked_invalid" if status == "invalid_number" else "customer_skipped"
        self.statistics.record_event(
            event_type,
            session_id=self.session_manager.current_session()["id"] if self.session_manager.current_session() else None,
            customer=self.database.get_customer(int(customer_id)),
            notes=outcome,
            duration=duration,
            telegram_user_id=telegram_user_id,
        )
        # Advance to next customer
        next_selection = self.queue_engine.next_customer()
        next_customer = self._customer_payload(next_selection.customer) if next_selection and next_selection.customer else None
        # Complete session if queue is done
        session = self.session_manager.current_session()
        if session and next_selection and next_selection.complete:
            self.session_manager.complete_current_session()
            session = self.session_manager.most_recent_session()
        session_data = self.get_current_session() if session else {"completed": True}
        return {
            "ok": True,
            "customerId": customer_id,
            "outcome": outcome,
            "status": status,
            "duration": duration,
            "nextCustomer": next_customer,
            "session": session_data,
        }

    def save_note(self, customer_id: int | None, note: str, telegram_user_id: int | None = None) -> dict[str, Any]:
        if customer_id is None or not note or not note.strip():
            return {"ok": False, "error": "customerId and note are required"}
        self.statistics.record_event(
            "customer_note_added",
            session_id=self.session_manager.current_session()["id"] if self.session_manager.current_session() else None,
            customer=self.database.get_customer(int(customer_id)),
            notes=note.strip(),
            telegram_user_id=telegram_user_id,
        )
        return {"ok": True, "customerId": customer_id, "note": note.strip()}

    def next_customer(self) -> dict[str, Any]:
        selection = self.queue_engine.next_customer()
        return {
            "customer": self._customer_payload(selection.customer),
            "session": self.get_current_session(),
        }

    def pause_queue(self) -> dict[str, Any]:
        self.database.update_queue_session(is_paused=1)
        return {"paused": True}

    def resume_queue(self) -> dict[str, Any]:
        self.database.update_queue_session(is_paused=0)
        return {"paused": False}

    def call_back(self) -> dict[str, Any]:
        """Reset all call_later customers back to waiting."""
        self.queue_engine.restart_call_later()
        return {"ok": True}

    def get_upcoming_customer(self) -> dict[str, Any] | None:
        """Peek at the next customer after the current active one."""
        # Get the customer after the currently active one
        queue_state = self.database.get_queue_session()
        current_id = queue_state.get("current_customer_id")
        customers = self.database.get_all_customers()
        waiting = [c for c in customers if c["status"] == "waiting" and not c.get("is_blacklisted")]
        if not waiting:
            return None
        if current_id:
            # Find the next after current
            ids = [c["id"] for c in waiting]
            try:
                idx = ids.index(int(current_id))
                if idx + 1 < len(waiting):
                    return self._customer_payload(waiting[idx + 1])
            except ValueError:
                pass
        return self._customer_payload(waiting[0]) if waiting else None

    def search_customers(self, query: str, limit: int = 10) -> dict[str, Any]:
        results = self.database.search_customers(query, limit=limit)
        return {"results": [self._customer_payload(c) or {} for c in results]}

    def get_customer_record(self, customer_id: int) -> dict[str, Any] | None:
        return self.database.get_customer_record(customer_id)

    def edit_customer(self, customer_id: int, fields: dict) -> dict[str, Any]:
        self.database.update_customer_fields(customer_id, **fields)
        customer = self.database.get_customer(customer_id)
        return {"ok": True, "customer": customer}

    def set_customer_blacklisted(self, customer_id: int, blacklisted: bool) -> dict[str, Any]:
        self.database.set_customer_blacklisted(customer_id, blacklisted)
        customer = self.database.get_customer(customer_id)
        return {"customer": {"id": str(customer["id"]), "isBlacklisted": bool(customer["is_blacklisted"])}}

    def set_phone_blacklisted(self, phone: str, blacklisted: bool, reason: str | None = None) -> dict[str, Any]:
        if blacklisted:
            self.database.blacklist_phone(phone, reason=reason)
        else:
            self.database.unblacklist_phone(phone)
        return {"phone": phone, "blacklisted": blacklisted}

    def get_statistics(self) -> dict[str, Any]:
        snapshot = self.statistics.snapshot()
        return {
            "today": snapshot.today,
            "lifetime": snapshot.lifetime,
            "averageContactsPerSession": snapshot.average_contacts_per_session,
            "averageSecondsPerCustomer": snapshot.average_seconds_per_customer,
            "todaysCalls": snapshot.today.get("customers_contacted", 0) + snapshot.today.get("customers_not_answered", 0),
            "answered": snapshot.today.get("customers_contacted", 0),
            "didntAnswer": snapshot.today.get("customers_not_answered", 0),
            "wrongNumber": 0,
            "averageCallTime": self._format_duration(snapshot.average_seconds_per_customer),
            "successRate": self._success_rate(snapshot.today),
            "lifetimeCalls": snapshot.lifetime.get("customers_contacted", 0) + snapshot.lifetime.get("customers_not_answered", 0),
            "sessions": snapshot.lifetime.get("sessions", 0),
            "customersContacted": snapshot.lifetime.get("customers_contacted", 0),
            "bestDay": "N/A",
        }

    def _map_outcome(self, outcome: str) -> str:
        normalized = (outcome or "").strip().lower()
        mapping = {
            "answered": "warned",
            "contacted": "warned",
            "did_not_answer": "call_later",
            "didnt_answer": "call_later",
            "wrong_number": "invalid_number",
            "wrongnumber": "invalid_number",
            "skip": "skip",
            "skipped": "skip",
            "paid": "paid",
        }
        return mapping.get(normalized, "warned")

    def _success_rate(self, stats: dict[str, int]) -> str:
        contacted = stats.get("customers_contacted", 0)
        total = contacted + stats.get("customers_not_answered", 0)
        if not total:
            return "0%"
        return f"{round((contacted / total) * 100)}%"

    def _record_event(self, event_type: str, *, customer_id: int | None = None, notes: str | None = None, duration: int | None = None) -> None:
        session = self.session_manager.current_session()
        with self.database.connect() as conn:
            conn.execute(
                """
                INSERT INTO customer_events (
                    session_id,
                    loan_number,
                    customer_id,
                    event_type,
                    event_timestamp,
                    telegram_user_id,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["id"] if session else None,
                    None,
                    customer_id,
                    event_type,
                    datetime.now(timezone.utc).isoformat(),
                    None,
                    notes,
                ),
            )
            conn.commit()


class MiniAppRequestHandler(BaseHTTPRequestHandler):
    service: MiniAppService | None = None
    telegram_user_id: int | None = None

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch()

    def _dispatch(self) -> None:
        if self.service is None:
            self._json(500, {"error": "service not configured"})
            return

        auth_header = self.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("tma "):
            try:
                validated_data = validate_init_data(auth_header[4:], self.service.bot_token or "")
                self.telegram_user_id = extract_user_id(validated_data)
            except TelegramAuthError as e:
                self._json(401, {"error": "unauthorized", "details": str(e)})
                return

        parsed = urlparse(self.path)
        path = parsed.path
        method = self.command.upper()
        body = self._read_body()

        api_path = path[4:] if path.startswith("/api/") else (path if path != "/api" else "/")

        if api_path == "/session/current" and method == "GET":
            self._json(200, self.service.get_current_session())
            return
        if api_path == "/customer/current" and method == "GET":
            self._json(200, self.service.get_current_customer() or {})
            return
        if api_path == "/statistics" and method == "GET":
            self._json(200, self.service.get_statistics())
            return
        if api_path == "/session/next" and method == "POST":
            self._json(200, self.service.next_customer())
            return
        if api_path == "/call/start" and method == "POST":
            payload = self._parse_json(body)
            customer_id = payload.get("customerId") or payload.get("customer_id")
            self._json(200, self.service.start_call(customer_id=int(customer_id) if customer_id is not None else None, telegram_user_id=self.telegram_user_id))
            return
        if api_path == "/call/result" and method == "POST":
            payload = self._parse_json(body)
            customer_id = payload.get("customerId") or payload.get("customer_id")
            outcome = payload.get("outcome") or payload.get("result") or "answered"
            duration = payload.get("duration")
            self._json(200, self.service.submit_call_result(int(customer_id) if customer_id is not None else None, str(outcome), int(duration) if duration is not None else None, telegram_user_id=self.telegram_user_id))
            return
        if api_path == "/note" and method == "POST":
            payload = self._parse_json(body)
            customer_id = payload.get("customerId") or payload.get("customer_id")
            note = payload.get("note") or payload.get("content") or ""
            self._json(200, self.service.save_note(int(customer_id) if customer_id is not None else None, str(note), telegram_user_id=self.telegram_user_id))
            return
        if api_path == "/queue/pause" and method == "POST":
            self._json(200, self.service.pause_queue())
            return
        if api_path == "/queue/resume" and method == "POST":
            self._json(200, self.service.resume_queue())
            return
        if api_path == "/queue/call-back" and method == "POST":
            self._json(200, self.service.call_back())
            return
        if api_path == "/queue/upcoming" and method == "GET":
            result = self.service.get_upcoming_customer()
            self._json(200, result or {})
            return
        if api_path == "/customer/search" and method == "GET":
            params = parse_qs(parsed.query)
            query = params.get("q", [""])[0]
            self._json(200, self.service.search_customers(query))
            return
        if api_path == "/customer/record" and method == "GET":
            params = parse_qs(parsed.query)
            cid = params.get("id", [None])[0]
            if cid is None:
                self._json(400, {"error": "id is required"})
                return
            record = self.service.get_customer_record(int(cid))
            if record is None:
                self._json(404, {"error": "not found"})
                return
            self._json(200, record)
            return
        if api_path == "/customer/edit" and method == "POST":
            payload = self._parse_json(body)
            customer_id = payload.get("customerId") or payload.get("customer_id")
            fields = payload.get("fields") or {}
            self._json(200, self.service.edit_customer(int(customer_id), fields))
            return
        if api_path == "/customer/blacklist" and method == "POST":
            payload = self._parse_json(body)
            customer_id = payload.get("customerId") or payload.get("customer_id")
            blacklisted = bool(payload.get("blacklisted", True))
            self._json(200, self.service.set_customer_blacklisted(int(customer_id), blacklisted))
            return
        if api_path == "/phone/blacklist" and method == "POST":
            payload = self._parse_json(body)
            phone = payload.get("phone", "")
            blacklisted = bool(payload.get("blacklisted", True))
            reason = payload.get("reason")
            self._json(200, self.service.set_phone_blacklisted(phone, blacklisted, reason))
            return
        
        if api_path == "/export" and method == "GET":
            admin_ids = self.service.backend.settings.admin_user_ids
            if not self.telegram_user_id or self.telegram_user_id not in admin_ids:
                self._json(403, {"error": "forbidden"})
                return

            params = parse_qs(parsed.query)
            export_format = (params.get("format", ["csv"])[0]).lower()
            if export_format not in ("csv", "json", "xlsx"):
                self._json(400, {"error": f"unsupported format: {export_format}"})
                return

            try:
                customers = self.service.database.get_all_customers()
                session = self.service.session_manager.most_recent_session()
                export_path = export_customers(customers, session["id"] if session else None, export_format)
                
                self.service.statistics.record_event(
                    "admin_action",
                    telegram_user_id=self.telegram_user_id,
                    notes=f"export:{export_format}"
                )
                
                content_type = "text/csv" if export_format == "csv" else "application/json" if export_format == "json" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                data = export_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            except ExportError as e:
                self._json(500, {"error": "export failed", "details": str(e)})
            except Exception as e:
                self._json(500, {"error": "internal server error", "details": str(e)})
            return

        if path.startswith("/api/") or path == "/api":
            self._json(404, {"error": "not found"})
            return

        if method == "GET":
            self._serve_static(path)
            return

        self._json(404, {"error": "not found"})

    def _serve_static(self, path: str) -> None:
        """Serve the built frontend (index.html, /assets/*, favicon,
        etc.) from FRONTEND_DIR.

        Only "/" (and "/index.html") fall back to index.html -- this
        app has no client-side URL routing (it's a single-page app that
        switches screens via internal state, not the URL), so any other
        unmatched path is a genuine 404, not a deep link to redirect.
        Falling back more broadly would silently turn a mistyped or
        not-yet-implemented API path into a 200 HTML response instead
        of a 404, which is worse for debugging, not better.
        """
        relative = path.lstrip("/")
        if not relative:
            relative = "index.html"

        # Allow serving from the exports directory
        if "export" in relative:
             candidate = (BASE_DIR / relative).resolve()
        else:
            candidate = (FRONTEND_DIR / relative).resolve()
        
        try:
            if "export" not in relative:
                candidate.relative_to(FRONTEND_DIR.resolve())
        except ValueError:
            self._json(404, {"error": "not found"})
            return
        if not candidate.is_file() and relative in ("", "index.html"):
            candidate = FRONTEND_DIR / "index.html"
        if not candidate.is_file():
            self._json(404, {"error": "not found", "path": str(candidate)})
            return

        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


    def _read_body(self) -> bytes:
        length_header = self.headers.get("Content-Length")
        if not length_header:
            return b""
        try:
            length = int(length_header)
        except ValueError:
            return b""
        return self.rfile.read(length)

    def _parse_json(self, body: bytes) -> dict[str, Any]:
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class MiniAppAPI:
    def __init__(self, service: MiniAppService):
        self.service = service

    def create_server(self, host: str = "0.0.0.0", port: int = 8000) -> ThreadingHTTPServer:
        server = ThreadingHTTPServer((host, port), self._handler_class())
        return server

    def _handler_class(self) -> type[MiniAppRequestHandler]:
        class Handler(MiniAppRequestHandler):
            service = self.service

        return Handler


def create_service(
    db_path: str | Path | None = None,
    bot_token: str | None = None,
    settings: Settings | None = None,
) -> MiniAppService:
    return MiniAppService(db_path=db_path, bot_token=bot_token, settings=settings)


def main() -> None:
    service = create_service()
    api = MiniAppAPI(service)
    server = api.create_server(host="0.0.0.0", port=8000)
    print(f"Mini App API listening on http://0.0.0.0:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
