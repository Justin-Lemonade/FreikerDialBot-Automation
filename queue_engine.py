"""Deterministic customer queue engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from database import Database
from logger import log
from session_manager import SessionManager
from statistics_engine import StatisticsEngine


QUEUE_STATUSES = {
    "waiting",
    "warned",
    "call_later",
    "skip",
    "paid",
    "invalid_number",
    "needs_review",
}

ActionStatus = Literal["warned", "call_later", "skip", "invalid_number"]

# app_settings key for the Settings > Calling Behavior > Max Call
# Attempts value. Stored as a string: "1".."4", or "unlimited". Missing
# key (never configured) also means unlimited -- this preserves the
# pre-existing behavior (every call_later customer is always requeued)
# for anyone who hasn't touched the setting yet.
MAX_CALL_ATTEMPTS_KEY = "max_call_attempts"


@dataclass(frozen=True)
class QueueProgress:
    current_position: int
    total_customers: int
    remaining: int
    contacted: int
    did_not_answer: int
    percent: int


@dataclass(frozen=True)
class QueueSelection:
    customer: dict[str, Any] | None
    progress: QueueProgress
    complete: bool
    paused: bool


class QueueEngine:
    """Presents waiting customers one at a time and records operator choices."""

    def __init__(
        self,
        database: Database,
        statistics: StatisticsEngine | None = None,
        session_manager: SessionManager | None = None,
    ):
        self.database = database
        self.statistics = statistics
        self.session_manager = session_manager

    def pause(self, telegram_user_id: int | None = None) -> None:
        self.database.update_queue_session(is_paused=1)
        if self.session_manager:
            self.session_manager.pause_current_session(telegram_user_id=telegram_user_id)

    def resume(self, telegram_user_id: int | None = None) -> QueueSelection:
        session = self.database.get_queue_session()
        if not session["session_start_time"]:
            self.database.update_queue_session(
                session_start_time=datetime.now(timezone.utc).isoformat(),
            )
        self.database.update_queue_session(is_paused=0)
        if self.session_manager:
            self.session_manager.resume_current_session(telegram_user_id=telegram_user_id)
        return self.next_customer()

    def status(self) -> QueueProgress:
        return self._progress()

    def peek_next_customer(self) -> dict[str, Any] | None:
        """Non-mutating equivalent of next_customer(): returns the next
        actionable customer WITHOUT committing it as current, advancing
        current_position, or writing a customer_loaded event.

        Used by read-only surfaces (Mini App GET endpoints) that must be
        safe to poll repeatedly. Also skips any customer who is
        blacklisted -- next_customer() intentionally does NOT do this
        yet (see BACKLOG.md: blacklist-in-queue-selection is a separate,
        undecided change to the *mutating* path), but a read-only peek
        showing a blacklisted customer as "up next" is unambiguously
        wrong regardless of that open decision, so this filters here.
        """
        exclude_ids: set[int] = set()
        while True:
            customer = self.database.get_next_actionable_customer(exclude_ids=exclude_ids or None)
            if customer is None:
                return None
            if customer.get("is_blacklisted"):
                exclude_ids.add(customer["id"])
                continue
            return customer

    def next_customer(self) -> QueueSelection:
        session = self.database.get_queue_session()
        progress = self._progress()

        if session["is_paused"]:
            customer = self._current_customer(session)
            return QueueSelection(customer, progress, complete=False, paused=True)

        exclude_ids: set[int] = set()
        while True:
            customer = self.database.get_next_actionable_customer(exclude_ids=exclude_ids or None)
            if customer is None:
                self.database.update_queue_session(current_customer_id=None)
                return QueueSelection(None, progress, complete=True, paused=False)

            if customer.get("is_blacklisted"):
                # A blacklisted customer must never become the active
                # customer -- previously only peek_next_customer() (the
                # read-only path) enforced this; the mutating advance
                # path used after every real outcome did not, so a
                # blacklisted customer could still surface as "current"
                # here. Same exclude-and-retry pattern as
                # peek_next_customer() for consistency.
                exclude_ids.add(customer["id"])
                continue

            if customer["status"] == "waiting" and not self._is_loadable(customer):
                # A round-trip verification issue slipped through import.
                # Skip this row instead of crashing the whole queue for
                # every operator behind it -- flag it and keep going.
                # (needs_review rows are EXPECTED to be incomplete and
                # should reach the operator via Skip/Delete, not be
                # auto-flagged here.)
                log.warning(
                    "Skipping malformed customer id=%s loan_number=%s",
                    customer.get("id"),
                    customer.get("loan_number"),
                )
                self.database.update_customer_status(customer["id"], "invalid_number")
                progress = self._progress()
                continue

            current_position = progress.contacted + progress.did_not_answer + 1
            self.database.update_queue_session(
                current_customer_id=customer["id"],
                current_position=current_position,
            )
            self._record_event("customer_loaded", customer=customer)
            progress = self._progress(current_position=current_position)
            return QueueSelection(customer, progress, complete=False, paused=False)

    @staticmethod
    def _is_loadable(customer: dict[str, Any]) -> bool:
        try:
            if not customer.get("loan_number") or not customer.get("first_name") or not customer.get("last_name"):
                return False
            phones = customer.get("phone_numbers")
            return isinstance(phones, list) and len(phones) > 0
        except Exception:
            return False

    def apply_action(
        self,
        customer_id: int,
        status: ActionStatus,
        telegram_user_id: int | None = None,
        duration_seconds: int | None = None,
    ) -> QueueSelection:
        if status not in {"warned", "call_later", "skip", "invalid_number"}:
            raise ValueError(f"Unsupported queue action: {status}")

        customer = self.database.get_customer(customer_id)
        if customer is None:
            return self.next_customer()

        current_status = customer["status"]
        if current_status not in {"waiting", "needs_review"}:
            return self.next_customer()

        if current_status == "needs_review" and status not in {"skip", "invalid_number"}:
            # An incomplete record can't be marked warned/call_later --
            # only Skip, Wrong Number, or Delete (via delete_customer)
            # make sense here.
            return self.next_customer()

        self.database.update_customer_status(customer_id, status)
        if status == "call_later":
            # Count this attempt. Enforcement happens later, in
            # restart_call_later() -- see get_max_call_attempts().
            self.database.increment_attempt_count(customer_id)
        event_type = {
            "warned": "customer_warned",
            "call_later": "customer_call_later",
            "skip": "customer_skipped",
            "invalid_number": "customer_marked_invalid",
        }[status]
        self._record_event(
            event_type,
            customer=customer,
            telegram_user_id=telegram_user_id,
            duration_seconds=duration_seconds,
        )
        return self.next_customer()

    def delete_customer(
        self,
        customer_id: int,
        telegram_user_id: int | None = None,
    ) -> QueueSelection:
        """Permanently remove a customer record, e.g. for a needs_review
        row an operator decides isn't worth fixing, or a same-day
        duplicate they'd rather remove than call again."""
        customer = self.database.get_customer(customer_id)
        if customer is not None:
            self._record_event(
                "customer_deleted", customer=customer, telegram_user_id=telegram_user_id
            )
            self.database.delete_customer(customer_id)
        return self.next_customer()

    def get_max_call_attempts(self) -> int | None:
        """Reads the Max Call Attempts setting. Returns None for
        unlimited (the default -- unset, or explicitly "unlimited"), or
        an int for a configured cap (1-4 per the Settings spec, though
        any positive int is accepted)."""
        raw = self.database.get_setting(MAX_CALL_ATTEMPTS_KEY)
        if raw is None or raw == "unlimited":
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        return value if value > 0 else None

    def restart_call_later(self, telegram_user_id: int | None = None) -> QueueSelection:
        """Requeue every 'call_later' customer back to 'waiting' and resume.

        Powers the "Call Back" button shown when a session completes.
        Customers marked warned/skip/paid/invalid_number are untouched.

        Customers who have already reached the configured Max Call
        Attempts limit are treated as exhausted and are intentionally
        left in call_later rather than requeued again -- see
        get_max_call_attempts() and Database.reassign_status().
        """
        max_attempts = self.get_max_call_attempts()
        requeued = self.database.reassign_status("call_later", "waiting", max_attempts=max_attempts)
        if requeued:
            self._record_event(
                "queue_call_back_started", telegram_user_id=telegram_user_id
            )
        self.database.update_queue_session(is_paused=0)
        if self.session_manager:
            self.session_manager.resume_current_session(telegram_user_id=telegram_user_id)
        return self.next_customer()

    def set_message_reference(self, chat_id: int, message_id: int) -> None:
        self.database.update_queue_session(
            queue_message_chat_id=chat_id,
            queue_message_id=message_id,
        )

    def edit_customer(
        self,
        customer_id: int,
        telegram_user_id: int | None = None,
        **fields: Any,
    ) -> dict[str, Any] | None:
        """Edit a customer's own fields (name, phone numbers, balance,
        days overdue, monthly payment, current overdue amount, original
        loan amount), auditing exactly what changed. Unlike
        apply_action/delete_customer, this doesn't touch queue position
        or status -- it's a data correction, not a queue-advancing
        action, so it does NOT call next_customer() and returns the
        updated customer record directly instead of a QueueSelection.
        """
        customer = self.database.get_customer(customer_id)
        if customer is None:
            return None

        changed = {
            key: (customer.get(key), value)
            for key, value in fields.items()
            if customer.get(key) != value
        }
        if not changed:
            return customer

        self.database.update_customer_fields(customer_id, **fields)
        summary = ", ".join(f"{key}: {old!r} -> {new!r}" for key, (old, new) in changed.items())
        self._record_event(
            "customer_edited",
            customer=customer,
            telegram_user_id=telegram_user_id,
            notes=summary,
        )
        return self.database.get_customer(customer_id)

    def blacklist_customer(
        self,
        customer_id: int,
        blacklisted: bool = True,
        telegram_user_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Set or clear a customer's blacklist flag, always with an audit
        event (blacklisting AND un-blacklisting are both consequential
        enough to want a record of who did it and when).

        This only marks state and records the audit trail -- it does NOT
        automatically skip blacklisted customers in the calling queue.
        That's a deliberate, separate decision; see BACKLOG.md.
        """
        customer = self.database.get_customer(customer_id)
        if customer is None:
            return None
        self.database.set_customer_blacklisted(customer_id, blacklisted)
        self._record_event(
            "customer_blacklisted" if blacklisted else "customer_unblacklisted",
            customer=customer,
            telegram_user_id=telegram_user_id,
        )
        return self.database.get_customer(customer_id)

    def blacklist_phone(
        self,
        phone: str,
        reason: str | None = None,
        telegram_user_id: int | None = None,
    ) -> None:
        """Blacklist a phone number, independent of any specific
        customer -- see Database.blacklist_phone for why this is
        decoupled from the customers table."""
        self.database.blacklist_phone(phone, reason=reason, telegram_user_id=telegram_user_id)
        self._record_event(
            "phone_blacklisted",
            telegram_user_id=telegram_user_id,
            notes=f"{phone} ({reason})" if reason else phone,
        )

    def unblacklist_phone(self, phone: str, telegram_user_id: int | None = None) -> None:
        self.database.unblacklist_phone(phone)
        self._record_event(
            "phone_unblacklisted",
            telegram_user_id=telegram_user_id,
            notes=phone,
        )

    def _current_customer(self, session: dict[str, Any]) -> dict[str, Any] | None:
        current_id = session.get("current_customer_id")
        if not current_id:
            return None
        return self.database.get_customer(int(current_id))

    def _progress(self, current_position: int | None = None) -> QueueProgress:
        counts = self.database.status_counts()
        # remaining/total must exclude blacklisted customers stuck in
        # 'waiting'/'needs_review' -- they can never actually be
        # selected (see peek_next_customer/next_customer's blacklist
        # skip), so counting them as "remaining" would mean a queue
        # whose only leftover customers are blacklisted could never
        # reach 100% or auto-complete. Confirmed live before this fix.
        actionable_remaining = self.database.actionable_waiting_count()
        handled = counts["warned"] + counts["call_later"] + counts["skip"] + counts["invalid_number"]
        total = handled + actionable_remaining
        remaining = actionable_remaining
        contacted = counts["warned"]
        did_not_answer = counts["call_later"]
        if current_position is None:
            session = self.database.get_queue_session()
            current_position = int(session["current_position"] or handled)
        percent = int(round((handled / total) * 100)) if total else 0
        return QueueProgress(
            current_position=current_position,
            total_customers=total,
            remaining=remaining,
            contacted=contacted,
            did_not_answer=did_not_answer,
            percent=percent,
        )

    def completion_summary(self) -> str:
        counts = self.database.status_counts()
        contacted = self.database.customers_by_status("warned")
        did_not_answer = self.database.customers_by_status("call_later")

        def names(customers: list[dict[str, Any]]) -> str:
            if not customers:
                return "None"
            return "\n".join(
                f"{customer['first_name']} {customer['last_name']}"
                for customer in customers
            )

        return (
            "Session Complete\n\n"
            f"Number Contacted: {counts['warned']}\n"
            f"Number Didn't Answer: {counts['call_later']}\n"
            f"Number Remaining: {counts['waiting']}\n\n"
            "Contacted\n"
            f"{names(contacted)}\n\n"
            "Didn't Answer\n"
            f"{names(did_not_answer)}"
        )

    def session_completion_summary(self, telegram_user_id: int | None = None) -> str | None:
        if not self.session_manager:
            return None
        summary = self.session_manager.complete_current_session(
            telegram_user_id=telegram_user_id,
        )
        return self.session_manager.render_completion_summary(summary)

    def _record_event(
        self,
        event_type: str,
        *,
        customer: dict[str, Any] | None = None,
        telegram_user_id: int | None = None,
        notes: str | None = None,
        duration_seconds: int | None = None,
    ) -> None:
        if not self.statistics:
            return
        session_id = None
        if self.session_manager:
            session = self.session_manager.current_session()
            session_id = session["id"] if session else None
        self.statistics.record_event(
            event_type,
            session_id=session_id,
            customer=customer,
            telegram_user_id=telegram_user_id,
            notes=notes,
            duration_seconds=duration_seconds,
        )
