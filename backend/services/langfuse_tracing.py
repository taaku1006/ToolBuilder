"""Langfuse tracing helpers.

Provides a thin wrapper that creates structured traces with nested spans
for each orchestration phase. Safe to call when Langfuse is disabled —
all methods become no-ops.
"""

from __future__ import annotations

import logging
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
            host=settings.langfuse_host,
        )
        logger.info("Langfuse client initialized")
        return _langfuse_client
    except Exception:
        logger.warning("Failed to initialize Langfuse client", exc_info=True)
        return None


class OrchestrationTrace:
    """Wraps a Langfuse trace for one orchestrate() call.

    If Langfuse is disabled, all methods are safe no-ops.
    """

    def __init__(self, settings: Settings, task: str, metadata: dict[str, Any] | None = None) -> None:
        self._lf = _get_langfuse(settings)
        self._trace = None
        self._current_span = None

        if self._lf is not None:
            try:
                self._trace = self._lf.trace(
                    name="orchestrate",
                    input={"task": task},
                    metadata=metadata or {},
                    session_id=metadata.get("run_id") if metadata else None,
                )
            except Exception:
                logger.warning("Failed to create Langfuse trace", exc_info=True)

    def start_phase(self, phase: str) -> None:
        """Begin a new span for a pipeline phase (A, B, C, D, E)."""
        if self._trace is None:
            return
        try:
            phase_names = {
                "A": "Phase A: Exploration",
                "B": "Phase B: Reflection",
                "C": "Phase C: Code Generation",
                "D": "Phase D: Debug Loop",
                "E": "Phase E: Skill Save",
            }
            self._current_span = self._trace.span(
                name=phase_names.get(phase, f"Phase {phase}"),
                metadata={"phase": phase},
            )
        except Exception:
            logger.warning("Failed to start Langfuse span", exc_info=True)
            self._current_span = None

    def end_phase(self, phase: str, output: Any = None, status: str = "complete") -> None:
        """End the current phase span."""
        if self._current_span is None:
            return
        try:
            level = "DEFAULT" if status == "complete" else "ERROR"
            self._current_span.end(
                output=output if isinstance(output, (str, dict)) else str(output)[:500] if output else None,
                level=level,
            )
        except Exception:
            logger.warning("Failed to end Langfuse span", exc_info=True)
        self._current_span = None

    def log_generation(self, phase: str, model: str, input_text: str, output_text: str, usage: dict | None = None) -> None:
        """Log an LLM generation within the current span."""
        parent = self._current_span or self._trace
        if parent is None:
            return
        try:
            parent.generation(
                name=f"LLM call ({phase})",
                model=model,
                input=input_text[:2000],
                output=output_text[:2000],
                usage=usage,
            )
        except Exception:
            logger.warning("Failed to log Langfuse generation", exc_info=True)

    def end_trace(self, output: Any = None) -> None:
        """Finalize the trace."""
        if self._trace is None:
            return
        try:
            self._trace.update(
                output=output if isinstance(output, (str, dict)) else str(output)[:500] if output else None,
            )
        except Exception:
            logger.warning("Failed to end Langfuse trace", exc_info=True)

    def flush(self) -> None:
        """Flush pending events to Langfuse."""
        if self._lf is not None:
            try:
                self._lf.flush()
            except Exception:
                pass
