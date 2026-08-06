from __future__ import annotations

import pytest

from database import Database


SAMPLE = [
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
]


@pytest.fixture
def database(tmp_path) -> Database:
    db = Database(path=tmp_path / "session.db")
    db.insert_customers(SAMPLE)
    return db


class TestSearch:
    def test_search_by_first_name(self, database):
        results = database.search_customers("Ann")
        assert [r["loan_number"] for r in results] == ["L001"]

    def test_search_by_loan_number(self, database):
        results = database.search_customers("L002")
        assert [r["loan_number"] for r in results] == ["L002"]

    def test_search_by_phone_substring(self, database):
        results = database.search_customers("0002222")
        assert [r["loan_number"] for r in results] == ["L002"]

    def test_search_is_case_insensitive_for_names(self, database):
        results = database.search_customers("ann")
        assert [r["loan_number"] for r in results] == ["L001"]

    def test_search_by_full_name(self, database):
        """Confirmed bug, now fixed: searching a combined "first last"
        name previously returned zero results even with an exact match
        on file, since first_name/last_name are separate columns and
        neither alone contains the full typed string."""
        results = database.search_customers("Ann Owens")
        assert [r["loan_number"] for r in results] == ["L001"]

    def test_search_no_match_returns_empty(self, database):
        assert database.search_customers("nonexistent") == []

    def test_search_empty_query_returns_empty(self, database):
        assert database.search_customers("   ") == []

    def test_search_covers_any_status_not_just_waiting(self, database):
        customer = database.get_customer(1)
        database.update_customer_status(customer["id"], "paid")
        results = database.search_customers("Ann")
        assert [r["loan_number"] for r in results] == ["L001"]


class TestCustomerEvents:
    def test_get_customer_events_empty_when_nothing_recorded(self, database):
        assert database.get_customer_events(1) == []

    def test_get_customer_events_returns_newest_first(self, database):
        with database.connect() as conn:
            conn.execute(
                "INSERT INTO customer_events (customer_id, event_type, event_timestamp) "
                "VALUES (1, 'customer_warned', '2026-01-01T00:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO customer_events (customer_id, event_type, event_timestamp) "
                "VALUES (1, 'customer_skipped', '2026-01-02T00:00:00+00:00')"
            )
            conn.commit()

        events = database.get_customer_events(1)
        assert [e["event_type"] for e in events] == ["customer_skipped", "customer_warned"]

    def test_get_customer_events_scoped_to_one_customer(self, database):
        with database.connect() as conn:
            conn.execute(
                "INSERT INTO customer_events (customer_id, event_type, event_timestamp) "
                "VALUES (1, 'customer_warned', '2026-01-01T00:00:00+00:00')"
            )
            conn.execute(
                "INSERT INTO customer_events (customer_id, event_type, event_timestamp) "
                "VALUES (2, 'customer_warned', '2026-01-01T00:00:00+00:00')"
            )
            conn.commit()

        assert len(database.get_customer_events(1)) == 1
        assert len(database.get_customer_events(2)) == 1


class TestUpdateCustomerFields:
    def test_update_known_fields(self, database):
        database.update_customer_fields(1, first_name="Annie", balance="600")
        updated = database.get_customer(1)
        assert updated["first_name"] == "Annie"
        assert updated["balance"] == "600"

    def test_update_phone_numbers_serializes_list(self, database):
        database.update_customer_fields(1, phone_numbers=["+15559999999", "+15558888888"])
        updated = database.get_customer(1)
        assert updated["phone_numbers"] == ["+15559999999", "+15558888888"]

    def test_rejects_unknown_field(self, database):
        with pytest.raises(ValueError, match="loan_number"):
            database.update_customer_fields(1, loan_number="HACKED")

    def test_rejects_status_edit(self, database):
        """status is QueueEngine's concern (via update_customer_status),
        not a generic field edit -- this method must not be a backdoor
        around QueueEngine's status-transition rules."""
        with pytest.raises(ValueError, match="status"):
            database.update_customer_fields(1, status="paid")

    def test_no_fields_is_a_safe_no_op(self, database):
        before = database.get_customer(1)
        database.update_customer_fields(1)
        after = database.get_customer(1)
        assert before == after


