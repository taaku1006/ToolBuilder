"""Backward-compatible wrapper. Delegates to client_factory for provider routing."""

from infra.client_factory import create_llm_client


class OpenAIClient:
    """Backward-compatible wrapper that delegates to the appropriate LLM backend.

    Usage: client = OpenAIClient(settings)
    The returned object has chat(), generate_code(), and token tracking.
    """

    def __new__(cls, settings):
        return create_llm_client(settings)


__all__ = ["OpenAIClient"]
