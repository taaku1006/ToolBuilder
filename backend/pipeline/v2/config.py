"""Adaptive Pipeline v2 stage configuration.

Per-stage model, temperature, and max_tokens settings.
Analogous to Auto-Claude's AGENT_CONFIGS.
"""

from __future__ import annotations

from dataclasses import dataclass, field


STAGE_CONFIGS: dict[str, dict] = {
    "understand": {
        "model": "gpt-4o-mini",
        "temperature": 0.1,
        "max_tokens": 3000,
    },
    "strategize": {
        "model": "gpt-4o-mini",
        "temperature": 0.2,
        "max_tokens": 2000,
    },
    "generate": {
        "model": "gpt-4o",
        "temperature": 0.3,
        "max_tokens": 8000,
    },
    "generate_step": {
        "model": "gpt-4o",
        "temperature": 0.3,
        "max_tokens": 4000,
    },
    "verify_llm": {
        "model": "gpt-4o-mini",
        "temperature": 0.0,
        "max_tokens": 2000,
    },
    "fix": {
        "model": "gpt-4o",
        "temperature": 0.2,
        "max_tokens": 8000,
    },
}


@dataclass
class V2Settings:
    """Runtime settings for the v2 pipeline, populated from architecture JSON."""

    stage_models: dict[str, str] = field(default_factory=lambda: {
        k: v["model"] for k, v in STAGE_CONFIGS.items()
    })
    max_attempts: dict[str, int] = field(default_factory=lambda: {
        "simple": 2,
        "standard": 4,
        "complex": 6,
    })
    max_replan: int = 2
    quality_threshold: float = 0.85
    semantic_threshold: float = 7.0
    pass_threshold: float = 0.75
    memory_enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> V2Settings:
        """Create V2Settings from a v2_config dict (from architecture JSON)."""
        kwargs: dict = {}
        if "stage_models" in data:
            kwargs["stage_models"] = data["stage_models"]
        if "max_attempts" in data:
            kwargs["max_attempts"] = data["max_attempts"]
        for key in ("max_replan", "quality_threshold", "semantic_threshold",
                     "pass_threshold", "memory_enabled"):
            if key in data:
                kwargs[key] = data[key]
        return cls(**kwargs)