class TestBlacklist:
    def test_customer_starts_not_blacklisted(self, database):
        assert database.get_customer(1)["is_blacklisted"] is False

    def test_set_customer_blacklisted(self, database):
        database.set_customer_blacklisted(1, True)
        assert database.get_customer(1)["is_blacklisted"] is True
        database.set_customer_blacklisted(1, False)
        assert database.get_customer(1)["is_blacklisted"] is False

    def test_phone_blacklist_independent_of_customer_row(self, database):
        """The whole point of the separate table: blacklisting a phone
        must survive the customer row it was first seen on being deleted."""
        database.blacklist_phone("+15550001111", reason="abuse", telegram_user_id=7)
        database.delete_customer(1)

        assert database.is_phone_blacklisted("+15550001111") is True

    def test_unblacklist_phone_removes_it(self, database):
        database.blacklist_phone("+15550001111")
        database.unblacklist_phone("+15550001111")
        assert database.is_phone_blacklisted("+15550001111") is False

    def test_blacklisting_same_phone_twice_updates_reason(self, database):
        database.blacklist_phone("+15550001111", reason="first reason")
        database.blacklist_phone("+15550001111", reason="updated reason")
        with database.connect() as conn:
            row = conn.execute(
                "SELECT reason FROM blacklisted_phones WHERE phone = ?", ("+15550001111",)
            ).fetchone()
        assert row["reason"] == "updated reason"

    def test_first_non_blacklisted_phone_skips_blacklisted(self, database):
        """When a phone is blacklisted, first_non_blacklisted_phone must
        return the next non-blacklisted phone from the list, not the
        blacklisted one -- so the Mini App API never shows a blacklisted
        number as the customer's contact phone."""
        database.blacklist_phone("+15550001111")
        database.blacklist_phone("+15550002222")
        result = database.first_non_blacklisted_phone(["+15550001111", "+15550002222", "+15550003333"])
        assert result == "+15550003333"

    def test_first_non_blacklisted_phone_falls_back_to_first_when_all_blacklisted(self, database):
        """If every phone number for a customer is blacklisted, fall back
        to the first phone rather than returning None/empty -- the
        operator can still see the number and decide what to do."""
        database.blacklist_phone("+15550001111")
        result = database.first_non_blacklisted_phone(["+15550001111"])
        assert result == "+15550001111"

    def test_first_non_blacklisted_phone_returns_first_when_none_blacklisted(self, database):
        """No blacklisted phones in the list means the first phone is
        returned unchanged -- the normal case, no filtering needed."""
        result = database.first_non_blacklisted_phone(["+15550001111", "+15550002222"])
        assert result == "+15550001111"


class TestGetCustomerRecord:
    def test_returns_none_for_missing_customer(self, database):
        assert database.get_customer_record(9999) is None

    def test_combines_customer_notes_and_history(self, database):
        database.set_customer_blacklisted(1, True)
        with database.connect() as conn:
            conn.execute(
                "INSERT INTO customer_events (customer_id, event_type, event_timestamp, notes) "
                "VALUES (1, 'customer_note_added', '2026-01-01T00:00:00+00:00', 'Call back after 4pm')"
            )
            conn.execute(
                "INSERT INTO customer_events (customer_id, event_type, event_timestamp) "
                "VALUES (1, 'customer_warned', '2026-01-02T00:00:00+00:00')"
            )
            conn.commit()

        record = database.get_customer_record(1)

        assert record["loan_number"] == "L001"
        assert record["is_blacklisted"] is True
        assert record["notes"] == [
            {"text": "Call back after 4pm", "telegram_user_id": None, "timestamp": "2026-01-01T00:00:00+00:00"}
        ]
        assert [e["event_type"] for e in record["history"]] == ["customer_warned", "customer_note_added"]

    def test_flags_blacklisted_phones_among_the_customers_numbers(self, database):
        database.blacklist_phone("+15550001111")
        record = database.get_customer_record(1)
        assert record["blacklisted_phones"] == ["+15550001111"]

    def test_no_blacklisted_phones_gives_empty_list(self, database):
        record = database.get_customer_record(1)
        assert record["blacklisted_phones"] == []


class TestExtendedFinancialFields:
    """monthly_payment, current_overdue_amount, original_loan_amount --
    added so the operator never needs the original CRM/spreadsheet to
    answer a customer's questions about their loan."""

    def test_new_fields_default_to_empty_string(self, database):
        customer = database.get_customer(1)
        assert customer["monthly_payment"] == ""
        assert customer["current_overdue_amount"] == ""
        assert customer["original_loan_amount"] == ""

    def test_new_fields_persist_through_insert(self, tmp_path):
        db = Database(path=tmp_path / "extended.db")
        db.insert_customers(
            [
                {
                    "loan_number": "F001",
                    "first_name": "Fin",
                    "last_name": "Ance",
                    "phone_numbers": ["+15550001234"],
                    "balance": "5000",
                    "days_overdue": "12",
                    "monthly_payment": "250.00",
                    "current_overdue_amount": "500.00",
                    "original_loan_amount": "10000.00",
                }
            ]
        )
        customer = db.get_customer(1)
        assert customer["monthly_payment"] == "250.00"
        assert customer["current_overdue_amount"] == "500.00"
        assert customer["original_loan_amount"] == "10000.00"

    def test_primary_phone_is_first_in_list(self, database):
        customer = database.get_customer(1)
        assert customer["primary_phone"] == customer["phone_numbers"][0]

    def test_primary_phone_empty_when_no_phones(self, tmp_path):
        db = Database(path=tmp_path / "nophone.db")
        db.insert_customers(
            [
                {
                    "loan_number": "NP1",
                    "first_name": "No",
                    "last_name": "Phone",
                    "phone_numbers": [],
                }
            ]
        )
        assert db.get_customer(1)["primary_phone"] == ""


