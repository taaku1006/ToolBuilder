"""Phase P: Task decomposition planner.

Analyzes a task and optionally breaks it into ordered sub-tasks.
Planner only — code generation is handled by Phase C (run_phase_c_subtask).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from services.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# ---------------------------------------------------------------------------
# Immutable data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubTask:
    """A single sub-task within a decomposition plan."""

    id: int
    title: str
    description: str
    depends_on: tuple[int, ...]
    expected_output: str
    is_retry: bool = False


@dataclass(frozen=True)
class PlanResult:
    """Result of the planner's analysis."""

    decompose: bool
    subtasks: tuple[SubTask, ...]
    reasoning: str


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------


def _load_prompt(name: str) -> str:
    """Load a prompt template, preferring Langfuse when available."""
    try:
        from services.reflection_engine import _settings_ref

        if _settings_ref is not None:
            from services.prompt_manager import get_prompt

            return get_prompt(name, _settings_ref)
    except Exception:
        pass
    prompt_path = _PROMPTS_DIR / f"{name}.txt"
    return prompt_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Planner: decides whether to decompose and produces sub-tasks
# ---------------------------------------------------------------------------


async def run_planner(
    openai_client: OpenAIClient,
    task: str,
    exploration_result: str,
    reflection_result: str,
    file_context: str | None,
    max_subtasks: int = 5,
) -> PlanResult:
    """Analyze a task and decide whether to decompose it.

    Returns a PlanResult. When decompose=False, subtasks contains
    a single entry representing the whole task.
    """
    template = _load_prompt("phase_p_plan")
    prompt = (
        template
        .replace("{task}", task)
        .replace("{exploration_result}", exploration_result)
        .replace("{reflection_result}", reflection_result)
        .replace("{file_context}", file_context or "")
        .replace("{max_subtasks}", str(max_subtasks))
    )

    response = openai_client.generate_code(
        system_prompt=prompt,
        user_prompt="タスクを分析し、分解要否をJSON形式で返してください。",
    )

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        logger.warning("Planner returned invalid JSON, falling back to no decomposition")
        return PlanResult(
            decompose=False,
            subtasks=(SubTask(
                id=1, title="Full task", description=task,
                depends_on=(), expected_output="output.xlsx",
            ),),
            reasoning="JSON parse error - fallback",
        )

    decompose = data.get("decompose", False)
    reasoning = data.get("reasoning", "")
    raw_subtasks = data.get("subtasks", [])

    raw_subtasks = raw_subtasks[:max_subtasks]

    subtasks = tuple(
        SubTask(
            id=st.get("id", i + 1),
            title=st.get("title", f"Step {i + 1}"),
            description=st.get("description", ""),
            depends_on=tuple(st.get("depends_on", [])),
            expected_output=st.get("expected_output", f"step_{i + 1}_output.xlsx"),
        )
        for i, st in enumerate(raw_subtasks)
    )

    if not subtasks:
        subtasks = (SubTask(
            id=1, title="Full task", description=task,
            depends_on=(), expected_output="output.xlsx",
        ),)
        decompose = False

    return PlanResult(decompose=decompose, subtasks=subtasks, reasoning=reasoning)


# ---------------------------------------------------------------------------
# Replanner: re-plan based on Phase F feedback
# ---------------------------------------------------------------------------


async def run_replanner(
    openai_client: OpenAIClient,
    task: str,
    previous_plan: PlanResult,
    eval_feedback: str,
    comparison_score: float,
    missing_requirements: str,
    exploration_result: str,
    file_context: str | None,
    max_subtasks: int = 5,
) -> PlanResult:
    """Re-plan based on Phase F quality feedback.

    Takes the previous plan and evaluation feedback, produces a new plan
    targeting only the failed/missing parts.
    """
    template = _load_prompt("phase_p_replan")

    previous_plan_str = json.dumps(
        [{"id": st.id, "title": st.title, "description": st.description}
         for st in previous_plan.subtasks],
        ensure_ascii=False,
    )

    prompt = (
        template
        .replace("{task}", task)
        .replace("{previous_plan}", previous_plan_str)
        .replace("{eval_feedback}", eval_feedback)
        .replace("{comparison_score}", f"{comparison_score:.2%}")
        .replace("{missing_requirements}", missing_requirements)
        .replace("{exploration_result}", exploration_result)
        .replace("{file_context}", file_context or "")
    )

    response = openai_client.generate_code(
        system_prompt=prompt,
        user_prompt="フィードバックを踏まえて再計画してください。",
    )

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        logger.warning("Replanner returned invalid JSON")
        return PlanResult(
            decompose=True,
            subtasks=previous_plan.subtasks,
            reasoning="Replan JSON parse error - keeping original plan",
        )

    raw_subtasks = data.get("subtasks", [])[:max_subtasks]
    reasoning = data.get("reasoning", "")

    subtasks = tuple(
        SubTask(
            id=st.get("id", i + 1),
            title=st.get("title", f"Retry Step {i + 1}"),
            description=st.get("description", ""),
            depends_on=tuple(st.get("depends_on", [])),
            expected_output=st.get("expected_output", f"retry_{i + 1}_output.xlsx"),
            is_retry=st.get("is_retry", True),
        )
        for i, st in enumerate(raw_subtasks)
    )

    if not subtasks:
        return PlanResult(
            decompose=True,
            subtasks=previous_plan.subtasks,
            reasoning="No subtasks in replan - keeping original plan",
        )

    return PlanResult(decompose=True, subtasks=subtasks, reasoning=reasoning)
