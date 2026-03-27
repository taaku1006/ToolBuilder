"""Tests for services.xlsx_parser — TDD: tests written FIRST.

All tests use pytest fixtures defined in conftest.py to create real xlsx/csv
files in a temp directory. No mocking of the parser itself.
"""

from __future__ import annotations

import csv
import io
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Unit tests: parse_file — xlsx
# ---------------------------------------------------------------------------


class TestParseFileXlsx:
    """Unit tests for parse_file with xlsx input."""

    def test_returns_list_of_sheet_info(self, sample_xlsx: Path) -> None:
        """parse_file must return a list."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))

        assert isinstance(result, list)

    def test_single_sheet_length(self, sample_xlsx: Path) -> None:
        """Single-sheet xlsx must return a list with one element."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))

        assert len(result) == 1

    def test_sheet_name(self, sample_xlsx: Path) -> None:
        """SheetInfo.name must match the actual sheet name."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))

        assert result[0].name == "Sales"

    def test_total_rows_excludes_header(self, sample_xlsx: Path) -> None:
        """total_rows must count data rows only (excluding header row)."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))

        # fixture has 5 data rows
        assert result[0].total_rows == 5

    def test_headers_extracted(self, sample_xlsx: Path) -> None:
        """headers must match row-1 values of the sheet."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))

        assert result[0].headers == ["date", "product", "quantity", "price", "active"]

    def test_preview_is_list_of_dicts(self, sample_xlsx: Path) -> None:
        """preview must be a list of dicts keyed by header names."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))
        preview = result[0].preview

        assert isinstance(preview, list)
        assert all(isinstance(row, dict) for row in preview)

    def test_preview_keys_match_headers(self, sample_xlsx: Path) -> None:
        """Each preview dict must have keys matching headers."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))
        sheet = result[0]

        for row in sheet.preview:
            assert set(row.keys()) == set(sheet.headers)

    def test_preview_max_30_rows(self, large_xlsx: Path) -> None:
        """preview must contain at most 30 rows even when sheet has more."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(large_xlsx))

        assert len(result[0].preview) <= 30

    def test_preview_all_rows_when_fewer_than_30(self, sample_xlsx: Path) -> None:
        """When data rows <= 30 all rows appear in preview."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))

        # sample_xlsx has 5 data rows — all must appear
        assert len(result[0].preview) == 5

    def test_types_dict_has_all_headers(self, sample_xlsx: Path) -> None:
        """types dict must contain an entry for every header."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))
        sheet = result[0]

        assert set(sheet.types.keys()) == set(sheet.headers)

    def test_number_column_type(self, sample_xlsx: Path) -> None:
        """Numeric columns must be mapped to 'number'."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))
        types = result[0].types

        assert types["quantity"] == "number"
        assert types["price"] == "number"

    def test_date_column_type(self, sample_xlsx: Path) -> None:
        """Date columns must be mapped to 'date'."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))
        types = result[0].types

        assert types["date"] == "date"

    def test_string_column_type(self, sample_xlsx: Path) -> None:
        """String columns must be mapped to 'string'."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))
        types = result[0].types

        assert types["product"] == "string"

    def test_boolean_column_type(self, sample_xlsx: Path) -> None:
        """Boolean columns must be mapped to 'boolean'."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_xlsx))
        types = result[0].types

        assert types["active"] == "boolean"

    def test_multi_sheet_xlsx(self, multi_sheet_xlsx: Path) -> None:
        """xlsx with multiple sheets returns one SheetInfo per sheet."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(multi_sheet_xlsx))

        assert len(result) == 2
        names = {s.name for s in result}
        assert names == {"Sheet1", "Sheet2"}

    def test_sheet_info_is_frozen(self, sample_xlsx: Path) -> None:
        """SheetInfo must be immutable (frozen dataclass)."""
        from services.xlsx_parser import SheetInfo, parse_file

        result = parse_file(str(sample_xlsx))
        sheet = result[0]

        with pytest.raises((FrozenInstanceError, AttributeError)):
            sheet.name = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Unit tests: parse_file — csv
# ---------------------------------------------------------------------------


class TestParseFileCsv:
    """Unit tests for parse_file with csv input."""

    def test_csv_returns_single_sheet(self, sample_csv: Path) -> None:
        """CSV must be treated as a single sheet named 'Sheet1'."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_csv))

        assert len(result) == 1
        assert result[0].name == "Sheet1"

    def test_csv_headers(self, sample_csv: Path) -> None:
        """CSV headers must be read from first row."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_csv))

        assert result[0].headers == ["id", "name", "value"]

    def test_csv_total_rows(self, sample_csv: Path) -> None:
        """CSV total_rows must count data rows only."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_csv))

        assert result[0].total_rows == 3

    def test_csv_preview(self, sample_csv: Path) -> None:
        """CSV preview must contain all data rows when <= 30."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(sample_csv))

        assert len(result[0].preview) == 3


# ---------------------------------------------------------------------------
# Unit tests: edge cases
# ---------------------------------------------------------------------------


class TestParseFileEdgeCases:
    """Edge case tests for parse_file."""

    def test_empty_xlsx_returns_empty_list_or_empty_sheets(
        self, empty_xlsx: Path
    ) -> None:
        """Empty xlsx (no data rows) must not raise; returns list."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(empty_xlsx))

        assert isinstance(result, list)

    def test_empty_xlsx_sheet_has_zero_rows(self, empty_xlsx: Path) -> None:
        """Sheet with no data rows must have total_rows == 0."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(empty_xlsx))

        if result:
            assert result[0].total_rows == 0

    def test_empty_xlsx_sheet_empty_preview(self, empty_xlsx: Path) -> None:
        """Sheet with no data rows must have empty preview list."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(empty_xlsx))

        if result:
            assert result[0].preview == []

    def test_xlsx_with_none_values_in_preview(self, xlsx_with_nulls: Path) -> None:
        """Rows containing None/empty cells must appear in preview without error."""
        from services.xlsx_parser import parse_file

        result = parse_file(str(xlsx_with_nulls))

        assert isinstance(result, list)
        assert len(result) > 0
        preview = result[0].preview
        assert any(None in row.values() for row in preview)

    def test_unsupported_extension_raises_value_error(self, tmp_path: Path) -> None:
        """Passing a .txt file must raise ValueError."""
        from services.xlsx_parser import parse_file

        bad_file = tmp_path / "data.txt"
        bad_file.write_text("not a spreadsheet")

        with pytest.raises(ValueError, match="Unsupported"):
            parse_file(str(bad_file))

    def test_nonexistent_file_raises_file_not_found(self, tmp_path: Path) -> None:
        """Passing a path that does not exist must raise FileNotFoundError."""
        from services.xlsx_parser import parse_file

        with pytest.raises(FileNotFoundError):
            parse_file(str(tmp_path / "missing.xlsx"))


