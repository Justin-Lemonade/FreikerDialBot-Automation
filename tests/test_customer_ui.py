from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import customer_ui
from database import Database
from queue_engine import QueueEngine
from session_manager import SessionManager
from statistics_engine import StatisticsEngine


CUSTOMERS = [
    {
        "loan_number": "C-1",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "phone_numbers": ["+15550001111"],
        "balance": "100",
        "days_overdue": "3",
    },
    {
        "loan_number": "C-2",
        "first_name": "Grace",
        "last_name": "Hopper",
        "phone_numbers": ["+15550002222"],
        "balance": "200",
        "days_overdue": "7",
    },
]


@pytest.fixture
def database(tmp_path) -> Database:
    db = Database(path=tmp_path / "session.db")
    db.insert_customers(CUSTOMERS)
    return db


@pytest.fixture
def queue_engine(database) -> QueueEngine:
    statistics = StatisticsEngine(database)
    session_manager = SessionManager(database, statistics)
    return QueueEngine(database, statistics=statistics, session_manager=session_manager)


def _fake_update(args, user_id=42):
    message = SimpleNamespace(reply_text=AsyncMock())
    user = SimpleNamespace(id=user_id) if user_id is not None else None
    return SimpleNamespace(effective_message=message, effective_user=user)


def _fake_context(database, queue_engine, args=None):
    application = SimpleNamespace(
        bot_data={"database": database, "queue_engine": queue_engine}
    )
    return SimpleNamespace(application=application, args=args or [])


class FakeCallbackQuery:
    def __init__(self, data):
        self.data = data
        self.message = SimpleNamespace(reply_text=AsyncMock(), edit_text=AsyncMock())

    async def answer(self):
        return None


def _fake_callback_update(data, user_id=42):
    user = SimpleNamespace(id=user_id) if user_id is not None else None
    return SimpleNamespace(callback_query=FakeCallbackQuery(data), effective_user=user)


