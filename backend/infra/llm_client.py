"""Unified LLM client powered by LiteLLM.

Supports OpenAI, Anthropic, Google Gemini, Ollama and any other provider
that LiteLLM supports — switch models by changing the model string alone.

Examples:
    "gpt-4o"                        → OpenAI
    "anthropic/claude-sonnet-4-6"   → Anthropic
    "gemini/gemini-2.0-flash"       → Google Gemini
    "ollama/gemma4:e4b"             → Ollama (local)
"""

import logging
import os
import re
import time

import litellm

from core.config import Settings

logger = logging.getLogger(__name__)

# Regex to strip markdown code fences (```json, ```python, ``` etc.)
_CODE_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)


def _strip_code_fence(text: str) -> str:
    """Remove markdown code fences wrapping a JSON response."""
    stripped = text.strip()
    m = _CODE_FENCE_RE.match(stripped)
    return m.group(1).strip() if m else stripped


def _configure_env(settings: Settings) -> None:
    """Push provider API keys into env vars so LiteLLM picks them up."""
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    if settings.anthropic_api_key:
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
    if settings.gemini_api_key:
        os.environ.setdefault("GEMINI_API_KEY", settings.gemini_api_key)


def _init_langfuse_env(settings: Settings) -> None:
    """Set Langfuse env vars so the SDK picks them up."""
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)


class LLMClient:
    """Provider-agnostic LLM client.

    Drop-in replacement for the former OpenAIClient.
    Uses litellm.completion() internally so any model string that LiteLLM
    recognises will work.
    """

    def __init__(self, settings: Settings) -> None:
        _configure_env(settings)

        self._langfuse_enabled = settings.langfuse_enabled
        if self._langfuse_enabled:
            try:
                _init_langfuse_env(settings)
                litellm.callbacks = ["langfuse_otel"]
                logger.info("LLM client created with Langfuse tracing enabled")
            except Exception:
                logger.warning("Langfuse callback setup failed, continuing without tracing")
                self._langfuse_enabled = False

        self._model = settings.active_model
        self._base_url = settings.active_base_url or None

        # Suppress litellm's noisy INFO logs unless we're in DEBUG
        litellm.suppress_debug_info = True

        self.total_tokens: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.api_calls: int = 0

    def _call_kwargs(self, model: str) -> dict:
        """Build extra kwargs for a litellm.completion call."""
        kwargs: dict = {}
        if model.startswith("ollama/"):
            # For Ollama: use configured base_url, or fall back to OLLAMA_API_BASE env,
            # or default http://localhost:11434
            kwargs["api_base"] = (
                self._base_url
                or os.environ.get("OLLAMA_API_BASE")
                or "http://localhost:11434"
            )
        elif self._base_url and not any(
            model.startswith(p) for p in ("anthropic/", "gemini/", "vertex_ai/")
        ):
            kwargs["api_base"] = self._base_url
        return kwargs

    def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Multi-turn chat with arbitrary message history.

        Returns:
            The assistant's reply content (raw, no code-fence stripping).
        """
        use_model = model or self._model
        use_temperature = temperature if temperature is not None else 0.2

        start = time.monotonic()
        kwargs: dict = {
            "model": use_model,
            "messages": messages,
            "temperature": use_temperature,
            **self._call_kwargs(use_model),
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        try:
            response = litellm.completion(**kwargs)
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "LLM API call (chat) failed",
                extra={"model": use_model, "duration_ms": duration_ms},
            )
            raise

        duration_ms = int((time.monotonic() - start) * 1000)
        self._track_usage(response, use_model, duration_ms, "chat")
        return response.choices[0].message.content or ""

    def generate_code(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        use_model = model or self._model
        use_temperature = temperature if temperature is not None else 0.2

        logger.info("LLM API call started", extra={"model": use_model})
        start = time.monotonic()
        kwargs: dict = {
            "model": use_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": use_temperature,
            **self._call_kwargs(use_model),
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        try:
            response = litellm.completion(**kwargs)
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "LLM API call failed",
                extra={"model": use_model, "duration_ms": duration_ms},
            )
            raise

        duration_ms = int((time.monotonic() - start) * 1000)
        self._track_usage(response, use_model, duration_ms, "generate_code")

        raw = response.choices[0].message.content or ""
        return _strip_code_fence(raw)

    def _track_usage(self, response, model: str, duration_ms: int, method: str) -> None:
        """Update cumulative token counters from a LiteLLM response."""
        usage = response.usage
        extra: dict[str, object] = {"model": model, "duration_ms": duration_ms}
        self.api_calls += 1
        if usage is not None:
            prompt = usage.prompt_tokens or 0
            completion = usage.completion_tokens or 0
            total = usage.total_tokens or (prompt + completion)
            extra["prompt_tokens"] = prompt
            extra["completion_tokens"] = completion
            extra["total_tokens"] = total
            self.total_tokens += total
            self.prompt_tokens += prompt
            self.completion_tokens += completion

        logger.info("LLM API call (%s) completed", method, extra=extra)


# Backward-compatible alias so existing imports keep working.
OpenAIClient = LLMClient
