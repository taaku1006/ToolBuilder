"""Agent implementations for the MagenticOne embedded orchestrator.

Faithfully mirrors autogen's agent behavior:

  CoderAgent (mirrors AssistantAgent / MagenticOneCoderAgent):
    - Maintains an internal model_context (list of LLM messages) that accumulates
    - receive() adds messages to context (like handle_agent_response → _buffer_message)
    - respond() calls LLM with system_message + accumulated context + instruction
    - respond() adds the instruction and its own response to context (like model_context.add_message)
    - reset() clears context (like on_reset → model_context.clear())

  ComputerTerminalAgent (mirrors CodeExecutorAgent with model_client=None):
    - Receives a message buffer (not full thread)
    - Scans ALL messages in the buffer for code blocks (not just the last one)
    - Extracts only python|sh blocks (not generic fences) — matches autogen's _supported_languages_regex
    - Collects ALL code blocks and executes them sequentially as one script
    - Returns (output_text, success)

Reference:
  autogen_agentchat/agents/_assistant_agent.py
  autogen_agentchat/agents/_code_executor_agent.py
  autogen_agentchat/teams/_group_chat/_chat_agent_container.py
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infra.sandbox import execute_code, execute_code_block

from .prompts import CODER_DESCRIPTION, CODER_SYSTEM_MESSAGE

if TYPE_CHECKING:
    from infra.openai_client import OpenAIClient

# ---------------------------------------------------------------------------
# Message (shared data structure — mirrors autogen TextMessage/BaseChatMessage)
# ---------------------------------------------------------------------------

_ORCHESTRATOR_NAME = "Orchestrator"


@dataclass
class Message:
    """A single entry in the shared group-chat thread."""
    source: str   # e.g. "Orchestrator", "Coder", "ComputerTerminal"
    content: str


# ---------------------------------------------------------------------------
# Code extraction helpers
# ---------------------------------------------------------------------------

# Mirrors CodeExecutorAgent._extract_markdown_code_blocks() with
# DEFAULT_SUPPORTED_LANGUAGES = ["python", "sh"]
# Pattern: ```<language>\n<code>``` where language must be python or sh
_SUPPORTED_LANGUAGES_RE = re.compile(
    r"```(?:\s*(python|sh))\n([\s\S]*?)```", re.IGNORECASE
)


def _extract_code_from_text(text: str) -> str | None:
    """Extract the last executable code block from a string.

    Only python and sh blocks are extracted (matches autogen's supported_languages).
    """
    matches = _SUPPORTED_LANGUAGES_RE.findall(text)
    if matches:
        return matches[-1][1].strip()
    return None


def extract_code_blocks_from_messages(
    messages: list[Message],
    sources: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Extract all code blocks from a list of messages.

    Mirrors CodeExecutorAgent.extract_code_blocks_from_messages():
      - Iterates ALL messages (not just the last)
      - Filters by source if sources is provided
      - Extracts ALL python|sh code blocks from each message
      - Returns list of (language, code) tuples in order

    Args:
        messages: List of Message objects (the buffer).
        sources: Optional list of source names to filter by.
                 None means all sources (default, matches autogen).

    Returns:
        List of (language, code) tuples.
    """
    blocks: list[tuple[str, str]] = []
    for msg in messages:
        if sources is not None and msg.source not in sources:
            continue
        matches = _SUPPORTED_LANGUAGES_RE.findall(msg.content)
        for lang, code in matches:
            blocks.append((lang.lower(), code.strip()))
    return blocks


def extract_last_code_from_thread(thread: list[Message]) -> str | None:
    """Legacy helper: scan thread from end and return the last code block.

    Kept for backward compatibility but NOT used by ComputerTerminalAgent.
    """
    for msg in reversed(thread):
        code = _extract_code_from_text(msg.content)
        if code:
            return code
    return None


# ---------------------------------------------------------------------------
# CoderAgent
# ---------------------------------------------------------------------------

class CoderAgent:
    """Mirrors autogen's MagenticOneCoderAgent (AssistantAgent subclass).

    Key behavior matching autogen's AssistantAgent:
      - Maintains an internal model_context that accumulates across turns
      - receive() adds incoming messages to context (mirrors _buffer_message → on_messages)
      - respond() sends system_messages + model_context to LLM
      - respond() adds its own response to model_context (mirrors model_context.add_message)
      - reset() clears context (mirrors on_reset → model_context.clear())
    """

    name = "Coder"
    description = CODER_DESCRIPTION

    def __init__(self, client: "OpenAIClient") -> None:
        self._client = client
        self._model_context: list[dict] = []

    def receive(self, msg: Message) -> None:
        """Add a message to the accumulated model context.

        Mirrors ChatAgentContainer._buffer_message() → on_messages() →
        _add_messages_to_context() → model_context.add_message().

        In autogen, all incoming messages (including from Orchestrator) become
        UserMessage via to_model_message(). Coder is the assistant; everyone
        else is the user giving instructions or reporting results.
        """
        self._model_context.append({"role": "user", "content": msg.content})

    def reset(self) -> None:
        """Clear accumulated model context.

        Mirrors AssistantAgent.on_reset() → model_context.clear().
        Called by orchestrator in _reenter_outer_loop().
        """
        self._model_context.clear()

    def respond(self) -> str:
        """Generate a response using accumulated context.

        Mirrors AssistantAgent.on_messages_stream():
          1. Build messages = system_messages + model_context
          2. Call LLM
          3. Add LLM response to context (assistant message)
          4. Return response text

        The instruction has ALREADY been added to model_context via receive()
        before this method is called. This avoids the duplication bug where
        the instruction would appear twice in the context.

        Returns:
            The Coder's response text.
        """
        # Step 1: Build messages = system + accumulated context
        messages: list[dict] = [
            {"role": "system", "content": CODER_SYSTEM_MESSAGE},
            *self._model_context,
        ]

        # Step 2: Call LLM
        response = self._client.chat(messages)

        # Step 3: Add own response to context
        self._model_context.append({"role": "assistant", "content": response})

        return response


# ---------------------------------------------------------------------------
# ComputerTerminalAgent
# ---------------------------------------------------------------------------

class ComputerTerminalAgent:
    """Mirrors autogen's CodeExecutorAgent (model_client=None) + LocalCommandLineCodeExecutor.

    Key behavior matching autogen's CodeExecutorAgent:
      - extract_code_blocks_from_messages() scans ALL messages in the buffer
      - Extracts ALL python|sh code blocks (not just the last one)
      - Executes ALL blocks sequentially as a concatenated script
      - No model_client reflection (model_client=None mode)

    Docker compatibility: execute_code uses subprocess, not Docker-in-Docker.
    """

    name = "ComputerTerminal"
    description = (
        "A computer terminal that performs no other action than running "
        "Python scripts (provided to it quoted in ```python code blocks), "
        "or sh shell scripts (provided to it quoted in ```sh code blocks)."
    )

    def __init__(
        self,
        file_id: str | None,
        upload_dir: str,
        output_dir: str,
        timeout: int = 60,
    ) -> None:
        self._file_id = file_id
        self._upload_dir = upload_dir
        self._output_dir = output_dir
        self._timeout = timeout
        self._last_output_files: list[str] = []

    def reset(self) -> None:
        """Reset agent state."""
        self._last_output_files = []

    @property
    def output_files(self) -> list[str]:
        return self._last_output_files

    async def execute(self, messages: list[Message]) -> tuple[str, bool]:
        """Extract all code blocks from messages and execute them individually.

        Mirrors autogen's CodeExecutorAgent + LocalCommandLineCodeExecutor:
          1. extract_code_blocks_from_messages(messages) — collect all blocks
          2. Execute each block individually with its language interpreter
          3. Accumulate stderr + stdout from all blocks
          4. Stop on first error (non-zero exit code)
          5. Return (accumulated_output, success)

        Args:
            messages: The message buffer (from ChatAgentContainer).

        Returns:
            (output_text, success) tuple.
        """
        blocks = extract_code_blocks_from_messages(messages)
        if not blocks:
            return (
                "No code blocks found in the thread. Please provide at least one "
                "markdown-encoded code block to execute (i.e., quoting code in "
                "```python or ```sh code blocks).",
                False,
            )

        logs_all = ""
        all_output_files: list[str] = []
        success = True

        for lang, code in blocks:
            result = await asyncio.to_thread(
                execute_code_block,
                code,
                language=lang,
                file_id=self._file_id,
                upload_dir=self._upload_dir,
                output_dir=self._output_dir,
                timeout=self._timeout,
            )
            logs_all += result.stderr + result.stdout
            all_output_files.extend(result.output_files)

            if not result.success:
                success = False
                break  # Stop on first error (mirrors autogen)

        self._last_output_files = all_output_files

        if not logs_all.strip():
            logs_all = (
                f"The script ran but produced no output to console. "
                f"Success: {success}."
            )

        return logs_all, success
