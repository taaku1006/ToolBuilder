"""Tests for MagenticOne embedded implementation.

TDD: Tests are written first, then implementation is fixed to pass them.
"""

from __future__ import annotations

import asyncio
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Orchestrator construction
# ---------------------------------------------------------------------------


class TestOrchestratorConstruction:
    """MagenticOneOrchestrator should be constructable without errors."""

    def _make_orchestrator(self):
        from pipeline.magentic_one.embedded.agents import (
            CoderAgent,
            ComputerTerminalAgent,
        )
        from pipeline.magentic_one.embedded.orchestrator import (
            MagenticOneOrchestrator,
        )

        mock_client = MagicMock()
        coder = CoderAgent(mock_client)
        terminal = ComputerTerminalAgent(
            file_id=None, upload_dir="/tmp", output_dir="/tmp",
        )
        return MagenticOneOrchestrator(mock_client, coder, terminal)

    def test_construction_does_not_raise(self):
        orch = self._make_orchestrator()
        assert orch is not None

    def test_team_description_contains_both_agents(self):
        orch = self._make_orchestrator()
        assert "Coder" in orch._team_description
        assert "ComputerTerminal" in orch._team_description

    def test_team_description_is_multiline(self):
        orch = self._make_orchestrator()
        lines = orch._team_description.strip().split("\n")
        assert len(lines) == 2


# ---------------------------------------------------------------------------
# ComputerTerminalAgent code extraction
# ---------------------------------------------------------------------------


class TestComputerTerminalCodeExtraction:
    """ComputerTerminalAgent must extract code blocks like autogen's CodeExecutorAgent."""

    def test_extract_all_python_blocks_from_single_message(self):
        from pipeline.magentic_one.embedded.agents import (
            Message,
            extract_code_blocks_from_messages,
        )

        msg = Message(
            source="Coder",
            content=(
                "First install:\n```sh\npip install pandas\n```\n\n"
                "Then run:\n```python\nimport pandas as pd\nprint(pd.__version__)\n```"
            ),
        )
        blocks = extract_code_blocks_from_messages([msg])
        assert len(blocks) == 2
        assert blocks[0] == ("sh", "pip install pandas")
        assert blocks[1] == ("python", "import pandas as pd\nprint(pd.__version__)")

    def test_extract_from_multiple_messages(self):
        from pipeline.magentic_one.embedded.agents import (
            Message,
            extract_code_blocks_from_messages,
        )

        msgs = [
            Message(source="Orchestrator", content="Please run the following"),
            Message(source="Coder", content="```python\nprint('hello')\n```"),
            Message(source="Orchestrator", content="Now execute"),
            Message(source="Coder", content="```python\nprint('world')\n```"),
        ]
        blocks = extract_code_blocks_from_messages(msgs)
        assert len(blocks) == 2
        assert blocks[0] == ("python", "print('hello')")
        assert blocks[1] == ("python", "print('world')")

    def test_ignore_generic_fence_without_language(self):
        from pipeline.magentic_one.embedded.agents import (
            Message,
            extract_code_blocks_from_messages,
        )

        msg = Message(
            source="Coder",
            content="```\nsome text\n```\n\n```json\n{\"key\": 1}\n```",
        )
        blocks = extract_code_blocks_from_messages([msg])
        assert len(blocks) == 0

    @pytest.mark.asyncio
    async def test_execute_runs_each_block_individually(self):
        from pipeline.magentic_one.embedded.agents import (
            ComputerTerminalAgent,
            Message,
        )

        terminal = ComputerTerminalAgent(
            file_id=None, upload_dir="/tmp", output_dir="/tmp",
        )
        msgs = [
            Message(source="Coder", content="```sh\npip install openpyxl\n```"),
            Message(source="Coder", content="```python\nimport openpyxl\nprint('ok')\n```"),
        ]

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = "ok\n"
        mock_result.stderr = ""
        mock_result.output_files = []

        with patch(
            "pipeline.magentic_one.embedded.agents.execute_code_block",
            return_value=mock_result,
        ) as mock_exec:
            output, success = await terminal.execute(msgs)
            assert mock_exec.call_count == 2
            first_call = mock_exec.call_args_list[0]
            assert first_call[1]["language"] == "sh"
            assert "pip install openpyxl" in first_call[0][0]
            second_call = mock_exec.call_args_list[1]
            assert second_call[1]["language"] == "python"
            assert "import openpyxl" in second_call[0][0]
            assert success is True

    @pytest.mark.asyncio
    async def test_execute_stops_on_first_error(self):
        from pipeline.magentic_one.embedded.agents import (
            ComputerTerminalAgent,
            Message,
        )

        terminal = ComputerTerminalAgent(
            file_id=None, upload_dir="/tmp", output_dir="/tmp",
        )
        msgs = [
            Message(source="Coder", content="```sh\nexit 1\n```\n\n```python\nprint('should not run')\n```"),
        ]

        fail_result = MagicMock()
        fail_result.success = False
        fail_result.stdout = ""
        fail_result.stderr = "error"
        fail_result.output_files = []

        with patch(
            "pipeline.magentic_one.embedded.agents.execute_code_block",
            return_value=fail_result,
        ) as mock_exec:
            output, success = await terminal.execute(msgs)
            assert mock_exec.call_count == 1
            assert success is False


