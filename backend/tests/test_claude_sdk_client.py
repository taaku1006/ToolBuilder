"""Tests for infra/claude_sdk_client.py."""

from unittest.mock import MagicMock, patch

import pytest


class TestClaudeSDKClient:
    def test_strips_prefix_from_model(self):
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)
        assert client._model == "claude-sonnet-4-6"

    def test_default_token_tracking(self):
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)
        assert client.total_tokens == 0
        assert client.prompt_tokens == 0
        assert client.completion_tokens == 0
        assert client.api_calls == 0
        assert client.total_cost_usd == 0.0

    def test_chat_returns_string(self):
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)

        with patch.object(client, "_call_sdk", return_value="Hello from Claude"):
            result = client.chat([{"role": "user", "content": "hi"}])
            assert result == "Hello from Claude"
            assert client.api_calls == 1

    def test_generate_code_strips_outer_fences(self):
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)

        raw = "```python\nprint('hello')\n```"
        with patch.object(client, "_call_sdk", return_value=raw):
            result = client.generate_code("system", "user")
            assert result == "print('hello')"
            assert "```" not in result

    def test_generate_code_strips_embedded_fences(self):
        """Fences embedded mid-code should be removed."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)

        raw = "```python\nimport os\ndata = process()```python\nprint(data)\n```"
        with patch.object(client, "_call_sdk", return_value=raw):
            result = client.generate_code("system", "user")
            assert "```" not in result
            assert "import os" in result
            assert "print(data)" in result

    def test_generate_code_strips_multiple_fence_blocks(self):
        """Multiple separate code blocks should be merged."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)

        raw = "```python\npart1()\n```\nSome text\n```python\npart2()\n```"
        with patch.object(client, "_call_sdk", return_value=raw):
            result = client.generate_code("system", "user")
            assert "```" not in result
            assert "part1()" in result
            assert "part2()" in result

    def test_model_override_in_chat(self):
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)

        call_args = {}
        def mock_call(messages, *, model, **kwargs):
            call_args["model"] = model
            return "response"

        with patch.object(client, "_call_sdk", side_effect=mock_call):
            client.chat([{"role": "user", "content": "hi"}], model="claude-sdk/claude-haiku-4-5")
            assert call_args["model"] == "claude-haiku-4-5"

    def test_has_same_interface_as_llm_client(self):
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)

        assert callable(getattr(client, "chat", None))
        assert callable(getattr(client, "generate_code", None))
        assert hasattr(client, "total_tokens")
        assert hasattr(client, "prompt_tokens")
        assert hasattr(client, "completion_tokens")
        assert hasattr(client, "api_calls")
        assert hasattr(client, "total_cost_usd")

    def test_track_usage(self):
        """_track_usage should extract tokens and cost from ResultMessage."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)

        mock_result = MagicMock()
        mock_result.usage = {
            "input_tokens": 100,
            "cache_read_input_tokens": 50,
            "cache_creation_input_tokens": 20,
            "output_tokens": 200,
        }
        mock_result.total_cost_usd = 0.005

        client._track_usage(mock_result)

        assert client.prompt_tokens == 170  # 100 + 50 + 20
        assert client.completion_tokens == 200
        assert client.total_tokens == 370
        assert client.total_cost_usd == 0.005
