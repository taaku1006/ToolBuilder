"""Phase handler functions for agent orchestration.

Each public handler is an async generator that yields AgentLogEntry objects.
Optional state dataclasses capture mutable outputs so callers can read results.

Import hierarchy (no circular imports):
  orchestrator_types  <-- phase_handlers
  phase_handlers      <-- agent_orchestrator
"""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from pathlib import Path

from core.config import Settings
from services.debug_loop import run_debug_loop
from services.openai_client import OpenAIClient
from services.orchestrator_types import AgentLogEntry, CancelledError, _now_iso
from services.reflection_engine import run_phase_a, run_phase_b, run_phase_c_subtask
from services.sandbox import execute_code
from services.task_planner import run_planner


# ---------------------------------------------------------------------------
# Phase state dataclasses (mutable output containers)
# ---------------------------------------------------------------------------


@dataclass
class PhaseAState:
    """Mutable output state for handle_phase_a."""
    exploration_result: str = ""
    phase_tokens: int = 0


@dataclass
class PhaseBState:
    """Mutable output state for handle_phase_b."""
    reflection_result: str = ""
    phase_tokens: int = 0


@dataclass
class PhaseDState:
    """Mutable output state for handle_phase_d."""
    python_code: str = ""
    debug_retries: int = 0
    exec_succeeded: bool = True
    phase_tokens: int = 0


@dataclass
class PhasePState:
    """Mutable output state for handle_phase_p."""
    decomposition_succeeded: bool = False
    decomp_final_code: str = ""
    plan: object = None
    phase_tokens: int = 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_cancel(cancel_check: Callable | None) -> None:
    if cancel_check is not None and cancel_check():
        raise CancelledError("Orchestration cancelled")


# ---------------------------------------------------------------------------
# Phase A — Excel structure exploration
# ---------------------------------------------------------------------------


