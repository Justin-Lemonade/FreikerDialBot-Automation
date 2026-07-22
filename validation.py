"""Customer import validation and normalization."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


STANDARD_KEYS = (
    "loan_number",
    "first_name",
    "last_name",
    "phone_numbers",
    "balance",
    "days_overdue",
    "monthly_payment",
    "current_overdue_amount",
    "original_loan_amount",
)


class ValidationError(Exception):
    """Raised when an import cannot be accepted."""


@dataclass(frozen=True)
class ValidationResult:
    customers: list[dict[str, Any]]
    flagged: list[dict[str, Any]]
    errors: list[str]

    @property
    def ok(self) -> bool:
        return bool(self.customers) or bool(self.flagged)


def load_json_array(raw_json: str) -> list[dict[str, Any]]:
    """Parse a JSON array of customer objects."""
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Malformed JSON: {exc.msg}") from exc

    if not isinstance(parsed, list):
        raise ValidationError("Import must be a JSON array.")
    if not parsed:
        raise ValidationError("Import is empty.")
    if not all(isinstance(item, dict) for item in parsed):
        raise ValidationError("Every imported customer must be an object.")
    return parsed


# Column name aliases for Excel imports: maps common spreadsheet header
# variations to the canonical field names used throughout the pipeline.
_XLSX_COLUMN_ALIASES: dict[str, str] = {
    # loan_number
    "loan number": "loan_number",
    "loan#": "loan_number",
    "loan id": "loan_number",
    "account number": "loan_number",
    "account#": "loan_number",
    # first_name
    "first name": "first_name",
    "firstname": "first_name",
    # last_name
    "last name": "last_name",
    "lastname": "last_name",
    "surname": "last_name",
    # phone_numbers
    "phone": "phone_numbers",
    "phone number": "phone_numbers",
    "phone numbers": "phone_numbers",
    "mobile": "phone_numbers",
    "cell": "phone_numbers",
    "telephone": "phone_numbers",
    # balance
    "balance owed": "balance",
    "amount owed": "balance",
    "outstanding balance": "balance",
    # days_overdue
    "days overdue": "days_overdue",
    "days past due": "days_overdue",
    "dpd": "days_overdue",
    # monthly_payment
    "monthly payment": "monthly_payment",
    "monthly installment": "monthly_payment",
    "payment amount": "monthly_payment",
    # current_overdue_amount
    "overdue amount": "current_overdue_amount",
    "amount overdue": "current_overdue_amount",
    "past due amount": "current_overdue_amount",
    "current overdue amount": "current_overdue_amount",
    # original_loan_amount
    "original loan amount": "original_loan_amount",
    "original amount": "original_loan_amount",
    "loan amount": "original_loan_amount",
    "principal": "original_loan_amount",
}


def load_xlsx_rows(path) -> list[dict[str, Any]]:
    """Parse an Excel (.xlsx) file into a list of customer dicts.

    The first row is treated as headers. Column names are matched
    case-insensitively against canonical field names and common aliases.
    Extra columns are ignored. Missing optional columns default to empty.

    Raises ValidationError if openpyxl is not installed, the file cannot
    be opened, or the sheet is empty / has no recognizable headers.
    """
    try:
        import openpyxl  # noqa: PLC0415
    except ImportError as exc:
        raise ValidationError(
            "openpyxl is required for Excel import. Run: pip install openpyxl"
        ) from exc

    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
    except Exception as exc:
        raise ValidationError(f"Could not open Excel file: {exc}") from exc

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValidationError("Excel file is empty.")

    # Map column index -> canonical key
    raw_headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    col_map: dict[int, str] = {}
    for idx, header in enumerate(raw_headers):
        lower = header.lower()
        # Direct match first, then alias lookup
        canonical = lower.replace(" ", "_") if lower.replace(" ", "_") in STANDARD_KEYS \
            else _XLSX_COLUMN_ALIASES.get(lower)
        if canonical:
            col_map[idx] = canonical

    if not col_map:
        raise ValidationError(
            "Could not find any recognizable column headers in the Excel file. "
            "Expected headers like: Loan Number, First Name, Last Name, Phone, Balance, Days Overdue."
        )

    result: list[dict[str, Any]] = []
    for row in rows[1:]:
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue  # skip blank rows
        record: dict[str, Any] = {}
        for idx, key in col_map.items():
            cell_val = row[idx] if idx < len(row) else None
            record[key] = str(cell_val).strip() if cell_val is not None else ""
        result.append(record)

    if not result:
        raise ValidationError("Excel file contains no data rows.")
    return result


def normalize_phone_number(phone: Any) -> str:
    """Normalize a phone number while preserving a leading plus."""
    value = str(phone or "").strip()
    if not value:
        return ""

    has_plus = value.startswith("+")
    digits = re.sub(r"\D", "", value)
    if not digits:
        return ""
    return f"+{digits}" if has_plus else digits


def normalize_loan_number(loan_number: Any) -> str:
    """Trim a loan number exactly as shown -- no reformatting, no case
    changes. Loan numbers (e.g. "C-KT12345") are opaque identifiers, not
    display values, so the only normalization that's ever safe is
    trimming incidental whitespace."""
    return str(loan_number or "").strip()


def normalize_money(value: Any) -> str:
    """Normalize a currency-ish field (balance, monthly payment, overdue
    amount, original loan amount) to a bare numeric string.

    Strips a leading "$", thousands-separator commas, and surrounding
    whitespace, but otherwise leaves the value alone -- this is
    deterministic cleanup, not currency parsing. An unreadable or blank
    value normalizes to "" (never invented), matching how balance has
    always behaved; nothing here rejects a row, it only tidies it before
    display-time formatting (see formatting.format_currency) is applied.
    """
    value = str(value if value is not None else "").strip()
    if not value:
        return ""
    cleaned = value.replace("$", "").replace(",", "").strip()
    return cleaned


def normalize_customer(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a customer with exactly the standard keys."""
    phones = raw.get("phone_numbers", raw.get("phone_number", []))
    if isinstance(phones, str):
        phones = re.split(r"[,;/\n]+", phones)
    if not isinstance(phones, list):
        phones = [phones]

    normalized_phones = []
    seen = set()
    for phone in phones:
        normalized = normalize_phone_number(phone)
        if normalized and normalized not in seen:
            normalized_phones.append(normalized)
            seen.add(normalized)

    return {
        "loan_number": normalize_loan_number(raw.get("loan_number", raw.get("loanNumber", ""))),
        "first_name": str(raw.get("first_name", raw.get("firstName", ""))).strip(),
        "last_name": str(raw.get("last_name", raw.get("lastName", ""))).strip(),
        "phone_numbers": normalized_phones,
        "balance": normalize_money(raw.get("balance", raw.get("balance_owed", ""))),
        "days_overdue": str(raw.get("days_overdue", raw.get("daysOverdue", ""))).strip(),
        "monthly_payment": normalize_money(raw.get("monthly_payment", raw.get("monthlyPayment", ""))),
        "current_overdue_amount": normalize_money(
            raw.get("current_overdue_amount", raw.get("currentOverdueAmount", ""))
        ),
        "original_loan_amount": normalize_money(
            raw.get("original_loan_amount", raw.get("originalLoanAmount", ""))
        ),
    }


