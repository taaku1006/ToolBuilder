"""Unit tests for pipeline.reflection_engine.

TDD: tests written FIRST, implementation follows.
All OpenAI calls and sandbox executions are mocked.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infra.openai_client import OpenAIClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_openai_client(response_text: str) -> OpenAIClient:
    """Return a mock OpenAIClient whose generate_code returns response_text."""
    client = MagicMock(spec=OpenAIClient)
    client.generate_code.return_value = response_text
    return client


def _make_sandbox(stdout: str = "", success: bool = True) -> Callable:
    """Return a mock sandbox_execute that returns an ExecutionResult-like object."""
    from infra.sandbox import ExecutionResult

    result = ExecutionResult(
        stdout=stdout,
        stderr="",
        elapsed_ms=100,
        output_files=[],
        success=success,
    )

    def sandbox_execute(code: str, **kwargs):  # noqa: ANN001
        return result

    return sandbox_execute


# ---------------------------------------------------------------------------
# PhaseAResult dataclass
# ---------------------------------------------------------------------------


class TestPhaseAResult:
    """PhaseAResult must be immutable and carry the right fields."""

    def test_frozen_dataclass(self) -> None:
        from pipeline.reflection_engine import PhaseAResult

        r = PhaseAResult(
            exploration_script="print('hi')",
            exploration_output="hi\n",
            success=True,
        )
        with pytest.raises(Exception):
            r.success = False  # type: ignore[misc]

    def test_fields(self) -> None:
        from pipeline.reflection_engine import PhaseAResult

        r = PhaseAResult(
            exploration_script="s",
            exploration_output="o",
            success=False,
        )
        assert r.exploration_script == "s"
        assert r.exploration_output == "o"
        assert r.success is False


# ---------------------------------------------------------------------------
# PhaseBResult dataclass
# ---------------------------------------------------------------------------


class TestPhaseBResult:
    """PhaseBResult must be immutable."""

    def test_frozen_dataclass(self) -> None:
        from pipeline.reflection_engine import PhaseBResult

        r = PhaseBResult(
            needs_custom_tool=False,
            reason="no need",
            tool_code=None,
            tool_output=None,
        )
        with pytest.raises(Exception):
            r.needs_custom_tool = True  # type: ignore[misc]

    def test_fields_with_tool(self) -> None:
        from pipeline.reflection_engine import PhaseBResult

        r = PhaseBResult(
            needs_custom_tool=True,
            reason="special calc needed",
            tool_code="print('tool')",
            tool_output="tool\n",
        )
        assert r.needs_custom_tool is True
        assert r.reason == "special calc needed"
        assert r.tool_code == "print('tool')"
        assert r.tool_output == "tool\n"


# ---------------------------------------------------------------------------
# PhaseCResult dataclass
# ---------------------------------------------------------------------------


class TestPhaseCResult:
    """PhaseCResult must be immutable."""

    def test_frozen_dataclass(self) -> None:
        from pipeline.reflection_engine import PhaseCResult

        r = PhaseCResult(
            summary="処理内容",
            python_code="print('done')",
            steps=["step1"],
            tips="注意点",
        )
        with pytest.raises(Exception):
            r.summary = "changed"  # type: ignore[misc]

    def test_fields(self) -> None:
        from pipeline.reflection_engine import PhaseCResult

        r = PhaseCResult(
            summary="要約",
            python_code="code",
            steps=["s1", "s2"],
            tips="tips",
        )
        assert r.summary == "要約"
        assert r.steps == ["s1", "s2"]


# ---------------------------------------------------------------------------
# run_phase_a
# ---------------------------------------------------------------------------


class TestRunPhaseA:
    """Unit tests for run_phase_a."""

    @pytest.mark.asyncio
    async def test_returns_phase_a_result(self) -> None:
        """run_phase_a returns a PhaseAResult with exploration_script set."""
        from pipeline.reflection_engine import PhaseAResult, run_phase_a

        script = "print('exploring')"
        client = _make_openai_client(script)
        sandbox = _make_sandbox(stdout="col_a: int\n", success=True)

        result = await run_phase_a(
            openai_client=client,
            sandbox_execute=sandbox,
            file_context="col_a: int, col_b: str",
        )

        assert isinstance(result, PhaseAResult)

    @pytest.mark.asyncio
    async def test_exploration_script_from_openai(self) -> None:
        """exploration_script in result comes from OpenAI response."""
        from pipeline.reflection_engine import run_phase_a

        script = "import os\nprint(os.environ['INPUT_FILE'])"
        client = _make_openai_client(script)
        sandbox = _make_sandbox(stdout="file_path.xlsx\n", success=True)

        result = await run_phase_a(
            openai_client=client,
            sandbox_execute=sandbox,
            file_context="col_a: int",
        )

        assert result.exploration_script == script

    @pytest.mark.asyncio
    async def test_exploration_output_from_sandbox(self) -> None:
        """exploration_output comes from sandbox stdout."""
        from pipeline.reflection_engine import run_phase_a

        client = _make_openai_client("print('output')")
        sandbox = _make_sandbox(stdout="output\n", success=True)

        result = await run_phase_a(
            openai_client=client,
            sandbox_execute=sandbox,
            file_context="col_a: int",
        )

        assert result.exploration_output == "output\n"

    @pytest.mark.asyncio
    async def test_success_true_when_sandbox_succeeds(self) -> None:
        from pipeline.reflection_engine import run_phase_a

        client = _make_openai_client("print('ok')")
        sandbox = _make_sandbox(stdout="ok", success=True)

        result = await run_phase_a(
            openai_client=client,
            sandbox_execute=sandbox,
            file_context="col_a: int",
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_success_false_when_sandbox_fails(self) -> None:
        from pipeline.reflection_engine import run_phase_a

        client = _make_openai_client("raise ValueError()")
        sandbox = _make_sandbox(stdout="", success=False)

        result = await run_phase_a(
            openai_client=client,
            sandbox_execute=sandbox,
            file_context="col_a: int",
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_openai_called_with_phase_a_prompt(self) -> None:
        """OpenAI must be called with a prompt containing the file context."""
        from pipeline.reflection_engine import run_phase_a

        client = _make_openai_client("print('ok')")
        sandbox = _make_sandbox()

        await run_phase_a(
            openai_client=client,
            sandbox_execute=sandbox,
            file_context="col_a: int, col_b: str",
        )

        assert client.generate_code.called
        call_args = client.generate_code.call_args
        # system_prompt or user_prompt must contain file context
        all_args_str = str(call_args)
        assert "col_a" in all_args_str or "col_b" in all_args_str

    @pytest.mark.asyncio
    async def test_empty_file_context_still_works(self) -> None:
        """run_phase_a works with empty file context."""
        from pipeline.reflection_engine import run_phase_a

        client = _make_openai_client("print('ok')")
        sandbox = _make_sandbox(stdout="ok", success=True)

        result = await run_phase_a(
            openai_client=client,
            sandbox_execute=sandbox,
            file_context="",
        )

        assert isinstance(result.exploration_script, str)


# ---------------------------------------------------------------------------
# run_phase_b
# ---------------------------------------------------------------------------


class TestRunPhaseB:
    """Unit tests for run_phase_b."""

    def _phase_b_response(
        self,
        needs_custom_tool: bool = False,
        reason: str = "no need",
        tool_code: str | None = None,
    ) -> str:
        payload: dict = {
            "needs_custom_tool": needs_custom_tool,
            "reason": reason,
            "tool_code": tool_code,
        }
        return json.dumps(payload, ensure_ascii=False)

    @pytest.mark.asyncio
    async def test_returns_phase_b_result(self) -> None:
        from pipeline.reflection_engine import PhaseBResult, run_phase_b

        client = _make_openai_client(
            self._phase_b_response(needs_custom_tool=False, reason="simple task")
        )
        sandbox = _make_sandbox()

        result = await run_phase_b(
            openai_client=client,
            sandbox_execute=sandbox,
            exploration_result="cols: a, b",
            task="集計する",
        )

        assert isinstance(result, PhaseBResult)

    @pytest.mark.asyncio
    async def test_no_custom_tool_needed(self) -> None:
        from pipeline.reflection_engine import run_phase_b

        client = _make_openai_client(
            self._phase_b_response(needs_custom_tool=False, reason="simple")
        )
        sandbox = _make_sandbox()

        result = await run_phase_b(
            openai_client=client,
            sandbox_execute=sandbox,
            exploration_result="cols: a, b",
            task="集計する",
        )

        assert result.needs_custom_tool is False
        assert result.reason == "simple"
        assert result.tool_code is None
        assert result.tool_output is None

    @pytest.mark.asyncio
    async def test_custom_tool_executed_when_needed(self) -> None:
        """When needs_custom_tool=True, tool_code is executed in sandbox."""
        from pipeline.reflection_engine import run_phase_b

        tool_code = "print('custom tool output')"
        client = _make_openai_client(
            self._phase_b_response(
                needs_custom_tool=True,
                reason="needs special logic",
                tool_code=tool_code,
            )
        )

        executed_codes: list[str] = []

        def capturing_sandbox(code: str, **kwargs):  # noqa: ANN001
            executed_codes.append(code)
            from infra.sandbox import ExecutionResult

            return ExecutionResult(
                stdout="custom tool output\n",
                stderr="",
                elapsed_ms=50,
                output_files=[],
                success=True,
            )

        result = await run_phase_b(
            openai_client=client,
            sandbox_execute=capturing_sandbox,
            exploration_result="cols: a",
            task="特殊集計",
        )

        assert result.needs_custom_tool is True
        assert result.tool_code == tool_code
        assert len(executed_codes) == 1
        assert executed_codes[0] == tool_code

    @pytest.mark.asyncio
    async def test_tool_output_captured(self) -> None:
        """tool_output in result is sandbox stdout when custom tool runs."""
        from pipeline.reflection_engine import run_phase_b

        client = _make_openai_client(
            self._phase_b_response(
                needs_custom_tool=True,
                reason="needs it",
                tool_code="print('result')",
            )
        )
        sandbox = _make_sandbox(stdout="result\n", success=True)

        result = await run_phase_b(
            openai_client=client,
            sandbox_execute=sandbox,
            exploration_result="cols: a",
            task="特殊集計",
        )

        assert result.tool_output == "result\n"

    @pytest.mark.asyncio
    async def test_exploration_result_in_prompt(self) -> None:
        """OpenAI prompt must include exploration_result."""
        from pipeline.reflection_engine import run_phase_b

        client = _make_openai_client(
            self._phase_b_response(needs_custom_tool=False)
        )
        sandbox = _make_sandbox()

        await run_phase_b(
            openai_client=client,
            sandbox_execute=sandbox,
            exploration_result="unique_col_a: 42",
            task="集計",
        )

        all_args_str = str(client.generate_code.call_args)
        assert "unique_col_a: 42" in all_args_str

    @pytest.mark.asyncio
    async def test_task_in_prompt(self) -> None:
        """OpenAI prompt must include task."""
        from pipeline.reflection_engine import run_phase_b

        client = _make_openai_client(
            self._phase_b_response(needs_custom_tool=False)
        )
        sandbox = _make_sandbox()

        await run_phase_b(
            openai_client=client,
            sandbox_execute=sandbox,
            exploration_result="cols: a",
            task="特殊集計タスクXYZ",
        )

        all_args_str = str(client.generate_code.call_args)
        assert "特殊集計タスクXYZ" in all_args_str

    @pytest.mark.asyncio
    async def test_invalid_json_response_raises(self) -> None:
        """If OpenAI returns non-JSON, run_phase_b raises ValueError."""
        from pipeline.reflection_engine import run_phase_b

        client = _make_openai_client("not valid json")
        sandbox = _make_sandbox()

        with pytest.raises((ValueError, json.JSONDecodeError, Exception)):
            await run_phase_b(
                openai_client=client,
                sandbox_execute=sandbox,
                exploration_result="cols: a",
                task="集計",
            )


# ---------------------------------------------------------------------------
# run_phase_c
# ---------------------------------------------------------------------------


class TestRunPhaseC:
    """Unit tests for run_phase_c."""

    def _phase_c_response(
        self,
        summary: str = "処理内容",
        python_code: str = "print('done')",
        steps: list[str] | None = None,
        tips: str = "注意点",
    ) -> str:
        return json.dumps(
            {
                "summary": summary,
                "python_code": python_code,
                "steps": steps or ["step1", "step2"],
                "tips": tips,
            },
            ensure_ascii=False,
        )

    @pytest.mark.asyncio
    async def test_returns_phase_c_result(self) -> None:
        from pipeline.reflection_engine import PhaseCResult, run_phase_c

        client = _make_openai_client(self._phase_c_response())

        result = await run_phase_c(
            openai_client=client,
            exploration_result="cols: a, b",
            reflection_result="no custom tool",
            task="集計する",
            file_context="col_a: int",
        )

        assert isinstance(result, PhaseCResult)

    @pytest.mark.asyncio
    async def test_summary_from_openai(self) -> None:
        from pipeline.reflection_engine import run_phase_c

        client = _make_openai_client(
            self._phase_c_response(summary="Excelの集計処理です")
        )

        result = await run_phase_c(
            openai_client=client,
            exploration_result="cols",
            reflection_result="none",
            task="集計",
            file_context="",
        )

        assert result.summary == "Excelの集計処理です"

    @pytest.mark.asyncio
    async def test_python_code_from_openai(self) -> None:
        from pipeline.reflection_engine import run_phase_c

        expected_code = "import pandas as pd\ndf = pd.read_excel(INPUT_FILE)"
        client = _make_openai_client(self._phase_c_response(python_code=expected_code))

        result = await run_phase_c(
            openai_client=client,
            exploration_result="cols",
            reflection_result="none",
            task="集計",
            file_context="",
        )

        assert result.python_code == expected_code

    @pytest.mark.asyncio
    async def test_steps_is_list(self) -> None:
        from pipeline.reflection_engine import run_phase_c

        client = _make_openai_client(
            self._phase_c_response(steps=["読み込み", "集計", "保存"])
        )

        result = await run_phase_c(
            openai_client=client,
            exploration_result="cols",
            reflection_result="none",
            task="集計",
            file_context="",
        )

        assert result.steps == ["読み込み", "集計", "保存"]

    @pytest.mark.asyncio
    async def test_all_context_in_prompt(self) -> None:
        """exploration_result, reflection_result, and task all appear in prompt."""
        from pipeline.reflection_engine import run_phase_c

        client = _make_openai_client(self._phase_c_response())

        await run_phase_c(
            openai_client=client,
            exploration_result="UNIQUE_EXPLORATION_DATA",
            reflection_result="UNIQUE_REFLECTION_DATA",
            task="UNIQUE_TASK_TEXT",
            file_context="UNIQUE_FILE_CONTEXT",
        )

        all_args_str = str(client.generate_code.call_args)
        assert "UNIQUE_EXPLORATION_DATA" in all_args_str
        assert "UNIQUE_REFLECTION_DATA" in all_args_str
        assert "UNIQUE_TASK_TEXT" in all_args_str

    @pytest.mark.asyncio
    async def test_invalid_json_response_raises(self) -> None:
        """If OpenAI returns non-JSON, run_phase_c raises ValueError or JSONDecodeError."""
        from pipeline.reflection_engine import run_phase_c

        client = _make_openai_client("not json")

        with pytest.raises((ValueError, json.JSONDecodeError, Exception)):
            await run_phase_c(
                openai_client=client,
                exploration_result="cols",
                reflection_result="none",
                task="集計",
                file_context="",
            )

    @pytest.mark.asyncio
    async def test_missing_field_raises(self) -> None:
        """If OpenAI JSON is missing required field, raises KeyError or ValueError."""
        from pipeline.reflection_engine import run_phase_c

        client = _make_openai_client(json.dumps({"summary": "only summary"}))

        with pytest.raises((KeyError, ValueError, Exception)):
            await run_phase_c(
                openai_client=client,
                exploration_result="cols",
                reflection_result="none",
                task="集計",
                file_context="",
            )
