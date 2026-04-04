"""Tests for pipeline/v2/stages/recovery.py — RED phase."""

import pytest

from pipeline.v2.models import Attempt, Issue, VerificationResult, Strategy


class TestRecoveryManager:
    def _make_manager(self):
        from pipeline.v2.stages.recovery import RecoveryManager
        return RecoveryManager()

    def test_first_failure_returns_fix(self):
        rm = self._make_manager()
        rm.record_attempt(
            code="x=1", code_hash="a", approach="pandas",
            error_category="runtime_error", error_message="NameError: foo",
            quality_score=0.0,
        )
        verdict = VerificationResult(
            passed=False,
            execution_error="NameError: foo",
            issues=[Issue(level="execution", description="NameError: foo", severity="critical")],
            fix_guidance="Fix the NameError",
        )
        decision = rm.analyze(verdict, Strategy())
        assert decision.action == "fix"
        assert decision.fix_request is not None
        assert "NameError: foo" in decision.fix_request.must_not_repeat

    def test_repeating_error_triggers_replan(self):
        rm = self._make_manager()
        for i in range(3):
            rm.record_attempt(
                code=f"x={i}", code_hash=f"h{i}", approach="pandas",
                error_category="runtime_error",
                error_message="TypeError: unsupported operand",
                quality_score=0.0,
            )
        verdict = VerificationResult(
            passed=False,
            execution_error="TypeError: unsupported operand",
            issues=[Issue(level="execution", description="TypeError", severity="critical")],
        )
        decision = rm.analyze(verdict, Strategy(approach="pandas"))
        assert decision.action == "replan"
        assert decision.replan_reason is not None

    def test_quality_stagnation_triggers_replan(self):
        rm = self._make_manager()
        for score in [0.5, 0.5, 0.5]:
            rm.record_attempt(
                code="x=1", code_hash="h", approach="pandas",
                error_category=None, error_message=None,
                quality_score=score,
            )
        verdict = VerificationResult(passed=False, quality_score=0.5, combined_score=0.5)
        decision = rm.analyze(verdict, Strategy())
        assert decision.action == "replan"

    def test_escalate_after_max_attempts(self):
        rm = self._make_manager()
        # 6 attempts with very different errors AND improving quality
        errors = [
            "ImportError: no module named foo",
            "TypeError: cannot add str and int",
            "KeyError: column_x not found",
            "ValueError: invalid literal for int",
            "FileNotFoundError: output.xlsx",
            "IndexError: list index out of range",
        ]
        scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        for i in range(6):
            rm.record_attempt(
                code=f"x={i}", code_hash=f"h{i}", approach=f"approach_{i}",
                error_category="runtime_error",
                error_message=errors[i],
                quality_score=scores[i],
            )
        verdict = VerificationResult(passed=False)
        decision = rm.analyze(verdict, Strategy())
        assert decision.action == "escalate"

    def test_get_recovery_hints_empty(self):
        rm = self._make_manager()
        assert rm.get_recovery_hints() == ""

    def test_get_recovery_hints_with_attempts(self):
        rm = self._make_manager()
        rm.record_attempt(
            code="x=1", code_hash="a", approach="pandas",
            error_category="runtime_error", error_message="KeyError",
            quality_score=0.0,
        )
        hints = rm.get_recovery_hints()
        assert "pandas" in hints
        assert "KeyError" in hints
        assert "DO NOT repeat" in hints

    def test_suggest_alternative_pandas_to_openpyxl(self):
        rm = self._make_manager()
        for i in range(3):
            rm.record_attempt(
                code=f"x={i}", code_hash=f"h{i}", approach="pandas",
                error_category="runtime_error",
                error_message="Same error always",
                quality_score=0.0,
            )
        verdict = VerificationResult(passed=False, execution_error="Same error always")
        decision = rm.analyze(verdict, Strategy(approach="pandas"))
        assert decision.action == "replan"
        assert decision.suggested_strategy_change is not None
        assert "openpyxl" in decision.suggested_strategy_change
