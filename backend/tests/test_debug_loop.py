"""Unit tests for services.debug_loop.

TDD: tests written FIRST, implementation follows.
All OpenAI calls and sandbox executions are mocked.

Test cases:
- DebugAttempt and DebugResult are frozen dataclasses
- Immediate success (0 retries)
- Success after 1 retry
- Success after max_retries
- Failure after max_retries exhausted
- attempts list populated correctly
- DebugResult.total_retries reflects actual retry count
- Empty / None stderr edge cases
"""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.openai_client import OpenAIClient
from services.sandbox import ExecutionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_exec_result(
    success: bool,
    stdout: str = "",
    stderr: str = "",
) -> ExecutionResult:
    return ExecutionResult(
        stdout=stdout,
        stderr=stderr,
        elapsed_ms=100,
        output_files=[],
        success=success,
    )


def _make_openai_client(fixed_code: str = "print('fixed')") -> OpenAIClient:
    """Return a mock OpenAIClient whose generate_code returns fixed_code."""
    client = MagicMock(spec=OpenAIClient)
    client.generate_code.return_value = fixed_code
    return client


def _make_sandbox_sequence(results: list[ExecutionResult]) -> Callable:
    """Return a mock sandbox callable that returns results in order."""
    call_count = [0]

    def sandbox(code: str, **kwargs):  # noqa: ANN001
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(results):
            return results[idx]
        # default: success
        return _make_exec_result(success=True, stdout="default")

    return sandbox


# ---------------------------------------------------------------------------
# DebugAttempt dataclass
# ---------------------------------------------------------------------------


class TestDebugAttempt:
    """DebugAttempt must be a frozen (immutable) dataclass."""

    def test_frozen_dataclass(self) -> None:
        from services.debug_loop import DebugAttempt

        attempt = DebugAttempt(
            retry_num=1,
            error="NameError: name 'x' is not defined",
            fixed_code="x = 1\nprint(x)",
            success=True,
        )
        with pytest.raises(Exception):
            attempt.retry_num = 2  # type: ignore[misc]

    def test_fields(self) -> None:
        from services.debug_loop import DebugAttempt

        attempt = DebugAttempt(
            retry_num=2,
            error="SyntaxError",
            fixed_code="print('ok')",
            success=False,
        )
        assert attempt.retry_num == 2
        assert attempt.error == "SyntaxError"
        assert attempt.fixed_code == "print('ok')"
        assert attempt.success is False


# ---------------------------------------------------------------------------
# DebugResult dataclass
# ---------------------------------------------------------------------------


class TestDebugResult:
    """DebugResult must be a frozen (immutable) dataclass."""

    def test_frozen_dataclass(self) -> None:
        from services.debug_loop import DebugAttempt, DebugResult

        result = DebugResult(
            final_code="print('done')",
            final_stdout="done\n",
            final_stderr="",
            success=True,
            attempts=[],
            total_retries=0,
        )
        with pytest.raises(Exception):
            result.success = False  # type: ignore[misc]

    def test_fields(self) -> None:
        from services.debug_loop import DebugAttempt, DebugResult

        attempt = DebugAttempt(
            retry_num=1,
            error="err",
            fixed_code="code",
            success=True,
        )
        result = DebugResult(
            final_code="final code",
            final_stdout="output",
            final_stderr="",
            success=True,
            attempts=[attempt],
            total_retries=1,
        )
        assert result.final_code == "final code"
        assert result.final_stdout == "output"
        assert result.final_stderr == ""
        assert result.success is True
        assert len(result.attempts) == 1
        assert result.total_retries == 1


# ---------------------------------------------------------------------------
# run_debug_loop — immediate success (no retries needed)
# ---------------------------------------------------------------------------


