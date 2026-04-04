"""Langfuse tracing helpers (v4 API).

Provides a thin wrapper that creates structured traces with nested spans
for each orchestration phase. Safe to call when Langfuse is disabled —
all methods become no-ops.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any

from core.config import Settings

logger = logging.getLogger(__name__)

_langfuse_client = None


def _get_langfuse(settings: Settings):
    """Lazily initialize and cache the Langfuse client."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client
    if not settings.langfuse_enabled:
        return None
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_host,
        )
        logger.info("Langfuse client initialized")
        return _langfuse_client
    except Exception:
        logger.warning("Failed to initialize Langfuse client", exc_info=True)
        return None


class OrchestrationTrace:
    """Wraps a Langfuse trace for one orchestrate() call.

    Uses the v4 start_as_current_observation API.
    If Langfuse is disabled, all methods are safe no-ops.
    """

    def __init__(self, settings: Settings, task: str, metadata: dict[str, Any] | None = None) -> None:
        self._lf = _get_langfuse(settings)
        self._root_ctx = None
        self._root_span = None
        self._current_ctx = None
        self._current_span = None

        if self._lf is not None:
            try:
                self._root_ctx = self._lf.start_as_current_observation(
                    name="orchestrate",
                    as_type="span",
                    input={"task": task},
                    metadata=metadata or {},
                )
                self._root_span = self._root_ctx.__enter__()
                if metadata and metadata.get("run_id"):
                    self._root_span.update_trace(session_id=metadata["run_id"])
            except Exception:
                logger.warning("Failed to create Langfuse trace", exc_info=True)

    def start_phase(self, phase: str) -> None:
        """Begin a new span for a pipeline phase."""
        if self._lf is None or self._root_span is None:
            return
        try:
            phase_names = {
                "A": "Phase A: Exploration",
                "B": "Phase B: Reflection",
                "C": "Phase C: Code Generation",
                "D": "Phase D: Debug Loop",
                "E": "Phase E: Skill Save",
                "U": "Phase U: Understand",
                "G": "Phase G: Generate",
                "VF": "Phase VF: Verify-Fix",
                "L": "Phase L: Learn",
            }
            self._current_ctx = self._lf.start_as_current_observation(
                name=phase_names.get(phase, f"Phase {phase}"),
                as_type="span",
                metadata={"phase": phase},
            )
            self._current_span = self._current_ctx.__enter__()
        except Exception:
            logger.warning("Failed to start Langfuse span", exc_info=True)
            self._current_ctx = None
            self._current_span = None

    def end_phase(self, phase: str, output: Any = None, status: str = "complete") -> None:
        """End the current phase span."""
        if self._current_ctx is None:
            return
        try:
            level = "DEFAULT" if status == "complete" else "ERROR"
            if self._current_span is not None:
                self._current_span.update(
                    output=output if isinstance(output, (str, dict)) else str(output)[:500] if output else None,
                    level=level,
                )
            self._current_ctx.__exit__(None, None, None)
        except Exception:
            logger.warning("Failed to end Langfuse span", exc_info=True)
        self._current_ctx = None
        self._current_span = None

    def log_generation(self, phase: str, model: str, input_text: str, output_text: str, usage: dict | None = None) -> None:
        """Log an LLM generation within the current span."""
        if self._lf is None:
            return
        try:
            ctx = self._lf.start_as_current_observation(
                name=f"LLM call ({phase})",
                as_type="generation",
                model=model,
                input=input_text[:2000],
            )
            gen = ctx.__enter__()
            update_kwargs: dict[str, Any] = {"output": output_text[:2000]}
            if usage:
                update_kwargs["usage_details"] = usage
            gen.update(**update_kwargs)
            ctx.__exit__(None, None, None)
        except Exception:
            logger.warning("Failed to log Langfuse generation", exc_info=True)

    def score(self, name: str, value: float | str, comment: str | None = None, data_type: str | None = None) -> None:
        """Register a score on the current trace."""
        if self._root_span is None or self._lf is None:
            return
        try:
            kwargs: dict[str, Any] = {
                "name": name,
                "value": value,
            }
            if comment:
                kwargs["comment"] = comment
            if data_type:
                kwargs["data_type"] = data_type
            self._root_span.score(**kwargs)
        except Exception:
            logger.warning("Failed to register Langfuse score", exc_info=True)

    def score_eval_result(
        self,
        success: bool,
        retries: int,
        cost_usd: float,
        duration_ms: int,
        error_category: str,
        total_tokens: int,
    ) -> None:
        """Register all eval metrics as scores on the trace."""
        self.score("success", 1.0 if success else 0.0, data_type="BOOLEAN")
        self.score("retries", float(retries), data_type="NUMERIC")
        self.score("cost_usd", cost_usd, data_type="NUMERIC")
        self.score("duration_ms", float(duration_ms), data_type="NUMERIC")
        self.score("total_tokens", float(total_tokens), data_type="NUMERIC")
        self.score("error_category", error_category, data_type="CATEGORICAL")

    def end_trace(self, output: Any = None) -> None:
        """Finalize the trace."""
        if self._root_ctx is None:
            return
        try:
            if self._root_span is not None:
                self._root_span.update(
                    output=output if isinstance(output, (str, dict)) else str(output)[:500] if output else None,
                )
            self._root_ctx.__exit__(None, None, None)
        except Exception:
            logger.warning("Failed to end Langfuse trace", exc_info=True)

    @property
    def trace_id(self) -> str | None:
        """Return the trace ID, or None if no trace."""
        if self._root_span is None:
            return None
        try:
            return self._root_span.trace_id
        except Exception:
            return None

    def flush(self) -> None:
        """Flush pending events to Langfuse."""
        if self._lf is not None:
            try:
                self._lf.flush()
            except Exception:
                pass
