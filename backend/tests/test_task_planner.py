"""Tests for the task decomposition planner (Phase P)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from services.task_planner import (
    DecompositionResult,
    PlanResult,
    SubTask,
    SubTaskResult,
    run_planner,
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


class TestSubTaskResult:
    def test_frozen(self):
        sr = SubTaskResult(subtask_id=1, code="x", stdout="ok", success=True, output_files=(), debug_retries=0)
        with pytest.raises(AttributeError):
            sr.success = False  # type: ignore[misc]


class TestDecompositionResult:
    def test_success(self):
        dr = DecompositionResult(
            subtask_results=(), final_code="code", success=True,
            total_subtasks=2, failed_subtask_id=None,
        )
        assert dr.success is True
        assert dr.failed_subtask_id is None

    def test_failure(self):
        dr = DecompositionResult(
            subtask_results=(), final_code="", success=False,
            total_subtasks=3, failed_subtask_id=2,
        )
        assert dr.success is False
        assert dr.failed_subtask_id == 2


# ---------------------------------------------------------------------------
# run_planner tests
# ---------------------------------------------------------------------------


class TestRunPlanner:
    @pytest.fixture()
    def mock_client(self):
        client = MagicMock()
        return client

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
            openai_client=mock_client,
            task="complex task",
            exploration_result="cols: A, B",
            reflection_result="{}",
            file_context="file info",
        )

        assert result.decompose is True
        assert len(result.subtasks) == 2
        assert result.subtasks[0].title == "Step 1"
        assert result.subtasks[1].depends_on == (1,)

    @pytest.mark.asyncio
    async def test_decompose_false(self, mock_client):
        mock_client.generate_code.return_value = json.dumps({
            "decompose": False,
            "reasoning": "simple aggregation",
            "subtasks": [
                {"id": 1, "title": "Full task", "description": "aggregate", "depends_on": [], "expected_output": "out.xlsx"},
            ],
        })

        result = await run_planner(
            openai_client=mock_client,
            task="simple task",
            exploration_result="",
            reflection_result="{}",
            file_context=None,
        )

        assert result.decompose is False
        assert len(result.subtasks) == 1

    @pytest.mark.asyncio
    async def test_max_subtasks_enforced(self, mock_client):
        mock_client.generate_code.return_value = json.dumps({
            "decompose": True,
            "reasoning": "many steps",
            "subtasks": [
                {"id": i, "title": f"Step {i}", "description": f"do {i}", "depends_on": [], "expected_output": f"{i}.xlsx"}
                for i in range(1, 11)
            ],
        })

        result = await run_planner(
            openai_client=mock_client,
            task="big task",
            exploration_result="",
            reflection_result="{}",
            file_context=None,
            max_subtasks=3,
        )

        assert len(result.subtasks) == 3

    @pytest.mark.asyncio
    async def test_invalid_json_fallback(self, mock_client):
        mock_client.generate_code.return_value = "not valid json"

        result = await run_planner(
            openai_client=mock_client,
            task="task",
            exploration_result="",
            reflection_result="{}",
            file_context=None,
        )

        assert result.decompose is False
        assert len(result.subtasks) == 1
        assert "fallback" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_empty_subtasks_fallback(self, mock_client):
        mock_client.generate_code.return_value = json.dumps({
            "decompose": True,
            "reasoning": "no subtasks given",
            "subtasks": [],
        })

        result = await run_planner(
            openai_client=mock_client,
            task="task",
            exploration_result="",
            reflection_result="{}",
            file_context=None,
        )

        assert result.decompose is False
        assert len(result.subtasks) == 1
