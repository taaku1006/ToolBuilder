"""Backward-compatible re-export. Use infra.llm_client directly."""

from infra.llm_client import LLMClient

OpenAIClient = LLMClient

__all__ = ["LLMClient", "OpenAIClient"]
