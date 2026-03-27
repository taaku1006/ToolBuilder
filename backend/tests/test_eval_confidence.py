"""Tests for Wilson score confidence interval."""

from __future__ import annotations

import pytest

from eval.report import _wilson_ci


class TestWilsonCI:
    def test_zero_trials(self) -> None:
        assert _wilson_ci(0, 0) == (0.0, 0.0)

    def test_all_success(self) -> None:
        low, high = _wilson_ci(10, 10)
        assert low > 0.6
        assert high == 1.0

    def test_all_failure(self) -> None:
        low, high = _wilson_ci(0, 10)
        assert low == 0.0
        assert high < 0.4

    def test_half_success(self) -> None:
        low, high = _wilson_ci(50, 100)
        assert 0.35 < low < 0.45
        assert 0.55 < high < 0.65

    def test_small_sample_wide_interval(self) -> None:
        """3 cases, 2 successes → very wide CI."""
        low, high = _wilson_ci(2, 3)
        assert high - low > 0.3  # Wide interval

    def test_large_sample_narrow_interval(self) -> None:
        """100 cases, 80 successes → narrow CI."""
        low, high = _wilson_ci(80, 100)
        assert high - low < 0.16

    def test_bounds_are_valid(self) -> None:
        for s in range(11):
            low, high = _wilson_ci(s, 10)
            assert 0.0 <= low <= high <= 1.0
