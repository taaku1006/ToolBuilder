"""Phase A-E orchestrator.

Orchestrates Phase A→B→C sequentially, yielding AgentLogEntry objects.
Each entry carries a phase label, action type, content, and ISO timestamp.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.config import Settings
from services.openai_client import OpenAIClient
from services.sandbox import execute_code
from services.reflection_engine import run_phase_a, run_phase_b, run_phase_c
from services.debug_loop import run_debug_loop
from services.xlsx_parser import SheetInfo, build_file_context, parse_file


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
    openai_client = OpenAIClient(settings)
    file_context = _resolve_file_context(file_id, settings)

    exploration_result = ""
    reflection_result = ""

    # ------------------------------------------------------------------
    # Phase A — exploration (only when file is provided AND reflection on)
    # ------------------------------------------------------------------
    if file_id and settings.reflection_enabled:
        yield AgentLogEntry(
            phase="A",
            action="start",
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
        )

        exploration_result = phase_a.exploration_output

        yield AgentLogEntry(
            phase="A",
            action="complete" if phase_a.success else "error",
            content=exploration_result,
            timestamp=_now_iso(),
        )

        # ------------------------------------------------------------------
        # Phase B — reflection / tool synthesis
        # ------------------------------------------------------------------
        yield AgentLogEntry(
            phase="B",
            action="start",
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
        )

        reflection_result = json.dumps(
            {
                "needs_custom_tool": phase_b.needs_custom_tool,
                "reason": phase_b.reason,
                "tool_output": phase_b.tool_output,
            },
            ensure_ascii=False,
        )

        yield AgentLogEntry(
            phase="B",
            action="complete",
            content=reflection_result,
            timestamp=_now_iso(),
        )

    # ------------------------------------------------------------------
    # Phase C — main code generation
    # ------------------------------------------------------------------
    yield AgentLogEntry(
        phase="C",
        action="start",
        content="Phase C: メインコードの生成を開始します",
        timestamp=_now_iso(),
    )

    phase_c = await run_phase_c(
        openai_client=openai_client,
        exploration_result=exploration_result,
        reflection_result=reflection_result,
        task=task,
        file_context=file_context,
    )

    # ------------------------------------------------------------------
    # Phase D — autonomous debugging loop
    # ------------------------------------------------------------------
    python_code = phase_c.python_code
    debug_retries = 0

    if settings.debug_loop_enabled:
        yield AgentLogEntry(
            phase="D",
            action="start",
            content="Phase D: 自律デバッグループを開始します",
            timestamp=_now_iso(),
        )

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

            if debug_result.success:
                python_code = debug_result.final_code
                debug_retries = debug_result.total_retries
                yield AgentLogEntry(
                    phase="D",
                    action="complete",
                    content=f"{debug_result.total_retries}回のリトライで成功",
                    timestamp=_now_iso(),
                )
            else:
                debug_retries = debug_result.total_retries
                yield AgentLogEntry(
                    phase="D",
                    action="error",
                    content=f"{settings.debug_retry_limit}回リトライしましたが解決できませんでした",
                    timestamp=_now_iso(),
                )

    result_payload = json.dumps(
        {
            "python_code": python_code,
            "summary": phase_c.summary,
            "steps": phase_c.steps,
            "tips": phase_c.tips,
            "debug_retries": debug_retries,
        },
        ensure_ascii=False,
    )

    yield AgentLogEntry(
        phase="C",
        action="complete",
        content=result_payload,
        timestamp=_now_iso(),
    )
