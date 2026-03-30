"""Phase F: Evaluation-driven debug loop.

Retries code when it runs successfully but produces incorrect output.
Uses mechanical Excel comparison as the loop gate, and LLM evaluation
agent on the first iteration for rich diagnostic feedback.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from services.excel_comparator import ComparisonResult, compare_excel_files, find_best_output_match
from services.openai_client import OpenAIClient
from services.sandbox import ExecutionResult
from services.xlsx_parser import build_file_context, parse_file

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# ---------------------------------------------------------------------------
# Immutable result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvalDebugAttempt:
    """Record of a single evaluation-driven retry attempt."""

    retry_num: int
    mechanical_score: float
    eval_reasoning: str | None
    comparison_summary: str
    fixed_code: str
    success: bool


@dataclass(frozen=True)
class EvalDebugResult:
    """Final result of the evaluation-driven debug loop."""

    final_code: str
    final_score: float
    success: bool
    attempts: list[EvalDebugAttempt]
    total_retries: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_eval_debug_prompt() -> str:
    """Load the Phase F prompt template."""
    try:
        from services.reflection_engine import _settings_ref

        if _settings_ref is not None:
            from services.prompt_manager import get_prompt

            return get_prompt("phase_f_eval_debug", _settings_ref)
    except Exception:
        pass
    prompt_path = _PROMPTS_DIR / "phase_f_eval_debug.txt"
    return prompt_path.read_text(encoding="utf-8")


def _build_comparison_summary(result: ComparisonResult) -> str:
    """Build a human-readable summary of the mechanical comparison."""
    lines = [f"Overall score: {result.overall_score:.2%}"]
    if result.missing_sheets:
        lines.append(f"Missing sheets: {', '.join(result.missing_sheets)}")
    if result.extra_sheets:
        lines.append(f"Extra sheets: {', '.join(result.extra_sheets)}")
    for sr in result.sheet_results:
        lines.append(
            f"  Sheet '{sr.sheet_name}': "
            f"header={sr.header_score:.0%}, structure={sr.structure_score:.0%}, "
            f"cells={sr.cell_value_score:.0%} "
            f"({sr.mismatched_cells}/{sr.total_cells} mismatched, "
            f"rows: {sr.row_count_actual}/{sr.row_count_expected}, "
            f"cols: {sr.col_count_actual}/{sr.col_count_expected})"
        )
    if result.error:
        lines.append(f"Error: {result.error}")
    return "\n".join(lines)


def _build_eval_debug_prompt(
    task: str,
    code: str,
    expected_context: str,
    comparison_summary: str,
    eval_reasoning: str,
    file_context: str,
) -> str:
    """Substitute template placeholders and return the formatted prompt."""
    template = _load_eval_debug_prompt()
    return (
        template
        .replace("{task}", task)
        .replace("{code}", code)
        .replace("{expected_context}", expected_context)
        .replace("{comparison_summary}", comparison_summary)
        .replace("{eval_reasoning}", eval_reasoning)
        .replace("{file_context}", file_context)
    )


# ---------------------------------------------------------------------------
# Main evaluation-driven debug loop
# ---------------------------------------------------------------------------


async def run_eval_debug_loop(
    code: str,
    task: str,
    expected_file_path: str,
    openai_client: OpenAIClient,
    sandbox_execute,
    file_id: str | None = None,
    file_context: str | None = None,
    upload_dir: str = "./uploads",
    output_dir: str = "./outputs",
    timeout: int = 30,
    max_retries: int = 3,
    quality_threshold: float = 0.85,
    settings=None,
) -> EvalDebugResult:
    """Execute code and retry when output quality is below threshold.

    Uses mechanical Excel comparison as the loop gate. Calls the LLM
    evaluation agent on the first iteration for rich diagnostic feedback.

    Args:
        code: Python source code to execute.
        task: Original user task description.
        expected_file_path: Path to expected output Excel file.
        openai_client: Client for calling OpenAI.
        sandbox_execute: Callable matching execute_code's signature.
        file_id: Optional upload file ID.
        file_context: Pre-built file context string.
        upload_dir: Directory containing uploaded files.
        output_dir: Parent directory for execution temp dirs.
        timeout: Maximum execution time per attempt.
        max_retries: Maximum fix-and-retry cycles.
        quality_threshold: Minimum mechanical score to pass (0.0-1.0).
        settings: Application settings (for eval agent).

    Returns:
        Frozen EvalDebugResult with final code, score, and attempt history.
    """
    logger.info(
        "Eval debug loop started",
        extra={"max_retries": max_retries, "threshold": quality_threshold},
    )

    # Parse expected file structure once
    try:
        expected_sheets = parse_file(expected_file_path)
        expected_context = build_file_context(expected_sheets) or "(empty)"
    except Exception:
        logger.warning("Failed to parse expected file", exc_info=True)
        expected_context = "(parse error)"

    current_code = code
    attempts: list[EvalDebugAttempt] = []
    eval_reasoning = "(not yet evaluated)"
    best_score = 0.0

    async def _execute(exec_code: str) -> ExecutionResult:
        return await asyncio.to_thread(
            sandbox_execute,
            exec_code,
            file_id=file_id,
            upload_dir=upload_dir,
            output_dir=output_dir,
            timeout=timeout,
        )

    # Initial execution
    exec_result = await _execute(current_code)

    if not exec_result.success:
        logger.info("Eval debug loop: initial execution failed (crash)")
        return EvalDebugResult(
            final_code=current_code,
            final_score=0.0,
            success=False,
            attempts=[],
            total_retries=0,
        )

    # Find output file
    actual_path = find_best_output_match(exec_result.output_files, expected_file_path)
    if not actual_path:
        logger.info("Eval debug loop: no output file found")
        return EvalDebugResult(
            final_code=current_code,
            final_score=0.0,
            success=False,
            attempts=[],
            total_retries=0,
        )

    # Initial mechanical comparison
    comparison = compare_excel_files(actual_path, expected_file_path)
    best_score = comparison.overall_score

    if comparison.overall_score >= quality_threshold:
        logger.info(
            "Eval debug loop: initial quality sufficient",
            extra={"score": comparison.overall_score},
        )
        return EvalDebugResult(
            final_code=current_code,
            final_score=comparison.overall_score,
            success=True,
            attempts=[],
            total_retries=0,
        )

    # First iteration: get LLM evaluation for rich feedback
    if settings is not None:
        try:
            from services.eval_agent import evaluate_output

            eval_result = await asyncio.to_thread(
                evaluate_output,
                task=task,
                actual_path=actual_path,
                expected_path=expected_file_path,
                settings=settings,
            )
            if eval_result is not None:
                eval_reasoning = (
                    f"semantic_correctness: {eval_result.semantic_correctness}/10, "
                    f"data_integrity: {eval_result.data_integrity}/10, "
                    f"completeness: {eval_result.completeness}/10\n"
                    f"Reasoning: {eval_result.reasoning}"
                )
        except Exception:
            logger.warning("Eval agent call failed in debug loop", exc_info=True)

    # Retry loop
    for retry_num in range(1, max_retries + 1):
        comparison_summary = _build_comparison_summary(comparison)

        logger.info(
            "Eval debug loop retry",
            extra={
                "retry_num": retry_num,
                "current_score": comparison.overall_score,
                "threshold": quality_threshold,
            },
        )

        # Build prompt and ask LLM for improved code
        prompt = _build_eval_debug_prompt(
            task=task,
            code=current_code,
            expected_context=expected_context,
            comparison_summary=comparison_summary,
            eval_reasoning=eval_reasoning,
            file_context=file_context or "",
        )

        fixed_code = openai_client.generate_code(
            system_prompt=prompt,
            user_prompt="出力品質を改善したコードを生成してください。",
        )

        # Execute fixed code
        exec_result = await _execute(fixed_code)

        if not exec_result.success:
            attempt = EvalDebugAttempt(
                retry_num=retry_num,
                mechanical_score=0.0,
                eval_reasoning=eval_reasoning if retry_num == 1 else None,
                comparison_summary="execution failed",
                fixed_code=fixed_code,
                success=False,
            )
            attempts = [*attempts, attempt]
            current_code = fixed_code
            continue

        # Find output and compare
        actual_path = find_best_output_match(exec_result.output_files, expected_file_path)
        if not actual_path:
            attempt = EvalDebugAttempt(
                retry_num=retry_num,
                mechanical_score=0.0,
                eval_reasoning=eval_reasoning if retry_num == 1 else None,
                comparison_summary="no output file",
                fixed_code=fixed_code,
                success=False,
            )
            attempts = [*attempts, attempt]
            current_code = fixed_code
            continue

        comparison = compare_excel_files(actual_path, expected_file_path)
        current_code = fixed_code
        best_score = max(best_score, comparison.overall_score)

        passed = comparison.overall_score >= quality_threshold
        attempt = EvalDebugAttempt(
            retry_num=retry_num,
            mechanical_score=comparison.overall_score,
            eval_reasoning=eval_reasoning if retry_num == 1 else None,
            comparison_summary=_build_comparison_summary(comparison),
            fixed_code=fixed_code,
            success=passed,
        )
        attempts = [*attempts, attempt]

        if passed:
            logger.info(
                "Eval debug loop: quality improved",
                extra={"retry_num": retry_num, "score": comparison.overall_score},
            )
            return EvalDebugResult(
                final_code=current_code,
                final_score=comparison.overall_score,
                success=True,
                attempts=attempts,
                total_retries=retry_num,
            )

    # All retries exhausted
    logger.warning(
        "Eval debug loop exhausted",
        extra={"max_retries": max_retries, "best_score": best_score},
    )
    return EvalDebugResult(
        final_code=current_code,
        final_score=best_score,
        success=False,
        attempts=attempts,
        total_retries=max_retries,
    )
