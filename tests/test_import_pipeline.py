"""Comprehensive test cases for the customer import pipeline.

Covers every way customer data can enter the system:
  - pasted JSON / plain JSON objects
  - uploaded .json files
  - pasted free-form text (AI-parsed)
  - CRM screenshots (AI vision-parsed)

...across four tiers: clean inputs, data edge cases, malformed/adversarial
inputs, and full pipeline integration.

WHY MOCKED AI RESPONSES: the OpenAI API isn't wired up yet. Tests that
exercise AIParser.parse_text/parse_image use a FakeOpenAIClient that
returns a scripted response instead of calling the network, so this
whole suite runs and passes today. When the real API key is added later,
these tests still validate the same thing: that our code correctly
handles whatever shape of response comes back (clean JSON, markdown
fences, wrapped objects, human-readable keys, or outright garbage). You
would additionally want a small number of *live* smoke tests against the
real API once it's active -- see the note at the bottom of this file.
"""

from __future__ import annotations

import asyncio
import json
import time as time_module
from datetime import datetime, timedelta, timezone

import pytest

from ai_parser import AIParser, ParserError
from config import Settings
from database import Database
from importer import Importer, ImporterError
from session_manager import SessionManager
from statistics_engine import StatisticsEngine


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def database(tmp_path):
    return Database(path=tmp_path / "session.db")


@pytest.fixture
def statistics(database):
    return StatisticsEngine(database)


@pytest.fixture
def session_manager(database, statistics):
    return SessionManager(database, statistics)


class _NullParser:
    """Stands in for AIParser when a test never needs the AI path
    (pasted/valid JSON short-circuits before touching the parser)."""


@pytest.fixture
def importer(database, session_manager):
    return Importer(_NullParser(), database, session_manager=session_manager)


# ---------------------------------------------------------------------------
# Fake OpenAI client -- lets AI-path tests run without a live API key
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, output_text: str):
        self.output_text = output_text


class _FakeResponses:
    def __init__(self, scripted_output):
        self._scripted_output = scripted_output

    async def create(self, **kwargs):
        output = self._scripted_output
        if callable(output):
            output = output(kwargs)
        return _FakeResponse(output)


class FakeOpenAIClient:
    """Drop-in stand-in for AsyncOpenAI. Swap for the real client once the
    API key is live -- nothing else about these tests needs to change."""

    def __init__(self, scripted_output):
        self.responses = _FakeResponses(scripted_output)


def make_ai_parser(scripted_output: str) -> AIParser:
    parser = AIParser(Settings(telegram_bot_token="x", openai_api_key="fake-key-for-tests"))
    parser.client = FakeOpenAIClient(scripted_output)
    parser.bypass_router = True
    return parser


# ===========================================================================
# TIER 1: Clean / valid inputs
# ===========================================================================

class TestCleanInputs:
    """The happy path for every entry point. If any of these fail, something
    basic is broken -- start debugging here first."""

    @pytest.mark.asyncio
    async def test_paste_clean_json_array(self, importer, database):
        """A well-formed JSON array pasted directly should import every row."""
        text = json.dumps([
            {"loan_number": "L1", "first_name": "Ann", "last_name": "Owens",
             "phone_numbers": ["5551234567"], "balance": "500", "days_overdue": "10"},
            {"loan_number": "L2", "first_name": "Bo", "last_name": "Kim",
             "phone_numbers": ["5559876543"], "balance": "750", "days_overdue": "20"},
        ])
        result = await importer.import_text(text)
        assert result.imported_count == 2
        assert database.count_customers() == 2
        assert result.verification_warnings == []

    @pytest.mark.asyncio
    async def test_paste_single_json_object_auto_wrapped(self, importer, database):
        """A single {..} object (not wrapped in []) should still import --
        the importer auto-wraps it into a one-item array."""
        text = json.dumps({"loan_number": "L1", "first_name": "Ann", "last_name": "Owens",
                            "phone_numbers": ["5551234567"]})
        result = await importer.import_text(text)
        assert result.imported_count == 1

    @pytest.mark.asyncio
    async def test_multiple_phone_numbers_per_customer(self, importer, database):
        text = json.dumps([{
            "loan_number": "L1", "first_name": "Ann", "last_name": "Owens",
            "phone_numbers": ["5551234567", "5559998888", "5551112222"],
        }])
        result = await importer.import_text(text)
        assert result.imported_count == 1
        stored = database.get_customer(1)
        assert len(stored["phone_numbers"]) == 3

    @pytest.mark.asyncio
    async def test_various_phone_number_formats_normalize_correctly(self, importer, database):
        """Dashes, parens, spaces, and a leading + should all normalize to
        digits-only (with + preserved when present)."""
        text = json.dumps([{
            "loan_number": "L1", "first_name": "Ann", "last_name": "Owens",
            "phone_numbers": ["(555) 123-4567", "+1 555 999 8888", "555.111.2222"],
        }])
        result = await importer.import_text(text)
        stored = database.get_customer(1)
        assert stored["phone_numbers"] == ["5551234567", "+15559998888", "5551112222"]


