"""RecoveryManager — failure analysis without LLM calls.

Tracks attempt history, detects stuck patterns (repeating errors,
quality stagnation), and decides whether to fix, replan, or escalate.
Analogous to Auto-Claude's post_session_processing + RecoveryManager.
"""

from __future__ import annotations

from datetime import datetime
from difflib import SequenceMatcher

from pipeline.v2.models import (
    Attempt,
    FixRequest,
    RecoveryDecision,
    Strategy,
    VerificationResult,
)


class RecoveryManager:
    """Pure-Python recovery analysis — zero LLM calls."""

    def __init__(self) -> None:
        self.attempts: list[Attempt] = []

    def record_attempt(
        self,
        *,
        code: str,
        code_hash: str,
        approach: str,
        error_category: str | None,
        error_message: str | None,
        quality_score: float,
    ) -> None:
        self.attempts.append(Attempt(
            code=code,
            code_hash=code_hash,
            approach=approach,
            error_category=error_category,
            error_message=error_message,
            quality_score=quality_score,
            timestamp=datetime.now(),
        ))

    def analyze(
        self,
        verdict: VerificationResult,
        strategy: Strategy,
    ) -> RecoveryDecision:
        """Decide recovery action based on attempt history and verdict."""

        # Repeating the same error 3+ times → replan
        if self._is_repeating_error():
            return RecoveryDecision(
                action="replan",
                replan_reason="同一エラーが3回繰り返し。アプローチ変更が必要",
                suggested_strategy_change=self._suggest_alternative(strategy),
            )

        # Quality not improving → replan
        if self._is_quality_stagnant():
            return RecoveryDecision(
                action="replan",
                replan_reason="品質スコアが2回連続で改善なし",
                suggested_strategy_change=self._suggest_quality_improvement(strategy),
            )

        # Too many attempts → escalate
        if len(self.attempts) >= 6:
            return RecoveryDecision(action="escalate")

        # Normal fix
        return RecoveryDecision(
            action="fix",
            fix_request=self._build_fix_request(verdict),
        )

    def get_recovery_hints(self) -> str:
        """Format past attempts as hints for the Fixer prompt."""
        if not self.attempts:
            return ""
        hints = "## Previous Failed Approaches (DO NOT repeat these):\n"
        for a in self.attempts:
            hints += f"- Approach: {a.approach}\n"
            if a.error_message:
                hints += f"  Error: {a.error_message[:200]}\n"
        hints += "\nYou MUST try a fundamentally different approach.\n"
        return hints

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_repeating_error(self) -> bool:
        """True if the last 3 errors are highly similar."""
        if len(self.attempts) < 3:
            return False
        recent = self.attempts[-3:]
        errors = [a.error_message for a in recent if a.error_message]
        if len(errors) < 3:
            return False
        return all(
            SequenceMatcher(None, errors[i], errors[i + 1]).ratio() > 0.8
            for i in range(len(errors) - 1)
        )

    def _is_quality_stagnant(self) -> bool:
        """True if quality score has not improved for last 3 attempts."""
        if len(self.attempts) < 3:
            return False
        scores = [a.quality_score for a in self.attempts[-3:]]
        return scores[-1] <= scores[-2] <= scores[-3]

    def _suggest_alternative(self, strategy: Strategy) -> str:
        used = {a.approach for a in self.attempts}
        if "pandas" in strategy.approach and "openpyxl" not in str(used):
            return "openpyxl に切り替え"
        if "openpyxl" in strategy.approach and "pandas" not in str(used):
            return "pandas に切り替え"
        return "完全に異なるアルゴリズムで再試行"

    def _suggest_quality_improvement(self, strategy: Strategy) -> str:
        return "出力フォーマットやデータ処理ロジックを根本的に見直し"

    def _build_fix_request(self, verdict: VerificationResult) -> FixRequest:
        return FixRequest(
            issues=list(verdict.issues),
            must_not_repeat=[
                a.error_message for a in self.attempts if a.error_message
            ],
            previous_approaches=[a.approach for a in self.attempts],
            fix_guidance=verdict.fix_guidance,
        )
