"""Phase G: LLM evaluation-driven debug loop.

Retries code when it runs successfully but the LLM evaluation agent
scores the output below threshold. Uses eval_agent for scoring and
a dedicated prompt for code improvement feedback.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from evaluation.eval_agent import EvalAgentResult, evaluate_output
from evaluation.excel_comparator import find_best_output_match
from infra.openai_client import OpenAIClient
from infra.prompt_loader import load_prompt
from infra.sandbox import ExecutionResult
from evaluation.structured_comparator import compare_excel_structured
from excel.xlsx_parser import build_file_context, parse_file

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Immutable result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LlmEvalDebugAttempt:
    """Record of a single LLM-eval-driven retry attempt."""

    retry_num: int
    llm_score: float
    semantic_correctness: float
    data_integrity: float
    completeness: float
    reasoning: str
    fixed_code: str
    success: bool


@dataclass(frozen=True)
class LlmEvalDebugResult:
    """Final result of the LLM evaluation debug loop."""

    final_code: str
    final_score: float
    success: bool
    attempts: list[LlmEvalDebugAttempt]
    total_retries: int
    final_eval: EvalAgentResult | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_fix_prompt(
    task: str,
    code: str,
    expected_context: str,
    eval_result: EvalAgentResult,
    file_context: str,
    settings=None,
) -> str:
    """Build the code improvement prompt from LLM eval feedback."""
    template = load_prompt("phase_g_llm_eval_debug", settings)
    return (
        template
        .replace("{task}", task)
        .replace("{code}", code)
        .replace("{expected_context}", expected_context)
        .replace("{semantic_correctness}", f"{eval_result.semantic_correctness:.1f}")
        .replace("{data_integrity}", f"{eval_result.data_integrity:.1f}")
        .replace("{completeness}", f"{eval_result.completeness:.1f}")
        .replace("{overall}", f"{eval_result.overall:.1f}")
        .replace("{reasoning}", eval_result.reasoning)
        .replace("{file_context}", file_context)
    )


# ---------------------------------------------------------------------------
# Main LLM evaluation debug loop
# ---------------------------------------------------------------------------


async def run_llm_eval_debug_loop(
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
    max_retries: int = 2,
    score_threshold: float = 7.0,
    settings=None,
    rubric: dict | None = None,
) -> LlmEvalDebugResult:
    """Execute code and retry when LLM evaluation score is below threshold.

    Each iteration:
    1. Execute code in sandbox
    2. Find output file
    3. Call eval_agent to get LLM score (0-10)
    4. If score >= threshold -> success
    5. Build fix prompt with eval reasoning -> LLM generates improved code
    6. Repeat

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
        score_threshold: Minimum LLM eval score to pass (0-10).
        settings: Application settings (for eval agent and Langfuse prompts).

    Returns:
        Frozen LlmEvalDebugResult with final code, score, and attempt history.
    """
    logger.info(
        "LLM eval debug loop started",
        extra={"max_retries": max_retries, "threshold": score_threshold},
    )

    # Parse expected file structure once
    try:
        expected_sheets = parse_file(expected_file_path)
        expected_context = build_file_context(expected_sheets) or "(empty)"
    except Exception:
        logger.warning("Failed to parse expected file for Phase G", exc_info=True)
        expected_context = "(parse error)"

    current_code = code
    attempts: list[LlmEvalDebugAttempt] = []
    best_score = 0.0
    last_eval: EvalAgentResult | None = None

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
        logger.info("LLM eval debug loop: initial execution failed")
        return LlmEvalDebugResult(
            final_code=current_code, final_score=0.0, success=False,
            attempts=[], total_retries=0, final_eval=None,
        )

    actual_path = find_best_output_match(exec_result.output_files, expected_file_path)
    if not actual_path:
        logger.info("LLM eval debug loop: no output file found")
        return LlmEvalDebugResult(
            final_code=current_code, final_score=0.0, success=False,
            attempts=[], total_retries=0, final_eval=None,
        )

    # Initial LLM evaluation
    if settings is None:
        logger.warning("LLM eval debug loop: no settings, cannot call eval agent")
        return LlmEvalDebugResult(
            final_code=current_code, final_score=0.0, success=False,
            attempts=[], total_retries=0, final_eval=None,
        )

    def _structured_report(path: str) -> str | None:
        if not rubric:
            return None
        try:
            sc_report = compare_excel_structured(path, expected_file_path, rubric=rubric)
            return sc_report.summary_text()
        except Exception:
            logger.warning("Structured comparator failed in LLM eval debug loop", exc_info=True)
            return None

    eval_result = await asyncio.to_thread(
        evaluate_output, task=task, actual_path=actual_path,
        expected_path=expected_file_path, settings=settings,
        structured_report=_structured_report(actual_path),
    )

    if eval_result is None:
        logger.warning("LLM eval debug loop: eval agent returned None")
        return LlmEvalDebugResult(
            final_code=current_code, final_score=0.0, success=False,
            attempts=[], total_retries=0, final_eval=None,
        )

    last_eval = eval_result
    best_score = eval_result.overall

    if eval_result.overall >= score_threshold:
        logger.info("LLM eval debug loop: initial score sufficient", extra={"score": eval_result.overall})
        return LlmEvalDebugResult(
            final_code=current_code, final_score=eval_result.overall, success=True,
            attempts=[], total_retries=0, final_eval=eval_result,
        )

    # Retry loop
    for retry_num in range(1, max_retries + 1):
        logger.info(
            "LLM eval debug loop retry",
            extra={"retry_num": retry_num, "current_score": eval_result.overall},
        )

        # Build fix prompt with eval feedback
        prompt = _build_fix_prompt(
            task=task,
            code=current_code,
            expected_context=expected_context,
            eval_result=eval_result,
            file_context=file_context or "",
            settings=settings,
        )

        fixed_code = openai_client.generate_code(
            system_prompt=prompt,
            user_prompt="評価エージェントの指摘を踏まえてコードを改善してください。",
        )

        # Execute fixed code
        exec_result = await _execute(fixed_code)

        if not exec_result.success:
            attempt = LlmEvalDebugAttempt(
                retry_num=retry_num, llm_score=0.0,
                semantic_correctness=0.0, data_integrity=0.0, completeness=0.0,
                reasoning="execution failed", fixed_code=fixed_code, success=False,
            )
            attempts = [*attempts, attempt]
            current_code = fixed_code
            continue

        actual_path = find_best_output_match(exec_result.output_files, expected_file_path)
        if not actual_path:
            attempt = LlmEvalDebugAttempt(
                retry_num=retry_num, llm_score=0.0,
                semantic_correctness=0.0, data_integrity=0.0, completeness=0.0,
                reasoning="no output file", fixed_code=fixed_code, success=False,
            )
            attempts = [*attempts, attempt]
            current_code = fixed_code
            continue

        # Re-evaluate with LLM
        eval_result = await asyncio.to_thread(
            evaluate_output, task=task, actual_path=actual_path,
            expected_path=expected_file_path, settings=settings,
            structured_report=_structured_report(actual_path),
        )

        if eval_result is None:
            attempt = LlmEvalDebugAttempt(
                retry_num=retry_num, llm_score=0.0,
                semantic_correctness=0.0, data_integrity=0.0, completeness=0.0,
                reasoning="eval agent failed", fixed_code=fixed_code, success=False,
            )
            attempts = [*attempts, attempt]
            current_code = fixed_code
            continue

        current_code = fixed_code
        last_eval = eval_result
        best_score = max(best_score, eval_result.overall)
        passed = eval_result.overall >= score_threshold

        attempt = LlmEvalDebugAttempt(
            retry_num=retry_num,
            llm_score=eval_result.overall,
            semantic_correctness=eval_result.semantic_correctness,
            data_integrity=eval_result.data_integrity,
            completeness=eval_result.completeness,
            reasoning=eval_result.reasoning,
            fixed_code=fixed_code,
            success=passed,
        )
        attempts = [*attempts, attempt]

        if passed:
            logger.info("LLM eval debug loop: improved", extra={"retry_num": retry_num, "score": eval_result.overall})
            return LlmEvalDebugResult(
                final_code=current_code, final_score=eval_result.overall, success=True,
                attempts=attempts, total_retries=retry_num, final_eval=eval_result,
            )

    # All retries exhausted
    logger.warning("LLM eval debug loop exhausted", extra={"best_score": best_score})
    return LlmEvalDebugResult(
        final_code=current_code, final_score=best_score, success=False,
        attempts=attempts, total_retries=max_retries, final_eval=last_eval,
    )