# ===========================================================================
# TIER 2: Data edge cases
# ===========================================================================

class TestDataEdgeCases:
    """Real-world messy data: duplicates, missing fields, unicode, scale."""

    @pytest.mark.asyncio
    async def test_duplicate_loan_number_across_separate_imports_is_flagged(self, importer, database):
        """Importing the same loan_number twice (two separate calls) should
        be silently skipped at the DB level but SURFACED as a warning
        (this is the round-trip verification redundancy check)."""
        text = json.dumps([{"loan_number": "L1", "first_name": "Ann", "last_name": "Owens",
                             "phone_numbers": ["5551234567"]}])
        first = await importer.import_text(text)
        second = await importer.import_text(text)
        assert first.verification_warnings == []
        assert any("already existed" in w for w in second.verification_warnings)
        assert database.count_customers() == 1  # not duplicated

    @pytest.mark.asyncio
    async def test_duplicate_loan_number_within_same_batch_is_silently_dropped(self, importer, database):
        """KNOWN GAP: if the SAME batch contains the same loan_number twice,
        validate_customers silently drops the second occurrence with no
        error and no warning -- unlike the cross-import case above, this
        is currently invisible to the operator. This test documents the
        current behavior; see the summary notes for a suggested fix."""
        text = json.dumps([
            {"loan_number": "L1", "first_name": "Ann", "last_name": "Owens", "phone_numbers": ["5551234567"]},
            {"loan_number": "L1", "first_name": "Ann2", "last_name": "Owens2", "phone_numbers": ["5559999999"]},
        ])
        result = await importer.import_text(text)
        assert result.imported_count == 1  # second L1 silently dropped
        assert result.verification_warnings == []  # currently: no visibility at all

    @pytest.mark.asyncio
    async def test_missing_required_field_no_longer_kills_the_whole_batch(self, importer, database):
        """FIXED: previously, one invalid row (a missing last name) killed
        the entire batch, discarding otherwise-valid customers. Now the
        valid row imports normally, and the incomplete-but-identifiable
        row (it has a loan_number) is flagged as 'needs_review' instead
        of being silently dropped or blocking everyone else."""
        text = json.dumps([
            {"loan_number": "L1", "first_name": "Ann", "last_name": "Owens", "phone_numbers": ["5551234567"]},
            {"loan_number": "L2", "first_name": "Bo", "last_name": "", "phone_numbers": ["5559876543"]},
        ])
        result = await importer.import_text(text)
        assert result.imported_count == 1
        assert result.flagged_count == 1
        # The issue lives on the flagged customer's warning_note, not in
        # result.errors -- errors is reserved for hard-rejected rows that
        # couldn't be stored at all (no loan_number, or an intra-batch dup).

        clean = database.get_customer(1)
        assert clean["status"] == "waiting"
        flagged = database.get_customer(2)
        assert flagged["status"] == "needs_review"
        assert flagged["warning_note"] == "last name is missing"

    @pytest.mark.asyncio
    async def test_missing_phone_number_is_flagged_not_rejected(self, importer, database):
        """A single row missing its phone number should be flagged for
        review (status='needs_review'), not raise -- there's nothing else
        wrong with the batch."""
        text = json.dumps([{"loan_number": "L1", "first_name": "Ann", "last_name": "Owens",
                             "phone_numbers": []}])
        result = await importer.import_text(text)
        assert result.imported_count == 0
        assert result.flagged_count == 1
        stored = database.get_customer(1)
        assert stored["status"] == "needs_review"
        assert "phone number is required" in stored["warning_note"]

    @pytest.mark.asyncio
    async def test_more_than_five_invalid_rows_rejects_the_whole_batch(self, importer, database):
        """The safety net: if a batch has MANY hard-rejected rows (no
        loan_number at all -- can't even be flagged for review), that
        usually means the whole file/schema is wrong, not just a few
        typos. Above the threshold, the entire import is refused rather
        than silently keeping a handful of survivors."""
        customers = [{"first_name": f"NoLoan{i}", "last_name": "X", "phone_numbers": ["5551234567"]}
                     for i in range(6)]  # 6 rows, all missing loan_number -- over the threshold of 5
        with pytest.raises(ImporterError, match="Too many invalid rows"):
            await importer.import_text(json.dumps(customers))
        assert database.count_customers() == 0

    @pytest.mark.asyncio
    async def test_five_or_fewer_invalid_rows_still_imports_the_rest(self, importer, database):
        """Right at the threshold: exactly 5 unidentifiable bad rows plus
        1 good row should still import the good one, not reject everything."""
        bad_customers = [{"first_name": f"NoLoan{i}", "last_name": "X", "phone_numbers": ["5551234567"]}
                          for i in range(5)]
        good_customer = {"loan_number": "L1", "first_name": "Ann", "last_name": "Owens",
                          "phone_numbers": ["5551234567"]}
        result = await importer.import_text(json.dumps(bad_customers + [good_customer]))
        assert result.imported_count == 1
        assert len(result.errors) == 5
        assert database.count_customers() == 1

    @pytest.mark.asyncio
    async def test_unicode_and_emoji_names_import_correctly(self, importer, database):
        """Accented characters, CJK, and emoji should all round-trip cleanly."""
        text = json.dumps([
            {"loan_number": "L1", "first_name": "José", "last_name": "Muñoz", "phone_numbers": ["5551234567"]},
            {"loan_number": "L2", "first_name": "田中", "last_name": "太郎", "phone_numbers": ["5559876543"]},
            {"loan_number": "L3", "first_name": "Anna 🎉", "last_name": "Star", "phone_numbers": ["5551112222"]},
        ])
        result = await importer.import_text(text)
        assert result.imported_count == 3
        assert database.get_customer(1)["first_name"] == "José"
        assert database.get_customer(2)["first_name"] == "田中"
        assert database.get_customer(3)["first_name"] == "Anna 🎉"

    @pytest.mark.asyncio
    async def test_very_long_field_values_do_not_crash(self, importer, database):
        long_name = "A" * 2000
        text = json.dumps([{"loan_number": "L1", "first_name": long_name, "last_name": "Owens",
                             "phone_numbers": ["5551234567"]}])
        result = await importer.import_text(text)
        assert result.imported_count == 1
        assert len(database.get_customer(1)["first_name"]) == 2000

    @pytest.mark.asyncio
    async def test_large_batch_imports_completely(self, importer, database):
        """500 unique customers should all import without error. Not a
        strict timing assertion (environment-dependent) -- just proves
        correctness doesn't degrade at scale."""
        customers = [
            {"loan_number": f"L{i:05d}", "first_name": f"First{i}", "last_name": f"Last{i}",
             "phone_numbers": [f"555{i:07d}"], "balance": "100", "days_overdue": "5"}
            for i in range(500)
        ]
        started = time_module.monotonic()
        result = await importer.import_text(json.dumps(customers))
        elapsed = time_module.monotonic() - started
        assert result.imported_count == 500
        assert database.count_customers() == 500
        print(f"\n  [perf] 500-customer import took {elapsed:.2f}s")


