"""EvalRunManager service.

Encapsulates all business logic for running evaluations, tracking run state,
and loading results/snapshots. The router delegates to this service and
remains a thin HTTP handler.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from core.config import Settings
from eval.models import (
    ArchitectureConfig,
    EvalMetrics,
    EvalResult,
    TestCase,
    load_architecture,
    load_test_case,
)
from eval.versioning import RunSnapshot

logger = logging.getLogger(__name__)


class EvalRunManager:
    """Manages eval run lifecycle and provides data-loading helpers.

    A single instance should be kept alive for the lifetime of the application
    so that `_run_status` (in-memory run tracking) persists across requests.

    Parameters
    ----------
    settings:
        Application settings used as the base for `settings_factory`.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._run_status: dict[str, dict] = {}
        self._change_events: dict[str, asyncio.Event] = {}

    # ------------------------------------------------------------------
    # Architecture / test-case loading
    # ------------------------------------------------------------------

    def list_architectures(self, archs_dir: Path) -> list[ArchitectureConfig]:
        """Return all architecture configs found in *archs_dir*.

        Returns an empty list when the directory does not exist.
        """
        if not archs_dir.exists():
            return []
        return [load_architecture(p) for p in sorted(archs_dir.glob("*.json"))]

    def list_test_cases(self, cases_dir: Path) -> list[TestCase]:
        """Return all test cases found in *cases_dir*.

        Returns an empty list when the directory does not exist.
        """
        if not cases_dir.exists():
            return []
        return [load_test_case(p) for p in sorted(cases_dir.glob("*.json"))]

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------

    def start_run(self, *, run_id: str, total: int) -> dict:
        """Register a new run in the in-memory status store.

        Parameters
        ----------
        run_id:
            Unique identifier for this run (e.g. ``"20240101_120000"``).
        total:
            Total number of (arch, case) combinations to evaluate.

        Returns
        -------
        dict
            The initial status dict for the run.
        """
        entry: dict = {
            "status": "running",
            "progress": 0,
            "total": total,
            "report": None,
            "cancel_requested": False,
        }
        self._run_status[run_id] = entry
        return entry

    def _notify(self, run_id: str) -> None:
        """Signal all SSE waiters that *run_id* status has changed."""
        event = self._change_events.get(run_id)
        if event is not None:
            event.set()

    async def wait_for_change(self, run_id: str, timeout: float = 5.0) -> bool:
        """Block until *run_id* status changes or *timeout* elapses.

        Returns ``True`` if a change was signalled, ``False`` on timeout.
        The event is automatically reset after waking so subsequent calls
        will wait for the *next* change.
        """
        if run_id not in self._change_events:
            self._change_events[run_id] = asyncio.Event()
        event = self._change_events[run_id]
        event.clear()
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def get_status(self, run_id: str) -> dict | None:
        """Return the current status dict for *run_id*, or ``None`` if unknown."""
        return self._run_status.get(run_id)

    def stop_run(self, run_id: str) -> bool:
        """Request cancellation for *run_id*.

        Returns
        -------
        bool
            ``True`` if the run was found and the flag was set,
            ``False`` when *run_id* is not tracked.
        """
        entry = self._run_status.get(run_id)
        if entry is None:
            return False
        entry["cancel_requested"] = True
        self._notify(run_id)
        return True

    def update_progress(self, *, run_id: str, progress: int) -> None:
        """Update the progress counter for an active run."""
        entry = self._run_status.get(run_id)
        if entry is not None:
            entry["progress"] = progress
            self._notify(run_id)

    def complete_run(self, *, run_id: str, report: dict | None) -> None:
        """Mark a run as completed and attach its report."""
        entry = self._run_status.get(run_id)
        if entry is not None:
            entry["status"] = "completed"
            entry["report"] = report
            self._notify(run_id)

    def fail_run(self, *, run_id: str, error: str) -> None:
        """Mark a run as failed with an error message."""
        entry = self._run_status.get(run_id)
        if entry is not None:
            entry["status"] = "failed"
            entry["report"] = {"error": error}
            self._notify(run_id)

    def mark_stopped(self, *, run_id: str) -> None:
        """Mark a run as stopped (cancelled mid-run)."""
        entry = self._run_status.get(run_id)
        if entry is not None:
            entry["status"] = "stopped"
            self._notify(run_id)

    # ------------------------------------------------------------------
    # Settings factory
    # ------------------------------------------------------------------

    def settings_factory(self, overrides: dict | None = None) -> Settings:
        """Return a Settings instance, optionally with field overrides applied.

        The base settings come from the instance's ``_settings``.
        Each override is set via ``object.__setattr__`` to bypass Pydantic's
        immutability guard.
        """
        settings = self._settings
        if overrides:
            for key, value in overrides.items():
                object.__setattr__(settings, key, value)
        return settings

    # ------------------------------------------------------------------
    # Results / snapshot loading
    # ------------------------------------------------------------------

    def load_results(self, *, run_id: str, results_dir: Path) -> list[EvalResult]:
        """Load eval results from a run's ``summary.json`` file.

        Parameters
        ----------
        run_id:
            The run identifier used to locate ``results/run_{run_id}/summary.json``.
        results_dir:
            Base directory that contains per-run result sub-directories.

        Raises
        ------
        FileNotFoundError
            When the summary file does not exist.
        """
        summary_path = results_dir / f"run_{run_id}" / "summary.json"
        if not summary_path.exists():
            raise FileNotFoundError(f"Run '{run_id}' not found at {summary_path}")

        raw = json.loads(summary_path.read_text(encoding="utf-8"))
        results: list[EvalResult] = []
        for item in raw.get("results", []):
            m = item.get("metrics", {})
            results.append(
                EvalResult(
                    architecture_id=item["architecture_id"],
                    test_case_id=item["test_case_id"],
                    metrics=EvalMetrics(
                        success=m.get("success", False),
                        total_duration_ms=m.get("total_duration_ms", 0),
                        total_tokens=m.get("total_tokens", 0),
                        prompt_tokens=m.get("prompt_tokens", 0),
                        completion_tokens=m.get("completion_tokens", 0),
                        api_calls=m.get("api_calls", 0),
                        phase_durations_ms=m.get("phase_durations_ms", {}),
                        phase_tokens=m.get("phase_tokens", {}),
                        retry_count=m.get("retry_count", 0),
                        code_executes=m.get("code_executes", False),
                        error_category=m.get("error_category", "none"),
                        quality_score=m.get("quality_score"),
                        quality_details=m.get("quality_details"),
                        llm_eval_score=m.get("llm_eval_score"),
                        llm_eval_details=m.get("llm_eval_details"),
                    ),
                    agent_log=item.get("agent_log", []),
                    model=item.get("model", "gpt-4o"),
                    generated_code=item.get("generated_code"),
                    error=item.get("error"),
                )
            )
        return results

    def load_snapshot(self, *, run_id: str, results_dir: Path) -> RunSnapshot:
        """Load the ``RunSnapshot`` for a completed run.

        Parameters
        ----------
        run_id:
            The run identifier.
        results_dir:
            Base results directory.

        Raises
        ------
        FileNotFoundError
            When the snapshot file does not exist.
        """
        path = results_dir / f"run_{run_id}" / "snapshot.json"
        if not path.exists():
            raise FileNotFoundError(f"Snapshot not found for run '{run_id}' at {path}")

        raw = json.loads(path.read_text(encoding="utf-8"))
        return RunSnapshot(
            prompt_hashes=raw["prompt_hashes"],
            prompt_contents=raw["prompt_contents"],
            architecture_configs=raw["architecture_configs"],
            snapshot_hash=raw["snapshot_hash"],
        )

    # ------------------------------------------------------------------
    # Run listing
    # ------------------------------------------------------------------

    def list_runs(self, *, results_dir: Path) -> list[dict]:
        """List all known eval runs, combining disk-persisted and in-memory runs.

        Disk runs are sorted newest-first (by directory name).
        In-memory running runs are prepended at the front of the list.

        Parameters
        ----------
        results_dir:
            Directory containing per-run sub-directories (``run_<id>``).
        """
        runs: list[dict] = []

        if results_dir.exists():
            for d in sorted(results_dir.iterdir(), reverse=True):
                if d.is_dir() and d.name.startswith("run_"):
                    report_path = d / "report.json"
                    run_id = d.name.removeprefix("run_")
                    entry: dict = {"run_id": run_id, "status": "completed"}
                    if report_path.exists():
                        report_data = json.loads(report_path.read_text(encoding="utf-8"))
                        entry["best_architecture"] = report_data.get("best_architecture")
                        entry["summary"] = report_data.get("summary")
                    runs.append(entry)

        # Prepend in-memory running runs
        for run_id, s in self._run_status.items():
            if s["status"] == "running":
                runs.insert(0, {
                    "run_id": run_id,
                    "status": "running",
                    "progress": s["progress"],
                    "total": s["total"],
                })

        return runs
