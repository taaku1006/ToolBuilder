"""Tests for LLMClient (formerly OpenAIClient) per-call parameter overrides."""

from unittest.mock import MagicMock, patch

import pytest


def _mock_response(content: str = "test response") -> MagicMock:
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    mock_response.usage = MagicMock(
        total_tokens=100, prompt_tokens=60, completion_tokens=40
    )
    return mock_response


class TestLLMClientOverrides:
    def test_chat_default_params(self):
        """Without overrides, uses default model and temperature."""
        with patch("infra.llm_client.litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_response()
            from core.config import Settings
            settings = Settings(openai_api_key="sk-test", openai_model="gpt-4o", langfuse_enabled=False)
            from infra.llm_client import LLMClient
            client = LLMClient(settings)
            client.chat([{"role": "user", "content": "hi"}])
            call_kwargs = mock_litellm.completion.call_args.kwargs
            assert call_kwargs["model"] == "gpt-4o"
            assert call_kwargs["temperature"] == 0.2

    def test_chat_model_override(self):
        """model kwarg should override the default."""
        with patch("infra.llm_client.litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_response()
            from core.config import Settings
            settings = Settings(openai_api_key="sk-test", openai_model="gpt-4o", langfuse_enabled=False)
            from infra.llm_client import LLMClient
            client = LLMClient(settings)
            client.chat([{"role": "user", "content": "hi"}], model="gpt-4o-mini")
            call_kwargs = mock_litellm.completion.call_args.kwargs
            assert call_kwargs["model"] == "gpt-4o-mini"

    def test_chat_temperature_override(self):
        with patch("infra.llm_client.litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_response()
            from core.config import Settings
            settings = Settings(openai_api_key="sk-test", openai_model="gpt-4o", langfuse_enabled=False)
            from infra.llm_client import LLMClient
            client = LLMClient(settings)
            client.chat([{"role": "user", "content": "hi"}], temperature=0.8)
            call_kwargs = mock_litellm.completion.call_args.kwargs
            assert call_kwargs["temperature"] == 0.8

    def test_chat_max_tokens_override(self):
        with patch("infra.llm_client.litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_response()
            from core.config import Settings
            settings = Settings(openai_api_key="sk-test", openai_model="gpt-4o", langfuse_enabled=False)
            from infra.llm_client import LLMClient
            client = LLMClient(settings)
            client.chat([{"role": "user", "content": "hi"}], max_tokens=2000)
            call_kwargs = mock_litellm.completion.call_args.kwargs
            assert call_kwargs["max_tokens"] == 2000

    def test_chat_max_tokens_omitted_by_default(self):
        """max_tokens should NOT be passed when not specified."""
        with patch("infra.llm_client.litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_response()
            from core.config import Settings
            settings = Settings(openai_api_key="sk-test", openai_model="gpt-4o", langfuse_enabled=False)
            from infra.llm_client import LLMClient
            client = LLMClient(settings)
            client.chat([{"role": "user", "content": "hi"}])
            call_kwargs = mock_litellm.completion.call_args.kwargs
            assert "max_tokens" not in call_kwargs

    def test_generate_code_model_override(self):
        with patch("infra.llm_client.litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_response()
            from core.config import Settings
            settings = Settings(openai_api_key="sk-test", openai_model="gpt-4o", langfuse_enabled=False)
            from infra.llm_client import LLMClient
            client = LLMClient(settings)
            client.generate_code("system", "user", model="gpt-4o-mini")
            call_kwargs = mock_litellm.completion.call_args.kwargs
            assert call_kwargs["model"] == "gpt-4o-mini"

    def test_generate_code_temperature_override(self):
        with patch("infra.llm_client.litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_response()
            from core.config import Settings
            settings = Settings(openai_api_key="sk-test", openai_model="gpt-4o", langfuse_enabled=False)
            from infra.llm_client import LLMClient
            client = LLMClient(settings)
            client.generate_code("system", "user", temperature=0.5)
            call_kwargs = mock_litellm.completion.call_args.kwargs
            assert call_kwargs["temperature"] == 0.5

    def test_token_tracking_preserved(self):
        """Token tracking should work regardless of overrides."""
        with patch("infra.llm_client.litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_response()
            from core.config import Settings
            settings = Settings(openai_api_key="sk-test", openai_model="gpt-4o", langfuse_enabled=False)
            from infra.llm_client import LLMClient
            client = LLMClient(settings)
            client.chat([{"role": "user", "content": "hi"}], model="gpt-4o-mini")
            assert client.total_tokens == 100
            assert client.api_calls == 1

    def test_ollama_model_passes_api_base(self):
        """Ollama models should include api_base in the call kwargs."""
        with patch("infra.llm_client.litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_response()
            from core.config import Settings
            settings = Settings(
                openai_api_key="ollama",
                llm_model="ollama/gemma4:e4b",
                llm_base_url="http://localhost:11434",
                langfuse_enabled=False,
            )
            from infra.llm_client import LLMClient
            client = LLMClient(settings)
            client.chat([{"role": "user", "content": "hi"}])
            call_kwargs = mock_litellm.completion.call_args.kwargs
            assert call_kwargs["model"] == "ollama/gemma4:e4b"
            assert call_kwargs["api_base"] == "http://localhost:11434"
