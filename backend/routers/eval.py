"""Eval harness API endpoints.

This router is a thin HTTP handler. All business logic lives in
`eval.run_manager.EvalRunManager`.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, UploadFile
from fastapi import File as FastAPIFile
from pydantic import BaseModel

from core.config import Settings
from core.deps import get_settings
from eval.models import load_architecture, load_test_case
from eval.report import EvalReport, compare_runs
from eval.runner import EvalRunner
from eval.versioning import capture_run_snapshot, diff_snapshots
from eval.run_manager import EvalRunManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["eval"])

_EVAL_DIR = Path(__file__).parent.parent / "eval"
_ARCHS_DIR = _EVAL_DIR / "architectures"
_CASES_DIR = _EVAL_DIR / "test_cases"
_RESULTS_DIR = _EVAL_DIR / "results"

_ALLOWED_EVAL_EXTENSIONS = {".xlsx", ".xls", ".csv"}

# Module-level singleton so _run_status persists across requests
_manager = EvalRunManager(settings=get_settings())


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
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/eval/architectures")
async def list_architectures() -> list[ArchitectureOut]:
    archs = _manager.list_architectures(archs_dir=_ARCHS_DIR)
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
                "llm_eval_debug": a.pipeline.llm_eval_debug,
                "llm_eval_score_threshold": a.pipeline.llm_eval_score_threshold,
                "llm_eval_retry_limit": a.pipeline.llm_eval_retry_limit,
                "subtask_debug_retries": a.pipeline.subtask_debug_retries,
            } if a.pipeline else None,
        )
        for a in archs
    ]


@router.get("/eval/test-cases")
async def list_test_cases() -> list[TestCaseOut]:
    cases = _manager.list_test_cases(cases_dir=_CASES_DIR)
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
    all_archs = _manager.list_architectures(archs_dir=_ARCHS_DIR)
    all_cases = _manager.list_test_cases(cases_dir=_CASES_DIR)

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
    _manager.start_run(run_id=run_id, total=total)

    async def _run() -> None:
        try:
            runner = EvalRunner(
                architectures=archs,
                test_cases=cases,
                settings_factory=_manager.settings_factory,
                cancel_check=lambda: (_manager.get_status(run_id) or {}).get(
                    "cancel_requested", False
                ),
            )

            results = []
            for arch in archs:
                for case in cases:
                    status = _manager.get_status(run_id) or {}
                    if status.get("cancel_requested"):
                        logger.info("Eval run cancelled", extra={"run_id": run_id})
                        break
                    result = await runner.run_single(arch, case)
                    results.append(result)
                    _manager.update_progress(run_id=run_id, progress=len(results))
                if (_manager.get_status(run_id) or {}).get("cancel_requested"):
                    break

            cancelled = (_manager.get_status(run_id) or {}).get("cancel_requested", False)

            if results:
                output_dir = _RESULTS_DIR / f"run_{run_id}"
                snapshot = capture_run_snapshot(
                    prompt_dir=Path(__file__).parent.parent / "prompts",
                    arch_dir=_ARCHS_DIR,
                )
                runner.save_results(results, output_dir, snapshot=snapshot)
                report = EvalReport(results)
                report.save(output_dir / "report.json")
                _manager.complete_run(run_id=run_id, report=report.to_dict())
            elif cancelled:
                _manager.mark_stopped(run_id=run_id)
            else:
                _manager.complete_run(run_id=run_id, report=None)

            if cancelled and results:
                _manager.mark_stopped(run_id=run_id)

        except Exception as exc:
            logger.exception("Eval run failed")
            _manager.fail_run(run_id=run_id, error=str(exc))

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
    s = _manager.get_status(run_id)
    if s is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    if s["status"] != "running":
        raise HTTPException(status_code=400, detail=f"Run is not running (status: {s['status']})")

    _manager.stop_run(run_id)
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
    s = _manager.get_status(run_id)
    if s is None:
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
        return RunStatusOut(run_id=run_id, status="not_found", progress=0, total=0)

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
    return _manager.list_runs(results_dir=_RESULTS_DIR)


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
    """Create a new test case with optional input and expected output files."""
    stripped_task = task.strip()
    if not stripped_task:
        raise HTTPException(status_code=422, detail="'task' must not be empty or whitespace")

    case_id = str(uuid.uuid4())
    file_path: str | None = None
    expected_file_path: str | None = None

    files_dir = _CASES_DIR / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

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
    """Delete a test case by ID."""
    json_file = _CASES_DIR / f"{case_id}.json"

    if not json_file.exists():
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

    try:
        case_data = json.loads(json_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        case_data = {}

    file_path = case_data.get("file_path")
    if file_path:
        Path(file_path).unlink(missing_ok=True)

    json_file.unlink()


# ---------------------------------------------------------------------------
# Snapshot endpoints
# ---------------------------------------------------------------------------


@router.get("/eval/run/{run_id}/snapshot")
async def get_run_snapshot(run_id: str) -> dict:
    """Return the prompt/config snapshot captured for this run."""
    try:
        snapshot = _manager.load_snapshot(run_id=run_id, results_dir=_RESULTS_DIR)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Snapshot not found for run '{run_id}'",
        )
    return snapshot.to_dict()


@router.get("/eval/run/{run_id}/compare/{baseline_id}")
async def compare_eval_runs(run_id: str, baseline_id: str) -> dict:
    """Compare two eval runs and return regression/fix analysis."""
    try:
        current = _manager.load_results(run_id=run_id, results_dir=_RESULTS_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    try:
        baseline = _manager.load_results(run_id=baseline_id, results_dir=_RESULTS_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run '{baseline_id}' not found")

    from eval.report import RunComparison
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
    """Return the diff between two run snapshots."""
    try:
        snap_a = _manager.load_snapshot(run_id=run_id, results_dir=_RESULTS_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Snapshot not found for run '{run_id}'")

    try:
        snap_b = _manager.load_snapshot(run_id=other_id, results_dir=_RESULTS_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Snapshot not found for run '{other_id}'")

    diff = diff_snapshots(snap_a, snap_b)
    return {
        "run_id": run_id,
        "other_id": other_id,
        "changed_prompts": diff.changed_prompts,
        "changed_configs": diff.changed_configs,
        "is_identical": diff.is_identical,
    }


@router.get("/eval/run/{run_id}/result/{arch_id}/{case_id}/files")
async def get_result_files(run_id: str, arch_id: str, case_id: str) -> dict:
    """Return output file paths for a specific eval result."""
    summary_path = _RESULTS_DIR / f"run_{run_id}" / "summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    raw = json.loads(summary_path.read_text(encoding="utf-8"))
    for item in raw.get("results", []):
        if item["architecture_id"] == arch_id and item["test_case_id"] == case_id:
            files = item.get("output_files", [])
            existing = [f for f in files if Path(f).exists()]
            return {
                "architecture_id": arch_id,
                "test_case_id": case_id,
                "files": [
                    {"path": f, "name": Path(f).name, "size": Path(f).stat().st_size}
                    for f in existing
                ],
            }

    raise HTTPException(status_code=404, detail=f"Result not found for {arch_id}/{case_id}")
