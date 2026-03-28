"""Tests for run-to-run regression detection in the eval harness.

TDD RED phase: defines the expected API before implementation.

Tests cover:
  - RunComparison dataclass structure
  - compare_runs() logic (regressions, fixes, unchanged, new_cases)
  - Edge cases: empty runs, disjoint architectures, all-same results
  - GET /api/eval/run/{run_id}/compare/{baseline_id} endpoint
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from eval.models import EvalMetrics, EvalResult
from eval.report import RunComparison, compare_runs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _result(
    arch: str,
    case: str,
    success: bool = True,
) -> EvalResult:
    return EvalResult(
        architecture_id=arch,
        test_case_id=case,
        metrics=EvalMetrics(
            success=success,
            total_duration_ms=1000,
            total_tokens=500,
        ),
        agent_log=[],
    )


def _make_summary(results: list[EvalResult]) -> dict:
    """Build a summary.json-compatible dict from a list of EvalResult."""
    return {
        "results": [r.to_dict() for r in results],
        "total_runs": len(results),
    }


# ---------------------------------------------------------------------------
# RunComparison dataclass
# ---------------------------------------------------------------------------


class TestRunComparisonDataclass:
    """RunComparison must be a dataclass with the required fields."""

    def test_has_regressions_field(self) -> None:
        rc = RunComparison(
            regressions=[],
            fixes=[],
            unchanged_pass=0,
            unchanged_fail=0,
            new_cases=[],
        )
        assert rc.regressions == []

    def test_has_fixes_field(self) -> None:
        rc = RunComparison(
            regressions=[],
            fixes=[],
            unchanged_pass=0,
            unchanged_fail=0,
            new_cases=[],
        )
        assert rc.fixes == []

    def test_has_unchanged_pass(self) -> None:
        rc = RunComparison(
            regressions=[],
            fixes=[],
            unchanged_pass=5,
            unchanged_fail=0,
            new_cases=[],
        )
        assert rc.unchanged_pass == 5

    def test_has_unchanged_fail(self) -> None:
        rc = RunComparison(
            regressions=[],
            fixes=[],
            unchanged_pass=0,
            unchanged_fail=3,
            new_cases=[],
        )
        assert rc.unchanged_fail == 3

    def test_has_new_cases(self) -> None:
        rc = RunComparison(
            regressions=[],
            fixes=[],
            unchanged_pass=0,
            unchanged_fail=0,
            new_cases=["c_new"],
        )
        assert rc.new_cases == ["c_new"]

    def test_regression_entry_has_required_keys(self) -> None:
        regression = {"test_case_id": "c1", "architecture_id": "v1"}
        rc = RunComparison(
            regressions=[regression],
            fixes=[],
            unchanged_pass=0,
            unchanged_fail=0,
            new_cases=[],
        )
        entry = rc.regressions[0]
        assert "test_case_id" in entry
        assert "architecture_id" in entry

    def test_fix_entry_has_required_keys(self) -> None:
        fix = {"test_case_id": "c2", "architecture_id": "v2"}
        rc = RunComparison(
            regressions=[],
            fixes=[fix],
            unchanged_pass=0,
            unchanged_fail=0,
            new_cases=[],
        )
        entry = rc.fixes[0]
        assert "test_case_id" in entry
        assert "architecture_id" in entry


# ---------------------------------------------------------------------------
# compare_runs() — happy path
# ---------------------------------------------------------------------------


class TestCompareRunsHappyPath:
    """compare_runs(current, previous) produces correct RunComparison."""

    def test_pass_to_fail_is_regression(self) -> None:
        """A (arch, case) pair that was passing and is now failing is a regression."""
        previous = [_result("v1", "c1", success=True)]
        current = [_result("v1", "c1", success=False)]

        result = compare_runs(current, previous)

        assert len(result.regressions) == 1
        assert result.regressions[0] == {"test_case_id": "c1", "architecture_id": "v1"}

    def test_fail_to_pass_is_fix(self) -> None:
        """A (arch, case) pair that was failing and is now passing is a fix."""
        previous = [_result("v1", "c1", success=False)]
        current = [_result("v1", "c1", success=True)]

        result = compare_runs(current, previous)

        assert len(result.fixes) == 1
        assert result.fixes[0] == {"test_case_id": "c1", "architecture_id": "v1"}

    def test_pass_to_pass_is_unchanged_pass(self) -> None:
        """A pair that stayed passing contributes to unchanged_pass count."""
        previous = [_result("v1", "c1", success=True)]
        current = [_result("v1", "c1", success=True)]

        result = compare_runs(current, previous)

        assert result.unchanged_pass == 1
        assert len(result.regressions) == 0
        assert len(result.fixes) == 0

    def test_fail_to_fail_is_unchanged_fail(self) -> None:
        """A pair that stayed failing contributes to unchanged_fail count."""
        previous = [_result("v1", "c1", success=False)]
        current = [_result("v1", "c1", success=False)]

        result = compare_runs(current, previous)

        assert result.unchanged_fail == 1
        assert len(result.regressions) == 0
        assert len(result.fixes) == 0

    def test_multiple_mixed_results(self) -> None:
        """Multiple pairs produce correct classification across all categories."""
        previous = [
            _result("v1", "c1", success=True),   # stays pass
            _result("v1", "c2", success=False),  # stays fail
            _result("v1", "c3", success=True),   # regression
            _result("v1", "c4", success=False),  # fix
        ]
        current = [
            _result("v1", "c1", success=True),
            _result("v1", "c2", success=False),
            _result("v1", "c3", success=False),  # was pass → now fail
            _result("v1", "c4", success=True),   # was fail → now pass
        ]

        result = compare_runs(current, previous)

        assert result.unchanged_pass == 1
        assert result.unchanged_fail == 1
        assert len(result.regressions) == 1
        assert result.regressions[0] == {"test_case_id": "c3", "architecture_id": "v1"}
        assert len(result.fixes) == 1
        assert result.fixes[0] == {"test_case_id": "c4", "architecture_id": "v1"}

    def test_multiple_architectures(self) -> None:
        """Comparison is done per (architecture_id, test_case_id) pair."""
        previous = [
            _result("v1", "c1", success=True),
            _result("v2", "c1", success=True),
        ]
        current = [
            _result("v1", "c1", success=False),  # v1/c1: regression
            _result("v2", "c1", success=True),   # v2/c1: unchanged pass
        ]

        result = compare_runs(current, previous)

        assert len(result.regressions) == 1
        assert result.regressions[0]["architecture_id"] == "v1"
        assert result.unchanged_pass == 1


# ---------------------------------------------------------------------------
# compare_runs() — new cases
# ---------------------------------------------------------------------------


class TestCompareRunsNewCases:
    """Cases present in current but not in previous are reported as new_cases."""

    def test_new_case_not_in_previous(self) -> None:
        """A test_case_id only in current is listed in new_cases."""
        previous = [_result("v1", "c1", success=True)]
        current = [
            _result("v1", "c1", success=True),
            _result("v1", "c_new", success=True),
        ]

        result = compare_runs(current, previous)

        assert "c_new" in result.new_cases

    def test_new_case_not_counted_as_regression_or_fix(self) -> None:
        """New cases are excluded from regression/fix/unchanged counts."""
        previous = [_result("v1", "c1", success=True)]
        current = [
            _result("v1", "c1", success=True),
            _result("v1", "c_brand_new", success=False),
        ]

        result = compare_runs(current, previous)

        assert len(result.regressions) == 0
        assert len(result.fixes) == 0
        assert "c_brand_new" in result.new_cases

    def test_no_new_cases_when_same_cases(self) -> None:
        """When the same cases exist in both runs, new_cases is empty."""
        previous = [_result("v1", "c1", success=True)]
        current = [_result("v1", "c1", success=False)]

        result = compare_runs(current, previous)

        assert result.new_cases == []

    def test_new_case_with_new_architecture(self) -> None:
        """A new (arch, case) pair where case exists in previous (but not same arch) is new."""
        previous = [_result("v1", "c1", success=True)]
        current = [
            _result("v1", "c1", success=True),
            _result("v2", "c1", success=True),  # v2 is a new arch — (v2, c1) pair is new
        ]

        result = compare_runs(current, previous)

        # (v2, c1) was not in previous so this is a new pair
        # c1 is NOT a new case (it existed in previous under v1)
        assert result.unchanged_pass == 1  # (v1, c1)


# ---------------------------------------------------------------------------
# compare_runs() — edge cases
# ---------------------------------------------------------------------------


class TestCompareRunsEdgeCases:
    """Edge cases: empty inputs, identical runs, disjoint architectures."""

    def test_empty_current_and_previous(self) -> None:
        result = compare_runs([], [])
        assert result.regressions == []
        assert result.fixes == []
        assert result.unchanged_pass == 0
        assert result.unchanged_fail == 0
        assert result.new_cases == []

    def test_empty_previous(self) -> None:
        """All cases in current are new when previous is empty."""
        current = [_result("v1", "c1", success=True)]
        result = compare_runs(current, [])
        assert "c1" in result.new_cases
        assert len(result.regressions) == 0
        assert len(result.fixes) == 0

    def test_empty_current(self) -> None:
        """Empty current with non-empty previous yields all zeros."""
        previous = [_result("v1", "c1", success=True)]
        result = compare_runs([], previous)
        assert result.regressions == []
        assert result.fixes == []
        assert result.unchanged_pass == 0
        assert result.unchanged_fail == 0
        assert result.new_cases == []

    def test_no_change_large_run(self) -> None:
        """When all results are identical, all go to unchanged counts."""
        archs = ["v1", "v2"]
        cases = ["c1", "c2", "c3"]
        results = [_result(a, c, success=True) for a in archs for c in cases]

        comparison = compare_runs(results, results)

        assert len(comparison.regressions) == 0
        assert len(comparison.fixes) == 0
        assert comparison.unchanged_pass == 6
        assert comparison.unchanged_fail == 0

    def test_all_regressions(self) -> None:
        """When everything flips from pass to fail."""
        previous = [_result("v1", "c1", success=True), _result("v1", "c2", success=True)]
        current = [_result("v1", "c1", success=False), _result("v1", "c2", success=False)]

        result = compare_runs(current, previous)

        assert len(result.regressions) == 2
        assert result.unchanged_pass == 0

    def test_all_fixes(self) -> None:
        """When everything flips from fail to pass."""
        previous = [_result("v1", "c1", success=False), _result("v1", "c2", success=False)]
        current = [_result("v1", "c1", success=True), _result("v1", "c2", success=True)]

        result = compare_runs(current, previous)

        assert len(result.fixes) == 2
        assert result.unchanged_fail == 0

    def test_disjoint_architectures(self) -> None:
        """Previous used v1; current uses v2 — all current results are new pairs."""
        previous = [_result("v1", "c1", success=True)]
        current = [_result("v2", "c1", success=True)]

        result = compare_runs(current, previous)

        # (v2, c1) was never in previous
        assert len(result.regressions) == 0
        assert len(result.fixes) == 0
        assert result.unchanged_pass == 0

    def test_duplicate_pairs_in_current_last_wins(self) -> None:
        """If the same (arch, case) appears twice in current, the last value is used."""
        previous = [_result("v1", "c1", success=True)]
        current = [
            _result("v1", "c1", success=False),  # first entry
            _result("v1", "c1", success=True),   # second entry — should win
        ]

        result = compare_runs(current, previous)

        # last value is pass, previous was pass → unchanged
        assert result.unchanged_pass == 1
        assert len(result.regressions) == 0


# ---------------------------------------------------------------------------
# API endpoint: GET /api/eval/run/{run_id}/compare/{baseline_id}
# ---------------------------------------------------------------------------


@pytest.fixture
def eval_results_dir(tmp_path: Path) -> Path:
    """Temporary directory acting as _RESULTS_DIR."""
    d = tmp_path / "eval" / "results"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def compare_client(eval_results_dir: Path) -> TestClient:
    """TestClient with _RESULTS_DIR patched to the tmp dir."""
    from core.config import Settings
    from core.deps import get_settings
    from main import app

    settings = Settings(
        openai_api_key="test-key",
        openai_model="gpt-4o",
        cors_origins="http://localhost:5173",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    with patch("routers.eval._RESULTS_DIR", eval_results_dir):
        with TestClient(app) as client:
            yield client

    app.dependency_overrides.clear()


def _write_run(results_dir: Path, run_id: str, results: list[EvalResult]) -> None:
    """Write a run's summary.json to the given results directory."""
    run_dir = results_dir / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "results": [r.to_dict() for r in results],
        "total_runs": len(results),
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False),
        encoding="utf-8",
    )


