"""MagenticOne orchestrator — faithful port of autogen's MagenticOneOrchestrator.

Reference:
  autogen-agentchat/teams/_group_chat/_magentic_one/_magentic_one_orchestrator.py

Architecture:
  Outer loop — Task Ledger (facts + plan)
    ↓ on stall: _update_task_ledger() → re-enter outer loop
  Inner loop — Progress Ledger per round
    → dispatch to CoderAgent or ComputerTerminalAgent
    → stall detection (n_stalls counter)

Key fidelity notes vs the original:
  - Planning conversation (facts→plan) is a separate multi-turn LLM conversation,
    not folded into the execution thread.
  - TASK_LEDGER_FULL_PROMPT is prepended to the execution thread at the start of
    each outer loop iteration (mirrors _reenter_outer_loop()).
  - Progress ledger is appended to the CURRENT execution thread context
    (mirrors _orchestrate_step → _thread_to_context() + append prompt).
  - Orchestrator messages → "assistant" role; agent messages → "user" role
    (mirrors _thread_to_context()).
  - Stall recovery uses separate UPDATE prompts, not the initial creation prompts.
  - Final answer is generated via FINAL_ANSWER_PROMPT appended to thread context.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .agents import CoderAgent, ComputerTerminalAgent, Message
from .prompts import (
    FINAL_ANSWER_PROMPT,
    PROGRESS_LEDGER_PROMPT,
    TASK_LEDGER_FACTS_PROMPT,
    TASK_LEDGER_FACTS_UPDATE_PROMPT,
    TASK_LEDGER_FULL_PROMPT,
    TASK_LEDGER_PLAN_PROMPT,
    TASK_LEDGER_PLAN_UPDATE_PROMPT,
)

if TYPE_CHECKING:
    from infra.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Progress ledger parsing
# ---------------------------------------------------------------------------

_REQUIRED_LEDGER_KEYS = [
    "is_request_satisfied",
    "is_in_loop",
    "is_progress_being_made",
    "next_speaker",
    "instruction_or_question",
]

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def _extract_json(text: str) -> dict | None:
    """Extract the first JSON object from text (handles code fences)."""
    fence_match = _JSON_FENCE_RE.search(text)
    candidate = fence_match.group(1).strip() if fence_match else text.strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # Find first { ... } in raw text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _validate_ledger(data: dict, participant_names: list[str]) -> bool:
    """Validate progress ledger structure (mirrors autogen's validation logic)."""
    for key in _REQUIRED_LEDGER_KEYS:
        if key not in data:
            return False
        val = data[key]
        if not isinstance(val, dict):
            return False
        if "answer" not in val or "reason" not in val:
            return False
    if not data["is_request_satisfied"]["answer"]:
        if data["next_speaker"]["answer"] not in participant_names:
            return False
    return True


# ---------------------------------------------------------------------------
# Orchestrator events
# ---------------------------------------------------------------------------

@dataclass
class OrchestratorEvent:
    """Internal event emitted by the orchestrator, converted to AgentLogEntry by runner."""
    phase: str
    action: str
    content: str


# ---------------------------------------------------------------------------
# MagenticOneOrchestrator
# ---------------------------------------------------------------------------

class MagenticOneOrchestrator:
    """Faithful port of autogen's MagenticOneOrchestrator.

    Uses two agents: CoderAgent and ComputerTerminalAgent.
    Drives a 2-loop structure via an async generator (run()).

    After run() is exhausted, access:
      .final_answer   — the orchestrator's final text response
      .output_files   — list of files produced by ComputerTerminal
    """

    _ORCHESTRATOR_NAME = "Orchestrator"
    _MAX_JSON_RETRIES = 10
    _MAX_OUTER_LOOPS = 5

    def __init__(
        self,
        client: "OpenAIClient",
        coder: CoderAgent,
        terminal: ComputerTerminalAgent,
    ) -> None:
        self._client = client
        self._coder = coder
        self._terminal = terminal

        self._participant_names = [coder.name, terminal.name]
        self._team_description = "\n".join([
            f"{coder.name}: {coder.description}",
            f"{terminal.name}: {terminal.description}",
        ])

        # State
        self._task: str = ""
        self._facts: str = ""
        self._plan: str = ""
        self._n_stalls: int = 0
        self._n_rounds: int = 0
        self._message_thread: list[Message] = []

        # Per-agent message buffer for Terminal (mirrors ChatAgentContainer._message_buffer).
        # Coder uses its own model_context (accumulated via receive()).
        # Terminal has no persistent state, so it gets a buffer that is cleared after each execution.
        self._terminal_buffer: list[Message] = []

        # Results (set after run() completes)
        self.final_answer: str = ""
        self.output_files: list[str] = []

    @property
    def message_thread(self) -> list[Message]:
        """Read-only access to the execution message thread."""
        return self._message_thread

    # ------------------------------------------------------------------
    # Message broadcast (mirrors GroupChatAgentResponse broadcast)
    # ------------------------------------------------------------------

    def _broadcast(self, msg: Message) -> None:
        """Broadcast a message to all agents' buffers.

        Mirrors autogen's publish_message(GroupChatAgentResponse) which
        triggers ChatAgentContainer.handle_agent_response() → _buffer_message()
        on every participant.

        Coder: msg is added to model_context via receive().
        Terminal: msg is added to _terminal_buffer.
        """
        self._coder.receive(msg)
        self._terminal_buffer.append(msg)

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    def _llm(self, messages: list[dict]) -> str:
        return self._client.chat(messages)

    def _thread_to_context(self) -> list[dict]:
        """Convert execution thread to OpenAI messages.

        Mirrors autogen's _thread_to_context():
          orchestrator messages → role="assistant"
          all other messages   → role="user"
        """
        context: list[dict] = []
        for m in self._message_thread:
            if m.source == self._ORCHESTRATOR_NAME:
                context.append({"role": "assistant", "content": m.content})
            else:
                context.append({"role": "user", "content": m.content})
        return context

    # ------------------------------------------------------------------
    # Task Ledger (outer loop)
    # ------------------------------------------------------------------

    def _gather_facts_and_plan(self) -> None:
        """Initial Task Ledger creation.

        Mirrors handle_start():
          1. GATHER FACTS  — via TASK_LEDGER_FACTS_PROMPT (closed-book pre-survey)
          2. CREATE A PLAN — via TASK_LEDGER_PLAN_PROMPT
        Uses a dedicated planning_conversation separate from the execution thread.
        """
        planning: list[dict] = []

        planning.append({"role": "user", "content": TASK_LEDGER_FACTS_PROMPT.format(task=self._task)})
        self._facts = self._llm(planning)
        planning.append({"role": "assistant", "content": self._facts})

        planning.append({"role": "user", "content": TASK_LEDGER_PLAN_PROMPT.format(team=self._team_description)})
        self._plan = self._llm(planning)

    def _update_task_ledger(self) -> None:
        """Update Task Ledger after a stall.

        Mirrors _update_task_ledger():
          - Uses FACTS_UPDATE_PROMPT to revise existing facts based on thread
          - Uses PLAN_UPDATE_PROMPT to devise a new plan
          - Both appended to the CURRENT execution thread context (not planning conv)
        """
        context = self._thread_to_context()

        context.append({"role": "user", "content": TASK_LEDGER_FACTS_UPDATE_PROMPT.format(
            task=self._task, facts=self._facts,
        )})
        self._facts = self._llm(context)
        context.append({"role": "assistant", "content": self._facts})

        context.append({"role": "user", "content": TASK_LEDGER_PLAN_UPDATE_PROMPT.format(
            team=self._team_description,
        )})
        self._plan = self._llm(context)

    def _reenter_outer_loop(self) -> None:
        """Reset agents and prepend full Task Ledger to execution thread.

        Mirrors _reenter_outer_loop():
          1. Send GroupChatReset to all agents → agent.reset() + buffer.clear()
          2. Clear orchestrator's _message_thread
          3. Create ledger message with TASK_LEDGER_FULL_PROMPT
          4. Broadcast ledger to all agents (mirrors GroupChatAgentResponse)
        """
        # Step 1: Reset all agents and buffers
        self._coder.reset()
        self._terminal.reset()
        self._terminal_buffer.clear()
        self._message_thread.clear()
        self._n_stalls = 0

        # Step 3: Create ledger message
        ledger_content = TASK_LEDGER_FULL_PROMPT.format(
            task=self._task,
            team=self._team_description,
            facts=self._facts,
            plan=self._plan,
        )
        ledger_msg = Message(source=self._ORCHESTRATOR_NAME, content=ledger_content)
        self._message_thread.append(ledger_msg)

        # Step 4: Broadcast to all agents
        self._broadcast(ledger_msg)

    # ------------------------------------------------------------------
    # Progress Ledger (inner loop step)
    # ------------------------------------------------------------------

    def _orchestrate_step(self) -> tuple[dict | None, str]:
        """Run one inner-loop step: build progress ledger via LLM.

        Mirrors _orchestrate_step():
          - Appends PROGRESS_LEDGER_PROMPT to current thread context
          - Retries up to _MAX_JSON_RETRIES times on parse failure
        Returns (ledger_dict, error_msg). error_msg is "" on success.
        """
        progress_prompt = PROGRESS_LEDGER_PROMPT.format(
            task=self._task,
            team=self._team_description,
            names=", ".join(self._participant_names),
        )
        context = self._thread_to_context()
        context.append({"role": "user", "content": progress_prompt})

        for _ in range(self._MAX_JSON_RETRIES):
            raw = self._llm(context)
            data = _extract_json(raw)
            if data and _validate_ledger(data, self._participant_names):
                return data, ""

        return None, "Progress Ledger のパースに失敗しました（リトライ上限）"

    def _prepare_final_answer(self) -> str:
        """Generate final answer from the full execution thread.

        Mirrors _prepare_final_answer():
          - Appends FINAL_ANSWER_PROMPT to thread context
        """
        context = self._thread_to_context()
        context.append({"role": "user", "content": FINAL_ANSWER_PROMPT.format(task=self._task)})
        return self._llm(context)

    # ------------------------------------------------------------------
    # Main async generator
    # ------------------------------------------------------------------

    async def run(
        self,
        task: str,
        max_turns: int = 20,
        max_stalls: int = 3,
        cancel_check=None,
    ) -> AsyncGenerator[OrchestratorEvent, None]:
        """Run the 2-loop orchestrator, yielding OrchestratorEvent objects.

        After this generator is exhausted, read .final_answer and .output_files.
        """
        self._task = task
        self._n_rounds = 0

        # ================================================================
        # Initial Task Ledger
        # ================================================================
        yield OrchestratorEvent(
            phase="M1E_Orchestrator", action="task_ledger",
            content="Task Ledger 作成中（事実収集 → 計画）",
        )
        await asyncio.to_thread(self._gather_facts_and_plan)

        yield OrchestratorEvent(
            phase="M1E_Orchestrator", action="plan",
            content=f"計画:\n{self._plan[:400]}",
        )

        # ================================================================
        # Outer loop
        # ================================================================
        task_done = False

        for outer_round in range(self._MAX_OUTER_LOOPS):
            if cancel_check and cancel_check():
                break

            if outer_round > 0:
                yield OrchestratorEvent(
                    phase="M1E_Orchestrator", action="task_ledger_update",
                    content=f"Task Ledger 更新中（外ループ {outer_round + 1}）",
                )
                await asyncio.to_thread(self._update_task_ledger)
                yield OrchestratorEvent(
                    phase="M1E_Orchestrator", action="plan",
                    content=f"更新された計画:\n{self._plan[:400]}",
                )

            # Reset agents, prepend full ledger
            self._reenter_outer_loop()

            # ============================================================
            # Inner loop
            # ============================================================
            for _turn in range(max_turns):
                if cancel_check and cancel_check():
                    break

                # Max turns check (mirrors autogen)
                if self._n_rounds >= max_turns:
                    yield OrchestratorEvent(
                        phase="M1E_Orchestrator", action="max_turns",
                        content="最大ターン数に達しました",
                    )
                    self.final_answer = await asyncio.to_thread(self._prepare_final_answer)
                    task_done = True
                    break

                self._n_rounds += 1

                # Progress Ledger
                ledger, err = await asyncio.to_thread(self._orchestrate_step)
                if ledger is None:
                    yield OrchestratorEvent(
                        phase="M1E_Orchestrator", action="error", content=err,
                    )
                    break

                sat: bool = ledger["is_request_satisfied"]["answer"]
                in_loop: bool = ledger["is_in_loop"]["answer"]
                progress: bool = ledger["is_progress_being_made"]["answer"]
                next_speaker: str = ledger["next_speaker"]["answer"]
                instruction: str = ledger["instruction_or_question"]["answer"]

                yield OrchestratorEvent(
                    phase="M1E_Orchestrator", action="progress_ledger",
                    content=(
                        f"satisfied={sat} in_loop={in_loop} progress={progress} "
                        f"next={next_speaker} | {instruction[:150]}"
                    ),
                )

                # Task complete?
                if sat:
                    yield OrchestratorEvent(
                        phase="M1E_Orchestrator", action="complete",
                        content="タスク完了。最終回答を生成中",
                    )
                    self.final_answer = await asyncio.to_thread(self._prepare_final_answer)
                    task_done = True
                    break

                # Stall detection (mirrors autogen exactly)
                if not progress or in_loop:
                    self._n_stalls += 1
                else:
                    self._n_stalls = max(0, self._n_stalls - 1)

                if self._n_stalls >= max_stalls:
                    yield OrchestratorEvent(
                        phase="M1E_Orchestrator", action="stall",
                        content=f"Stall {self._n_stalls}回 → 外ループで再計画",
                    )
                    break  # exit inner loop → outer loop re-plans

                # Add orchestrator instruction to thread and broadcast to all agents
                instr_msg = Message(source=self._ORCHESTRATOR_NAME, content=instruction)
                self._message_thread.append(instr_msg)
                self._broadcast(instr_msg)

                # Dispatch to next speaker
                if next_speaker == self._coder.name:
                    yield OrchestratorEvent(
                        phase="M1E_Coder", action="start",
                        content=f"指示: {instruction[:200]}",
                    )
                    # Coder's instruction is already in model_context via _broadcast→receive()
                    # respond() calls LLM with system + model_context, then adds response
                    response = await asyncio.to_thread(self._coder.respond)
                    response_msg = Message(source=self._coder.name, content=response)
                    self._message_thread.append(response_msg)
                    # Broadcast coder response to Terminal's buffer
                    # (Coder's own response is already in its model_context via respond())
                    self._terminal_buffer.append(response_msg)
                    yield OrchestratorEvent(
                        phase="M1E_Coder", action="response",
                        content=response[:500],
                    )

                elif next_speaker == self._terminal.name:
                    yield OrchestratorEvent(
                        phase="M1E_Terminal", action="start",
                        content="メッセージバッファからコードを抽出して実行中",
                    )
                    # Pass only the Terminal's buffer (not full thread)
                    # Mirrors: ChatAgentContainer passes _message_buffer to on_messages()
                    output, success = await self._terminal.execute(self._terminal_buffer)
                    # Clear buffer after execution (mirrors handle_request → buffer.clear())
                    self._terminal_buffer.clear()
                    terminal_msg = Message(source=self._terminal.name, content=output)
                    self._message_thread.append(terminal_msg)
                    # Broadcast terminal output to Coder
                    self._broadcast(terminal_msg)
                    yield OrchestratorEvent(
                        phase="M1E_Terminal", action="response",
                        content=f"success={success}\n{output[:400]}",
                    )

            if task_done:
                break

        # Collect output files from ComputerTerminal
        self.output_files = self._terminal.output_files
