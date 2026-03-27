"""CLI entry point for eval harness.

Usage:
    uv run python -m eval --cases eval/test_cases/ --archs eval/architectures/
    uv run python -m eval --report eval/results/run_xxx/summary.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from eval.models import load_architecture, load_test_case
from eval.report import EvalReport
from eval.runner import EvalRunner

from core.config import Settings

logger = logging.getLogger(__name__)


def _load_all_architectures(dir_path: Path) -> list:
    return [load_architecture(p) for p in sorted(dir_path.glob("*.json"))]


def _load_all_test_cases(dir_path: Path) -> list:
    return [load_test_case(p) for p in sorted(dir_path.glob("*.json"))]


def _settings_factory(overrides: dict | None = None) -> Settings:
    """Create Settings from .env with optional overrides."""
    settings = Settings()  # type: ignore[call-arg]
    if overrides:
        for key, value in overrides.items():
            object.__setattr__(settings, key, value)
    return settings


async def run_eval(cases_dir: Path, archs_dir: Path, output_dir: Path) -> None:
    archs = _load_all_architectures(archs_dir)
    cases = _load_all_test_cases(cases_dir)

    print(f"Loaded {len(archs)} architectures, {len(cases)} test cases")
    print(f"Total combinations: {len(archs) * len(cases)}")

    runner = EvalRunner(
        architectures=archs,
        test_cases=cases,
        settings_factory=_settings_factory,
    )

    results = await runner.run_all()
    runner.save_results(results, output_dir)

    report = EvalReport(results)
    report.save(output_dir / "report.json")

    print("\n" + report.to_markdown())
    print(f"\nResults saved to: {output_dir}")


def show_report(report_path: Path) -> None:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    summary = data.get("summary", {})

    print(f"{'Architecture':<15} {'Success%':>10} {'Avg Tokens':>12} {'Avg Time(ms)':>14} {'Avg Retries':>12} {'Runs':>6}")
    print("-" * 75)
    for arch_id, row in summary.items():
        print(
            f"{arch_id:<15} "
            f"{row['success_rate']:>9.0%} "
            f"{row['avg_tokens']:>12.0f} "
            f"{row['avg_duration_ms']:>14.0f} "
            f"{row['avg_retries']:>12.1f} "
            f"{row['total_runs']:>6}"
        )

    best = data.get("best_architecture")
    if best:
        print(f"\nBest: {best}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Architecture Eval Harness")
    subparsers = parser.add_subparsers(dest="command")

    # Run evaluation
    run_parser = subparsers.add_parser("run", help="Run evaluations")
    run_parser.add_argument("--cases", type=Path, required=True, help="Test cases directory")
    run_parser.add_argument("--archs", type=Path, required=True, help="Architectures directory")
    run_parser.add_argument("--output", type=Path, default=None, help="Output directory")

    # Show report
    report_parser = subparsers.add_parser("report", help="Show report")
    report_parser.add_argument("path", type=Path, help="Path to report.json")

    args = parser.parse_args()

    if args.command == "run":
        output = args.output or Path(f"eval/results/run_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}")
        asyncio.run(run_eval(args.cases, args.archs, output))
    elif args.command == "report":
        show_report(args.path)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
