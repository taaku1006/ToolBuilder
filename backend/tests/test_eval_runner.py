"""Tests for eval.runner — runs test cases against architecture configs.

TDD RED phase: defines the expected runner API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eval.models import ArchitectureConfig, EvalMetrics, EvalResult, TestCase
from eval.runner import EvalRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def baseline_arch() -> ArchitectureConfig:
    return ArchitectureConfig(id="v1_baseline")


@pytest.fixture
def minimal_arch() -> ArchitectureConfig:
    return ArchitectureConfig(id="v3_minimal", phases=["C", "D"])


@pytest.fixture
def simple_case() -> TestCase:
    return TestCase(
        id="case_001",
        task="売上を集計してください",
        description="Basic aggregation",
    )


@pytest.fixture
def case_with_file(tmp_path: Path) -> TestCase:
    """TestCase pointing to a real xlsx file."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["product", "amount"])
    ws.append(["A", 100])
    ws.append(["B", 200])
    fpath = tmp_path / "test.xlsx"
    wb.save(str(fpath))

    return TestCase(
        id="case_002",
        task="商品別に金額を合計してください",
        file_path=str(fpath),
        description="Group by product",
    )


def _make_mock_settings(overrides: dict | None = None) -> MagicMock:
    """Create a mock Settings with defaults."""
    s = MagicMock()
    s.openai_api_key = "test-key"
    s.openai_model = "gpt-4o"
    s.upload_dir = "./uploads"
    s.output_dir = "./outputs"
    s.exec_timeout = 30
    s.reflection_enabled = True
    s.reflection_max_steps = 3
    s.debug_loop_enabled = True
    s.debug_retry_limit = 3
    s.skills_enabled = True
    if overrides:
        for k, v in overrides.items():
            setattr(s, k, v)
    return s


# ---------------------------------------------------------------------------
# EvalRunner creation
# ---------------------------------------------------------------------------


class TestEvalRunnerCreation:
    def test_create_runner(self, baseline_arch: ArchitectureConfig) -> None:
        runner = EvalRunner(
            architectures=[baseline_arch],
            test_cases=[],
            settings_factory=_make_mock_settings,
        )
        assert len(runner.architectures) == 1
        assert runner.architectures[0].id == "v1_baseline"

    def test_create_runner_multiple_archs(self) -> None:
        archs = [
            ArchitectureConfig(id="v1"),
            ArchitectureConfig(id="v2", phases=["C", "D"]),
        ]
        runner = EvalRunner(
            architectures=archs,
            test_cases=[],
            settings_factory=_make_mock_settings,
        )
        assert len(runner.architectures) == 2


# ---------------------------------------------------------------------------
# Single run
# ---------------------------------------------------------------------------


