"""Minimal HTTP API for the Telegram Mini App to drive the existing queue."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from backend import Backend, build_backend
from config import BASE_DIR, Settings, load_settings
from database import Database
from export_engine import EXPORTERS, ExportError, export_customers
from queue_engine import QueueEngine
import security
from session_manager import SessionManager
from statistics_engine import StatisticsEngine
from telegram_auth import TelegramAuthError, extract_user_id, validate_init_data


class MiniAppService:
    """Thin adapter over the existing queue/session/statistics classes."""

    def __init__(
        self,
        bot_token: str | None = None,
        settings: Settings | None = None,
        backend: Backend | None = None,
    ):
        self.backend = backend or build_backend(settings=settings)
        self.database = self.backend.database
        self.statistics = self.backend.statistics
        self.session_manager = self.backend.session_manager
        self.queue_engine = self.backend.queue_engine

        # Settings drives auth (bot_token for initData verification,
        # admin_user_ids for /export). Falls back to real environment
        # settings if not explicitly provided, but tests construct their
        # own Settings so they never depend on real env values.
        self.settings = self.backend.settings
        self.bot_token = bot_token or self.settings.telegram_bot_token

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
        phone = self.database.first_non_blacklisted_phone(phone_numbers) if isinstance(phone_numbers, list) else ""
        notes = []
        if customer.get("warning_note"):
            notes.append(customer["warning_note"])
        return {
            "id": str(customer["id"]),
            "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            "loanNumber": customer.get("loan_number", ""), # Duplicated below, but keep for compatibility
            "balance": customer.get("balance", ""),
            "daysLate": customer.get("days_overdue", ""),
            "monthlyPayment": customer.get("monthly_payment", ""), # Corrected from ""
            "currentOverdueAmount": customer.get("current_overdue_amount", ""),
            "originalLoanAmount": customer.get("original_loan_amount", ""),
            "phone": phone,
            "notes": notes,
            "loan_number": customer.get("loan_number", ""),
            "first_name": customer.get("first_name", ""),
            "last_name": customer.get("last_name", ""),
            "status": customer.get("status", "waiting"),
            "isBlacklisted": bool(customer.get("is_blacklisted", False)),
        }

    def _active_customer(self) -> dict[str, Any] | None:
        """Read-only: returns the customer currently committed as
        'current' in queue_session, WITHOUT ever calling next_customer()
        (that mutates). If no customer is committed yet, callers should
        use peek_next_customer() instead of assuming one exists here."""
        queue_state = self.database.get_queue_session()
        current_id = queue_state.get("current_customer_id")
        if current_id:
            customer = self.database.get_customer(int(current_id))
            if customer and not customer.get("is_blacklisted"):
                return customer
        return None

    def get_current_session(self) -> dict[str, Any]:
        progress = self.queue_engine.status()
        session = self.session_manager.current_session()
        queue_complete = bool(progress.total_customers) and progress.remaining == 0

        if session and queue_complete:
            # Finalize now, before deciding whether to show a customer or
            # spawn anything -- this is what stops a second /session/current
            # poll from seeing "no active session" and starting a new one.
            self.session_manager.complete_current_session()
            session = self.session_manager.current_session()  # None: it's completed now

        customer = None if queue_complete else self._active_customer()
        if customer is None and not queue_complete and progress.total_customers:
            customer = self.queue_engine.peek_next_customer()

        snapshot = self.statistics.snapshot()
        today_stats = snapshot.today
        total_customers = progress.total_customers if progress.total_customers else int(session["total_customers"]) if session else 0
        session_id = int(session["id"]) if session else None
        if session_id is None and total_customers and not queue_complete:
            self.session_manager.start_current_session()
            session = self.session_manager.current_session()
            session_id = int(session["id"]) if session else None
        average_seconds = snapshot.average_seconds_per_customer
        completed = queue_complete or bool(session and session.get("status") == "completed")

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
        customer = self._active_customer()
        if customer is None:
            customer = self.queue_engine.peek_next_customer()
        return self._customer_payload(customer)

    def start_call(self, customer_id: int | None = None) -> dict[str, Any]:
        if customer_id is None:
            customer = self.get_current_customer()
            if customer is None:
                return {"ok": False, "error": "No customer available"}
            customer_id = int(customer["id"])

        self.session_manager.start_current_session()
        self.database.update_queue_session(current_customer_id=customer_id)
        self.statistics.record_event("queue_started", session_id=self.session_manager.current_session()["id"] if self.session_manager.current_session() else None, customer=self.database.get_customer(customer_id))
        return {"ok": True, "customerId": customer_id, "startedAt": datetime.now(timezone.utc).isoformat()}

    def submit_call_result(
        self,
        customer_id: int | None,
        outcome: str,
        duration: int | None = None,
        telegram_user_id: int | None = None,
    ) -> dict[str, Any]:
        """The single write path for outcome buttons (Contacted/Didn't
        Answer/Wrong Number/Skip). Routes through QueueEngine.apply_action
        -- the exact same method the Telegram bot uses -- so both
        frontends share one source of truth for status transitions,
        the needs_review guard, and event-type mapping. This also
        advances the queue and returns the next customer in the same
        call, so the frontend never needs a separate "advance" request.
        """
        if customer_id is None:
            return {"ok": False, "error": "customerId is required"}

        status = self._map_outcome(outcome)
        if status not in {"warned", "call_later", "skip", "invalid_number"}:
            return {"ok": False, "error": f"Unsupported outcome: {outcome}"}

        self.session_manager.start_current_session()

        selection = self.queue_engine.apply_action(
            int(customer_id),
            status,
            telegram_user_id=telegram_user_id,
            duration_seconds=int(duration) if duration is not None else None,
        )

        session_payload = self.get_current_session()
        return {
            "ok": True,
            "customerId": customer_id,
            "outcome": outcome,
            "status": status,
            "duration": duration,
            "nextCustomer": self._customer_payload(selection.customer),
            "session": session_payload,
        }

    def save_note(self, customer_id: int | None, note: str) -> dict[str, Any]:
        if customer_id is None or not note or not note.strip():
            return {"ok": False, "error": "customerId and note are required"}
        self.statistics.record_event(
            "customer_warned",
            session_id=self.session_manager.current_session()["id"] if self.session_manager.current_session() else None,
            customer=self.database.get_customer(int(customer_id)),
            notes=note.strip(),
        )
        return {"ok": True, "customerId": customer_id, "note": note.strip()}

    def next_customer(self) -> dict[str, Any]:
        selection = self.queue_engine.next_customer()
        return {
            "customer": self._customer_payload(selection.customer),
            "session": self.get_current_session(),
        }

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

    def pause_queue(self, telegram_user_id: int | None = None) -> dict[str, Any]:
        self.queue_engine.pause(telegram_user_id=telegram_user_id)
        return {"ok": True, "paused": True}

    def call_back(self, telegram_user_id: int | None = None) -> dict[str, Any]:
        """Requeue every 'call_later' customer -- the Mini App equivalent
        of the bot's 'Call Back' completion-screen button. Reuses
        QueueEngine.restart_call_later() rather than reimplementing the
        requeue rule."""
        selection = self.queue_engine.restart_call_later(telegram_user_id=telegram_user_id)
        return {
            "ok": True,
            "customer": self._customer_payload(selection.customer),
            "session": self.get_current_session(),
        }

    def queue_upcoming(self) -> dict[str, Any] | None:
        """Preview the customer after the current one, without touching
        queue state -- used for a "who's next" glance, not to be confused
        with the current customer itself."""
        current = self._active_customer()
        current_id = current["id"] if current else None
        exclude_ids = {current_id} if current_id else set()
        upcoming = self.database.get_next_actionable_customer(exclude_ids=exclude_ids or None)
        while upcoming and upcoming.get("is_blacklisted"):
            exclude_ids.add(upcoming["id"])
            upcoming = self.database.get_next_actionable_customer(exclude_ids=exclude_ids)
        return self._customer_payload(upcoming)

    def search_customers(self, query: str) -> dict[str, Any]:
        results = self.database.search_customers(query)
        return {"results": [self._customer_payload(customer) for customer in results]}

    def get_customer_record(self, customer_id: int) -> dict[str, Any] | None:
        record = self.database.get_customer_record(customer_id)
        if record is None:
            return None
        payload = self._customer_payload(record) or {}
        payload["notes"] = record.get("notes", [])
        payload["history"] = record.get("history", [])
        payload["blacklisted_phones"] = record.get("blacklisted_phones", [])
        return payload

    def edit_customer(
        self, customer_id: int, fields: dict[str, Any], telegram_user_id: int | None = None
    ) -> dict[str, Any]:
        """Field edits route through QueueEngine.edit_customer -- the same
        method /edit uses on Telegram -- so both frontends share one audit
        trail and one 'only write what actually changed' rule."""
        updated = self.queue_engine.edit_customer(
            customer_id, telegram_user_id=telegram_user_id, **fields
        )
        if updated is None:
            return {"ok": False, "error": "Customer not found"}
        return {"ok": True, "customer": self._customer_payload(updated)}

    def set_customer_blacklist(
        self, customer_id: int, blacklisted: bool, telegram_user_id: int | None = None
    ) -> dict[str, Any]:
        updated = self.queue_engine.blacklist_customer(
            customer_id, blacklisted, telegram_user_id=telegram_user_id
        )
        if updated is None:
            return {"ok": False, "error": "Customer not found"}
        return {"ok": True, "customer": self._customer_payload(updated)}

    def set_phone_blacklist(
        self,
        phone: str,
        blacklisted: bool,
        reason: str | None = None,
        telegram_user_id: int | None = None,
    ) -> dict[str, Any]:
        if blacklisted:
            self.queue_engine.blacklist_phone(phone, reason=reason, telegram_user_id=telegram_user_id)
        else:
            self.queue_engine.unblacklist_phone(phone, telegram_user_id=telegram_user_id)
        return {"ok": True, "phone": phone, "blacklisted": blacklisted}

    def export(self, export_format: str, telegram_user_id: int | None = None) -> tuple[bytes, str, str] | dict[str, Any]:
        """Mirrors admin_commands.export(): same source data, same
        export_engine call, same admin_action audit event -- just
        returned as bytes for an HTTP response instead of a Telegram
        document attachment. Caller (the HTTP handler) is responsible
        for the admin authorization check before this runs."""
        customers = self.database.get_all_customers()
        if not customers:
            return {"ok": False, "error": "No customers loaded"}

        session = self.session_manager.current_session()
        session_id = session["id"] if session else None

        try:
            file_path: Path = export_customers(customers, session_id, export_format)
        except ExportError as exc:
            return {"ok": False, "error": str(exc)}

        content_type = {
            "csv": "text/csv",
            "json": "application/json",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }.get(export_format, "application/octet-stream")

        body = file_path.read_bytes()
        self.statistics.record_event(
            "admin_action",
            telegram_user_id=telegram_user_id,
            notes=f"export:{export_format}",
        )
        return body, content_type, file_path.name

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

        parsed = urlparse(self.path)
        path = parsed.path

        if self._api_request(path, parsed.query, self.command.upper()):
            return
        if path.startswith("/api"):
            api_path = path[len("/api") :]
            if self._api_request(api_path, parsed.query, self.command.upper()):
                return

        if self._serve_static(path):
            return

        self._json(404, {"error": "not found"})

    def _api_request(self, path: str, query: str, method: str) -> bool:
        """True if a matching API endpoint was found and handled, False otherwise."""
        body = self._read_body()
        query = parse_qs(query)

        try:
            telegram_user_id = self._authenticate()
        except TelegramAuthError as exc:
            self._json(401, {"error": str(exc)})
            return True
        if path == "/session/current" and method == "GET":
            self._json(200, self.service.get_current_session())
            return True
        if path == "/customer/current" and method == "GET":
            self._json(200, self.service.get_current_customer() or {})
            return True
        if path == "/statistics" and method == "GET":
            self._json(200, self.service.get_statistics())
            return True
        if path == "/session/next" and method == "POST":
            self._json(200, self.service.next_customer())
            return True
        if path == "/call/start" and method == "POST":
            payload = self._parse_json(body)
            customer_id = payload.get("customerId") or payload.get("customer_id")
            self._json(200, self.service.start_call(customer_id=int(customer_id) if customer_id is not None else None))
            return True
        if path == "/call/result" and method == "POST":
            payload = self._parse_json(body)
            customer_id = payload.get("customerId") or payload.get("customer_id")
            outcome = payload.get("outcome") or payload.get("result") or "answered"
            duration = payload.get("duration")
            self._json(
                200,
                self.service.submit_call_result(
                    int(customer_id) if customer_id is not None else None,
                    str(outcome),
                    int(duration) if duration is not None else None,
                    telegram_user_id=telegram_user_id,
                ),
            )
            return True
        if path == "/note" and method == "POST":
            payload = self._parse_json(body)
            customer_id = payload.get("customerId") or payload.get("customer_id")
            note = payload.get("note") or payload.get("content") or ""
            self._json(200, self.service.save_note(int(customer_id) if customer_id is not None else None, str(note)))
            return True
        if path == "/queue/pause" and method == "POST":
            self._json(200, self.service.pause_queue(telegram_user_id=telegram_user_id))
            return True
        if path == "/queue/call-back" and method == "POST":
            self._json(200, self.service.call_back(telegram_user_id=telegram_user_id))
            return True
        if path == "/queue/upcoming" and method == "GET":
            upcoming = self.service.queue_upcoming()
            if upcoming is None:
                self._json(404, {"error": "No upcoming customer"})
                return True
            self._json(200, upcoming)
            return True
        if path == "/customer/search" and method == "GET":
            search_query = (query.get("q") or query.get("query") or [""])[0]
            self._json(200, self.service.search_customers(search_query))
            return True
        if path == "/customer/record" and method == "GET":
            raw_id = (query.get("id") or [None])[0]
            if raw_id is None:
                self._json(400, {"error": "id is required"})
                return True
            record = self.service.get_customer_record(int(raw_id))
            if record is None:
                self._json(404, {"error": "Customer not found"})
                return True
            self._json(200, record)
            return True
        if path == "/customer/edit" and method == "POST":
            payload = self._parse_json(body)
            customer_id = payload.get("customerId") or payload.get("customer_id")
            fields = payload.get("fields") or {}
            if customer_id is None:
                self._json(400, {"error": "customerId is required"})
                return True
            self._json(
                200,
                self.service.edit_customer(int(customer_id), fields, telegram_user_id=telegram_user_id),
            )
            return True
        if path == "/customer/blacklist" and method == "POST":
            payload = self._parse_json(body)
            customer_id = payload.get("customerId") or payload.get("customer_id")
            blacklisted = bool(payload.get("blacklisted", True))
            if customer_id is None:
                self._json(400, {"error": "customerId is required"})
                return True
            self._json(
                200,
                self.service.set_customer_blacklist(
                    int(customer_id), blacklisted, telegram_user_id=telegram_user_id
                ),
            )
            return True
        if path == "/phone/blacklist" and method == "POST":
            payload = self._parse_json(body)
            phone = payload.get("phone")
            blacklisted = bool(payload.get("blacklisted", True))
            reason = payload.get("reason")
            if not phone:
                self._json(400, {"error": "phone is required"})
                return True
            self._json(
                200,
                self.service.set_phone_blacklist(
                    str(phone), blacklisted, reason=reason, telegram_user_id=telegram_user_id
                ),
            )
            return True
        if path == "/export" and method == "GET":
            if not security.is_admin(telegram_user_id, self.service.settings):
                self._json(403, {"error": "Admin authorization required"})
                return True
            export_format = (query.get("format") or ["csv"])[0].lower()
            result = self.service.export(export_format, telegram_user_id=telegram_user_id)
            if isinstance(result, dict):
                self._json(400, result)
                return True
            file_bytes, content_type, filename = result
            self._file(200, file_bytes, content_type, filename)
            return True

        # No matching API endpoint found. The caller should now try static file serving.
        return False

    def _serve_static(self, path: str) -> bool:
        """Serves static files from the frontend's build output directory."""
        static_dir = self.service.backend.settings.mini_app_static_dir
        if not static_dir or not static_dir.is_dir():
            return False

        if path == "/":
            path = "/index.html"

        # Sanitize path to prevent directory traversal
        try:
            # Important: os.path.normpath is not enough, as it doesn't
            # prevent '..' segments from backing out of the root.
            # Path.resolve() is the correct tool here.
            filepath = (static_dir / path.lstrip("/")).resolve()
            if not str(filepath).startswith(str(static_dir.resolve())):
                return False  # Forbidden
        except Exception:
            return False  # Bad request or other error

        if not filepath.is_file():
            return False

        content_type = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".ico": "image/x-icon",
        }.get(filepath.suffix, "application/octet-stream")

        try:
            with filepath.open("rb") as f:
                self.send_response(200)
                self.send_header("Content-Type", f"{content_type}; charset=utf-8")
                self.send_header("Content-Length", str(filepath.stat().st_size))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(f.read())
                return True
        except OSError:
            # This can still happen if the file is deleted between the
            # is_file() check and the open() call.
            return False

    def _authenticate(self) -> int | None:
        """Extract and validate the Telegram user id from the
        Authorization header, if present. Missing credentials are still
        allowed through (anonymous) for every endpoint except /export,
        which checks admin authorization separately -- see
        MINI_APP_API.md for the plan to make initData mandatory once the
        real frontend always sends it. An Authorization header that IS
        present but fails signature validation is always a hard 401,
        never silently downgraded to anonymous.
        """
        header = self.headers.get("Authorization", "")
        if not header:
            return None
        prefix = "tma "
        if not header.startswith(prefix):
            return None
        init_data = header[len(prefix):]
        validated = validate_init_data(
            init_data,
            self.service.bot_token,
            max_age_seconds=self.service.settings.mini_app_auth_max_age_seconds,
        )
        return extract_user_id(validated)

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

    def _file(self, status: int, body: bytes, content_type: str, filename: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
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


def create_service(backend: Backend | None = None) -> MiniAppService:
    """Instantiates the Mini App's backend service, either from a shared
    (injected) backend or by constructing a new one.
    """
    return MiniAppService(backend=backend)


def main() -> None:
    """Entry point for starting the Mini App's standalone API server."""
    backend = build_backend()
    service = create_service(backend=backend)
    api = MiniAppAPI(service)
    server = api.create_server(host="0.0.0.0", port=8000)
    print("Mini App API listening on http://0.0.0.0:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
