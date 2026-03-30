"""Unit tests for services.agent_orchestrator.

TDD: tests written FIRST, implementation follows.
All OpenAI calls and sandbox executions are mocked.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config import Settings


def _make_settings(
    reflection_enabled: bool = True,
    reflection_phase_enabled: bool = True,
    debug_loop_enabled: bool = False,
    task_decomposition_enabled: bool = False,
    eval_debug_loop_enabled: bool = False,
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
    )


def _phase_c_json(
    summary: str = "要約",
    python_code: str = "print('done')",
    steps: list[str] | None = None,
    tips: str = "注意",
) -> str:
    return json.dumps(
        {
            "summary": summary,
            "python_code": python_code,
            "steps": steps or ["step1"],
            "tips": tips,
        },
        ensure_ascii=False,
    )


def _phase_b_json(needs_custom_tool: bool = False) -> str:
    return json.dumps(
        {
            "needs_custom_tool": needs_custom_tool,
            "reason": "no need",
            "tool_code": None,
        }
    )


# ---------------------------------------------------------------------------
# AgentLogEntry dataclass
# ---------------------------------------------------------------------------


class TestAgentLogEntry:
    """AgentLogEntry must be immutable and carry the right fields."""

    def test_frozen_dataclass(self) -> None:
        from services.agent_orchestrator import AgentLogEntry

        entry = AgentLogEntry(
            phase="A",
            action="start",
            content="探索開始",
            timestamp="2024-01-01T00:00:00",
        )
        with pytest.raises(Exception):
            entry.phase = "B"  # type: ignore[misc]

    def test_fields(self) -> None:
        from services.agent_orchestrator import AgentLogEntry

        entry = AgentLogEntry(
            phase="C",
            action="complete",
            content="コード生成完了",
            timestamp="2024-01-01T00:00:00",
        )
        assert entry.phase == "C"
        assert entry.action == "complete"
        assert entry.content == "コード生成完了"
        assert entry.timestamp == "2024-01-01T00:00:00"


# ---------------------------------------------------------------------------
# orchestrate — no file_id
# ---------------------------------------------------------------------------


class TestOrchestrateNoFile:
    """orchestrate without file_id skips Phase A and B."""

    @pytest.mark.asyncio
    async def test_yields_agent_log_entries(self) -> None:
        """orchestrate yields at least one AgentLogEntry."""
        from services.agent_orchestrator import AgentLogEntry, orchestrate

        settings = _make_settings()

        with patch("services.agent_orchestrator.OpenAIClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json()
            mock_cls.return_value = mock_instance

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id=None,
                    settings=settings,
                )
            ]

        assert len(entries) >= 1
        assert all(isinstance(e, AgentLogEntry) for e in entries)

    @pytest.mark.asyncio
    async def test_final_entry_has_python_code(self) -> None:
        """The last entry must include python_code in its content as JSON."""
        from services.agent_orchestrator import orchestrate

        settings = _make_settings()
        expected_code = "import pandas as pd\nprint('test')"

        with patch("services.agent_orchestrator.OpenAIClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json(
                python_code=expected_code
            )
            mock_cls.return_value = mock_instance

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id=None,
                    settings=settings,
                )
            ]

        last = entries[-1]
        payload = json.loads(last.content)
        assert "python_code" in payload
        assert payload["python_code"] == expected_code

    @pytest.mark.asyncio
    async def test_entries_have_iso_timestamps(self) -> None:
        """All AgentLogEntry timestamps must be valid ISO-format strings."""
        import datetime

        from services.agent_orchestrator import orchestrate

        settings = _make_settings()

        with patch("services.agent_orchestrator.OpenAIClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json()
            mock_cls.return_value = mock_instance

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id=None,
                    settings=settings,
                )
            ]

        for e in entries:
            # Should parse without exception
            datetime.datetime.fromisoformat(e.timestamp)

    @pytest.mark.asyncio
    async def test_phase_c_entry_present(self) -> None:
        """At least one entry with phase='C' must be yielded."""
        from services.agent_orchestrator import orchestrate

        settings = _make_settings()

        with patch("services.agent_orchestrator.OpenAIClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json()
            mock_cls.return_value = mock_instance

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id=None,
                    settings=settings,
                )
            ]

        phases = [e.phase for e in entries]
        assert "C" in phases

    @pytest.mark.asyncio
    async def test_no_phase_a_without_file_id(self) -> None:
        """Without file_id, no Phase A entries should be yielded."""
        from services.agent_orchestrator import orchestrate

        settings = _make_settings()

        with patch("services.agent_orchestrator.OpenAIClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json()
            mock_cls.return_value = mock_instance

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id=None,
                    settings=settings,
                )
            ]

        phases = [e.phase for e in entries]
        assert "A" not in phases


# ---------------------------------------------------------------------------
# orchestrate — with file_id and reflection enabled
# ---------------------------------------------------------------------------


class TestOrchestrateWithFile:
    """orchestrate with file_id and REFLECTION_ENABLED runs Phase A, B, C."""

    @pytest.mark.asyncio
    async def test_phase_a_entry_present(self) -> None:
        """With file_id, Phase A entry must be yielded."""
        from services.agent_orchestrator import orchestrate

        settings = _make_settings(reflection_enabled=True)

        exploration_script = "print('exploring')"
        exploration_output = "col_a: int\n"

        with (
            patch("services.agent_orchestrator.OpenAIClient") as mock_cls,
            patch("services.agent_orchestrator.execute_code") as mock_exec,
            patch("services.agent_orchestrator._resolve_file_context") as mock_ctx,
        ):
            mock_ctx.return_value = "col_a: int"
            mock_instance = MagicMock()
            # Phase A → exploration script; Phase B → needs_custom_tool=False; Phase C → final
            mock_instance.generate_code.side_effect = [
                exploration_script,
                _phase_b_json(needs_custom_tool=False),
                _phase_c_json(),
            ]
            mock_cls.return_value = mock_instance

            from services.sandbox import ExecutionResult

            mock_exec.return_value = ExecutionResult(
                stdout=exploration_output,
                stderr="",
                elapsed_ms=100,
                output_files=[],
                success=True,
            )

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id="file-uuid-123",
                    settings=settings,
                )
            ]

        phases = [e.phase for e in entries]
        assert "A" in phases

    @pytest.mark.asyncio
    async def test_phase_b_entry_present(self) -> None:
        """With file_id, Phase B entry must be yielded."""
        from services.agent_orchestrator import orchestrate

        settings = _make_settings(reflection_enabled=True)

        with (
            patch("services.agent_orchestrator.OpenAIClient") as mock_cls,
            patch("services.agent_orchestrator.execute_code") as mock_exec,
            patch("services.agent_orchestrator._resolve_file_context") as mock_ctx,
        ):
            mock_ctx.return_value = "col_a: int"
            mock_instance = MagicMock()
            mock_instance.generate_code.side_effect = [
                "print('explore')",
                _phase_b_json(needs_custom_tool=False),
                _phase_c_json(),
            ]
            mock_cls.return_value = mock_instance

            from services.sandbox import ExecutionResult

            mock_exec.return_value = ExecutionResult(
                stdout="explored",
                stderr="",
                elapsed_ms=100,
                output_files=[],
                success=True,
            )

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id="file-uuid-123",
                    settings=settings,
                )
            ]

        phases = [e.phase for e in entries]
        assert "B" in phases

    @pytest.mark.asyncio
    async def test_reflection_disabled_skips_a_and_b(self) -> None:
        """With REFLECTION_ENABLED=false, Phase A and B are skipped."""
        from services.agent_orchestrator import orchestrate

        settings = _make_settings(reflection_enabled=False, reflection_phase_enabled=False)

        with patch("services.agent_orchestrator.OpenAIClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json()
            mock_cls.return_value = mock_instance

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id="file-uuid-123",
                    settings=settings,
                )
            ]

        phases = [e.phase for e in entries]
        assert "A" not in phases
        assert "B" not in phases

    @pytest.mark.asyncio
    async def test_all_phases_have_action_field(self) -> None:
        """Every AgentLogEntry must have a non-empty action field."""
        from services.agent_orchestrator import orchestrate

        settings = _make_settings(reflection_enabled=True)

        with (
            patch("services.agent_orchestrator.OpenAIClient") as mock_cls,
            patch("services.agent_orchestrator.execute_code") as mock_exec,
            patch("services.agent_orchestrator._resolve_file_context") as mock_ctx,
        ):
            mock_ctx.return_value = "col_a: int"
            mock_instance = MagicMock()
            mock_instance.generate_code.side_effect = [
                "print('explore')",
                _phase_b_json(needs_custom_tool=False),
                _phase_c_json(),
            ]
            mock_cls.return_value = mock_instance

            from services.sandbox import ExecutionResult

            mock_exec.return_value = ExecutionResult(
                stdout="explored",
                stderr="",
                elapsed_ms=100,
                output_files=[],
                success=True,
            )

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id="file-uuid-123",
                    settings=settings,
                )
            ]

        for e in entries:
            assert e.action, f"Entry {e} has empty action"


# ---------------------------------------------------------------------------
# orchestrate — generator protocol
# ---------------------------------------------------------------------------


class TestOrchestrateGeneratorProtocol:
    """orchestrate must be an async generator."""

    def test_is_async_generator_function(self) -> None:
        import inspect

        from services.agent_orchestrator import orchestrate

        assert inspect.isasyncgenfunction(orchestrate)

    @pytest.mark.asyncio
    async def test_can_be_iterated_multiple_times_with_new_call(self) -> None:
        """Each call to orchestrate() produces an independent generator."""
        from services.agent_orchestrator import orchestrate

        settings = _make_settings()

        with patch("services.agent_orchestrator.OpenAIClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json()
            mock_cls.return_value = mock_instance

            entries1 = [
                e
                async for e in orchestrate(
                    task="タスク1",
                    file_id=None,
                    settings=settings,
                )
            ]
            entries2 = [
                e
                async for e in orchestrate(
                    task="タスク2",
                    file_id=None,
                    settings=settings,
                )
            ]

        assert len(entries1) >= 1
        assert len(entries2) >= 1


# ---------------------------------------------------------------------------
# orchestrate — Phase D (debug loop)
# ---------------------------------------------------------------------------


class TestOrchestratePhaseD:
    """orchestrate with debug_loop_enabled=True runs Phase D after Phase C."""

    @pytest.mark.asyncio
    async def test_phase_d_start_entry_present(self) -> None:
        """With debug_loop_enabled, Phase D start entry must be yielded."""
        from services.agent_orchestrator import orchestrate
        from services.sandbox import ExecutionResult

        settings = _make_settings(debug_loop_enabled=True)

        with (
            patch("services.agent_orchestrator.OpenAIClient") as mock_cls,
            patch("services.agent_orchestrator.execute_code") as mock_exec,
        ):
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json()
            mock_cls.return_value = mock_instance

            mock_exec.return_value = ExecutionResult(
                stdout="ok",
                stderr="",
                elapsed_ms=100,
                output_files=[],
                success=True,
            )

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id=None,
                    settings=settings,
                )
            ]

        phases = [e.phase for e in entries]
        assert "D" in phases

    @pytest.mark.asyncio
    async def test_phase_d_complete_on_first_exec_success(self) -> None:
        """When code executes successfully on first try, D/complete is yielded."""
        from services.agent_orchestrator import orchestrate
        from services.sandbox import ExecutionResult

        settings = _make_settings(debug_loop_enabled=True)

        with (
            patch("services.agent_orchestrator.OpenAIClient") as mock_cls,
            patch("services.agent_orchestrator.execute_code") as mock_exec,
        ):
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json()
            mock_cls.return_value = mock_instance

            mock_exec.return_value = ExecutionResult(
                stdout="ok",
                stderr="",
                elapsed_ms=100,
                output_files=[],
                success=True,
            )

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id=None,
                    settings=settings,
                )
            ]

        d_entries = [e for e in entries if e.phase == "D"]
        actions = [e.action for e in d_entries]
        assert "complete" in actions

    @pytest.mark.asyncio
    async def test_phase_d_disabled_when_setting_off(self) -> None:
        """With debug_loop_enabled=False, no Phase D entries yielded."""
        from services.agent_orchestrator import orchestrate

        settings = _make_settings(debug_loop_enabled=False)

        with patch("services.agent_orchestrator.OpenAIClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json()
            mock_cls.return_value = mock_instance

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id=None,
                    settings=settings,
                )
            ]

        phases = [e.phase for e in entries]
        assert "D" not in phases

    @pytest.mark.asyncio
    async def test_phase_d_retry_entries_on_failure(self) -> None:
        """When first exec fails and debug_loop fixes it, D/retry and D/complete are yielded."""
        from services.agent_orchestrator import orchestrate
        from services.debug_loop import DebugAttempt, DebugResult
        from services.sandbox import ExecutionResult

        settings = _make_settings(debug_loop_enabled=True)

        fail_result = ExecutionResult(
            stdout="",
            stderr="NameError: x",
            elapsed_ms=100,
            output_files=[],
            success=False,
        )

        # Simulate: first exec (orchestrator Phase D) fails, then debug_loop fixes it
        debug_result_with_retry = DebugResult(
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
            patch("services.agent_orchestrator.OpenAIClient") as mock_cls,
            patch("services.agent_orchestrator.execute_code") as mock_exec,
            patch(
                "services.agent_orchestrator.run_debug_loop",
                new=AsyncMock(return_value=debug_result_with_retry),
            ),
        ):
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json(python_code="bad code")
            mock_cls.return_value = mock_instance

            # First execute_code call (Phase D initial check) fails
            mock_exec.return_value = fail_result

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id=None,
                    settings=settings,
                )
            ]

        d_entries = [e for e in entries if e.phase == "D"]
        actions = [e.action for e in d_entries]
        assert "retry" in actions
        assert "complete" in actions

    @pytest.mark.asyncio
    async def test_final_payload_has_debug_retries_field(self) -> None:
        """The final C/complete payload must include debug_retries field."""
        from services.agent_orchestrator import orchestrate
        from services.sandbox import ExecutionResult

        settings = _make_settings(debug_loop_enabled=True)

        with (
            patch("services.agent_orchestrator.OpenAIClient") as mock_cls,
            patch("services.agent_orchestrator.execute_code") as mock_exec,
        ):
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json()
            mock_cls.return_value = mock_instance

            mock_exec.return_value = ExecutionResult(
                stdout="ok",
                stderr="",
                elapsed_ms=100,
                output_files=[],
                success=True,
            )

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id=None,
                    settings=settings,
                )
            ]

        c_complete = next(
            e for e in entries if e.phase == "C" and e.action == "complete"
        )
        payload = json.loads(c_complete.content)
        assert "debug_retries" in payload

    @pytest.mark.asyncio
    async def test_final_payload_debug_retries_zero_on_first_success(self) -> None:
        """debug_retries is 0 when code succeeds on first execution."""
        from services.agent_orchestrator import orchestrate
        from services.sandbox import ExecutionResult

        settings = _make_settings(debug_loop_enabled=True)

        with (
            patch("services.agent_orchestrator.OpenAIClient") as mock_cls,
            patch("services.agent_orchestrator.execute_code") as mock_exec,
        ):
            mock_instance = MagicMock()
            mock_instance.generate_code.return_value = _phase_c_json()
            mock_cls.return_value = mock_instance

            mock_exec.return_value = ExecutionResult(
                stdout="ok",
                stderr="",
                elapsed_ms=100,
                output_files=[],
                success=True,
            )

            entries = [
                entry
                async for entry in orchestrate(
                    task="集計する",
                    file_id=None,
                    settings=settings,
                )
            ]

        c_complete = next(
            e for e in entries if e.phase == "C" and e.action == "complete"
        )
        payload = json.loads(c_complete.content)
        assert payload["debug_retries"] == 0
