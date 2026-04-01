"""Phase A-E orchestrator.

Orchestrates Phase A→B→C sequentially, yielding AgentLogEntry objects.
Each entry carries a phase label, action type, content, and ISO timestamp.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from core.config import Settings

logger = logging.getLogger(__name__)
from infra.openai_client import OpenAIClient
from infra.sandbox import execute_code
from pipeline.reflection_engine import run_phase_c
from pipeline.eval_debug_loop import run_eval_debug_loop
from pipeline.llm_eval_debug_loop import run_llm_eval_debug_loop
from excel.xlsx_parser import SheetInfo, build_file_context, parse_file
from infra.langfuse_tracing import OrchestrationTrace

# Re-export shared types for backward compatibility
from pipeline.orchestrator_types import AgentLogEntry, CancelledError, _now_iso  # noqa: F401

# Phase handler functions
from pipeline.phase_handlers import (
    PhaseAState, PhaseBState, PhaseDState, PhasePState,
    handle_phase_a, handle_phase_b, handle_phase_d,
    handle_phase_e, handle_phase_p,
)


# ---------------------------------------------------------------------------
# File context helper — kept at module level so tests can patch it
# ---------------------------------------------------------------------------


def _resolve_file_context(file_id: str | None, settings: Settings) -> str | None:
    """Look up the uploaded file by file_id and build a context string.

    Returns None when file_id is absent or the file cannot be found.
    """
    if not file_id:
        return None

    upload_dir = Path(settings.upload_dir)
    if not upload_dir.exists():
        return None

    matches = list(upload_dir.glob(f"{file_id}_*"))
    if not matches:
        return None

    dest = matches[0]
    try:
        sheets: list[SheetInfo] = parse_file(str(dest))
        return build_file_context(sheets) or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def orchestrate(
    task: str,
    file_id: str | None,
    settings: Settings,
    expected_file_path: str | None = None,
    cancel_check: callable | None = None,
    rubric: dict | None = None,
):
    """Run Phase A→B→P→C→D→F→G→E sequentially, yielding AgentLogEntry objects.

    Phase A and B only run when file_id is set and reflection is enabled.
    Phase P (decomposition) runs when task_decomposition_enabled and file_id present.
    Phase D (debug loop) runs after Phase C when debug_loop_enabled.
    Phases F and G run when their respective loop settings are enabled.
    """
    logger.info(
        "Orchestration started",
        extra={
            "task_length": len(task),
            "file_id": file_id,
            "reflection_enabled": settings.reflection_enabled,
            "debug_loop_enabled": settings.debug_loop_enabled,
            "skills_enabled": settings.skills_enabled,
        },
    )

    openai_client = OpenAIClient(settings)
    file_context = _resolve_file_context(file_id, settings)
    trace = OrchestrationTrace(settings, task, metadata={
        "file_id": file_id,
        "model": settings.openai_model,
        "reflection_enabled": settings.reflection_enabled,
        "debug_loop_enabled": settings.debug_loop_enabled,
    })

    def _tok() -> int:
        v = openai_client.total_tokens
        return int(v) if isinstance(v, int) else 0

    phase_tokens: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Phase A — exploration
    # ------------------------------------------------------------------
    state_a = PhaseAState()
    tok_before = _tok()
    async for entry in handle_phase_a(openai_client, settings, task, file_id, file_context, cancel_check, trace, state_a):
        yield entry
    if state_a.exploration_result:
        phase_tokens["A"] = _tok() - tok_before

    exploration_result = state_a.exploration_result

    # ------------------------------------------------------------------
    # Phase B — reflection
    # ------------------------------------------------------------------
    state_b = PhaseBState()
    tok_before = _tok()
    async for entry in handle_phase_b(openai_client, settings, task, file_id, file_context, exploration_result, cancel_check, trace, state_b):
        yield entry
    if state_b.reflection_result:
        phase_tokens["B"] = _tok() - tok_before

    reflection_result = state_b.reflection_result

    # ------------------------------------------------------------------
    # Phase P — task decomposition
    # ------------------------------------------------------------------
    state_p = PhasePState()
    tok_before = _tok()
    async for entry in handle_phase_p(openai_client, settings, task, file_id, file_context, exploration_result, reflection_result, cancel_check, trace, state_p):
        yield entry
    if settings.task_decomposition_enabled and file_id:
        phase_tokens["P"] = _tok() - tok_before

    decomposition_succeeded = state_p.decomposition_succeeded
    decomp_final_code = state_p.decomp_final_code
    plan = state_p.plan

    # ------------------------------------------------------------------
    # Phase C — main code generation (skipped if decomposition succeeded)
    # ------------------------------------------------------------------
    if cancel_check and cancel_check():
        raise CancelledError("Orchestration cancelled")

    trace.start_phase("C")
    yield AgentLogEntry(
        phase="C", action="start",
        content="Phase C: メインコードの生成を開始します" if not decomposition_succeeded else "Phase C: タスク分解が成功したためスキップします",
        timestamp=_now_iso(),
    )

    from pipeline.reflection_engine import PhaseCResult
    if decomposition_succeeded and plan is not None:
        phase_c = PhaseCResult(
            summary="タスク分解により段階的に生成されたコード",
            python_code=decomp_final_code,
            steps=[f"サブタスク{st.id}: {st.title}" for st in plan.subtasks],
            tips="タスク分解エージェントにより自動生成",
        )
        phase_tokens["C"] = 0
    else:
        tok_before = _tok()
        phase_c = await run_phase_c(
            openai_client=openai_client,
            exploration_result=exploration_result,
            reflection_result=reflection_result,
            task=task,
            file_context=file_context,
            settings=settings,
        )
        phase_tokens["C"] = _tok() - tok_before

    # ------------------------------------------------------------------
    # Phase D — autonomous debugging loop
    # ------------------------------------------------------------------
    state_d = PhaseDState(python_code=phase_c.python_code)
    tok_before = _tok()
    async for entry in handle_phase_d(openai_client, settings, task, file_id, file_context, phase_c.python_code, cancel_check, trace, state_d):
        yield entry
    if settings.debug_loop_enabled:
        phase_tokens["D"] = _tok() - tok_before

    python_code = state_d.python_code if settings.debug_loop_enabled else phase_c.python_code
    debug_retries = state_d.debug_retries
    exec_succeeded = state_d.exec_succeeded if settings.debug_loop_enabled else True

    # ------------------------------------------------------------------
    # Phase F — evaluation-driven quality debug loop (optional)
    # ------------------------------------------------------------------
    if cancel_check and cancel_check():
        raise CancelledError("Orchestration cancelled")
    eval_debug_retries = 0
    eval_final_score: float | None = None

    if settings.eval_debug_loop_enabled and expected_file_path and Path(expected_file_path).exists() and exec_succeeded:
        trace.start_phase("F")
        yield AgentLogEntry(phase="F", action="start", content="Phase F: 評価駆動デバッグループを開始します", timestamp=_now_iso())
        tok_before = _tok()
        eval_debug_result = await run_eval_debug_loop(
            code=python_code, task=task, expected_file_path=expected_file_path,
            openai_client=openai_client, sandbox_execute=execute_code,
            file_id=file_id, file_context=file_context,
            upload_dir=settings.upload_dir, output_dir=settings.output_dir,
            timeout=settings.exec_timeout, max_retries=settings.eval_debug_retry_limit,
            quality_threshold=settings.eval_debug_quality_threshold, settings=settings,
            rubric=rubric,
        )
        for attempt in eval_debug_result.attempts:
            yield AgentLogEntry(phase="F", action="retry", content=f"リトライ {attempt.retry_num}: score={attempt.mechanical_score:.2%} {attempt.comparison_summary[:100]}", timestamp=_now_iso())
        phase_tokens["F"] = _tok() - tok_before
        eval_debug_retries = eval_debug_result.total_retries
        eval_final_score = eval_debug_result.final_score
        if eval_debug_result.success:
            python_code = eval_debug_result.final_code
            trace.end_phase("F", output=f"score={eval_debug_result.final_score:.2%} ({eval_debug_result.total_retries}回リトライ)")
            yield AgentLogEntry(phase="F", action="complete", content=f"品質スコア {eval_debug_result.final_score:.2%} で合格 ({eval_debug_result.total_retries}回リトライ)", timestamp=_now_iso())
        else:
            trace.end_phase("F", output=f"score={eval_debug_result.final_score:.2%} 閾値未達", status="error")
            yield AgentLogEntry(phase="F", action="error", content=f"品質スコア {eval_debug_result.final_score:.2%} (閾値: {settings.eval_debug_quality_threshold:.0%}) - 改善できませんでした", timestamp=_now_iso())

    # ------------------------------------------------------------------
    # Phase G — LLM evaluation-driven debug loop (optional)
    # ------------------------------------------------------------------
    if cancel_check and cancel_check():
        raise CancelledError("Orchestration cancelled")
    llm_eval_retries = 0
    llm_eval_final_score: float | None = None

    if settings.llm_eval_loop_enabled and expected_file_path and Path(expected_file_path).exists() and exec_succeeded:
        trace.start_phase("G")
        yield AgentLogEntry(phase="G", action="start", content="Phase G: LLM評価デバッグループを開始します", timestamp=_now_iso())
        tok_before = _tok()
        llm_eval_debug_result = await run_llm_eval_debug_loop(
            code=python_code, task=task, expected_file_path=expected_file_path,
            openai_client=openai_client, sandbox_execute=execute_code,
            file_id=file_id, file_context=file_context,
            upload_dir=settings.upload_dir, output_dir=settings.output_dir,
            timeout=settings.exec_timeout, max_retries=settings.llm_eval_retry_limit,
            score_threshold=settings.llm_eval_score_threshold, settings=settings,
            rubric=rubric,
        )
        for attempt in llm_eval_debug_result.attempts:
            yield AgentLogEntry(phase="G", action="retry", content=f"リトライ {attempt.retry_num}: score={attempt.llm_score:.1f}/10 {attempt.reasoning[:100]}", timestamp=_now_iso())
        phase_tokens["G"] = _tok() - tok_before
        llm_eval_retries = llm_eval_debug_result.total_retries
        llm_eval_final_score = llm_eval_debug_result.final_score
        if llm_eval_debug_result.success:
            python_code = llm_eval_debug_result.final_code
            trace.end_phase("G", output=f"score={llm_eval_debug_result.final_score:.1f}/10 ({llm_eval_debug_result.total_retries}回リトライ)")
            yield AgentLogEntry(phase="G", action="complete", content=f"LLM評価スコア {llm_eval_debug_result.final_score:.1f}/10 で合格 ({llm_eval_debug_result.total_retries}回リトライ)", timestamp=_now_iso())
        else:
            trace.end_phase("G", output=f"score={llm_eval_debug_result.final_score:.1f}/10 閾値未達", status="error")
            yield AgentLogEntry(phase="G", action="error", content=f"LLM評価スコア {llm_eval_debug_result.final_score:.1f}/10 (閾値: {settings.llm_eval_score_threshold:.1f}) - 改善できませんでした", timestamp=_now_iso())

    # ------------------------------------------------------------------
    # Result payload (Phase C complete event)
    # ------------------------------------------------------------------
    logger.info("Orchestration completed", extra={"debug_retries": debug_retries, "exec_succeeded": exec_succeeded})

    result_payload = json.dumps(
        {
            "python_code": python_code,
            "summary": phase_c.summary,
            "steps": phase_c.steps,
            "tips": phase_c.tips,
            "debug_retries": debug_retries,
            "eval_debug_retries": eval_debug_retries,
            "eval_final_score": eval_final_score,
            "llm_eval_retries": llm_eval_retries,
            "llm_eval_final_score": llm_eval_final_score,
            "total_tokens": int(openai_client.total_tokens) if isinstance(openai_client.total_tokens, int) else 0,
            "prompt_tokens": int(openai_client.prompt_tokens) if isinstance(openai_client.prompt_tokens, int) else 0,
            "completion_tokens": int(openai_client.completion_tokens) if isinstance(openai_client.completion_tokens, int) else 0,
            "api_calls": int(openai_client.api_calls) if isinstance(openai_client.api_calls, int) else 0,
            "phase_tokens": phase_tokens,
        },
        ensure_ascii=False,
    )
    trace.end_phase("C", output={"summary": phase_c.summary, "code_length": len(python_code)})
    yield AgentLogEntry(phase="C", action="complete", content=result_payload, timestamp=_now_iso())

    # ------------------------------------------------------------------
    # Phase E — skill save suggestion
    # ------------------------------------------------------------------
    async for entry in handle_phase_e(settings, task, python_code, phase_c.summary, exec_succeeded, cancel_check, trace):
        yield entry

    # ------------------------------------------------------------------
    # LLM-as-Judge & Langfuse score
    # ------------------------------------------------------------------
    if settings.langfuse_enabled and exec_succeeded and python_code:
        try:
            from evaluation.llm_judge import evaluate_and_score
            evaluate_and_score(task=task, code=python_code, settings=settings, trace=trace)
        except Exception:
            logger.warning("LLM judge evaluation failed", exc_info=True)

    _prompt_tokens = int(openai_client.prompt_tokens) if isinstance(openai_client.prompt_tokens, int) else 0
    _completion_tokens = int(openai_client.completion_tokens) if isinstance(openai_client.completion_tokens, int) else 0
    trace.score_eval_result(
        success=exec_succeeded,
        retries=debug_retries,
        cost_usd=(_prompt_tokens / 1_000_000) * 2.50 + (_completion_tokens / 1_000_000) * 10.00,
        duration_ms=0,
        error_category="none" if exec_succeeded else "runtime_error",
        total_tokens=int(openai_client.total_tokens) if isinstance(openai_client.total_tokens, int) else 0,
    )
    trace.end_trace(output={"success": exec_succeeded, "debug_retries": debug_retries})
    trace.flush()
