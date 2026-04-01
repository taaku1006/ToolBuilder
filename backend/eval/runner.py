"""Eval harness runner.

Executes test cases against architecture configs and collects metrics.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from eval.models import ArchitectureConfig, EvalMetrics, EvalResult, TestCase
from pipeline.agent_orchestrator import CancelledError, orchestrate
from evaluation.eval_agent import evaluate_output
from evaluation.excel_comparator import compare_excel_files, find_best_output_match
from infra.sandbox import execute_code

if TYPE_CHECKING:
    from eval.versioning import RunSnapshot

logger = logging.getLogger(__name__)


def classify_error(error: str | None, agent_log: list[dict]) -> str:
    """Classify an error string into an actionable category."""
    if not error:
        # Check agent_log for Phase D failures
        for entry in agent_log:
            if entry.get("phase") == "D" and entry.get("action") == "error":
                return "runtime_error"
        return "none"

    if "JSONDecodeError" in error or "Expecting value" in error:
        return "json_parse"
    if "SyntaxError" in error:
        return "syntax_error"
    if "timeout" in error.lower() or "timed out" in error.lower():
        return "timeout"
    if "OpenAI" in error or "API error" in error:
        return "api_error"
    if "not found" in error.lower():
        return "file_not_found"
    if "Traceback" in error or "Error" in error:
        return "runtime_error"
    return "unknown"


class EvalRunner:
    """Runs evaluation: architecture x test_case -> EvalResult."""

    def __init__(
        self,
        architectures: list[ArchitectureConfig],
        test_cases: list[TestCase],
        settings_factory: Callable,
        cancel_check: Callable | None = None,
    ) -> None:
        self.architectures = architectures
        self.test_cases = test_cases
        self._cancel_check = cancel_check
        self._settings_factory = settings_factory

    def _prepare_file_id(self, case: TestCase, settings) -> str | None:
        """Copy test case file into upload_dir and return a file_id, or None.

        If case.file_path is set but the file does not exist, raises FileNotFoundError.
        """
        if not case.file_path:
            return None

        src = Path(case.file_path)
        if not src.exists():
            raise FileNotFoundError(f"Test case file not found: {case.file_path}")

        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_id = str(uuid.uuid4())
        dest = upload_dir / f"{file_id}_{src.name}"
        shutil.copy2(src, dest)

        return file_id

    async def run_single(
        self,
        arch: ArchitectureConfig,
        case: TestCase,
    ) -> EvalResult:
        """Run one (architecture, test_case) pair and return EvalResult."""
        overrides = arch.to_settings_overrides()
        settings = self._settings_factory(overrides)

        agent_log: list[dict] = []
        generated_code: str | None = None
        error: str | None = None
        retry_count = 0
        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        api_calls = 0
        phase_starts: dict[str, float] = {}
        phase_durations: dict[str, int] = {}
        phase_tokens: dict[str, int] = {}
        decomp_output_files: list[str] = []

        start_ms = time.monotonic_ns() // 1_000_000

        try:
            file_id = self._prepare_file_id(case, settings)
        except FileNotFoundError as exc:
            error = str(exc)
            return EvalResult(
                architecture_id=arch.id,
                test_case_id=case.id,
                model=arch.model,
                metrics=EvalMetrics(
                    success=False,
                    total_duration_ms=0,
                    phase_durations_ms={},
                    retry_count=0,
                    code_executes=False,
                    error_category=classify_error(error, []),
                ),
                agent_log=[],
                generated_code=None,
                error=error,
            )

        try:
            async for entry in orchestrate(
                task=case.task,
                file_id=file_id,
                settings=settings,
                expected_file_path=case.expected_file_path,
                cancel_check=self._cancel_check,
                rubric=case.rubric,
            ):
                # Keep full content for internal processing; truncate for log storage
                full_content = entry.content
                log_entry = {
                    "phase": entry.phase,
                    "action": entry.action,
                    "content": full_content[:200],
                    "timestamp": entry.timestamp,
                }
                agent_log.append(log_entry)

                # Track phase durations
                if entry.action == "start":
                    phase_starts[entry.phase] = time.monotonic_ns() // 1_000_000

                if entry.action in ("complete", "error") and entry.phase in phase_starts:
                    elapsed = (time.monotonic_ns() // 1_000_000) - phase_starts[entry.phase]
                    phase_durations[entry.phase] = elapsed

                # Count retries
                if entry.action == "retry":
                    retry_count += 1

                # Capture decomposition output files from Phase P complete
                if entry.phase == "P" and entry.action == "complete":
                    try:
                        p_payload = json.loads(entry.content)
                        decomp_output_files = p_payload.get("output_files", [])
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Extract generated code from Phase C complete
                if entry.phase == "C" and entry.action == "complete":
                    try:
                        payload = json.loads(entry.content)
                        generated_code = payload.get("python_code")
                        retry_count = max(retry_count, payload.get("debug_retries", 0))
                        total_tokens = payload.get("total_tokens", 0)
                        prompt_tokens = payload.get("prompt_tokens", 0)
                        completion_tokens = payload.get("completion_tokens", 0)
                        api_calls = payload.get("api_calls", 0)
                        phase_tokens = payload.get("phase_tokens", {})
                    except (json.JSONDecodeError, TypeError):
                        pass

        except CancelledError:
            error = "cancelled"
        except Exception as exc:
            error = str(exc)

        end_ms = time.monotonic_ns() // 1_000_000
        total_duration = end_ms - start_ms

        success = generated_code is not None and error is None

        # ----- Output quality comparison -----
        quality_score: float | None = None
        quality_details: dict | None = None
        actual_path: str | None = None
        output_files_for_compare: list[str] = []

        if (
            success
            and case.expected_file_path
            and Path(case.expected_file_path).exists()
        ):
            try:
                output_files_for_compare: list[str] = []

                if decomp_output_files:
                    # Task decomposition: use workspace output files directly
                    output_files_for_compare = [
                        f for f in decomp_output_files if Path(f).exists()
                    ]
                elif generated_code:
                    # Standard path: re-execute code to get output files
                    exec_result = await asyncio.to_thread(
                        execute_code,
                        generated_code,
                        file_id=file_id,
                        upload_dir=settings.upload_dir,
                        output_dir=settings.output_dir,
                        timeout=settings.exec_timeout,
                    )
                    if exec_result.success:
                        output_files_for_compare = exec_result.output_files

                if output_files_for_compare:
                    actual_path = find_best_output_match(
                        output_files_for_compare, case.expected_file_path,
                    )
                    if actual_path:
                        comparison = compare_excel_files(
                            actual_path, case.expected_file_path,
                        )
                        quality_score = comparison.overall_score
                        quality_details = {
                            "overall_score": comparison.overall_score,
                            "missing_sheets": list(comparison.missing_sheets),
                            "extra_sheets": list(comparison.extra_sheets),
                            "sheet_count": len(comparison.sheet_results),
                            "error": comparison.error,
                        }
            except Exception:
                logger.warning("Quality comparison failed", exc_info=True)

        # ----- LLM evaluation agent -----
        llm_eval_score: float | None = None
        llm_eval_details: dict | None = None

        if (
            success
            and case.expected_file_path
            and Path(case.expected_file_path).exists()
            and actual_path
        ):
            try:
                eval_result = await asyncio.to_thread(
                    evaluate_output,
                    task=case.task,
                    actual_path=actual_path,
                    expected_path=case.expected_file_path,
                    settings=settings,
                )
                if eval_result is not None:
                    llm_eval_score = eval_result.overall
                    llm_eval_details = {
                        "semantic_correctness": eval_result.semantic_correctness,
                        "data_integrity": eval_result.data_integrity,
                        "completeness": eval_result.completeness,
                        "overall": eval_result.overall,
                        "reasoning": eval_result.reasoning,
                    }
            except Exception:
                logger.warning("LLM eval agent failed", exc_info=True)

        # ----- Final success determination -----
        # Mechanical comparison (Phase F gate)
        mechanical_success = True
        if quality_score is not None:
            mechanical_success = quality_score >= settings.eval_debug_quality_threshold

        # LLM evaluation (Phase G gate)
        llm_eval_success = True
        if llm_eval_score is not None:
            llm_eval_success = llm_eval_score >= settings.llm_eval_score_threshold

        if success:
            success = mechanical_success and llm_eval_success

        return EvalResult(
            architecture_id=arch.id,
            test_case_id=case.id,
            model=arch.model,
            metrics=EvalMetrics(
                success=success,
                total_duration_ms=total_duration,
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                api_calls=api_calls,
                phase_durations_ms=phase_durations,
                phase_tokens=phase_tokens,
                retry_count=retry_count,
                code_executes=success,
                error_category=classify_error(error, agent_log),
                quality_score=quality_score,
                quality_details=quality_details,
                llm_eval_score=llm_eval_score,
                llm_eval_details=llm_eval_details,
            ),
            agent_log=agent_log,
            generated_code=generated_code,
            error=error,
            output_files=output_files_for_compare if output_files_for_compare else [],
        )

    async def run_all(self) -> list[EvalResult]:
        """Run all architecture x test_case combinations sequentially."""
        results: list[EvalResult] = []
        for arch in self.architectures:
            for case in self.test_cases:
                logger.info(
                    "Running eval",
                    extra={"architecture": arch.id, "test_case": case.id},
                )
                result = await self.run_single(arch, case)
                results.append(result)
        return results

    def save_results(
        self,
        results: list[EvalResult],
        output_dir: Path,
        snapshot: "RunSnapshot | None" = None,
    ) -> None:
        """Save evaluation results to JSON files.

        If *snapshot* is provided it is written to ``snapshot.json`` alongside
        ``summary.json``.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        for result in results:
            filename = f"{result.architecture_id}_{result.test_case_id}.json"
            filepath = output_dir / filename
            filepath.write_text(
                json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        summary = {
            "results": [r.to_dict() for r in results],
            "total_runs": len(results),
        }
        summary_path = output_dir / "summary.json"
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if snapshot is not None:
            snapshot_path = output_dir / "snapshot.json"
            snapshot_path.write_text(
                json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
