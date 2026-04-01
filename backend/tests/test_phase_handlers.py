"""Tests for phase_handlers module (TDD-first).

Phase handlers are async generators that yield AgentLogEntry objects.
Each handler encapsulates one phase of the orchestration pipeline.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config import Settings
from pipeline.agent_orchestrator import AgentLogEntry, CancelledError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def collect_entries(gen) -> list[AgentLogEntry]:
    """Collect all entries from an AsyncGenerator."""
    return [entry async for entry in gen]


def _make_settings(
    reflection_enabled: bool = True,
    reflection_phase_enabled: bool = True,
    debug_loop_enabled: bool = False,
    task_decomposition_enabled: bool = False,
    eval_debug_loop_enabled: bool = False,
    llm_eval_loop_enabled: bool = False,
    skills_enabled: bool = False,
) -> Settings:
    return Settings(
        openai_api_key="test-key-123",
        openai_model="gpt-4o",
        cors_origins="http://localhost:5173",
        reflection_enabled=reflection_enabled,
        reflection_phase_enabled=reflection_phase_enabled,
        debug_loop_enabled=debug_loop_enabled,
        task_decomposition_enabled=task_decomposition_enabled,
        eval_debug_loop_enabled=eval_debug_loop_enabled,
        llm_eval_loop_enabled=llm_eval_loop_enabled,
        skills_enabled=skills_enabled,
    )


def _make_mock_openai_client() -> MagicMock:
    mock = MagicMock()
    mock.total_tokens = 0
    mock.prompt_tokens = 0
    mock.completion_tokens = 0
    mock.api_calls = 0
    return mock


def _make_mock_trace() -> MagicMock:
    mock = MagicMock()
    mock.start_phase = MagicMock()
    mock.end_phase = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# handle_phase_a
# ---------------------------------------------------------------------------


class TestHandlePhaseA:
    """handle_phase_a yields Phase A start/complete entries."""

    @pytest.mark.asyncio
    async def test_yields_start_entry(self) -> None:
        """Phase A start entry must be yielded."""
        from pipeline.phase_handlers import handle_phase_a
        from pipeline.reflection_engine import PhaseAResult

        settings = _make_settings()
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()

        phase_a_result = PhaseAResult(
            exploration_script="print('exploring')",
            exploration_output="col_a: int",
            success=True,
        )

        with patch(
            "pipeline.phase_handlers.run_phase_a",
            new=AsyncMock(return_value=phase_a_result),
        ):
            entries = await collect_entries(
                handle_phase_a(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id="file-123",
                    file_context="col_a: int",
                    cancel_check=None,
                    trace=trace,
                )
            )

        actions = [e.action for e in entries if e.phase == "A"]
        assert "start" in actions

    @pytest.mark.asyncio
    async def test_yields_complete_on_success(self) -> None:
        """Phase A complete entry must be yielded when exploration succeeds."""
        from pipeline.phase_handlers import handle_phase_a
        from pipeline.reflection_engine import PhaseAResult

        settings = _make_settings()
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()

        phase_a_result = PhaseAResult(
            exploration_script="print('exploring')",
            exploration_output="col_a: int",
            success=True,
        )

        with patch(
            "pipeline.phase_handlers.run_phase_a",
            new=AsyncMock(return_value=phase_a_result),
        ):
            entries = await collect_entries(
                handle_phase_a(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id="file-123",
                    file_context="col_a: int",
                    cancel_check=None,
                    trace=trace,
                )
            )

        actions = [e.action for e in entries if e.phase == "A"]
        assert "complete" in actions

    @pytest.mark.asyncio
    async def test_yields_error_on_failure(self) -> None:
        """Phase A error entry must be yielded when exploration fails."""
        from pipeline.phase_handlers import handle_phase_a
        from pipeline.reflection_engine import PhaseAResult

        settings = _make_settings()
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()

        phase_a_result = PhaseAResult(
            exploration_script="bad script",
            exploration_output="",
            success=False,
        )

        with patch(
            "pipeline.phase_handlers.run_phase_a",
            new=AsyncMock(return_value=phase_a_result),
        ):
            entries = await collect_entries(
                handle_phase_a(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id="file-123",
                    file_context="col_a: int",
                    cancel_check=None,
                    trace=trace,
                )
            )

        actions = [e.action for e in entries if e.phase == "A"]
        assert "error" in actions

    @pytest.mark.asyncio
    async def test_returns_exploration_result(self) -> None:
        """handle_phase_a must return the exploration output via state mutation."""
        from pipeline.phase_handlers import handle_phase_a, PhaseAState
        from pipeline.reflection_engine import PhaseAResult

        settings = _make_settings()
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()
        state = PhaseAState()

        phase_a_result = PhaseAResult(
            exploration_script="print('exploring')",
            exploration_output="col_a: int\ncol_b: str",
            success=True,
        )

        with patch(
            "pipeline.phase_handlers.run_phase_a",
            new=AsyncMock(return_value=phase_a_result),
        ):
            await collect_entries(
                handle_phase_a(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id="file-123",
                    file_context="col_a: int",
                    cancel_check=None,
                    trace=trace,
                    state=state,
                )
            )

        assert state.exploration_result == "col_a: int\ncol_b: str"

    @pytest.mark.asyncio
    async def test_cancel_raises_error(self) -> None:
        """cancel_check returning True must raise CancelledError."""
        from pipeline.phase_handlers import handle_phase_a
        from pipeline.reflection_engine import PhaseAResult

        settings = _make_settings()
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()

        phase_a_result = PhaseAResult(
            exploration_script="print('exploring')",
            exploration_output="col_a: int",
            success=True,
        )

        cancel_check = MagicMock(return_value=True)

        with patch(
            "pipeline.phase_handlers.run_phase_a",
            new=AsyncMock(return_value=phase_a_result),
        ):
            with pytest.raises(CancelledError):
                await collect_entries(
                    handle_phase_a(
                        openai_client=openai_client,
                        settings=settings,
                        task="集計する",
                        file_id="file-123",
                        file_context="col_a: int",
                        cancel_check=cancel_check,
                        trace=trace,
                    )
                )


# ---------------------------------------------------------------------------
# handle_phase_b
# ---------------------------------------------------------------------------


class TestHandlePhaseB:
    """handle_phase_b yields Phase B start/complete entries."""

    @pytest.mark.asyncio
    async def test_yields_start_and_complete(self) -> None:
        """Phase B must yield start and complete entries."""
        from pipeline.phase_handlers import handle_phase_b
        from pipeline.reflection_engine import PhaseBResult

        settings = _make_settings()
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()

        phase_b_result = PhaseBResult(
            needs_custom_tool=False,
            reason="no need",
            tool_code=None,
            tool_output=None,
        )

        with patch(
            "pipeline.phase_handlers.run_phase_b",
            new=AsyncMock(return_value=phase_b_result),
        ):
            entries = await collect_entries(
                handle_phase_b(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id="file-123",
                    file_context="col_a: int",
                    exploration_result="col_a explored",
                    cancel_check=None,
                    trace=trace,
                )
            )

        phases = [e.phase for e in entries]
        actions = [e.action for e in entries if e.phase == "B"]
        assert "B" in phases
        assert "start" in actions
        assert "complete" in actions

    @pytest.mark.asyncio
    async def test_returns_reflection_result_json(self) -> None:
        """handle_phase_b must store reflection result as JSON."""
        from pipeline.phase_handlers import handle_phase_b, PhaseBState
        from pipeline.reflection_engine import PhaseBResult

        settings = _make_settings()
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()
        state = PhaseBState()

        phase_b_result = PhaseBResult(
            needs_custom_tool=True,
            reason="カスタムツールが必要",
            tool_code="def my_tool(): pass",
            tool_output="output",
        )

        with patch(
            "pipeline.phase_handlers.run_phase_b",
            new=AsyncMock(return_value=phase_b_result),
        ):
            await collect_entries(
                handle_phase_b(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id="file-123",
                    file_context="col_a: int",
                    exploration_result="col_a explored",
                    cancel_check=None,
                    trace=trace,
                    state=state,
                )
            )

        parsed = json.loads(state.reflection_result)
        assert parsed["needs_custom_tool"] is True
        assert "reason" in parsed


# ---------------------------------------------------------------------------
# handle_phase_d
# ---------------------------------------------------------------------------


class TestHandlePhaseD:
    """handle_phase_d manages the debug loop phase."""

    @pytest.mark.asyncio
    async def test_yields_start_entry(self) -> None:
        """Phase D start entry must be yielded."""
        from pipeline.phase_handlers import handle_phase_d
        from infra.sandbox import ExecutionResult

        settings = _make_settings(debug_loop_enabled=True)
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()

        success_result = ExecutionResult(
            stdout="ok",
            stderr="",
            elapsed_ms=100,
            output_files=[],
            success=True,
        )

        with patch(
            "pipeline.phase_handlers.execute_code",
            return_value=success_result,
        ):
            entries = await collect_entries(
                handle_phase_d(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id=None,
                    file_context=None,
                    python_code="print('hello')",
                    cancel_check=None,
                    trace=trace,
                )
            )

        phases = [e.phase for e in entries]
        assert "D" in phases
        actions = [e.action for e in entries if e.phase == "D"]
        assert "start" in actions

    @pytest.mark.asyncio
    async def test_yields_complete_on_first_success(self) -> None:
        """Phase D complete entry when first execution succeeds."""
        from pipeline.phase_handlers import handle_phase_d
        from infra.sandbox import ExecutionResult

        settings = _make_settings(debug_loop_enabled=True)
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()

        success_result = ExecutionResult(
            stdout="ok",
            stderr="",
            elapsed_ms=100,
            output_files=[],
            success=True,
        )

        with patch(
            "pipeline.phase_handlers.execute_code",
            return_value=success_result,
        ):
            entries = await collect_entries(
                handle_phase_d(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id=None,
                    file_context=None,
                    python_code="print('hello')",
                    cancel_check=None,
                    trace=trace,
                )
            )

        d_entries = [e for e in entries if e.phase == "D"]
        actions = [e.action for e in d_entries]
        assert "complete" in actions

    @pytest.mark.asyncio
    async def test_yields_retry_and_complete_on_debug_success(self) -> None:
        """Phase D retry and complete when debug loop fixes the error."""
        from pipeline.phase_handlers import handle_phase_d
        from pipeline.debug_loop import DebugAttempt, DebugResult
        from infra.sandbox import ExecutionResult

        settings = _make_settings(debug_loop_enabled=True)
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()

        fail_result = ExecutionResult(
            stdout="",
            stderr="NameError: x",
            elapsed_ms=100,
            output_files=[],
            success=False,
        )

        debug_success = DebugResult(
            final_code="x = 1\nprint(x)",
            final_stdout="1\n",
            final_stderr="",
            success=True,
            attempts=[
                DebugAttempt(
                    retry_num=1,
                    error="NameError: x",
                    fixed_code="x = 1\nprint(x)",
                    success=True,
                )
            ],
            total_retries=1,
        )

        with (
            patch("pipeline.phase_handlers.execute_code", return_value=fail_result),
            patch(
                "pipeline.phase_handlers.run_debug_loop",
                new=AsyncMock(return_value=debug_success),
            ),
        ):
            entries = await collect_entries(
                handle_phase_d(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id=None,
                    file_context=None,
                    python_code="bad code",
                    cancel_check=None,
                    trace=trace,
                )
            )

        d_entries = [e for e in entries if e.phase == "D"]
        actions = [e.action for e in d_entries]
        assert "retry" in actions
        assert "complete" in actions

    @pytest.mark.asyncio
    async def test_state_updated_with_final_code(self) -> None:
        """Phase D state must contain final_code after successful debug."""
        from pipeline.phase_handlers import handle_phase_d, PhaseDState
        from pipeline.debug_loop import DebugAttempt, DebugResult
        from infra.sandbox import ExecutionResult

        settings = _make_settings(debug_loop_enabled=True)
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()
        state = PhaseDState()

        fail_result = ExecutionResult(
            stdout="",
            stderr="NameError: x",
            elapsed_ms=100,
            output_files=[],
            success=False,
        )

        fixed_code = "x = 1\nprint(x)"
        debug_success = DebugResult(
            final_code=fixed_code,
            final_stdout="1\n",
            final_stderr="",
            success=True,
            attempts=[
                DebugAttempt(
                    retry_num=1,
                    error="NameError: x",
                    fixed_code=fixed_code,
                    success=True,
                )
            ],
            total_retries=1,
        )

        with (
            patch("pipeline.phase_handlers.execute_code", return_value=fail_result),
            patch(
                "pipeline.phase_handlers.run_debug_loop",
                new=AsyncMock(return_value=debug_success),
            ),
        ):
            await collect_entries(
                handle_phase_d(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id=None,
                    file_context=None,
                    python_code="bad code",
                    cancel_check=None,
                    trace=trace,
                    state=state,
                )
            )

        assert state.python_code == fixed_code
        assert state.debug_retries == 1
        assert state.exec_succeeded is True


# ---------------------------------------------------------------------------
# handle_phase_p
# ---------------------------------------------------------------------------


class TestHandlePhaseP:
    """handle_phase_p manages task decomposition phase."""

    @pytest.mark.asyncio
    async def test_no_decompose_yields_complete(self) -> None:
        """When decompose=False, P/complete is yielded with single-step message."""
        from pipeline.phase_handlers import handle_phase_p
        from pipeline.task_planner import PlanResult

        settings = _make_settings(task_decomposition_enabled=True)
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()

        no_decomp_plan = PlanResult(
            decompose=False,
            subtasks=[],
            reasoning="単一ステップで実行可能",
        )

        with patch(
            "pipeline.phase_handlers.run_planner",
            new=AsyncMock(return_value=no_decomp_plan),
        ):
            entries = await collect_entries(
                handle_phase_p(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id="file-123",
                    file_context="col_a: int",
                    exploration_result="",
                    reflection_result="",
                    cancel_check=None,
                    trace=trace,
                )
            )

        p_entries = [e for e in entries if e.phase == "P"]
        actions = [e.action for e in p_entries]
        assert "start" in actions
        assert "complete" in actions

    @pytest.mark.asyncio
    async def test_decompose_yields_subtask_entries(self) -> None:
        """When decompose=True, subtask phase entries are yielded."""
        from pipeline.phase_handlers import handle_phase_p
        from pipeline.task_planner import PlanResult, SubTask
        from infra.sandbox import ExecutionResult

        settings = _make_settings(task_decomposition_enabled=True)
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()

        subtask1 = SubTask(id=1, title="データ読み込み", description="Excelを読む", depends_on=(), expected_output="step1.xlsx")
        subtask2 = SubTask(id=2, title="集計", description="集計する", depends_on=(1,), expected_output="step2.xlsx")
        decomp_plan = PlanResult(
            decompose=True,
            subtasks=[subtask1, subtask2],
            reasoning="複数ステップが必要",
        )

        success_exec = ExecutionResult(
            stdout="ok",
            stderr="",
            elapsed_ms=100,
            output_files=[],
            success=True,
        )

        with (
            patch(
                "pipeline.phase_handlers.run_planner",
                new=AsyncMock(return_value=decomp_plan),
            ),
            patch(
                "pipeline.phase_handlers.run_phase_c_subtask",
                new=AsyncMock(return_value="print('subtask code')"),
            ),
            patch(
                "pipeline.phase_handlers.execute_code",
                return_value=success_exec,
            ),
        ):
            entries = await collect_entries(
                handle_phase_p(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id="file-123",
                    file_context="col_a: int",
                    exploration_result="",
                    reflection_result="",
                    cancel_check=None,
                    trace=trace,
                )
            )

        phases = [e.phase for e in entries]
        # Subtask entries like "C.1", "C.2"
        subtask_phases = [p for p in phases if p.startswith("C.")]
        assert len(subtask_phases) >= 2

    @pytest.mark.asyncio
    async def test_decompose_state_updated_on_success(self) -> None:
        """When all subtasks succeed, state reflects decomposition success."""
        from pipeline.phase_handlers import handle_phase_p, PhasePState
        from pipeline.task_planner import PlanResult, SubTask
        from infra.sandbox import ExecutionResult

        settings = _make_settings(task_decomposition_enabled=True)
        openai_client = _make_mock_openai_client()
        trace = _make_mock_trace()
        state = PhasePState()

        subtask1 = SubTask(id=1, title="データ読み込み", description="Excelを読む", depends_on=(), expected_output="step1.xlsx")
        decomp_plan = PlanResult(
            decompose=True,
            subtasks=[subtask1],
            reasoning="分解が必要",
        )

        success_exec = ExecutionResult(
            stdout="ok",
            stderr="",
            elapsed_ms=100,
            output_files=[],
            success=True,
        )

        with (
            patch(
                "pipeline.phase_handlers.run_planner",
                new=AsyncMock(return_value=decomp_plan),
            ),
            patch(
                "pipeline.phase_handlers.run_phase_c_subtask",
                new=AsyncMock(return_value="print('done')"),
            ),
            patch(
                "pipeline.phase_handlers.execute_code",
                return_value=success_exec,
            ),
        ):
            await collect_entries(
                handle_phase_p(
                    openai_client=openai_client,
                    settings=settings,
                    task="集計する",
                    file_id="file-123",
                    file_context="col_a: int",
                    exploration_result="",
                    reflection_result="",
                    cancel_check=None,
                    trace=trace,
                    state=state,
                )
            )

        assert state.decomposition_succeeded is True
        assert state.decomp_final_code != ""


# ---------------------------------------------------------------------------
# handle_phase_e
# ---------------------------------------------------------------------------


class TestHandlePhaseE:
    """handle_phase_e manages skill save suggestion phase."""

    @pytest.mark.asyncio
    async def test_yields_suggest_save_when_exec_succeeded(self) -> None:
        """When execution succeeded, Phase E suggests saving as skill."""
        from pipeline.phase_handlers import handle_phase_e

        settings = _make_settings(skills_enabled=True)
        trace = _make_mock_trace()

        entries = await collect_entries(
            handle_phase_e(
                settings=settings,
                task="集計する",
                python_code="print('done')",
                phase_c_summary="要約",
                exec_succeeded=True,
                cancel_check=None,
                trace=trace,
            )
        )

        e_entries = [e for e in entries if e.phase == "E"]
        assert len(e_entries) >= 1

        complete_entry = next(
            (e for e in e_entries if e.action == "complete"), None
        )
        assert complete_entry is not None
        payload = json.loads(complete_entry.content)
        assert payload["suggest_save"] is True

    @pytest.mark.asyncio
    async def test_no_suggest_save_when_exec_failed(self) -> None:
        """When execution failed, Phase E does not suggest saving."""
        from pipeline.phase_handlers import handle_phase_e

        settings = _make_settings(skills_enabled=True)
        trace = _make_mock_trace()

        entries = await collect_entries(
            handle_phase_e(
                settings=settings,
                task="集計する",
                python_code="bad code",
                phase_c_summary="",
                exec_succeeded=False,
                cancel_check=None,
                trace=trace,
            )
        )

        complete_entry = next(
            (e for e in entries if e.phase == "E" and e.action == "complete"), None
        )
        assert complete_entry is not None
        payload = json.loads(complete_entry.content)
        assert payload["suggest_save"] is False
