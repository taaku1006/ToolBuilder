"""Tests for EvalRunManager service.

TDD: RED phase - these tests are written before the implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        openai_api_key="test-key",
        openai_model="gpt-4o",
        cors_origins="http://localhost:5173",
    )


@pytest.fixture
def manager(test_settings: Settings):
    from services.eval_run_manager import EvalRunManager
    return EvalRunManager(settings=test_settings)


@pytest.fixture
def arch_json(tmp_path: Path) -> Path:
    """Create a minimal architecture JSON file."""
    arch_dir = tmp_path / "architectures"
    arch_dir.mkdir()
    arch_data = {
        "id": "test-arch",
        "phases": ["A", "B", "C"],
        "model": "gpt-4o",
        "debug_retry_limit": 3,
        "temperature": 0.2,
        "description": "Test architecture",
    }
    (arch_dir / "test_arch.json").write_text(
        json.dumps(arch_data), encoding="utf-8"
    )
    return arch_dir


@pytest.fixture
def case_json(tmp_path: Path) -> Path:
    """Create a minimal test case JSON file."""
    case_dir = tmp_path / "test_cases"
    case_dir.mkdir()
    case_data = {
        "id": "test-case-1",
        "task": "Sort a list",
        "description": "Test task",
        "file_path": None,
        "expected_success": True,
    }
    (case_dir / "test_case_1.json").write_text(
        json.dumps(case_data), encoding="utf-8"
    )
    return case_dir


# ---------------------------------------------------------------------------
# list_architectures
# ---------------------------------------------------------------------------


class TestListArchitectures:
    def test_returns_empty_when_dir_missing(self, manager, tmp_path: Path):
        missing_dir = tmp_path / "no_archs"
        result = manager.list_architectures(archs_dir=missing_dir)
        assert result == []

    def test_returns_arch_list(self, manager, arch_json: Path):
        result = manager.list_architectures(archs_dir=arch_json)
        assert len(result) == 1
        assert result[0].id == "test-arch"

    def test_returns_multiple_archs(self, manager, tmp_path: Path):
        arch_dir = tmp_path / "architectures"
        arch_dir.mkdir()
        for i in range(3):
            data = {
                "id": f"arch-{i}",
                "phases": ["A", "B"],
                "model": "gpt-4o",
                "debug_retry_limit": 3,
                "temperature": 0.2,
                "description": f"Arch {i}",
            }
            (arch_dir / f"arch_{i}.json").write_text(json.dumps(data), encoding="utf-8")

        result = manager.list_architectures(archs_dir=arch_dir)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# list_test_cases
# ---------------------------------------------------------------------------


class TestListTestCases:
    def test_returns_empty_when_dir_missing(self, manager, tmp_path: Path):
        missing_dir = tmp_path / "no_cases"
        result = manager.list_test_cases(cases_dir=missing_dir)
        assert result == []

    def test_returns_case_list(self, manager, case_json: Path):
        result = manager.list_test_cases(cases_dir=case_json)
        assert len(result) == 1
        assert result[0].id == "test-case-1"
        assert result[0].task == "Sort a list"

    def test_returns_multiple_cases(self, manager, tmp_path: Path):
        case_dir = tmp_path / "test_cases"
        case_dir.mkdir()
        for i in range(2):
            data = {
                "id": f"case-{i}",
                "task": f"Task {i}",
                "description": "",
                "file_path": None,
                "expected_success": True,
            }
            (case_dir / f"case_{i}.json").write_text(json.dumps(data), encoding="utf-8")

        result = manager.list_test_cases(cases_dir=case_dir)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# start_run / get_status
# ---------------------------------------------------------------------------


class TestStartRun:
    def test_start_run_adds_to_status(self, manager):
        run_id = "20240101_120000"
        manager.start_run(run_id=run_id, total=4)
        status = manager.get_status(run_id)
        assert status is not None
        assert status["status"] == "running"
        assert status["progress"] == 0
        assert status["total"] == 4
        assert status["cancel_requested"] is False

    def test_get_status_returns_none_for_unknown(self, manager):
        result = manager.get_status("nonexistent-run-id")
        assert result is None

    def test_start_run_multiple_independent(self, manager):
        manager.start_run(run_id="run-1", total=2)
        manager.start_run(run_id="run-2", total=5)
        assert manager.get_status("run-1")["total"] == 2
        assert manager.get_status("run-2")["total"] == 5


# ---------------------------------------------------------------------------
# stop_run
# ---------------------------------------------------------------------------


class TestStopRun:
    def test_stop_sets_cancel_flag(self, manager):
        manager.start_run(run_id="run-abc", total=3)
        result = manager.stop_run(run_id="run-abc")
        assert result is True
        status = manager.get_status("run-abc")
        assert status["cancel_requested"] is True

    def test_stop_nonexistent_run_returns_false(self, manager):
        result = manager.stop_run(run_id="does-not-exist")
        assert result is False


# ---------------------------------------------------------------------------
# update_progress
# ---------------------------------------------------------------------------


class TestUpdateProgress:
    def test_update_progress(self, manager):
        manager.start_run(run_id="run-prog", total=10)
        manager.update_progress(run_id="run-prog", progress=3)
        status = manager.get_status("run-prog")
        assert status["progress"] == 3

    def test_complete_run(self, manager):
        manager.start_run(run_id="run-done", total=2)
        manager.complete_run(run_id="run-done", report={"best_architecture": "arch-1"})
        status = manager.get_status("run-done")
        assert status["status"] == "completed"
        assert status["report"]["best_architecture"] == "arch-1"

    def test_fail_run(self, manager):
        manager.start_run(run_id="run-fail", total=2)
        manager.fail_run(run_id="run-fail", error="Something went wrong")
        status = manager.get_status("run-fail")
        assert status["status"] == "failed"
        assert status["report"]["error"] == "Something went wrong"

    def test_stop_run_updates_status_to_stopped(self, manager):
        manager.start_run(run_id="run-stop", total=2)
        manager.stop_run("run-stop")
        manager.mark_stopped(run_id="run-stop")
        status = manager.get_status("run-stop")
        assert status["status"] == "stopped"


# ---------------------------------------------------------------------------
# load_results
# ---------------------------------------------------------------------------


class TestLoadResults:
    def test_load_results_raises_when_not_found(self, manager, tmp_path: Path):
        results_dir = tmp_path / "results"
        with pytest.raises(FileNotFoundError):
            manager.load_results(run_id="nonexistent", results_dir=results_dir)

    def test_load_results_parses_summary(self, manager, tmp_path: Path):
        results_dir = tmp_path / "results"
        run_dir = results_dir / "run_test-run"
        run_dir.mkdir(parents=True)
        summary = {
            "results": [
                {
                    "architecture_id": "arch-1",
                    "test_case_id": "case-1",
                    "model": "gpt-4o",
                    "metrics": {
                        "success": True,
                        "total_duration_ms": 1000,
                        "total_tokens": 500,
                        "prompt_tokens": 300,
                        "completion_tokens": 200,
                        "api_calls": 1,
                        "phase_durations_ms": {},
                        "phase_tokens": {},
                        "retry_count": 0,
                        "code_executes": True,
                        "error_category": "none",
                        "quality_score": None,
                        "quality_details": None,
                        "llm_eval_score": None,
                        "llm_eval_details": None,
                    },
                    "agent_log": [],
                    "generated_code": None,
                    "error": None,
                }
            ]
        }
        (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

        results = manager.load_results(run_id="test-run", results_dir=results_dir)
        assert len(results) == 1
        assert results[0].architecture_id == "arch-1"
        assert results[0].test_case_id == "case-1"
        assert results[0].metrics.success is True


# ---------------------------------------------------------------------------
# load_snapshot
# ---------------------------------------------------------------------------


class TestLoadSnapshot:
    def test_load_snapshot_raises_when_not_found(self, manager, tmp_path: Path):
        results_dir = tmp_path / "results"
        with pytest.raises(FileNotFoundError):
            manager.load_snapshot(run_id="nonexistent", results_dir=results_dir)

    def test_load_snapshot_returns_run_snapshot(self, manager, tmp_path: Path):
        results_dir = tmp_path / "results"
        run_dir = results_dir / "run_snap-run"
        run_dir.mkdir(parents=True)
        snapshot_data = {
            "prompt_hashes": {"phase_a": "abc123"},
            "prompt_contents": {"phase_a": "explore prompt"},
            "architecture_configs": {"arch-1": {"id": "arch-1"}},
            "snapshot_hash": "deadbeef",
        }
        (run_dir / "snapshot.json").write_text(json.dumps(snapshot_data), encoding="utf-8")

        from eval.versioning import RunSnapshot
        result = manager.load_snapshot(run_id="snap-run", results_dir=results_dir)
        assert isinstance(result, RunSnapshot)
        assert result.snapshot_hash == "deadbeef"
        assert result.prompt_hashes == {"phase_a": "abc123"}


# ---------------------------------------------------------------------------
# list_runs
# ---------------------------------------------------------------------------


class TestListRuns:
    def test_list_runs_empty_when_no_dir(self, manager, tmp_path: Path):
        results_dir = tmp_path / "results"
        runs = manager.list_runs(results_dir=results_dir)
        assert runs == []

    def test_list_runs_includes_completed_from_disk(self, manager, tmp_path: Path):
        results_dir = tmp_path / "results"
        run_dir = results_dir / "run_20240101"
        run_dir.mkdir(parents=True)
        report = {"best_architecture": "arch-1", "summary": {}}
        (run_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")

        runs = manager.list_runs(results_dir=results_dir)
        assert len(runs) == 1
        assert runs[0]["run_id"] == "20240101"
        assert runs[0]["status"] == "completed"

    def test_list_runs_includes_in_memory_running(self, manager, tmp_path: Path):
        results_dir = tmp_path / "results"
        manager.start_run(run_id="live-run", total=5)

        runs = manager.list_runs(results_dir=results_dir)
        running = [r for r in runs if r["run_id"] == "live-run"]
        assert len(running) == 1
        assert running[0]["status"] == "running"

    def test_list_runs_from_disk_sorted_descending(self, manager, tmp_path: Path):
        results_dir = tmp_path / "results"
        for name in ["run_20240101", "run_20240201", "run_20240301"]:
            d = results_dir / name
            d.mkdir(parents=True)
            (d / "report.json").write_text(json.dumps({}), encoding="utf-8")

        runs = manager.list_runs(results_dir=results_dir)
        disk_runs = [r for r in runs if r["status"] == "completed"]
        ids = [r["run_id"] for r in disk_runs]
        assert ids == sorted(ids, reverse=True)


# ---------------------------------------------------------------------------
# settings_factory
# ---------------------------------------------------------------------------


class TestSettingsFactory:
    def test_settings_factory_returns_settings(self, manager):
        settings = manager.settings_factory()
        assert settings is not None

    def test_settings_factory_with_overrides(self, manager):
        settings = manager.settings_factory(overrides={"openai_model": "gpt-4o-mini"})
        assert settings.openai_model == "gpt-4o-mini"

    def test_settings_factory_without_overrides_uses_base(self, manager, test_settings: Settings):
        settings = manager.settings_factory()
        assert settings.openai_api_key == test_settings.openai_api_key
