import logging
import os
import re
import time

from openai import OpenAI

from core.config import Settings

logger = logging.getLogger(__name__)

# Regex to strip markdown code fences (```json, ```python, ``` etc.)
_CODE_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)


def _strip_code_fence(text: str) -> str:
    """Remove markdown code fences wrapping a JSON response."""
    stripped = text.strip()
    m = _CODE_FENCE_RE.match(stripped)
    return m.group(1).strip() if m else stripped


def _init_langfuse_env(settings: Settings) -> None:
    """Set Langfuse env vars so the SDK picks them up."""
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)


class OpenAIClient:
    def __init__(self, settings: Settings) -> None:
        self._langfuse_enabled = settings.langfuse_enabled
        if self._langfuse_enabled:
            try:
                _init_langfuse_env(settings)
                from langfuse.openai import OpenAI as LangfuseOpenAI

                self._client = LangfuseOpenAI(api_key=settings.openai_api_key)
                logger.info("OpenAI client created with Langfuse tracing enabled")
            except ImportError:
                logger.warning("langfuse not installed, falling back to standard OpenAI client")
                self._client = OpenAI(api_key=settings.openai_api_key)
                self._langfuse_enabled = False
        else:
            self._client = OpenAI(api_key=settings.openai_api_key)

        self._model = settings.openai_model
        self.total_tokens: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.api_calls: int = 0

    def generate_code(self, system_prompt: str, user_prompt: str) -> str:
        logger.info(
            "OpenAI API call started",
            extra={"model": self._model},
        )
        start = time.monotonic()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            )
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "OpenAI API call failed",
                extra={"model": self._model, "duration_ms": duration_ms},
            )
            raise

        duration_ms = int((time.monotonic() - start) * 1000)
        usage = response.usage
        extra: dict[str, object] = {
            "model": self._model,
            "duration_ms": duration_ms,
        }
        self.api_calls += 1
        if usage is not None:
            extra["prompt_tokens"] = usage.prompt_tokens
            extra["completion_tokens"] = usage.completion_tokens
            extra["total_tokens"] = usage.total_tokens
            self.total_tokens += usage.total_tokens
            self.prompt_tokens += usage.prompt_tokens
            self.completion_tokens += usage.completion_tokens

        logger.info("OpenAI API call completed", extra=extra)

        raw = response.choices[0].message.content or ""
        return _strip_code_fence(raw)
