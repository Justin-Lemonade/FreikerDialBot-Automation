"""SQLite storage for imported customers and queue session state."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATABASE_PATH, ensure_directories
from logger import log


SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_number TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    phone_numbers TEXT NOT NULL,
    balance TEXT,
    days_overdue TEXT,
    status TEXT NOT NULL DEFAULT 'waiting',
    import_timestamp TEXT NOT NULL,
    status_timestamp TEXT
);
"""

SESSION_SCHEMA = """
CREATE TABLE IF NOT EXISTS queue_session (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_customer_id INTEGER,
    current_position INTEGER NOT NULL DEFAULT 0,
    session_start_time TEXT,
    is_paused INTEGER NOT NULL DEFAULT 0,
    queue_message_chat_id INTEGER,
    queue_message_id INTEGER,
    updated_at TEXT NOT NULL
);
"""

SESSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    duration_seconds INTEGER,
    total_customers INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL
);
"""

CUSTOMER_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS customer_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    loan_number TEXT,
    customer_id INTEGER,
    event_type TEXT NOT NULL,
    event_timestamp TEXT NOT NULL,
    telegram_user_id INTEGER,
    notes TEXT,
    duration_seconds INTEGER,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
"""

DAILY_STATISTICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_statistics (
    date TEXT PRIMARY KEY,
    customers_loaded INTEGER NOT NULL DEFAULT 0,
    customers_contacted INTEGER NOT NULL DEFAULT 0,
    customers_not_answered INTEGER NOT NULL DEFAULT 0,
    sessions_completed INTEGER NOT NULL DEFAULT 0
);
"""

# Phone-level blacklist, deliberately independent of the customers table:
# a customer row can be deleted (see delete_customer), but a blacklisted
# phone number needs to survive that and survive across different loans
# that happen to reuse the same number. See ARCHITECTURE.md's Customer
# Model Review for why this is a separate table rather than a column.
BLACKLISTED_PHONES_SCHEMA = """
CREATE TABLE IF NOT EXISTS blacklisted_phones (
    phone TEXT PRIMARY KEY,
    reason TEXT,
    blacklisted_at TEXT NOT NULL,
    telegram_user_id INTEGER
);
"""

# Generic key/value store for operator-configurable, backend-enforced
# preferences (Settings screen). Deliberately generic rather than one
# column per setting: the Mini App master spec requires that "adding a
# setting should ideally mean: define its type, default, control, and
# persistence -- without restructuring the entire Settings page." A
# single row is written per known setting key; unknown/legacy keys are
# simply ignored by readers. Global (not per-operator) because the
# underlying behaviors it controls (max attempts, auto-advance) apply to
# the one shared queue every operator works from, not a personal
# profile -- see ARCHITECTURE.md.
APP_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# Columns added via _migrate() rather than the base SCHEMA above, so
# existing on-disk databases pick them up automatically without a manual
# migration step. New financial fields (monthly_payment,
# current_overdue_amount, original_loan_amount) deliberately follow the
# same convention as balance/days_overdue: nullable TEXT, never numeric --
# OCR/import data is frequently partial, masked, or illegible, and TEXT
# lets "" mean "not visible" without inventing a sentinel value. See
# ARCHITECTURE.md's Customer Model Review.
_CUSTOMER_MIGRATION_COLUMNS: dict[str, str] = {
    "status_timestamp": "TEXT",
    "warning_note": "TEXT",
    "is_blacklisted": "INTEGER NOT NULL DEFAULT 0",
    "monthly_payment": "TEXT",
    "current_overdue_amount": "TEXT",
    "original_loan_amount": "TEXT",
    "last_edited_timestamp": "TEXT",
    # How many times this customer has been marked "call_later" (Didn't
    # Answer). Backs the real Settings > Max Call Attempts feature --
    # QueueEngine.apply_action increments this on every call_later
    # outcome, and restart_call_later() ("Call Back") uses it to decide
    # whether a customer is still eligible for another attempt. See
    # ARCHITECTURE.md for why this replaced the old "just re-run
    # call_later manually forever" behavior.
    "attempt_count": "INTEGER NOT NULL DEFAULT 0",
}

# Every standard customer field beyond the original core five, used by
# insert_customers/_customer_from_row/update_customer_fields so a new
# field only needs to be added in this one list (plus the migration
# entry above) rather than threaded through each method by hand.
EXTENDED_CUSTOMER_FIELDS = (
    "monthly_payment",
    "current_overdue_amount",
    "original_loan_amount",
)


class Database:
    """Small SQLite repository for the importer."""

    def __init__(self, path: Path = DATABASE_PATH):
        self.path = path
        ensure_directories()
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        # WAL mode improves concurrent read/write behavior (the Mini App
        # API and the bot can both hold the DB open), and a busy timeout
        # prevents immediate "database is locked" errors when two
        # connections contend. WAL is persistent per database file;
        # busy_timeout is per-connection.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute(SCHEMA)
            self._migrate(conn)
            conn.execute(SESSION_SCHEMA)
            conn.execute(SESSIONS_SCHEMA)
            conn.execute(CUSTOMER_EVENTS_SCHEMA)
            conn.execute(DAILY_STATISTICS_SCHEMA)
            conn.execute(BLACKLISTED_PHONES_SCHEMA)
            conn.execute(APP_SETTINGS_SCHEMA)
            # Performance indexes for high-cardinality / frequently filtered columns.
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_customers_status_import "
                "ON customers(status, import_timestamp, id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_customers_status_timestamp "
                "ON customers(status, status_timestamp, id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_session "
                "ON customer_events(session_id, event_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_customer "
                "ON customer_events(customer_id, event_timestamp)"
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO queue_session (
                    id,
                    current_customer_id,
                    current_position,
                    session_start_time,
                    is_paused,
                    updated_at
                )
                VALUES (1, NULL, 0, NULL, 0, ?)
                """,
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.commit()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(customers)").fetchall()
        }
        for column, column_type in _CUSTOMER_MIGRATION_COLUMNS.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE customers ADD COLUMN {column} {column_type}")

        event_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(customer_events)").fetchall()
        }
        if event_columns and "duration_seconds" not in event_columns:
            conn.execute("ALTER TABLE customer_events ADD COLUMN duration_seconds INTEGER")

    def insert_customers(self, customers: list[dict[str, Any]], status: str = "waiting") -> int:
        """Insert new customers, or refresh ones reappearing from a prior
        session, for this import.

        - Brand-new loan_number: inserted fresh with `status`.
        - Existing loan_number still 'waiting' (sitting un-worked in the
          active queue): left untouched -- a true duplicate within a
          single unworked queue. Surfaced separately by the round-trip
          verification pass as "already existed, not re-imported".
        - Existing loan_number already worked in a PRIOR session (any
          status other than 'waiting'): this is a legitimate reappearance
          across sessions and IS allowed -- refreshed and reset to
          `status`. If they were last worked earlier TODAY (UTC), a
          same-day warning_note is attached so the operator sees it on
          the customer's card before calling again.

        A customer dict may include an optional "_issue" key (from
        validation's flagged rows) which becomes the warning_note for
        brand-new inserts.

        Returns the number of rows actually inserted or refreshed.
        """
        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()
        affected = 0

        with self.connect() as conn:
            for customer in customers:
                row_status = customer.get("_status", status)
                issue_note = customer.get("_issue")
                phone_json = json.dumps(customer["phone_numbers"], ensure_ascii=False)
                existing = conn.execute(
                    "SELECT status, status_timestamp FROM customers WHERE loan_number = ?",
                    (customer["loan_number"],),
                ).fetchone()

                extended_values = [customer.get(field, "") for field in EXTENDED_CUSTOMER_FIELDS]

                if existing is None:
                    extended_columns = ", ".join(EXTENDED_CUSTOMER_FIELDS)
                    extended_placeholders = ", ".join("?" for _ in EXTENDED_CUSTOMER_FIELDS)
                    conn.execute(
                        f"""
                        INSERT INTO customers (
                            loan_number, first_name, last_name, phone_numbers,
                            balance, days_overdue, status, import_timestamp, warning_note,
                            {extended_columns}
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, {extended_placeholders})
                        """,
                        (
                            customer["loan_number"],
                            customer["first_name"],
                            customer["last_name"],
                            phone_json,
                            customer.get("balance", ""),
                            customer.get("days_overdue", ""),
                            row_status,
                            timestamp,
                            issue_note,
                            *extended_values,
                        ),
                    )
                    affected += 1
                    continue

                if existing["status"] == "waiting":
                    # Still un-worked from an earlier import into the same
                    # active queue -- leave it alone.
                    continue

                # Already worked in a prior session -- allowed to be
                # re-queued for a new one.
                warning_note = issue_note
                previous_timestamp = existing["status_timestamp"]
                if previous_timestamp:
                    previous_dt = datetime.fromisoformat(previous_timestamp)
                    if previous_dt.date() == now.date():
                        formatted = previous_dt.strftime("%I:%M %p UTC")
                        warning_note = f"Already contacted today at {formatted}"

                extended_assignments = ", ".join(f"{field} = ?" for field in EXTENDED_CUSTOMER_FIELDS)
                conn.execute(
                    f"""
                    UPDATE customers
                    SET first_name = ?, last_name = ?, phone_numbers = ?,
                        balance = ?, days_overdue = ?, status = ?,
                        status_timestamp = NULL, import_timestamp = ?,
                        warning_note = ?, {extended_assignments}
                    WHERE loan_number = ?
                    """,
                    (
                        customer["first_name"],
                        customer["last_name"],
                        phone_json,
                        customer.get("balance", ""),
                        customer.get("days_overdue", ""),
                        row_status,
                        timestamp,
                        warning_note,
                        *extended_values,
                        customer["loan_number"],
                    ),
                )
                affected += 1

            conn.commit()
        return affected

    def delete_customer(self, customer_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
            conn.commit()

    def count_customers(self) -> int:
        with self.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0])

    def clear_customers(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM customers")
            conn.execute(
                """
                UPDATE queue_session
                SET current_customer_id = NULL,
                    current_position = 0,
                    session_start_time = NULL,
                    is_paused = 0,
                    queue_message_chat_id = NULL,
                    queue_message_id = NULL,
                    updated_at = ?
                WHERE id = 1
                """,
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.commit()

    def reset_queue(self) -> None:
        """Reset every customer back to 'waiting' and clear queue progress.

        Preserves the customers themselves, the current session row,
        customer_events history, and daily_statistics.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE customers
                SET status = 'waiting', status_timestamp = NULL
                """
            )
            conn.execute(
                """
                UPDATE queue_session
                SET current_customer_id = NULL,
                    current_position = 0,
                    is_paused = 0,
                    queue_message_chat_id = NULL,
                    queue_message_id = NULL,
                    updated_at = ?
                WHERE id = 1
                """,
                (timestamp,),
            )
            conn.commit()

    def get_customers_by_loan_numbers(self, loan_numbers: list[str]) -> list[dict[str, Any]]:
        """Re-fetch specific customers as they actually landed in the DB.

        Used right after import to verify the round trip (JSON encoding of
        phone_numbers, etc.) actually worked, instead of trusting the
        in-memory validated dicts blindly.
        """
        if not loan_numbers:
            return []
        with self.connect() as conn:
            placeholders = ",".join("?" for _ in loan_numbers)
            rows = conn.execute(
                f"SELECT * FROM customers WHERE loan_number IN ({placeholders})",
                loan_numbers,
            ).fetchall()
            return [self._customer_from_row(row) for row in rows]

    def get_all_customers(self) -> list[dict[str, Any]]:
        """Return every customer row regardless of status, in import order."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM customers ORDER BY id ASC"
            ).fetchall()
            return [self._customer_from_row(row) for row in rows]

    def reassign_status(self, from_status: str, to_status: str, max_attempts: int | None = None) -> int:
        """Bulk-move every customer in from_status to to_status.

        Clears status_timestamp on affected rows (their status is changing
        again) and returns the number of rows affected. Used by the "Call
        Back" feature to requeue everyone marked call_later.

        max_attempts, when given, excludes rows whose attempt_count has
        already reached the configured Max Call Attempts limit -- those
        customers are "exhausted" and stay in from_status rather than
        being requeued again. None means unlimited (every row is
        requeued), matching the setting's own "Unlimited" option.
        """
        with self.connect() as conn:
            if max_attempts is None:
                cursor = conn.execute(
                    """
                    UPDATE customers
                    SET status = ?, status_timestamp = NULL
                    WHERE status = ?
                    """,
                    (to_status, from_status),
                )
            else:
                cursor = conn.execute(
                    """
                    UPDATE customers
                    SET status = ?, status_timestamp = NULL
                    WHERE status = ? AND attempt_count < ?
                    """,
                    (to_status, from_status, max_attempts),
                )
            conn.commit()
            return cursor.rowcount

    def increment_attempt_count(self, customer_id: int) -> int:
        """Increments and returns the customer's attempt_count. Called by
        QueueEngine.apply_action exactly once per call_later ("Didn't
        Answer") outcome -- the single write path both the Telegram bot
        and the Mini App share, so attempts are counted identically
        regardless of which frontend recorded the outcome."""
        with self.connect() as conn:
            conn.execute(
                "UPDATE customers SET attempt_count = attempt_count + 1 WHERE id = ?",
                (customer_id,),
            )
            conn.commit()
            row = conn.execute(
                "SELECT attempt_count FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
            return int(row["attempt_count"]) if row else 0

    # -----------------------------------------------------------------------
    # App settings -- generic key/value store for backend-enforced operator
    # preferences (see APP_SETTINGS_SCHEMA docstring).
    # -----------------------------------------------------------------------

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def get_settings(self, keys: list[str]) -> dict[str, str | None]:
        with self.connect() as conn:
            placeholders = ", ".join("?" for _ in keys)
            rows = conn.execute(
                f"SELECT key, value FROM app_settings WHERE key IN ({placeholders})",
                tuple(keys),
            ).fetchall()
            found = {row["key"]: row["value"] for row in rows}
            return {key: found.get(key) for key in keys}

    def set_setting(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def get_customer(self, customer_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM customers WHERE id = ?",
                (customer_id,),
            ).fetchone()
            return self._customer_from_row(row) if row else None

    def get_next_waiting_customer(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM customers
                WHERE status = 'waiting'
                ORDER BY import_timestamp ASC, id ASC
                LIMIT 1
                """
            ).fetchone()
            return self._customer_from_row(row) if row else None

    def get_next_actionable_customer(self, exclude_ids: set[int] | None = None) -> dict[str, Any] | None:
        """Like get_next_waiting_customer, but also surfaces 'needs_review'
        rows (imported but missing name/phone) so the operator gets a
        chance to Skip or Delete them instead of them being silently
        stuck forever.

        exclude_ids lets a caller peek past specific rows (e.g. a
        blacklisted customer) without mutating anything -- the row stays
        'waiting', it's just excluded from *this* query's result.
        """
        with self.connect() as conn:
            if exclude_ids:
                placeholders = ", ".join("?" for _ in exclude_ids)
                row = conn.execute(
                    f"""
                    SELECT * FROM customers
                    WHERE status IN ('waiting', 'needs_review')
                      AND id NOT IN ({placeholders})
                    ORDER BY import_timestamp ASC, id ASC
                    LIMIT 1
                    """,
                    tuple(exclude_ids),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM customers
                    WHERE status IN ('waiting', 'needs_review')
                    ORDER BY import_timestamp ASC, id ASC
                    LIMIT 1
                    """
                ).fetchone()
            return self._customer_from_row(row) if row else None

    def update_customer_status(self, customer_id: int, status: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE customers
                SET status = ?, status_timestamp = ?, warning_note = NULL
                WHERE id = ?
                """,
                (status, timestamp, customer_id),
            )
            conn.commit()

    def count_by_status(self, status: str) -> int:
        with self.connect() as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM customers WHERE status = ?",
                    (status,),
                ).fetchone()[0]
            )

    def status_counts(self) -> dict[str, int]:
        counts = {
            "waiting": 0,
            "warned": 0,
            "call_later": 0,
            "skip": 0,
            "paid": 0,
            "invalid_number": 0,
            "needs_review": 0,
        }
        with self.connect() as conn:
            for row in conn.execute(
                "SELECT status, COUNT(*) AS count FROM customers GROUP BY status"
            ):
                counts[row["status"]] = int(row["count"])
        return counts

    def actionable_waiting_count(self) -> int:
        """Count of 'waiting'/'needs_review' customers who are NOT
        blacklisted -- i.e. customers who could actually still be
        surfaced by peek_next_customer()/next_customer().

        status_counts()['waiting'] + status_counts()['needs_review']
        counts blacklisted customers too, since it only groups by
        status. That's fine for status_counts() as a general-purpose
        primitive, but using it directly for "how many are left in the
        queue" is wrong: a blacklisted customer sitting in 'waiting'
        status can never actually be selected, yet would count as
        'remaining' forever, meaning the queue could never reach 100%
        or auto-complete. Confirmed live: a session with only a
        blacklisted customer left stayed at remaining=1/67% forever.
        """
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count FROM customers
                WHERE status IN ('waiting', 'needs_review')
                  AND is_blacklisted = 0
                """
            ).fetchone()
            return int(row["count"]) if row else 0

    def customers_by_status(self, status: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM customers
                WHERE status = ?
                ORDER BY status_timestamp ASC, id ASC
                """,
                (status,),
            ).fetchall()
            return [self._customer_from_row(row) for row in rows]

    # -----------------------------------------------------------------------
    # Search, history, editing, blacklist -- the customer-record surface.
    # -----------------------------------------------------------------------

    def search_customers(self, query: str, limit: int = 20, fields: list[str] | None = None) -> list[dict[str, Any]]:
        """Search across loan number, name, and phone numbers.

        Searches every customer regardless of status (waiting, warned,
        paid, etc.) -- finding "what happened with this person before" is
        the point, not just who's currently queued. Phone matching is a
        plain substring check against the raw JSON-encoded phone_numbers
        column, which works fine for digit/substring search without
        depending on SQLite's json1 extension being compiled in.

        Also matches the COMBINED "first last" name -- confirmed by
        direct testing that searching "John Smith" previously returned
        zero results even with a customer named exactly John Smith on
        file, since first_name/last_name are separate columns and
        neither alone contains the full typed string.

        `fields` scopes which of the three field groups
        ("name", "loanNumber", "phone") get OR'd into the WHERE clause
        -- the real backend enforcement behind Settings > Search >
        Default Search Fields (MiniAppService.search_customers reads
        that setting and passes it through here; nothing about which
        fields are searched happens client-side). `None` (the default,
        used by every pre-existing caller) means "no restriction, search
        all three" -- unchanged from this method's original behavior.
        """
        stripped = query.strip()
        if not stripped:
            return []
        pattern = f"%{stripped}%"
        active_fields = set(fields) if fields is not None else {"name", "loanNumber", "phone"}
        clauses: list[str] = []
        params: list[str] = []
        if "loanNumber" in active_fields:
            clauses.append("loan_number LIKE ?")
            params.append(pattern)
        if "name" in active_fields:
            clauses.append("first_name LIKE ?")
            params.append(pattern)
            clauses.append("last_name LIKE ?")
            params.append(pattern)
            clauses.append("(first_name || ' ' || last_name) LIKE ?")
            params.append(pattern)
        if "phone" in active_fields:
            clauses.append("phone_numbers LIKE ?")
            params.append(pattern)
        if not clauses:
            # Every field group was excluded (e.g. an empty `fields`
            # list slipped through despite the service layer's own
            # fallback) -- searching literally nothing would silently
            # break the Search screen for every query, which is worse
            # than ignoring an impossible restriction. Fall back to the
            # unrestricted default rather than returning zero results
            # for every search.
            clauses = ["loan_number LIKE ?", "first_name LIKE ?", "last_name LIKE ?", "phone_numbers LIKE ?", "(first_name || ' ' || last_name) LIKE ?"]
            params = [pattern, pattern, pattern, pattern, pattern]
        where_sql = " OR ".join(clauses)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM customers
                WHERE {where_sql}
                ORDER BY id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
            return [self._customer_from_row(row) for row in rows]

    def get_customer_events(self, customer_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """Full event history for one customer, most recent first --
        every status change, note, edit, and blacklist action recorded
        against them. This is the "call history" the customer record
        surface is built on; the data already existed in customer_events,
        this is just the first method that reads it back per-customer."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM customer_events
                WHERE customer_id = ?
                ORDER BY event_timestamp DESC, id DESC
                LIMIT ?
                """,
                (customer_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def update_customer_fields(self, customer_id: int, **fields: Any) -> None:
        """Edit a customer's own data (name, phone numbers, balance,
        days overdue, and the new financial fields). Deliberately does
        NOT allow editing loan_number (the unique key imports are keyed
        on -- fixing a wrong loan_number is a bigger operation than a
        field edit) or status (that's QueueEngine's job, via
        update_customer_status).

        phone_numbers, if provided, must already be a list of normalized
        strings -- callers should run values through
        validation.normalize_phone_number themselves, same as import
        does, so there's one normalization rule, not two.

        Sets last_edited_timestamp automatically -- distinct from
        status_timestamp (which tracks call outcomes, not data edits) so
        an operator can tell "when was this customer last called" apart
        from "when was this record last corrected."
        """
        if not fields:
            return
        editable = {
            "first_name",
            "last_name",
            "balance",
            "days_overdue",
            "phone_numbers",
            "monthly_payment",
            "current_overdue_amount",
            "original_loan_amount",
        }
        unknown = set(fields) - editable
        if unknown:
            raise ValueError(f"Cannot edit field(s): {', '.join(sorted(unknown))}")

        values: dict[str, Any] = dict(fields)
        if "phone_numbers" in values:
            values["phone_numbers"] = json.dumps(values["phone_numbers"], ensure_ascii=False)
        values["last_edited_timestamp"] = datetime.now(timezone.utc).isoformat()

        assignments = ", ".join(f"{key} = ?" for key in values)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE customers SET {assignments} WHERE id = ?",
                [*values.values(), customer_id],
            )
            conn.commit()

    def set_customer_blacklisted(self, customer_id: int, blacklisted: bool) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE customers SET is_blacklisted = ? WHERE id = ?",
                (1 if blacklisted else 0, customer_id),
            )
            conn.commit()

    def is_phone_blacklisted(self, phone: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM blacklisted_phones WHERE phone = ?", (phone,)
            ).fetchone()
            return row is not None

    def first_non_blacklisted_phone(self, phone_numbers: list[str]) -> str:
        """Pick the phone to actually display/dial: the first number in
        the list that isn't blacklisted, falling back to the first
        number at all if every number is blacklisted (still show
        *something* rather than silently blank the field)."""
        if not phone_numbers:
            return ""
        for phone in phone_numbers:
            if not self.is_phone_blacklisted(phone):
                return phone
        return phone_numbers[0]

    def blacklist_phone(
        self, phone: str, reason: str | None = None, telegram_user_id: int | None = None
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO blacklisted_phones (phone, reason, blacklisted_at, telegram_user_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(phone) DO UPDATE SET
                    reason = excluded.reason,
                    blacklisted_at = excluded.blacklisted_at,
                    telegram_user_id = excluded.telegram_user_id
                """,
                (phone, reason, datetime.now(timezone.utc).isoformat(), telegram_user_id),
            )
            conn.commit()

    def unblacklist_phone(self, phone: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM blacklisted_phones WHERE phone = ?", (phone,))
            conn.commit()

    def get_customer_record(self, customer_id: int) -> dict[str, Any] | None:
        """The one shared "full customer view" both frontends use.
        Combines the customer row, its blacklist state (customer-level
        and per-phone), its notes, and its full event history, so
        neither frontend has to assemble this itself from three separate
        queries.
        """
        customer = self.get_customer(customer_id)
        if customer is None:
            return None

        events = self.get_customer_events(customer_id)
        notes = [
            {
                "text": event["notes"],
                "telegram_user_id": event["telegram_user_id"],
                "timestamp": event["event_timestamp"],
            }
            for event in events
            if event["event_type"] == "customer_note_added" and event["notes"]
        ]
        blacklisted_phones = [
            phone for phone in customer["phone_numbers"] if self.is_phone_blacklisted(phone)
        ]

        record = dict(customer)
        record["notes"] = notes
        record["history"] = events
        record["blacklisted_phones"] = blacklisted_phones
        return record

    def get_queue_session(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM queue_session WHERE id = 1").fetchone()
            return dict(row)

    def update_queue_session(self, **fields: Any) -> None:
        """Update the single queue_session row (id=1).

        Deliberately whitelists the fields that may be written, mirroring
        update_customer_fields -- queue_session is internal queue state,
        and callers must not be able to write arbitrary columns (e.g. a
        typo'd field name would otherwise silently create a new column
        via the dynamic UPDATE). `updated_at` is always set automatically.
        """
        if not fields:
            return
        editable = {
            "current_customer_id",
            "current_position",
            "session_start_time",
            "is_paused",
            "queue_message_chat_id",
            "queue_message_id",
            "updated_at",
        }
        unknown = set(fields) - editable
        if unknown:
            raise ValueError(f"Cannot update queue session field(s): {', '.join(sorted(unknown))}")

        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values())
        with self.connect() as conn:
            conn.execute(
                f"UPDATE queue_session SET {assignments} WHERE id = 1",
                values,
            )
            conn.commit()

    def _customer_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            phone_numbers = json.loads(row["phone_numbers"])
            if not isinstance(phone_numbers, list):
                phone_numbers = []
        except (json.JSONDecodeError, TypeError):
            # A corrupted phone_numbers column shouldn't take down every
            # caller that reads this row -- surface it as "no numbers"
            # instead, so the row can still be loaded, inspected, and
            # skipped/flagged by higher layers (e.g. QueueEngine).
            log.warning(
                "Corrupted phone_numbers for customer id=%s loan_number=%s",
                row["id"],
                row["loan_number"],
            )
            phone_numbers = []

        row_keys = row.keys()
        return {
            "id": row["id"],
            "loan_number": row["loan_number"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "phone_numbers": phone_numbers,
            "primary_phone": phone_numbers[0] if phone_numbers else "",
            "balance": row["balance"] or "",
            "days_overdue": row["days_overdue"] or "",
            "monthly_payment": (row["monthly_payment"] or "") if "monthly_payment" in row_keys else "",
            "current_overdue_amount": (
                (row["current_overdue_amount"] or "") if "current_overdue_amount" in row_keys else ""
            ),
            "original_loan_amount": (
                (row["original_loan_amount"] or "") if "original_loan_amount" in row_keys else ""
            ),
            "status": row["status"],
            "import_timestamp": row["import_timestamp"],
            "status_timestamp": row["status_timestamp"],
            "last_edited_timestamp": row["last_edited_timestamp"] if "last_edited_timestamp" in row_keys else None,
            "warning_note": row["warning_note"] if "warning_note" in row_keys else None,
            "is_blacklisted": bool(row["is_blacklisted"]) if "is_blacklisted" in row_keys else False,
            "attempt_count": int(row["attempt_count"]) if "attempt_count" in row_keys and row["attempt_count"] is not None else 0,
        }

    # -----------------------------------------------------------------------
    # Async wrappers — call these from async handlers so blocking SQLite I/O
    # runs in a thread pool instead of stalling the event loop.
    # The synchronous originals are preserved for test code.
    # -----------------------------------------------------------------------

    async def async_insert_customers(self, customers, status="waiting"):
        return await asyncio.to_thread(self.insert_customers, customers, status)

    async def async_delete_customer(self, customer_id):
        await asyncio.to_thread(self.delete_customer, customer_id)

    async def async_count_customers(self):
        return await asyncio.to_thread(self.count_customers)

    async def async_clear_customers(self):
        await asyncio.to_thread(self.clear_customers)

    async def async_reset_queue(self):
        await asyncio.to_thread(self.reset_queue)

    async def async_get_customers_by_loan_numbers(self, loan_numbers):
        return await asyncio.to_thread(self.get_customers_by_loan_numbers, loan_numbers)

    async def async_get_all_customers(self):
        return await asyncio.to_thread(self.get_all_customers)

    async def async_reassign_status(self, from_status, to_status):
        return await asyncio.to_thread(self.reassign_status, from_status, to_status)

    async def async_get_customer(self, customer_id):
        return await asyncio.to_thread(self.get_customer, customer_id)

    async def async_get_next_waiting_customer(self):
        return await asyncio.to_thread(self.get_next_waiting_customer)

    async def async_get_next_actionable_customer(self):
        return await asyncio.to_thread(self.get_next_actionable_customer)

    async def async_update_customer_status(self, customer_id, status):
        await asyncio.to_thread(self.update_customer_status, customer_id, status)

    async def async_count_by_status(self, status):
        return await asyncio.to_thread(self.count_by_status, status)

    async def async_status_counts(self):
        return await asyncio.to_thread(self.status_counts)

    async def async_customers_by_status(self, status):
        return await asyncio.to_thread(self.customers_by_status, status)

    async def async_get_queue_session(self):
        return await asyncio.to_thread(self.get_queue_session)

    async def async_search_customers(self, query, limit=20):
        return await asyncio.to_thread(self.search_customers, query, limit)

    async def async_get_customer_events(self, customer_id, limit=50):
        return await asyncio.to_thread(self.get_customer_events, customer_id, limit)

    async def async_get_customer_record(self, customer_id):
        return await asyncio.to_thread(self.get_customer_record, customer_id)

    async def async_update_customer_fields(self, customer_id, **fields):
        await asyncio.to_thread(self.update_customer_fields, customer_id, **fields)

    async def async_set_customer_blacklisted(self, customer_id, blacklisted):
        await asyncio.to_thread(self.set_customer_blacklisted, customer_id, blacklisted)

    async def async_is_phone_blacklisted(self, phone):
        return await asyncio.to_thread(self.is_phone_blacklisted, phone)

    async def async_blacklist_phone(self, phone, reason=None, telegram_user_id=None):
        await asyncio.to_thread(self.blacklist_phone, phone, reason, telegram_user_id)

    async def async_unblacklist_phone(self, phone):
        await asyncio.to_thread(self.unblacklist_phone, phone)