def _describe_identity(customer: dict[str, Any]) -> str:
    """Best-effort identifying info for an error message, even when the
    row is missing some required fields -- so it's clear which record had
    a problem instead of just an index number."""
    bits = []
    if customer.get("loan_number"):
        bits.append(f"loan {customer['loan_number']}")
    full_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
    if full_name:
        bits.append(full_name)
    return f" ({', '.join(bits)})" if bits else ""


def validate_customers(customers: list[dict[str, Any]]) -> ValidationResult:
    """Normalize, validate, and deduplicate imported customers.

    Three outcomes per row:
      - customers: fully valid, imported normally as 'waiting'.
      - flagged: has a loan_number (so it's identifiable and storable) but
        is missing a name or phone number -- imported as 'needs_review'
        instead of being silently discarded, so an operator can see it in
        the queue and Skip or Delete it deliberately.
      - errors: hard rejections that can't be stored at all (no
        loan_number to key off of) or intra-batch duplicate loan numbers.
        These are reported but never saved.
    """
    if not customers:
        return ValidationResult([], [], ["Import is empty."])

    errors: list[str] = []
    accepted: list[dict[str, Any]] = []
    flagged: list[dict[str, Any]] = []
    seen_loans: set[str] = set()

    for index, raw_customer in enumerate(customers, start=1):
        customer = normalize_customer(raw_customer)
        row_errors = []

        if not customer["loan_number"]:
            row_errors.append("loan number is missing")
        if not customer["first_name"]:
            row_errors.append("first name is missing")
        if not customer["last_name"]:
            row_errors.append("last name is missing")
        if not customer["phone_numbers"]:
            row_errors.append("at least one phone number is required")

        loan_number = customer["loan_number"]

        if not loan_number:
            # No identifier at all -- can't be stored (loan_number is the
            # unique key) or reliably flagged for review. Hard rejection,
            # but still reported with whatever identity info exists.
            identity = _describe_identity(customer)
            errors.append(f"Customer {index}{identity}: {', '.join(row_errors)}.")
            continue

        if loan_number in seen_loans:
            errors.append(
                f"Customer {index} (loan {loan_number}): duplicate loan number "
                "within this import, skipped."
            )
            continue
        seen_loans.add(loan_number)

        row = {key: customer[key] for key in STANDARD_KEYS}
        row["_original_index"] = index
        if row_errors:
            # Identifiable (has a loan_number) but incomplete -- flag for
            # manual review rather than dropping it silently.
            row["_issue"] = ", ".join(row_errors)
            row["_status"] = "needs_review"
            flagged.append(row)
        else:
            row["_status"] = "waiting"
            accepted.append(row)

    if not accepted and not flagged and not errors:
        errors.append("Import contained only duplicate customers.")

    return ValidationResult(accepted, flagged, errors)