# ---------------------------------------------------------------------------
# Unit tests: build_file_context
# ---------------------------------------------------------------------------


class TestBuildFileContext:
    """Unit tests for build_file_context helper."""

    def test_returns_non_empty_string(self, sample_xlsx: Path) -> None:
        """build_file_context must return a non-empty string."""
        from services.xlsx_parser import build_file_context, parse_file

        sheets = parse_file(str(sample_xlsx))
        ctx = build_file_context(sheets)

        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_contains_sheet_name(self, sample_xlsx: Path) -> None:
        """Output must include the sheet name."""
        from services.xlsx_parser import build_file_context, parse_file

        sheets = parse_file(str(sample_xlsx))
        ctx = build_file_context(sheets)

        assert "Sales" in ctx

    def test_contains_headers(self, sample_xlsx: Path) -> None:
        """Output must list the column headers."""
        from services.xlsx_parser import build_file_context, parse_file

        sheets = parse_file(str(sample_xlsx))
        ctx = build_file_context(sheets)

        for header in ["date", "product", "quantity"]:
            assert header in ctx

    def test_sample_rows_capped_by_max_sample_rows(self, sample_xlsx: Path) -> None:
        """max_sample_rows parameter limits the number of sample rows included."""
        from services.xlsx_parser import build_file_context, parse_file

        sheets = parse_file(str(sample_xlsx))

        ctx_1 = build_file_context(sheets, max_sample_rows=1)
        ctx_3 = build_file_context(sheets, max_sample_rows=3)

        # More sample rows => longer or equal output
        assert len(ctx_3) >= len(ctx_1)

    def test_empty_sheets_returns_string(self) -> None:
        """Empty sheets list must return a (possibly empty) string, not raise."""
        from services.xlsx_parser import build_file_context

        ctx = build_file_context([])

        assert isinstance(ctx, str)

    def test_contains_type_information(self, sample_xlsx: Path) -> None:
        """Output must include type information for columns."""
        from services.xlsx_parser import build_file_context, parse_file

        sheets = parse_file(str(sample_xlsx))
        ctx = build_file_context(sheets)

        # At least one type label must appear
        assert any(t in ctx for t in ["string", "number", "date", "boolean"])
