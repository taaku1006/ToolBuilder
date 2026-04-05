"""Stage 2: GENERATE — Code generation with complexity-adaptive strategy.

- SIMPLE: Single LLM call, no memory injection
- STANDARD: Single LLM call with memory + gotchas
- COMPLEX: Step-by-step generation with intermediate verification
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncGenerator

from infra.openai_client import OpenAIClient
from infra.prompt_loader import load_prompt
from infra.sandbox import execute_code
from pipeline.orchestrator_types import AgentLogEntry, _now_iso
from pipeline.v2.config import STAGE_CONFIGS
from pipeline.v2.models import (
    FileContext,
    GenerateResult,
    MemoryContext,
    PipelineState,
    StepVerification,
    Strategy,
    StrategyStep,
)

logger = logging.getLogger(__name__)

_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def _extract_code(raw: str) -> str:
    """Extract Python code from LLM response, stripping markdown fences."""
    m = _CODE_FENCE_RE.search(raw)
    if m:
        return m.group(1).strip()
    return raw.strip()


async def generate(state: PipelineState, openai_client: OpenAIClient, settings=None) -> AsyncGenerator[AgentLogEntry, None]:
    """Dispatch to the appropriate generation strategy."""
    match state.classification.complexity:
        case "simple":
            result = await generate_simple(state, openai_client, settings)
        case "complex":
            # complex yields entries for step progress
            async for entry in generate_complex(state, openai_client, settings):
                yield entry
            return
        case _:
            result = await generate_standard(state, openai_client, settings)

    state.generation_result = result
    yield AgentLogEntry(
        phase="G", action="complete",
        content=f"コード生成完了 ({state.classification.complexity})",
        timestamp=_now_iso(),
    )


async def generate_simple(
    state: PipelineState,
    openai_client: OpenAIClient,
    settings=None,
) -> GenerateResult:
    """Single LLM call, no memory injection."""
    prompt_template = load_prompt("v2_generate", settings)
    prompt = prompt_template.format(
        task=state.task,
        file_context=state.file_context.to_prompt(),
        strategy=state.strategy.to_prompt(),
        memory="",
        checklist=state.memory_context.to_checklist(),
        fix_request="",
    )

    cfg = STAGE_CONFIGS["generate"]
    raw = openai_client.generate_code(
        "あなたはPythonコード生成の専門家です。", prompt,
        model=cfg["model"],
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
    )

    return GenerateResult(code=_extract_code(raw), success=True)


async def generate_standard(
    state: PipelineState,
    openai_client: OpenAIClient,
    settings=None,
) -> GenerateResult:
    """Single LLM call with memory + gotchas injected."""
    prompt_template = load_prompt("v2_generate", settings)
    prompt = prompt_template.format(
        task=state.task,
        file_context=state.file_context.to_prompt(),
        strategy=state.strategy.to_prompt(),
        memory=state.memory_context.to_prompt(),
        checklist=state.memory_context.to_checklist(),
        fix_request="",
    )

    cfg = STAGE_CONFIGS["generate"]
    raw = openai_client.generate_code(
        "あなたはPythonコード生成の専門家です。", prompt,
        model=cfg["model"],
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
    )

    return GenerateResult(code=_extract_code(raw), success=True)


MAX_COMPLEX_STEPS = 4
STEP_TIMEOUT_HINT = "Keep the code concise. Do not exceed 200 lines for this step."


async def generate_complex(
    state: PipelineState,
    openai_client: OpenAIClient,
    settings=None,
) -> AsyncGenerator[AgentLogEntry, None]:
    """Step-by-step generation with intermediate verification (Inner Loop 1).

    Limits: max 4 steps, try/except per step, partial result on failure.
    """
    steps = state.strategy.steps or []
    if not steps:
        result = await generate_standard(state, openai_client, settings)
        state.generation_result = result
        yield AgentLogEntry(
            phase="G", action="complete",
            content="コード生成完了 (complex fallback to standard)",
            timestamp=_now_iso(),
        )
        return

    # Limit step count and ensure final step writes output
    if len(steps) > MAX_COMPLEX_STEPS:
        logger.warning(
            "COMPLEX: truncating %d steps to %d", len(steps), MAX_COMPLEX_STEPS
        )
        # Keep first N-1 steps + replace last with output step
        steps = list(steps[:MAX_COMPLEX_STEPS - 1])
        steps.append(StrategyStep(
            id=MAX_COMPLEX_STEPS,
            action="Combine all results and save to OUTPUT_DIR as Excel file with all required sheets",
            verify="print output file path and confirm file exists",
            expected_in_output=["OUTPUT_DIR", ".xlsx"],
        ))
        yield AgentLogEntry(
            phase="G", action="info",
            content=f"ステップ数を {MAX_COMPLEX_STEPS} に制限 (最終ステップ=Excel書き出し)",
            timestamp=_now_iso(),
        )
    else:
        # Even without truncation, ensure last step mentions output
        last = steps[-1]
        if "save" not in last.action.lower() and "output" not in last.action.lower() and "write" not in last.action.lower():
            steps = list(steps)
            steps.append(StrategyStep(
                id=len(steps) + 1,
                action="Save all results to OUTPUT_DIR as Excel file",
                verify="print output file path and confirm file exists",
                expected_in_output=["OUTPUT_DIR", ".xlsx"],
            ))

    accumulated_code_parts: list[str] = []
    step_max_retries = 2  # Reduced from 3 to limit total time

    for step in steps:
        step_succeeded = False
        for attempt in range(step_max_retries):
            yield AgentLogEntry(
                phase=f"G.{step.id}", action="start",
                content=f"Step {step.id}: {step.action}",
                timestamp=_now_iso(),
            )

            try:
                step_code = await _generate_step(
                    state=state,
                    step=step,
                    prior_code="\n".join(accumulated_code_parts),
                    openai_client=openai_client,
                    settings=settings,
                    recovery_hints=(
                        STEP_TIMEOUT_HINT if attempt == 0
                        else f"Previous attempt failed. {STEP_TIMEOUT_HINT}"
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "COMPLEX step %d generation failed: %s", step.id, exc
                )
                yield AgentLogEntry(
                    phase=f"G.{step.id}", action="error",
                    content=f"Step {step.id} LLM error: {str(exc)[:100]}",
                    timestamp=_now_iso(),
                )
                break  # Move to partial result fallback

            # Execute full code (prior + this step)
            full_code = "\n".join(accumulated_code_parts + [step_code])
            exec_result = execute_code(
                full_code,
                file_id=state.file_id,
            )

            verification = _verify_step(exec_result, step)

            if verification.passed:
                accumulated_code_parts.append(step_code)
                yield AgentLogEntry(
                    phase=f"G.{step.id}", action="complete",
                    content=f"Step {step.id} 完了: {step.action}",
                    timestamp=_now_iso(),
                )
                step_succeeded = True
                break
            else:
                yield AgentLogEntry(
                    phase=f"G.{step.id}", action="retry",
                    content=f"Step {step.id} リトライ: {verification.error[:100]}",
                    timestamp=_now_iso(),
                )

        if not step_succeeded:
            # Return partial result if we have some steps done
            if accumulated_code_parts:
                partial_code = "\n".join(accumulated_code_parts)
                logger.info(
                    "COMPLEX: returning partial result (%d/%d steps)",
                    len(accumulated_code_parts), len(steps),
                )
                state.generation_result = GenerateResult(
                    code=partial_code, success=True,
                    tips=f"Partial: {len(accumulated_code_parts)}/{len(steps)} steps completed",
                )
                yield AgentLogEntry(
                    phase="G", action="complete",
                    content=f"部分生成完了 ({len(accumulated_code_parts)}/{len(steps)} steps)",
                    timestamp=_now_iso(),
                )
                return

            state.generation_result = GenerateResult(success=False, replan_needed=True)
            yield AgentLogEntry(
                phase=f"G.{step.id}", action="error",
                content=f"Step {step.id} が解決できません",
                timestamp=_now_iso(),
            )
            return

    # All steps succeeded — combine
    final_code = "\n".join(accumulated_code_parts)
    state.generation_result = GenerateResult(code=final_code, success=True)
    yield AgentLogEntry(
        phase="G", action="complete",
        content="コード生成完了 (complex: 全ステップ成功)",
        timestamp=_now_iso(),
    )


async def _generate_step(
    state: PipelineState,
    step: StrategyStep,
    prior_code: str,
    openai_client: OpenAIClient,
    settings=None,
    recovery_hints: str = "",
) -> str:
    prompt_template = load_prompt("v2_generate_step", settings)
    prompt = prompt_template.format(
        task=state.task,
        step_id=step.id,
        step_action=step.action,
        step_verify=step.verify,
        file_context=state.file_context.to_prompt(),
        strategy=state.strategy.to_prompt(),
        prior_code=prior_code,
        recovery_hints=recovery_hints,
    )

    cfg = STAGE_CONFIGS["generate_step"]
    raw = openai_client.generate_code(
        "あなたはPythonコード生成の専門家です。", prompt,
        model=cfg["model"],
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
    )
    return _extract_code(raw)


def _verify_step(exec_result, step: StrategyStep) -> StepVerification:
    """Verify a single COMPLEX step — Python only, no LLM."""
    if not exec_result.success:
        return StepVerification(
            passed=False, error=exec_result.stderr, error_type="execution"
        )

    stdout = exec_result.stdout
    if not stdout.strip():
        return StepVerification(
            passed=False, error="検証出力なし", error_type="no_output"
        )

    error_keywords = ["Traceback", "Error", "Warning"]
    for kw in error_keywords:
        if kw in stdout and kw not in (step.expected_in_output or []):
            return StepVerification(
                passed=False,
                error=f"出力に {kw} を検出",
                error_type="suspicious_output",
            )

    return StepVerification(passed=True)
