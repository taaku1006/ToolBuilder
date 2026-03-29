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
class ArchitectureConfig:
    """Defines an agent architecture variant for evaluation."""

    id: str
    phases: list[str] = field(default_factory=lambda: ["A", "B", "C", "D", "E"])
    model: str = "gpt-4o"
    debug_retry_limit: int = 3
    temperature: float = 0.2
    description: str = ""

    def to_settings_overrides(self) -> dict:
        """Return a dict of Settings field overrides derived from this config."""
        has_exploration = "A" in self.phases
        has_reflection_b = "B" in self.phases
        has_debug = "D" in self.phases
        has_skills = "E" in self.phases
        return {
            "reflection_enabled": has_exploration,
            "reflection_phase_enabled": has_reflection_b,
            "debug_loop_enabled": has_debug,
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
        }


# ---------------------------------------------------------------------------
# JSON loading helpers
# ---------------------------------------------------------------------------


def load_architecture(path: Path) -> ArchitectureConfig:
    """Load an ArchitectureConfig from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return ArchitectureConfig(
        id=data["id"],
        phases=data.get("phases", ["A", "B", "C", "D", "E"]),
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
    )
