"""Tests for the LLM evaluation agent."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from evaluation.eval_agent import EvalAgentResult, evaluate_output


class TestEvalAgentResult:
    def test_frozen(self):
        r = EvalAgentResult(
            semantic_correctness=8.0, data_integrity=7.0,
            completeness=9.0, overall=8.0, reasoning="good",
        )
        with pytest.raises(AttributeError):
            r.overall = 5.0  # type: ignore[misc]

    def test_fields(self):
        r = EvalAgentResult(
            semantic_correctness=6.0, data_integrity=7.5,
            completeness=8.0, overall=7.2, reasoning="ok",
        )
        assert r.semantic_correctness == 6.0
        assert r.reasoning == "ok"


class TestEvaluateOutput:
    @pytest.fixture()
    def mock_settings(self):
        settings = MagicMock()
        settings.openai_api_key = "test-key"
        settings.openai_model = "gpt-4o"
        settings.langfuse_enabled = False
        return settings

    def test_successful_evaluation(self, mock_settings, tmp_path):
        """LLM returns valid JSON -> EvalAgentResult."""
        import pandas as pd

        # Create test Excel files
        expected = tmp_path / "expected.xlsx"
        actual = tmp_path / "actual.xlsx"
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        df.to_excel(str(expected), index=False)
        df.to_excel(str(actual), index=False)

        llm_response = json.dumps({
            "semantic_correctness": 9.0,
            "data_integrity": 8.5,
            "completeness": 10.0,
            "overall": 9.2,
            "reasoning": "Output matches expected perfectly.",
        })

        with patch("evaluation.eval_agent.OpenAIClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.generate_code.return_value = llm_response
            mock_cls.return_value = mock_client

            result = evaluate_output(
                task="test task",
                actual_path=str(actual),
                expected_path=str(expected),
                settings=mock_settings,
            )

        assert result is not None
        assert result.overall == 9.2
        assert result.semantic_correctness == 9.0
        assert result.completeness == 10.0
        assert "perfectly" in result.reasoning

    def test_invalid_json_returns_none(self, mock_settings, tmp_path):
        """LLM returns invalid JSON -> None."""
        import pandas as pd

        expected = tmp_path / "expected.xlsx"
        actual = tmp_path / "actual.xlsx"
        df = pd.DataFrame({"A": [1]})
        df.to_excel(str(expected), index=False)
        df.to_excel(str(actual), index=False)

        with patch("evaluation.eval_agent.OpenAIClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.generate_code.return_value = "not valid json"
            mock_cls.return_value = mock_client

            result = evaluate_output(
                task="task", actual_path=str(actual),
                expected_path=str(expected), settings=mock_settings,
            )

        assert result is None

    def test_missing_field_returns_none(self, mock_settings, tmp_path):
        """LLM returns JSON missing required fields -> None."""
        import pandas as pd

        expected = tmp_path / "expected.xlsx"
        actual = tmp_path / "actual.xlsx"
        df = pd.DataFrame({"A": [1]})
        df.to_excel(str(expected), index=False)
        df.to_excel(str(actual), index=False)

        llm_response = json.dumps({
            "semantic_correctness": 8.0,
            # missing data_integrity, completeness, overall
        })

        with patch("evaluation.eval_agent.OpenAIClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.generate_code.return_value = llm_response
            mock_cls.return_value = mock_client

            result = evaluate_output(
                task="task", actual_path=str(actual),
                expected_path=str(expected), settings=mock_settings,
            )

        assert result is None

    def test_nonexistent_file_returns_none(self, mock_settings):
        """File not found -> None."""
        result = evaluate_output(
            task="task",
            actual_path="/nonexistent.xlsx",
            expected_path="/also_nonexistent.xlsx",
            settings=mock_settings,
        )
        assert result is None

    def test_api_error_returns_none(self, mock_settings, tmp_path):
        """OpenAI API error -> None."""
        import pandas as pd

        expected = tmp_path / "expected.xlsx"
        actual = tmp_path / "actual.xlsx"
        df = pd.DataFrame({"A": [1]})
        df.to_excel(str(expected), index=False)
        df.to_excel(str(actual), index=False)

        with patch("evaluation.eval_agent.OpenAIClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.generate_code.side_effect = RuntimeError("API error")
            mock_cls.return_value = mock_client

            result = evaluate_output(
                task="task", actual_path=str(actual),
                expected_path=str(expected), settings=mock_settings,
            )

        assert result is None
