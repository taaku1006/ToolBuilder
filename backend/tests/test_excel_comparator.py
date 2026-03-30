"""Tests for the Excel comparison engine."""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from services.excel_comparator import (
    ComparisonResult,
    SheetComparison,
    compare_excel_files,
    find_best_output_match,
)


@pytest.fixture()
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _write_xlsx(path: Path, sheets: dict[str, pd.DataFrame]) -> str:
    """Helper: write a multi-sheet Excel file and return its path."""
    with pd.ExcelWriter(str(path), engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return str(path)


def _write_csv(path: Path, df: pd.DataFrame) -> str:
    df.to_csv(str(path), index=False)
    return str(path)


# ---------------------------------------------------------------------------
# Identical files
# ---------------------------------------------------------------------------


class TestIdenticalFiles:
    def test_identical_xlsx(self, tmp_dir: Path):
        df = pd.DataFrame({"Name": ["Alice", "Bob"], "Score": [90, 85]})
        actual = _write_xlsx(tmp_dir / "actual.xlsx", {"Sheet1": df})
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {"Sheet1": df})

        result = compare_excel_files(actual, expected)

        assert result.error is None
        assert result.overall_score == 1.0
        assert len(result.missing_sheets) == 0
        assert len(result.extra_sheets) == 0
        assert len(result.sheet_results) == 1
        assert result.sheet_results[0].mismatched_cells == 0

    def test_identical_csv(self, tmp_dir: Path):
        df = pd.DataFrame({"A": ["1", "2"], "B": ["x", "y"]})
        actual = _write_csv(tmp_dir / "actual.csv", df)
        expected = _write_csv(tmp_dir / "expected.csv", df)

        result = compare_excel_files(actual, expected)

        assert result.error is None
        assert result.overall_score == 1.0

    def test_identical_multi_sheet(self, tmp_dir: Path):
        sheets = {
            "Sales": pd.DataFrame({"Product": ["A"], "Amount": [100]}),
            "Costs": pd.DataFrame({"Item": ["X"], "Cost": [50]}),
        }
        actual = _write_xlsx(tmp_dir / "actual.xlsx", sheets)
        expected = _write_xlsx(tmp_dir / "expected.xlsx", sheets)

        result = compare_excel_files(actual, expected)

        assert result.overall_score == 1.0
        assert len(result.sheet_results) == 2


# ---------------------------------------------------------------------------
# Completely different files
# ---------------------------------------------------------------------------


class TestDifferentFiles:
    def test_different_data(self, tmp_dir: Path):
        actual_df = pd.DataFrame({"X": ["a", "b"], "Y": ["c", "d"]})
        expected_df = pd.DataFrame({"P": ["1", "2"], "Q": ["3", "4"]})

        actual = _write_xlsx(tmp_dir / "actual.xlsx", {"Sheet1": actual_df})
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {"Sheet1": expected_df})

        result = compare_excel_files(actual, expected)

        assert result.overall_score < 0.3

    def test_no_common_sheets(self, tmp_dir: Path):
        actual = _write_xlsx(tmp_dir / "actual.xlsx", {"A": pd.DataFrame({"x": [1]})})
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {"B": pd.DataFrame({"y": [2]})})

        result = compare_excel_files(actual, expected)

        assert result.overall_score == 0.0
        assert result.missing_sheets == ("B",)
        assert result.extra_sheets == ("A",)


# ---------------------------------------------------------------------------
# Numeric tolerance
# ---------------------------------------------------------------------------


class TestNumericTolerance:
    def test_close_values_match(self, tmp_dir: Path):
        actual_df = pd.DataFrame({"Value": ["1.00000001"]})
        expected_df = pd.DataFrame({"Value": ["1.0"]})

        actual = _write_xlsx(tmp_dir / "actual.xlsx", {"Sheet1": actual_df})
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {"Sheet1": expected_df})

        result = compare_excel_files(actual, expected, tolerance=1e-6)

        assert result.sheet_results[0].cell_value_score == 1.0

    def test_far_values_mismatch(self, tmp_dir: Path):
        actual_df = pd.DataFrame({"Value": ["100"]})
        expected_df = pd.DataFrame({"Value": ["200"]})

        actual = _write_xlsx(tmp_dir / "actual.xlsx", {"Sheet1": actual_df})
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {"Sheet1": expected_df})

        result = compare_excel_files(actual, expected)

        assert result.sheet_results[0].cell_value_score == 0.0
        assert result.sheet_results[0].mismatched_cells == 1