# ---------------------------------------------------------------------------
# CoderAgent: autogen-faithful model_context behavior
# ---------------------------------------------------------------------------


class TestCoderAgentModelContext:
    """CoderAgent must mirror autogen's AssistantAgent message handling."""

    def test_receive_accumulates_messages(self):
        from pipeline.magentic_one.embedded.agents import CoderAgent, Message

        mock_client = MagicMock()
        coder = CoderAgent(mock_client)

        coder.receive(Message(source="Orchestrator", content="Hello"))
        coder.receive(Message(source="ComputerTerminal", content="Output: ok"))
        assert len(coder._model_context) == 2

    def test_receive_orchestrator_as_user_role(self):
        """Orchestrator messages should be 'user' role in Coder's context.

        In autogen, Orchestrator's TextMessage → UserMessage via to_model_message().
        Coder is the assistant; everyone else (including Orchestrator) is user.
        """
        from pipeline.magentic_one.embedded.agents import CoderAgent, Message

        mock_client = MagicMock()
        coder = CoderAgent(mock_client)

        coder.receive(Message(source="Orchestrator", content="Do this"))
        assert coder._model_context[0]["role"] == "user"

    def test_receive_terminal_as_user_role(self):
        """Terminal messages should be 'user' role."""
        from pipeline.magentic_one.embedded.agents import CoderAgent, Message

        mock_client = MagicMock()
        coder = CoderAgent(mock_client)

        coder.receive(Message(source="ComputerTerminal", content="output"))
        assert coder._model_context[0]["role"] == "user"

    def test_reset_clears_context(self):
        from pipeline.magentic_one.embedded.agents import CoderAgent, Message

        mock_client = MagicMock()
        coder = CoderAgent(mock_client)
        coder.receive(Message(source="Orchestrator", content="Hello"))
        coder.reset()
        assert len(coder._model_context) == 0

    def test_respond_does_not_duplicate_instruction(self):
        """respond() must NOT add instruction to model_context.

        In autogen, instruction is already in the buffer → added via
        _add_messages_to_context(). respond() should only call LLM and
        add the response. The instruction was already added by receive().
        """
        from pipeline.magentic_one.embedded.agents import CoderAgent, Message

        mock_client = MagicMock()
        mock_client.chat.return_value = "my code"
        coder = CoderAgent(mock_client)

        # Orchestrator broadcasts instruction, then calls respond
        coder.receive(Message(source="Orchestrator", content="Write code"))
        coder.respond()

        # model_context should be: [instruction(user), response(assistant)]
        assert len(coder._model_context) == 2
        assert coder._model_context[0]["role"] == "user"
        assert coder._model_context[0]["content"] == "Write code"
        assert coder._model_context[1]["role"] == "assistant"
        assert coder._model_context[1]["content"] == "my code"

    def test_respond_sends_system_plus_context_to_llm(self):
        """respond() should send system_message + accumulated model_context to LLM."""
        from pipeline.magentic_one.embedded.agents import CoderAgent, Message
        from pipeline.magentic_one.embedded.prompts import CODER_SYSTEM_MESSAGE

        mock_client = MagicMock()
        mock_client.chat.return_value = "result"
        coder = CoderAgent(mock_client)

        coder.receive(Message(source="Orchestrator", content="Task ledger"))
        coder.receive(Message(source="ComputerTerminal", content="Previous output"))
        coder.receive(Message(source="Orchestrator", content="Write code"))
        coder.respond()

        call_args = mock_client.chat.call_args[0][0]
        # system message first
        assert call_args[0]["role"] == "system"
        assert call_args[0]["content"] == CODER_SYSTEM_MESSAGE
        # then accumulated context (all user role, since Coder is the assistant)
        assert call_args[1] == {"role": "user", "content": "Task ledger"}
        assert call_args[2] == {"role": "user", "content": "Previous output"}
        assert call_args[3] == {"role": "user", "content": "Write code"}
        # total: system + 3 context = 4
        assert len(call_args) == 4

    def test_respond_adds_response_to_context(self):
        """After respond(), the coder's own response is in model_context."""
        from pipeline.magentic_one.embedded.agents import CoderAgent

        mock_client = MagicMock()
        mock_client.chat.return_value = "generated code"
        coder = CoderAgent(mock_client)

        coder.respond()
        assert coder._model_context[-1]["role"] == "assistant"
        assert coder._model_context[-1]["content"] == "generated code"


