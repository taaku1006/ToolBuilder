"""Tests for OpenAIClient per-call parameter overrides — RED phase."""

from unittest.mock import MagicMock, patch

import pytest


class TestOpenAIClientOverrides:
    def _make_client(self):
        from core.config import Settings

        settings = Settings(
            openai_api_key="sk-test-fake",
            openai_model="gpt-4o",
            langfuse_enabled=False,
        )
        with patch("infra.openai_client.OpenAI") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            # Mock response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "test response"
            mock_response.usage = MagicMock(
                total_tokens=100, prompt_tokens=60, completion_tokens=40
            )
            mock_instance.chat.completions.create.return_value = mock_response

            from infra.openai_client import OpenAIClient
            client = OpenAIClient(settings)
            return client, mock_instance

    def test_chat_default_params(self):
        """Without overrides, uses default model and temperature."""
        client, mock = self._make_client()
        client.chat([{"role": "user", "content": "hi"}])

        call_kwargs = mock.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o"
        assert call_kwargs.kwargs["temperature"] == 0.2

    def test_chat_model_override(self):
        """model kwarg should override the default."""
        client, mock = self._make_client()
        client.chat([{"role": "user", "content": "hi"}], model="gpt-4o-mini")

        call_kwargs = mock.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o-mini"

    def test_chat_temperature_override(self):
        client, mock = self._make_client()
        client.chat([{"role": "user", "content": "hi"}], temperature=0.8)

        call_kwargs = mock.chat.completions.create.call_args
        assert call_kwargs.kwargs["temperature"] == 0.8

    def test_chat_max_tokens_override(self):
        client, mock = self._make_client()
        client.chat([{"role": "user", "content": "hi"}], max_tokens=2000)

        call_kwargs = mock.chat.completions.create.call_args
        assert call_kwargs.kwargs["max_tokens"] == 2000

    def test_chat_max_tokens_omitted_by_default(self):
        """max_tokens should NOT be passed when not specified."""
        client, mock = self._make_client()
        client.chat([{"role": "user", "content": "hi"}])

        call_kwargs = mock.chat.completions.create.call_args
        assert "max_tokens" not in call_kwargs.kwargs

    def test_generate_code_model_override(self):
        client, mock = self._make_client()
        client.generate_code("system", "user", model="gpt-4o-mini")

        call_kwargs = mock.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o-mini"

    def test_generate_code_temperature_override(self):
        client, mock = self._make_client()
        client.generate_code("system", "user", temperature=0.5)

        call_kwargs = mock.chat.completions.create.call_args
        assert call_kwargs.kwargs["temperature"] == 0.5

    def test_token_tracking_preserved(self):
        """Token tracking should work regardless of overrides."""
        client, mock = self._make_client()
        client.chat([{"role": "user", "content": "hi"}], model="gpt-4o-mini")
        assert client.total_tokens == 100
        assert client.api_calls == 1
