from __future__ import annotations

from database import Database
from queue_engine import QueueEngine
from session_manager import SessionManager
from statistics_engine import StatisticsEngine


CUSTOMERS = [
    {
        "loan_number": "S-1",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "phone_numbers": ["111"],
        "balance": "100",
        "days_overdue": "3",
    },
    {
        "loan_number": "S-2",
        "first_name": "Grace",
        "last_name": "Hopper",
        "phone_numbers": ["222"],
        "balance": "200",
        "days_overdue": "7",
    },
]


def build_stack(tmp_path):
    database = Database(tmp_path / "stats.db")
    statistics = StatisticsEngine(database)
    sessions = SessionManager(database, statistics)
    queue = QueueEngine(database, statistics=statistics, session_manager=sessions)
    return database, statistics, sessions, queue


def event_count(database: Database, event_type: str | None = None) -> int:
    with database.connect() as conn:
        if event_type:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM customer_events WHERE event_type = ?",
                    (event_type,),
                ).fetchone()[0]
            )
        return int(conn.execute("SELECT COUNT(*) FROM customer_events").fetchone()[0])


def table_exists(database: Database, table: str) -> bool:
    with database.connect() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None


def test_session_creation_updates_daily_loaded(tmp_path):
    database, statistics, sessions, _queue = build_stack(tmp_path)

    session_id = sessions.create_session(2, "Morning Calls")

    current = sessions.current_session()
    today = statistics.today_statistics()
    assert current["id"] == session_id
    assert current["status"] == "created"
    assert today["customers_loaded"] == 2
    assert event_count(database, "session_created") == 1


def test_event_recording_creates_immutable_history(tmp_path):
    database, _statistics, sessions, queue = build_stack(tmp_path)
    database.insert_customers(CUSTOMERS)
    sessions.create_session(2)

    selection = queue.resume(telegram_user_id=123)
    queue.apply_action(selection.customer["id"], "warned", telegram_user_id=123)

    assert event_count(database, "queue_started") == 1
    assert event_count(database, "queue_resumed") == 1
    assert event_count(database, "customer_loaded") >= 1
    assert event_count(database, "customer_warned") == 1


def test_session_completion_records_duration_and_daily_completed(tmp_path):
    database, statistics, sessions, queue = build_stack(tmp_path)
    database.insert_customers(CUSTOMERS)
    sessions.create_session(2)

    first = queue.resume()
    second = queue.apply_action(first.customer["id"], "warned")
    complete = queue.apply_action(second.customer["id"], "call_later")
    summary_text = queue.session_completion_summary()

    lifetime = statistics.lifetime_statistics()
    assert complete.complete
    assert "Session Complete" in summary_text
    assert "• <b>Imported:</b> 2" in summary_text
    assert lifetime["customers_contacted"] == 1
    assert lifetime["customers_not_answered"] == 1
    assert lifetime["sessions_completed"] == 1
    assert event_count(database, "queue_completed") == 1


def test_restart_persistence_for_session_and_statistics(tmp_path):
    database, _statistics, sessions, queue = build_stack(tmp_path)
    database.insert_customers(CUSTOMERS)
    session_id = sessions.create_session(2)
    first = queue.resume()
    queue.apply_action(first.customer["id"], "warned")

    restarted_database = Database(database.path)
    restarted_statistics = StatisticsEngine(restarted_database)
    restarted_sessions = SessionManager(restarted_database, restarted_statistics)

    assert restarted_sessions.current_session()["id"] == session_id
    assert restarted_statistics.lifetime_statistics()["customers_contacted"] == 1


def test_session_retrieval_and_rendering(tmp_path):
    database, _statistics, sessions, _queue = build_stack(tmp_path)
    database.insert_customers(CUSTOMERS)
    session_id = sessions.create_session(2, "Evening Calls")
    sessions.start_current_session()

    session = sessions.get_session(session_id)
    rendered = sessions.render_current_session()

    assert session["session_name"] == "Evening Calls"
    assert "Evening Calls" in rendered
    assert "• <b>Imported:</b> 2" in rendered
    assert "running" in rendered


def test_statistics_after_multiple_sessions(tmp_path):
    database, statistics, sessions, queue = build_stack(tmp_path)
    database.insert_customers(CUSTOMERS)
    sessions.create_session(2)
    first = queue.resume()
    second = queue.apply_action(first.customer["id"], "warned")
    queue.apply_action(second.customer["id"], "call_later")
    queue.session_completion_summary()

    database.clear_customers()
    database.insert_customers(
        [
            {
                "loan_number": "S-3",
                "first_name": "Katherine",
                "last_name": "Johnson",
                "phone_numbers": ["333"],
                "balance": "300",
                "days_overdue": "1",
            }
        ]
    )
    sessions.create_session(1)
    third = queue.resume()
    queue.apply_action(third.customer["id"], "warned")
    queue.session_completion_summary()

    lifetime = statistics.lifetime_statistics()
    snapshot = statistics.snapshot()
    assert lifetime["customers_loaded"] == 3
    assert lifetime["customers_contacted"] == 2
    assert lifetime["customers_not_answered"] == 1
    assert lifetime["sessions_completed"] == 2
    assert snapshot.average_contacts_per_session == 1


def test_database_migration_creates_history_tables(tmp_path):
    database = Database(tmp_path / "migration.db")

    assert table_exists(database, "sessions")
    assert table_exists(database, "customer_events")
    assert table_exists(database, "daily_statistics")


def test_clear_does_not_delete_history(tmp_path):
    database, statistics, sessions, _queue = build_stack(tmp_path)
    sessions.create_session(5)

    database.clear_customers()

    assert sessions.current_session()["total_customers"] == 5
    assert statistics.today_statistics()["customers_loaded"] == 5
    assert event_count(database) == 1


def test_statistics_plain_text_output(tmp_path):
    _database, statistics, sessions, _queue = build_stack(tmp_path)
    sessions.create_session(4)

    rendered = statistics.render_statistics()

    assert "Today's Statistics" in rendered
    assert "• <b>Imported:</b> 4" in rendered
    assert "<b>Lifetime</b>" in rendered