# ---------------------------------------------------------------------------
# Orchestrator: message buffer per agent (mirrors ChatAgentContainer._message_buffer)
# ---------------------------------------------------------------------------


class TestOrchestratorMessageBuffer:
    """Orchestrator must maintain per-agent message buffers like autogen's ChatAgentContainer."""

    def _make_orchestrator(self):
        from pipeline.magentic_one.embedded.agents import (
            CoderAgent,
            ComputerTerminalAgent,
        )
        from pipeline.magentic_one.embedded.orchestrator import (
            MagenticOneOrchestrator,
        )

        mock_client = MagicMock()
        coder = CoderAgent(mock_client)
        terminal = ComputerTerminalAgent(
            file_id=None, upload_dir="/tmp", output_dir="/tmp",
        )
        return MagenticOneOrchestrator(mock_client, coder, terminal)

    def test_has_terminal_buffer(self):
        """Orchestrator should have a _terminal_buffer for Terminal's messages."""
        orch = self._make_orchestrator()
        assert hasattr(orch, "_terminal_buffer")
        assert isinstance(orch._terminal_buffer, list)

    def test_broadcast_adds_to_terminal_buffer(self):
        """_broadcast() should add messages to _terminal_buffer."""
        from pipeline.magentic_one.embedded.agents import Message

        orch = self._make_orchestrator()
        msg = Message(source="Orchestrator", content="instruction")
        orch._broadcast(msg)
        assert len(orch._terminal_buffer) > 0
        assert orch._terminal_buffer[-1].content == "instruction"

    def test_reenter_outer_loop_clears_terminal_buffer(self):
        """_reenter_outer_loop() should clear _terminal_buffer."""
        from pipeline.magentic_one.embedded.agents import Message

        orch = self._make_orchestrator()
        orch._task = "test"
        orch._facts = "facts"
        orch._plan = "plan"
        orch._terminal_buffer.append(Message(source="Coder", content="old code"))
        orch._reenter_outer_loop()
        assert len(orch._terminal_buffer) == 1  # only the new ledger message
