"""Tests for PipelineConfig and updated ArchitectureConfig.

TDD RED: Tests define expected API for pipeline-based architecture configs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.models import (
    ArchitectureConfig,
    PipelineConfig,
    load_architecture,
)


class TestPipelineConfig:
    def test_defaults(self) -> None:
        p = PipelineConfig()
        assert p.explore is True
        assert p.reflect is True
        assert p.decompose is False
        assert p.debug_retry_limit == 3
        assert p.eval_debug is False
        assert p.eval_retry_strategy == "none"
        assert p.eval_retry_max_loops == 2
        assert p.eval_quality_threshold == 0.85
        assert p.subtask_debug_retries == 2
        assert p.skills is True

    def test_custom(self) -> None:
        p = PipelineConfig(
            explore=False,
            reflect=False,
            decompose=True,
            eval_debug=True,
            eval_retry_strategy="replan",
            eval_retry_max_loops=3,
        )
        assert p.decompose is True
        assert p.eval_retry_strategy == "replan"

    def test_frozen(self) -> None:
        p = PipelineConfig()
        with pytest.raises(AttributeError):
            p.explore = False  # type: ignore[misc]


class TestArchitectureConfigWithPipeline:
    def test_pipeline_to_settings_overrides(self) -> None:
        cfg = ArchitectureConfig(
            id="v5_planner_replan",
            pipeline=PipelineConfig(
                explore=True,
                reflect=True,
                decompose=True,
                debug_retry_limit=3,
                eval_debug=True,
                eval_retry_strategy="replan",
                eval_retry_max_loops=2,
                subtask_debug_retries=2,
            ),
            model="gpt-4o",
        )
        overrides = cfg.to_settings_overrides()
        assert overrides["reflection_enabled"] is True
        assert overrides["reflection_phase_enabled"] is True
        assert overrides["task_decomposition_enabled"] is True
        assert overrides["debug_loop_enabled"] is True
        assert overrides["eval_debug_loop_enabled"] is True
        assert overrides["eval_retry_strategy"] == "replan"
        assert overrides["eval_retry_max_loops"] == 2
        assert overrides["subtask_debug_retries"] == 2
        assert overrides["openai_model"] == "gpt-4o"

    def test_pipeline_no_explore(self) -> None:
        cfg = ArchitectureConfig(
            id="v2",
            pipeline=PipelineConfig(explore=False, reflect=False),
        )
        overrides = cfg.to_settings_overrides()
        assert overrides["reflection_enabled"] is False
        assert overrides["reflection_phase_enabled"] is False

    def test_legacy_phases_still_work(self) -> None:
        """ArchitectureConfig with phases array (no pipeline) still works."""
        cfg = ArchitectureConfig(id="v1", phases=["A", "B", "C", "D", "F", "E"])
        overrides = cfg.to_settings_overrides()
        assert overrides["reflection_enabled"] is True
        assert overrides["eval_debug_loop_enabled"] is True

    def test_pipeline_takes_precedence(self) -> None:
        """When pipeline is set, phases array is ignored."""
        cfg = ArchitectureConfig(
            id="v1",
            phases=["A", "B", "C", "D", "E"],
            pipeline=PipelineConfig(explore=False),
        )
        overrides = cfg.to_settings_overrides()
        assert overrides["reflection_enabled"] is False


class TestLoadArchitectureWithPipeline:
    def test_load_pipeline_format(self, tmp_path: Path) -> None:
        data = {
            "id": "v5_planner_replan",
            "pipeline": {
                "explore": True,
                "reflect": True,
                "decompose": True,
                "debug_retry_limit": 3,
                "eval_debug": True,
                "eval_retry_strategy": "replan",
                "eval_retry_max_loops": 2,
                "subtask_debug_retries": 2,
            },
            "model": "gpt-4o",
            "description": "Planner + smart replan",
        }
        p = tmp_path / "v5.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        cfg = load_architecture(p)
        assert cfg.id == "v5_planner_replan"
        assert cfg.pipeline is not None
        assert cfg.pipeline.decompose is True
        assert cfg.pipeline.eval_retry_strategy == "replan"

    def test_load_legacy_format(self, tmp_path: Path) -> None:
        data = {
            "id": "v1_baseline",
            "phases": ["A", "B", "C", "D", "F", "E"],
            "model": "gpt-4o",
        }
        p = tmp_path / "v1.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        cfg = load_architecture(p)
        assert cfg.pipeline is None
        assert cfg.phases == ["A", "B", "C", "D", "F", "E"]
