"""Tests for infra/client_factory.py — RED phase."""

from unittest.mock import patch, MagicMock

import pytest


class TestCreateLLMClient:
    def test_litellm_for_openai_model(self):
        """OpenAI model strings should return LLMClient."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", openai_model="gpt-4o", langfuse_enabled=False)
        settings.llm_model = "gpt-4o"

        with patch("infra.llm_client.litellm"):
            from infra.client_factory import create_llm_client
            client = create_llm_client(settings)
            from infra.llm_client import LLMClient
            assert isinstance(client, LLMClient)

    def test_litellm_for_anthropic_api_model(self):
        """anthropic/ prefixed models go through LiteLLM."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "anthropic/claude-sonnet-4-6"

        with patch("infra.llm_client.litellm"):
            from infra.client_factory import create_llm_client
            client = create_llm_client(settings)
            from infra.llm_client import LLMClient
            assert isinstance(client, LLMClient)

    def test_litellm_for_ollama_model(self):
        """ollama/ prefixed models go through LiteLLM."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "ollama/gemma4:e4b"

        with patch("infra.llm_client.litellm"):
            from infra.client_factory import create_llm_client
            client = create_llm_client(settings)
            from infra.llm_client import LLMClient
            assert isinstance(client, LLMClient)

    def test_claude_sdk_for_claude_sdk_prefix(self):
        """claude-sdk/ prefixed models should return ClaudeSDKClient."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", langfuse_enabled=False)
        settings.llm_model = "claude-sdk/claude-sonnet-4-6"

        with patch("infra.claude_sdk_client.ClaudeSDKClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            from infra.client_factory import create_llm_client
            client = create_llm_client(settings)
            assert mock_cls.called

    def test_empty_model_defaults_to_litellm(self):
        """Empty model string should use LiteLLM."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", openai_model="gpt-4o", langfuse_enabled=False)
        settings.llm_model = ""

        with patch("infra.llm_client.litellm"):
            from infra.client_factory import create_llm_client
            client = create_llm_client(settings)
            from infra.llm_client import LLMClient
            assert isinstance(client, LLMClient)


class TestOpenAIClientWrapper:
    def test_openai_client_returns_correct_backend(self):
        """OpenAIClient(settings) should delegate to factory."""
        from core.config import Settings
        settings = Settings(openai_api_key="sk-test", openai_model="gpt-4o", langfuse_enabled=False)

        with patch("infra.llm_client.litellm"):
            from infra.openai_client import OpenAIClient
            client = OpenAIClient(settings)
            # Should have chat() and generate_code() methods
            assert hasattr(client, "chat")
            assert hasattr(client, "generate_code")
            assert hasattr(client, "total_tokens")
