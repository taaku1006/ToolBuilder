"""Tests for the evaluation-driven debug loop (Phase F)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from pipeline.eval_debug_loop import (
    EvalDebugAttempt,
    EvalDebugResult,
    run_eval_debug_loop,
)
from infra.sandbox import ExecutionResult


def _write_xlsx(path: Path, data: dict[str, list]) -> str:
    df = pd.DataFrame(data)
    df.to_excel(str(path), index=False)
    return str(path)


class TestEvalDebugAttempt:
    def test_frozen(self):
        a = EvalDebugAttempt(
            retry_num=1, mechanical_score=0.5, eval_reasoning=None,
            comparison_summary="summary", fixed_code="code", success=False,
        )
        with pytest.raises(AttributeError):
            a.success = True  # type: ignore[misc]


class TestEvalDebugResult:
    def test_frozen(self):
        r = EvalDebugResult(
            final_code="code", final_score=0.9, success=True,
            attempts=[], total_retries=0,
        )
        with pytest.raises(AttributeError):
            r.success = False  # type: ignore[misc]

    def test_fields(self):
        r = EvalDebugResult(
            final_code="x", final_score=0.75, success=False,
            attempts=[], total_retries=3,
        )
        assert r.final_score == 0.75
        assert r.total_retries == 3


class TestRunEvalDebugLoop:
    @pytest.fixture()
    def tmp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture()
    def mock_client(self):
        client = MagicMock()
        client.total_tokens = 0
        client.prompt_tokens = 0
        client.completion_tokens = 0
        client.api_calls = 0
        return client

    def _make_exec_result(self, success: bool, output_files: list[str] | None = None) -> ExecutionResult:
        return ExecutionResult(
            stdout="done", stderr="", elapsed_ms=100,
            output_files=output_files or [], success=success,
        )

    @pytest.mark.asyncio
    async def test_initial_quality_above_threshold(self, tmp_dir, mock_client):
        """Output matches expected on first try -> 0 retries."""
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {"A": [1, 2], "B": [3, 4]})
        actual = _write_xlsx(tmp_dir / "actual.xlsx", {"A": [1, 2], "B": [3, 4]})

        def fake_execute(code, **kwargs):
            return self._make_exec_result(True, [actual])

        result = await run_eval_debug_loop(
            code="print('ok')",
            task="test",
            expected_file_path=expected,
            openai_client=mock_client,
            sandbox_execute=fake_execute,
            quality_threshold=0.8,
        )

        assert result.success is True
        assert result.total_retries == 0
        assert result.final_score >= 0.8

    @pytest.mark.asyncio
    async def test_retry_improves_quality(self, tmp_dir, mock_client):
        """First output is wrong, retry produces correct output."""
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {"A": [1, 2], "B": [3, 4]})
        bad_output = _write_xlsx(tmp_dir / "bad.xlsx", {"X": [99], "Y": [99]})
        good_output = _write_xlsx(tmp_dir / "good.xlsx", {"A": [1, 2], "B": [3, 4]})

        call_count = 0

        def fake_execute(code, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return self._make_exec_result(True, [bad_output])
            return self._make_exec_result(True, [good_output])

        mock_client.generate_code.return_value = "improved code"

        result = await run_eval_debug_loop(
            code="print('ok')",
            task="test",
            expected_file_path=expected,
            openai_client=mock_client,
            sandbox_execute=fake_execute,
            quality_threshold=0.8,
        )

        assert result.success is True
        assert result.total_retries == 1
        assert len(result.attempts) == 1

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, tmp_dir, mock_client):
        """Output never improves -> fail after max retries."""
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {"A": [1, 2], "B": [3, 4]})
        bad_output = _write_xlsx(tmp_dir / "bad.xlsx", {"X": [99], "Y": [99]})

        def fake_execute(code, **kwargs):
            return self._make_exec_result(True, [bad_output])

        mock_client.generate_code.return_value = "still bad code"

        result = await run_eval_debug_loop(
            code="print('ok')",
            task="test",
            expected_file_path=expected,
            openai_client=mock_client,
            sandbox_execute=fake_execute,
            max_retries=2,
            quality_threshold=0.8,
        )

        assert result.success is False
        assert result.total_retries == 2
        assert len(result.attempts) == 2

    @pytest.mark.asyncio
    async def test_execution_failure_returns_immediately(self, tmp_dir, mock_client):
        """Code crashes -> return immediately with score 0."""
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {"A": [1]})

        def fake_execute(code, **kwargs):
            return self._make_exec_result(False)

        result = await run_eval_debug_loop(
            code="raise Exception()",
            task="test",
            expected_file_path=expected,
            openai_client=mock_client,
            sandbox_execute=fake_execute,
        )

        assert result.success is False
        assert result.final_score == 0.0
        assert result.total_retries == 0

    @pytest.mark.asyncio
    async def test_no_output_files(self, tmp_dir, mock_client):
        """Code runs but produces no files -> score 0."""
        expected = _write_xlsx(tmp_dir / "expected.xlsx", {"A": [1]})

        def fake_execute(code, **kwargs):
            return self._make_exec_result(True, [])

        result = await run_eval_debug_loop(
            code="print('ok')",
            task="test",
            expected_file_path=expected,
            openai_client=mock_client,
            sandbox_execute=fake_execute,
        )

        assert result.success is False
        assert result.final_score == 0.0
        assert result.total_retries == 0