class TestUpdateQueueSession:
    """update_queue_session must whitelist the fields it writes, mirroring
    update_customer_fields -- queue_session is internal queue state and
    callers must not be able to write arbitrary columns."""

    def test_update_known_fields(self, database):
        database.update_queue_session(is_paused=1, current_position=3)
        session = database.get_queue_session()
        assert session["is_paused"] == 1
        assert session["current_position"] == 3

    def test_rejects_unknown_field(self, database):
        with pytest.raises(ValueError, match="hacked_field"):
            database.update_queue_session(hacked_field="boom")

    def test_no_fields_is_a_safe_no_op(self, database):
        before = database.get_queue_session()
        database.update_queue_session()
        after = database.get_queue_session()
        assert before == after

    def test_updated_at_is_set_automatically(self, database):
        database.update_queue_session(is_paused=1)
        assert database.get_queue_session()["updated_at"] is not None


class TestWalMode:
    def test_connect_uses_wal_journal_mode(self, tmp_path):
        db = Database(path=tmp_path / "wal.db")
        with db.connect() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"


class TestLastEditedTimestamp:
    def test_starts_unset(self, database):
        assert database.get_customer(1)["last_edited_timestamp"] is None

    def test_set_on_edit(self, database):
        database.update_customer_fields(1, balance="999")
        assert database.get_customer(1)["last_edited_timestamp"] is not None

    def test_distinct_from_status_timestamp(self, database):
        """Editing a field must not look like a call outcome, and
        marking a call outcome must not look like a data correction."""
        database.update_customer_status(1, "warned")
        after_call = database.get_customer(1)
        assert after_call["status_timestamp"] is not None
        assert after_call["last_edited_timestamp"] is None

        database.update_customer_fields(1, balance="42")
        after_edit = database.get_customer(1)
        assert after_edit["last_edited_timestamp"] is not None
        # The call outcome timestamp is untouched by an unrelated edit.
        assert after_edit["status_timestamp"] == after_call["status_timestamp"]


class TestAttemptCount:
    def test_starts_at_zero(self, database):
        assert database.get_customer(1)["attempt_count"] == 0

    def test_increment_returns_new_count(self, database):
        assert database.increment_attempt_count(1) == 1
        assert database.increment_attempt_count(1) == 2
        assert database.get_customer(1)["attempt_count"] == 2

    def test_increment_only_affects_the_target_customer(self, database):
        database.increment_attempt_count(1)
        assert database.get_customer(2)["attempt_count"] == 0


class TestAppSettings:
    def test_get_setting_returns_default_when_unset(self, database):
        assert database.get_setting("max_call_attempts") is None
        assert database.get_setting("max_call_attempts", "unlimited") == "unlimited"

    def test_set_then_get_round_trips(self, database):
        database.set_setting("max_call_attempts", "3")
        assert database.get_setting("max_call_attempts") == "3"

    def test_set_overwrites_existing_value(self, database):
        database.set_setting("max_call_attempts", "3")
        database.set_setting("max_call_attempts", "1")
        assert database.get_setting("max_call_attempts") == "1"

    def test_get_settings_returns_a_dict_with_missing_keys_as_none(self, database):
        database.set_setting("auto_advance", "0")
        result = database.get_settings(["max_call_attempts", "auto_advance"])
        assert result == {"max_call_attempts": None, "auto_advance": "0"}


class TestReassignStatusWithAttemptLimit:
    def test_max_attempts_none_requeues_everyone(self, database):
        database.update_customer_status(1, "call_later")
        database.increment_attempt_count(1)
        database.increment_attempt_count(1)
        database.increment_attempt_count(1)
        moved = database.reassign_status("call_later", "waiting", max_attempts=None)
        assert moved == 1
        assert database.get_customer(1)["status"] == "waiting"

    def test_max_attempts_excludes_customers_at_or_over_the_cap(self, database):
        database.update_customer_status(1, "call_later")
        database.increment_attempt_count(1)
        database.increment_attempt_count(1)  # attempt_count == 2
        moved = database.reassign_status("call_later", "waiting", max_attempts=2)
        assert moved == 0
        assert database.get_customer(1)["status"] == "call_later"

    def test_max_attempts_includes_customers_under_the_cap(self, database):
        database.update_customer_status(1, "call_later")
        database.increment_attempt_count(1)  # attempt_count == 1
        moved = database.reassign_status("call_later", "waiting", max_attempts=2)
        assert moved == 1
        assert database.get_customer(1)["status"] == "waiting"
