"""Adaptive Pipeline v2 — Main orchestrator.

Wires the 4 stages together with outer-loop replan support.
Yields AgentLogEntry for SSE streaming and eval runner compatibility.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, Callable
from pathlib import Path

from core.config import Settings
from infra.openai_client import OpenAIClient
from pipeline.orchestrator_types import AgentLogEntry, CancelledError, _now_iso
from pipeline.v2.config import V2Settings
from pipeline.v2.models import MemoryContext, PipelineState
from pipeline.v2.phase_tracker import PhaseTracker
from pipeline.v2.stages.generate import generate
from pipeline.v2.stages.learn import LearnPhase
from pipeline.v2.stages.recovery import RecoveryManager
from pipeline.v2.stages.understand import ExcelAnalyzer, StrategyPhase
from pipeline.v2.stages.verify_fix import verify_fix_loop

logger = logging.getLogger(__name__)


async def orchestrate_v2(
    task: str,
    file_id: str | None,
    settings: Settings,
    expected_file_path: str | None = None,
    cancel_check: Callable | None = None,
    rubric: dict | None = None,
    v2_config: dict | None = None,
) -> AsyncGenerator[AgentLogEntry, None]:
    """Main v2 pipeline entry point.

    Signature matches agent_orchestrator.orchestrate() for eval runner
    compatibility. v2_config is passed from ArchitectureConfig.v2_config
    by the eval runner.
    """
    # Load v2-specific settings from architecture config if available
    v2_settings = V2Settings.from_dict(v2_config) if v2_config else V2Settings()

    # Apply stage model overrides to STAGE_CONFIGS so all stages pick them up.
    # If no per-stage overrides but a global model is set (via Settings.active_model),
    # apply it to ALL stages so the architecture's top-level model is respected.
    from pipeline.v2.config import STAGE_CONFIGS
    global_model = settings.active_model  # from arch.model → Settings.llm_model
    has_stage_overrides = "stage_models" in (v2_config or {})

    if has_stage_overrides:
        for stage, model in v2_settings.stage_models.items():
            if stage in STAGE_CONFIGS:
                STAGE_CONFIGS[stage]["model"] = model
    elif global_model:
        for stage in STAGE_CONFIGS:
            STAGE_CONFIGS[stage]["model"] = global_model

    openai_client = OpenAIClient(settings)

    tracker = PhaseTracker(["understand", "generate", "verify_fix", "learn"])

    # ── Stage 1: UNDERSTAND ──
    tracker.transition("understand")
    yield AgentLogEntry(
        phase="U", action="start",
        content="タスクとデータを分析中",
        timestamp=_now_iso(),
    )

    if cancel_check and cancel_check():
        raise CancelledError()

    # 1a. File analysis (LLM-free)
    file_context_text = None
    if file_id:
        try:
            analyzer = ExcelAnalyzer()
            file_path = _resolve_file_path(file_id, settings)
            file_context = analyzer.analyze(file_path)
        except Exception:
            logger.warning("ExcelAnalyzer failed, using empty context", exc_info=True)
            from pipeline.v2.models import FileContext
            file_context = FileContext()
    else:
        from pipeline.v2.models import FileContext
        file_context = FileContext()

    # 1b. Memory recall (LLM-free, skipped when memory_enabled=False)
    if v2_settings.memory_enabled:
        memory_context = _recall_memory(file_context)
    else:
        memory_context = MemoryContext()
    strategizer = StrategyPhase(openai_client, settings)
    classification, strategy = await strategizer.plan(task, file_context, memory_context)

    yield AgentLogEntry(
        phase="U", action="complete",
        content=f"複雑度: {classification.complexity}, 戦略: {strategy.approach}",
        timestamp=_now_iso(),
    )

    # Build pipeline state
    state = PipelineState(
        task=task,
        file_id=file_id,
        file_context=file_context,
        classification=classification,
        strategy=strategy,
        memory_context=memory_context,
        max_replan=v2_settings.max_replan,
        expected_file_path=expected_file_path,
        rubric=rubric,
    )

    # ── Outer Loop (replan) ──
    while state.replan_count <= state.max_replan:
        if cancel_check and cancel_check():
            raise CancelledError()

        # ── Stage 2: GENERATE ──
        tracker.transition("generate")
        yield AgentLogEntry(
            phase="G", action="start",
            content=f"コード生成中 ({classification.complexity} モード)",
            timestamp=_now_iso(),
        )

        async for entry in generate(state, openai_client, settings):
            yield entry

        if state.generation_result and not state.generation_result.success:
            if state.generation_result.replan_needed and state.replan_count < state.max_replan:
                state.replan_count += 1
                yield AgentLogEntry(
                    phase="G", action="replan",
                    content=f"戦略変更 ({state.replan_count}/{state.max_replan})",
                    timestamp=_now_iso(),
                )
                classification, strategy = await strategizer.replan(
                    task, file_context, memory_context,
                    previous_strategy=state.strategy,
                    failure_info=state.attempt_history,
                )
                state.classification = classification
                state.strategy = strategy
                continue
            break

        if not state.generation_result or not state.generation_result.code:
            break

        # ── Stage 3: VERIFY-FIX ──
        if expected_file_path:
            tracker.transition("verify_fix")
            recovery = RecoveryManager()

            async for entry in verify_fix_loop(
                code=state.generation_result.code,
                state=state,
                recovery=recovery,
                v2_settings=v2_settings,
                openai_client=openai_client,
                settings=settings,
            ):
                yield entry

            result = state.verify_fix_result
            if result and result.replan_needed and state.replan_count < state.max_replan:
                state.replan_count += 1
                yield AgentLogEntry(
                    phase="VF", action="replan",
                    content=f"戦略変更 ({state.replan_count}/{state.max_replan})",
                    timestamp=_now_iso(),
                )
                classification, strategy = await strategizer.replan(
                    task, file_context, memory_context,
                    previous_strategy=state.strategy,
                    failure_info=recovery.attempts,
                )
                state.classification = classification
                state.strategy = strategy
                continue

        break  # Success or escalate

    # ── Stage 4: LEARN ──
    tracker.transition("learn")
    if v2_settings.memory_enabled:
        LearnPhase(_memory_data_dir()).learn(state)
    yield AgentLogEntry(
        phase="L", action="complete",
        content="学習完了",
        timestamp=_now_iso(),
    )

    # ── Final result payload ──
    # Must use phase="C", action="complete" for eval/runner.py compatibility
    final_code = ""
    if state.verify_fix_result and state.verify_fix_result.best_code:
        final_code = state.verify_fix_result.best_code
    elif state.generation_result and state.generation_result.code:
        final_code = state.generation_result.code

    payload = {
        "python_code": final_code,
        "summary": state.generation_result.summary if state.generation_result else "",
        "steps": state.generation_result.steps if state.generation_result else [],
        "tips": f"Adaptive Pipeline v2 ({state.classification.complexity})",
        "debug_retries": len(state.attempt_history),
        "eval_debug_retries": 0,
        "eval_final_score": (
            state.verify_fix_result.best_score if state.verify_fix_result else None
        ),
        "llm_eval_retries": 0,
        "llm_eval_final_score": None,
        "total_tokens": openai_client.total_tokens,
        "prompt_tokens": openai_client.prompt_tokens,
        "completion_tokens": openai_client.completion_tokens,
        "api_calls": openai_client.api_calls,
        "phase_tokens": {},
    }

    yield AgentLogEntry(
        phase="C", action="complete",
        content=json.dumps(payload, ensure_ascii=False),
        timestamp=_now_iso(),
    )


def _resolve_file_path(file_id: str, settings: Settings) -> str:
    """Resolve a file_id to an actual file path."""
    import os
    upload_dir = settings.upload_dir
    for entry in os.listdir(upload_dir):
        if entry.startswith(file_id):
            return os.path.join(upload_dir, entry)
    # Fallback: treat file_id as direct path
    return os.path.join(upload_dir, file_id)


def _memory_data_dir() -> Path:
    """Return the default memory data directory."""
    return Path(__file__).resolve().parents[2] / "memory" / "data"


def _recall_memory(file_context) -> MemoryContext:
    """Recall past patterns, gotchas, and strategy stats from file-based memory."""
    from memory.search import search_gotchas, search_patterns
    from memory.store import MemoryStore

    data_dir = _memory_data_dir()
    if not data_dir.exists():
        return MemoryContext()

    store = MemoryStore(data_dir)
    feature_keys = file_context.get_feature_keys()
    patterns = search_patterns(data_dir, file_features=feature_keys)
    gotchas = search_gotchas(data_dir, file_features=feature_keys)
    strategy_stats = store.get_strategy_stats()

    # Merge insights into gotchas so they appear in checklist and prompts
    for insight in store.load_insights():
        gotchas.append({
            "_key": insight.get("pattern", ""),
            "detection": insight.get("trigger", ""),
            "fix": insight.get("prevention", ""),
            "confidence": insight.get("confidence", 0.5),
        })

    return MemoryContext(patterns=patterns, gotchas=gotchas, strategy_stats=strategy_stats)
