"""Tests for pipeline/v2/phase_tracker.py — RED phase."""

import pytest


class TestPhaseTracker:
    def test_normal_forward_transitions(self):
        from pipeline.v2.phase_tracker import PhaseTracker

        tracker = PhaseTracker(["understand", "generate", "verify_fix", "learn"])
        tracker.transition("understand")
        tracker.transition("generate")
        tracker.transition("verify_fix")
        tracker.transition("learn")
        assert len(tracker.transitions) == 4

    def test_regression_raises_error(self):
        from pipeline.v2.phase_tracker import PhaseRegressionError, PhaseTracker

        tracker = PhaseTracker(["understand", "generate", "verify_fix", "learn"])
        tracker.transition("understand")
        tracker.transition("verify_fix")
        with pytest.raises(PhaseRegressionError):
            tracker.transition("understand")

    def test_generate_replan_allowed(self):
        """Replan: going back to generate from verify_fix is allowed."""
        from pipeline.v2.phase_tracker import PhaseTracker

        tracker = PhaseTracker(["understand", "generate", "verify_fix", "learn"])
        tracker.transition("understand")
        tracker.transition("generate")
        tracker.transition("verify_fix")
        # Replan: going back to generate is explicitly allowed
        tracker.transition("generate")
        assert len(tracker.transitions) == 4

    def test_same_phase_allowed(self):
        from pipeline.v2.phase_tracker import PhaseTracker

        tracker = PhaseTracker(["understand", "generate", "verify_fix", "learn"])
        tracker.transition("understand")
        tracker.transition("understand")  # same phase = OK
        assert len(tracker.transitions) == 2

    def test_unknown_phase_raises(self):
        from pipeline.v2.phase_tracker import PhaseTracker

        tracker = PhaseTracker(["understand", "generate"])
        with pytest.raises(ValueError):
            tracker.transition("nonexistent")
