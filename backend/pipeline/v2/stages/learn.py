"""Stage 4: LEARN — Record success/failure patterns to file-based memory.

Writes patterns, gotchas, and session metrics to memory/data/*.json.
Zero LLM calls — pure Python.
"""

from __future__ import annotations

import logging
from pathlib import Path

from memory.store import MemoryStore
from pipeline.v2.models import PipelineState

logger = logging.getLogger(__name__)


class LearnPhase:
    """Record session results for future learning."""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        if data_dir is None:
            data_dir = Path(__file__).resolve().parents[3] / "memory" / "data"
        self._store = MemoryStore(Path(data_dir))

    def learn(self, state: PipelineState) -> None:
        result = state.verify_fix_result
        if result is None:
            logger.info("Learn: no verify_fix_result to learn from")
            return

        # Save successful pattern
        if result.passed:
            pattern_key = f"{state.classification.task_type}_{state.strategy.approach}"
            self._store.save_pattern(
                key=pattern_key,
                file_features=state.file_context.get_feature_keys(),
                task_type=state.classification.task_type,
                winning_strategy={
                    "approach": state.strategy.approach,
                    "key_functions": list(state.strategy.key_functions),
                    "preprocessing": list(state.strategy.preprocessing_steps),
                },
                quality_score=result.best_score,
            )

        # Save gotchas from failed attempts (success or fail)
        for attempt in result.attempts:
            if attempt.error_category and attempt.error_message:
                gotcha_key = attempt.error_category
                self._store.save_gotcha(
                    key=gotcha_key,
                    detection=attempt.error_message[:200],
                    fix=f"Approach '{attempt.approach}' caused: {attempt.error_message[:100]}",
                )

        # Save session metrics
        self._store.save_session(
            task_type=state.classification.task_type,
            complexity=state.classification.complexity,
            strategy=state.strategy.approach,
            attempts=len(result.attempts),
            replan_count=state.replan_count,
            final_score=result.best_score,
            passed=result.passed,
        )

        logger.info(
            "Learn: session recorded",
            extra={
                "task_type": state.classification.task_type,
                "passed": result.passed,
                "final_score": result.best_score,
            },
        )
