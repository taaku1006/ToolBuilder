"""Phase A-C: exploration, reflection, and code generation engine.

Each phase is an async function that accepts injected dependencies so they
can be easily mocked in tests without patching module-level names.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from services.openai_client import OpenAIClient
from services.sandbox import ExecutionResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclasses — all frozen (immutable)
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Optional prompt manager (used when settings is available)
_settings_ref = None


def set_settings_ref(settings) -> None:
    """Store settings reference for prompt_manager access."""
    global _settings_ref
    _settings_ref = settings


def _load_prompt(name: str, fallback_file: str) -> str:
    """Load prompt via prompt_manager if available, else read file."""
    if _settings_ref is not None:
        try:
            from services.prompt_manager import get_prompt

            return get_prompt(name, _settings_ref)
        except Exception:
            pass
    path = _PROMPTS_DIR / fallback_file
    return path.read_text(encoding="utf-8")


@dataclass(frozen=True)
class PhaseAResult:
    """Result of Phase A — Excel structure exploration."""

    exploration_script: str
    exploration_output: str
    success: bool


@dataclass(frozen=True)
class PhaseBResult:
    """Result of Phase B — reflection on whether custom tools are needed."""

    needs_custom_tool: bool
    reason: str
    tool_code: str | None
    tool_output: str | None


@dataclass(frozen=True)
class PhaseCResult:
    """Result of Phase C — main Python code generation."""

    summary: str
    python_code: str
    steps: list[str]
    tips: str


# ---------------------------------------------------------------------------
# Phase A
# ---------------------------------------------------------------------------


async def run_phase_a(
    openai_client: OpenAIClient,
    sandbox_execute: object,  # callable: (code, **kwargs) -> ExecutionResult
    file_context: str,
    file_id: str | None = None,
    upload_dir: str = "./uploads",
    output_dir: str = "./outputs",
) -> PhaseAResult:
    """Generate an exploration script via OpenAI and execute it in the sandbox.

    Args:
        openai_client: Client for calling OpenAI.
        sandbox_execute: Callable matching execute_code's signature.
        file_context: Pre-built file context string (columns, types, etc.).
        file_id: Optional upload file ID to inject as INPUT_FILE.
        upload_dir: Directory containing uploaded files.
        output_dir: Parent directory for execution temp dirs.

    Returns:
        Frozen PhaseAResult with exploration_script, exploration_output, success.
    """
    logger.info(
        "Phase A started",
        extra={"file_id": file_id, "file_context_length": len(file_context)},
    )

    system_prompt = _load_prompt("phase_a_exploration", "phase_a_exploration.txt")

    # Build user prompt from file context
    user_prompt = f"【ファイル情報】\n{file_context}" if file_context else "ファイル情報なし"

    # Format the template placeholders that appear in the prompt file
    # The prompt file uses {file_context} as a placeholder
    formatted_system = system_prompt.replace("{file_context}", file_context or "")

    exploration_script = openai_client.generate_code(
        system_prompt=formatted_system,
        user_prompt=user_prompt,
    )

    # Execute the script in the sandbox — wrap sync call in a thread
    result: ExecutionResult = await asyncio.to_thread(
        sandbox_execute,
        exploration_script,
        file_id=file_id,
        upload_dir=upload_dir,
        output_dir=output_dir,
    )

    logger.info(
        "Phase A completed",
        extra={"success": result.success, "output_length": len(result.stdout)},
    )

    return PhaseAResult(
        exploration_script=exploration_script,
        exploration_output=result.stdout,
        success=result.success,
    )


# ---------------------------------------------------------------------------
# Phase B
# ---------------------------------------------------------------------------


async def run_phase_b(
    openai_client: OpenAIClient,
    sandbox_execute: object,  # callable: (code, **kwargs) -> ExecutionResult
    exploration_result: str,
    task: str,
    file_id: str | None = None,
    upload_dir: str = "./uploads",
    output_dir: str = "./outputs",
) -> PhaseBResult:
    """Reflect on whether specialised tools are needed.

    The prompt template is loaded from prompts/phase_b_reflect.txt.
    OpenAI is expected to return a JSON object with keys:
      needs_custom_tool (bool), reason (str), tool_code (str | null).

    If needs_custom_tool is True, tool_code is executed in the sandbox and
    its stdout is captured as tool_output.

    Raises:
        json.JSONDecodeError: If OpenAI does not return valid JSON.
        KeyError: If the JSON is missing required keys.
    """
    logger.info("Phase B started", extra={"task_length": len(task)})

    template = _load_prompt("phase_b_reflect", "phase_b_reflect.txt")

    formatted = (
        template
        .replace("{exploration_result}", exploration_result)
        .replace("{task}", task)
    )

    raw = openai_client.generate_code(
        system_prompt=formatted,
        user_prompt=f"探索結果を踏まえてツールの必要性を判断してください。\nタスク: {task}\n\n探索結果:\n{exploration_result}",
    )

    parsed: dict = json.loads(raw)
    needs_custom_tool: bool = bool(parsed["needs_custom_tool"])
    reason: str = str(parsed["reason"])
    tool_code: str | None = parsed.get("tool_code") or None

    tool_output: str | None = None
    if needs_custom_tool and tool_code:
        exec_result: ExecutionResult = await asyncio.to_thread(
            sandbox_execute,
            tool_code,
            file_id=file_id,
            upload_dir=upload_dir,
            output_dir=output_dir,
        )
        tool_output = exec_result.stdout

    logger.info(
        "Phase B completed",
        extra={"needs_custom_tool": needs_custom_tool, "reason_preview": reason[:100]},
    )

    return PhaseBResult(
        needs_custom_tool=needs_custom_tool,
        reason=reason,
        tool_code=tool_code,
        tool_output=tool_output,
    )


# ---------------------------------------------------------------------------
# Phase C
# ---------------------------------------------------------------------------


async def run_phase_c(
    openai_client: OpenAIClient,
    exploration_result: str,
    reflection_result: str,
    task: str,
    file_context: str | None = None,
) -> PhaseCResult:
    """Generate the main Python code using all accumulated context.

    The prompt template is loaded from prompts/phase_c_generate.txt.
    OpenAI is expected to return a JSON object with keys:
      summary, python_code, steps, tips.

    Raises:
        json.JSONDecodeError: If OpenAI does not return valid JSON.
        KeyError: If the JSON is missing required keys.
    """
    logger.info(
        "Phase C started",
        extra={"task_length": len(task), "has_file_context": file_context is not None},
    )

    template = _load_prompt("phase_c_generate", "phase_c_generate.txt")

    formatted_system = (
        template
        .replace("{exploration_result}", exploration_result)
        .replace("{tool_synthesis_result}", reflection_result)
        .replace("{file_context}", file_context or "")
        .replace("{task}", task)
    )

    user_prompt = (
        f"【タスク】\n{task}\n\n"
        f"【探索結果】\n{exploration_result}\n\n"
        f"【ツール合成結果】\n{reflection_result}"
    )

    raw = openai_client.generate_code(
        system_prompt=formatted_system,
        user_prompt=user_prompt,
    )

    parsed: dict = json.loads(raw)

    logger.info(
        "Phase C completed",
        extra={"code_length": len(parsed["python_code"]), "steps_count": len(parsed["steps"])},
    )

    return PhaseCResult(
        summary=parsed["summary"],
        python_code=parsed["python_code"],
        steps=parsed["steps"],
        tips=parsed["tips"],
    )


# ---------------------------------------------------------------------------
# Phase C for subtasks
# ---------------------------------------------------------------------------


async def run_phase_c_subtask(
    openai_client: OpenAIClient,
    subtask_title: str,
    subtask_description: str,
    task: str,
    exploration_result: str,
    file_context: str | None,
    completed_summaries: str,
    available_files: str,
) -> str:
    """Generate Python code for a single sub-task.

    Returns raw Python code string (not JSON).
    This is Phase C's responsibility, moved from task_planner.run_subtask().
    """
    logger.info(
        "Phase C subtask started",
        extra={"subtask_title": subtask_title},
    )

    template = _load_prompt("phase_c_subtask", "phase_c_subtask.txt")
    prompt = (
        template
        .replace("{task}", task)
        .replace("{subtask_title}", subtask_title)
        .replace("{subtask_description}", subtask_description)
        .replace("{completed_summaries}", completed_summaries)
        .replace("{available_files}", available_files)
        .replace("{exploration_result}", exploration_result)
        .replace("{file_context}", file_context or "")
    )

    code = openai_client.generate_code(
        system_prompt=prompt,
        user_prompt=f"サブタスク「{subtask_title}」のPythonコードを生成してください。",
    )

    logger.info(
        "Phase C subtask completed",
        extra={"subtask_title": subtask_title, "code_length": len(code)},
    )

    return code
