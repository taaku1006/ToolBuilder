"""Eval harness runner.

Executes test cases against architecture configs and collects metrics.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Callable

from eval.models import ArchitectureConfig, EvalMetrics, EvalResult, TestCase
from services.agent_orchestrator import orchestrate

logger = logging.getLogger(__name__)


class EvalRunner:
    """Runs evaluation: architecture x test_case -> EvalResult."""

    def __init__(
        self,
        architectures: list[ArchitectureConfig],
        test_cases: list[TestCase],
        settings_factory: Callable,
    ) -> None:
        self.architectures = architectures
        self.test_cases = test_cases
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
            ):
                log_entry = {
                    "phase": entry.phase,
                    "action": entry.action,
                    "content": entry.content[:200],
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
                    except (json.JSONDecodeError, TypeError):
                        pass

        except Exception as exc:
            error = str(exc)

        end_ms = time.monotonic_ns() // 1_000_000
        total_duration = end_ms - start_ms

        success = generated_code is not None and error is None

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
                retry_count=retry_count,
                code_executes=success,
            ),
            agent_log=agent_log,
            generated_code=generated_code,
            error=error,
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

    def save_results(self, results: list[EvalResult], output_dir: Path) -> None:
        """Save evaluation results to JSON files."""
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