class TestRunDebugLoopImmediateSuccess:
    """When the first execution succeeds, no retries are performed."""

    @pytest.mark.asyncio
    async def test_success_on_first_run_returns_success(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([_make_exec_result(success=True, stdout="ok\n")])
        client = _make_openai_client()

        result = await run_debug_loop(
            code="print('ok')",
            task="test task",
            openai_client=client,
            sandbox_execute=sandbox,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_success_on_first_run_zero_retries(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([_make_exec_result(success=True, stdout="ok\n")])
        client = _make_openai_client()

        result = await run_debug_loop(
            code="print('ok')",
            task="test task",
            openai_client=client,
            sandbox_execute=sandbox,
        )

        assert result.total_retries == 0
        assert result.attempts == []

    @pytest.mark.asyncio
    async def test_success_on_first_run_final_code_unchanged(self) -> None:
        from services.debug_loop import run_debug_loop

        original_code = "print('hello')"
        sandbox = _make_sandbox_sequence([_make_exec_result(success=True, stdout="hello\n")])
        client = _make_openai_client()

        result = await run_debug_loop(
            code=original_code,
            task="test task",
            openai_client=client,
            sandbox_execute=sandbox,
        )

        assert result.final_code == original_code

    @pytest.mark.asyncio
    async def test_success_on_first_run_final_stdout_captured(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([_make_exec_result(success=True, stdout="captured output\n")])
        client = _make_openai_client()

        result = await run_debug_loop(
            code="print('captured output')",
            task="test task",
            openai_client=client,
            sandbox_execute=sandbox,
        )

        assert result.final_stdout == "captured output\n"

    @pytest.mark.asyncio
    async def test_openai_not_called_on_immediate_success(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([_make_exec_result(success=True)])
        client = _make_openai_client()

        await run_debug_loop(
            code="print('ok')",
            task="test task",
            openai_client=client,
            sandbox_execute=sandbox,
        )

        client.generate_code.assert_not_called()


# ---------------------------------------------------------------------------
# run_debug_loop — success after 1 retry
# ---------------------------------------------------------------------------


class TestRunDebugLoopSuccessAfterOneRetry:
    """First run fails, fix from OpenAI succeeds on second run."""

    @pytest.mark.asyncio
    async def test_success_after_one_retry(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr="NameError: x"),
            _make_exec_result(success=True, stdout="fixed\n"),
        ])
        client = _make_openai_client(fixed_code="x = 1\nprint(x)")

        result = await run_debug_loop(
            code="print(x)",
            task="test task",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=3,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_one_retry_total_retries_is_one(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr="NameError: x"),
            _make_exec_result(success=True, stdout="fixed\n"),
        ])
        client = _make_openai_client(fixed_code="x = 1\nprint(x)")

        result = await run_debug_loop(
            code="print(x)",
            task="test task",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=3,
        )

        assert result.total_retries == 1

    @pytest.mark.asyncio
    async def test_attempts_list_has_one_entry(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr="NameError: x"),
            _make_exec_result(success=True, stdout="fixed\n"),
        ])
        client = _make_openai_client(fixed_code="x = 1\nprint(x)")

        result = await run_debug_loop(
            code="print(x)",
            task="test task",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=3,
        )

        assert len(result.attempts) == 1

    @pytest.mark.asyncio
    async def test_attempt_has_correct_retry_num(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr="err"),
            _make_exec_result(success=True),
        ])
        client = _make_openai_client(fixed_code="print('fixed')")

        result = await run_debug_loop(
            code="bad code",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=3,
        )

        assert result.attempts[0].retry_num == 1

    @pytest.mark.asyncio
    async def test_attempt_error_field_contains_stderr(self) -> None:
        from services.debug_loop import run_debug_loop

        error_msg = "NameError: name 'x' is not defined"
        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr=error_msg),
            _make_exec_result(success=True),
        ])
        client = _make_openai_client(fixed_code="x = 1")

        result = await run_debug_loop(
            code="print(x)",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=3,
        )

        assert error_msg in result.attempts[0].error

    @pytest.mark.asyncio
    async def test_fixed_code_sent_to_sandbox_on_retry(self) -> None:
        from services.debug_loop import run_debug_loop

        executed_codes: list[str] = []

        def capturing_sandbox(code: str, **kwargs):  # noqa: ANN001
            executed_codes.append(code)
            if len(executed_codes) == 1:
                return _make_exec_result(success=False, stderr="err")
            return _make_exec_result(success=True, stdout="ok")

        fixed_code = "x = 42\nprint(x)"
        client = _make_openai_client(fixed_code=fixed_code)

        await run_debug_loop(
            code="print(x)",
            task="test",
            openai_client=client,
            sandbox_execute=capturing_sandbox,
            max_retries=3,
        )

        assert executed_codes[1] == fixed_code

    @pytest.mark.asyncio
    async def test_final_code_is_fixed_code_after_retry(self) -> None:
        from services.debug_loop import run_debug_loop

        fixed_code = "x = 99\nprint(x)"
        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr="err"),
            _make_exec_result(success=True, stdout="99\n"),
        ])
        client = _make_openai_client(fixed_code=fixed_code)

        result = await run_debug_loop(
            code="print(x)",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=3,
        )

        assert result.final_code == fixed_code

    @pytest.mark.asyncio
    async def test_attempt_success_true_when_fixed_code_works(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr="err"),
            _make_exec_result(success=True, stdout="ok"),
        ])
        client = _make_openai_client(fixed_code="print('fixed')")

        result = await run_debug_loop(
            code="bad",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=3,
        )

        assert result.attempts[0].success is True


