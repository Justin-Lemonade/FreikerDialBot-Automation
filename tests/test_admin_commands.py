"""Automated tests for the Administrative Commands module.

Covers: reset queue, clear queue, summary generation, CSV export,
JSON export, authorization, database persistence, restart
compatibility, and export file generation.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import admin_commands
from config import Settings
from database import Database
from export_engine import ExportError, export_customers
from session_manager import SessionManager
from statistics_engine import StatisticsEngine


SAMPLE_CUSTOMERS = [
    {
        "loan_number": "L001",
        "first_name": "Ann",
        "last_name": "Owens",
        "phone_numbers": ["+15550001111"],
        "balance": "500",
        "days_overdue": "10",
    },
    {
        "loan_number": "L002",
        "first_name": "Bo",
        "last_name": "Kim",
        "phone_numbers": ["+15550002222"],
        "balance": "750",
        "days_overdue": "20",
    },
    {
        "loan_number": "L003",
        "first_name": "Cy",
        "last_name": "Diaz",
        "phone_numbers": ["+15550003333"],
        "balance": "125",
        "days_overdue": "5",
    },
]


@pytest.fixture
def database(tmp_path: Path) -> Database:
    return Database(path=tmp_path / "session.db")


@pytest.fixture
def statistics(database: Database) -> StatisticsEngine:
    return StatisticsEngine(database)


@pytest.fixture
def session_manager(database: Database, statistics: StatisticsEngine) -> SessionManager:
    return SessionManager(database, statistics)


def _fake_update(user_id: int | None):
    message = SimpleNamespace(
        reply_text=AsyncMock(),
        reply_document=AsyncMock(),
    )
    user = SimpleNamespace(id=user_id) if user_id is not None else None
    return SimpleNamespace(effective_user=user, effective_message=message)


def _fake_context(database: Database, session_manager: SessionManager, settings: Settings, args=None):
    application = SimpleNamespace(
        bot_data={
            "database": database,
            "session_manager": session_manager,
            # Real bot_data always includes this (see bot.py); pull it off
            # session_manager so it's guaranteed to be the same
            # StatisticsEngine instance session_manager itself records to.
            "statistics_engine": session_manager.statistics,
            "settings": settings,
        }
    )
    return SimpleNamespace(application=application, args=args or [])


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

def test_authorization_denies_when_no_admins_configured():
    settings = Settings(telegram_bot_token="x", openai_api_key=None)
    update = _fake_update(user_id=123)
    assert admin_commands.is_authorized(update, settings) is False


def test_authorization_denies_unlisted_user():
    settings = Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=frozenset({111}))
    update = _fake_update(user_id=999)
    assert admin_commands.is_authorized(update, settings) is False


def test_authorization_allows_listed_user():
    settings = Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=frozenset({111}))
    update = _fake_update(user_id=111)
    assert admin_commands.is_authorized(update, settings) is True


@pytest.mark.asyncio
async def test_reset_command_denied_for_unauthorized_user(database):
    settings = Settings(telegram_bot_token="x", openai_api_key=None)
    update = _fake_update(user_id=1)
    context = _fake_context(database, SessionManager(database, StatisticsEngine(database)), settings)

    await admin_commands.reset(update, context)

    update.effective_message.reply_text.assert_awaited_once_with("Permission denied.")


# ---------------------------------------------------------------------------
# /reset - Reset queue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_queue_restores_waiting_status_and_preserves_customers(
    database, session_manager
):
    database.insert_customers(SAMPLE_CUSTOMERS)
    session_manager.create_session(len(SAMPLE_CUSTOMERS))

    first = database.get_next_waiting_customer()
    database.update_customer_status(first["id"], "warned")
    second = database.get_next_waiting_customer()
    database.update_customer_status(second["id"], "call_later")
    database.update_queue_session(current_position=2, current_customer_id=second["id"])

    assert database.status_counts()["waiting"] == 1

    settings = Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=frozenset({7}))
    update = _fake_update(user_id=7)
    context = _fake_context(database, session_manager, settings)

    await admin_commands.reset(update, context)

    counts = database.status_counts()
    assert counts["waiting"] == 3
    assert database.count_customers() == 3  # customer records preserved

    queue_session = database.get_queue_session()
    assert queue_session["current_customer_id"] is None
    assert queue_session["current_position"] == 0
    assert queue_session["is_paused"] == 0

    update.effective_message.reply_text.assert_awaited_once_with("Queue Reset Complete")


@pytest.mark.asyncio
async def test_reset_with_no_customers_reports_no_customers(database, session_manager):
    settings = Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=frozenset({7}))
    update = _fake_update(user_id=7)
    context = _fake_context(database, session_manager, settings)

    await admin_commands.reset(update, context)

    update.effective_message.reply_text.assert_awaited_once_with("No customers loaded.")


def test_reset_queue_preserves_history_and_statistics(database, session_manager, statistics):
    database.insert_customers(SAMPLE_CUSTOMERS)
    session_id = session_manager.create_session(len(SAMPLE_CUSTOMERS))
    customer = database.get_next_waiting_customer()
    database.update_customer_status(customer["id"], "warned")
    statistics.record_event("customer_warned", session_id=session_id, customer=customer)

    with database.connect() as conn:
        events_before = conn.execute("SELECT COUNT(*) FROM customer_events").fetchone()[0]
        sessions_before = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

    database.reset_queue()

    with database.connect() as conn:
        events_after = conn.execute("SELECT COUNT(*) FROM customer_events").fetchone()[0]
        sessions_after = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

    assert events_after == events_before
    assert sessions_after == sessions_before


# ---------------------------------------------------------------------------
# /clear - Clear queue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clear_command_removes_customers_but_keeps_history(database, session_manager):
    database.insert_customers(SAMPLE_CUSTOMERS)
    # create_session() already records its own "session_created" event.
    session_manager.create_session(len(SAMPLE_CUSTOMERS))

    with database.connect() as conn:
        events_before = conn.execute("SELECT COUNT(*) FROM customer_events").fetchone()[0]

    settings = Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=frozenset({7}))
    update = _fake_update(user_id=7)
    context = _fake_context(database, session_manager, settings)

    await admin_commands.clear(update, context)

    assert database.count_customers() == 0
    with database.connect() as conn:
        sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        events_after = conn.execute("SELECT COUNT(*) FROM customer_events").fetchone()[0]
        latest_event = conn.execute(
            "SELECT event_type, telegram_user_id, notes FROM customer_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert sessions == 1
    # clear_customers() itself still leaves customer_events untouched, as
    # documented -- but admin_commands.clear() now also writes one
    # admin_action audit event on top of that, which is the +1 here.
    assert events_after == events_before + 1
    assert latest_event["event_type"] == "admin_action"
    assert latest_event["telegram_user_id"] == 7
    assert latest_event["notes"] == "clear"

    text = update.effective_message.reply_text.await_args.args[0]
    assert "Current Queue Cleared" in text
    assert "No customer list loaded" in text
    _, kwargs = update.effective_message.reply_text.await_args
    assert kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_clear_denied_for_unauthorized_user(database, session_manager):
    settings = Settings(telegram_bot_token="x", openai_api_key=None)
    update = _fake_update(user_id=999)
    context = _fake_context(database, session_manager, settings)

    await admin_commands.clear(update, context)

    update.effective_message.reply_text.assert_awaited_once_with("Permission denied.")


# ---------------------------------------------------------------------------
# Denied admin attempts are audited too, not just successful ones
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command_name, expected_action",
    [
        ("reset", "reset"),
        ("clear", "clear"),
        ("summary", "summary"),
        ("export", "export"),
    ],
)
async def test_denied_admin_attempt_is_audit_logged(database, session_manager, command_name, expected_action):
    """Every admin command's denial path must write an
    admin_action_denied event -- previously only successful admin
    actions were logged at all, so repeated unauthorized attempts left
    no trace."""
    settings = Settings(telegram_bot_token="x", openai_api_key=None)  # no admins configured -> always denied
    update = _fake_update(user_id=42)
    context = _fake_context(database, session_manager, settings)

    command = getattr(admin_commands, command_name)
    await command(update, context)

    with database.connect() as conn:
        latest_event = conn.execute(
            "SELECT event_type, telegram_user_id, notes FROM customer_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert latest_event["event_type"] == "admin_action_denied"
    assert latest_event["telegram_user_id"] == 42
    assert latest_event["notes"] == expected_action
    update.effective_message.reply_text.assert_awaited_once_with("Permission denied.")


@pytest.mark.asyncio
async def test_denied_admin_attempt_does_not_log_as_a_successful_admin_action(database, session_manager):
    """A denied attempt must never be mistakable for a successful one
    in the audit trail -- distinct event_type, not just distinct notes."""
    settings = Settings(telegram_bot_token="x", openai_api_key=None)
    update = _fake_update(user_id=42)
    context = _fake_context(database, session_manager, settings)

    await admin_commands.reset(update, context)

    with database.connect() as conn:
        admin_action_count = conn.execute(
            "SELECT COUNT(*) FROM customer_events WHERE event_type = 'admin_action'"
        ).fetchone()[0]
    assert admin_action_count == 0


# ---------------------------------------------------------------------------
# /summary - Summary generation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summary_reports_no_active_session(database, session_manager):
    settings = Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=frozenset({7}))
    update = _fake_update(user_id=7)
    context = _fake_context(database, session_manager, settings)

    await admin_commands.summary(update, context)

    update.effective_message.reply_text.assert_awaited_once_with("No active session.")


@pytest.mark.asyncio
async def test_summary_includes_expected_fields(database, session_manager):
    database.insert_customers(SAMPLE_CUSTOMERS)
    session_manager.create_session(len(SAMPLE_CUSTOMERS))
    session_manager.start_current_session()
    customer = database.get_next_waiting_customer()
    database.update_customer_status(customer["id"], "warned")

    settings = Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=frozenset({7}))
    update = _fake_update(user_id=7)
    context = _fake_context(database, session_manager, settings)

    await admin_commands.summary(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    for field in (
        "Session Name",
        "Started",
        "Elapsed Time",
        "Imported",
        "Remaining",
        "Contacted",
        "Didn't Answer",
        "Completion %",
    ):
        assert field in text


@pytest.mark.asyncio
async def test_summary_shows_completion_details_when_session_completed(
    database, session_manager
):
    database.insert_customers(SAMPLE_CUSTOMERS)
    session_manager.create_session(len(SAMPLE_CUSTOMERS))
    session_manager.start_current_session()
    for _ in SAMPLE_CUSTOMERS:
        customer = database.get_next_waiting_customer()
        database.update_customer_status(customer["id"], "warned")
    session_manager.complete_current_session()

    settings = Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=frozenset({7}))
    update = _fake_update(user_id=7)
    context = _fake_context(database, session_manager, settings)

    await admin_commands.summary(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "Completed" in text
    assert "Completion Time" in text
    assert "Duration" in text


# ---------------------------------------------------------------------------
# /export - CSV and JSON export, file generation
# ---------------------------------------------------------------------------

def test_export_customers_csv_contains_expected_fields(tmp_path, monkeypatch):
    monkeypatch.setattr("export_engine.EXPORTS_DIR", tmp_path)
    customers = [
        {
            "loan_number": "L001",
            "first_name": "Ann",
            "last_name": "Owens",
            "phone_numbers": ["+15550001111"],
            "balance": "500",
            "days_overdue": "10",
            "status": "warned",
            "status_timestamp": "2026-01-01T00:00:00+00:00",
        }
    ]

    path = export_customers(customers, session_id=1, export_format="csv")

    assert path.exists()
    assert path.suffix == ".csv"
    content = path.read_text(encoding="utf-8")
    assert "Loan Number" in content
    assert "L001" in content
    assert "warned" in content
    assert "1" in content  # Session ID


def test_export_customers_json_contains_expected_fields(tmp_path, monkeypatch):
    monkeypatch.setattr("export_engine.EXPORTS_DIR", tmp_path)
    customers = [
        {
            "loan_number": "L002",
            "first_name": "Bo",
            "last_name": "Kim",
            "phone_numbers": ["+15550002222"],
            "balance": "750",
            "days_overdue": "20",
            "status": "call_later",
            "status_timestamp": None,
        }
    ]

    path = export_customers(customers, session_id=2, export_format="json")

    assert path.exists()
    assert path.suffix == ".json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0]["Loan Number"] == "L002"
    assert data[0]["Final Status"] == "call_later"
    assert data[0]["Session ID"] == "2"


def test_export_rejects_unsupported_format(tmp_path, monkeypatch):
    monkeypatch.setattr("export_engine.EXPORTS_DIR", tmp_path)
    with pytest.raises(ExportError):
        export_customers([{"loan_number": "L1", "first_name": "A", "last_name": "B",
                            "phone_numbers": [], "balance": "", "days_overdue": "",
                            "status": "waiting", "status_timestamp": None}],
                          session_id=1, export_format="pdf")


def test_export_rejects_empty_customer_list(tmp_path, monkeypatch):
    monkeypatch.setattr("export_engine.EXPORTS_DIR", tmp_path)
    with pytest.raises(ExportError):
        export_customers([], session_id=1, export_format="csv")


@pytest.mark.asyncio
async def test_export_command_no_customers(database, session_manager):
    settings = Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=frozenset({7}))
    update = _fake_update(user_id=7)
    context = _fake_context(database, session_manager, settings, args=["csv"])

    await admin_commands.export(update, context)

    update.effective_message.reply_text.assert_awaited_once_with("No customers loaded.")


@pytest.mark.asyncio
async def test_export_command_sends_document(database, session_manager, tmp_path, monkeypatch):
    monkeypatch.setattr("export_engine.EXPORTS_DIR", tmp_path)

    database.insert_customers(SAMPLE_CUSTOMERS)
    session_manager.create_session(len(SAMPLE_CUSTOMERS))

    settings = Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=frozenset({7}))
    update = _fake_update(user_id=7)
    context = _fake_context(database, session_manager, settings, args=["csv"])

    await admin_commands.export(update, context)

    update.effective_message.reply_document.assert_awaited_once()
    update.effective_message.reply_text.assert_any_call("Export Ready")


@pytest.mark.asyncio
async def test_export_command_rejects_unsupported_format(database, session_manager):
    database.insert_customers(SAMPLE_CUSTOMERS)
    settings = Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=frozenset({7}))
    update = _fake_update(user_id=7)
    context = _fake_context(database, session_manager, settings, args=["pdf"])

    await admin_commands.export(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "Unsupported format" in text


# ---------------------------------------------------------------------------
# Database persistence / restart compatibility
# ---------------------------------------------------------------------------

def test_database_persists_across_reconnects(tmp_path):
    db_path = tmp_path / "session.db"
    database = Database(path=db_path)
    database.insert_customers(SAMPLE_CUSTOMERS)

    # Simulate a restart: build a brand new Database instance from the
    # same file path, as bot.py would do on the next run.
    reopened = Database(path=db_path)
    assert reopened.count_customers() == 3
    assert reopened.status_counts()["waiting"] == 3


def test_reset_queue_is_restart_compatible(tmp_path):
    db_path = tmp_path / "session.db"
    database = Database(path=db_path)
    database.insert_customers(SAMPLE_CUSTOMERS)
    customer = database.get_next_waiting_customer()
    database.update_customer_status(customer["id"], "warned")
    database.reset_queue()

    reopened = Database(path=db_path)
    assert reopened.status_counts()["waiting"] == 3
    session_state = reopened.get_queue_session()
    assert session_state["current_customer_id"] is None
    assert session_state["current_position"] == 0


# ---------------------------------------------------------------------------
# Call Back (restart_call_later) and average-time statistics
# ---------------------------------------------------------------------------

def test_reassign_status_moves_matching_rows_only(database):
    database.insert_customers(SAMPLE_CUSTOMERS)
    first = database.get_next_waiting_customer()
    database.update_customer_status(first["id"], "call_later")
    second = database.get_next_waiting_customer()
    database.update_customer_status(second["id"], "warned")

    moved = database.reassign_status("call_later", "waiting")

    assert moved == 1
    counts = database.status_counts()
    assert counts["waiting"] == 2  # the untouched third customer + the requeued one
    assert counts["warned"] == 1
    assert counts["call_later"] == 0


def test_restart_call_later_requeues_only_call_later_customers(database, session_manager):
    from queue_engine import QueueEngine

    database.insert_customers(SAMPLE_CUSTOMERS)
    session_manager.create_session(len(SAMPLE_CUSTOMERS))
    statistics = StatisticsEngine(database)
    queue = QueueEngine(database, statistics=statistics, session_manager=session_manager)

    # Mark one warned, one call_later, leave the third waiting.
    a = database.get_next_waiting_customer()
    database.update_customer_status(a["id"], "warned")
    b = database.get_next_waiting_customer()
    database.update_customer_status(b["id"], "call_later")

    selection = queue.restart_call_later()

    counts = database.status_counts()
    assert counts["call_later"] == 0
    assert counts["warned"] == 1  # untouched
    # The requeued customer and the original third customer are both waiting
    # again; next_customer() picks one of them up as "current".
    assert selection.customer is not None or selection.complete is False


def test_restart_call_later_with_nothing_to_requeue_is_safe(database, session_manager):
    from queue_engine import QueueEngine

    statistics = StatisticsEngine(database)
    queue = QueueEngine(database, statistics=statistics, session_manager=session_manager)

    # No customers loaded at all -- should not raise.
    selection = queue.restart_call_later()
    assert selection.complete is True


def test_session_summary_includes_average_seconds_per_customer(database, session_manager):
    database.insert_customers(SAMPLE_CUSTOMERS)
    session_id = session_manager.create_session(len(SAMPLE_CUSTOMERS))
    for _ in SAMPLE_CUSTOMERS:
        customer = database.get_next_waiting_customer()
        database.update_customer_status(customer["id"], "warned")

    summary = session_manager.summary_for_session(session_id)
    assert hasattr(summary, "average_seconds_per_customer")
    assert summary.average_seconds_per_customer >= 0


def test_render_completion_summary_includes_average_time_line(database, session_manager):
    database.insert_customers(SAMPLE_CUSTOMERS)
    session_id = session_manager.create_session(len(SAMPLE_CUSTOMERS))
    for _ in SAMPLE_CUSTOMERS:
        customer = database.get_next_waiting_customer()
        database.update_customer_status(customer["id"], "warned")
    summary = session_manager.summary_for_session(session_id)

    text = session_manager.render_completion_summary(summary)
    assert "Average Time Per Customer" in text


def test_lifetime_average_seconds_per_customer_uses_completed_sessions_only(
    database, session_manager, statistics
):
    database.insert_customers(SAMPLE_CUSTOMERS)
    session_id = session_manager.create_session(len(SAMPLE_CUSTOMERS))
    session_manager.start_current_session()
    for _ in SAMPLE_CUSTOMERS:
        customer = database.get_next_waiting_customer()
        database.update_customer_status(customer["id"], "warned")
        statistics.record_event("customer_warned", session_id=session_id, customer=customer)
    session_manager.complete_current_session()

    snapshot = statistics.snapshot()
    assert snapshot.average_seconds_per_customer >= 0
    assert hasattr(snapshot, "average_seconds_per_customer")


@pytest.mark.asyncio
async def test_summary_includes_average_time_per_customer(database, session_manager):
    database.insert_customers(SAMPLE_CUSTOMERS)
    session_manager.create_session(len(SAMPLE_CUSTOMERS))
    session_manager.start_current_session()
    customer = database.get_next_waiting_customer()
    database.update_customer_status(customer["id"], "warned")

    settings = Settings(telegram_bot_token="x", openai_api_key=None, admin_user_ids=frozenset({7}))
    update = _fake_update(user_id=7)
    context = _fake_context(database, session_manager, settings)

    await admin_commands.summary(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "Average Time Per Customer" in text


# ---------------------------------------------------------------------------
# Session naming: fun label generator + rename
# ---------------------------------------------------------------------------

def test_generate_session_name_has_label_and_timestamp_notation():
    from session_manager import generate_session_name

    name = generate_session_name()
    assert " - " in name
    label, _, notation = name.partition(" - ")
    assert len(label.split()) == 2  # "Adjective Noun"
    assert notation  # non-empty timestamp notation


def test_create_session_uses_fun_name_by_default(database, session_manager):
    session_id = session_manager.create_session(3)
    session = session_manager.get_session(session_id)
    assert " - " in session["session_name"]
    assert "Import Session" not in session["session_name"]


def test_rename_session_keeps_timestamp_notation(database, session_manager):
    session_id = session_manager.create_session(3)
    original_name = session_manager.get_session(session_id)["session_name"]
    _, _, original_notation = original_name.partition(" - ")

    renamed = session_manager.rename_session("Morning Batch")
    assert renamed is True

    new_name = session_manager.get_session(session_id)["session_name"]
    assert new_name.startswith("Morning Batch - ")
    assert new_name.endswith(original_notation)


def test_rename_session_returns_false_with_no_session(database, session_manager):
    assert session_manager.rename_session("Anything") is False


@pytest.mark.asyncio
async def test_rename_command_updates_session_name(database, session_manager):
    import telegram_ui

    session_manager.create_session(3)
    update = _fake_update(user_id=1)
    application = SimpleNamespace(bot_data={"session_manager": session_manager})
    context = SimpleNamespace(application=application, args=["Evening", "Batch"])

    await telegram_ui.rename(update, context)

    session = session_manager.current_session()
    assert session["session_name"].startswith("Evening Batch - ")
    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_rename_command_without_args_shows_usage(database, session_manager):
    import telegram_ui

    update = _fake_update(user_id=1)
    application = SimpleNamespace(bot_data={"session_manager": session_manager})
    context = SimpleNamespace(application=application, args=[])

    await telegram_ui.rename(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "Usage" in text


# ---------------------------------------------------------------------------
# Import redundancy: round-trip verification + split-paste merge
# ---------------------------------------------------------------------------

def test_looks_like_incomplete_json_detects_split_fragments():
    from telegram_ui import _looks_like_incomplete_json

    fragment = '[{"loan_number":"L1","first_name":"Ann","last_name":"Owens","phone_numbers":["555'
    assert _looks_like_incomplete_json(fragment) is True
    assert _looks_like_incomplete_json('[{"a": 1}]') is False
    assert _looks_like_incomplete_json("just plain text") is False


@pytest.mark.asyncio
async def test_handle_text_merges_split_json_fragments(database, session_manager, monkeypatch):
    import telegram_ui

    class FakeParser:
        pass

    from importer import Importer

    importer = Importer(FakeParser(), database, session_manager=session_manager)

    fragment_1 = '[{"loan_number":"L1","first_name":"Ann","last_name":"Owens","phone_numbers":["5551234567"],"balance":"500","days_overdue":"10"'
    fragment_2 = '}]'

    application = SimpleNamespace(
        bot_data={"importer": importer, "database": database, "session_manager": session_manager}
    )

    message_1 = SimpleNamespace(text=fragment_1, reply_text=AsyncMock())
    update_1 = SimpleNamespace(effective_message=message_1)
    context = SimpleNamespace(application=application, chat_data={})

    await telegram_ui.handle_text(update_1, context)
    # First fragment alone isn't valid JSON -- should be held, not imported.
    assert database.count_customers() == 0
    assert "pending_text_fragment" in context.chat_data

    progress_message = SimpleNamespace(
        edit_text=AsyncMock(), reply_text=AsyncMock()
    )
    message_2 = SimpleNamespace(
        text=fragment_2, reply_text=AsyncMock(return_value=progress_message)
    )
    update_2 = SimpleNamespace(effective_message=message_2)

    await telegram_ui.handle_text(update_2, context)

    # Combined, the two fragments form valid JSON and should have imported.
    assert database.count_customers() == 1
    assert "pending_text_fragment" not in context.chat_data


@pytest.mark.asyncio
async def test_handle_json_file_imports_from_uploaded_file(database, session_manager):
    import telegram_ui

    class FakeParser:
        pass

    from importer import Importer

    importer = Importer(FakeParser(), database, session_manager=session_manager)

    file_content = (
        '[{"loan_number":"L200","first_name":"Cy","last_name":"Diaz",'
        '"phone_numbers":["5559998888"],"balance":"200","days_overdue":"3"}]'
    ).encode("utf-8")

    telegram_file = SimpleNamespace(
        download_as_bytearray=AsyncMock(return_value=bytearray(file_content))
    )
    document = SimpleNamespace(get_file=AsyncMock(return_value=telegram_file))

    progress_message = SimpleNamespace(edit_text=AsyncMock(), reply_text=AsyncMock())
    message = SimpleNamespace(
        document=document, reply_text=AsyncMock(return_value=progress_message)
    )
    update = SimpleNamespace(effective_message=message)
    application = SimpleNamespace(
        bot_data={"importer": importer, "database": database, "session_manager": session_manager}
    )
    context = SimpleNamespace(application=application)

    await telegram_ui.handle_json_file(update, context)

    assert database.count_customers() == 1
    # The final report now edits the existing progress message in place
    # instead of leaving "Selecting first customer..." as clutter and
    # sending a brand new message on top of it (message-cleanup pass).
    progress_message.edit_text.assert_awaited()
    final_text = progress_message.edit_text.await_args.args[0]
    assert "Import complete" in final_text


def test_round_trip_verification_flags_duplicate_import(database, session_manager):
    import asyncio

    class FakeParser:
        pass

    from importer import Importer

    importer = Importer(FakeParser(), database, session_manager=session_manager)
    good_json = (
        '[{"loan_number":"L300","first_name":"Dee","last_name":"Nguyen",'
        '"phone_numbers":["5551112222"],"balance":"300","days_overdue":"7"}]'
    )

    async def run():
        first = await importer.import_text(good_json)
        second = await importer.import_text(good_json)
        return first, second

    first_result, second_result = asyncio.run(run())
    assert first_result.verification_warnings == []
    assert any("already existed" in w for w in second_result.verification_warnings)


def test_queue_engine_skips_malformed_customer_row(database, session_manager):
    from queue_engine import QueueEngine

    database.insert_customers(SAMPLE_CUSTOMERS)
    session_manager.create_session(len(SAMPLE_CUSTOMERS))
    statistics = StatisticsEngine(database)
    queue = QueueEngine(database, statistics=statistics, session_manager=session_manager)

    # Corrupt one row directly at the DB layer, bypassing normal validation,
    # to simulate whatever produced the "internal issue" the user saw.
    with database.connect() as conn:
        conn.execute(
            "UPDATE customers SET phone_numbers = ? WHERE loan_number = 'L001'",
            ("not-a-json-array",),
        )
        conn.commit()

    # next_customer() should skip the corrupted row instead of crashing,
    # and mark it invalid_number rather than surfacing it to an operator.
    selections = []
    for _ in range(3):
        selection = queue.next_customer()
        selections.append(selection)
        if selection.customer:
            queue.apply_action(selection.customer["id"], "warned")

    counts = database.status_counts()
    assert counts["invalid_number"] == 1
    assert counts["warned"] == 2
