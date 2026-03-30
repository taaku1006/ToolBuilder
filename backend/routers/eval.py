"""Eval harness API endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from fastapi import File as FastAPIFile
from pydantic import BaseModel

from core.config import Settings
from core.deps import get_settings
from eval.models import EvalMetrics, EvalResult, load_architecture, load_test_case
from eval.report import EvalReport, RunComparison, compare_runs
from eval.runner import EvalRunner
from eval.versioning import capture_run_snapshot, diff_snapshots

logger = logging.getLogger(__name__)

router = APIRouter(tags=["eval"])

_EVAL_DIR = Path(__file__).parent.parent / "eval"
_ARCHS_DIR = _EVAL_DIR / "architectures"
_CASES_DIR = _EVAL_DIR / "test_cases"
_RESULTS_DIR = _EVAL_DIR / "results"

_ALLOWED_EVAL_EXTENSIONS = {".xlsx", ".xls", ".csv"}

# In-memory run status tracking
_run_status: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ArchitectureOut(BaseModel):
    id: str
    phases: list[str]
    model: str
    debug_retry_limit: int
    temperature: float
    description: str
    pipeline: dict | None = None


class TestCaseOut(BaseModel):
    id: str
    task: str
    description: str
    file_path: str | None
    expected_file_path: str | None = None
    expected_success: bool


class RunRequest(BaseModel):
    architecture_ids: list[str] | None = None  # None = all
    test_case_ids: list[str] | None = None     # None = all


class RunStatusOut(BaseModel):
    run_id: str
    status: str  # "running" | "completed" | "failed"
    progress: int  # completed combos
    total: int     # total combos
    report: dict | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings_factory(overrides: dict | None = None) -> Settings:
    settings = get_settings()
    if overrides:
        for key, value in overrides.items():
            object.__setattr__(settings, key, value)
    return settings


def _load_archs() -> list:
    if not _ARCHS_DIR.exists():
        return []
    return [load_architecture(p) for p in sorted(_ARCHS_DIR.glob("*.json"))]


def _load_cases() -> list:
    if not _CASES_DIR.exists():
        return []
    return [load_test_case(p) for p in sorted(_CASES_DIR.glob("*.json"))]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/eval/architectures")
async def list_architectures() -> list[ArchitectureOut]:
    archs = _load_archs()
    return [
        ArchitectureOut(
            id=a.id,
            phases=a.phases,
            model=a.model,
            debug_retry_limit=a.debug_retry_limit,
            temperature=a.temperature,
            description=a.description,
            pipeline={
                "explore": a.pipeline.explore,
                "reflect": a.pipeline.reflect,
                "decompose": a.pipeline.decompose,
                "debug_retry_limit": a.pipeline.debug_retry_limit,
                "eval_debug": a.pipeline.eval_debug,
                "eval_retry_strategy": a.pipeline.eval_retry_strategy,
                "eval_retry_max_loops": a.pipeline.eval_retry_max_loops,
                "subtask_debug_retries": a.pipeline.subtask_debug_retries,
            } if a.pipeline else None,
        )
        for a in archs
    ]


@router.get("/eval/test-cases")
async def list_test_cases() -> list[TestCaseOut]:
    cases = _load_cases()
    return [
        TestCaseOut(
            id=c.id,
            task=c.task,
            description=c.description,
            file_path=c.file_path,
            expected_file_path=getattr(c, "expected_file_path", None),
            expected_success=c.expected_success,
        )
        for c in cases
    ]


@router.post("/eval/run")
async def start_eval_run(
    req: RunRequest,
    background_tasks: BackgroundTasks,
) -> RunStatusOut:
    """Start an eval run in the background."""
    all_archs = _load_archs()
    all_cases = _load_cases()

    archs = (
        [a for a in all_archs if a.id in req.architecture_ids]
        if req.architecture_ids
        else all_archs
    )
    cases = (
        [c for c in all_cases if c.id in req.test_case_ids]
        if req.test_case_ids
        else all_cases
    )

    run_id = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    total = len(archs) * len(cases)

    _run_status[run_id] = {
        "status": "running",
        "progress": 0,
        "total": total,
        "report": None,
        "cancel_requested": False,
    }

    async def _run() -> None:
        try:
            runner = EvalRunner(
                architectures=archs,
                test_cases=cases,
                settings_factory=_settings_factory,
            )

            results = []
            for arch in archs:
                for case in cases:
                    if _run_status[run_id]["cancel_requested"]:
                        logger.info("Eval run cancelled", extra={"run_id": run_id})
                        break
                    result = await runner.run_single(arch, case)
                    results.append(result)
                    _run_status[run_id]["progress"] = len(results)
                if _run_status[run_id]["cancel_requested"]:
                    break

            cancelled = _run_status[run_id]["cancel_requested"]

            if results:
                output_dir = _RESULTS_DIR / f"run_{run_id}"
                snapshot = capture_run_snapshot(
                    prompt_dir=Path(__file__).parent.parent / "prompts",
                    arch_dir=_ARCHS_DIR,
                )
                runner.save_results(results, output_dir, snapshot=snapshot)
                report = EvalReport(results)
                report.save(output_dir / "report.json")
                _run_status[run_id]["report"] = report.to_dict()

            _run_status[run_id]["status"] = "stopped" if cancelled else "completed"
        except Exception as exc:
            logger.exception("Eval run failed")
            _run_status[run_id]["status"] = "failed"
            _run_status[run_id]["report"] = {"error": str(exc)}

    background_tasks.add_task(_run)

    return RunStatusOut(
        run_id=run_id,
        status="running",
        progress=0,
        total=total,
    )


@router.post("/eval/run/{run_id}/stop")
async def stop_eval_run(run_id: str) -> RunStatusOut:
    """Request cancellation of a running eval."""
    if run_id not in _run_status:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    s = _run_status[run_id]
    if s["status"] != "running":
        raise HTTPException(status_code=400, detail=f"Run is not running (status: {s['status']})")

    s["cancel_requested"] = True
    logger.info("Eval stop requested", extra={"run_id": run_id})

    return RunStatusOut(
        run_id=run_id,
        status="stopping",
        progress=s["progress"],
        total=s["total"],
    )


@router.get("/eval/run/{run_id}")
async def get_eval_status(run_id: str) -> RunStatusOut:
    """Poll eval run status."""
    if run_id not in _run_status:
        # Try loading from disk
        result_dir = _RESULTS_DIR / f"run_{run_id}"
        report_path = result_dir / "report.json"
        if report_path.exists():
            report_data = json.loads(report_path.read_text(encoding="utf-8"))
            return RunStatusOut(
                run_id=run_id,
                status="completed",
                progress=report_data.get("total_runs", 0),
                total=report_data.get("total_runs", 0),
                report=report_data,
            )
        return RunStatusOut(
            run_id=run_id, status="not_found", progress=0, total=0
        )

    s = _run_status[run_id]
    return RunStatusOut(
        run_id=run_id,
        status=s["status"],
        progress=s["progress"],
        total=s["total"],
        report=s["report"],
    )


@router.get("/eval/runs")
async def list_runs() -> list[dict]:
    """List past eval runs."""
    runs = []
    if _RESULTS_DIR.exists():
        for d in sorted(_RESULTS_DIR.iterdir(), reverse=True):
            if d.is_dir() and d.name.startswith("run_"):
                report_path = d / "report.json"
                run_id = d.name.removeprefix("run_")
                entry: dict = {"run_id": run_id, "status": "completed"}
                if report_path.exists():
                    report_data = json.loads(report_path.read_text(encoding="utf-8"))
                    entry["best_architecture"] = report_data.get("best_architecture")
                    entry["summary"] = report_data.get("summary")
                runs.append(entry)

    # Add in-memory running runs
    for run_id, s in _run_status.items():
        if s["status"] == "running":
            runs.insert(0, {
                "run_id": run_id,
                "status": "running",
                "progress": s["progress"],
                "total": s["total"],
            })

    return runs


# ---------------------------------------------------------------------------
# Create test case
# ---------------------------------------------------------------------------


@router.post("/eval/test-cases", status_code=201)
async def create_test_case(
    task: str = Form(...),
    description: str = Form(""),
    file: UploadFile | None = FastAPIFile(default=None),
    expected_file: UploadFile | None = FastAPIFile(default=None),
) -> TestCaseOut:
    """Create a new test case (with optional input file and expected output file).

    Saves the test case as a JSON file in the eval test_cases directory.
    If files are uploaded, they are saved to eval/test_cases/files/ and
    the paths are recorded in the test case JSON.
    """
    stripped_task = task.strip()
    if not stripped_task:
        raise HTTPException(status_code=422, detail="'task' must not be empty or whitespace")

    case_id = str(uuid.uuid4())
    file_path: str | None = None
    expected_file_path: str | None = None

    files_dir = _CASES_DIR / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    # Save input file
    if file is not None:
        filename = file.filename or ""
        ext = Path(filename).suffix.lower()
        if ext not in _ALLOWED_EVAL_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file type '{ext}'. "
                    f"Allowed: {', '.join(sorted(_ALLOWED_EVAL_EXTENSIONS))}"
                ),
            )
        safe_name = f"{case_id}_input{ext}"
        dest = files_dir / safe_name
        content = await file.read()
        dest.write_bytes(content)
        file_path = str(dest)

    # Save expected output file
    if expected_file is not None:
        filename = expected_file.filename or ""
        ext = Path(filename).suffix.lower()
        if ext not in _ALLOWED_EVAL_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported expected file type '{ext}'. "
                    f"Allowed: {', '.join(sorted(_ALLOWED_EVAL_EXTENSIONS))}"
                ),
            )
        safe_name = f"{case_id}_expected{ext}"
        dest = files_dir / safe_name
        content = await expected_file.read()
        dest.write_bytes(content)
        expected_file_path = str(dest)

    case_data = {
        "id": case_id,
        "task": stripped_task,
        "description": description,
        "file_path": file_path,
        "expected_file_path": expected_file_path,
        "expected_success": True,
    }

    _CASES_DIR.mkdir(parents=True, exist_ok=True)
    json_file = _CASES_DIR / f"{case_id}.json"
    json_file.write_text(json.dumps(case_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return TestCaseOut(
        id=case_id,
        task=stripped_task,
        description=description,
        file_path=file_path,
        expected_file_path=expected_file_path,
        expected_success=True,
    )


# ---------------------------------------------------------------------------
# Delete test case
# ---------------------------------------------------------------------------


@router.delete("/eval/test-cases/{case_id}", status_code=204)
async def delete_test_case(case_id: str) -> None:
    """Delete a test case by ID.

    Removes the JSON file and, if the test case has an associated file,
    removes that file too.
    """
    # Find the JSON file — could be named <case_id>.json or <anything>.json
    # matching by id field inside for pre-defined cases not named by uuid
    json_file = _CASES_DIR / f"{case_id}.json"

    if not json_file.exists():
        # Search all JSON files for one whose 'id' matches
        found = None
        if _CASES_DIR.exists():
            for p in _CASES_DIR.glob("*.json"):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if data.get("id") == case_id:
                        found = p
                        break
                except (json.JSONDecodeError, OSError):
                    continue
        if found is None:
            raise HTTPException(status_code=404, detail=f"Test case '{case_id}' not found")
        json_file = found

    # Load the case data to find the file_path
    try:
        case_data = json.loads(json_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        case_data = {}

    # Remove associated file if present
    file_path = case_data.get("file_path")
    if file_path:
        fp = Path(file_path)
        fp.unlink(missing_ok=True)

    json_file.unlink()


# ---------------------------------------------------------------------------
# Snapshot endpoints
# ---------------------------------------------------------------------------


@router.get("/eval/run/{run_id}/snapshot")
async def get_run_snapshot(run_id: str) -> dict:
    """Return the prompt/config snapshot captured for this run."""
    snapshot_path = _RESULTS_DIR / f"run_{run_id}" / "snapshot.json"
    if not snapshot_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Snapshot not found for run '{run_id}'",
        )
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


@router.get("/eval/run/{run_id}/compare/{baseline_id}")
async def compare_eval_runs(run_id: str, baseline_id: str) -> dict:
    """Compare two eval runs and return regression/fix analysis.

    Compares *run_id* (current) against *baseline_id* (previous/baseline).

    Returns a dict with keys:
      - regressions: list of {test_case_id, architecture_id} that flipped pass→fail
      - fixes: list of {test_case_id, architecture_id} that flipped fail→pass
      - unchanged_pass: count of pairs that stayed passing
      - unchanged_fail: count of pairs that stayed failing
      - new_cases: list of test_case_ids present in current but not in baseline
    """

    def _load_results(rid: str) -> list[EvalResult]:
        summary_path = _RESULTS_DIR / f"run_{rid}" / "summary.json"
        if not summary_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Run '{rid}' not found",
            )
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

    current = _load_results(run_id)
    baseline = _load_results(baseline_id)

    comparison: RunComparison = compare_runs(current, baseline)
    return {
        "regressions": comparison.regressions,
        "fixes": comparison.fixes,
        "unchanged_pass": comparison.unchanged_pass,
        "unchanged_fail": comparison.unchanged_fail,
        "new_cases": comparison.new_cases,
        "quality_regressions": comparison.quality_regressions,
    }


@router.get("/eval/run/{run_id}/diff/{other_id}")
async def diff_run_snapshots(run_id: str, other_id: str) -> dict:
    """Return the diff between two run snapshots.

    Compares the snapshot of *run_id* (snapshot a) against *other_id* (snapshot b).
    """
    _prompts_dir = Path(__file__).parent.parent / "prompts"

    def _load_snapshot(rid: str):
        path = _RESULTS_DIR / f"run_{rid}" / "snapshot.json"
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Snapshot not found for run '{rid}'",
            )
        raw = json.loads(path.read_text(encoding="utf-8"))
        from eval.versioning import RunSnapshot
        return RunSnapshot(
            prompt_hashes=raw["prompt_hashes"],
            prompt_contents=raw["prompt_contents"],
            architecture_configs=raw["architecture_configs"],
            snapshot_hash=raw["snapshot_hash"],
        )

    snap_a = _load_snapshot(run_id)
    snap_b = _load_snapshot(other_id)
    diff = diff_snapshots(snap_a, snap_b)
    return {
        "run_id": run_id,
        "other_id": other_id,
        "changed_prompts": diff.changed_prompts,
        "changed_configs": diff.changed_configs,
        "is_identical": diff.is_identical,
    }
