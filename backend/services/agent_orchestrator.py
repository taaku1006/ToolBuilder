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


async def orchestrate(
    task: str,
    file_id: str | None,
    settings: Settings,
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
        # Phase B — reflection / tool synthesis
        # ------------------------------------------------------------------
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
    # Phase C — main code generation
    # ------------------------------------------------------------------
    trace.start_phase("C")
    yield AgentLogEntry(
        phase="C",
        action="start",
        content="Phase C: メインコードの生成を開始します",
        timestamp=_now_iso(),
    )

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

    trace.end_trace(output={"success": exec_succeeded, "debug_retries": debug_retries})
    trace.flush()
