"""Tests for Auto-Claude gap features — TDD RED phase.

Feature 1: Predictive Bug Prevention (checklist)
Feature 2: Risk-Based Verification Strategy
Feature 3: QA Fixer Loop (quality fix path)
Feature 4: Phase-specific thinking_tokens
Feature 5: Session Insight Extraction
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.v2.models import (
    FileContext,
    MemoryContext,
    PipelineState,
    Strategy,
    TaskClassification,
    VerifyFixResult,
    Attempt,
    Issue,
    VerificationResult,
)


# ---------------------------------------------------------------
# Feature 1: Predictive Bug Prevention
# ---------------------------------------------------------------


class TestPredictiveBugPrevention:
    """MemoryContext should generate a checklist from gotchas."""

    def test_to_checklist_from_gotchas(self) -> None:
        ctx = MemoryContext(
            gotchas=[
                {"_key": "pip_install_in_code", "fix": "pip install 文をコードに含めないこと。", "confidence": 0.9},
                {"_key": "encoding_error", "fix": "pd.read_csv(encoding='cp932') を試す。", "confidence": 0.7},
            ],
        )
        checklist = ctx.to_checklist()
        assert "pip install" in checklist
        assert "encoding" in checklist or "cp932" in checklist
        assert "チェックリスト" in checklist or "checklist" in checklist.lower()

    def test_to_checklist_empty_when_no_gotchas(self) -> None:
        ctx = MemoryContext()
        assert ctx.to_checklist() == ""

    def test_to_checklist_sorted_by_confidence(self) -> None:
        ctx = MemoryContext(
            gotchas=[
                {"_key": "low", "fix": "low priority fix", "confidence": 0.3},
                {"_key": "high", "fix": "high priority fix", "confidence": 0.95},
            ],
        )
        checklist = ctx.to_checklist()
        high_pos = checklist.find("high priority")
        low_pos = checklist.find("low priority")
        assert high_pos < low_pos, "Higher confidence should appear first"


# ---------------------------------------------------------------
# Feature 2: Risk-Based Verification Strategy
# ---------------------------------------------------------------


class TestRiskBasedVerification:
    """Verification should adjust intensity based on risk factors."""

    def test_high_risk_increases_attempts(self) -> None:
        from pipeline.v2.stages.verify_fix import _assess_risk
        from pipeline.v2.config import V2Settings

        state = MagicMock()
        state.strategy.risk_factors = ["merged_cells", "encoding_error", "nan_handling"]
        state.classification.complexity = "standard"

        v2 = V2Settings()
        base = v2.max_attempts["standard"]
        adjusted, force_l3 = _assess_risk(state, v2)

        assert adjusted > base
        assert force_l3 is True

    def test_no_risk_simple_reduces_attempts(self) -> None:
        from pipeline.v2.stages.verify_fix import _assess_risk
        from pipeline.v2.config import V2Settings

        state = MagicMock()
        state.strategy.risk_factors = []
        state.classification.complexity = "simple"

        v2 = V2Settings()
        base = v2.max_attempts["simple"]
        adjusted, force_l3 = _assess_risk(state, v2)

        assert adjusted <= base
        assert force_l3 is False

    def test_standard_risk_unchanged(self) -> None:
        from pipeline.v2.stages.verify_fix import _assess_risk
        from pipeline.v2.config import V2Settings

        state = MagicMock()
        state.strategy.risk_factors = ["merged_cells"]
        state.classification.complexity = "standard"

        v2 = V2Settings()
        base = v2.max_attempts["standard"]
        adjusted, force_l3 = _assess_risk(state, v2)

        assert adjusted == base


# ---------------------------------------------------------------
# Feature 3: QA Fixer Loop — Quality Fix Path
# ---------------------------------------------------------------


class TestQualityFixPath:
    """Fix requests should include quality-specific guidance when quality issues exist."""

    def test_quality_issues_add_guidance(self) -> None:
        from pipeline.v2.stages.recovery import RecoveryManager

        rm = RecoveryManager()
        rm.record_attempt(
            code="import pandas as pd\ndf = pd.read_excel('test.xlsx')\ndf.to_excel('out.xlsx')",
            code_hash="h1", approach="pandas",
            error_category=None, error_message=None,
            quality_score=0.4,
        )

        verdict = VerificationResult(
            passed=False,
            execution_error=None,
            quality_score=0.4,
            combined_score=0.4,
            issues=[Issue(level="quality", description="出力にシートが不足", severity="major")],
            fix_guidance="不足シートを追加してください",
        )

        decision = rm.analyze(verdict, Strategy())
        assert decision.action == "fix"
        assert decision.fix_request is not None
        assert any(i.level == "quality" for i in decision.fix_request.issues)

    def test_execution_error_not_quality_path(self) -> None:
        from pipeline.v2.stages.recovery import RecoveryManager

        rm = RecoveryManager()
        rm.record_attempt(
            code="bad code", code_hash="h1", approach="pandas",
            error_category="syntax_error", error_message="SyntaxError",
            quality_score=0.0,
        )

        verdict = VerificationResult(
            passed=False,
            execution_error="SyntaxError: invalid syntax",
            issues=[Issue(level="execution", description="SyntaxError", severity="critical")],
        )

        decision = rm.analyze(verdict, Strategy())
        assert decision.action == "fix"
        assert all(i.level == "execution" for i in decision.fix_request.issues)


# ---------------------------------------------------------------
# Feature 4: Phase-specific thinking_tokens
# ---------------------------------------------------------------


class TestPhaseThinkingTokens:
    """STAGE_CONFIGS should support thinking_tokens field."""

    def test_stage_configs_have_thinking_tokens(self) -> None:
        from pipeline.v2.config import STAGE_CONFIGS

        for stage, cfg in STAGE_CONFIGS.items():
            assert "thinking_tokens" in cfg, f"{stage} missing thinking_tokens"

    def test_v2settings_stage_thinking(self) -> None:
        from pipeline.v2.config import V2Settings

        v2 = V2Settings.from_dict({
            "stage_thinking": {"generate": 4096, "fix": 4096},
        })
        cfg = v2.get_stage_config("generate")
        assert cfg["thinking_tokens"] == 4096

    def test_default_thinking_tokens_zero(self) -> None:
        from pipeline.v2.config import V2Settings

        v2 = V2Settings()
        cfg = v2.get_stage_config("generate")
        assert cfg["thinking_tokens"] == 0


# ---------------------------------------------------------------
# Feature 5: Session Insight Extraction
# ---------------------------------------------------------------


class TestSessionInsightExtraction:
    """Learn phase should extract and save structured insights."""

    def test_save_and_load_insights(self, tmp_path: Path) -> None:
        from memory.store import MemoryStore

        store = MemoryStore(tmp_path)
        store.save_insight(
            pattern="csv_encoding_failure",
            trigger="CSVファイルで UnicodeDecodeError",
            prevention="pd.read_csv(encoding='cp932') を試す",
            source_task_type="aggregation",
        )

        insights = store.load_insights()
        assert len(insights) == 1
        assert insights[0]["pattern"] == "csv_encoding_failure"
        assert insights[0]["occurrences"] == 1

    def test_insight_increments_on_duplicate(self, tmp_path: Path) -> None:
        from memory.store import MemoryStore

        store = MemoryStore(tmp_path)
        for _ in range(3):
            store.save_insight(
                pattern="pip_in_code",
                trigger="pip install in Python file",
                prevention="Never include pip install",
                source_task_type="general",
            )

        insights = store.load_insights()
        pip_insight = [i for i in insights if i["pattern"] == "pip_in_code"]
        assert len(pip_insight) == 1
        assert pip_insight[0]["occurrences"] == 3
        assert pip_insight[0]["confidence"] > 0.6

    def test_extract_insights_from_attempts(self) -> None:
        from pipeline.v2.stages.learn import _extract_insights

        attempts = [
            Attempt(code="c1", code_hash="h1", approach="pandas",
                    error_category="encoding_error", error_message="UnicodeDecodeError",
                    quality_score=0.0, timestamp=datetime.now()),
            Attempt(code="c2", code_hash="h2", approach="pandas",
                    error_category="encoding_error", error_message="UnicodeDecodeError: cp932",
                    quality_score=0.0, timestamp=datetime.now()),
        ]

        insights = _extract_insights(
            attempts=attempts,
            task_type="aggregation",
            strategy="pandas",
            passed=False,
            replan_count=1,
        )
        assert len(insights) >= 1
        assert any(i["pattern"] == "encoding_error" for i in insights)
