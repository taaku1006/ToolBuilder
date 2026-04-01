"""Tests for the task decomposition planner (Phase P)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from pipeline.task_planner import (
    PlanResult,
    SubTask,
    run_planner,
    run_replanner,
)


# ---------------------------------------------------------------------------
# Frozen dataclass tests
# ---------------------------------------------------------------------------


class TestSubTask:
    def test_frozen(self):
        st = SubTask(id=1, title="t", description="d", depends_on=(), expected_output="o.xlsx")
        with pytest.raises(AttributeError):
            st.title = "x"  # type: ignore[misc]

    def test_fields(self):
        st = SubTask(id=2, title="Step 2", description="desc", depends_on=(1,), expected_output="step2.xlsx")
        assert st.id == 2
        assert st.depends_on == (1,)

    def test_is_retry_default(self):
        st = SubTask(id=1, title="t", description="d", depends_on=(), expected_output="o")
        assert st.is_retry is False

    def test_is_retry_true(self):
        st = SubTask(id=1, title="t", description="d", depends_on=(), expected_output="o", is_retry=True)
        assert st.is_retry is True


class TestPlanResult:
    def test_frozen(self):
        pr = PlanResult(decompose=False, subtasks=(), reasoning="simple")
        with pytest.raises(AttributeError):
            pr.decompose = True  # type: ignore[misc]

    def test_decompose_true(self):
        st = SubTask(id=1, title="s", description="d", depends_on=(), expected_output="o")
        pr = PlanResult(decompose=True, subtasks=(st,), reasoning="complex")
        assert pr.decompose is True
        assert len(pr.subtasks) == 1


# ---------------------------------------------------------------------------
# run_planner tests
# ---------------------------------------------------------------------------


class TestRunPlanner:
    @pytest.fixture()
    def mock_client(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_decompose_true(self, mock_client):
        mock_client.generate_code.return_value = json.dumps({
            "decompose": True,
            "reasoning": "complex task",
            "subtasks": [
                {"id": 1, "title": "Step 1", "description": "Do A", "depends_on": [], "expected_output": "a.xlsx"},
                {"id": 2, "title": "Step 2", "description": "Do B", "depends_on": [1], "expected_output": "b.xlsx"},
            ],
        })

        result = await run_planner(
            openai_client=mock_client, task="complex task",
            exploration_result="cols: A, B", reflection_result="{}",
            file_context="file info",
        )

        assert result.decompose is True
        assert len(result.subtasks) == 2

    @pytest.mark.asyncio
    async def test_decompose_false(self, mock_client):
        mock_client.generate_code.return_value = json.dumps({
            "decompose": False, "reasoning": "simple",
            "subtasks": [{"id": 1, "title": "Full task", "description": "agg", "depends_on": [], "expected_output": "o.xlsx"}],
        })

        result = await run_planner(
            openai_client=mock_client, task="simple", exploration_result="",
            reflection_result="{}", file_context=None,
        )
        assert result.decompose is False

    @pytest.mark.asyncio
    async def test_max_subtasks_enforced(self, mock_client):
        mock_client.generate_code.return_value = json.dumps({
            "decompose": True, "reasoning": "many",
            "subtasks": [{"id": i, "title": f"S{i}", "description": f"d{i}", "depends_on": [], "expected_output": f"{i}.xlsx"} for i in range(1, 11)],
        })

        result = await run_planner(
            openai_client=mock_client, task="big", exploration_result="",
            reflection_result="{}", file_context=None, max_subtasks=3,
        )
        assert len(result.subtasks) == 3

    @pytest.mark.asyncio
    async def test_invalid_json_fallback(self, mock_client):
        mock_client.generate_code.return_value = "not valid json"

        result = await run_planner(
            openai_client=mock_client, task="task", exploration_result="",
            reflection_result="{}", file_context=None,
        )
        assert result.decompose is False
        assert "fallback" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_empty_subtasks_fallback(self, mock_client):
        mock_client.generate_code.return_value = json.dumps({
            "decompose": True, "reasoning": "no subtasks", "subtasks": [],
        })

        result = await run_planner(
            openai_client=mock_client, task="task", exploration_result="",
            reflection_result="{}", file_context=None,
        )
        assert result.decompose is False
        assert len(result.subtasks) == 1


# ---------------------------------------------------------------------------
# run_replanner tests
# ---------------------------------------------------------------------------


class TestRunReplanner:
    @pytest.fixture()
    def mock_client(self):
        return MagicMock()

    @pytest.fixture()
    def previous_plan(self):
        return PlanResult(
            decompose=True,
            subtasks=(
                SubTask(id=1, title="Data Agg", description="aggregate", depends_on=(), expected_output="agg.xlsx"),
                SubTask(id=2, title="Template Fill", description="fill", depends_on=(1,), expected_output="filled.xlsx"),
            ),
            reasoning="original plan",
        )

    @pytest.mark.asyncio
    async def test_replan_produces_retry_subtasks(self, mock_client, previous_plan):
        mock_client.generate_code.return_value = json.dumps({
            "subtasks": [
                {"id": 3, "title": "Fix Template", "description": "fix missing cells", "depends_on": [], "expected_output": "fixed.xlsx", "is_retry": True},
            ],
            "reasoning": "template fill was incomplete",
        })

        result = await run_replanner(
            openai_client=mock_client, task="task",
            previous_plan=previous_plan, eval_feedback="missing cells",
            comparison_score=0.45, missing_requirements="section 2 empty",
            exploration_result="", file_context=None,
        )

        assert result.decompose is True
        assert len(result.subtasks) == 1
        assert result.subtasks[0].is_retry is True

    @pytest.mark.asyncio
    async def test_replan_invalid_json_keeps_original(self, mock_client, previous_plan):
        mock_client.generate_code.return_value = "broken json"

        result = await run_replanner(
            openai_client=mock_client, task="task",
            previous_plan=previous_plan, eval_feedback="bad",
            comparison_score=0.3, missing_requirements="everything",
            exploration_result="", file_context=None,
        )

        assert result.subtasks == previous_plan.subtasks

    @pytest.mark.asyncio
    async def test_replan_empty_subtasks_keeps_original(self, mock_client, previous_plan):
        mock_client.generate_code.return_value = json.dumps({
            "subtasks": [], "reasoning": "nothing to fix",
        })

        result = await run_replanner(
            openai_client=mock_client, task="task",
            previous_plan=previous_plan, eval_feedback="",
            comparison_score=0.8, missing_requirements="",
            exploration_result="", file_context=None,
        )

        assert result.subtasks == previous_plan.subtasks