class TestEvalRunnerSingleRun:
    """Test running a single (architecture, test_case) pair."""

    @pytest.mark.asyncio
    async def test_run_single_returns_eval_result(
        self,
        minimal_arch: ArchitectureConfig,
        simple_case: TestCase,
    ) -> None:
        """run_single should return an EvalResult with metrics."""
        mock_log_entry = MagicMock()
        mock_log_entry.phase = "C"
        mock_log_entry.action = "complete"
        mock_log_entry.content = json.dumps({
            "python_code": "print('hello')",
            "summary": "test",
            "steps": [],
            "tips": "",
            "debug_retries": 0,
        })
        mock_log_entry.timestamp = "2026-03-28T00:00:00+00:00"

        async def mock_orchestrate(*args, **kwargs):
            yield mock_log_entry

        runner = EvalRunner(
            architectures=[minimal_arch],
            test_cases=[simple_case],
            settings_factory=_make_mock_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            result = await runner.run_single(minimal_arch, simple_case)

        assert isinstance(result, EvalResult)
        assert result.architecture_id == "v3_minimal"
        assert result.test_case_id == "case_001"
        assert isinstance(result.metrics, EvalMetrics)
        assert result.metrics.total_duration_ms >= 0

    @pytest.mark.asyncio
    async def test_run_single_captures_error(
        self,
        minimal_arch: ArchitectureConfig,
        simple_case: TestCase,
    ) -> None:
        """If orchestrate raises, result should capture the error."""

        async def mock_orchestrate_fail(*args, **kwargs):
            raise RuntimeError("OpenAI API error")
            yield  # make it a generator  # noqa: E501

        runner = EvalRunner(
            architectures=[minimal_arch],
            test_cases=[simple_case],
            settings_factory=_make_mock_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate_fail):
            result = await runner.run_single(minimal_arch, simple_case)

        assert result.metrics.success is False
        assert result.error is not None
        assert "OpenAI API error" in result.error

    @pytest.mark.asyncio
    async def test_run_single_tracks_phase_durations(
        self,
        baseline_arch: ArchitectureConfig,
        simple_case: TestCase,
    ) -> None:
        """Phase start/complete events should produce phase duration tracking."""
        entries = []

        # Simulate A start → A complete → C start → C complete
        for phase, action, content in [
            ("A", "start", "Phase A start"),
            ("A", "complete", "exploration done"),
            ("C", "start", "Phase C start"),
            ("C", "complete", json.dumps({
                "python_code": "x=1",
                "summary": "s",
                "steps": [],
                "tips": "",
                "debug_retries": 0,
            })),
        ]:
            entry = MagicMock()
            entry.phase = phase
            entry.action = action
            entry.content = content
            entry.timestamp = "2026-03-28T00:00:00+00:00"
            entries.append(entry)

        async def mock_orchestrate(*args, **kwargs):
            for e in entries:
                yield e

        runner = EvalRunner(
            architectures=[baseline_arch],
            test_cases=[simple_case],
            settings_factory=_make_mock_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            result = await runner.run_single(baseline_arch, simple_case)

        assert isinstance(result.metrics.phase_durations_ms, dict)

    @pytest.mark.asyncio
    async def test_run_single_counts_retries(
        self,
        minimal_arch: ArchitectureConfig,
        simple_case: TestCase,
    ) -> None:
        """Retry events from Phase D should be counted."""
        entries = []
        for phase, action, content in [
            ("C", "start", "start"),
            ("D", "start", "debug start"),
            ("D", "retry", "retry 1: error"),
            ("D", "retry", "retry 2: error"),
            ("D", "complete", "2 retries to succeed"),
            ("C", "complete", json.dumps({
                "python_code": "fixed",
                "summary": "s",
                "steps": [],
                "tips": "",
                "debug_retries": 2,
            })),
        ]:
            entry = MagicMock()
            entry.phase = phase
            entry.action = action
            entry.content = content
            entry.timestamp = "2026-03-28T00:00:00+00:00"
            entries.append(entry)

        async def mock_orchestrate(*args, **kwargs):
            for e in entries:
                yield e

        runner = EvalRunner(
            architectures=[minimal_arch],
            test_cases=[simple_case],
            settings_factory=_make_mock_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            result = await runner.run_single(minimal_arch, simple_case)

        assert result.metrics.retry_count == 2


# ---------------------------------------------------------------------------
# Full run (all combos)
# ---------------------------------------------------------------------------


class TestEvalRunnerFullRun:
    """Test running all architecture x test_case combinations."""

    @pytest.mark.asyncio
    async def test_run_all_returns_results_for_each_combo(self) -> None:
        archs = [
            ArchitectureConfig(id="v1"),
            ArchitectureConfig(id="v2", phases=["C", "D"]),
        ]
        cases = [
            TestCase(id="c1", task="task1", description="d1"),
            TestCase(id="c2", task="task2", description="d2"),
        ]

        async def mock_orchestrate(*args, **kwargs):
            entry = MagicMock()
            entry.phase = "C"
            entry.action = "complete"
            entry.content = json.dumps({
                "python_code": "pass",
                "summary": "s",
                "steps": [],
                "tips": "",
                "debug_retries": 0,
            })
            entry.timestamp = "2026-03-28T00:00:00+00:00"
            yield entry

        runner = EvalRunner(
            architectures=archs,
            test_cases=cases,
            settings_factory=_make_mock_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            results = await runner.run_all()

        # 2 archs x 2 cases = 4 results
        assert len(results) == 4
        arch_ids = {r.architecture_id for r in results}
        assert arch_ids == {"v1", "v2"}
        case_ids = {r.test_case_id for r in results}
        assert case_ids == {"c1", "c2"}

    @pytest.mark.asyncio
    async def test_run_all_applies_settings_overrides(self) -> None:
        """Each architecture's settings overrides should be applied."""
        arch = ArchitectureConfig(id="v3", phases=["C"], model="gpt-4o-mini")
        case = TestCase(id="c1", task="t", description="d")

        applied_settings = {}

        async def mock_orchestrate(task, file_id, settings):
            applied_settings["reflection_enabled"] = settings.reflection_enabled
            applied_settings["debug_loop_enabled"] = settings.debug_loop_enabled
            applied_settings["openai_model"] = settings.openai_model
            entry = MagicMock()
            entry.phase = "C"
            entry.action = "complete"
            entry.content = json.dumps({
                "python_code": "pass",
                "summary": "s",
                "steps": [],
                "tips": "",
                "debug_retries": 0,
            })
            entry.timestamp = "2026-03-28T00:00:00+00:00"
            yield entry

        runner = EvalRunner(
            architectures=[arch],
            test_cases=[case],
            settings_factory=_make_mock_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            await runner.run_all()

        assert applied_settings["reflection_enabled"] is False
        assert applied_settings["debug_loop_enabled"] is False
        assert applied_settings["openai_model"] == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Result persistence
# ---------------------------------------------------------------------------


class TestResultPersistence:
    """Test saving results to disk."""

    @pytest.mark.asyncio
    async def test_save_results(self, tmp_path: Path) -> None:
        results = [
            EvalResult(
                architecture_id="v1",
                test_case_id="c1",
                metrics=EvalMetrics(success=True, total_duration_ms=100, total_tokens=500),
                agent_log=[],
                generated_code="x=1",
            ),
        ]

        runner = EvalRunner(
            architectures=[],
            test_cases=[],
            settings_factory=_make_mock_settings,
        )
        runner.save_results(results, tmp_path)

        # Should create individual result files
        result_files = list(tmp_path.glob("*.json"))
        assert len(result_files) >= 1

        # Should create a summary file
        summary_path = tmp_path / "summary.json"
        assert summary_path.exists()

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert len(summary["results"]) == 1
        assert summary["results"][0]["architecture_id"] == "v1"
