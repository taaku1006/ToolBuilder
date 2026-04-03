"""MagenticOne package runner — uses autogen-agentchat directly.

Wraps autogen's MagenticOneGroupChat with:
  - MagenticOneCoderAgent  (Coder)
  - CodeExecutorAgent + LocalCommandLineCodeExecutor  (ComputerTerminal)
No WebSurfer, no FileSurfer.

The autogen package is imported lazily so ToolBuilder remains runnable even
if autogen packages are not installed (the runner will yield an error entry).
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import uuid
from collections.abc import AsyncGenerator, Callable
from pathlib import Path

from core.config import Settings
from pipeline.orchestrator_types import AgentLogEntry, CancelledError, _now_iso

logger = logging.getLogger(__name__)

_PYTHON_FENCE_RE = re.compile(r"```python\s*\n(.*?)\n```", re.DOTALL)


def _extract_python(text: str) -> str | None:
    matches = _PYTHON_FENCE_RE.findall(text)
    return matches[-1].strip() if matches else None


async def run_magentic_one_pkg(
    task: str,
    file_id: str | None,
    settings: Settings,
    expected_file_path: str | None = None,
    cancel_check: Callable | None = None,
    max_turns: int = 20,
    max_stalls: int = 3,
) -> AsyncGenerator[AgentLogEntry, None]:
    """Run MagenticOne via autogen-agentchat package, yielding AgentLogEntry objects.

    Uses:
      autogen_agentchat.teams.MagenticOneGroupChat
      autogen_ext.agents.magentic_one.MagenticOneCoderAgent
      autogen_ext.code_executors.local.LocalCommandLineCodeExecutor

    Final entry: phase="C", action="complete" with JSON payload matching orchestrate().
    """
    try:
        from autogen_agentchat.agents import CodeExecutorAgent
        from autogen_agentchat.base import TaskResult
        from autogen_agentchat.messages import (
            CodeExecutionEvent,
            CodeGenerationEvent,
            SelectSpeakerEvent,
            TextMessage,
        )
        from autogen_agentchat.teams import MagenticOneGroupChat
        from autogen_ext.agents.magentic_one import MagenticOneCoderAgent
        from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
        from autogen_ext.models.openai import OpenAIChatCompletionClient
    except ImportError as exc:
        yield AgentLogEntry(
            phase="M1P", action="error",
            content=f"autogenパッケージが未インストール: {exc}",
            timestamp=_now_iso(),
        )
        return

    # --- Prepare work directory ---
    work_dir = Path(settings.output_dir) / f"m1p_{uuid.uuid4().hex[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)

    input_file_path: str | None = None
    if file_id:
        upload_dir = Path(settings.upload_dir)
        matches = list(upload_dir.glob(f"{file_id}_*"))
        if matches:
            src = matches[0]
            dest = work_dir / src.name
            shutil.copy2(src, dest)
            input_file_path = str(dest)

    # --- Build task string ---
    task_parts = [task]
    if input_file_path:
        task_parts.append(
            f"\nInput file: {input_file_path}\n"
            f"Working directory: {work_dir}\n"
            "Save output files to the working directory."
        )
    full_task = "\n".join(task_parts)

    yield AgentLogEntry(
        phase="M1P", action="start",
        content="MagenticOne Package: 開始",
        timestamp=_now_iso(),
    )

    python_code: str | None = None
    output_files: list[str] = []

    try:
        client = OpenAIChatCompletionClient(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
        )

        async with LocalCommandLineCodeExecutor(work_dir=str(work_dir)) as executor:
            coder = MagenticOneCoderAgent("Coder", model_client=client)
            terminal = CodeExecutorAgent("ComputerTerminal", code_executor=executor)

            team = MagenticOneGroupChat(
                participants=[coder, terminal],
                model_client=client,
                max_turns=max_turns,
                max_stalls=max_stalls,
            )

            async for msg in team.run_stream(task=full_task):
                if cancel_check and cancel_check():
                    raise CancelledError("MagenticOne pkg cancelled")

                if isinstance(msg, TaskResult):
                    break

                source = getattr(msg, "source", "unknown")

                if isinstance(msg, CodeGenerationEvent):
                    code = _extract_python(msg.content)
                    if code:
                        python_code = code
                    yield AgentLogEntry(
                        phase="M1P_Coder", action="code_generation",
                        content=msg.content[:500],
                        timestamp=_now_iso(),
                    )

                elif isinstance(msg, CodeExecutionEvent):
                    yield AgentLogEntry(
                        phase="M1P_Terminal", action="code_execution",
                        content=msg.result.output[:500],
                        timestamp=_now_iso(),
                    )

                elif isinstance(msg, SelectSpeakerEvent):
                    yield AgentLogEntry(
                        phase="M1P_Orchestrator", action="select_speaker",
                        content=str(msg.content),
                        timestamp=_now_iso(),
                    )

                elif isinstance(msg, TextMessage):
                    if source == "Coder":
                        code = _extract_python(msg.content)
                        if code:
                            python_code = code
                    yield AgentLogEntry(
                        phase=f"M1P_{source}", action="message",
                        content=msg.content[:300],
                        timestamp=_now_iso(),
                    )

        await client.close()

    except CancelledError:
        raise
    except Exception as exc:
        logger.exception("MagenticOne pkg runner failed")
        yield AgentLogEntry(
            phase="M1P", action="error",
            content=str(exc)[:400],
            timestamp=_now_iso(),
        )
        python_code = None

    # --- Collect output files from work_dir ---
    if work_dir.exists():
        output_files = [
            str(p) for p in work_dir.glob("**/*")
            if p.is_file()
            and p.suffix.lower() in {".xlsx", ".xls", ".csv"}
            and str(p) != input_file_path
        ]

    payload = json.dumps(
        {
            "python_code": python_code or "",
            "summary": f"MagenticOne Package: {task[:80]}",
            "steps": [],
            "tips": "MagenticOne (autogen-agentchat) アーキテクチャによる生成",
            "debug_retries": 0,
            "eval_debug_retries": 0,
            "eval_final_score": None,
            "llm_eval_retries": 0,
            "llm_eval_final_score": None,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "api_calls": 0,
            "phase_tokens": {},
            "m1_output_files": output_files,
        },
        ensure_ascii=False,
    )
    yield AgentLogEntry(
        phase="C", action="complete",
        content=payload,
        timestamp=_now_iso(),
    )
