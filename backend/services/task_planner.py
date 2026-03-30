"""Phase P: Task decomposition planner.

Analyzes a task and optionally breaks it into ordered sub-tasks.
Each sub-task is then generated, executed, and verified independently.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from services.openai_client import OpenAIClient
from services.sandbox import ExecutionResult

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# ---------------------------------------------------------------------------
# Immutable data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubTask:
    """A single sub-task within a decomposition plan."""

    id: int
    title: str
    description: str
    depends_on: tuple[int, ...]
    expected_output: str


@dataclass(frozen=True)
class PlanResult:
    """Result of the planner's analysis."""

    decompose: bool
    subtasks: tuple[SubTask, ...]
    reasoning: str


@dataclass(frozen=True)
class SubTaskResult:
    """Result of executing a single sub-task."""

    subtask_id: int
    code: str
    stdout: str
    success: bool
    output_files: tuple[str, ...]
    debug_retries: int


@dataclass(frozen=True)
class DecompositionResult:
    """Final result of the full decomposition pipeline."""

    subtask_results: tuple[SubTaskResult, ...]
    final_code: str
    success: bool
    total_subtasks: int
    failed_subtask_id: int | None


# ---------------------------------------------------------------------------
# AgentLogEntry import (avoid circular dependency at module level)
# ---------------------------------------------------------------------------