# ---------------------------------------------------------------------------
# Missing / extra sheets
# ---------------------------------------------------------------------------


class TestSheetMismatch:
    def test_missing_sheet_penalizes_score(self, tmp_dir: Path):
        actual = _write_xlsx(tmp_dir / "actual.xlsx", {
            "Sheet1": pd.DataFrame({"A": [1]}),
        })
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {
            "Sheet1": pd.DataFrame({"A": [1]}),
            "Sheet2": pd.DataFrame({"B": [2]}),
        })

        result = compare_excel_files(actual, expected)

        # Sheet1 matches perfectly but coverage = 1/2 = 0.5
        assert result.overall_score <= 0.5
        assert result.missing_sheets == ("Sheet2",)

    def test_extra_sheets_do_not_inflate_score(self, tmp_dir: Path):
        actual = _write_xlsx(tmp_dir / "actual.xlsx", {
            "Sheet1": pd.DataFrame({"A": [1]}),
            "Extra": pd.DataFrame({"C": [3]}),
        })
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {
            "Sheet1": pd.DataFrame({"A": [1]}),
        })

        result = compare_excel_files(actual, expected)

        # All expected sheets matched, coverage = 1.0
        assert result.overall_score == 1.0
        assert result.extra_sheets == ("Extra",)


# ---------------------------------------------------------------------------
# Different row counts
# ---------------------------------------------------------------------------


class TestDifferentRowCounts:
    def test_partial_row_match(self, tmp_dir: Path):
        actual_df = pd.DataFrame({"A": ["1", "2"]})
        expected_df = pd.DataFrame({"A": ["1", "2", "3", "4"]})

        actual = _write_xlsx(tmp_dir / "actual.xlsx", {"Sheet1": actual_df})
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {"Sheet1": expected_df})

        result = compare_excel_files(actual, expected)

        # Cell values match for rows present, but structure score is penalized
        sheet = result.sheet_results[0]
        assert sheet.cell_value_score == 1.0  # first 2 rows match
        assert sheet.structure_score < 1.0    # 2/4 rows
        assert result.overall_score < 1.0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_nonexistent_file(self, tmp_dir: Path):
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {"S": pd.DataFrame({"A": [1]})})

        result = compare_excel_files("/nonexistent.xlsx", expected)

        assert result.overall_score == 0.0
        assert result.error is not None


# ---------------------------------------------------------------------------
# find_best_output_match
# ---------------------------------------------------------------------------


class TestFindBestOutputMatch:
    def test_single_file(self):
        assert find_best_output_match(["/out/result.xlsx"], "/exp/expected.xlsx") == "/out/result.xlsx"

    def test_no_files(self):
        assert find_best_output_match([], "/exp/expected.xlsx") is None

    def test_matches_extension(self):
        files = ["/out/data.csv", "/out/report.xlsx"]
        assert find_best_output_match(files, "/exp/report.xlsx") == "/out/report.xlsx"

    def test_matches_filename_similarity(self):
        files = ["/out/summary_report.xlsx", "/out/raw_data.xlsx"]
        result = find_best_output_match(files, "/exp/summary_report_expected.xlsx")
        assert result == "/out/summary_report.xlsx"


# ---------------------------------------------------------------------------
# Frozen dataclass invariants
# ---------------------------------------------------------------------------


class TestDataclassInvariants:
    def test_sheet_comparison_frozen(self):
        sc = SheetComparison(
            sheet_name="S", header_score=1.0, structure_score=1.0,
            cell_value_score=1.0, row_count_expected=1, row_count_actual=1,
            col_count_expected=1, col_count_actual=1, mismatched_cells=0, total_cells=1,
        )
        with pytest.raises(AttributeError):
            sc.header_score = 0.5  # type: ignore[misc]

    def test_comparison_result_frozen(self):
        cr = ComparisonResult(
            overall_score=0.5, sheet_results=(), missing_sheets=(), extra_sheets=(), error=None,
        )
        with pytest.raises(AttributeError):
            cr.overall_score = 0.0  # type: ignore[misc]
