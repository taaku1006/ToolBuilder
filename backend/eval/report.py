"""Eval harness report generation.

Aggregates EvalResult objects into comparison tables and reports.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import math

from eval.models import EvalResult


def _wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% confidence interval for a proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return (max(0.0, center - margin), min(1.0, center + margin))


class EvalReport:
    """Generates comparison reports from evaluation results."""

    def __init__(self, results: list[EvalResult]) -> None:
        self._results = results
        self._by_arch: dict[str, list[EvalResult]] = defaultdict(list)
        for r in results:
            self._by_arch[r.architecture_id].append(r)

    @property
    def architecture_ids(self) -> list[str]:
        return sorted(self._by_arch.keys())

    @property
    def test_case_ids(self) -> list[str]:
        seen: dict[str, None] = {}
        for r in self._results:
            seen[r.test_case_id] = None
        return list(seen.keys())

    def summary_table(self) -> dict[str, dict]:
        """Per-architecture aggregated metrics.

        Returns:
            {arch_id: {success_rate, avg_tokens, avg_duration_ms, avg_retries, total_runs}}
        """
        table: dict[str, dict] = {}
        for arch_id, results in self._by_arch.items():
            n = len(results)
            successes = sum(1 for r in results if r.metrics.success)
            total_tokens = sum(r.metrics.total_tokens for r in results)
            total_duration = sum(r.metrics.total_duration_ms for r in results)
            total_retries = sum(r.metrics.retry_count for r in results)
            total_cost = sum(r.metrics.estimated_cost_usd(r.model) for r in results)

            error_counts: dict[str, int] = {}
            for r in results:
                cat = r.metrics.error_category
                error_counts[cat] = error_counts.get(cat, 0) + 1

            # Compute per-phase token averages across all runs.
            # For each phase, average is computed over runs that reported that phase.
            phase_token_sums: dict[str, float] = defaultdict(float)
            phase_token_counts: dict[str, int] = defaultdict(int)
            for r in results:
                for phase, tokens in r.metrics.phase_tokens.items():
                    phase_token_sums[phase] += tokens
                    phase_token_counts[phase] += 1
            avg_phase_tokens: dict[str, float] = {
                phase: phase_token_sums[phase] / phase_token_counts[phase]
                for phase in phase_token_sums
            }

            ci_low, ci_high = _wilson_ci(successes, n)

            table[arch_id] = {
                "success_rate": successes / n if n > 0 else 0.0,
                "avg_tokens": total_tokens / n if n > 0 else 0.0,
                "avg_duration_ms": total_duration / n if n > 0 else 0.0,
                "avg_retries": total_retries / n if n > 0 else 0.0,
                "avg_cost_usd": total_cost / n if n > 0 else 0.0,
                "total_cost_usd": total_cost,
                "total_runs": n,
                "error_breakdown": error_counts,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "avg_phase_tokens": avg_phase_tokens,
            }
        return table

    def comparison_matrix(self) -> dict[str, dict[str, bool]]:
        """Per test case success by architecture.

        Returns:
            {case_id: {arch_id: success}}
        """
        matrix: dict[str, dict[str, bool]] = defaultdict(dict)
        for r in self._results:
            matrix[r.test_case_id][r.architecture_id] = r.metrics.success
        return dict(matrix)

    def best_architecture(self) -> str | None:
        """Return the architecture with highest success rate (tiebreak: lower tokens)."""
        if not self._by_arch:
            return None

        table = self.summary_table()

        def sort_key(arch_id: str) -> tuple[float, float]:
            row = table[arch_id]
            # Higher success rate is better (negate for ascending sort)
            # Lower tokens is better
            return (-row["success_rate"], row["avg_tokens"])

        return min(self._by_arch.keys(), key=sort_key)

    def to_markdown(self) -> str:
        """Generate a markdown comparison table."""
        table = self.summary_table()
        if not table:
            return "No results to report."

        lines = [
            "| Architecture | 成功率 | Avg Tokens | Avg Duration(ms) | Avg Retries | Runs |",
            "|---|---|---|---|---|---|",
        ]
        for arch_id in self.architecture_ids:
            row = table[arch_id]
            lines.append(
                f"| {arch_id} "
                f"| {row['success_rate']:.0%} "
                f"| {row['avg_tokens']:.0f} "
                f"| {row['avg_duration_ms']:.0f} "
                f"| {row['avg_retries']:.1f} "
                f"| {row['total_runs']} |"
            )

        best = self.best_architecture()
        if best:
            lines.append(f"\nBest: **{best}**")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize the full report to a dict."""
        return {
            "summary": self.summary_table(),
            "comparison_matrix": self.comparison_matrix(),
            "best_architecture": self.best_architecture(),
            "architecture_ids": self.architecture_ids,
            "test_case_ids": self.test_case_ids,
        }

    def save(self, path: Path) -> None:
        """Save report as JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
