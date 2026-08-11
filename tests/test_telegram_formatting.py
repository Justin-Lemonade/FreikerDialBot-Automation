"""Focused tests for the centralized Telegram presentation layer.

Covers HTML escaping (the security requirement), representative formatter
output, and the safe long-message split helper.
"""

from __future__ import annotations

from types import SimpleNamespace

import telegram_formatting as tf


def make_progress(**overrides):
    base = {
        "current_position": 1,
        "total_customers": 3,
        "remaining": 2,
        "contacted": 1,
        "did_not_answer": 0,
        "percent": 33,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def make_customer(**overrides):
    base = {
        "id": 1,
        "loan_number": "Q-1",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "phone_numbers": ["111"],
        "balance": "100",
        "days_overdue": "3",
    }
    base.update(overrides)
    return base


def make_record(**overrides):
    base = {
        "id": 1,
        "loan_number": "Q-1",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "phone_numbers": ["111"],
        "balance": "100",
        "monthly_payment": "10",
        "current_overdue_amount": "20",
        "original_loan_amount": "500",
        "days_overdue": "3",
        "status": "waiting",
        "import_timestamp": "2026-07-18T10:00:00+00:00",
        "last_edited_timestamp": None,
        "is_blacklisted": False,
        "blacklisted_phones": [],
        "warning_note": None,
        "notes": [],
        "history": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Escaping / injection safety
# ---------------------------------------------------------------------------

def test_customer_name_cannot_inject_html():
    customer = make_customer(first_name="<b>Hacker</b>", last_name="<img src=x>")
    rendered = tf.render_customer_card(customer, make_progress())

    assert "<b>Hacker</b>" not in rendered
    assert "<img src=x>" not in rendered
    assert "&lt;b&gt;Hacker&lt;/b&gt;" in rendered
    assert "&lt;img src=x&gt;" in rendered


def test_customer_record_escapes_notes_and_history():
    record = make_record(
        notes=[{"text": "<script>alert(1)</script>"}],
        history=[{"event_timestamp": "2026-07-18T10:00:00", "event_type": "<b>warned</b>"}],
    )
    rendered = tf.render_customer_record(record)

    assert "<script>alert(1)</script>" not in rendered
    assert "<b>warned</b>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered


def test_import_result_escapes_error_lines():
    result = SimpleNamespace(
        imported_count=2,
        flagged_count=0,
        errors=["<b>bad row</b>"],
        verification_warnings=[],
    )
    rendered = tf.render_import_result(result)

    assert "<b>bad row</b>" not in rendered
    assert "&lt;b&gt;bad row&lt;/b&gt;" in rendered


def test_error_message_never_exposes_raw_markup():
    rendered = tf.render_error(
        "Could not complete that action",
        "customer <script>",  # user-ish content, must be escaped
        "run /resume",
    )

    assert "<b>Could not complete that action</b>" in rendered
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "<b>What to do:</b>" in rendered


# ---------------------------------------------------------------------------
# Representative formatter output
# ---------------------------------------------------------------------------

def test_customer_card_structure_and_phone_link():
    rendered = tf.render_customer_card(make_customer(), make_progress())

    assert "<b>Ada Lovelace</b>" in rendered
    assert "<code>Q-1</code>" in rendered
    assert "<b>Contact</b>" in rendered
    assert 'Phone:</b> <a href="tel:111">111</a>' in rendered
    assert "<b>Balance:</b> <b>100</b>" in rendered
    assert "Position:</b> 1 / 3" in rendered
    assert "Progress:</b> 33%" in rendered


def test_customer_card_omits_missing_fields():
    customer = make_customer(
        loan_number=None,
        balance=None,
        days_overdue=None,
        monthly_payment=None,
        current_overdue_amount=None,
    )
    rendered = tf.render_customer_card(customer, make_progress())

    assert "<code>" not in rendered
    assert "<b>Balance:</b> <b>—</b>" in rendered
    assert "Days overdue" not in rendered


def test_customer_card_shows_warning_note():
    customer = make_customer(warning_note="Same day recontact — called today")
    rendered = tf.render_customer_card(customer, make_progress())

    assert "⚠️" in rendered
    assert "today" in rendered


def test_queue_status():
    rendered = tf.render_queue_status(make_progress())

    assert "<b>Calling Queue</b>" in rendered
    assert "<b>Remaining:</b> 2" in rendered
    assert "<b>Contacted:</b> 1" in rendered
    assert "<b>Didn't answer:</b> 0" in rendered
    assert "<b>Progress:</b> 33%" in rendered


def test_statistics_sections():
    snapshot = SimpleNamespace(
        today={
            "customers_loaded": 4,
            "customers_contacted": 2,
            "customers_not_answered": 1,
            "sessions_completed": 1,
        },
        lifetime={
            "customers_loaded": 9,
            "customers_contacted": 5,
            "customers_not_answered": 3,
            "sessions": 2,
        },
        average_contacts_per_session=2,
        average_seconds_per_customer=45,
    )
    rendered = tf.render_statistics(snapshot)

    assert "Today's Statistics" in rendered
    assert "<b>Lifetime</b>" in rendered
    assert "• <b>Imported:</b> 4" in rendered
    assert "• <b>Sessions:</b> 2" in rendered


def test_current_session_render():
    session = {
        "session_name": "Evening Calls",
        "started_at": "2026-07-18T10:00:00+00:00",
        "total_customers": 2,
        "status": "running",
    }
    counts = {"waiting": 1, "warned": 1, "call_later": 0}
    rendered = tf.render_current_session(session, counts)

    assert "<b>Session</b>" in rendered
    assert "Evening Calls" in rendered
    assert "running" in rendered
    assert "• <b>Imported:</b> 2" in rendered


def test_completion_summary_includes_average_line():
    summary = SimpleNamespace(
        imported=2,
        contacted=1,
        did_not_answer=1,
        duration_seconds=600,
        average_seconds_per_customer=45,
    )
    rendered = tf.render_completion_summary(summary)

    assert "Session Complete" in rendered
    assert "Average Time Per Customer" in rendered
    assert "• <b>Contacted:</b> 1" in rendered


def test_completion_details_names():
    counts = {"warned": 2, "call_later": 1, "waiting": 0}
    rendered = tf.render_completion_details(
        counts, ["Ada Lovelace", "Grace Hopper"], ["<b>Doe</b>"]
    )

    assert "Session Complete" in rendered
    assert "• <b>Contacted:</b> 2" in rendered
    assert "Ada Lovelace" in rendered
    assert "&lt;b&gt;Doe&lt;/b&gt;" in rendered


def test_help_text_groups_all_commands():
    rendered = tf.render_help_text()

    for group in ("Calling", "Customers", "Session &amp; Stats", "General", "Administration"):
        assert f"<b>{group}</b>" in rendered
    for command in (
        "/start",
        "/resume",
        "/pause",
        "/status",
        "/session",
        "/rename",
        "/stats",
        "/customer",
        "/edit",
        "/blacklist",
        "/unblacklist",
        "/blacklist_phone",
        "/unblacklist_phone",
        "/help",
        "/summary",
        "/reset",
        "/clear",
        "/export",
    ):
        assert f"<code>{command}" in rendered


# ---------------------------------------------------------------------------
# Safe long-message splitting
# ---------------------------------------------------------------------------

def test_split_html_returns_single_chunk_for_short_text():
    assert tf.split_html("<b>short</b>") == ["<b>short</b>"]


def test_split_html_never_loses_data():
    paragraphs = [
        f"<b>Section {i}</b>\n• value {i}" for i in range(3)
    ]
    paragraphs.extend(
        [
            "Some longer paragraph with plain text.",
            "<code>id-12345</code> and more",
        ]
    )
    text = "\n\n".join(paragraphs)
    chunks = tf.split_html(text, limit=80)

    assert len(chunks) > 1
    assert all(len(chunk) <= 80 for chunk in chunks)
    assert "\n\n".join(chunks) == text


def test_split_html_does_not_split_inside_tags():
    line = "<b>" + "x" * 50 + "</b>"
    text = line + "\n\n" + "<code>y</code>" * 40
    chunks = tf.split_html(text, limit=100)

    # Tag markup is never split across a chunk boundary.
    for chunk in chunks:
        assert "<b>" not in chunk or "</b>" in chunk
        assert "<code>" not in chunk or "</code>" in chunk


def test_split_html_handles_single_oversized_line():
    text = "x" * 9000
    chunks = tf.split_html(text, limit=4000)

    assert len(chunks) >= 3
    assert all(len(chunk) <= 4000 for chunk in chunks)
    assert "".join(chunks) == text
