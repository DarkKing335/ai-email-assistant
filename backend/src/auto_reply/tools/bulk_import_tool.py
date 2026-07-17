"""
bulk_import_tool.py — CSV and Excel import for whitelist entries.

Pipeline:
  1. Parse file bytes → list of raw dicts
  2. Validate each row via guardrails
  3. Detect duplicates (against DB + within file)
  4. Bulk-upsert valid rows
  5. Return a structured BulkImportReport
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.agent.guardrails import validate_import_row, RowValidationResult
from src.auto_reply.infrastructure.repositories import WhitelistRepository
from src.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Report model
# ---------------------------------------------------------------------------


@dataclass
class ImportRowError:
    row_index: int
    raw_value: str
    errors: list[str]


@dataclass
class BulkImportReport:
    total_rows: int
    inserted: int
    skipped_duplicates: int
    validation_errors: list[ImportRowError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# BulkImportTool
# ---------------------------------------------------------------------------


class BulkImportTool:
    """Parse + validate + import whitelist entries from CSV or Excel."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = WhitelistRepository(session)

    # ------------------------------------------------------------------ CSV

    def _parse_csv(self, file_bytes: bytes) -> list[dict[str, Any]]:
        text = file_bytes.decode("utf-8-sig")   # strip BOM if present
        reader = csv.DictReader(io.StringIO(text))
        return [dict(row) for row in reader]

    # ---------------------------------------------------------------- Excel

    def _parse_excel(self, file_bytes: bytes) -> list[dict[str, Any]]:
        import openpyxl

        wb = openpyxl.load_workbook(filename=io.BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active
        if ws is None:
            return []

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        # First row = headers
        headers = [str(h).strip().lower() if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
        result: list[dict[str, Any]] = []
        for row in rows[1:]:
            result.append({headers[i]: (cell if cell is not None else "") for i, cell in enumerate(row)})
        wb.close()
        return result

    # ----------------------------------------------------------- Main entry

    async def import_csv(self, file_bytes: bytes, *, created_by: str | None = None) -> BulkImportReport:
        try:
            raw_rows = self._parse_csv(file_bytes)
        except Exception as exc:
            return BulkImportReport(
                total_rows=0,
                inserted=0,
                skipped_duplicates=0,
                warnings=[f"Failed to parse CSV: {exc}"],
            )
        return await self._process(raw_rows, created_by=created_by)

    async def import_excel(self, file_bytes: bytes, *, created_by: str | None = None) -> BulkImportReport:
        try:
            raw_rows = self._parse_excel(file_bytes)
        except Exception as exc:
            return BulkImportReport(
                total_rows=0,
                inserted=0,
                skipped_duplicates=0,
                warnings=[f"Failed to parse Excel file: {exc}"],
            )
        return await self._process(raw_rows, created_by=created_by)

    async def _process(
        self,
        raw_rows: list[dict[str, Any]],
        *,
        created_by: str | None,
    ) -> BulkImportReport:
        settings = get_settings()
        warnings: list[str] = []

        if len(raw_rows) > settings.bulk_import_max_rows:
            warnings.append(
                f"Import truncated: file contains {len(raw_rows)} rows "
                f"but limit is {settings.bulk_import_max_rows}."
            )
            raw_rows = raw_rows[: settings.bulk_import_max_rows]

        total_rows = len(raw_rows)
        validation_errors: list[ImportRowError] = []
        valid_rows: list[RowValidationResult] = []
        seen_in_file: set[str] = set()

        for i, row in enumerate(raw_rows, start=2):  # row 1 = header
            result = validate_import_row(i, row)
            if not result.is_valid:
                validation_errors.append(
                    ImportRowError(
                        row_index=i,
                        raw_value=str(row.get("value", "")),
                        errors=result.errors,
                    )
                )
                continue

            # In-file duplicate detection
            if result.value in seen_in_file:
                validation_errors.append(
                    ImportRowError(
                        row_index=i,
                        raw_value=result.value,
                        errors=[f"Duplicate value within the import file: '{result.value}'."],
                    )
                )
                continue

            seen_in_file.add(result.value)
            valid_rows.append(result)

        if not valid_rows:
            return BulkImportReport(
                total_rows=total_rows,
                inserted=0,
                skipped_duplicates=0,
                validation_errors=validation_errors,
                warnings=warnings,
            )

        db_rows = [
            {
                "value": r.value,
                "entry_type": r.entry_type,
                "priority": r.priority,
                "created_by": created_by,
            }
            for r in valid_rows
        ]

        inserted, skipped = await self._repo.bulk_upsert(db_rows)
        logger.info(
            "bulk_import total=%d inserted=%d skipped=%d errors=%d",
            total_rows,
            inserted,
            skipped,
            len(validation_errors),
        )

        return BulkImportReport(
            total_rows=total_rows,
            inserted=inserted,
            skipped_duplicates=skipped,
            validation_errors=validation_errors,
            warnings=warnings,
        )
