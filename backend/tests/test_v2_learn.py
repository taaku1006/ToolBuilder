"""Tests for pipeline/v2/stages/learn.py — full implementation."""

import pytest
from pathlib import Path

from pipeline.v2.models import (
    Attempt,
    FileContext,
    ComplexitySignals,
    PipelineState,
    Strategy,
    TaskClassification,
    VerifyFixResult,
)


@pytest.fixture
def memory_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "patterns.json").write_text("{}")
    (data_dir / "gotchas.json").write_text("{}")
    (data_dir / "session_log.json").write_text("[]")
    return data_dir


def _make_state(passed: bool = True, attempts: list[Attempt] | None = None) -> PipelineState:
    return PipelineState(
        task="合計を出して",
        file_id="test_file",
        file_context=FileContext(
            sheets=[{"name": "Sheet1", "headers": ["A", "B"]}],
            has_merged_cells=True,
            complexity_signals=ComplexitySignals(multi_sheet_refs=False),
        ),
        classification=TaskClassification(complexity="standard", task_type="aggregation"),
        strategy=Strategy(approach="pandas", key_functions=["sum"]),
        verify_fix_result=VerifyFixResult(
            best_code="import pandas as pd",
            best_score=0.9 if passed else 0.3,
            attempts=attempts or [],
            passed=passed,
        ),
    )


class TestLearnPhase:
    def test_learn_saves_pattern_on_success(self, memory_dir):
        from pipeline.v2.stages.learn import LearnPhase
        from memory.store import MemoryStore

        state = _make_state(passed=True)
        learn = LearnPhase(memory_dir)
        learn.learn(state)

        store = MemoryStore(memory_dir)
        patterns = store.load_patterns()
        assert len(patterns) > 0
        # Should contain aggregation pattern
        found = any(p.get("task_type") == "aggregation" for p in patterns.values())
        assert found

    def test_learn_saves_gotcha_from_failed_attempts(self, memory_dir):
        from pipeline.v2.stages.learn import LearnPhase
        from memory.store import MemoryStore

        attempts = [
            Attempt(
                code="x=1", code_hash="a", approach="pandas",
                error_category="runtime_error",
                error_message="KeyError: 'missing_col'",
                quality_score=0.0,
            ),
        ]
        state = _make_state(passed=True, attempts=attempts)
        state.verify_fix_result = VerifyFixResult(
            best_code="fixed", best_score=0.9,
            attempts=attempts, passed=True,
        )
        learn = LearnPhase(memory_dir)
        learn.learn(state)

        store = MemoryStore(memory_dir)
        gotchas = store.load_gotchas()
        assert len(gotchas) > 0

    def test_learn_saves_session_log(self, memory_dir):
        from pipeline.v2.stages.learn import LearnPhase
        from memory.store import MemoryStore

        state = _make_state(passed=True)
        learn = LearnPhase(memory_dir)
        learn.learn(state)

        store = MemoryStore(memory_dir)
        log = store.load_session_log()
        assert len(log) == 1
        assert log[0]["task_type"] == "aggregation"
        assert log[0]["passed"] is True

    def test_learn_no_crash_on_empty_result(self, memory_dir):
        from pipeline.v2.stages.learn import LearnPhase

        state = PipelineState(task="test")
        state.verify_fix_result = None
        learn = LearnPhase(memory_dir)
        learn.learn(state)  # Should not raise
