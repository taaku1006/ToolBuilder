"""Tests for pipeline/v2/models.py — data model validation."""

import pytest

from pipeline.v2.models import (
    Attempt,
    ComplexitySignals,
    FileContext,
    FixRequest,
    GenerateResult,
    Issue,
    MemoryContext,
    PipelineState,
    RecoveryDecision,
    Strategy,
    StrategyStep,
    StepVerification,
    TaskClassification,
    VerificationResult,
    VerifyFixResult,
)


class TestFileContext:
    def test_to_prompt_empty(self):
        ctx = FileContext()
        assert ctx.to_prompt() == ""

    def test_to_prompt_with_sheets(self):
        ctx = FileContext(
            sheets=[
                {"name": "Sheet1", "headers": ["A", "B"], "types": {"A": "string"}, "total_rows": 10}
            ],
            has_merged_cells=True,
        )
        prompt = ctx.to_prompt()
        assert "Sheet1" in prompt
        assert "10 rows" in prompt
        assert "merged_cells" in prompt

    def test_get_feature_keys_empty(self):
        ctx = FileContext()
        assert ctx.get_feature_keys() == []

    def test_get_feature_keys_with_features(self):
        ctx = FileContext(
            sheets=[{"name": "S1"}, {"name": "S2"}],
            has_merged_cells=True,
            has_formulas=True,
            complexity_signals=ComplexitySignals(nested_headers=True),
        )
        keys = ctx.get_feature_keys()
        assert "merged_cells" in keys
        assert "formulas" in keys
        assert "nested_headers" in keys
        assert "multi_sheet" in keys


class TestStrategy:
    def test_to_prompt_simple(self):
        s = Strategy(approach="pandas", key_functions=["pivot_table"])
        prompt = s.to_prompt()
        assert "pandas" in prompt
        assert "pivot_table" in prompt

    def test_to_prompt_with_steps(self):
        s = Strategy(
            approach="openpyxl",
            steps=[StrategyStep(id=1, action="read", verify="print shape")],
        )
        prompt = s.to_prompt()
        assert "Steps:" in prompt
        assert "1. read" in prompt


class TestMemoryContext:
    def test_to_prompt_empty(self):
        mc = MemoryContext()
        assert mc.to_prompt() == ""

    def test_to_prompt_with_data(self):
        mc = MemoryContext(
            patterns=[{"task_type": "pivot", "winning_strategy": {"approach": "pandas"}}],
            gotchas=[{"detection": "merged cells", "fix": "unmerge first"}],
        )
        prompt = mc.to_prompt()
        assert "pivot" in prompt
        assert "merged cells" in prompt


class TestPipelineState:
    def test_mutable(self):
        """PipelineState must be mutable (not frozen)."""
        state = PipelineState(task="test")
        state.replan_count = 1
        assert state.replan_count == 1

    def test_defaults(self):
        state = PipelineState()
        assert state.task == ""
        assert state.replan_count == 0
        assert state.max_replan == 2
        assert state.generation_result is None


class TestFrozenModels:
    def test_issue_frozen(self):
        issue = Issue(level="execution", description="err", severity="critical")
        with pytest.raises(AttributeError):
            issue.level = "quality"  # type: ignore[misc]

    def test_attempt_frozen(self):
        a = Attempt(code="x=1", code_hash="abc")
        with pytest.raises(AttributeError):
            a.code = "y=2"  # type: ignore[misc]

    def test_verification_result_frozen(self):
        vr = VerificationResult(passed=True, combined_score=0.9)
        with pytest.raises(AttributeError):
            vr.passed = False  # type: ignore[misc]