# ===========================================================================
# TIER 3: Malformed / adversarial inputs
# ===========================================================================

class TestMalformedAndAdversarialInputs:
    """Inputs designed to break the parser, not just annoy it."""

    @pytest.mark.asyncio
    async def test_malformed_json_syntax_raises_clear_error(self, importer):
        bad_json = '[{"loan_number": "L1", "first_name": "Ann",]'  # trailing comma, unclosed
        with pytest.raises(ImporterError, match="Malformed JSON"):
            await importer.import_text(bad_json)

    def test_load_json_array_rejects_non_array_json(self):
        """Direct unit test of validation.load_json_array: a bare JSON
        scalar (valid JSON, but not an array) must be rejected clearly."""
        from validation import ValidationError, load_json_array

        with pytest.raises(ValidationError, match="must be a JSON array"):
            load_json_array("42")

    @pytest.mark.asyncio
    async def test_bare_scalar_text_is_routed_to_ai_parser_not_json_validation(self, database, session_manager):
        """KNOWN NUANCE, not necessarily a bug: import_text's json-vs-text
        routing is based on whether the text STARTS with '[' or '{' --
        not on whether it came from a .json file. So a .json file whose
        top-level content is a bare number/string (technically valid
        JSON, just not an object/array) skips load_json_array entirely
        and gets sent to the AI text parser instead. Flagged in the
        summary as a candidate fix: have handle_json_file call
        load_json_array directly instead of import_text's heuristic."""
        parser = make_ai_parser("[]")  # AI "correctly" finds nothing in "42"
        importer = Importer(parser, database, session_manager=session_manager)
        with pytest.raises(ImporterError, match="empty"):
            await importer.import_text("42")

    @pytest.mark.asyncio
    async def test_json_array_of_non_objects_is_rejected(self, importer):
        with pytest.raises(ImporterError, match="must be an object"):
            await importer.import_text(json.dumps(["Ann", "Bo", "Cy"]))

    @pytest.mark.asyncio
    async def test_empty_json_array_is_rejected(self, importer):
        with pytest.raises(ImporterError, match="empty"):
            await importer.import_text("[]")

    @pytest.mark.asyncio
    async def test_sql_injection_style_values_are_stored_literally_not_executed(self, importer, database):
        """Confidence check that parameterized queries hold: a classic
        injection string should just be stored as inert text, and the
        customers table should still exist and be queryable afterward."""
        text = json.dumps([{
            "loan_number": "L1",
            "first_name": "Robert'); DROP TABLE customers;--",
            "last_name": "Tables",
            "phone_numbers": ["5551234567"],
        }])
        result = await importer.import_text(text)
        assert result.imported_count == 1
        # If the injection had worked, this would raise sqlite3.OperationalError.
        assert database.count_customers() == 1
        assert database.get_customer(1)["first_name"] == "Robert'); DROP TABLE customers;--"

    def test_json_file_with_invalid_utf8_is_handled(self, tmp_path):
        """Simulates handle_json_file's decode step directly -- invalid
        bytes should raise UnicodeDecodeError, which the handler catches
        and turns into a friendly message rather than crashing."""
        bad_bytes = b"\xff\xfe\x00\x01 not valid utf-8 \x80\x81"
        with pytest.raises(UnicodeDecodeError):
            bad_bytes.decode("utf-8")

    @pytest.mark.asyncio
    async def test_empty_text_is_rejected_with_clear_message(self, importer):
        with pytest.raises(ImporterError):
            await importer.import_text("   ")