class TestCompareEndpoint:
    """GET /api/eval/run/{run_id}/compare/{baseline_id}"""

    def test_compare_returns_200(
        self, compare_client: TestClient, eval_results_dir: Path
    ) -> None:
        _write_run(eval_results_dir, "run_a", [_result("v1", "c1", success=True)])
        _write_run(eval_results_dir, "run_b", [_result("v1", "c1", success=True)])

        resp = compare_client.get("/api/eval/run/run_a/compare/run_b")
        assert resp.status_code == 200

    def test_compare_response_has_required_keys(
        self, compare_client: TestClient, eval_results_dir: Path
    ) -> None:
        _write_run(eval_results_dir, "run_a", [_result("v1", "c1", success=True)])
        _write_run(eval_results_dir, "run_b", [_result("v1", "c1", success=True)])

        body = compare_client.get("/api/eval/run/run_a/compare/run_b").json()

        assert "regressions" in body
        assert "fixes" in body
        assert "unchanged_pass" in body
        assert "unchanged_fail" in body
        assert "new_cases" in body

    def test_compare_detects_regression(
        self, compare_client: TestClient, eval_results_dir: Path
    ) -> None:
        """run_a has a case failing that was passing in run_b (baseline)."""
        _write_run(eval_results_dir, "run_a", [_result("v1", "c1", success=False)])
        _write_run(eval_results_dir, "run_b", [_result("v1", "c1", success=True)])

        body = compare_client.get("/api/eval/run/run_a/compare/run_b").json()

        assert len(body["regressions"]) == 1
        assert body["regressions"][0]["test_case_id"] == "c1"
        assert body["regressions"][0]["architecture_id"] == "v1"

    def test_compare_detects_fix(
        self, compare_client: TestClient, eval_results_dir: Path
    ) -> None:
        """run_a has a case passing that was failing in run_b (baseline)."""
        _write_run(eval_results_dir, "run_a", [_result("v1", "c1", success=True)])
        _write_run(eval_results_dir, "run_b", [_result("v1", "c1", success=False)])

        body = compare_client.get("/api/eval/run/run_a/compare/run_b").json()

        assert len(body["fixes"]) == 1
        assert body["fixes"][0]["test_case_id"] == "c1"

    def test_compare_unchanged_pass_count(
        self, compare_client: TestClient, eval_results_dir: Path
    ) -> None:
        _write_run(eval_results_dir, "run_a", [
            _result("v1", "c1", success=True),
            _result("v1", "c2", success=True),
        ])
        _write_run(eval_results_dir, "run_b", [
            _result("v1", "c1", success=True),
            _result("v1", "c2", success=True),
        ])

        body = compare_client.get("/api/eval/run/run_a/compare/run_b").json()

        assert body["unchanged_pass"] == 2

    def test_compare_new_cases(
        self, compare_client: TestClient, eval_results_dir: Path
    ) -> None:
        """Cases in run_a that weren't in run_b appear in new_cases."""
        _write_run(eval_results_dir, "run_a", [
            _result("v1", "c1", success=True),
            _result("v1", "c_brand_new", success=True),
        ])
        _write_run(eval_results_dir, "run_b", [_result("v1", "c1", success=True)])

        body = compare_client.get("/api/eval/run/run_a/compare/run_b").json()

        assert "c_brand_new" in body["new_cases"]

    def test_compare_current_run_not_found_returns_404(
        self, compare_client: TestClient, eval_results_dir: Path
    ) -> None:
        _write_run(eval_results_dir, "run_b", [_result("v1", "c1", success=True)])

        resp = compare_client.get("/api/eval/run/nonexistent/compare/run_b")
        assert resp.status_code == 404

    def test_compare_baseline_not_found_returns_404(
        self, compare_client: TestClient, eval_results_dir: Path
    ) -> None:
        _write_run(eval_results_dir, "run_a", [_result("v1", "c1", success=True)])

        resp = compare_client.get("/api/eval/run/run_a/compare/nonexistent_baseline")
        assert resp.status_code == 404

    def test_compare_both_not_found_returns_404(
        self, compare_client: TestClient, eval_results_dir: Path
    ) -> None:
        resp = compare_client.get("/api/eval/run/nope/compare/also_nope")
        assert resp.status_code == 404

    def test_compare_empty_runs(
        self, compare_client: TestClient, eval_results_dir: Path
    ) -> None:
        """Both runs exist but have zero results — returns all zeros."""
        _write_run(eval_results_dir, "run_a", [])
        _write_run(eval_results_dir, "run_b", [])

        body = compare_client.get("/api/eval/run/run_a/compare/run_b").json()

        assert body["regressions"] == []
        assert body["fixes"] == []
        assert body["unchanged_pass"] == 0
        assert body["unchanged_fail"] == 0
        assert body["new_cases"] == []

    def test_compare_multiple_architectures_and_cases(
        self, compare_client: TestClient, eval_results_dir: Path
    ) -> None:
        """Full multi-arch, multi-case scenario."""
        current = [
            _result("v1", "c1", success=True),
            _result("v1", "c2", success=False),  # regression (was True)
            _result("v2", "c1", success=True),
            _result("v2", "c2", success=True),   # fix (was False)
        ]
        baseline = [
            _result("v1", "c1", success=True),
            _result("v1", "c2", success=True),
            _result("v2", "c1", success=True),
            _result("v2", "c2", success=False),
        ]
        _write_run(eval_results_dir, "run_new", current)
        _write_run(eval_results_dir, "run_old", baseline)

        body = compare_client.get("/api/eval/run/run_new/compare/run_old").json()

        assert len(body["regressions"]) == 1
        assert body["regressions"][0] == {"test_case_id": "c2", "architecture_id": "v1"}
        assert len(body["fixes"]) == 1
        assert body["fixes"][0] == {"test_case_id": "c2", "architecture_id": "v2"}
        assert body["unchanged_pass"] == 2
        assert body["unchanged_fail"] == 0
