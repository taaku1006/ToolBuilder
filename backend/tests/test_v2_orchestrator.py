"""Tests for pipeline/v2/orchestrator.py — integration test with mocks."""

import json
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
import pytest_asyncio


@pytest.fixture
def mock_settings():
    from core.config import Settings
    return Settings(
        openai_api_key="sk-test-fake",
        openai_model="gpt-4o",
        langfuse_enabled=False,
        upload_dir="/tmp/test_uploads",
        output_dir="/tmp/test_outputs",
    )


def _make_mock_litellm_response(content: str):
    """Create a mock LiteLLM API response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    mock_response.usage = MagicMock(
        total_tokens=100, prompt_tokens=60, completion_tokens=40
    )
    return mock_response


class TestOrchestrateV2:
    @pytest.mark.asyncio
    async def test_basic_flow_emits_expected_phases(self, mock_settings):
        """orchestrate_v2 should emit U, G, C phase entries."""
        strategy_json = json.dumps({
            "complexity": "simple",
            "task_type": "aggregation",
            "estimated_difficulty": 0.3,
            "library": "pandas",
            "approach": "Use pandas to sum columns",
            "key_functions": ["sum"],
            "preprocessing": [],
            "risk_factors": [],
            "output_format": "xlsx",
        })

        code_response = '```python\nimport pandas as pd\nprint("done")\n```'

        with patch("infra.llm_client.litellm") as mock_litellm, \
             patch("pipeline.v2.stages.understand.parse_file") as mock_parse, \
             patch("pipeline.v2.stages.understand.load_prompt") as mock_load_prompt:

            # First call: strategy, Second call: code generation
            mock_litellm.completion.side_effect = [
                _make_mock_litellm_response(strategy_json),
                _make_mock_litellm_response(code_response),
            ]

            # Mock file parser
            mock_parse.return_value = []

            # Mock prompt loading
            mock_load_prompt.return_value = "{task}{file_context}{past_patterns}{past_gotchas}"

            from pipeline.v2 import orchestrate_v2
            entries = []
            async for entry in orchestrate_v2(
                task="合計を計算して",
                file_id=None,
                settings=mock_settings,
            ):
                entries.append(entry)

        phases = [e.phase for e in entries]

        # Must have U (understand), G (generate), L (learn), C (final payload)
        assert "U" in phases
        assert "G" in phases
        assert "L" in phases
        assert "C" in phases

        # Final entry must be phase=C, action=complete with JSON payload
        final = entries[-1]
        assert final.phase == "C"
        assert final.action == "complete"
        payload = json.loads(final.content)
        assert "python_code" in payload
        assert "total_tokens" in payload

    @pytest.mark.asyncio
    async def test_cancel_check_raises(self, mock_settings):
        """orchestrate_v2 should raise CancelledError when cancel_check returns True."""
        from pipeline.orchestrator_types import CancelledError

        with patch("infra.llm_client.litellm"):
            from pipeline.v2 import orchestrate_v2
            with pytest.raises(CancelledError):
                async for _ in orchestrate_v2(
                    task="test",
                    file_id=None,
                    settings=mock_settings,
                    cancel_check=lambda: True,
                ):
                    pass
