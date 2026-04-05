"""Claude Agent SDK-based LLM client.

Uses Claude Code OAuth tokens (subscription-based) instead of API keys.
Same interface as LLMClient for seamless swapping via client_factory.

Model strings: "claude-sdk/claude-sonnet-4-6" → SDK receives "claude-sonnet-4-6"
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time

from core.config import Settings

logger = logging.getLogger(__name__)

# Matches ``` or ```python etc. anywhere in text
_CODE_FENCE_LINE_RE = re.compile(r"^```\w*\s*$", re.MULTILINE)


def _strip_all_code_fences(text: str) -> str:
    """Remove ALL markdown code fences from text, not just outer ones.

    Handles:
    - ```python ... ``` wrapping entire response
    - Multiple ``` blocks scattered through long code
    - Partial fences embedded mid-line (e.g., `data = o```python`)
    """
    # Remove full fence lines (```python, ```)
    result = _CODE_FENCE_LINE_RE.sub("", text)
    # Remove inline fence fragments (e.g., ```python appearing mid-line)
    result = re.sub(r"```\w*", "", result)
    return result.strip()


def _strip_prefix(model: str) -> str:
    """Remove 'claude-sdk/' prefix from model string."""
    if model.startswith("claude-sdk/"):
        return model[len("claude-sdk/"):]
    return model


class ClaudeSDKClient:
    """LLM client using Claude Agent SDK with OAuth token auth.

    Implements the same interface as LLMClient (chat, generate_code, token tracking).
    """

    def __init__(self, settings: Settings) -> None:
        self._model = _strip_prefix(settings.active_model)
        self._oauth_token = (
            getattr(settings, "claude_code_oauth_token", "")
            or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
        )

        # Token tracking (same as LLMClient)
        self.total_tokens: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.api_calls: int = 0
        self.total_cost_usd: float = 0.0

        if self._oauth_token:
            os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = self._oauth_token

        logger.info(
            "ClaudeSDKClient initialized",
            extra={"model": self._model, "has_token": bool(self._oauth_token)},
        )

    def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Multi-turn chat — same signature as LLMClient.chat()."""
        use_model = _strip_prefix(model) if model else self._model

        start = time.monotonic()
        try:
            result = self._call_sdk(
                messages,
                model=use_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "Claude SDK call (chat) failed",
                extra={"model": use_model, "duration_ms": duration_ms},
            )
            raise

        duration_ms = int((time.monotonic() - start) * 1000)
        self.api_calls += 1
        logger.info(
            "Claude SDK call (chat) completed",
            extra={
                "model": use_model,
                "duration_ms": duration_ms,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            },
        )
        return result

    def generate_code(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Code generation — same signature as LLMClient.generate_code()."""
        use_model = _strip_prefix(model) if model else self._model

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        start = time.monotonic()
        try:
            result = self._call_sdk(
                messages,
                model=use_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "Claude SDK call (generate_code) failed",
                extra={"model": use_model, "duration_ms": duration_ms},
            )
            raise

        duration_ms = int((time.monotonic() - start) * 1000)
        self.api_calls += 1
        logger.info(
            "Claude SDK call (generate_code) completed",
            extra={
                "model": use_model,
                "duration_ms": duration_ms,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            },
        )
        return _strip_all_code_fences(result)

    def _call_sdk(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Call Claude Agent SDK and collect response text.

        Always runs in a separate thread with a fresh event loop to avoid
        conflicts with uvicorn's running loop.
        """
        import concurrent.futures

        def _run_in_thread():
            return asyncio.run(
                self._call_sdk_async(
                    messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run_in_thread)
            return future.result(timeout=120)  # 2 min timeout per call

    async def _call_sdk_async(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Async implementation using Claude Agent SDK."""
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient as SDKClient

        # Build prompt from messages
        system_prompt = ""
        user_messages: list[str] = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                user_messages.append(msg["content"])

        prompt = "\n\n".join(user_messages)

        # Build SDK options
        options_kwargs: dict = {
            "model": model,
            "max_turns": 1,
        }
        if system_prompt:
            options_kwargs["system_prompt"] = system_prompt

        client = SDKClient(options=ClaudeAgentOptions(**options_kwargs))

        response_text = ""
        async with client:
            await client.query(prompt)
            async for msg in client.receive_response():
                msg_type = type(msg).__name__
                if msg_type == "AssistantMessage":
                    for content in msg.content:
                        if hasattr(content, "text"):
                            response_text += content.text
                elif msg_type == "ResultMessage":
                    self._track_usage(msg)

        return response_text

    def _track_usage(self, result_msg) -> None:
        """Extract token counts and cost from ResultMessage."""
        usage = getattr(result_msg, "usage", None)
        if usage and isinstance(usage, dict):
            input_t = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
            output_t = usage.get("output_tokens", 0)
            self.prompt_tokens += input_t
            self.completion_tokens += output_t
            self.total_tokens += input_t + output_t

        cost = getattr(result_msg, "total_cost_usd", 0.0)
        if cost:
            self.total_cost_usd += cost
            logger.info(
                "Claude SDK usage tracked",
                extra={
                    "cost_usd": cost,
                    "cumulative_cost_usd": self.total_cost_usd,
                    "total_tokens": self.total_tokens,
                },
            )