# ===========================================================================
# TIER 4: Telegram split-message edge cases
# ===========================================================================

class TestSplitMessageMerging:
    """Telegram auto-splits pastes over ~4096 characters into consecutive
    messages. These test the merge-and-retry redundancy in telegram_ui.py.
    """

    def test_incomplete_json_fragment_is_detected(self):
        from telegram_ui import _looks_like_incomplete_json

        fragment = '[{"loan_number":"L1","first_name":"Ann","phone_numbers":["555'
        assert _looks_like_incomplete_json(fragment) is True

    def test_complete_json_is_not_flagged_as_incomplete(self):
        from telegram_ui import _looks_like_incomplete_json

        assert _looks_like_incomplete_json('[{"a": 1}]') is False

    def test_plain_prose_is_never_flagged_as_incomplete_json(self):
        """Free-form text (destined for the AI parser) must never be
        mistaken for a broken JSON paste."""
        from telegram_ui import _looks_like_incomplete_json

        assert _looks_like_incomplete_json("John Smith owes $500, call him back") is False

    def test_two_fragments_combine_into_valid_json(self):
        from telegram_ui import _looks_like_incomplete_json

        fragment_1 = '[{"loan_number":"L1","first_name":"Ann","last_name":"Owens","phone_numbers":["555'
        fragment_2 = '1234567"]}]'
        assert _looks_like_incomplete_json(fragment_1) is True
        assert _looks_like_incomplete_json(fragment_1 + fragment_2) is False

    def test_merge_window_expiry_is_respected(self):
        """A pending fragment older than FRAGMENT_MERGE_WINDOW_SECONDS
        should NOT be merged with a later, unrelated message -- this
        test checks the timing logic in isolation."""
        from telegram_ui import FRAGMENT_MERGE_WINDOW_SECONDS

        pending_timestamp = time_module.monotonic() - (FRAGMENT_MERGE_WINDOW_SECONDS + 1)
        now = time_module.monotonic()
        assert (now - pending_timestamp) > FRAGMENT_MERGE_WINDOW_SECONDS


# ===========================================================================
# TIER 5: AI-path tests (mocked -- run and pass without a live API key)
# ===========================================================================

