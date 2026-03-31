"""Tests for eval.report — comparison report generation.

TDD RED phase: defines the expected report API.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.models import EvalMetrics, EvalResult
from eval.report import EvalReport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _result(
    arch: str,
    case: str,
    success: bool = True,
    tokens: int = 1000,
    duration_ms: int = 5000,
    retries: int = 0,
) -> EvalResult:
    return EvalResult(
        architecture_id=arch,
        test_case_id=case,
        metrics=EvalMetrics(
            success=success,
            total_tokens=tokens,
            total_duration_ms=duration_ms,
            retry_count=retries,
            code_executes=success,
        ),
        agent_log=[],
        generated_code="print(1)" if success else None,
    )


@pytest.fixture
def sample_results() -> list[EvalResult]:
    return [
        # v1: 2 successes, 1 failure
        _result("v1", "c1", success=True, tokens=4000, duration_ms=20000, retries=0),
        _result("v1", "c2", success=True, tokens=5000, duration_ms=30000, retries=1),
        _result("v1", "c3", success=False, tokens=6000, duration_ms=40000, retries=3),
        # v2: 3 successes, cheaper
        _result("v2", "c1", success=True, tokens=2000, duration_ms=10000, retries=0),
        _result("v2", "c2", success=True, tokens=2500, duration_ms=12000, retries=0),
        _result("v2", "c3", success=True, tokens=3000, duration_ms=15000, retries=1),
    ]


# ---------------------------------------------------------------------------
# Report creation
# ---------------------------------------------------------------------------


class TestEvalReport:
    def test_create_from_results(self, sample_results: list[EvalResult]) -> None:
        report = EvalReport(sample_results)
        assert report.architecture_ids == ["v1", "v2"]
        assert report.test_case_ids == ["c1", "c2", "c3"]

    def test_summary_table(self, sample_results: list[EvalResult]) -> None:
        """summary_table returns per-architecture aggregated metrics."""
        report = EvalReport(sample_results)
        table = report.summary_table()

        assert len(table) == 2  # 2 architectures

        v1 = table["v1"]
        assert v1["success_rate"] == pytest.approx(2 / 3, rel=1e-2)
        assert v1["avg_tokens"] == pytest.approx(5000, rel=1e-2)
        assert v1["avg_duration_ms"] == pytest.approx(30000, rel=1e-2)
        assert v1["avg_retries"] == pytest.approx(4 / 3, rel=1e-2)
        assert v1["total_runs"] == 3

        v2 = table["v2"]
        assert v2["success_rate"] == pytest.approx(1.0)
        assert v2["avg_tokens"] == pytest.approx(2500, rel=1e-2)

    def test_comparison_matrix(self, sample_results: list[EvalResult]) -> None:
        """comparison_matrix shows per test case success by architecture."""
        report = EvalReport(sample_results)
        matrix = report.comparison_matrix()

        # matrix[case_id][arch_id] = success
        assert matrix["c1"]["v1"] is True
        assert matrix["c1"]["v2"] is True
        assert matrix["c3"]["v1"] is False
        assert matrix["c3"]["v2"] is True

    def test_best_architecture(self, sample_results: list[EvalResult]) -> None:
        """best_architecture returns the arch with highest success rate."""
        report = EvalReport(sample_results)
        best = report.best_architecture()
        assert best == "v2"

    def test_best_architecture_tiebreak_by_cost(self) -> None:
        """When success rates tie, prefer lower token usage."""
        results = [
            _result("a", "c1", success=True, tokens=5000, duration_ms=1000),
            _result("b", "c1", success=True, tokens=2000, duration_ms=1000),
        ]
        report = EvalReport(results)
        best = report.best_architecture()
        assert best == "b"

    def test_to_markdown(self, sample_results: list[EvalResult]) -> None:
        """to_markdown returns a formatted comparison table."""
        report = EvalReport(sample_results)
        md = report.to_markdown()

        assert "v1" in md
        assert "v2" in md
        assert "success" in md.lower() or "成功率" in md

    def test_to_dict(self, sample_results: list[EvalResult]) -> None:
        report = EvalReport(sample_results)
        d = report.to_dict()

        assert "summary" in d
        assert "comparison_matrix" in d
        assert "best_architecture" in d
        assert d["best_architecture"] == "v2"

    def test_save_report(self, sample_results: list[EvalResult], tmp_path: Path) -> None:
        report = EvalReport(sample_results)
        report.save(tmp_path / "report.json")

        assert (tmp_path / "report.json").exists()
        loaded = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert loaded["best_architecture"] == "v2"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEvalReportEdgeCases:
    def test_empty_results(self) -> None:
        report = EvalReport([])
        assert report.architecture_ids == []
        table = report.summary_table()
        assert table == {}

    def test_single_result(self) -> None:
        results = [_result("v1", "c1")]
        report = EvalReport(results)
        assert report.best_architecture() == "v1"

    def test_result_details_with_scores(self) -> None:
        """result_details returns quality/llm scores and output_files per case/arch."""
        results = [
            EvalResult(
                architecture_id="v1",
                test_case_id="c1",
                metrics=EvalMetrics(
                    success=False,
                    total_duration_ms=1000,
                    quality_score=0.71,
                    quality_details={"missing_sheets": ["Sheet2"], "extra_sheets": [], "error": None},
                    llm_eval_score=6.7,
                    llm_eval_details={"semantic_correctness": 7.0, "reasoning": "missing data"},
                ),
                agent_log=[],
                output_files=["/outputs/abc/result.xlsx"],
            ),
        ]
        report = EvalReport(results)
        details = report.result_details()

        assert "c1" in details
        assert "v1" in details["c1"]
        d = details["c1"]["v1"]
        assert d["quality_score"] == 0.71
        assert d["llm_eval_score"] == 6.7
        assert d["quality_details"]["missing_sheets"] == ["Sheet2"]
        assert d["llm_eval_details"]["reasoning"] == "missing data"
        assert d["output_files"] == ["/outputs/abc/result.xlsx"]

    def test_to_dict_includes_result_details(self) -> None:
        results = [
            EvalResult(
                architecture_id="v1",
                test_case_id="c1",
                metrics=EvalMetrics(success=True, total_duration_ms=1000, quality_score=0.95),
                agent_log=[],
                output_files=["/outputs/xyz/out.xlsx"],
            ),
        ]
        report = EvalReport(results)
        d = report.to_dict()
        assert "result_details" in d
        assert d["result_details"]["c1"]["v1"]["output_files"] == ["/outputs/xyz/out.xlsx"]

    def test_all_failures(self) -> None:
        results = [
            _result("v1", "c1", success=False, tokens=1000, duration_ms=5000),
            _result("v2", "c1", success=False, tokens=500, duration_ms=3000),
        ]
        report = EvalReport(results)
        # Both fail; prefer cheaper
        best = report.best_architecture()
        assert best == "v2"
