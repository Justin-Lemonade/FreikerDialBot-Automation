"""Event history and statistics for calling sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from database import Database


EVENT_TYPES = {
    "session_created",
    "queue_started",
    "customer_loaded",
    "customer_warned",
    "customer_call_later",
    "customer_skipped",
    "customer_deleted",
    "customer_marked_invalid",
    "customer_edited",
    "customer_note_added",
    "customer_blacklisted",
    "customer_unblacklisted",
    "phone_blacklisted",
    "phone_unblacklisted",
    "queue_paused",
    "queue_resumed",
    "queue_completed",
    "queue_call_back_started",
    "admin_action",
}


@dataclass(frozen=True)
class StatisticsSnapshot:
    today: dict[str, int]
    lifetime: dict[str, int]
    average_contacts_per_session: int
    average_seconds_per_customer: int


def _format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s" if seconds else "0s"
    minutes, secs = divmod(seconds, 60)
    if secs:
        return f"{minutes}m {secs}s"
    return f"{minutes}m"


class StatisticsEngine:
    """Records immutable events and maintains running statistics."""

    def __init__(self, database: Database):
        self.database = database

    def record_event(
        self,
        event_type: str,
        *,
        session_id: int | None = None,
        customer: dict[str, Any] | None = None,
        telegram_user_id: int | None = None,
        notes: str | None = None,
        duration_seconds: int | None = None,
    ) -> int:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unsupported event type: {event_type}")

        timestamp = datetime.now(timezone.utc)
        customer_id = customer["id"] if customer else None
        loan_number = customer["loan_number"] if customer else None

        with self.database.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO customer_events (
                    session_id,
                    loan_number,
                    customer_id,
                    event_type,
                    event_timestamp,
                    telegram_user_id,
                    notes,
                    duration_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    loan_number,
                    customer_id,
                    event_type,
                    timestamp.isoformat(),
                    telegram_user_id,
                    notes,
                    duration_seconds,
                ),
            )
            self._update_daily_statistics(
                conn,
                event_type,
                timestamp.date().isoformat(),
                session_id,
            )
            conn.commit()
            return int(cursor.lastrowid)

    def _update_daily_statistics(
        self,
        conn,
        event_type: str,
        date: str,
        session_id: int | None,
    ) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO daily_statistics (
                date,
                customers_loaded,
                customers_contacted,
                customers_not_answered,
                sessions_completed
            )
            VALUES (?, 0, 0, 0, 0)
            """,
            (date,),
        )

        if event_type == "session_created":
            loaded = self._session_total_customers(conn, session_id)
            conn.execute(
                """
                UPDATE daily_statistics
                SET customers_loaded = customers_loaded + ?
                WHERE date = ?
                """,
                (loaded, date),
            )
        elif event_type == "customer_warned":
            conn.execute(
                """
                UPDATE daily_statistics
                SET customers_contacted = customers_contacted + 1
                WHERE date = ?
                """,
                (date,),
            )
        elif event_type == "customer_call_later":
            conn.execute(
                """
                UPDATE daily_statistics
                SET customers_not_answered = customers_not_answered + 1
                WHERE date = ?
                """,
                (date,),
            )
        elif event_type == "queue_completed":
            conn.execute(
                """
                UPDATE daily_statistics
                SET sessions_completed = sessions_completed + 1
                WHERE date = ?
                """,
                (date,),
            )

    def _session_total_customers(self, conn, session_id: int | None) -> int:
        if session_id is None:
            return 0
        row = conn.execute(
            "SELECT total_customers FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return int(row["total_customers"]) if row else 0

    def today_statistics(self) -> dict[str, int]:
        today = datetime.now(timezone.utc).date().isoformat()
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT * FROM daily_statistics WHERE date = ?",
                (today,),
            ).fetchone()
            if not row:
                return self._empty_daily()
            return self._daily_from_row(row)

    def lifetime_statistics(self) -> dict[str, int]:
        with self.database.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(customers_loaded), 0) AS customers_loaded,
                    COALESCE(SUM(customers_contacted), 0) AS customers_contacted,
                    COALESCE(SUM(customers_not_answered), 0) AS customers_not_answered,
                    COALESCE(SUM(sessions_completed), 0) AS sessions_completed
                FROM daily_statistics
                """
            ).fetchone()
            sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

        stats = self._daily_from_row(row)
        stats["sessions"] = int(sessions)
        return stats

    def lifetime_total_duration_seconds(self) -> int:
        """Sum of duration_seconds across every completed session, ever.

        Independent of daily_statistics/customers (never reset by
        /reset or /clear), since it reads straight from the permanent
        sessions table.
        """
        with self.database.connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(duration_seconds), 0) AS total
                FROM sessions
                WHERE status = 'completed'
                """
            ).fetchone()
            return int(row["total"])

    def snapshot(self) -> StatisticsSnapshot:
        lifetime = self.lifetime_statistics()
        completed_sessions = lifetime["sessions_completed"]
        average = (
            round(lifetime["customers_contacted"] / completed_sessions)
            if completed_sessions
            else 0
        )
        handled = lifetime["customers_contacted"] + lifetime["customers_not_answered"]
        total_seconds = self.lifetime_total_duration_seconds()
        average_seconds_per_customer = round(total_seconds / handled) if handled else 0
        return StatisticsSnapshot(
            today=self.today_statistics(),
            lifetime=lifetime,
            average_contacts_per_session=average,
            average_seconds_per_customer=average_seconds_per_customer,
        )

    def render_statistics(self) -> str:
        snapshot = self.snapshot()
        today = snapshot.today
        lifetime = snapshot.lifetime
        return (
            "Today's Statistics\n"
            "--------------\n"
            f"Customers Imported\n{today['customers_loaded']}\n\n"
            f"Customers Contacted\n{today['customers_contacted']}\n\n"
            f"Didn't Answer\n{today['customers_not_answered']}\n\n"
            f"Completed Sessions\n{today['sessions_completed']}\n\n"
            "Lifetime Statistics\n"
            "--------------\n"
            f"Customers Imported\n{lifetime['customers_loaded']}\n\n"
            f"Customers Contacted\n{lifetime['customers_contacted']}\n\n"
            f"Didn't Answer\n{lifetime['customers_not_answered']}\n\n"
            f"Sessions\n{lifetime['sessions']}\n\n"
            "Average Contacts Per Session\n"
            f"{snapshot.average_contacts_per_session}\n\n"
            "Average Time Per Customer (Lifetime)\n"
            f"{_format_duration(snapshot.average_seconds_per_customer)}"
        )

    def _empty_daily(self) -> dict[str, int]:
        return {
            "customers_loaded": 0,
            "customers_contacted": 0,
            "customers_not_answered": 0,
            "sessions_completed": 0,
        }

    def _daily_from_row(self, row) -> dict[str, int]:
        return {
            "customers_loaded": int(row["customers_loaded"]),
            "customers_contacted": int(row["customers_contacted"]),
            "customers_not_answered": int(row["customers_not_answered"]),
            "sessions_completed": int(row["sessions_completed"]),
        }