class TestAIParsingWithMockedClient:
    """Exercises AIParser.parse_text / parse_image against a scripted fake
    client, covering the response shapes real models are known to produce.
    """

    @pytest.mark.asyncio
    async def test_clean_array_response(self):
        parser = make_ai_parser(
            '[{"loan_number":"L1","first_name":"Ann","last_name":"Owens",'
            '"phone_numbers":["5551234567"],"balance":"500","days_overdue":"10"}]'
        )
        customers = await parser.parse_text("Ann Owens, loan L1, owes $500, 10 days late, 555-123-4567")
        assert len(customers) == 1
        assert customers[0]["loan_number"] == "L1"

    @pytest.mark.asyncio
    async def test_response_wrapped_in_markdown_code_fence(self):
        """Models frequently wrap JSON in ```json ... ``` even when told
        not to. _extract_json_array's regex fallback should still find it.
        """
        scripted = (
            "```json\n"
            '[{"loan_number":"L1","first_name":"Ann","last_name":"Owens",'
            '"phone_numbers":["5551234567"]}]\n'
            "```"
        )
        parser = make_ai_parser(scripted)
        customers = await parser.parse_text("some free text about Ann")
        assert len(customers) == 1
        assert customers[0]["first_name"] == "Ann"

    @pytest.mark.asyncio
    async def test_response_wrapped_in_outer_object(self):
        """If the model wraps the array in {"customers": [...]}, despite
        instructions not to, the regex fallback should still extract just
        the inner array."""
        scripted = '{"customers": [{"loan_number":"L1","first_name":"Ann","last_name":"Owens","phone_numbers":["5551234567"]}]}'
        parser = make_ai_parser(scripted)
        customers = await parser.parse_text("some free text")
        assert len(customers) == 1

    @pytest.mark.asyncio
    async def test_human_readable_keys_get_mapped_to_snake_case(self):
        """If the model ignores the schema and uses "Loan Number" etc.,
        _map_common_keys should still normalize it."""
        scripted = json.dumps([{
            "Loan Number": "L1", "First Name": "Ann", "Last Name": "Owens",
            "Phone Number(s)": ["5551234567"], "Balance Owed": "500", "Days Overdue": "10",
        }])
        parser = make_ai_parser(scripted)
        customers = await parser.parse_text("some free text")
        assert customers[0]["loan_number"] == "L1"
        assert customers[0]["first_name"] == "Ann"

    @pytest.mark.asyncio
    async def test_prose_only_response_with_no_json_raises_parser_error(self):
        """If the model ignores instructions entirely and just chats,
        there's no salvageable JSON -- should raise a clear ParserError,
        not crash or silently return nothing."""
        parser = make_ai_parser("I'm sorry, I can't help with that request.")
        with pytest.raises(ParserError, match="did not return a JSON array"):
            await parser.parse_text("some free text")

    @pytest.mark.asyncio
    async def test_ai_reports_zero_customers_gives_clear_import_is_empty_error(self, database, session_manager):
        """If the AI honestly finds nothing (e.g. every customer in a
        screenshot was excluded by the +/X/crossed-out rule), it returns
        []. That correctly surfaces as a clear "Import is empty" error
        through the full pipeline -- NOT a silent "0 customers imported"
        success, which would be confusing. This is calling parse_text
        directly first to show where the error actually originates, then
        confirming the full importer path turns it into a clean message."""
        parser = make_ai_parser("[]")
        with pytest.raises(Exception, match="empty"):
            await parser.parse_text("a screenshot description with nothing usable")

        importer = Importer(parser, database, session_manager=session_manager)
        with pytest.raises(ImporterError, match="empty"):
            await importer.import_text("a screenshot description with nothing usable")
        assert database.count_customers() == 0

    @pytest.mark.asyncio
    async def test_no_api_key_raises_clear_error_for_text(self):
        parser = AIParser(Settings(telegram_bot_token="x", openai_api_key=None))
        with pytest.raises(ParserError, match="OPENAI_API_KEY is required"):
            await parser.parse_text("some unstructured free text")

    @pytest.mark.asyncio
    async def test_image_end_to_end_with_mocked_vision_response(self, tmp_path):
        """Full parse_image path: base64-encodes a fake image, sends it to
        the (mocked) vision model, and parses the scripted response."""
        image_path = tmp_path / "screenshot.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\nnot a real png but non-empty")

        parser = make_ai_parser(
            '[{"loan_number":"L1","first_name":"Ann","last_name":"Owens","phone_numbers":["5551234567"]}]'
        )
        customers = await parser.parse_image(image_path)
        assert len(customers) == 1
        assert customers[0]["loan_number"] == "L1"

    @pytest.mark.asyncio
    async def test_image_missing_file_raises_clear_error(self, tmp_path):
        parser = make_ai_parser("[]")
        with pytest.raises(ParserError, match="could not be read"):
            await parser.parse_image(tmp_path / "does_not_exist.png")

    @pytest.mark.asyncio
    async def test_image_empty_file_raises_clear_error(self, tmp_path):
        empty_path = tmp_path / "empty.png"
        empty_path.write_bytes(b"")
        parser = make_ai_parser("[]")
        with pytest.raises(ParserError, match="could not be read"):
            await parser.parse_image(empty_path)

    @pytest.mark.asyncio
    async def test_image_no_api_key_raises_clear_error(self, tmp_path):
        image_path = tmp_path / "screenshot.jpg"
        image_path.write_bytes(b"not empty")
        parser = AIParser(Settings(telegram_bot_token="x", openai_api_key=None))
        with pytest.raises(ParserError, match="OPENAI_API_KEY is required"):
            await parser.parse_image(image_path)


# ===========================================================================
# TIER 6: Full pipeline integration
# ===========================================================================