async def handle_phase_a(
    openai_client: OpenAIClient,
    settings: Settings,
    task: str,
    file_id: str | None,
    file_context: str | None,
    cancel_check: Callable | None,
    trace: object,
    state: PhaseAState | None = None,
) -> AsyncGenerator[AgentLogEntry, None]:
    """Run Phase A (exploration). Skipped when reflection disabled or no file."""
    if not (file_id and settings.reflection_enabled):
        return

    _check_cancel(cancel_check)

    if trace:
        trace.start_phase("A")
    yield AgentLogEntry(
        phase="A", action="start",
        content="Phase A: Excelファイル構造の探索を開始します",
        timestamp=_now_iso(),
    )

    phase_a = await run_phase_a(
        openai_client=openai_client,
        sandbox_execute=execute_code,
        file_context=file_context or "",
        file_id=file_id,
        upload_dir=settings.upload_dir,
        output_dir=settings.output_dir,
        settings=settings,
    )

    if state is not None:
        state.exploration_result = phase_a.exploration_output

    if trace:
        trace.end_phase(
            "A",
            output=phase_a.exploration_output[:500],
            status="complete" if phase_a.success else "error",
        )
    yield AgentLogEntry(
        phase="A",
        action="complete" if phase_a.success else "error",
        content=phase_a.exploration_output,
        timestamp=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Phase B — reflection / tool synthesis
# ---------------------------------------------------------------------------


async def handle_phase_b(
    openai_client: OpenAIClient,
    settings: Settings,
    task: str,
    file_id: str | None,
    file_context: str | None,
    exploration_result: str,
    cancel_check: Callable | None,
    trace: object,
    state: PhaseBState | None = None,
) -> AsyncGenerator[AgentLogEntry, None]:
    """Run Phase B (reflection). Skipped when phase disabled or no file."""
    if not (file_id and settings.reflection_phase_enabled):
        return

    _check_cancel(cancel_check)

    if trace:
        trace.start_phase("B")
    yield AgentLogEntry(
        phase="B", action="start",
        content="Phase B: ツール必要性の内省を開始します",
        timestamp=_now_iso(),
    )

    phase_b = await run_phase_b(
        openai_client=openai_client,
        sandbox_execute=execute_code,
        exploration_result=exploration_result,
        task=task,
        file_id=file_id,
        upload_dir=settings.upload_dir,
        output_dir=settings.output_dir,
        settings=settings,
    )

    reflection_result = json.dumps(
        {
            "needs_custom_tool": phase_b.needs_custom_tool,
            "reason": phase_b.reason,
            "tool_output": phase_b.tool_output,
        },
        ensure_ascii=False,
    )

    if state is not None:
        state.reflection_result = reflection_result

    if trace:
        trace.end_phase("B", output=reflection_result[:500])
    yield AgentLogEntry(
        phase="B", action="complete",
        content=reflection_result,
        timestamp=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Phase P — task decomposition
# ---------------------------------------------------------------------------


async def handle_phase_p(
    openai_client: OpenAIClient,
    settings: Settings,
    task: str,
    file_id: str | None,
    file_context: str | None,
    exploration_result: str,
    reflection_result: str,
    cancel_check: Callable | None,
    trace: object,
    state: PhasePState | None = None,
) -> AsyncGenerator[AgentLogEntry, None]:
    """Run Phase P (task decomposition). Skipped when disabled or no file."""
    if not (settings.task_decomposition_enabled and file_id):
        return

    _check_cancel(cancel_check)

    if trace:
        trace.start_phase("P")
    yield AgentLogEntry(
        phase="P", action="start",
        content="Phase P: タスク分解を開始します",
        timestamp=_now_iso(),
    )

    plan = await run_planner(
        openai_client=openai_client,
        task=task,
        exploration_result=exploration_result,
        reflection_result=reflection_result,
        file_context=file_context,
        max_subtasks=settings.max_subtasks,
        settings=settings,
    )

    if not plan.decompose:
        if trace:
            trace.end_phase("P", output={"decompose": False})
        if state is not None:
            state.plan = plan
        yield AgentLogEntry(
            phase="P", action="complete",
            content=f"単一ステップで実行可能と判断: {plan.reasoning}",
            timestamp=_now_iso(),
        )
        return

    # Decomposition path
    yield AgentLogEntry(
        phase="P", action="info",
        content=f"タスクを{len(plan.subtasks)}個のサブタスクに分解します: {plan.reasoning}",
        timestamp=_now_iso(),
    )

    workspace_dir = str(Path(settings.output_dir) / f"workspace_{uuid.uuid4()}")
    Path(workspace_dir).mkdir(parents=True, exist_ok=True)

    all_code_parts: list[str] = []
    completed_summaries_parts: list[str] = []
    subtask_failed = False

    for subtask in plan.subtasks:
        _check_cancel(cancel_check)
        result = await _run_subtask_with_result(
            subtask=subtask,
            task=task,
            openai_client=openai_client,
            settings=settings,
            file_id=file_id,
            file_context=file_context,
            exploration_result=exploration_result,
            workspace_dir=workspace_dir,
            completed_summaries="\n".join(completed_summaries_parts) or "(none)",
        )
        async for entry in result["entries"]:
            yield entry

        if result["success"]:
            all_code_parts.append(
                f"# === サブタスク {subtask.id}: {subtask.title} ===\n{result['code']}"
            )
            completed_summaries_parts.append(f"Step {subtask.id} ({subtask.title}): 成功")
        else:
            subtask_failed = True
            break

    decomp_final_code = "\n\n".join(all_code_parts)
    if trace:
        trace.end_phase("P", output={"decompose": True, "success": not subtask_failed})
    if state is not None:
        state.decomposition_succeeded = not subtask_failed
        state.decomp_final_code = decomp_final_code
        state.plan = plan
    yield AgentLogEntry(
        phase="P",
        action="complete" if not subtask_failed else "error",
        content=json.dumps(
            {"success": not subtask_failed, "final_code": decomp_final_code},
            ensure_ascii=False,
        ),
        timestamp=_now_iso(),
    )



async def _run_subtask_with_result(
    subtask, task, openai_client, settings, file_id,
    file_context, exploration_result, workspace_dir, completed_summaries,
) -> dict:
    """Run a single subtask and return a dict with entries (async gen), code, and success."""
    phase_label = f"C.{subtask.id}"
    entries: list[AgentLogEntry] = []
    ws_path = Path(workspace_dir)
    available_files = (
        "\n".join(p.name for p in ws_path.iterdir() if p.is_file() and p.name != "script.py")
        or "(empty)"
    )

    entries.append(AgentLogEntry(
        phase=phase_label, action="start",
        content=f"サブタスク {subtask.id}: {subtask.title}",
        timestamp=_now_iso(),
    ))

    code = await run_phase_c_subtask(
        openai_client=openai_client,
        subtask_title=subtask.title,
        subtask_description=subtask.description,
        task=task,
        exploration_result=exploration_result,
        file_context=file_context,
        completed_summaries=completed_summaries,
        available_files=available_files,
        settings=settings,
    )

    exec_result = await asyncio.to_thread(
        execute_code, code,
        file_id=file_id,
        upload_dir=settings.upload_dir,
        output_dir=workspace_dir,
        timeout=settings.exec_timeout,
    )

    if not exec_result.success:
        debug_label = f"D.{subtask.id}"
        entries.append(AgentLogEntry(
            phase=debug_label, action="start",
            content=f"サブタスク {subtask.id} デバッグ開始",
            timestamp=_now_iso(),
        ))
        debug_result = await run_debug_loop(
            code=code,
            task=f"{task}\nサブタスク: {subtask.title}\n{subtask.description}",
            openai_client=openai_client,
            sandbox_execute=execute_code,
            file_id=file_id, file_context=file_context,
            upload_dir=settings.upload_dir,
            output_dir=workspace_dir,
            timeout=settings.exec_timeout,
            max_retries=settings.subtask_debug_retries,
            settings=settings,
        )
        if debug_result.success:
            code = debug_result.final_code
            exec_result = type(exec_result)(
                stdout=debug_result.final_stdout,
                stderr=debug_result.final_stderr,
                elapsed_ms=0, output_files=[], success=True,
            )
        entries.append(AgentLogEntry(
            phase=debug_label,
            action="complete" if debug_result.success else "error",
            content=f"デバッグ {'成功' if debug_result.success else '失敗'} (retries: {debug_result.total_retries})",
            timestamp=_now_iso(),
        ))

    if exec_result.success:
        # Copy outputs to workspace
        for fpath in exec_result.output_files:
            src = Path(fpath)
            if src.exists():
                shutil.copy2(src, ws_path / src.name)
        entries.append(AgentLogEntry(
            phase=phase_label, action="complete",
            content=f"サブタスク {subtask.id} 完了",
            timestamp=_now_iso(),
        ))
    else:
        entries.append(AgentLogEntry(
            phase=phase_label, action="error",
            content=f"サブタスク {subtask.id} 失敗",
            timestamp=_now_iso(),
        ))

    async def _gen():
        for e in entries:
            yield e

    return {"entries": _gen(), "code": code, "success": exec_result.success}


# ---------------------------------------------------------------------------
# Phase D — autonomous debugging loop
# ---------------------------------------------------------------------------


async def handle_phase_d(
    openai_client: OpenAIClient,
    settings: Settings,
    task: str,
    file_id: str | None,
    file_context: str | None,
    python_code: str,
    cancel_check: Callable | None,
    trace: object,
    state: PhaseDState | None = None,
) -> AsyncGenerator[AgentLogEntry, None]:
    """Run Phase D (debug loop). Skipped when debug_loop disabled."""
    if not settings.debug_loop_enabled:
        return

    _check_cancel(cancel_check)

    if trace:
        trace.start_phase("D")
    yield AgentLogEntry(
        phase="D", action="start",
        content="Phase D: 自律デバッグループを開始します",
        timestamp=_now_iso(),
    )

    first_exec = await asyncio.to_thread(
        execute_code,
        python_code,
        file_id=file_id,
        upload_dir=settings.upload_dir,
        output_dir=settings.output_dir,
        timeout=settings.exec_timeout,
    )

    if first_exec.success:
        if trace:
            trace.end_phase("D", output="初回実行で成功")
        if state is not None:
            state.python_code = python_code
            state.debug_retries = 0
            state.exec_succeeded = True
        yield AgentLogEntry(
            phase="D", action="complete",
            content="初回実行で成功",
            timestamp=_now_iso(),
        )
        return

    debug_result = await run_debug_loop(
        code=python_code,
        task=task,
        openai_client=openai_client,
        sandbox_execute=execute_code,
        file_id=file_id,
        file_context=file_context,
        upload_dir=settings.upload_dir,
        output_dir=settings.output_dir,
        timeout=settings.exec_timeout,
        max_retries=settings.debug_retry_limit,
        settings=settings,
    )

    for attempt in debug_result.attempts:
        yield AgentLogEntry(
            phase="D", action="retry",
            content=f"リトライ {attempt.retry_num}: {attempt.error[:100]}",
            timestamp=_now_iso(),
        )

    if debug_result.success:
        if trace:
            trace.end_phase("D", output=f"{debug_result.total_retries}回のリトライで成功")
        if state is not None:
            state.python_code = debug_result.final_code
            state.debug_retries = debug_result.total_retries
            state.exec_succeeded = True
        yield AgentLogEntry(
            phase="D", action="complete",
            content=f"{debug_result.total_retries}回のリトライで成功",
            timestamp=_now_iso(),
        )
    else:
        if trace:
            trace.end_phase("D", output=f"{settings.debug_retry_limit}回リトライ失敗", status="error")
        if state is not None:
            state.python_code = python_code
            state.debug_retries = debug_result.total_retries
            state.exec_succeeded = False
        yield AgentLogEntry(
            phase="D", action="error",
            content=f"{settings.debug_retry_limit}回リトライしましたが解決できませんでした",
            timestamp=_now_iso(),
        )


# ---------------------------------------------------------------------------
# Phase E — skill save suggestion
# ---------------------------------------------------------------------------


async def handle_phase_e(
    settings: Settings,
    task: str,
    python_code: str,
    phase_c_summary: str,
    exec_succeeded: bool,
    cancel_check: Callable | None,
    trace: object,
) -> AsyncGenerator[AgentLogEntry, None]:
    """Run Phase E (skill save suggestion). Skipped when skills disabled."""
    if not settings.skills_enabled:
        return

    _check_cancel(cancel_check)

    if trace:
        trace.start_phase("E")
    yield AgentLogEntry(
        phase="E", action="start",
        content="Phase E: スキル保存の提案を確認します",
        timestamp=_now_iso(),
    )

    if exec_succeeded:
        suggestion_payload = json.dumps(
            {
                "suggest_save": True,
                "python_code": python_code,
                "task_summary": phase_c_summary or task,
                "message": "実行が成功しました。このコードをスキルとして保存することをお勧めします。",
            },
            ensure_ascii=False,
        )
        if trace:
            trace.end_phase("E", output={"suggest_save": True})
        yield AgentLogEntry(
            phase="E", action="complete",
            content=suggestion_payload,
            timestamp=_now_iso(),
        )
    else:
        if trace:
            trace.end_phase("E", output={"suggest_save": False})
        yield AgentLogEntry(
            phase="E", action="complete",
            content=json.dumps(
                {"suggest_save": False, "message": "実行が失敗したためスキル保存は提案しません。"},
                ensure_ascii=False,
            ),
            timestamp=_now_iso(),
        )
