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


async def generate_complex(
    state: PipelineState,
    openai_client: OpenAIClient,
    settings=None,
) -> AsyncGenerator[AgentLogEntry, None]:
    """Step-by-step generation with intermediate verification (Inner Loop 1)."""
    steps = state.strategy.steps or []
    if not steps:
        # Fallback to standard if no steps defined
        result = await generate_standard(state, openai_client, settings)
        state.generation_result = result
        yield AgentLogEntry(
            phase="G", action="complete",
            content="コード生成完了 (complex fallback to standard)",
            timestamp=_now_iso(),
        )
        return

    accumulated_code_parts: list[str] = []
    step_max_retries = 3

    for step in steps:
        step_succeeded = False
        for attempt in range(step_max_retries):
            yield AgentLogEntry(
                phase=f"G.{step.id}", action="start",
                content=f"Step {step.id}: {step.action}",
                timestamp=_now_iso(),
            )

            # Generate step code
            step_code = await _generate_step(
                state=state,
                step=step,
                prior_code="\n".join(accumulated_code_parts),
                openai_client=openai_client,
                settings=settings,
                recovery_hints="" if attempt == 0 else f"前回の試行でエラー: attempt {attempt}",
            )

            # Execute full code (prior + this step)
            full_code = "\n".join(accumulated_code_parts + [step_code])
            exec_result = execute_code(
                full_code,
                file_id=state.file_id,
            )

            # Verify step
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
