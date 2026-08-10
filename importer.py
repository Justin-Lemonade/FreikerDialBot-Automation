from __future__ import annotations

import json
from dataclasses import dataclass, field

import validation

from config import IMPORTS_DIR, ORIGINALS_DIR


class ImporterError(Exception):
    pass


@dataclass
class ImportResult:
    imported_count: int = 0
    flagged_count: int = 0
    session_id: int | None = None
    errors: list[str] = field(default_factory=list)
    verification_warnings: list[str] = field(default_factory=list)
    customers: list[dict] = field(default_factory=list)
    original_path: object | None = None
    normalized_path: object | None = None


class Importer:
    def __init__(self, parser, database, session_manager=None):
        self.parser = parser
        self.database = database
        self.session_manager = session_manager

    async def import_text(self, text: str) -> ImportResult:
        text = (text or "").strip()
        if not text:
            raise ImporterError("Empty input: nothing to import.")

        if text.startswith("[") or text.startswith("{"):
            return await self._import_json(text)
        else:
            return await self._import_ai_text(text)

    async def import_image(self, image_path) -> ImportResult:
        import shutil
        from pathlib import Path

        image_path = Path(image_path)
        customers = await self.parser.parse_image(image_path)
        if not customers:
            raise ImporterError("AI found no customers in the image.")
        result = await self._process_customers(customers)

        if ORIGINALS_DIR and image_path.exists():
            orig_dir = Path(ORIGINALS_DIR)
            orig_dir.mkdir(parents=True, exist_ok=True)
            dest = orig_dir / image_path.name
            shutil.copy2(image_path, dest)
            result.original_path = dest

        if IMPORTS_DIR and result.customers:
            import_dir = Path(IMPORTS_DIR)
            import_dir.mkdir(parents=True, exist_ok=True)
            norm_path = import_dir / f"{image_path.stem}.json"
            import json as _json
            norm_path.write_text(_json.dumps(result.customers, indent=2, ensure_ascii=False))
            result.normalized_path = norm_path

        return result

    async def import_xlsx(self, xlsx_path) -> ImportResult:
        """Import from an .xlsx file. This method was called by
        telegram_ui.handle_xlsx_file but never actually implemented --
        every real .xlsx upload has been crashing with an AttributeError
        (not caught by handle_xlsx_file's `except ImporterError`, so it
        surfaced as an unhandled exception rather than a helpful
        message). validation.load_xlsx_rows already does the real
        parsing/column-alias work and has its own test coverage; this
        just wires it into the same _process_customers pipeline
        _import_json uses, so xlsx and JSON imports get identical
        duplicate-detection, flagging, and session-creation behavior.
        """
        from pathlib import Path

        xlsx_path = Path(xlsx_path)
        try:
            rows = validation.load_xlsx_rows(xlsx_path)
        except validation.ValidationError as exc:
            raise ImporterError(str(exc)) from exc

        customers = [validation.normalize_customer(row) for row in rows]
        result = await self._process_customers(customers)

        if ORIGINALS_DIR and xlsx_path.exists():
            import shutil

            orig_dir = Path(ORIGINALS_DIR)
            orig_dir.mkdir(parents=True, exist_ok=True)
            dest = orig_dir / xlsx_path.name
            shutil.copy2(xlsx_path, dest)
            result.original_path = dest

        if IMPORTS_DIR and result.customers:
            import_dir = Path(IMPORTS_DIR)
            import_dir.mkdir(parents=True, exist_ok=True)
            norm_path = import_dir / f"{xlsx_path.stem}.json"
            norm_path.write_text(json.dumps(result.customers, indent=2, ensure_ascii=False))
            result.normalized_path = norm_path

        return result

    async def _import_json(self, text: str) -> ImportResult:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ImporterError(f"Malformed JSON: {e}")

        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list):
            raise ImporterError("JSON root must be an array or object.")

        if not data:
            raise ImporterError("Import is empty: JSON array contains no records.")

        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise ImporterError(
                    f"JSON item {i + 1} must be an object, got {type(item).__name__}."
                )

        customers = [validation.normalize_customer(row) for row in data]
        return await self._process_customers(customers)

    async def _import_ai_text(self, text: str) -> ImportResult:
        try:
            customers = await self.parser.parse_text(text)
        except Exception as e:
            if "empty" in str(e).lower():
                raise ImporterError("AI found no customers in the text (empty result).") from e
            raise
        if not customers:
            raise ImporterError("AI found no customers in the text (empty result).")
        customers = [validation.normalize_customer(row) for row in customers]
        return await self._process_customers(customers)

    async def _process_customers(self, customers: list[dict]) -> ImportResult:
        result = ImportResult()

        all_rows = []
        flagged_count = 0
        rejected = 0

        for row in customers:
            issues = self._validate_row(row)
            has_loan = bool(row.get("loan_number", "").strip())

            if not has_loan:
                rejected += 1
                result.errors.append(
                    f"Row {len(result.errors) + rejected} rejected: no loan_number"
                )
                continue

            if issues:
                entry = dict(row)
                entry["_status"] = "needs_review"
                entry["_issue"] = "; ".join(issues)
                all_rows.append(entry)
                flagged_count += 1
            else:
                all_rows.append(row)

        if rejected > 5:
            raise ImporterError(
                f"Too many invalid rows ({rejected} missing loan_number). "
                "Please check the data format and try again."
            )

        if not all_rows:
            raise ImporterError("Import is empty: no valid customers found.")

        # Check for existing customers BEFORE inserting (for duplicate warnings)
        loan_numbers = [r.get("loan_number") for r in all_rows if r.get("loan_number")]
        existing_loans = set()
        if loan_numbers:
            existing = self.database.get_customers_by_loan_numbers(loan_numbers)
            existing_loans = {c["loan_number"] for c in existing}

        inserted = self.database.insert_customers(all_rows)

        result.imported_count = inserted - flagged_count
        result.flagged_count = flagged_count

        # Round-trip verification: warn about pre-existing customers
        for ln in loan_numbers:
            if ln in existing_loans:
                result.verification_warnings.append(
                    f"Customer {ln} already existed and was skipped."
                )

        # Create session
        if self.session_manager and all_rows:
            session_id = self.session_manager.create_session(len(all_rows))
            result.session_id = session_id

        result.customers = all_rows
        return result

    def _validate_row(self, row: dict) -> list[str]:
        issues = []
        loan = row.get("loan_number", "")
        if not isinstance(loan, str) or not loan.strip():
            issues.append("loan number is missing")
        name = row.get("first_name", "")
        if not isinstance(name, str) or not name.strip():
            issues.append("first name is missing")
        last = row.get("last_name", "")
        if not isinstance(last, str) or not last.strip():
            issues.append("last name is missing")
        phones = row.get("phone_numbers", [])
        if not phones or not isinstance(phones, list) or len(phones) == 0:
            issues.append("at least one phone number is required")
        return issues
