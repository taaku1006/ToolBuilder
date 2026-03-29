"""Phase D: Autonomous debug loop.

Executes Python code in a sandbox, and if it fails, asks OpenAI to produce
a fixed version, then retries.  Repeats up to max_retries times.

All dependencies (OpenAI client, sandbox callable) are injected as parameters
so the module can be tested without any module-level patching.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from services.openai_client import OpenAIClient
from services.sandbox import ExecutionResult

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# ---------------------------------------------------------------------------
# Immutable result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DebugAttempt:
    """Record of a single debug-and-retry attempt."""

    retry_num: int   # 1-based retry counter
    error: str       # stderr (or stdout fallback) from the failed execution
    fixed_code: str  # code suggested by OpenAI for this retry
    success: bool    # whether the fixed_code execution succeeded


@dataclass(frozen=True)
class DebugResult:
    """Final result of the autonomous debug loop."""

    final_code: str                # last code that was executed (original or fixed)
    final_stdout: str              # stdout from the last execution
    final_stderr: str              # stderr from the last execution
    success: bool                  # True if any execution succeeded
    attempts: list[DebugAttempt]   # one entry per retry performed (not for initial run)
    total_retries: int             # number of retries actually performed


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------


def _load_debug_prompt() -> str:
    """Load the Phase D debug prompt template."""
    try:
        from services.reflection_engine import _settings_ref

        if _settings_ref is not None:
            from services.prompt_manager import get_prompt

            return get_prompt("phase_d_debug", _settings_ref)
    except Exception:
        pass
    prompt_path = _PROMPTS_DIR / "phase_d_debug.txt"
    return prompt_path.read_text(encoding="utf-8")


def _build_debug_prompt(
    task: str,
    code: str,
    stderr: str,
    stdout: str,
    file_context: str,
) -> str:
    """Substitute template placeholders and return the formatted prompt."""
    template = _load_debug_prompt()
    return (
        template
        .replace("{task}", task)
        .replace("{code}", code)
        .replace("{stderr}", stderr)
        .replace("{stdout}", stdout)
        .replace("{file_context}", file_context)
    )


# ---------------------------------------------------------------------------
# Main debug loop
# ---------------------------------------------------------------------------


async def run_debug_loop(
    code: str,
    task: str,
    openai_client: OpenAIClient,
    sandbox_execute: object,  # callable: (code, **kwargs) -> ExecutionResult
    file_id: str | None = None,
    file_context: str | None = None,
    upload_dir: str = "./uploads",
    output_dir: str = "./outputs",
    timeout: int = 30,
    max_retries: int = 3,
) -> DebugResult:
    """Execute code in the sandbox; on failure ask OpenAI to fix it and retry.

    Loop:
    1. Execute code in sandbox (wrapped in asyncio.to_thread).
    2. If success -> return immediately with 0 retries.
    3. If failure -> build debug prompt with error + code + context.
    4. Call OpenAI for fixed code.
    5. Retry with fixed code (up to max_retries).
    6. If max_retries exceeded -> return with success=False.

    Args:
        code: Initial Python source code to execute.
        task: Original user task description (used in prompt context).
        openai_client: Client for calling OpenAI to obtain fixed code.
        sandbox_execute: Callable matching execute_code's signature.
        file_id: Optional upload file ID injected as INPUT_FILE.
        file_context: Pre-built file context string for the prompt.
        upload_dir: Directory containing uploaded files.
        output_dir: Parent directory for execution temp dirs.
        timeout: Maximum execution time in seconds for each run.
        max_retries: Maximum number of fix-and-retry cycles.

    Returns:
        Frozen DebugResult with final code, stdout/stderr, success flag,
        attempts list, and total_retries count.
    """
    logger.info(
        "Debug loop started",
        extra={"max_retries": max_retries, "code_length": len(code)},
    )

    current_code = code
    attempts: list[DebugAttempt] = []

    # Helper: execute current_code in a thread
    async def _execute(exec_code: str) -> ExecutionResult:
        return await asyncio.to_thread(
            sandbox_execute,  # type: ignore[arg-type]
            exec_code,
            file_id=file_id,
            upload_dir=upload_dir,
            output_dir=output_dir,
            timeout=timeout,
        )

    # Initial execution
    exec_result = await _execute(current_code)

    if exec_result.success:
        logger.info("Debug loop: initial execution succeeded")
        return DebugResult(
            final_code=current_code,
            final_stdout=exec_result.stdout,
            final_stderr=exec_result.stderr,
            success=True,
            attempts=[],
            total_retries=0,
        )

    # Retry loop
    for retry_num in range(1, max_retries + 1):
        error_text = exec_result.stderr or exec_result.stdout
        logger.info(
            "Debug loop retry",
            extra={"retry_num": retry_num, "error_preview": error_text[:200]},
        )

        # Build the debug prompt and ask OpenAI for a fix
        debug_prompt = _build_debug_prompt(
            task=task,
            code=current_code,
            stderr=exec_result.stderr,
            stdout=exec_result.stdout,
            file_context=file_context or "",
        )

        fixed_code: str = openai_client.generate_code(  # type: ignore[union-attr]
            system_prompt=debug_prompt,
            user_prompt=f"エラーを修正してください。\n\nエラー:\n{error_text}",
        )

        # Execute the fixed code
        exec_result = await _execute(fixed_code)
        current_code = fixed_code

        attempt = DebugAttempt(
            retry_num=retry_num,
            error=error_text,
            fixed_code=fixed_code,
            success=exec_result.success,
        )
        attempts = [*attempts, attempt]

        if exec_result.success:
            logger.info("Debug loop: retry succeeded", extra={"retry_num": retry_num})
            return DebugResult(
                final_code=current_code,
                final_stdout=exec_result.stdout,
                final_stderr=exec_result.stderr,
                success=True,
                attempts=attempts,
                total_retries=retry_num,
            )

    # All retries exhausted
    logger.warning("Debug loop exhausted", extra={"max_retries": max_retries})
    return DebugResult(
        final_code=current_code,
        final_stdout=exec_result.stdout,
        final_stderr=exec_result.stderr,
        success=False,
        attempts=attempts,
        total_retries=max_retries,
    )
