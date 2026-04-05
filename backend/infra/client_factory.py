"""LLM client factory — routes model strings to the appropriate backend.

Provider routing by model prefix:
- "claude-sdk/..."  → ClaudeSDKClient (Claude Agent SDK, OAuth token)
- everything else   → LLMClient (LiteLLM, API keys)

Future backends (e.g., OpenAI SDK direct) can be added with new prefixes.
"""

from __future__ import annotations

import logging

from core.config import Settings

logger = logging.getLogger(__name__)


def create_llm_client(settings: Settings):
    """Create the appropriate LLM client based on the active model string.

    Returns an object with chat(), generate_code(), and token tracking attributes.
    """
    model = settings.active_model

    if model.startswith("claude-sdk/"):
        logger.info("Creating ClaudeSDKClient for model: %s", model)
        from infra.claude_sdk_client import ClaudeSDKClient
        return ClaudeSDKClient(settings)

    # Default: LiteLLM (handles OpenAI, Anthropic API, Ollama, Gemini, etc.)
    from infra.llm_client import LLMClient
    return LLMClient(settings)
