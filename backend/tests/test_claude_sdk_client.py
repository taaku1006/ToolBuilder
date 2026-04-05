"""Tests for infra/claude_sdk_client.py — RED phase."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestClaudeSDKClient:
    def test_strips_prefix_from_model(self):
        """claude-sdk/ prefix should be stripped before passing to SDK."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)
        assert client._model == "claude-sonnet-4-6"

    def test_default_token_tracking(self):
        """Token counters should start at zero."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)
        assert client.total_tokens == 0
        assert client.prompt_tokens == 0
        assert client.completion_tokens == 0
        assert client.api_calls == 0

    def test_chat_returns_string(self):
        """chat() should return a string response."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)

        # Mock the internal _call method
        with patch.object(client, "_call_sdk", return_value="Hello from Claude"):
            result = client.chat([{"role": "user", "content": "hi"}])
            assert result == "Hello from Claude"
            assert client.api_calls == 1

    def test_generate_code_strips_fences(self):
        """generate_code() should strip markdown code fences."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        from infra.claude_sdk_client import ClaudeSDKClient
        client = ClaudeSDKClient(settings)

        raw = "```python\nprint('hello')\n```"
        with patch.object(client, "_call_sdk", return_value=raw):
            result = client.generate_code("system", "user")
            assert result == "print('hello')"

    def test_model_override_in_chat(self):
        """model kwarg should override the default."""
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
        """ClaudeSDKClient must have the same public interface as LLMClient."""
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
