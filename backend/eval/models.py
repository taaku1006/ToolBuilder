"""Eval harness data models.

Immutable dataclasses for architecture configs, test cases, and evaluation results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Cost per 1M tokens by model (input, output) — 2025-05 pricing
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o":           (2.50, 10.00),
    "gpt-4o-mini":      (0.15,  0.60),
    "gpt-4.1":          (2.00,  8.00),
    "gpt-4.1-mini":     (0.40,  1.60),
    "gpt-4.1-nano":     (0.10,  0.40),
    "gpt-4-turbo":      (10.00, 30.00),
    "gpt-3.5-turbo":    (0.50,  1.50),
    "o3":               (2.00,  8.00),
    "o3-mini":          (1.10,  4.40),
    "o4-mini":          (1.10,  4.40),
}


@dataclass(frozen=True)
class PipelineConfig:
    """Structured pipeline configuration for an architecture."""

    explore: bool = True
    reflect: bool = True
    decompose: bool = False
    debug_retry_limit: int = 3
    eval_debug: bool = False
    eval_retry_strategy: str = "none"
    eval_retry_max_loops: int = 2
    eval_quality_threshold: float = 0.85
    llm_eval_debug: bool = False
    llm_eval_score_threshold: float = 7.0
    llm_eval_retry_limit: int = 2
    subtask_debug_retries: int = 2
    skills: bool = True


@dataclass(frozen=True)
class ArchitectureConfig:
    """Defines an agent architecture variant for evaluation."""

    id: str
    phases: list[str] = field(default_factory=lambda: ["A", "B", "P", "C", "D", "F", "G", "E"])
    pipeline: PipelineConfig | None = None
    model: str = "gpt-4o"
    debug_retry_limit: int = 3
    temperature: float = 0.2
    description: str = ""

    def to_settings_overrides(self) -> dict:
        """Return a dict of Settings field overrides derived from this config."""
        if self.pipeline is not None:
            p = self.pipeline
            return {
                "reflection_enabled": p.explore,
                "reflection_phase_enabled": p.reflect,
                "task_decomposition_enabled": p.decompose,
                "debug_loop_enabled": True,
                "debug_retry_limit": p.debug_retry_limit,
                "eval_debug_loop_enabled": p.eval_debug,
                "eval_debug_retry_limit": p.debug_retry_limit,
                "eval_debug_quality_threshold": p.eval_quality_threshold,
                "eval_retry_strategy": p.eval_retry_strategy,
                "eval_retry_max_loops": p.eval_retry_max_loops,
                "subtask_debug_retries": p.subtask_debug_retries,
                "llm_eval_loop_enabled": p.llm_eval_debug,
                "llm_eval_score_threshold": p.llm_eval_score_threshold,
                "llm_eval_retry_limit": p.llm_eval_retry_limit,
                "max_subtasks": 10,
                "skills_enabled": p.skills,
                "openai_model": self.model,
            }

        has_exploration = "A" in self.phases
        has_reflection_b = "B" in self.phases
        has_planner = "P" in self.phases
        has_debug = "D" in self.phases
        has_eval_debug = "F" in self.phases
        has_skills = "E" in self.phases
        return {
            "reflection_enabled": has_exploration,
            "reflection_phase_enabled": has_reflection_b,
            "task_decomposition_enabled": has_planner,
            "debug_loop_enabled": has_debug,
            "eval_debug_loop_enabled": has_eval_debug,
            "skills_enabled": has_skills,
            "openai_model": self.model,
            "debug_retry_limit": self.debug_retry_limit,
        }


@dataclass(frozen=True)
class TestCase:
    """Input data for one evaluation run."""

    id: str
    task: str
    description: str
    file_path: str | None = None
    expected_file_path: str | None = None
    expected_success: bool = True
    # Optional task-specific evaluation rubric for structured comparison.
    # Schema: {key_cells, value_scan, color_checks, sheet_visibility, extra_files}
    rubric: dict | None = None


@dataclass(frozen=True)
class EvalMetrics:
    """Quantitative results of a single evaluation run."""

    success: bool
    total_duration_ms: int
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    api_calls: int = 0
    phase_durations_ms: dict[str, int] = field(default_factory=dict)
    phase_tokens: dict[str, int] = field(default_factory=dict)
    retry_count: int = 0
    code_executes: bool = False
    error_category: str = "none"
    quality_score: float | None = None
    quality_details: dict | None = None
    llm_eval_score: float | None = None
    llm_eval_details: dict | None = None

    def estimated_cost_usd(self, model: str = "gpt-4o") -> float:
        """Estimate cost based on input/output token counts and model pricing."""
        input_rate, output_rate = _MODEL_PRICING.get(model, _MODEL_PRICING["gpt-4o"])
        input_cost = (self.prompt_tokens / 1_000_000) * input_rate
        output_cost = (self.completion_tokens / 1_000_000) * output_rate
        return input_cost + output_cost


@dataclass(frozen=True)
class EvalResult:
    """Ties together architecture, test case, and evaluation metrics."""

    architecture_id: str
    test_case_id: str
    metrics: EvalMetrics
    agent_log: list[dict]
    model: str = "gpt-4o"
    generated_code: str | None = None
    error: str | None = None
    output_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to a plain dict (JSON-safe)."""
        return {
            "architecture_id": self.architecture_id,
            "test_case_id": self.test_case_id,
            "model": self.model,
            "metrics": {**asdict(self.metrics), "estimated_cost_usd": self.metrics.estimated_cost_usd(self.model)},
            "agent_log": self.agent_log,
            "generated_code": self.generated_code,
            "error": self.error,
            "output_files": self.output_files,
        }


# ---------------------------------------------------------------------------
# JSON loading helpers
# ---------------------------------------------------------------------------


def load_architecture(path: Path) -> ArchitectureConfig:
    """Load an ArchitectureConfig from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))

    pipeline = None
    if "pipeline" in data:
        p = data["pipeline"]
        pipeline = PipelineConfig(
            explore=p.get("explore", True),
            reflect=p.get("reflect", True),
            decompose=p.get("decompose", False),
            debug_retry_limit=p.get("debug_retry_limit", 3),
            eval_debug=p.get("eval_debug", False),
            eval_retry_strategy=p.get("eval_retry_strategy", "none"),
            eval_retry_max_loops=p.get("eval_retry_max_loops", 2),
            eval_quality_threshold=p.get("eval_quality_threshold", 0.85),
            llm_eval_debug=p.get("llm_eval_debug", False),
            llm_eval_score_threshold=p.get("llm_eval_score_threshold", 7.0),
            llm_eval_retry_limit=p.get("llm_eval_retry_limit", 2),
            subtask_debug_retries=p.get("subtask_debug_retries", 2),
            skills=p.get("skills", True),
        )

    return ArchitectureConfig(
        id=data["id"],
        phases=data.get("phases", ["A", "B", "P", "C", "D", "F", "G", "E"]),
        pipeline=pipeline,
        model=data.get("model", "gpt-4o"),
        debug_retry_limit=data.get("debug_retry_limit", 3),
        temperature=data.get("temperature", 0.2),
        description=data.get("description", ""),
    )


def load_test_case(path: Path) -> TestCase:
    """Load a TestCase from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return TestCase(
        id=data["id"],
        task=data["task"],
        description=data.get("description", ""),
        file_path=data.get("file_path"),
        expected_file_path=data.get("expected_file_path"),
        expected_success=data.get("expected_success", True),
        rubric=data.get("rubric"),
    )
