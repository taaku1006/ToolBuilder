"""Stage 3: VERIFY-FIX LOOP — Unified verification and repair.

Merges Phase D/F/G into a single adaptive loop:
- Verifier: 3-level check (execution → mechanical comparison → LLM semantic)
- RecoveryManager: decides fix / replan / escalate
- Fixer: LLM-based code repair with structured FixRequest
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import AsyncGenerator

from infra.openai_client import OpenAIClient
from infra.prompt_loader import load_prompt
from infra.sandbox import execute_code
from pipeline.orchestrator_types import AgentLogEntry, _now_iso
from pipeline.v2.config import STAGE_CONFIGS, V2Settings
from pipeline.v2.models import (
    Issue,
    PipelineState,
    VerificationResult,
    VerifyFixResult,
)
from pipeline.v2.stages.recovery import RecoveryManager

logger = logging.getLogger(__name__)

_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def _extract_code(raw: str) -> str:
    m = _CODE_FENCE_RE.search(raw)
    if m:
        return m.group(1).strip()
    return raw.strip()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def verify_fix_loop(
    code: str,
    state: PipelineState,
    recovery: RecoveryManager,
    v2_settings: V2Settings,
    openai_client: OpenAIClient,
    settings=None,
) -> AsyncGenerator[AgentLogEntry, None]:
    """Unified verify-fix loop (Inner Loop 2)."""

    best_code = code
    best_score = 0.0

    max_attempts = v2_settings.max_attempts.get(
        state.classification.complexity, 4
    )

    for attempt_num in range(max_attempts):
        yield AgentLogEntry(
            phase="VF", action="start",
            content=f"検証 (attempt {attempt_num + 1}/{max_attempts})",
            timestamp=_now_iso(),
        )

        # ── EXECUTE ──
        exec_result = execute_code(code, file_id=state.file_id)

        # ── VERIFY ──
        verification = await verify(
            exec_result=exec_result,
            expected_file_path=state.expected_file_path,
            task=state.task,
            v2_settings=v2_settings,
            openai_client=openai_client,
            settings=settings,
        )

        # Track best
        if verification.combined_score > best_score:
            best_score = verification.combined_score
            best_code = code

        if verification.passed:
            yield AgentLogEntry(
                phase="VF", action="complete",
                content=f"検証合格 (score: {verification.combined_score:.2f})",
                timestamp=_now_iso(),
            )
            state.verify_fix_result = VerifyFixResult(
                best_code=best_code,
                best_score=best_score,
                attempts=list(recovery.attempts),
                passed=True,
                replan_needed=False,
            )
            return

        # ── RECOVERY CHECK ──
        recovery.record_attempt(
            code=code,
            code_hash=hashlib.md5(code.encode()).hexdigest(),
            approach=state.strategy.approach,
            error_category=_classify_error(verification.execution_error),
            error_message=verification.execution_error,
            quality_score=verification.combined_score,
        )

        decision = recovery.analyze(verification, state.strategy)

        if decision.action == "fix" and decision.fix_request:
            yield AgentLogEntry(
                phase="VF", action="fix",
                content=f"修正 (attempt {attempt_num + 1})",
                timestamp=_now_iso(),
            )
            code = await fix(
                code=code,
                fix_request=decision.fix_request,
                state=state,
                openai_client=openai_client,
                settings=settings,
            )

        elif decision.action == "replan":
            yield AgentLogEntry(
                phase="VF", action="replan",
                content=f"戦略変更: {decision.replan_reason}",
                timestamp=_now_iso(),
            )
            state.verify_fix_result = VerifyFixResult(
                best_code=best_code,
                best_score=best_score,
                attempts=list(recovery.attempts),
                passed=False,
                replan_needed=True,
            )
            return

        else:  # escalate
            yield AgentLogEntry(
                phase="VF", action="escalate",
                content="品質改善が停滞。タスク記述の見直しを推奨。",
                timestamp=_now_iso(),
            )
            break

    # Loop exhausted
    state.verify_fix_result = VerifyFixResult(
        best_code=best_code,
        best_score=best_score,
        attempts=list(recovery.attempts),
        passed=False,
        replan_needed=False,
    )


# ---------------------------------------------------------------------------
# Verifier — 3-level unified check
# ---------------------------------------------------------------------------


async def verify(
    exec_result,
    expected_file_path: str | None,
    task: str,
    v2_settings: V2Settings,
    openai_client: OpenAIClient,
    settings=None,
) -> VerificationResult:
    """3-level verification: execution → mechanical → LLM semantic."""

    issues: list[Issue] = []

    # ── Level 1: Execution check (no LLM) ──
    if not exec_result.success:
        issues.append(Issue(
            level="execution",
            description=exec_result.stderr[:500],
            severity="critical",
        ))
        return VerificationResult(
            passed=False,
            execution_error=exec_result.stderr,
            quality_score=0.0,
            semantic_score=0.0,
            combined_score=0.0,
            issues=issues,
            fix_guidance="実行エラーを修正してください",
        )

    # ── Level 2: Mechanical comparison (no LLM) ──
    quality_score = 1.0
    if expected_file_path:
        try:
            from evaluation.structured_comparator import compare_excel_structured
            actual_file = _find_best_output(exec_result.output_files, expected_file_path)
            if actual_file:
                report = compare_excel_structured(actual_file, expected_file_path)
                quality_score = _compute_quality_score(report)
                if quality_score < v2_settings.quality_threshold:
                    issues.append(Issue(
                        level="quality",
                        description=report.summary_text()[:500],
                        severity="major",
                    ))
            else:
                quality_score = 0.0
                issues.append(Issue(
                    level="quality",
                    description="出力ファイルなし",
                    severity="critical",
                ))
        except Exception:
            logger.warning("Mechanical comparison failed", exc_info=True)

    # ── Level 3: LLM semantic eval (conditional) ──
    semantic_score = quality_score * 10
    if (expected_file_path
            and 0.5 < quality_score < v2_settings.quality_threshold):
        try:
            from evaluation.llm_judge import evaluate_code
            eval_result = evaluate_code(task, "", settings)
            if eval_result:
                semantic_score = eval_result.get("overall", quality_score * 10)
                if semantic_score < v2_settings.semantic_threshold:
                    issues.append(Issue(
                        level="semantic",
                        description=eval_result.get("comment", ""),
                        severity="major",
                    ))
        except Exception:
            logger.warning("LLM semantic eval failed", exc_info=True)

    combined = quality_score * 0.6 + (semantic_score / 10) * 0.4
    critical = sum(1 for i in issues if i.severity == "critical")
    passed = critical == 0 and combined >= v2_settings.pass_threshold

    return VerificationResult(
        passed=passed,
        execution_error=None,
        quality_score=quality_score,
        semantic_score=semantic_score,
        combined_score=combined,
        issues=issues,
        fix_guidance=_generate_fix_guidance(issues),
    )


# ---------------------------------------------------------------------------
# Fixer — LLM-based code repair
# ---------------------------------------------------------------------------


async def fix(
    code: str,
    fix_request,
    state: PipelineState,
    openai_client: OpenAIClient,
    settings=None,
) -> str:
    """Repair code based on structured FixRequest."""
    prompt_template = load_prompt("v2_fix", settings)
    prompt = prompt_template.format(
        code=code,
        issues="\n".join(f"- [{i.severity}] {i.description}" for i in fix_request.issues),
        fix_guidance=fix_request.fix_guidance,
        must_not_repeat="\n".join(fix_request.must_not_repeat[-3:]),
        previous_approaches="\n".join(fix_request.previous_approaches[-3:]),
        file_context=state.file_context.to_prompt(),
    )

    cfg = STAGE_CONFIGS["fix"]
    raw = openai_client.generate_code(
        "あなたはPythonコードのデバッグ専門家です。", prompt,
        model=cfg["model"],
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
    )
    return _extract_code(raw)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assess_risk(state: PipelineState, v2_settings: V2Settings) -> tuple[int, bool]:
    """Assess verification risk and return (adjusted_max_attempts, force_level3).

    Higher risk → more attempts + force LLM semantic check.
    Lower risk + simple → fewer attempts.
    """
    complexity = state.classification.complexity
    base = v2_settings.max_attempts.get(complexity, 4)
    risk_score = len(state.strategy.risk_factors)

    if complexity == "complex":
        risk_score += 2

    if risk_score >= 3:
        return (base + 2, True)
    if risk_score == 0 and complexity == "simple":
        return (max(1, base - 1), False)
    return (base, False)


def _find_best_output(output_files: list[str], expected_path: str) -> str | None:
    """Find the output file that best matches the expected file."""
    if not output_files:
        return None
    # Prefer .xlsx files
    xlsx_files = [f for f in output_files if f.endswith(".xlsx")]
    if xlsx_files:
        return xlsx_files[0]
    return output_files[0]


def _compute_quality_score(report) -> float:
    """Extract a 0-1 quality score from a StructuredCompareReport."""
    try:
        total = 0
        matched = 0
        for r in report.key_cell_results:
            total += 1
            if r.match:
                matched += 1
        for r in report.value_scan_results:
            total += 1
            if r.found:
                matched += 1
        if total == 0:
            return 1.0
        return matched / total
    except Exception:
        return 0.5


def _generate_fix_guidance(issues: list[Issue]) -> str:
    if not issues:
        return ""
    critical = [i for i in issues if i.severity == "critical"]
    if critical:
        return f"最優先で修正: {critical[0].description[:200]}"
    return f"改善が必要: {issues[0].description[:200]}"


def _classify_error(error: str | None) -> str | None:
    if not error:
        return None
    lower = error.lower()

    # Shell / pip commands in Python code
    if "pip install" in lower:
        return "pip_install_in_code"

    # Excel-specific
    if "mergedcell" in lower or "merged cell" in lower:
        return "merged_cells"
    if "invalidfileexception" in lower or "not a zip file" in lower or "openpyxl" in lower and "cannot" in lower:
        return "corrupt_excel"
    if "xlrd" in lower or ".xls" in lower and "not supported" in lower:
        return "legacy_xls"

    # CSV / text encoding
    if "unicodedecodeerror" in lower or "codec" in lower or "charmap" in lower:
        return "encoding_error"
    if "parserwarning" in lower or "tokenizing" in lower or "expected" in lower and "fields" in lower:
        return "csv_parse_error"

    # Data type / format
    if "datetimeindex" in lower or "to_datetime" in lower or "strftime" in lower:
        return "datetime_format"
    if "nan" in lower or "fillna" in lower or "cannot convert float nan" in lower:
        return "nan_handling"
    if "valueerror" in lower and ("convert" in lower or "cast" in lower):
        return "value_cast_error"

    # Standard Python errors
    if "import" in lower or "modulenotfounderror" in lower or "no module named" in lower:
        return "import_error"
    if "syntaxerror" in lower or "syntax" in lower:
        return "syntax_error"
    if "typeerror" in lower:
        return "type_error"
    if "keyerror" in lower:
        return "key_error"
    if "indexerror" in lower or "out of range" in lower:
        return "index_error"
    if "attributeerror" in lower:
        return "attribute_error"
    if "permissionerror" in lower or "permission denied" in lower:
        return "permission_error"
    if "filenotfounderror" in lower or "no such file" in lower:
        return "file_not_found"
    if "memoryerror" in lower or "killed" in lower:
        return "memory_error"
    if "timeout" in lower or "timed out" in lower:
        return "timeout"

    return "runtime_error"