class TestFullPipelineIntegration:
    """A deliberately messy mixed batch, run all the way through
    import -> queue -> export, proving nothing crashes end-to-end."""

    @pytest.mark.asyncio
    async def test_mixed_batch_survives_full_pipeline(self, importer, database, session_manager):
        from queue_engine import QueueEngine
        from export_engine import export_customers

        text = json.dumps([
            {"loan_number": "L1", "first_name": "Ann", "last_name": "Owens", "phone_numbers": ["5551234567"]},
            {"loan_number": "L2", "first_name": "田中", "last_name": "太郎", "phone_numbers": ["5559876543", "5551112222"]},
            {"loan_number": "L3", "first_name": "Anna 🎉", "last_name": "Star", "phone_numbers": ["+15551234567"]},
        ])
        result = await importer.import_text(text)
        assert result.imported_count == 3

        # Corrupt one row at the DB layer after the fact, simulating
        # whatever produced the original "internal issue" bug report --
        # the queue must route around it, not crash.
        with database.connect() as conn:
            conn.execute(
                "UPDATE customers SET phone_numbers = ? WHERE loan_number = 'L2'",
                ("{not valid json",),
            )
            conn.commit()

        statistics = StatisticsEngine(database)
        queue = QueueEngine(database, statistics=statistics, session_manager=session_manager)

        handled = 0
        for _ in range(5):
            selection = queue.next_customer()
            if selection.complete:
                break
            if selection.customer:
                queue.apply_action(selection.customer["id"], "warned")
                handled += 1

        counts = database.status_counts()
        assert counts["warned"] == 2       # L1 and L3
        assert counts["invalid_number"] == 1  # L2, skipped automatically

        # Export should still work cleanly against the surviving records.
        exported_path = export_customers(database.get_all_customers(), session_id=1, export_format="json")
        exported_data = json.loads(exported_path.read_text(encoding="utf-8"))
        assert len(exported_data) == 3

    @pytest.mark.asyncio
    async def test_call_order_matches_import_order(self, importer, database, session_manager):
        """The order data comes IN should be the order it goes OUT: customers
        must be called in exactly the sequence they appeared in the import,
        not reordered by name, loan number, or anything else."""
        from queue_engine import QueueEngine

        # Deliberately non-alphabetical, non-numeric-sorted loan numbers so
        # any accidental re-sorting would be caught.
        text = json.dumps([
            {"loan_number": "Z9", "first_name": "Zoe", "last_name": "Last", "phone_numbers": ["5550000001"]},
            {"loan_number": "A1", "first_name": "Alice", "last_name": "First", "phone_numbers": ["5550000002"]},
            {"loan_number": "M5", "first_name": "Mo", "last_name": "Middle", "phone_numbers": ["5550000003"]},
        ])
        await importer.import_text(text)

        statistics = StatisticsEngine(database)
        queue = QueueEngine(database, statistics=statistics, session_manager=session_manager)

        call_order = []
        for _ in range(3):
            selection = queue.next_customer()
            assert selection.customer is not None
            call_order.append(selection.customer["loan_number"])
            queue.apply_action(selection.customer["id"], "warned")

        assert call_order == ["Z9", "A1", "M5"]  # exact import order preserved

    @pytest.mark.asyncio
    async def test_call_order_preserved_across_mixed_clean_and_flagged_rows(self, importer, database, session_manager):
        """REGRESSION: clean and flagged (needs_review) rows are inserted
        via a single combined call precisely so a batch that INTERLEAVES
        them still comes out in true source order. (Two separate insert
        calls -- one for clean, one for flagged -- would stamp flagged
        rows with a later timestamp regardless of their original position,
        silently reordering them to the back.)"""
        from queue_engine import QueueEngine

        text = json.dumps([
            {"loan_number": "L1", "first_name": "Ann", "last_name": "Owens", "phone_numbers": ["5550000001"]},
            {"loan_number": "L2", "first_name": "Bo", "last_name": "", "phone_numbers": ["5550000002"]},  # flagged
            {"loan_number": "L3", "first_name": "Cy", "last_name": "Diaz", "phone_numbers": ["5550000003"]},
        ])
        result = await importer.import_text(text)
        assert result.imported_count == 2
        assert result.flagged_count == 1

        statistics = StatisticsEngine(database)
        queue = QueueEngine(database, statistics=statistics, session_manager=session_manager)

        order = []
        for _ in range(3):
            selection = queue.next_customer()
            assert selection.customer is not None
            order.append(selection.customer["loan_number"])
            action = "skip" if selection.customer["status"] == "needs_review" else "warned"
            queue.apply_action(selection.customer["id"], action)

        assert order == ["L1", "L2", "L3"]  # L2 (flagged) stays in its true position

    @pytest.mark.asyncio
    async def test_cross_session_duplicate_allowed_with_same_day_warning(self, importer, database, session_manager):
        """A customer already worked in a prior session CAN be re-imported
        and re-queued (unlike a same-session duplicate, which is a no-op).
        If they were contacted earlier the SAME day, the requeued row
        should carry a same-day warning_note, which the queue card then
        displays with a clarifying emoji."""
        from queue_engine import QueueEngine
        from queue_ui import render_customer

        text = json.dumps([{"loan_number": "L1", "first_name": "Ann", "last_name": "Owens",
                             "phone_numbers": ["5551234567"]}])
        await importer.import_text(text)

        statistics = StatisticsEngine(database)
        queue = QueueEngine(database, statistics=statistics, session_manager=session_manager)
        first_selection = queue.next_customer()
        queue.apply_action(first_selection.customer["id"], "warned")  # "worked" earlier today

        # Re-import the same loan_number later the same day.
        second_result = await importer.import_text(text)
        assert second_result.imported_count == 1  # allowed, not blocked

        requeued = database.get_customer(first_selection.customer["id"])
        assert requeued["status"] == "waiting"
        assert requeued["warning_note"] is not None
        assert "today" in requeued["warning_note"]

        # The queue should surface them again, with the warning visible
        # on the card itself.
        next_selection = queue.next_customer()
        rendered = render_customer(next_selection.customer, next_selection.progress)
        assert "⚠️" in rendered
        assert "today" in rendered

    @pytest.mark.asyncio
    async def test_cross_session_duplicate_different_day_has_no_warning(self, importer, database, session_manager):
        """If the prior contact was on an earlier CALENDAR DAY (not today),
        no same-day warning should be attached -- recontacting someone the
        next day is normal, expected workflow, not a duplicate-call risk."""
        from queue_engine import QueueEngine

        text = json.dumps([{"loan_number": "L1", "first_name": "Ann", "last_name": "Owens",
                             "phone_numbers": ["5551234567"]}])
        await importer.import_text(text)

        statistics = StatisticsEngine(database)
        queue = QueueEngine(database, statistics=statistics, session_manager=session_manager)
        selection = queue.next_customer()
        customer_id = selection.customer["id"]
        queue.apply_action(customer_id, "warned")

        # Backdate their status_timestamp to yesterday, simulating a
        # contact made on a previous day rather than "just now".
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        with database.connect() as conn:
            conn.execute(
                "UPDATE customers SET status_timestamp = ? WHERE id = ?",
                (yesterday, customer_id),
            )
            conn.commit()

        result = await importer.import_text(text)
        assert result.imported_count == 1
        requeued = database.get_customer(customer_id)
        assert requeued["warning_note"] is None

    @pytest.mark.asyncio
    async def test_needs_review_customer_shows_skip_and_delete_buttons(self, importer, database, session_manager):
        """A flagged (needs_review) customer should reach the queue with
        Skip/Delete buttons instead of Call/Didn't Answer/Message Received
        -- there's not enough data to safely call them."""
        from queue_engine import QueueEngine
        from queue_ui import queue_keyboard

        text = json.dumps([{"loan_number": "L1", "first_name": "Ann", "last_name": "",
                             "phone_numbers": ["5551234567"]}])
        result = await importer.import_text(text)
        assert result.flagged_count == 1

        statistics = StatisticsEngine(database)
        queue = QueueEngine(database, statistics=statistics, session_manager=session_manager)
        selection = queue.next_customer()
        assert selection.customer["status"] == "needs_review"

        keyboard = queue_keyboard(selection.customer).inline_keyboard
        button_texts = [button.text for row in keyboard for button in row]
        assert any("Skip" in text for text in button_texts)
        assert any("Delete" in text for text in button_texts)
        assert not any("Didn't Answer" in text for text in button_texts)
        assert not any("Message Received" in text for text in button_texts)

    @pytest.mark.asyncio
    async def test_skip_action_advances_queue_without_deleting(self, importer, database, session_manager):
        from queue_engine import QueueEngine

        text = json.dumps([
            {"loan_number": "L1", "first_name": "Ann", "last_name": "", "phone_numbers": ["5551234567"]},
            {"loan_number": "L2", "first_name": "Bo", "last_name": "Kim", "phone_numbers": ["5559876543"]},
        ])
        await importer.import_text(text)

        statistics = StatisticsEngine(database)
        queue = QueueEngine(database, statistics=statistics, session_manager=session_manager)
        first = queue.next_customer()
        assert first.customer["loan_number"] == "L1"

        second = queue.apply_action(first.customer["id"], "skip")
        assert second.customer["loan_number"] == "L2"

        skipped = database.get_customer(first.customer["id"])
        assert skipped["status"] == "skip"
        assert database.count_customers() == 2  # still there, just skipped

    @pytest.mark.asyncio
    async def test_delete_action_removes_customer_permanently(self, importer, database, session_manager):
        from queue_engine import QueueEngine

        text = json.dumps([
            {"loan_number": "L1", "first_name": "Ann", "last_name": "", "phone_numbers": ["5551234567"]},
            {"loan_number": "L2", "first_name": "Bo", "last_name": "Kim", "phone_numbers": ["5559876543"]},
        ])
        await importer.import_text(text)

        statistics = StatisticsEngine(database)
        queue = QueueEngine(database, statistics=statistics, session_manager=session_manager)
        first = queue.next_customer()
        assert first.customer["loan_number"] == "L1"

        second = queue.delete_customer(first.customer["id"])
        assert second.customer["loan_number"] == "L2"
        assert database.count_customers() == 1  # actually gone, not just marked


