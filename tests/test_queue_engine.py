from __future__ import annotations

import pytest

from database import Database
from queue_engine import QueueEngine
from queue_ui import handle_queue_callback, queue_keyboard, render_customer


CUSTOMERS = [
    {
        "loan_number": "Q-1",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "phone_numbers": ["111"],
        "balance": "100",
        "days_overdue": "3",
    },
    {
        "loan_number": "Q-2",
        "first_name": "Grace",
        "last_name": "Hopper",
        "phone_numbers": ["222"],
        "balance": "200",
        "days_overdue": "7",
    },
    {
        "loan_number": "Q-3",
        "first_name": "Katherine",
        "last_name": "Johnson",
        "phone_numbers": ["333"],
        "balance": "300",
        "days_overdue": "10",
    },
]


@pytest.fixture()
def database(tmp_path):
    db = Database(tmp_path / "queue.db")
    db.insert_customers(CUSTOMERS)
    return db


def test_next_customer_never_selects_a_blacklisted_customer(database):
    """The MUTATING advance path (next_customer, invoked by apply_action
    after every real Contacted/Didn't Answer/etc.) must skip blacklisted
    customers exactly like the read-only peek_next_customer() already
    did -- previously only the peek path filtered blacklisted customers,
    so one could still become 'current' via the real operator workflow.
    """
    engine = QueueEngine(database)
    first_id = database.get_customer(1)["id"]
    database.set_customer_blacklisted(first_id, True)

    selection = engine.next_customer()

    assert selection.customer is not None
    assert selection.customer["loan_number"] == "Q-2"
    assert selection.customer["id"] != first_id


def test_apply_action_never_advances_into_a_blacklisted_customer(database):
    """End-to-end through the actual code path an operator outcome
    triggers: apply_action() -> next_customer(). Q-2 gets blacklisted
    mid-queue; completing Q-1 must land on Q-3, never Q-2.
    """
    queue = QueueEngine(database)
    queue.resume()  # commits Q-1 as current

    second_id = database.get_customer(2)["id"]
    database.set_customer_blacklisted(second_id, True)

    selection = queue.apply_action(database.get_customer(1)["id"], "warned")

    assert selection.customer is not None
    assert selection.customer["loan_number"] == "Q-3"


def test_next_customer_selection_and_queue_order(database):
    queue = QueueEngine(database)

    first = queue.resume()
    assert first.customer["loan_number"] == "Q-1"

    second = queue.apply_action(first.customer["id"], "warned")
    assert second.customer["loan_number"] == "Q-2"

    third = queue.apply_action(second.customer["id"], "call_later")
    assert third.customer["loan_number"] == "Q-3"


def test_status_updates(database):
    queue = QueueEngine(database)
    first = queue.resume()

    queue.apply_action(first.customer["id"], "warned")
    customer = database.get_customer(first.customer["id"])

    assert customer["status"] == "warned"
    assert customer["status_timestamp"]


def test_resume_after_restart_uses_database_state(database):
    queue = QueueEngine(database)
    first = queue.resume()
    queue.apply_action(first.customer["id"], "warned")

    restarted_queue = QueueEngine(Database(database.path))
    selection = restarted_queue.resume()

    assert selection.customer["loan_number"] == "Q-2"
    assert selection.progress.current_position == 2


def test_progress_excludes_blacklisted_customers_from_remaining(database):
    """Confirmed live bug, now fixed: a blacklisted customer sitting in
    'waiting' status was counted in QueueProgress.remaining even though
    peek_next_customer()/next_customer() would never actually select
    them -- meaning a queue whose only leftover customer was blacklisted
    could never reach remaining=0 or 100%, and mini_app_api.py's session
    auto-completion (which checks progress.remaining == 0) would never
    fire. Handle the two real customers, blacklist the third, and
    confirm progress reflects a genuinely-complete queue.
    """
    queue = QueueEngine(database)
    first = queue.resume()
    second = queue.apply_action(first.customer["id"], "warned")
    third_selection = queue.apply_action(second.customer["id"], "call_later")

    # third_selection.customer is the last real customer -- blacklist
    # them mid-queue, the way an operator might via /blacklist.
    last_customer_id = third_selection.customer["id"]
    database.set_customer_blacklisted(last_customer_id, True)

    progress = queue.status()

    assert progress.remaining == 0
    assert progress.percent == 100


def test_queue_completion_and_summary(database):
    queue = QueueEngine(database)
    first = queue.resume()
    second = queue.apply_action(first.customer["id"], "warned")
    third = queue.apply_action(second.customer["id"], "call_later")
    complete = queue.apply_action(third.customer["id"], "warned")

    summary = queue.completion_summary()

    assert complete.complete
    assert "Session Complete" in summary
    assert "Number Contacted: 2" in summary
    assert "Number Didn't Answer: 1" in summary
    assert "Ada Lovelace" in summary
    assert "Grace Hopper" in summary


