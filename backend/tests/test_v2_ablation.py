"""Tests for Phase 3: ablation architecture configs and dynamic V2Settings loading."""

import json
from pathlib import Path

import pytest

from pipeline.v2.config import STAGE_CONFIGS, V2Settings


ARCH_DIR = Path(__file__).resolve().parents[1] / "eval" / "architectures"


class TestAblationArchitecturesExist:
    def test_v2_adaptive_exists(self):
        assert (ARCH_DIR / "v2_adaptive.json").exists()

    def test_v2_adaptive_no_memory_exists(self):
        assert (ARCH_DIR / "v2_adaptive_no_memory.json").exists()

    @pytest.mark.skipif(
        not (ARCH_DIR / "v2_adaptive_mini.json").exists(),
        reason="v2_adaptive_mini.json not present",
    )
    def test_v2_adaptive_mini_exists(self):
        assert (ARCH_DIR / "v2_adaptive_mini.json").exists()


class TestAblationConfigs:
    def test_no_memory_config(self):
        data = json.loads((ARCH_DIR / "v2_adaptive_no_memory.json").read_text())
        assert data["v2_config"]["memory_enabled"] is False

    @pytest.mark.skipif(
        not (ARCH_DIR / "v2_adaptive_mini.json").exists(),
        reason="v2_adaptive_mini.json not present",
    )
    def test_mini_config_all_models_are_mini(self):
        data = json.loads((ARCH_DIR / "v2_adaptive_mini.json").read_text())
        for stage, model in data["v2_config"]["stage_models"].items():
            assert "mini" in model, f"Stage {stage} should use mini model, got {model}"

    def test_v2_adaptive_has_memory_enabled(self):
        data = json.loads((ARCH_DIR / "v2_adaptive.json").read_text())
        assert data["v2_config"]["memory_enabled"] is True


class TestV2SettingsFromArchConfig:
    def test_from_dict_overrides_memory(self):
        s = V2Settings.from_dict({"memory_enabled": False})
        assert s.memory_enabled is False

    def test_from_dict_overrides_stage_models(self):
        s = V2Settings.from_dict({
            "stage_models": {
                "understand": "gpt-4o-mini",
                "strategize": "gpt-4o-mini",
                "generate": "gpt-4o-mini",
                "generate_step": "gpt-4o-mini",
                "verify_llm": "gpt-4o-mini",
                "fix": "gpt-4o-mini",
            }
        })
        for stage, model in s.stage_models.items():
            assert model == "gpt-4o-mini"

    def test_from_dict_overrides_thresholds(self):
        s = V2Settings.from_dict({
            "quality_threshold": 0.7,
            "pass_threshold": 0.6,
        })
        assert s.quality_threshold == 0.7
        assert s.pass_threshold == 0.6


class TestV2SettingsGetStageConfig:
    """V2Settings should provide per-stage model/temp/max_tokens that override STAGE_CONFIGS."""

    def test_get_stage_config_default(self):
        s = V2Settings()
        cfg = s.get_stage_config("generate")
        assert cfg["model"] == "gpt-4o"
        assert "temperature" in cfg
        assert "max_tokens" in cfg

    def test_get_stage_config_with_override(self):
        s = V2Settings.from_dict({
            "stage_models": {
                "generate": "gpt-4o-mini",
                "understand": "gpt-4o-mini",
                "strategize": "gpt-4o-mini",
                "generate_step": "gpt-4o-mini",
                "verify_llm": "gpt-4o-mini",
                "fix": "gpt-4o-mini",
            }
        })
        cfg = s.get_stage_config("generate")
        assert cfg["model"] == "gpt-4o-mini"
        # temperature and max_tokens should still come from STAGE_CONFIGS
        assert cfg["temperature"] == STAGE_CONFIGS["generate"]["temperature"]
