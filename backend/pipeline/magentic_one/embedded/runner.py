"""Entry point for the MagenticOne embedded architecture.

Wires together:
  CoderAgent + ComputerTerminalAgent + MagenticOneOrchestrator

and yields AgentLogEntry objects (ToolBuilder's unified log format).
"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from collections.abc import AsyncGenerator, Callable
from pathlib import Path

from core.config import Settings
from pipeline.orchestrator_types import AgentLogEntry, CancelledError, _now_iso

from .agents import CoderAgent, ComputerTerminalAgent
from .orchestrator import MagenticOneOrchestrator

logger = logging.getLogger(__name__)


async def run_magentic_one_embedded(
    task: str,
    file_id: str | None,
    settings: Settings,
    expected_file_path: str | None = None,
    cancel_check: Callable | None = None,
    max_turns: int = 20,
    max_stalls: int = 3,
) -> AsyncGenerator[AgentLogEntry, None]:
    """Run the MagenticOne embedded orchestrator.

    Yields AgentLogEntry objects. The final entry has:
      phase="C", action="complete"
    with a JSON payload matching the format produced by orchestrate().
    """
    from infra.openai_client import OpenAIClient

    openai_client = OpenAIClient(settings)

    # Copy uploaded file into sandbox output_dir so ComputerTerminal can access it.
    # Mirrors autogen's approach: place files in work_dir and pass absolute path in task string.
    input_file_path: str | None = None
    if file_id:
        upload_dir = Path(settings.upload_dir)
        matches = list(upload_dir.glob(f"{file_id}_*"))
        if matches:
            src = matches[0]
            input_file_path = str(src.resolve())

    # Build task description with file context (autogen style: absolute path in task string)
    task_with_context = task
    if input_file_path:
        task_with_context = (
            f"{task}\n\n"
            f"Input file: {input_file_path}\n"
            f"Use `os.environ['INPUT_FILE']` to read this file in your Python code.\n"
            f"Save output files to the directory specified by `os.environ['OUTPUT_DIR']`."
        )

    yield AgentLogEntry(
        phase="M1E", action="start",
        content="MagenticOne Embedded: 開始",
        timestamp=_now_iso(),
    )

    # Build agents
    coder = CoderAgent(openai_client)
    terminal = ComputerTerminalAgent(
        file_id=file_id,
        upload_dir=settings.upload_dir,
        output_dir=settings.output_dir,
        timeout=getattr(settings, "exec_timeout", 60),
    )
    orchestrator = MagenticOneOrchestrator(openai_client, coder, terminal)

    try:
        async for event in orchestrator.run(
            task=task_with_context,
            max_turns=max_turns,
            max_stalls=max_stalls,
            cancel_check=cancel_check,
        ):
            yield AgentLogEntry(
                phase=event.phase,
                action=event.action,
                content=event.content,
                timestamp=_now_iso(),
            )

    except CancelledError:
        raise
    except Exception as exc:
        logger.exception("MagenticOne embedded runner failed")
        yield AgentLogEntry(
            phase="M1E", action="error",
            content=str(exc)[:400],
            timestamp=_now_iso(),
        )

    # Final result payload — same format as orchestrate()
    # Extract last code from the thread for the final payload
    from .agents import extract_last_code_from_thread
    final_code = extract_last_code_from_thread(orchestrator.message_thread) or ""

    payload = json.dumps(
        {
            "python_code": final_code,
            "summary": orchestrator.final_answer or f"MagenticOne Embedded: {task[:80]}",
            "steps": [],
            "tips": "MagenticOne embedded アーキテクチャによる生成（autogen移植版）",
            "debug_retries": 0,
            "eval_debug_retries": 0,
            "eval_final_score": None,
            "llm_eval_retries": 0,
            "llm_eval_final_score": None,
            "total_tokens": int(openai_client.total_tokens),
            "prompt_tokens": int(openai_client.prompt_tokens),
            "completion_tokens": int(openai_client.completion_tokens),
            "api_calls": int(openai_client.api_calls),
            "phase_tokens": {},
            "m1_output_files": orchestrator.output_files,
        },
        ensure_ascii=False,
    )
    yield AgentLogEntry(
        phase="C", action="complete",
        content=payload,
        timestamp=_now_iso(),
    )
