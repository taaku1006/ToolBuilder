"""Tests for token usage tracking through the pipeline.

TDD RED: OpenAIClient accumulates tokens, orchestrate reports them,
eval runner captures them in metrics.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from infra.openai_client import OpenAIClient


# ---------------------------------------------------------------------------
# OpenAIClient token accumulation
# ---------------------------------------------------------------------------


class TestOpenAIClientTokenTracking:
    """OpenAIClient should track cumulative token usage."""

    def test_initial_counters_are_zero(self) -> None:
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.langfuse_enabled = False

        with patch("infra.openai_client.OpenAI"):
            client = OpenAIClient(mock_settings)

        assert client.total_tokens == 0
        assert client.api_calls == 0

    def test_counters_increment_after_call(self) -> None:
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.langfuse_enabled = False

        with patch("infra.openai_client.OpenAI") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            mock_usage = MagicMock()
            mock_usage.prompt_tokens = 100
            mock_usage.completion_tokens = 200
            mock_usage.total_tokens = 300

            mock_choice = MagicMock()
            mock_choice.message.content = '{"key": "value"}'
            mock_instance.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice],
                usage=mock_usage,
            )

            client = OpenAIClient(mock_settings)
            client.generate_code("system", "user")

        assert client.total_tokens == 300
        assert client.api_calls == 1

    def test_counters_accumulate_across_calls(self) -> None:
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.langfuse_enabled = False

        with patch("infra.openai_client.OpenAI") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            def make_response(tokens: int):
                usage = MagicMock()
                usage.prompt_tokens = tokens // 2
                usage.completion_tokens = tokens // 2
                usage.total_tokens = tokens
                choice = MagicMock()
                choice.message.content = "code"
                return MagicMock(choices=[choice], usage=usage)

            mock_instance.chat.completions.create.side_effect = [
                make_response(500),
                make_response(300),
                make_response(200),
            ]

            client = OpenAIClient(mock_settings)
            client.generate_code("s", "u")
            client.generate_code("s", "u")
            client.generate_code("s", "u")

        assert client.total_tokens == 1000
        assert client.api_calls == 3

    def test_none_usage_does_not_increment_tokens(self) -> None:
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.langfuse_enabled = False

        with patch("infra.openai_client.OpenAI") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            mock_choice = MagicMock()
            mock_choice.message.content = "code"
            mock_instance.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice],
                usage=None,
            )

            client = OpenAIClient(mock_settings)
            client.generate_code("s", "u")

        assert client.total_tokens == 0
        assert client.api_calls == 1


# ---------------------------------------------------------------------------
# Orchestrate includes token info in result payload
# ---------------------------------------------------------------------------


class TestOrchestrateTokenReporting:
    """orchestrate() should include total_tokens and api_calls in result."""

    @pytest.mark.asyncio
    async def test_result_payload_includes_tokens(self) -> None:
        from pipeline.agent_orchestrator import orchestrate

        mock_settings = MagicMock()
        mock_settings.reflection_enabled = False
        mock_settings.debug_loop_enabled = False
        mock_settings.skills_enabled = False
        mock_settings.upload_dir = "./uploads"
        mock_settings.output_dir = "./outputs"
        mock_settings.exec_timeout = 30
        mock_settings.debug_retry_limit = 3
        mock_settings.openai_api_key = "test"
        mock_settings.openai_model = "gpt-4o"

        mock_response = json.dumps({
            "summary": "test",
            "python_code": "print(1)",
            "steps": [],
            "tips": "",
        })

        with patch("pipeline.agent_orchestrator.OpenAIClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.generate_code.return_value = mock_response
            mock_client.total_tokens = 1500
            mock_client.api_calls = 3
            mock_client_cls.return_value = mock_client

            entries = []
            async for entry in orchestrate("task", None, mock_settings):
                entries.append(entry)

        # Find the C-complete entry with the result payload
        result_entry = next(
            e for e in entries if e.phase == "C" and e.action == "complete"
        )
        payload = json.loads(result_entry.content)
        assert payload["total_tokens"] == 1500
        assert payload["api_calls"] == 3


# ---------------------------------------------------------------------------
# Eval runner captures tokens in metrics
# ---------------------------------------------------------------------------


class TestEvalRunnerTokenCapture:
    """EvalRunner should populate total_tokens and api_calls in metrics."""

    @pytest.mark.asyncio
    async def test_metrics_include_tokens(self) -> None:
        from eval.models import ArchitectureConfig, TestCase
        from eval.runner import EvalRunner

        arch = ArchitectureConfig(id="v1", phases=["C"])
        case = TestCase(id="c1", task="t", description="d")

        entry = MagicMock()
        entry.phase = "C"
        entry.action = "complete"
        entry.content = json.dumps({
            "python_code": "pass",
            "summary": "s",
            "steps": [],
            "tips": "",
            "debug_retries": 0,
            "total_tokens": 2500,
            "api_calls": 4,
        })
        entry.timestamp = "2026-03-28T00:00:00+00:00"

        async def mock_orchestrate(*args, **kwargs):
            yield entry

        def mock_settings_factory(overrides=None):
            s = MagicMock()
            s.openai_api_key = "test"
            s.openai_model = "gpt-4o"
            s.upload_dir = "./uploads"
            s.output_dir = "./outputs"
            s.exec_timeout = 30
            s.reflection_enabled = False
            s.debug_loop_enabled = False
            s.skills_enabled = False
            s.debug_retry_limit = 3
            return s

        runner = EvalRunner(
            architectures=[arch],
            test_cases=[case],
            settings_factory=mock_settings_factory,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            result = await runner.run_single(arch, case)

        assert result.metrics.total_tokens == 2500
        assert result.metrics.api_calls == 4
