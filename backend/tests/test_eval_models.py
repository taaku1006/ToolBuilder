"""Tests for eval.models — architecture config, test case, and result dataclasses.

TDD RED phase: these tests define the expected API before implementation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.models import (
    ArchitectureConfig,
    EvalMetrics,
    EvalResult,
    TestCase,
    load_architecture,
    load_test_case,
)


# ---------------------------------------------------------------------------
# ArchitectureConfig
# ---------------------------------------------------------------------------


class TestArchitectureConfig:
    """ArchitectureConfig defines which phases/settings to use."""

    def test_default_baseline(self) -> None:
        cfg = ArchitectureConfig(id="v1_baseline")
        assert cfg.id == "v1_baseline"
        assert cfg.phases == ["A", "B", "P", "C", "D", "F", "G", "E"]
        assert cfg.model == "gpt-4o"
        assert cfg.debug_retry_limit == 3
        assert cfg.temperature == 0.2
        assert cfg.description == ""

    def test_custom_phases(self) -> None:
        cfg = ArchitectureConfig(
            id="v2_skip_b",
            phases=["A", "C", "D", "E"],
            description="Skip reflection phase",
        )
        assert cfg.phases == ["A", "C", "D", "E"]
        assert cfg.description == "Skip reflection phase"

    def test_minimal_phases(self) -> None:
        cfg = ArchitectureConfig(id="v3_minimal", phases=["C", "D"])
        assert "A" not in cfg.phases
        assert "B" not in cfg.phases
        assert "E" not in cfg.phases

    def test_custom_model_and_retries(self) -> None:
        cfg = ArchitectureConfig(
            id="v4",
            model="gpt-4o-mini",
            debug_retry_limit=5,
            temperature=0.0,
        )
        assert cfg.model == "gpt-4o-mini"
        assert cfg.debug_retry_limit == 5
        assert cfg.temperature == 0.0

    def test_frozen(self) -> None:
        cfg = ArchitectureConfig(id="v1")
        with pytest.raises(AttributeError):
            cfg.id = "changed"  # type: ignore[misc]

    def test_to_settings_overrides_baseline(self) -> None:
        """to_settings_overrides returns a dict that can patch Settings."""
        cfg = ArchitectureConfig(id="v1_baseline")
        overrides = cfg.to_settings_overrides()
        assert overrides["reflection_enabled"] is True
        assert overrides["debug_loop_enabled"] is True
        assert overrides["skills_enabled"] is True
        assert overrides["openai_model"] == "gpt-4o"
        assert overrides["debug_retry_limit"] == 3

    def test_to_settings_overrides_no_reflection(self) -> None:
        """Phases without A/B disable reflection."""
        cfg = ArchitectureConfig(id="v3", phases=["C", "D"])
        overrides = cfg.to_settings_overrides()
        assert overrides["reflection_enabled"] is False
        assert overrides["debug_loop_enabled"] is True
        assert overrides["skills_enabled"] is False

    def test_to_settings_overrides_no_debug(self) -> None:
        """Phases without D disable debug loop."""
        cfg = ArchitectureConfig(id="no_debug", phases=["A", "B", "C", "E"])
        overrides = cfg.to_settings_overrides()
        assert overrides["debug_loop_enabled"] is False


# ---------------------------------------------------------------------------
# TestCase
# ---------------------------------------------------------------------------


class TestTestCase:
    """TestCase holds input data for one evaluation run."""

    def test_basic_creation(self) -> None:
        tc = TestCase(
            id="case_001",
            task="Excelファイルの売上を集計してください",
            description="Basic aggregation task",
        )
        assert tc.id == "case_001"
        assert tc.task == "Excelファイルの売上を集計してください"
        assert tc.file_path is None
        assert tc.expected_success is True

    def test_with_file(self) -> None:
        tc = TestCase(
            id="case_002",
            task="列Aでグループ化",
            file_path="/path/to/test.xlsx",
            description="Group by column A",
        )
        assert tc.file_path == "/path/to/test.xlsx"

    def test_expected_failure(self) -> None:
        tc = TestCase(
            id="case_003",
            task="impossible task",
            expected_success=False,
            description="Should fail gracefully",
        )
        assert tc.expected_success is False

    def test_frozen(self) -> None:
        tc = TestCase(id="x", task="y", description="z")
        with pytest.raises(AttributeError):
            tc.id = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EvalMetrics
# ---------------------------------------------------------------------------


class TestEvalMetrics:
    """EvalMetrics captures quantitative results of a single run."""

    def test_creation(self) -> None:
        m = EvalMetrics(
            success=True,
            total_tokens=4500,
            api_calls=5,
            total_duration_ms=25300,
            phase_durations_ms={"A": 5000, "B": 3000, "C": 8000, "D": 9000, "E": 300},
            retry_count=1,
            code_executes=True,
        )
        assert m.success is True
        assert m.total_tokens == 4500
        assert m.api_calls == 5
        assert m.total_duration_ms == 25300
        assert m.phase_durations_ms["C"] == 8000
        assert m.retry_count == 1
        assert m.code_executes is True

    def test_defaults(self) -> None:
        m = EvalMetrics(
            success=False,
            total_duration_ms=1000,
        )
        assert m.total_tokens == 0
        assert m.api_calls == 0
        assert m.phase_durations_ms == {}
        assert m.retry_count == 0
        assert m.code_executes is False

    def test_estimated_cost(self) -> None:
        m = EvalMetrics(
            success=True,
            total_tokens=10000,
            prompt_tokens=7000,
            completion_tokens=3000,
            total_duration_ms=1000,
        )
        # gpt-4o: input $2.50/1M, output $10.00/1M
        cost = m.estimated_cost_usd(model="gpt-4o")
        assert isinstance(cost, float)
        assert cost > 0
        # 7000 * 2.50/1M + 3000 * 10.00/1M = 0.0175 + 0.03 = 0.0475
        assert abs(cost - 0.0475) < 0.001

    def test_frozen(self) -> None:
        m = EvalMetrics(success=True, total_duration_ms=100)
        with pytest.raises(AttributeError):
            m.success = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EvalResult
# ---------------------------------------------------------------------------


class TestEvalResult:
    """EvalResult ties together architecture, test case, and metrics."""

    def test_creation(self) -> None:
        r = EvalResult(
            architecture_id="v1_baseline",
            test_case_id="case_001",
            metrics=EvalMetrics(success=True, total_duration_ms=5000),
            agent_log=[],
            generated_code="print('hello')",
        )
        assert r.architecture_id == "v1_baseline"
        assert r.test_case_id == "case_001"
        assert r.metrics.success is True
        assert r.generated_code == "print('hello')"
        assert r.error is None

    def test_with_error(self) -> None:
        r = EvalResult(
            architecture_id="v2",
            test_case_id="case_002",
            metrics=EvalMetrics(success=False, total_duration_ms=3000),
            agent_log=[],
            error="Phase C JSON parse error",
        )
        assert r.error == "Phase C JSON parse error"
        assert r.metrics.success is False

    def test_to_dict(self) -> None:
        r = EvalResult(
            architecture_id="v1",
            test_case_id="c1",
            metrics=EvalMetrics(success=True, total_duration_ms=100, total_tokens=500),
            agent_log=[],
            generated_code="x=1",
        )
        d = r.to_dict()
        assert d["architecture_id"] == "v1"
        assert d["test_case_id"] == "c1"
        assert d["metrics"]["success"] is True
        assert d["metrics"]["total_tokens"] == 500
        assert d["generated_code"] == "x=1"

    def test_frozen(self) -> None:
        r = EvalResult(
            architecture_id="v1",
            test_case_id="c1",
            metrics=EvalMetrics(success=True, total_duration_ms=100),
            agent_log=[],
        )
        with pytest.raises(AttributeError):
            r.architecture_id = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# JSON loading helpers
# ---------------------------------------------------------------------------


class TestJsonLoading:
    """Test loading configs from JSON files."""

    def test_load_architecture(self, tmp_path: Path) -> None:
        data = {
            "id": "v2_skip_b",
            "phases": ["A", "C", "D", "E"],
            "model": "gpt-4o-mini",
            "debug_retry_limit": 5,
            "description": "Skip Phase B",
        }
        p = tmp_path / "v2.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        cfg = load_architecture(p)
        assert cfg.id == "v2_skip_b"
        assert cfg.phases == ["A", "C", "D", "E"]
        assert cfg.model == "gpt-4o-mini"
        assert cfg.debug_retry_limit == 5

    def test_load_test_case(self, tmp_path: Path) -> None:
        data = {
            "id": "case_001",
            "task": "売上集計",
            "file_path": "files/sample.xlsx",
            "expected_success": True,
            "description": "Basic aggregation",
        }
        p = tmp_path / "case_001.json"
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        tc = load_test_case(p)
        assert tc.id == "case_001"
        assert tc.task == "売上集計"
        assert tc.file_path == "files/sample.xlsx"

    def test_load_architecture_minimal(self, tmp_path: Path) -> None:
        """Only id is required; defaults should fill the rest."""
        data = {"id": "v_minimal"}
        p = tmp_path / "minimal.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        cfg = load_architecture(p)
        assert cfg.id == "v_minimal"
        assert cfg.phases == ["A", "B", "P", "C", "D", "F", "G", "E"]

    def test_load_test_case_minimal(self, tmp_path: Path) -> None:
        data = {"id": "tc_min", "task": "do something", "description": "desc"}
        p = tmp_path / "tc.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        tc = load_test_case(p)
        assert tc.file_path is None
        assert tc.expected_success is True