def _make_log_entry(phase: str, action: str, content: str):
    """Create an AgentLogEntry without top-level import."""
    from services.agent_orchestrator import AgentLogEntry

    return AgentLogEntry(
        phase=phase,
        action=action,
        content=content,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Prompt loaders
# ---------------------------------------------------------------------------


def _load_prompt(name: str) -> str:
    """Load a prompt template, preferring Langfuse when available."""
    try:
        from services.reflection_engine import _settings_ref

        if _settings_ref is not None:
            from services.prompt_manager import get_prompt

            return get_prompt(name, _settings_ref)
    except Exception:
        pass
    prompt_path = _PROMPTS_DIR / f"{name}.txt"
    return prompt_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Planner: decides whether to decompose and produces sub-tasks
# ---------------------------------------------------------------------------


async def run_planner(
    openai_client: OpenAIClient,
    task: str,
    exploration_result: str,
    reflection_result: str,
    file_context: str | None,
    max_subtasks: int = 5,
) -> PlanResult:
    """Analyze a task and decide whether to decompose it.

    Returns a PlanResult. When decompose=False, subtasks contains
    a single entry representing the whole task.
    """
    template = _load_prompt("phase_p_plan")
    prompt = (
        template
        .replace("{task}", task)
        .replace("{exploration_result}", exploration_result)
        .replace("{reflection_result}", reflection_result)
        .replace("{file_context}", file_context or "")
        .replace("{max_subtasks}", str(max_subtasks))
    )

    response = openai_client.generate_code(
        system_prompt=prompt,
        user_prompt="タスクを分析し、分解要否をJSON形式で返してください。",
    )

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        logger.warning("Planner returned invalid JSON, falling back to no decomposition")
        return PlanResult(
            decompose=False,
            subtasks=(SubTask(
                id=1, title="Full task", description=task,
                depends_on=(), expected_output="output.xlsx",
            ),),
            reasoning="JSON parse error - fallback",
        )

    decompose = data.get("decompose", False)
    reasoning = data.get("reasoning", "")
    raw_subtasks = data.get("subtasks", [])

    # Enforce max_subtasks limit
    raw_subtasks = raw_subtasks[:max_subtasks]

    subtasks = tuple(
        SubTask(
            id=st.get("id", i + 1),
            title=st.get("title", f"Step {i + 1}"),
            description=st.get("description", ""),
            depends_on=tuple(st.get("depends_on", [])),
            expected_output=st.get("expected_output", f"step_{i + 1}_output.xlsx"),
        )
        for i, st in enumerate(raw_subtasks)
    )

    if not subtasks:
        subtasks = (SubTask(
            id=1, title="Full task", description=task,
            depends_on=(), expected_output="output.xlsx",
        ),)
        decompose = False

    return PlanResult(decompose=decompose, subtasks=subtasks, reasoning=reasoning)


# ---------------------------------------------------------------------------
# Sub-task execution with mini debug loop
# ---------------------------------------------------------------------------


async def run_subtask(
    openai_client: OpenAIClient,
    sandbox_execute,
    subtask: SubTask,
    task: str,
    exploration_result: str,
    file_context: str | None,
    completed_summaries: str,
    available_files: str,
    file_id: str | None,
    upload_dir: str,
    output_dir: str,
    workspace_dir: str,
    timeout: int = 30,
    max_debug_retries: int = 2,
) -> SubTaskResult:
    """Generate and execute code for a single sub-task.

    Includes a mini debug loop (up to max_debug_retries).
    The workspace_dir contains accumulated intermediate files from
    prior sub-tasks.
    """
    template = _load_prompt("phase_p_subtask")
    prompt = (
        template
        .replace("{task}", task)
        .replace("{subtask_title}", subtask.title)
        .replace("{subtask_description}", subtask.description)
        .replace("{completed_summaries}", completed_summaries)
        .replace("{available_files}", available_files)
        .replace("{exploration_result}", exploration_result)
        .replace("{file_context}", file_context or "")
    )

    code = openai_client.generate_code(
        system_prompt=prompt,
        user_prompt=f"サブタスク「{subtask.title}」のPythonコードを生成してください。",
    )

    # Execute with workspace as output dir
    exec_result: ExecutionResult = await asyncio.to_thread(
        sandbox_execute,
        code,
        file_id=file_id,
        upload_dir=upload_dir,
        output_dir=workspace_dir,
        timeout=timeout,
    )

    debug_retries = 0

    if not exec_result.success and max_debug_retries > 0:
        debug_prompt_template = _load_prompt("phase_d_debug")

        for retry_num in range(1, max_debug_retries + 1):
            error_text = exec_result.stderr or exec_result.stdout
            debug_prompt = (
                debug_prompt_template
                .replace("{task}", f"{task}\n\nサブタスク: {subtask.title}\n{subtask.description}")
                .replace("{code}", code)
                .replace("{stderr}", exec_result.stderr)
                .replace("{stdout}", exec_result.stdout)
                .replace("{file_context}", file_context or "")
            )

            code = openai_client.generate_code(
                system_prompt=debug_prompt,
                user_prompt=f"エラーを修正してください。\n\nエラー:\n{error_text}",
            )

            exec_result = await asyncio.to_thread(
                sandbox_execute,
                code,
                file_id=file_id,
                upload_dir=upload_dir,
                output_dir=workspace_dir,
                timeout=timeout,
            )
            debug_retries = retry_num

            if exec_result.success:
                break

    return SubTaskResult(
        subtask_id=subtask.id,
        code=code,
        stdout=exec_result.stdout,
        success=exec_result.success,
        output_files=tuple(exec_result.output_files),
        debug_retries=debug_retries,
    )


# ---------------------------------------------------------------------------
# Full decomposition pipeline (async generator)
# ---------------------------------------------------------------------------


async def run_decomposition(
    openai_client: OpenAIClient,
    sandbox_execute,
    plan: PlanResult,
    task: str,
    exploration_result: str,
    file_context: str | None,
    file_id: str | None,
    upload_dir: str,
    output_dir: str,
    timeout: int = 30,
    max_debug_retries: int = 2,
):
    """Execute all sub-tasks in order, yielding AgentLogEntry events.

    Creates a shared workspace directory for intermediate files.
    Each sub-task's outputs are accumulated in the workspace.

    Yields AgentLogEntry objects with phase "P.1", "P.2", etc.
    """
    workspace_id = str(uuid.uuid4())
    workspace_dir = str(Path(output_dir) / f"workspace_{workspace_id}")
    Path(workspace_dir).mkdir(parents=True, exist_ok=True)

    subtask_results: list[SubTaskResult] = []
    completed_summaries_parts: list[str] = []
    all_code_parts: list[str] = []
    failed_subtask_id: int | None = None

    for subtask in plan.subtasks:
        phase_label = f"P.{subtask.id}"

        yield _make_log_entry(
            phase=phase_label,
            action="start",
            content=f"サブタスク {subtask.id}: {subtask.title}",
        )

        # List files currently in workspace
        ws_path = Path(workspace_dir)
        available_files = "\n".join(
            p.name for p in ws_path.iterdir() if p.is_file() and p.name != "script.py"
        ) or "(empty)"

        completed_summaries = "\n".join(completed_summaries_parts) or "(none)"

        result = await run_subtask(
            openai_client=openai_client,
            sandbox_execute=sandbox_execute,
            subtask=subtask,
            task=task,
            exploration_result=exploration_result,
            file_context=file_context,
            completed_summaries=completed_summaries,
            available_files=available_files,
            file_id=file_id,
            upload_dir=upload_dir,
            output_dir=output_dir,
            workspace_dir=workspace_dir,
            timeout=timeout,
            max_debug_retries=max_debug_retries,
        )

        subtask_results.append(result)

        if result.success:
            completed_summaries_parts.append(
                f"Step {subtask.id} ({subtask.title}): 成功 - stdout: {result.stdout[:200]}"
            )
            all_code_parts.append(
                f"# === サブタスク {subtask.id}: {subtask.title} ===\n{result.code}"
            )

            # Copy output files to workspace for next subtask
            for fpath in result.output_files:
                src = Path(fpath)
                if src.exists() and src.is_file():
                    dest = ws_path / src.name
                    shutil.copy2(src, dest)

            yield _make_log_entry(
                phase=phase_label,
                action="complete",
                content=f"サブタスク {subtask.id} 完了 (retries: {result.debug_retries})",
            )
        else:
            failed_subtask_id = subtask.id
            yield _make_log_entry(
                phase=phase_label,
                action="error",
                content=f"サブタスク {subtask.id} 失敗: {result.stdout[:200]}",
            )
            break

    overall_success = failed_subtask_id is None
    final_code = "\n\n".join(all_code_parts) if all_code_parts else ""

    decomp_result = DecompositionResult(
        subtask_results=tuple(subtask_results),
        final_code=final_code,
        success=overall_success,
        total_subtasks=len(plan.subtasks),
        failed_subtask_id=failed_subtask_id,
    )

    # Collect all output files in workspace
    workspace_output_files = [
        str(p) for p in Path(workspace_dir).iterdir()
        if p.is_file() and p.name != "script.py"
    ]

    # Yield final decomposition summary
    yield _make_log_entry(
        phase="P",
        action="complete" if overall_success else "error",
        content=json.dumps({
            "success": overall_success,
            "total_subtasks": decomp_result.total_subtasks,
            "completed": len([r for r in subtask_results if r.success]),
            "failed_subtask_id": failed_subtask_id,
            "final_code": final_code,
            "workspace_dir": workspace_dir,
            "output_files": workspace_output_files,
        }, ensure_ascii=False),
    )
