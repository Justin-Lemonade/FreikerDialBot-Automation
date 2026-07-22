"""Session lifecycle management for the customer calling workflow."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone

from database import Database
from formatting import format_duration_coarse, format_duration_fine
from statistics_engine import StatisticsEngine


# Fun, memorable session labels (e.g. "Swift Falcon") instead of a bare
# timestamp. The timestamp is never lost -- it's kept as a permanent
# " - " suffix (the "notation") even if the operator renames the label.
_ADJECTIVES = [
    "Swift", "Steady", "Bright", "Calm", "Bold", "Quick", "Sharp", "Clear",
    "Sunny", "Brisk", "Golden", "Silent", "Rapid", "Vivid", "Keen", "Prime",
]
_NOUNS = [
    "Falcon", "River", "Comet", "Harbor", "Summit", "Meadow", "Ridge",
    "Horizon", "Voyage", "Beacon", "Current", "Compass", "Anchor", "Trail", "Signal",
]


def _format_timestamp_notation(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%b %d, %I:%M %p UTC")


def generate_session_name(dt: datetime | None = None) -> str:
    """A fun label plus a permanent, worded date/time notation.

    e.g. "Swift Falcon - Jul 08, 08:42 AM UTC"
    """
    label = f"{random.choice(_ADJECTIVES)} {random.choice(_NOUNS)}"
    return f"{label} - {_format_timestamp_notation(dt)}"


@dataclass(frozen=True)
class SessionSummary:
    session_id: int
    imported: int
    contacted: int
    did_not_answer: int
    duration_seconds: int
    average_seconds_per_customer: int


class SessionManager:
    """Creates, starts, completes, and reports on calling sessions."""

    def __init__(self, database: Database, statistics: StatisticsEngine):
        self.database = database
        self.statistics = statistics

    def create_session(self, total_customers: int, session_name: str | None = None) -> int:
        timestamp = datetime.now(timezone.utc).isoformat()
        name = session_name or generate_session_name()
        with self.database.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sessions (
                    session_name,
                    created_at,
                    started_at,
                    finished_at,
                    duration_seconds,
                    total_customers,
                    status
                )
                VALUES (?, ?, NULL, NULL, NULL, ?, 'created')
                """,
                (name, timestamp, total_customers),
            )
            conn.commit()
            session_id = int(cursor.lastrowid)

        self.statistics.record_event("session_created", session_id=session_id)
        return session_id

    def rename_session(self, new_label: str) -> bool:
        """Rename the active (or most recently created) session's fun
        label, while always keeping the original timestamp notation --
        so a session can always be traced back to when it actually ran,
        even after a custom rename.
        """
        session = self.current_session() or self.most_recent_session()
        if not session:
            return False

        existing_name = session["session_name"] or ""
        if " - " in existing_name:
            _, _, notation = existing_name.partition(" - ")
        else:
            notation = _format_timestamp_notation()

        cleaned_label = new_label.strip()
        if not cleaned_label:
            return False

        new_name = f"{cleaned_label} - {notation}" if notation else cleaned_label
        self._update_session(session["id"], session_name=new_name)
        return True

    def current_session(self) -> dict | None:
        with self.database.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM sessions
                WHERE status IN ('created', 'running', 'paused')
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            return dict(row) if row else None

    def start_current_session(self, telegram_user_id: int | None = None) -> dict | None:
        session = self.current_session()
        if not session:
            total = self.database.count_customers()
            if total == 0:
                return None
            session_id = self.create_session(total)
            session = self.get_session(session_id)

        now = datetime.now(timezone.utc).isoformat()
        updates = {"status": "running"}
        if not session["started_at"]:
            updates["started_at"] = now
        self._update_session(session["id"], **updates)
        self.statistics.record_event(
            "queue_started",
            session_id=session["id"],
            telegram_user_id=telegram_user_id,
        )
        return self.get_session(session["id"])

    def pause_current_session(self, telegram_user_id: int | None = None) -> None:
        session = self.current_session()
        if not session:
            return
        self._update_session(session["id"], status="paused")
        self.statistics.record_event(
            "queue_paused",
            session_id=session["id"],
            telegram_user_id=telegram_user_id,
        )

    def resume_current_session(self, telegram_user_id: int | None = None) -> dict | None:
        session = self.start_current_session(telegram_user_id=telegram_user_id)
        if session:
            self.statistics.record_event(
                "queue_resumed",
                session_id=session["id"],
                telegram_user_id=telegram_user_id,
            )
        return session

    def complete_current_session(self, telegram_user_id: int | None = None) -> SessionSummary | None:
        session = self.current_session()
        if not session:
            return None
        if session["status"] == "completed":
            return self.summary_for_session(session["id"])

        finished = datetime.now(timezone.utc)
        started_at = self._parse_time(session["started_at"]) or finished
        duration_seconds = max(0, int((finished - started_at).total_seconds()))
        self._update_session(
            session["id"],
            status="completed",
            finished_at=finished.isoformat(),
            duration_seconds=duration_seconds,
        )
        self.statistics.record_event(
            "queue_completed",
            session_id=session["id"],
            telegram_user_id=telegram_user_id,
        )
        return self.summary_for_session(session["id"])

    def summary_for_session(self, session_id: int) -> SessionSummary:
        session = self.get_session(session_id)
        counts = self.database.status_counts()
        duration_seconds = int(session["duration_seconds"] or 0)
        handled = counts["warned"] + counts["call_later"]
        average_seconds_per_customer = (
            round(duration_seconds / handled) if handled else 0
        )
        return SessionSummary(
            session_id=session_id,
            imported=int(session["total_customers"]),
            contacted=counts["warned"],
            did_not_answer=counts["call_later"],
            duration_seconds=duration_seconds,
            average_seconds_per_customer=average_seconds_per_customer,
        )

    def render_current_session(self) -> str:
        session = self.current_session()
        if not session:
            return "No active session."

        counts = self.database.status_counts()
        started = session["started_at"] or "Not started"
        elapsed = self._elapsed_text(session["started_at"])
        return (
            f"Session Name\n{session['session_name']}\n\n"
            f"Started\n{started}\n\n"
            f"Elapsed Time\n{elapsed}\n\n"
            f"Imported\n{session['total_customers']}\n\n"
            f"Remaining\n{counts['waiting']}\n\n"
            f"Contacted\n{counts['warned']}\n\n"
            f"Didn't Answer\n{counts['call_later']}\n\n"
            f"Status\n{session['status']}"
        )

    def render_completion_summary(self, summary: SessionSummary | None) -> str:
        if summary is None:
            return "Session Complete"
        return (
            "Session Complete\n"
            "--------------\n"
            f"Imported\n{summary.imported}\n\n"
            f"Contacted\n{summary.contacted}\n\n"
            f"Didn't Answer\n{summary.did_not_answer}\n\n"
            f"Duration\n{format_duration_coarse(summary.duration_seconds)}\n\n"
            f"Average Time Per Customer\n{format_duration_fine(summary.average_seconds_per_customer)}"
        )

    def most_recent_session(self) -> dict | None:
        """Return the most recent session regardless of status.

        Unlike current_session(), this includes completed sessions, so
        callers (such as the /summary admin command) can still report on
        a session immediately after it finishes.
        """
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def get_session(self, session_id: int) -> dict:
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Session does not exist: {session_id}")
            return dict(row)

    def _update_session(self, session_id: int, **fields) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values())
        with self.database.connect() as conn:
            conn.execute(
                f"UPDATE sessions SET {assignments} WHERE id = ?",
                [*values, session_id],
            )
            conn.commit()

    def _parse_time(self, value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value)

    def _elapsed_text(self, started_at: str | None) -> str:
        start = self._parse_time(started_at)
        if not start:
            return "0 minutes"
        seconds = max(0, int((datetime.now(timezone.utc) - start).total_seconds()))
        return format_duration_coarse(seconds)
