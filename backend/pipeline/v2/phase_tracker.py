"""Phase regression prevention for the v2 pipeline.

Tracks stage transitions and prevents illegal backward moves,
except for the explicit replan route back to 'generate'.
"""

from __future__ import annotations

from datetime import datetime


class PhaseRegressionError(Exception):
    """Raised when an illegal backward phase transition is attempted."""


class PhaseTracker:
    """Enforces forward-only phase progression with replan exception.

    The 'generate' phase may be revisited from 'verify_fix' (replan route).
    All other backward transitions are forbidden.
    """

    def __init__(self, phase_order: list[str]) -> None:
        self.phase_order = phase_order
        self.current_index: int = -1
        self.transitions: list[tuple[str, datetime]] = []

    def transition(self, new_phase: str) -> None:
        if new_phase not in self.phase_order:
            raise ValueError(f"Unknown phase: {new_phase}")

        new_index = self.phase_order.index(new_phase)

        # Replan: going back to 'generate' is explicitly allowed
        if new_phase == "generate" and new_index < self.current_index:
            self.current_index = new_index
            self.transitions.append((new_phase, datetime.now()))
            return

        # All other backward transitions are forbidden
        if new_index < self.current_index:
            current = self.phase_order[self.current_index]
            raise PhaseRegressionError(
                f"Phase regression: {current} -> {new_phase}"
            )

        self.current_index = new_index
        self.transitions.append((new_phase, datetime.now()))
