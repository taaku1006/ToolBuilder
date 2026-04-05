"""LiteLLM-based multi-provider embedding client.

Automatically selects an embedding model based on available API keys.
Falls back gracefully: if no provider is available, returns None.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Protocol

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    """Protocol for embedding providers (allows mocking in tests)."""

    def embed(self, text: str) -> list[float]: ...


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class LiteLLMEmbedder:
    """Multi-provider embedding via litellm.embedding().

    Provider selection priority:
    1. Manual override via embedding_model parameter
    2. OpenAI (if OPENAI_API_KEY set)
    3. Gemini (if GEMINI_API_KEY set)
    4. Ollama (if OLLAMA_API_BASE set)
    """

    def __init__(self, model: str | None = None) -> None:
        self._model = model or self._auto_select_model()
        if self._model:
            logger.info("Embedder initialized with model: %s", self._model)
        else:
            logger.warning("No embedding model available")

    @property
    def available(self) -> bool:
        return self._model is not None

    def embed(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        if not self._model:
            return []
        import litellm

        kwargs: dict = {"model": self._model, "input": [text]}
        if self._model.startswith("ollama/"):
            kwargs["api_base"] = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")

        response = litellm.embedding(**kwargs)
        return response.data[0]["embedding"]

    @staticmethod
    def _auto_select_model() -> str | None:
        if os.environ.get("OPENAI_API_KEY"):
            return "text-embedding-3-small"
        if os.environ.get("GEMINI_API_KEY"):
            return "gemini/text-embedding-004"
        if os.environ.get("OLLAMA_API_BASE"):
            return "ollama/nomic-embed-text"
        return None


def create_embedder(embedding_model: str = "") -> LiteLLMEmbedder | None:
    """Factory: create an embedder if a provider is available.

    Returns None if no embedding model can be used.
    """
    try:
        embedder = LiteLLMEmbedder(model=embedding_model or None)
        return embedder if embedder.available else None
    except Exception:
        logger.warning("Failed to create embedder", exc_info=True)
        return None