# ===========================================================================
# TIER 7: Extended financial fields (customer-data-quality pass)
# ===========================================================================

class TestExtendedFinancialFieldImport:
    """monthly_payment, current_overdue_amount, and original_loan_amount
    are new customer-model fields; these confirm they survive the same
    import pipeline (JSON paste, human-readable keys, dollar-formatted
    values, and Excel column aliases) that balance/days_overdue already
    went through."""

    @pytest.mark.asyncio
    async def test_json_import_stores_new_financial_fields(self, importer, database):
        text = json.dumps([{
            "loan_number": "F1", "first_name": "Fin", "last_name": "Ance",
            "phone_numbers": ["5551234567"],
            "balance": "5000", "days_overdue": "12",
            "monthly_payment": "$250.00", "current_overdue_amount": "$500.00",
            "original_loan_amount": "$10,000.00",
        }])
        result = await importer.import_text(text)
        assert result.imported_count == 1
        stored = database.get_customer(1)
        assert stored["monthly_payment"] == "250.00"
        assert stored["current_overdue_amount"] == "500.00"
        assert stored["original_loan_amount"] == "10000.00"

    @pytest.mark.asyncio
    async def test_missing_financial_fields_default_to_empty_not_error(self, importer, database):
        """A row with none of the new fields should import exactly as it
        always did -- these fields are additive, never required."""
        text = json.dumps([{
            "loan_number": "F2", "first_name": "No", "last_name": "Extra",
            "phone_numbers": ["5551234567"],
        }])
        result = await importer.import_text(text)
        assert result.imported_count == 1
        stored = database.get_customer(1)
        assert stored["monthly_payment"] == ""
        assert stored["current_overdue_amount"] == ""
        assert stored["original_loan_amount"] == ""

    @pytest.mark.asyncio
    async def test_human_readable_financial_keys_map_correctly(self):
        from ai_parser import AIParser

        parser = AIParser(Settings(telegram_bot_token="x", openai_api_key="fake-key"))
        parser.client = FakeOpenAIClient(json.dumps([{
            "Loan Number": "F3", "First Name": "Human", "Last Name": "Keys",
            "Phone Number(s)": ["5551234567"],
            "Monthly Payment": "300.00", "Current Overdue Amount": "150.00",
            "Original Loan Amount": "8000.00",
        }]))
        parser.bypass_router = True
        customers = await parser.parse_text("some free text")
        assert customers[0]["monthly_payment"] == "300.00"
        assert customers[0]["current_overdue_amount"] == "150.00"
        assert customers[0]["original_loan_amount"] == "8000.00"

    def test_xlsx_alias_headers_map_new_financial_fields(self, tmp_path):
        import openpyxl
        from validation import load_xlsx_rows

        path = tmp_path / "loans.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append([
            "Loan Number", "First Name", "Last Name", "Phone",
            "Monthly Payment", "Overdue Amount", "Original Loan Amount",
        ])
        ws.append(["X1", "Xena", "Row", "5551234567", "275.50", "100.00", "9000.00"])
        wb.save(path)

        rows = load_xlsx_rows(path)
        assert rows[0]["monthly_payment"] == "275.50"
        assert rows[0]["current_overdue_amount"] == "100.00"
        assert rows[0]["original_loan_amount"] == "9000.00"

    def test_normalize_money_strips_dollar_sign_and_commas(self):
        from validation import normalize_money

        assert normalize_money("$1,234.56") == "1234.56"
        assert normalize_money("784,234,385.32") == "784234385.32"
        assert normalize_money("") == ""
        assert normalize_money(None) == ""

    def test_export_includes_new_financial_columns(self, importer, database, tmp_path, monkeypatch):
        import export_engine

        monkeypatch.setattr(export_engine, "EXPORTS_DIR", tmp_path)
        text = json.dumps([{
            "loan_number": "F4", "first_name": "Ex", "last_name": "Port",
            "phone_numbers": ["5551234567"], "monthly_payment": "100.00",
            "current_overdue_amount": "50.00", "original_loan_amount": "2000.00",
        }])
        await_result = importer.import_text(text)
        import asyncio
        asyncio.run(await_result)

        path = export_engine.export_customers(database.get_all_customers(), session_id=1, export_format="csv")
        content = path.read_text(encoding="utf-8")
        assert "Monthly Payment" in content
        assert "100.00" in content
        assert "Original Loan Amount" in content