# ---------------------------------------------------------------------------
# run_debug_loop — success after max_retries (exactly at the limit)
# ---------------------------------------------------------------------------


class TestRunDebugLoopSuccessAtMaxRetries:
    """Code finally succeeds on the last allowed retry."""

    @pytest.mark.asyncio
    async def test_success_on_last_retry(self) -> None:
        from services.debug_loop import run_debug_loop

        max_retries = 3
        # fail 3 times, succeed on 4th execution (3rd retry)
        results = (
            [_make_exec_result(success=False, stderr="err")] * max_retries
            + [_make_exec_result(success=True, stdout="ok")]
        )
        sandbox = _make_sandbox_sequence(results)
        client = _make_openai_client(fixed_code="print('fixed')")

        result = await run_debug_loop(
            code="bad code",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=max_retries,
        )

        assert result.success is True
        assert result.total_retries == max_retries

    @pytest.mark.asyncio
    async def test_attempts_count_equals_max_retries(self) -> None:
        from services.debug_loop import run_debug_loop

        max_retries = 3
        results = (
            [_make_exec_result(success=False, stderr="err")] * max_retries
            + [_make_exec_result(success=True, stdout="ok")]
        )
        sandbox = _make_sandbox_sequence(results)
        client = _make_openai_client(fixed_code="print('fixed')")

        result = await run_debug_loop(
            code="bad code",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=max_retries,
        )

        assert len(result.attempts) == max_retries


# ---------------------------------------------------------------------------
# run_debug_loop — failure after max_retries exhausted
# ---------------------------------------------------------------------------


class TestRunDebugLoopFailureExhausted:
    """All retries fail — result.success is False."""

    @pytest.mark.asyncio
    async def test_failure_after_max_retries(self) -> None:
        from services.debug_loop import run_debug_loop

        max_retries = 3
        # All executions fail
        results = [_make_exec_result(success=False, stderr="persistent error")] * (max_retries + 1)
        sandbox = _make_sandbox_sequence(results)
        client = _make_openai_client(fixed_code="still broken code")

        result = await run_debug_loop(
            code="bad code",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=max_retries,
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_total_retries_equals_max_retries_when_all_fail(self) -> None:
        from services.debug_loop import run_debug_loop

        max_retries = 3
        results = [_make_exec_result(success=False, stderr="err")] * (max_retries + 1)
        sandbox = _make_sandbox_sequence(results)
        client = _make_openai_client()

        result = await run_debug_loop(
            code="bad",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=max_retries,
        )

        assert result.total_retries == max_retries

    @pytest.mark.asyncio
    async def test_attempts_list_length_equals_max_retries_when_all_fail(self) -> None:
        from services.debug_loop import run_debug_loop

        max_retries = 2
        results = [_make_exec_result(success=False, stderr="err")] * (max_retries + 1)
        sandbox = _make_sandbox_sequence(results)
        client = _make_openai_client()

        result = await run_debug_loop(
            code="bad",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=max_retries,
        )

        assert len(result.attempts) == max_retries

    @pytest.mark.asyncio
    async def test_attempt_success_false_when_fixed_code_still_fails(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr="err1"),
            _make_exec_result(success=False, stderr="err2"),
        ])
        client = _make_openai_client()

        result = await run_debug_loop(
            code="bad",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=1,
        )

        assert result.attempts[0].success is False

    @pytest.mark.asyncio
    async def test_openai_called_max_retries_times_when_all_fail(self) -> None:
        from services.debug_loop import run_debug_loop

        max_retries = 3
        results = [_make_exec_result(success=False, stderr="err")] * (max_retries + 1)
        sandbox = _make_sandbox_sequence(results)
        client = _make_openai_client()

        await run_debug_loop(
            code="bad",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=max_retries,
        )

        assert client.generate_code.call_count == max_retries

    @pytest.mark.asyncio
    async def test_retry_num_increments_correctly(self) -> None:
        from services.debug_loop import run_debug_loop

        max_retries = 3
        results = [_make_exec_result(success=False, stderr="err")] * (max_retries + 1)
        sandbox = _make_sandbox_sequence(results)
        client = _make_openai_client()

        result = await run_debug_loop(
            code="bad",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=max_retries,
        )

        retry_nums = [a.retry_num for a in result.attempts]
        assert retry_nums == [1, 2, 3]


