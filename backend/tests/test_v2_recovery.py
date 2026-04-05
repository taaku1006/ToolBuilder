"""Tests for pipeline/v2/stages/recovery.py."""

from datetime import datetime, timedelta

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

    # ---------------------------------------------------------------
    # Phase 1: Circular Fix Detection
    # ---------------------------------------------------------------

    def test_circular_fix_same_hash_triggers_replan(self):
        """Two attempts with identical code_hash → replan."""
        rm = self._make_manager()
        rm.record_attempt(
            code="print('hello')", code_hash="abc123",
            approach="pandas", error_category="syntax_error",
            error_message="SyntaxError", quality_score=0.0,
        )
        rm.record_attempt(
            code="print('hello')", code_hash="abc123",
            approach="pandas", error_category="syntax_error",
            error_message="SyntaxError", quality_score=0.0,
        )
        verdict = VerificationResult(passed=False, execution_error="SyntaxError")
        decision = rm.analyze(verdict, Strategy())
        assert decision.action == "replan"
        assert "循環" in (decision.replan_reason or "")

    def test_circular_fix_different_hashes_no_trigger(self):
        """Different code_hashes → normal fix."""
        rm = self._make_manager()
        rm.record_attempt(
            code="print('a')", code_hash="h1",
            approach="pandas", error_category="syntax_error",
            error_message="SyntaxError", quality_score=0.0,
        )
        rm.record_attempt(
            code="print('b')", code_hash="h2",
            approach="pandas", error_category="syntax_error",
            error_message="SyntaxError", quality_score=0.0,
        )
        verdict = VerificationResult(passed=False, execution_error="SyntaxError")
        decision = rm.analyze(verdict, Strategy())
        assert decision.action == "fix"

    def test_circular_takes_priority_over_repeating_error(self):
        """Circular check fires before repeating-error check."""
        rm = self._make_manager()
        for _ in range(3):
            rm.record_attempt(
                code="pip install pandas", code_hash="same",
                approach="pandas", error_category="syntax_error",
                error_message="SyntaxError: pip", quality_score=0.0,
            )
        verdict = VerificationResult(passed=False, execution_error="SyntaxError: pip")
        decision = rm.analyze(verdict, Strategy())
        assert decision.action == "replan"
        assert "循環" in (decision.replan_reason or "")

    def test_single_attempt_no_circular(self):
        rm = self._make_manager()
        rm.record_attempt(
            code="x=1", code_hash="abc",
            approach="pandas", error_category=None,
            error_message=None, quality_score=0.5,
        )
        verdict = VerificationResult(passed=False)
        decision = rm.analyze(verdict, Strategy())
        assert decision.action == "fix"

    # ---------------------------------------------------------------
    # Phase 2: Time-Windowed Attempt Analysis
    # ---------------------------------------------------------------

    def test_old_errors_not_counted_as_repeating(self):
        """Errors older than window should not trigger repeating-error replan."""
        rm = self._make_manager()
        old_time = datetime.now() - timedelta(minutes=15)

        # 2 old errors
        for i in range(2):
            rm.attempts.append(Attempt(
                code=f"old{i}", code_hash=f"oh{i}", approach="pandas",
                error_category="syntax_error", error_message="SyntaxError: x",
                quality_score=0.0, timestamp=old_time,
            ))
        # 1 recent error
        rm.record_attempt(
            code="new", code_hash="nh1", approach="pandas",
            error_category="syntax_error", error_message="SyntaxError: x",
            quality_score=0.0,
        )
        verdict = VerificationResult(passed=False, execution_error="SyntaxError: x")
        decision = rm.analyze(verdict, Strategy())
        # Only 1 recent → should NOT trigger repeating error
        assert decision.action == "fix"

    def test_recent_errors_still_detected(self):
        """3 recent errors with same message → replan."""
        rm = self._make_manager()
        for i in range(3):
            rm.record_attempt(
                code=f"code_{i}", code_hash=f"h{i}",
                approach="pandas", error_category="syntax_error",
                error_message="SyntaxError: same",
                quality_score=0.0,
            )
        verdict = VerificationResult(passed=False, execution_error="SyntaxError: same")
        decision = rm.analyze(verdict, Strategy())
        assert decision.action == "replan"

    def test_old_quality_not_stagnant(self):
        """Old stagnant scores should not trigger replan."""
        rm = self._make_manager()
        old_time = datetime.now() - timedelta(minutes=15)

        for i in range(2):
            rm.attempts.append(Attempt(
                code=f"old{i}", code_hash=f"oh{i}", approach="pandas",
                error_category=None, error_message=None,
                quality_score=0.3, timestamp=old_time,
            ))
        rm.record_attempt(
            code="new", code_hash="nh1", approach="pandas",
            error_category=None, error_message=None,
            quality_score=0.3,
        )
        verdict = VerificationResult(passed=False, quality_score=0.3, combined_score=0.3)
        decision = rm.analyze(verdict, Strategy())
        assert decision.action == "fix"

    def test_escalate_counts_all_attempts(self):
        """Escalation (6+) counts ALL attempts regardless of time."""
        rm = self._make_manager()
        old_time = datetime.now() - timedelta(minutes=20)

        for i in range(6):
            rm.attempts.append(Attempt(
                code=f"c{i}", code_hash=f"h{i}", approach=f"a{i}",
                error_category=None, error_message=None,
                quality_score=float(i) / 10, timestamp=old_time,
            ))
        verdict = VerificationResult(passed=False)
        decision = rm.analyze(verdict, Strategy())
        assert decision.action == "escalate"

    # ---------------------------------------------------------------
    # Existing tests
    # ---------------------------------------------------------------

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
