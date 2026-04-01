"""Excel output comparison engine.

Compares an actual Excel/CSV output file against an expected file
and produces a structured quality score (0.0-1.0).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Scoring weights
_WEIGHT_CELL_VALUE = 0.60
_WEIGHT_STRUCTURE = 0.25
_WEIGHT_HEADER = 0.15


@dataclass(frozen=True)
class SheetComparison:
    """Comparison result for a single sheet."""

    sheet_name: str
    header_score: float
    structure_score: float
    cell_value_score: float
    row_count_expected: int
    row_count_actual: int
    col_count_expected: int
    col_count_actual: int
    mismatched_cells: int
    total_cells: int


@dataclass(frozen=True)
class ComparisonResult:
    """Overall comparison result across all sheets."""

    overall_score: float
    sheet_results: tuple[SheetComparison, ...]
    missing_sheets: tuple[str, ...]
    extra_sheets: tuple[str, ...]
    error: str | None


def _load_sheets(path: str) -> dict[str, pd.DataFrame]:
    """Load all sheets from an Excel or CSV file into DataFrames."""
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == ".csv":
        df = pd.read_csv(path, dtype=str)
        return {"Sheet1": df}

    # .xlsx / .xls
    xls = pd.ExcelFile(path)
    return {name: pd.read_excel(xls, sheet_name=name, dtype=str) for name in xls.sheet_names}


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two string sets."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _compare_headers(actual_cols: list[str], expected_cols: list[str]) -> float:
    """Compare column headers using Jaccard similarity (case-insensitive)."""
    actual_set = {c.strip().lower() for c in actual_cols}
    expected_set = {c.strip().lower() for c in expected_cols}
    return _jaccard_similarity(actual_set, expected_set)


def _compare_structure(actual_df: pd.DataFrame, expected_df: pd.DataFrame) -> float:
    """Compare row and column counts.

    Returns a score 0.0-1.0 based on min/max ratio of rows and columns.
    """
    actual_rows, actual_cols = actual_df.shape
    expected_rows, expected_cols = expected_df.shape

    if expected_rows == 0 and actual_rows == 0:
        row_score = 1.0
    elif expected_rows == 0 or actual_rows == 0:
        row_score = 0.0
    else:
        row_score = min(actual_rows, expected_rows) / max(actual_rows, expected_rows)

    if expected_cols == 0 and actual_cols == 0:
        col_score = 1.0
    elif expected_cols == 0 or actual_cols == 0:
        col_score = 0.0
    else:
        col_score = min(actual_cols, expected_cols) / max(actual_cols, expected_cols)

    return 0.5 * row_score + 0.5 * col_score


def _values_match(actual_val: str | None, expected_val: str | None, tolerance: float) -> bool:
    """Compare two cell values with numeric tolerance.

    Both values are strings (loaded with dtype=str). We attempt numeric
    comparison first, then fall back to case-insensitive string comparison.
    """
    # Both missing
    a_missing = actual_val is None or (isinstance(actual_val, float) and math.isnan(actual_val)) or str(actual_val).strip() == ""
    e_missing = expected_val is None or (isinstance(expected_val, float) and math.isnan(expected_val)) or str(expected_val).strip() == ""

    if a_missing and e_missing:
        return True
    if a_missing or e_missing:
        return False

    a_str = str(actual_val).strip()
    e_str = str(expected_val).strip()

    # Try numeric comparison
    try:
        a_num = float(a_str.replace(",", ""))
        e_num = float(e_str.replace(",", ""))
        if e_num == 0.0:
            return math.isclose(a_num, e_num, abs_tol=tolerance)
        return math.isclose(a_num, e_num, rel_tol=tolerance)
    except (ValueError, TypeError):
        pass

    # String comparison (case-insensitive)
    return a_str.lower() == e_str.lower()


def _compare_cell_values(
    actual_df: pd.DataFrame,
    expected_df: pd.DataFrame,
    tolerance: float,
) -> tuple[float, int, int]:
    """Compare cell values over the intersection of columns.

    Returns (score, mismatched_count, total_count).
    """
    actual_cols_lower = {c.strip().lower(): c for c in actual_df.columns}
    expected_cols_lower = {c.strip().lower(): c for c in expected_df.columns}

    common_keys = set(actual_cols_lower.keys()) & set(expected_cols_lower.keys())
    if not common_keys:
        return (0.0, 0, 0)

    # Use the smaller row count as comparison range
    row_count = min(len(actual_df), len(expected_df))
    if row_count == 0:
        return (1.0, 0, 0) if len(actual_df) == 0 and len(expected_df) == 0 else (0.0, 0, 0)

    total = row_count * len(common_keys)
    mismatched = 0

    for key in common_keys:
        a_col = actual_cols_lower[key]
        e_col = expected_cols_lower[key]
        for i in range(row_count):
            a_val = actual_df.iloc[i][a_col]
            e_val = expected_df.iloc[i][e_col]
            if not _values_match(a_val, e_val, tolerance):
                mismatched += 1

    score = (total - mismatched) / total if total > 0 else 0.0
    return (score, mismatched, total)


def _compare_sheet(
    actual_df: pd.DataFrame,
    expected_df: pd.DataFrame,
    sheet_name: str,
    tolerance: float,
) -> SheetComparison:
    """Compare a single sheet pair."""
    header_score = _compare_headers(
        list(actual_df.columns),
        list(expected_df.columns),
    )
    structure_score = _compare_structure(actual_df, expected_df)
    cell_score, mismatched, total = _compare_cell_values(actual_df, expected_df, tolerance)

    return SheetComparison(
        sheet_name=sheet_name,
        header_score=header_score,
        structure_score=structure_score,
        cell_value_score=cell_score,
        row_count_expected=len(expected_df),
        row_count_actual=len(actual_df),
        col_count_expected=len(expected_df.columns),
        col_count_actual=len(actual_df.columns),
        mismatched_cells=mismatched,
        total_cells=total,
    )


def compare_excel_files(
    actual_path: str,
    expected_path: str,
    tolerance: float = 1e-6,
) -> ComparisonResult:
    """Compare actual output against expected output.

    Args:
        actual_path: Path to the actual output file (.xlsx, .xls, .csv).
        expected_path: Path to the expected output file.
        tolerance: Relative tolerance for numeric comparison.

    Returns:
        Frozen ComparisonResult with overall_score (0.0-1.0) and per-sheet details.
    """
    try:
        actual_sheets = _load_sheets(actual_path)
        expected_sheets = _load_sheets(expected_path)
    except Exception as exc:
        logger.warning("Failed to load files for comparison", exc_info=True)
        return ComparisonResult(
            overall_score=0.0,
            sheet_results=(),
            missing_sheets=(),
            extra_sheets=(),
            error=str(exc),
        )

    actual_names = set(actual_sheets.keys())
    expected_names = set(expected_sheets.keys())

    missing = tuple(sorted(expected_names - actual_names))
    extra = tuple(sorted(actual_names - expected_names))
    common = sorted(actual_names & expected_names)

    sheet_results: list[SheetComparison] = []
    for name in common:
        result = _compare_sheet(actual_sheets[name], expected_sheets[name], name, tolerance)
        sheet_results.append(result)

    # Compute overall score
    if not expected_names:
        overall = 1.0 if not actual_names else 0.0
    elif not common:
        overall = 0.0
    else:
        sheet_scores = [
            _WEIGHT_CELL_VALUE * r.cell_value_score
            + _WEIGHT_STRUCTURE * r.structure_score
            + _WEIGHT_HEADER * r.header_score
            for r in sheet_results
        ]
        avg_sheet_score = sum(sheet_scores) / len(sheet_scores)
        # Penalize for missing sheets
        coverage = len(common) / len(expected_names)
        overall = avg_sheet_score * coverage

    return ComparisonResult(
        overall_score=round(overall, 4),
        sheet_results=tuple(sheet_results),
        missing_sheets=missing,
        extra_sheets=extra,
        error=None,
    )


def find_best_output_match(output_files: list[str], expected_path: str) -> str | None:
    """Find the output file that best matches the expected file.

    Strategy:
    1. If only one output file exists, use it.
    2. Match by extension first, then by filename similarity.

    Args:
        output_files: List of absolute paths to output files.
        expected_path: Path to the expected output file.

    Returns:
        Path to the best matching output file, or None if no match found.
    """
    if not output_files:
        return None

    if len(output_files) == 1:
        return output_files[0]

    expected_ext = Path(expected_path).suffix.lower()
    expected_stem = Path(expected_path).stem.lower()

    # Filter by extension
    same_ext = [f for f in output_files if Path(f).suffix.lower() == expected_ext]
    candidates = same_ext if same_ext else output_files

    if len(candidates) == 1:
        return candidates[0]

    # Pick by filename similarity
    best_path = None
    best_ratio = -1.0
    for f in candidates:
        ratio = SequenceMatcher(None, Path(f).stem.lower(), expected_stem).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_path = f

    return best_path
