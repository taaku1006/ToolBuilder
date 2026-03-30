"""Eval harness report generation.

Aggregates EvalResult objects into comparison tables and reports.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import math

from eval.models import EvalResult


# ---------------------------------------------------------------------------
# Run-to-run regression detection
# ---------------------------------------------------------------------------


@dataclass
class RunComparison:
    """Result of comparing two evaluation runs.

    Attributes:
        regressions: Cases that flipped pass→fail. Each entry is
            ``{"test_case_id": str, "architecture_id": str}``.
        fixes: Cases that flipped fail→pass. Same structure as regressions.
        unchanged_pass: Count of (arch, case) pairs that stayed passing.
        unchanged_fail: Count of (arch, case) pairs that stayed failing.
        new_cases: test_case_ids present in the current run but not in the
            previous run (across any architecture).
    """

    regressions: list[dict] = field(default_factory=list)
    fixes: list[dict] = field(default_factory=list)
    unchanged_pass: int = 0
    unchanged_fail: int = 0
    new_cases: list[str] = field(default_factory=list)
    quality_regressions: list[dict] = field(default_factory=list)


def compare_runs(
    current_results: list[EvalResult],
    previous_results: list[EvalResult],
) -> RunComparison:
    """Compare two evaluation runs and return a RunComparison.

    Matching is done on ``(architecture_id, test_case_id)`` pairs.
    If a pair appears multiple times in a list the last occurrence wins.

    Args:
        current_results: Results from the newer run.
        previous_results: Results from the baseline run.

    Returns:
        RunComparison describing regressions, fixes, and unchanged counts.
    """
    # Build lookup: (arch_id, case_id) -> success for each run.
    def _index(results: list[EvalResult]) -> dict[tuple[str, str], bool]:
        index: dict[tuple[str, str], bool] = {}
        for r in results:
            index[(r.architecture_id, r.test_case_id)] = r.metrics.success
        return index

    def _quality_index(results: list[EvalResult]) -> dict[tuple[str, str], float | None]:
        index: dict[tuple[str, str], float | None] = {}
        for r in results:
            index[(r.architecture_id, r.test_case_id)] = r.metrics.quality_score
        return index

    current_index = _index(current_results)
    previous_index = _index(previous_results)
    current_quality = _quality_index(current_results)
    previous_quality = _quality_index(previous_results)

    # Determine which test_case_ids existed in the previous run.
    previous_case_ids: set[str] = {case_id for _, case_id in previous_index}

    regressions: list[dict] = []
    fixes: list[dict] = []
    unchanged_pass = 0
    unchanged_fail = 0
    new_case_ids: set[str] = set()

    for (arch_id, case_id), current_success in current_index.items():
        key = (arch_id, case_id)
        if key not in previous_index:
            # This exact (arch, case) pair is new.
            # Track as new_case only when the case_id itself is absent from previous.
            if case_id not in previous_case_ids:
                new_case_ids.add(case_id)
            # Either way, don't count it in regression/fix/unchanged.
            continue

        previous_success = previous_index[key]

        if previous_success and not current_success:
            regressions.append({"test_case_id": case_id, "architecture_id": arch_id})
        elif not previous_success and current_success:
            fixes.append({"test_case_id": case_id, "architecture_id": arch_id})
        elif current_success:
            unchanged_pass += 1
        else:
            unchanged_fail += 1

    # Detect quality regressions (score dropped by >= 0.1)
    quality_regressions: list[dict] = []
    for key in current_quality:
        if key in previous_quality:
            cur_q = current_quality[key]
            prev_q = previous_quality[key]
            if cur_q is not None and prev_q is not None and prev_q - cur_q >= 0.1:
                quality_regressions.append({
                    "test_case_id": key[1],
                    "architecture_id": key[0],
                    "previous_score": round(prev_q, 4),
                    "current_score": round(cur_q, 4),
                })

    return RunComparison(
        regressions=regressions,
        fixes=fixes,
        unchanged_pass=unchanged_pass,
        unchanged_fail=unchanged_fail,
        new_cases=sorted(new_case_ids),
        quality_regressions=quality_regressions,
    )


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

            # Quality score average (skip None)
            quality_scores = [
                r.metrics.quality_score for r in results
                if r.metrics.quality_score is not None
            ]
            avg_quality = (
                sum(quality_scores) / len(quality_scores) if quality_scores else None
            )

            # LLM eval score average (skip None)
            llm_eval_scores = [
                r.metrics.llm_eval_score for r in results
                if r.metrics.llm_eval_score is not None
            ]
            avg_llm_eval = (
                sum(llm_eval_scores) / len(llm_eval_scores) if llm_eval_scores else None
            )

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
                "avg_quality_score": avg_quality,
                "quality_evaluated_count": len(quality_scores),
                "avg_llm_eval_score": avg_llm_eval,
                "llm_eval_count": len(llm_eval_scores),
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

    def quality_matrix(self) -> dict[str, dict[str, float | None]]:
        """Per test case quality score by architecture.

        Returns:
            {case_id: {arch_id: quality_score or None}}
        """
        matrix: dict[str, dict[str, float | None]] = defaultdict(dict)
        for r in self._results:
            matrix[r.test_case_id][r.architecture_id] = r.metrics.quality_score
        return dict(matrix)

    def llm_eval_matrix(self) -> dict[str, dict[str, float | None]]:
        """Per test case LLM evaluation score by architecture.

        Returns:
            {case_id: {arch_id: llm_eval_score or None}}
        """
        matrix: dict[str, dict[str, float | None]] = defaultdict(dict)
        for r in self._results:
            matrix[r.test_case_id][r.architecture_id] = r.metrics.llm_eval_score
        return dict(matrix)

    def best_architecture(self) -> str | None:
        """Return the architecture with highest success rate (tiebreak: lower tokens)."""
        if not self._by_arch:
            return None

        table = self.summary_table()

        def sort_key(arch_id: str) -> tuple[float, float, float]:
            row = table[arch_id]
            # Higher success rate is better (negate for ascending sort)
            # Higher quality score is better (negate)
            # Lower tokens is better
            quality = row.get("avg_quality_score") or 0.0
            return (-row["success_rate"], -quality, row["avg_tokens"])

        return min(self._by_arch.keys(), key=sort_key)

    def to_markdown(self) -> str:
        """Generate a markdown comparison table."""
        table = self.summary_table()
        if not table:
            return "No results to report."

        lines = [
            "| Architecture | 成功率 | Quality | LLM Eval | Avg Tokens | Avg Duration(ms) | Avg Retries | Runs |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for arch_id in self.architecture_ids:
            row = table[arch_id]
            quality_str = f"{row['avg_quality_score']:.2f}" if row.get("avg_quality_score") is not None else "-"
            llm_eval_str = f"{row['avg_llm_eval_score']:.1f}" if row.get("avg_llm_eval_score") is not None else "-"
            lines.append(
                f"| {arch_id} "
                f"| {row['success_rate']:.0%} "
                f"| {quality_str} "
                f"| {llm_eval_str} "
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
            "quality_matrix": self.quality_matrix(),
            "llm_eval_matrix": self.llm_eval_matrix(),
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
