"""Shared types for agent orchestration.

Extracted to avoid circular imports between agent_orchestrator and phase_handlers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class AgentLogEntry:
    """A single log event emitted during agent orchestration."""

    phase: str       # "A", "B", "C", "D", "E", "result"
    action: str      # "start", "complete", "error"
    content: str     # human-readable detail or JSON payload
    timestamp: str   # ISO 8601 string


class CancelledError(Exception):
    """Raised when orchestration is cancelled via cancel_check."""


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()
