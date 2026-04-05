"""Tests for pipeline/v2/config.py — RED phase (config.py not yet implemented)."""

import pytest


class TestStageConfigs:
    def test_stage_configs_has_required_stages(self):
        from pipeline.v2.config import STAGE_CONFIGS

        required = ["understand", "strategize", "generate", "generate_step", "verify_llm", "fix"]
        for stage in required:
            assert stage in STAGE_CONFIGS, f"Missing stage: {stage}"

    def test_each_config_has_model_and_temperature(self):
        from pipeline.v2.config import STAGE_CONFIGS

        for stage, cfg in STAGE_CONFIGS.items():
            assert "model" in cfg, f"{stage} missing 'model'"
            assert "temperature" in cfg, f"{stage} missing 'temperature'"
            assert "max_tokens" in cfg, f"{stage} missing 'max_tokens'"

    def test_understand_uses_mini(self):
        from pipeline.v2.config import STAGE_CONFIGS

        assert "mini" in STAGE_CONFIGS["understand"]["model"]

    def test_generate_uses_full_model(self):
        from pipeline.v2.config import STAGE_CONFIGS

        assert STAGE_CONFIGS["generate"]["model"] == "gpt-4o"


class TestV2Settings:
    def test_default_max_attempts(self):
        from pipeline.v2.config import V2Settings

        s = V2Settings()
        assert s.max_attempts["simple"] == 2
        assert s.max_attempts["standard"] == 4
        assert s.max_attempts["complex"] == 6

    def test_default_thresholds(self):
        from pipeline.v2.config import V2Settings

        s = V2Settings()
        assert s.quality_threshold == 0.85
        assert s.semantic_threshold == 7.0
        assert s.pass_threshold == 0.75

    def test_from_v2_config_dict(self):
        from pipeline.v2.config import V2Settings

        cfg = {
            "max_replan": 5,
            "quality_threshold": 0.9,
            "memory_enabled": False,
        }
        s = V2Settings.from_dict(cfg)
        assert s.max_replan == 5
        assert s.quality_threshold == 0.9
        assert s.memory_enabled is False
