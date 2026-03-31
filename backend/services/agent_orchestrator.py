"""Phase A-E orchestrator.

Orchestrates Phase A→B→C sequentially, yielding AgentLogEntry objects.
Each entry carries a phase label, action type, content, and ISO timestamp.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.config import Settings

logger = logging.getLogger(__name__)
from services.openai_client import OpenAIClient
from services.sandbox import execute_code
from services.reflection_engine import run_phase_a, run_phase_b, run_phase_c
from services.debug_loop import run_debug_loop
from services.eval_debug_loop import run_eval_debug_loop
from services.llm_eval_debug_loop import run_llm_eval_debug_loop
from services.task_planner import run_planner, run_replanner
from services.xlsx_parser import SheetInfo, build_file_context, parse_file
from services.langfuse_tracing import OrchestrationTrace


# ---------------------------------------------------------------------------
# AgentLogEntry — immutable event yielded by orchestrate()
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentLogEntry:
    """A single log event emitted during agent orchestration."""

    phase: str       # "A", "B", "C", "D", "E", "result"
    action: str      # "start", "complete", "error"
    content: str     # human-readable detail or JSON payload
    timestamp: str   # ISO 8601 string


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


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


class CancelledError(Exception):
    """Raised when orchestration is cancelled via cancel_check."""


async def orchestrate(
    task: str,
    file_id: str | None,
    settings: Settings,
    expected_file_path: str | None = None,
    cancel_check: callable | None = None,
):
    """Run Phase A→B→C→D (when debug_loop is enabled) sequentially.

    Phase A and B only run when file_id is set and reflection is enabled.
    Phase D (autonomous debug loop) runs after Phase C when debug_loop_enabled.

    Yields AgentLogEntry objects for each phase start/complete event and
    a final entry whose content is JSON with the generated python_code.
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

    # Set settings ref so prompt_manager can access Langfuse config
    from services.reflection_engine import set_settings_ref
    set_settings_ref(settings)

    def _check_cancel() -> None:
        """Raise CancelledError if cancellation was requested."""
        if cancel_check is not None and cancel_check():
            raise CancelledError("Orchestration cancelled")

    openai_client = OpenAIClient(settings)
    file_context = _resolve_file_context(file_id, settings)
    trace = OrchestrationTrace(settings, task, metadata={
        "file_id": file_id,
        "model": settings.openai_model,
        "reflection_enabled": settings.reflection_enabled,
        "debug_loop_enabled": settings.debug_loop_enabled,
    })

    exploration_result = ""
    reflection_result = ""

    # Track per-phase token deltas: snapshot total_tokens before each phase.
    phase_tokens: dict[str, int] = {}

    def _token_snapshot() -> int:
        """Return current cumulative token count (int-safe)."""
        v = openai_client.total_tokens
        return int(v) if isinstance(v, int) else 0

    # ------------------------------------------------------------------
    # Phase A — exploration (only when file is provided AND reflection on)
    # ------------------------------------------------------------------
    _check_cancel()
    if file_id and settings.reflection_enabled:
        trace.start_phase("A")
        yield AgentLogEntry(
            phase="A",
            action="start",
            content="Phase A: Excelファイル構造の探索を開始します",
            timestamp=_now_iso(),
        )

        _tokens_before_a = _token_snapshot()
        phase_a = await run_phase_a(
            openai_client=openai_client,
            sandbox_execute=execute_code,
            file_context=file_context or "",
            file_id=file_id,
            upload_dir=settings.upload_dir,
            output_dir=settings.output_dir,
        )
        phase_tokens["A"] = _token_snapshot() - _tokens_before_a

        exploration_result = phase_a.exploration_output

        trace.end_phase("A", output=exploration_result[:500], status="complete" if phase_a.success else "error")
        yield AgentLogEntry(
            phase="A",
            action="complete" if phase_a.success else "error",
            content=exploration_result,
            timestamp=_now_iso(),
        )

    # ------------------------------------------------------------------
    # Phase B — reflection / tool synthesis (independent from A)
    # ------------------------------------------------------------------
    _check_cancel()
    if file_id and settings.reflection_phase_enabled:
        trace.start_phase("B")
        yield AgentLogEntry(
            phase="B",
            action="start",
            content="Phase B: ツール必要性の内省を開始します",
            timestamp=_now_iso(),
        )

        _tokens_before_b = _token_snapshot()
        phase_b = await run_phase_b(
            openai_client=openai_client,
            sandbox_execute=execute_code,
            exploration_result=exploration_result,
            task=task,
            file_id=file_id,
            upload_dir=settings.upload_dir,
            output_dir=settings.output_dir,
        )
        phase_tokens["B"] = _token_snapshot() - _tokens_before_b

        reflection_result = json.dumps(
            {
                "needs_custom_tool": phase_b.needs_custom_tool,
                "reason": phase_b.reason,
                "tool_output": phase_b.tool_output,
            },
            ensure_ascii=False,
        )

        trace.end_phase("B", output=reflection_result[:500])
        yield AgentLogEntry(
            phase="B",
            action="complete",
            content=reflection_result,
            timestamp=_now_iso(),
        )

    # ------------------------------------------------------------------
    # Phase P — task decomposition (when enabled and file_id present)
    # Orchestrator directly manages [C→D per subtask] loop (SRP)
    # ------------------------------------------------------------------
    _check_cancel()
    decomposition_succeeded = False
    decomp_final_code = ""

    if settings.task_decomposition_enabled and file_id:
        trace.start_phase("P")
        yield AgentLogEntry(
            phase="P", action="start",
            content="Phase P: タスク分解を開始します",
            timestamp=_now_iso(),
        )

        _tokens_before_p = _token_snapshot()
        plan = await run_planner(
            openai_client=openai_client,
            task=task,
            exploration_result=exploration_result,
            reflection_result=reflection_result,
            file_context=file_context,
            max_subtasks=settings.max_subtasks,
        )

        if plan.decompose:
            yield AgentLogEntry(
                phase="P", action="info",
                content=f"タスクを{len(plan.subtasks)}個のサブタスクに分解します: {plan.reasoning}",
                timestamp=_now_iso(),
            )

            # Subtask loop: C→D per subtask
            import shutil
            import uuid as _uuid
            workspace_id = str(_uuid.uuid4())
            workspace_dir = str(Path(settings.output_dir) / f"workspace_{workspace_id}")
            Path(workspace_dir).mkdir(parents=True, exist_ok=True)

            all_code_parts: list[str] = []
            completed_summaries_parts: list[str] = []
            subtask_failed = False

            for subtask in plan.subtasks:
                _check_cancel()
                phase_label = f"C.{subtask.id}"
                yield AgentLogEntry(
                    phase=phase_label, action="start",
                    content=f"サブタスク {subtask.id}: {subtask.title}",
                    timestamp=_now_iso(),
                )

                # List workspace files
                ws_path = Path(workspace_dir)
                available_files = "\n".join(
                    p.name for p in ws_path.iterdir() if p.is_file() and p.name != "script.py"
                ) or "(empty)"
                completed_summaries = "\n".join(completed_summaries_parts) or "(none)"

                # Phase C for subtask (code generation)
                from services.reflection_engine import run_phase_c_subtask
                code = await run_phase_c_subtask(
                    openai_client=openai_client,
                    subtask_title=subtask.title,
                    subtask_description=subtask.description,
                    task=task,
                    exploration_result=exploration_result,
                    file_context=file_context,
                    completed_summaries=completed_summaries,
                    available_files=available_files,
                )

                # Phase D for subtask (debug)
                exec_result = await asyncio.to_thread(
                    execute_code, code,
                    file_id=file_id,
                    upload_dir=settings.upload_dir,
                    output_dir=workspace_dir,
                    timeout=settings.exec_timeout,
                )

                if not exec_result.success:
                    debug_label = f"D.{subtask.id}"
                    yield AgentLogEntry(
                        phase=debug_label, action="start",
                        content=f"サブタスク {subtask.id} デバッグ開始",
                        timestamp=_now_iso(),
                    )
                    debug_result = await run_debug_loop(
                        code=code, task=f"{task}\nサブタスク: {subtask.title}\n{subtask.description}",
                        openai_client=openai_client,
                        sandbox_execute=execute_code,
                        file_id=file_id, file_context=file_context,
                        upload_dir=settings.upload_dir,
                        output_dir=workspace_dir,
                        timeout=settings.exec_timeout,
                        max_retries=settings.subtask_debug_retries,
                    )
                    if debug_result.success:
                        code = debug_result.final_code
                        exec_result = type(exec_result)(
                            stdout=debug_result.final_stdout,
                            stderr=debug_result.final_stderr,
                            elapsed_ms=0, output_files=[], success=True,
                        )
                    yield AgentLogEntry(
                        phase=debug_label,
                        action="complete" if debug_result.success else "error",
                        content=f"デバッグ {'成功' if debug_result.success else '失敗'} (retries: {debug_result.total_retries})",
                        timestamp=_now_iso(),
                    )

                if exec_result.success:
                    all_code_parts.append(f"# === サブタスク {subtask.id}: {subtask.title} ===\n{code}")
                    completed_summaries_parts.append(
                        f"Step {subtask.id} ({subtask.title}): 成功"
                    )
                    # Copy outputs to workspace
                    for fpath in exec_result.output_files:
                        src = Path(fpath)
                        if src.exists():
                            shutil.copy2(src, ws_path / src.name)

                    yield AgentLogEntry(
                        phase=phase_label, action="complete",
                        content=f"サブタスク {subtask.id} 完了",
                        timestamp=_now_iso(),
                    )
                else:
                    subtask_failed = True
                    yield AgentLogEntry(
                        phase=phase_label, action="error",
                        content=f"サブタスク {subtask.id} 失敗",
                        timestamp=_now_iso(),
                    )
                    break

            decomposition_succeeded = not subtask_failed
            decomp_final_code = "\n\n".join(all_code_parts) if all_code_parts else ""
            phase_tokens["P"] = _token_snapshot() - _tokens_before_p
            trace.end_phase("P", output={"decompose": True, "success": decomposition_succeeded})

            yield AgentLogEntry(
                phase="P",
                action="complete" if decomposition_succeeded else "error",
                content=json.dumps({"success": decomposition_succeeded, "final_code": decomp_final_code}, ensure_ascii=False),
                timestamp=_now_iso(),
            )
        else:
            phase_tokens["P"] = _token_snapshot() - _tokens_before_p
            trace.end_phase("P", output={"decompose": False})
            yield AgentLogEntry(
                phase="P", action="complete",
                content=f"単一ステップで実行可能と判断: {plan.reasoning}",
                timestamp=_now_iso(),
            )

    # ------------------------------------------------------------------
    # Phase C — main code generation (skipped if decomposition succeeded)
    _check_cancel()
    # ------------------------------------------------------------------
    trace.start_phase("C")
    yield AgentLogEntry(
        phase="C",
        action="start",
        content="Phase C: メインコードの生成を開始します" if not decomposition_succeeded else "Phase C: タスク分解が成功したためスキップします",
        timestamp=_now_iso(),
    )

    if decomposition_succeeded:
        # Use decomposition's merged code
        _tokens_before_c = _token_snapshot()
        from services.reflection_engine import PhaseCResult
        phase_c = PhaseCResult(
            summary="タスク分解により段階的に生成されたコード",
            python_code=decomp_final_code,
            steps=[f"サブタスク{st.id}: {st.title}" for st in plan.subtasks],
            tips="タスク分解エージェントにより自動生成",
        )
        phase_tokens["C"] = 0
    else:
        _tokens_before_c = _token_snapshot()
        phase_c = await run_phase_c(
            openai_client=openai_client,
            exploration_result=exploration_result,
            reflection_result=reflection_result,
            task=task,
            file_context=file_context,
        )
        phase_tokens["C"] = _token_snapshot() - _tokens_before_c

    # ------------------------------------------------------------------
    # Phase D — autonomous debugging loop
    # ------------------------------------------------------------------
    _check_cancel()
    python_code = phase_c.python_code
    debug_retries = 0

    if settings.debug_loop_enabled:
        trace.start_phase("D")
        yield AgentLogEntry(
            phase="D",
            action="start",
            content="Phase D: 自律デバッグループを開始します",
            timestamp=_now_iso(),
        )

        _tokens_before_d = _token_snapshot()

        # First execution of Phase C code
        first_exec = await asyncio.to_thread(
            execute_code,
            python_code,
            file_id=file_id,
            upload_dir=settings.upload_dir,
            output_dir=settings.output_dir,
            timeout=settings.exec_timeout,
        )

        if first_exec.success:
            phase_tokens["D"] = _token_snapshot() - _tokens_before_d
            trace.end_phase("D", output="初回実行で成功")
            yield AgentLogEntry(
                phase="D",
                action="complete",
                content="初回実行で成功",
                timestamp=_now_iso(),
            )
        else:
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
            )

            for attempt in debug_result.attempts:
                yield AgentLogEntry(
                    phase="D",
                    action="retry",
                    content=f"リトライ {attempt.retry_num}: {attempt.error[:100]}",
                    timestamp=_now_iso(),
                )

            phase_tokens["D"] = _token_snapshot() - _tokens_before_d

            if debug_result.success:
                python_code = debug_result.final_code
                debug_retries = debug_result.total_retries
                trace.end_phase("D", output=f"{debug_result.total_retries}回のリトライで成功")
                yield AgentLogEntry(
                    phase="D",
                    action="complete",
                    content=f"{debug_result.total_retries}回のリトライで成功",
                    timestamp=_now_iso(),
                )
            else:
                debug_retries = debug_result.total_retries
                trace.end_phase("D", output=f"{settings.debug_retry_limit}回リトライ失敗", status="error")
                yield AgentLogEntry(
                    phase="D",
                    action="error",
                    content=f"{settings.debug_retry_limit}回リトライしましたが解決できませんでした",
                    timestamp=_now_iso(),
                )

    # Determine overall execution success for Phase E suggestion
    exec_succeeded = not settings.debug_loop_enabled or (
        settings.debug_loop_enabled and debug_retries < settings.debug_retry_limit
    )

    # ------------------------------------------------------------------
    # Phase F — evaluation-driven quality debug loop (optional)
    # ------------------------------------------------------------------
    _check_cancel()
    eval_debug_retries = 0
    eval_final_score: float | None = None

    if (
        settings.eval_debug_loop_enabled
        and expected_file_path
        and Path(expected_file_path).exists()
        and exec_succeeded
    ):
        trace.start_phase("F")
        yield AgentLogEntry(
            phase="F",
            action="start",
            content="Phase F: 評価駆動デバッグループを開始します",
            timestamp=_now_iso(),
        )

        _tokens_before_f = _token_snapshot()

        eval_debug_result = await run_eval_debug_loop(
            code=python_code,
            task=task,
            expected_file_path=expected_file_path,
            openai_client=openai_client,
            sandbox_execute=execute_code,
            file_id=file_id,
            file_context=file_context,
            upload_dir=settings.upload_dir,
            output_dir=settings.output_dir,
            timeout=settings.exec_timeout,
            max_retries=settings.eval_debug_retry_limit,
            quality_threshold=settings.eval_debug_quality_threshold,
            settings=settings,
        )

        for attempt in eval_debug_result.attempts:
            yield AgentLogEntry(
                phase="F",
                action="retry",
                content=f"リトライ {attempt.retry_num}: score={attempt.mechanical_score:.2%} {attempt.comparison_summary[:100]}",
                timestamp=_now_iso(),
            )

        phase_tokens["F"] = _token_snapshot() - _tokens_before_f
        eval_debug_retries = eval_debug_result.total_retries
        eval_final_score = eval_debug_result.final_score

        if eval_debug_result.success:
            python_code = eval_debug_result.final_code
            trace.end_phase("F", output=f"score={eval_debug_result.final_score:.2%} ({eval_debug_result.total_retries}回リトライ)")
            yield AgentLogEntry(
                phase="F",
                action="complete",
                content=f"品質スコア {eval_debug_result.final_score:.2%} で合格 ({eval_debug_result.total_retries}回リトライ)",
                timestamp=_now_iso(),
            )
        else:
            trace.end_phase("F", output=f"score={eval_debug_result.final_score:.2%} 閾値未達", status="error")
            yield AgentLogEntry(
                phase="F",
                action="error",
                content=f"品質スコア {eval_debug_result.final_score:.2%} (閾値: {settings.eval_debug_quality_threshold:.0%}) - 改善できませんでした",
                timestamp=_now_iso(),
            )

    # ------------------------------------------------------------------
    # Phase G — LLM evaluation-driven debug loop (optional)
    # ------------------------------------------------------------------
    _check_cancel()
    llm_eval_retries = 0
    llm_eval_final_score: float | None = None

    if (
        settings.llm_eval_loop_enabled
        and expected_file_path
        and Path(expected_file_path).exists()
        and exec_succeeded
    ):
        trace.start_phase("G")
        yield AgentLogEntry(
            phase="G",
            action="start",
            content="Phase G: LLM評価デバッグループを開始します",
            timestamp=_now_iso(),
        )

        _tokens_before_g = _token_snapshot()

        llm_eval_debug_result = await run_llm_eval_debug_loop(
            code=python_code,
            task=task,
            expected_file_path=expected_file_path,
            openai_client=openai_client,
            sandbox_execute=execute_code,
            file_id=file_id,
            file_context=file_context,
            upload_dir=settings.upload_dir,
            output_dir=settings.output_dir,
            timeout=settings.exec_timeout,
            max_retries=settings.llm_eval_retry_limit,
            score_threshold=settings.llm_eval_score_threshold,
            settings=settings,
        )

        for attempt in llm_eval_debug_result.attempts:
            yield AgentLogEntry(
                phase="G",
                action="retry",
                content=f"リトライ {attempt.retry_num}: score={attempt.llm_score:.1f}/10 {attempt.reasoning[:100]}",
                timestamp=_now_iso(),
            )

        phase_tokens["G"] = _token_snapshot() - _tokens_before_g
        llm_eval_retries = llm_eval_debug_result.total_retries
        llm_eval_final_score = llm_eval_debug_result.final_score

        if llm_eval_debug_result.success:
            python_code = llm_eval_debug_result.final_code
            trace.end_phase("G", output=f"score={llm_eval_debug_result.final_score:.1f}/10 ({llm_eval_debug_result.total_retries}回リトライ)")
            yield AgentLogEntry(
                phase="G",
                action="complete",
                content=f"LLM評価スコア {llm_eval_debug_result.final_score:.1f}/10 で合格 ({llm_eval_debug_result.total_retries}回リトライ)",
                timestamp=_now_iso(),
            )
        else:
            trace.end_phase("G", output=f"score={llm_eval_debug_result.final_score:.1f}/10 閾値未達", status="error")
            yield AgentLogEntry(
                phase="G",
                action="error",
                content=f"LLM評価スコア {llm_eval_debug_result.final_score:.1f}/10 (閾値: {settings.llm_eval_score_threshold:.1f}) - 改善できませんでした",
                timestamp=_now_iso(),
            )

    logger.info(
        "Orchestration completed",
        extra={"debug_retries": debug_retries, "exec_succeeded": exec_succeeded},
    )

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
    yield AgentLogEntry(
        phase="C",
        action="complete",
        content=result_payload,
        timestamp=_now_iso(),
    )

    # ------------------------------------------------------------------
    # Phase E — skill save suggestion
    # ------------------------------------------------------------------
    _check_cancel()
    if settings.skills_enabled:
        trace.start_phase("E")
        yield AgentLogEntry(
            phase="E",
            action="start",
            content="Phase E: スキル保存の提案を確認します",
            timestamp=_now_iso(),
        )

        if exec_succeeded:
            suggestion_payload = json.dumps(
                {
                    "suggest_save": True,
                    "python_code": python_code,
                    "task_summary": phase_c.summary or task,
                    "message": "実行が成功しました。このコードをスキルとして保存することをお勧めします。",
                },
                ensure_ascii=False,
            )
            trace.end_phase("E", output={"suggest_save": True})
            yield AgentLogEntry(
                phase="E",
                action="complete",
                content=suggestion_payload,
                timestamp=_now_iso(),
            )
        else:
            trace.end_phase("E", output={"suggest_save": False})
            yield AgentLogEntry(
                phase="E",
                action="complete",
                content=json.dumps(
                    {"suggest_save": False, "message": "実行が失敗したためスキル保存は提案しません。"},
                    ensure_ascii=False,
                ),
                timestamp=_now_iso(),
            )

    # LLM-as-Judge evaluation (only when Langfuse is enabled and code was generated)
    if settings.langfuse_enabled and exec_succeeded and python_code:
        try:
            from services.llm_judge import evaluate_and_score

            evaluate_and_score(
                task=task,
                code=python_code,
                settings=settings,
                trace=trace,
            )
        except Exception:
            logger.warning("LLM judge evaluation failed", exc_info=True)

    # Register scores on the Langfuse trace
    _total_tokens = int(openai_client.total_tokens) if isinstance(openai_client.total_tokens, int) else 0
    _prompt_tokens = int(openai_client.prompt_tokens) if isinstance(openai_client.prompt_tokens, int) else 0
    _completion_tokens = int(openai_client.completion_tokens) if isinstance(openai_client.completion_tokens, int) else 0
    trace.score_eval_result(
        success=exec_succeeded,
        retries=debug_retries,
        cost_usd=(_prompt_tokens / 1_000_000) * 2.50 + (_completion_tokens / 1_000_000) * 10.00,
        duration_ms=0,  # Not tracked at orchestrate level
        error_category="none" if exec_succeeded else "runtime_error",
        total_tokens=_total_tokens,
    )

    trace.end_trace(output={"success": exec_succeeded, "debug_retries": debug_retries})
    trace.flush()