# ---------------------------------------------------------------------------
# run_debug_loop — debug prompt construction
# ---------------------------------------------------------------------------


class TestRunDebugLoopPromptConstruction:
    """OpenAI must receive the debug prompt with correct placeholders filled."""

    @pytest.mark.asyncio
    async def test_task_in_openai_prompt(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr="err"),
            _make_exec_result(success=True),
        ])
        client = _make_openai_client()

        await run_debug_loop(
            code="bad code",
            task="UNIQUE_TASK_TEXT_XYZ",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=3,
        )

        call_args_str = str(client.generate_code.call_args)
        assert "UNIQUE_TASK_TEXT_XYZ" in call_args_str

    @pytest.mark.asyncio
    async def test_code_in_openai_prompt(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr="err"),
            _make_exec_result(success=True),
        ])
        client = _make_openai_client()

        await run_debug_loop(
            code="UNIQUE_CODE_CONTENT_ABC",
            task="task",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=3,
        )

        call_args_str = str(client.generate_code.call_args)
        assert "UNIQUE_CODE_CONTENT_ABC" in call_args_str

    @pytest.mark.asyncio
    async def test_stderr_in_openai_prompt(self) -> None:
        from services.debug_loop import run_debug_loop

        unique_error = "UNIQUE_STDERR_MESSAGE_789"
        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr=unique_error),
            _make_exec_result(success=True),
        ])
        client = _make_openai_client()

        await run_debug_loop(
            code="code",
            task="task",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=3,
        )

        call_args_str = str(client.generate_code.call_args)
        assert unique_error in call_args_str

    @pytest.mark.asyncio
    async def test_file_context_in_openai_prompt(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr="err"),
            _make_exec_result(success=True),
        ])
        client = _make_openai_client()

        await run_debug_loop(
            code="code",
            task="task",
            openai_client=client,
            sandbox_execute=sandbox,
            file_context="UNIQUE_FILE_CONTEXT_DATA",
            max_retries=3,
        )

        call_args_str = str(client.generate_code.call_args)
        assert "UNIQUE_FILE_CONTEXT_DATA" in call_args_str


# ---------------------------------------------------------------------------
# run_debug_loop — edge cases
# ---------------------------------------------------------------------------


class TestRunDebugLoopEdgeCases:
    """Edge cases: empty stderr, None file_context, max_retries=0."""

    @pytest.mark.asyncio
    async def test_empty_stderr_uses_stdout_as_error(self) -> None:
        """When stderr is empty but code failed, stdout is used as error context."""
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([
            _make_exec_result(success=False, stderr="", stdout="some stdout output"),
            _make_exec_result(success=True),
        ])
        client = _make_openai_client()

        result = await run_debug_loop(
            code="bad",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=3,
        )

        # Should still produce an attempt
        assert len(result.attempts) == 1

    @pytest.mark.asyncio
    async def test_none_file_context_does_not_crash(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([_make_exec_result(success=True)])
        client = _make_openai_client()

        result = await run_debug_loop(
            code="print('ok')",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            file_context=None,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_max_retries_zero_returns_failure_immediately(self) -> None:
        """max_retries=0 means no retries — failure on first run stays failure."""
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([_make_exec_result(success=False, stderr="err")])
        client = _make_openai_client()

        result = await run_debug_loop(
            code="bad",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=0,
        )

        assert result.success is False
        assert result.total_retries == 0
        assert result.attempts == []

    @pytest.mark.asyncio
    async def test_max_retries_zero_openai_not_called(self) -> None:
        from services.debug_loop import run_debug_loop

        sandbox = _make_sandbox_sequence([_make_exec_result(success=False, stderr="err")])
        client = _make_openai_client()

        await run_debug_loop(
            code="bad",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
            max_retries=0,
        )

        client.generate_code.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_debug_result_instance(self) -> None:
        from services.debug_loop import DebugResult, run_debug_loop

        sandbox = _make_sandbox_sequence([_make_exec_result(success=True)])
        client = _make_openai_client()

        result = await run_debug_loop(
            code="print('ok')",
            task="test",
            openai_client=client,
            sandbox_execute=sandbox,
        )

        assert isinstance(result, DebugResult)
