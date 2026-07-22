"""Tests for shared display formatting helpers (formatting.py).

Covers the currency/phone/loan-number/date helpers added for the
customer-data-quality pass, plus boundary cases for the pre-existing
duration formatters.
"""

from __future__ import annotations

from formatting import (
    format_currency,
    format_date,
    format_duration_coarse,
    format_duration_fine,
    format_loan_number,
    format_phone_display,
)


class TestFormatCurrency:
    def test_adds_thousands_separators(self):
        assert format_currency("784234385.32") == "784,234,385.32"

    def test_small_number_unchanged(self):
        assert format_currency("500") == "500"

    def test_whole_number_no_decimal(self):
        assert format_currency("1234567") == "1,234,567"

    def test_negative_number(self):
        assert format_currency("-2500.50") == "-2,500.50"

    def test_empty_value_is_em_dash(self):
        assert format_currency("") == "—"
        assert format_currency(None) == "—"

    def test_non_numeric_value_passes_through_unchanged(self):
        assert format_currency("N/A") == "N/A"


class TestFormatPhoneDisplay:
    def test_eleven_digit_us_number_with_country_code(self):
        assert format_phone_display("15551234567") == "+1 (555) 123-4567"

    def test_ten_digit_number(self):
        assert format_phone_display("5551234567") == "(555) 123-4567"

    def test_plus_prefixed_number(self):
        assert format_phone_display("+15551234567") == "+1 (555) 123-4567"

    def test_international_number_passes_through(self):
        assert format_phone_display("+442071234567") == "+442071234567"

    def test_empty_value(self):
        assert format_phone_display("") == ""
        assert format_phone_display(None) == ""


class TestFormatLoanNumber:
    def test_passes_through_unchanged(self):
        assert format_loan_number("C-KT12345") == "C-KT12345"

    def test_missing_value_is_em_dash(self):
        assert format_loan_number("") == "—"
        assert format_loan_number(None) == "—"


class TestFormatDate:
    def test_formats_iso_timestamp(self):
        assert format_date("2026-07-18T10:30:00+00:00") == "Jul 18, 2026"

    def test_missing_value_is_em_dash(self):
        assert format_date(None) == "—"
        assert format_date("") == "—"

    def test_malformed_value_passes_through(self):
        assert format_date("not-a-date") == "not-a-date"


class TestDurationFormattersBoundaries:
    def test_fine_zero_seconds(self):
        assert format_duration_fine(0) == "0s"

    def test_fine_under_a_minute(self):
        assert format_duration_fine(45) == "45s"

    def test_fine_exactly_one_minute(self):
        assert format_duration_fine(60) == "1m"

    def test_fine_minutes_and_seconds(self):
        assert format_duration_fine(138) == "2m 18s"

    def test_coarse_under_a_minute(self):
        assert format_duration_coarse(30) == "less than 1 minute"

    def test_coarse_exactly_one_minute(self):
        assert format_duration_coarse(60) == "1 minute"

    def test_coarse_multiple_minutes(self):
        assert format_duration_coarse(900) == "15 minutes"