def test_expanded_information_contains_required_fields(database):
    queue = QueueEngine(database)
    selection = queue.resume()

    text = render_customer(selection.customer, selection.progress)

    assert "Loan #: Q-1" in text
    assert "Balance: 100" in text
    assert "Days Overdue: 3" in text
    assert 'Phone: <a href="tel:111">111</a>' in text


def test_progress_calculation(database):
    queue = QueueEngine(database)
    first = queue.resume()
    queue.apply_action(first.customer["id"], "warned")

    progress = queue.status()

    assert progress.remaining == 2
    assert progress.contacted == 1
    assert progress.did_not_answer == 0
    assert progress.percent == 33


def test_database_persistence(database):
    queue = QueueEngine(database)
    first = queue.resume()
    queue.pause()

    session = Database(database.path).get_queue_session()

    assert session["current_customer_id"] == first.customer["id"]
    assert session["is_paused"] == 1


def test_queue_keyboard_has_three_buttons():
    keyboard = queue_keyboard(10).inline_keyboard

    assert len(keyboard) == 3
    assert len(keyboard[0]) == 2
    assert len(keyboard[1]) == 2


def test_queue_keyboard_has_more_info_button():
    """More Info is what makes customer history (Phase 5's "More Info"
    screen) reachable from the active call card."""
    keyboard = queue_keyboard(10).inline_keyboard

    last_row = keyboard[-1]
    assert len(last_row) == 1
    assert last_row[0].text == "ℹ️ More Info"
    assert last_row[0].callback_data == "customer_view:10"


def test_queue_keyboard_has_no_phone_call_buttons():
    customer = {
        "id": 99,
        "loan_number": "Q-4",
        "first_name": "Test",
        "last_name": "User",
        "phone_numbers": ["936999900", "905777509"],
        "balance": "100",
        "days_overdue": "0",
    }

    keyboard = queue_keyboard(customer).inline_keyboard

    assert len(keyboard) == 3
    assert all(button.url is None for row in keyboard for button in row)


def test_send_text_with_retry_strips_tel_buttons_on_failure():
    import asyncio
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.error import TelegramError
    from queue_ui import _send_text_with_retry, _strip_tel_buttons

    class DummyMessage:
        def __init__(self):
            self.attempts = 0

        async def edit_text(self, text, **kwargs):
            self.attempts += 1
            if self.attempts == 1:
                raise TelegramError("telegram rejected tel: url")
            return "sent"

        async def reply_text(self, text, **kwargs):
            self.attempts += 1
            if self.attempts == 1:
                raise TelegramError("telegram rejected tel: url")
            return "sent"

    message = DummyMessage()
    reply_markup = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("📞 Call: 887415151", url="tel:887415151"),
            InlineKeyboardButton("✅ Contacted", callback_data="queue_warned:1"),
        ]]
    )

    send_fn = _send_text_with_retry(message, "text", reply_markup)

    result = asyncio.run(send_fn(message.edit_text))

    assert result == "sent"
    assert message.attempts == 2
    stripped_markup = _strip_tel_buttons(reply_markup)
    assert len(stripped_markup.inline_keyboard) == 1
    assert len(stripped_markup.inline_keyboard[0]) == 1
    assert stripped_markup.inline_keyboard[0][0].text == "✅ Contacted"
    assert stripped_markup.inline_keyboard[0][0].callback_data == "queue_warned:1"


class FakeCallbackQuery:
    def __init__(self, data):
        self.data = data
        self.edited = []
        self.message = self

    async def answer(self):
        return None

    async def edit_message_text(self, text, **kwargs):
        self.edited.append((text, kwargs))

    async def reply_text(self, text, **kwargs):
        self.edited.append((text, kwargs))


class FakeApplication:
    def __init__(self, database):
        self.bot_data = {
            "database": database,
            "queue_engine": QueueEngine(database),
        }


class FakeContext:
    def __init__(self, database):
        self.application = FakeApplication(database)


class FakeUpdate:
    def __init__(self, data):
        self.callback_query = FakeCallbackQuery(data)


@pytest.mark.asyncio
async def test_button_callbacks_update_status_and_advance(database):
    queue = QueueEngine(database)
    selection = queue.resume()
    update = FakeUpdate(f"queue_warned:{selection.customer['id']}")

    await handle_queue_callback(update, FakeContext(database))

    assert database.get_customer(selection.customer["id"])["status"] == "warned"
    assert "Grace Hopper" in update.callback_query.edited[-1][0]
