"""Stage 4: LEARN — Record success/failure patterns (Phase 1: stub).

Full implementation with file-based memory will be added in Phase 2.
Currently logs metrics only.
"""

from __future__ import annotations

import logging

from pipeline.v2.models import PipelineState

logger = logging.getLogger(__name__)


class LearnPhase:
    """Record session results for future learning. Phase 1: logging stub."""

    def learn(self, state: PipelineState) -> None:
        result = state.verify_fix_result
        if result is None:
            logger.info("Learn: no verify_fix_result to learn from")
            return

        logger.info(
            "Learn: session complete",
            extra={
                "task_type": state.classification.task_type,
                "complexity": state.classification.complexity,
                "strategy": state.strategy.approach,
                "attempts": len(result.attempts),
                "replan_count": state.replan_count,
                "final_score": result.best_score,
                "passed": result.passed,
            },
        )