# ---------------------------------------------------------------------------
# /customer (search + view)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_customer_command_without_args_shows_usage(database, queue_engine):
    update = _fake_update([])
    context = _fake_context(database, queue_engine)

    await customer_ui.customer_command(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "Usage" in text


@pytest.mark.asyncio
async def test_customer_command_no_match(database, queue_engine):
    update = _fake_update(["nonexistent"])
    context = _fake_context(database, queue_engine, args=["nonexistent"])

    await customer_ui.customer_command(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "No customers found" in text


@pytest.mark.asyncio
async def test_customer_command_single_match_shows_full_record(database, queue_engine):
    update = _fake_update(["Ada"])
    context = _fake_context(database, queue_engine, args=["Ada"])

    await customer_ui.customer_command(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "Ada Lovelace" in text
    assert "C-1" in text


@pytest.mark.asyncio
async def test_customer_command_multiple_matches_shows_keyboard(database, queue_engine):
    update = _fake_update(["+1555"])
    context = _fake_context(database, queue_engine, args=["+1555"])

    await customer_ui.customer_command(update, context)

    _, kwargs = update.effective_message.reply_text.await_args
    keyboard = kwargs["reply_markup"].inline_keyboard
    assert len(keyboard) == 2
    assert all(row[0].callback_data.startswith("customer_view:") for row in keyboard)


@pytest.mark.asyncio
async def test_more_info_callback_shows_record(database, queue_engine):
    customer = database.get_customer(1)
    update = _fake_callback_update(f"customer_view:{customer['id']}")
    context = _fake_context(database, queue_engine)

    await customer_ui.handle_customer_callback(update, context)

    text = update.callback_query.message.reply_text.await_args.args[0]
    assert "Ada Lovelace" in text


@pytest.mark.asyncio
async def test_more_info_callback_missing_customer(database, queue_engine):
    update = _fake_callback_update("customer_view:99999")
    context = _fake_context(database, queue_engine)

    await customer_ui.handle_customer_callback(update, context)

    text = update.callback_query.message.reply_text.await_args.args[0]
    assert "not found" in text.lower()


@pytest.mark.asyncio
async def test_customer_record_shows_notes_and_history(database, queue_engine):
    customer = database.get_customer(1)
    queue_engine.edit_customer(customer["id"], telegram_user_id=1, balance="500")
    database.set_customer_blacklisted(customer["id"], True)

    update = _fake_update(["C-1"])
    context = _fake_context(database, queue_engine, args=["C-1"])
    await customer_ui.customer_command(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "BLACKLISTED" in text
    assert "customer_edited" in text or "History" in text


# ---------------------------------------------------------------------------
# /edit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_edit_command_without_enough_args_shows_usage(database, queue_engine):
    update = _fake_update(["C-1"])
    context = _fake_context(database, queue_engine, args=["C-1"])

    await customer_ui.edit_command(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "Usage" in text


@pytest.mark.asyncio
async def test_edit_command_unknown_customer(database, queue_engine):
    update = _fake_update(["NOPE", "balance=1"])
    context = _fake_context(database, queue_engine, args=["NOPE", "balance=1"])

    await customer_ui.edit_command(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "No customer found" in text


@pytest.mark.asyncio
async def test_edit_command_updates_field(database, queue_engine):
    args = ["C-1", "balance=999"]
    update = _fake_update(args)
    context = _fake_context(database, queue_engine, args=args)

    await customer_ui.edit_command(update, context)

    assert database.get_customer(1)["balance"] == "999"
    text = update.effective_message.reply_text.await_args.args[0]
    assert "Updated" in text


@pytest.mark.asyncio
async def test_edit_command_normalizes_phone_numbers(database, queue_engine):
    args = ["C-1", "phone_numbers=(555) 111-2222,555.333.4444"]
    update = _fake_update(args)
    context = _fake_context(database, queue_engine, args=args)

    await customer_ui.edit_command(update, context)

    assert database.get_customer(1)["phone_numbers"] == ["5551112222", "5553334444"]


@pytest.mark.asyncio
async def test_edit_command_flags_unknown_field(database, queue_engine):
    args = ["C-1", "loan_number=HACK"]
    update = _fake_update(args)
    context = _fake_context(database, queue_engine, args=args)

    await customer_ui.edit_command(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "Unknown field" in text
    assert database.get_customer(1)["loan_number"] == "C-1"


@pytest.mark.asyncio
async def test_edit_command_by_numeric_id_also_works(database, queue_engine):
    args = ["1", "balance=42"]
    update = _fake_update(args)
    context = _fake_context(database, queue_engine, args=args)

    await customer_ui.edit_command(update, context)

    assert database.get_customer(1)["balance"] == "42"


# ---------------------------------------------------------------------------
# Blacklist commands
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_blacklist_command_sets_flag(database, queue_engine):
    args = ["C-1"]
    update = _fake_update(args)
    context = _fake_context(database, queue_engine, args=args)

    await customer_ui.blacklist_command(update, context)

    assert database.get_customer(1)["is_blacklisted"] is True
    text = update.effective_message.reply_text.await_args.args[0]
    assert "Blacklisted" in text


@pytest.mark.asyncio
async def test_unblacklist_command_clears_flag(database, queue_engine):
    database.set_customer_blacklisted(1, True)
    args = ["C-1"]
    update = _fake_update(args)
    context = _fake_context(database, queue_engine, args=args)

    await customer_ui.unblacklist_command(update, context)

    assert database.get_customer(1)["is_blacklisted"] is False


@pytest.mark.asyncio
async def test_blacklist_command_unknown_customer(database, queue_engine):
    args = ["NOPE"]
    update = _fake_update(args)
    context = _fake_context(database, queue_engine, args=args)

    await customer_ui.blacklist_command(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "No customer found" in text


@pytest.mark.asyncio
async def test_blacklist_phone_command_with_reason(database, queue_engine):
    args = ["+15550009999", "reported", "spam"]
    update = _fake_update(args)
    context = _fake_context(database, queue_engine, args=args)

    await customer_ui.blacklist_phone_command(update, context)

    assert database.is_phone_blacklisted("+15550009999") is True
    text = update.effective_message.reply_text.await_args.args[0]
    assert "reported spam" in text


@pytest.mark.asyncio
async def test_unblacklist_phone_command(database, queue_engine):
    database.blacklist_phone("+15550009999")
    args = ["+15550009999"]
    update = _fake_update(args)
    context = _fake_context(database, queue_engine, args=args)

    await customer_ui.unblacklist_phone_command(update, context)

    assert database.is_phone_blacklisted("+15550009999") is False


@pytest.mark.asyncio
async def test_blacklist_phone_command_without_args_shows_usage(database, queue_engine):
    update = _fake_update([])
    context = _fake_context(database, queue_engine, args=[])

    await customer_ui.blacklist_phone_command(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "Usage" in text


# ---------------------------------------------------------------------------
# More Info action panel (Telegram UX pass)
# ---------------------------------------------------------------------------

def test_more_info_keyboard_shows_blacklist_when_not_blacklisted(database, queue_engine):
    record = database.get_customer_record(1)
    keyboard = customer_ui.more_info_keyboard(record).inline_keyboard
    labels = [b.text for row in keyboard for b in row]
    assert "🚫 Blacklist Customer" in labels
    assert "✅ Unblacklist Customer" not in labels


def test_more_info_keyboard_shows_unblacklist_when_blacklisted(database, queue_engine):
    database.set_customer_blacklisted(1, True)
    record = database.get_customer_record(1)
    keyboard = customer_ui.more_info_keyboard(record).inline_keyboard
    labels = [b.text for row in keyboard for b in row]
    assert "✅ Unblacklist Customer" in labels


def test_phone_menu_keyboard_lists_each_phone_with_actions(database, queue_engine):
    record = database.get_customer_record(1)
    keyboard = customer_ui.phone_menu_keyboard(record).inline_keyboard
    labels = [b.text for row in keyboard for b in row]
    assert any("Blacklist" in label and "+15550001111" in label for label in labels)
    assert any("Delete" in label and "+15550001111" in label for label in labels)


@pytest.mark.asyncio
async def test_action_callback_blacklists_customer(database, queue_engine):
    customer = database.get_customer(1)
    update = _fake_callback_update(f"cx:bl:{customer['id']}")
    context = _fake_context(database, queue_engine)

    await customer_ui.handle_customer_action_callback(update, context)

    assert database.get_customer(1)["is_blacklisted"] is True
    update.callback_query.message.edit_text.assert_awaited()


@pytest.mark.asyncio
async def test_action_callback_edit_gives_guided_command(database, queue_engine):
    customer = database.get_customer(1)
    update = _fake_callback_update(f"cx:edit:{customer['id']}")
    context = _fake_context(database, queue_engine)

    await customer_ui.handle_customer_action_callback(update, context)

    text = update.callback_query.message.reply_text.await_args.args[0]
    assert "/edit C-1" in text


@pytest.mark.asyncio
async def test_action_callback_delete_phone_removes_just_that_number(database, queue_engine):
    database.update_customer_fields(1, phone_numbers=["111", "222"])
    update = _fake_callback_update("cx:delphone:1:111")
    context = _fake_context(database, queue_engine)

    await customer_ui.handle_customer_action_callback(update, context)

    assert database.get_customer(1)["phone_numbers"] == ["222"]


@pytest.mark.asyncio
async def test_action_callback_blacklist_phone(database, queue_engine):
    update = _fake_callback_update("cx:blphone:1:+15550001111")
    context = _fake_context(database, queue_engine)

    await customer_ui.handle_customer_action_callback(update, context)

    assert database.is_phone_blacklisted("+15550001111") is True


@pytest.mark.asyncio
async def test_action_callback_queue_customer_shows_active_call_card(database, queue_engine):
    customer = database.get_customer(2)
    update = _fake_callback_update(f"cx:queue:{customer['id']}")
    context = _fake_context(database, queue_engine)

    await customer_ui.handle_customer_action_callback(update, context)

    text = update.callback_query.message.reply_text.await_args.args[0]
    assert "Grace Hopper" in text
    _, kwargs = update.callback_query.message.reply_text.await_args
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_action_callback_queue_refuses_blacklisted_customer(database, queue_engine):
    database.set_customer_blacklisted(1, True)
    update = _fake_callback_update("cx:queue:1")
    context = _fake_context(database, queue_engine)

    await customer_ui.handle_customer_action_callback(update, context)

    text = update.callback_query.message.reply_text.await_args.args[0]
    # Falls through to whoever IS eligible (customer 2), not customer 1.
    assert "Ada Lovelace" not in text


@pytest.mark.asyncio
async def test_action_callback_return_to_queue_with_no_active_customer(database, queue_engine):
    update = _fake_callback_update("cx:return:1")
    context = _fake_context(database, queue_engine)

    await customer_ui.handle_customer_action_callback(update, context)

    text = update.callback_query.message.reply_text.await_args.args[0]
    assert "No active customer" in text


@pytest.mark.asyncio
async def test_action_callback_full_history(database, queue_engine):
    queue_engine.edit_customer(1, telegram_user_id=1, balance="999")
    update = _fake_callback_update("cx:hist:1")
    context = _fake_context(database, queue_engine)

    await customer_ui.handle_customer_action_callback(update, context)

    text = update.callback_query.message.reply_text.await_args.args[0]
    assert "customer_edited" in text
