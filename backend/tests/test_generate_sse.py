"""Integration tests for SSE streaming on POST /api/generate.

TDD: tests written FIRST, implementation follows.
Tests cover both SSE streaming (Accept: text/event-stream) and
backward-compatible JSON response (Accept: application/json).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.config import Settings


def _make_settings(reflection_enabled: bool = False) -> Settings:
    """Settings with reflection disabled for simple generate tests."""
    return Settings(
        openai_api_key="test-key-123",
        openai_model="gpt-4o",
        cors_origins="http://localhost:5173",
        reflection_enabled=reflection_enabled,
    )


def _phase_c_json(
    summary: str = "テスト処理",
    python_code: str = "print('hello')",
    steps: list[str] | None = None,
    tips: str = "注意なし",
) -> str:
    return json.dumps(
        {
            "summary": summary,
            "python_code": python_code,
            "steps": steps or ["step1"],
            "tips": tips,
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# AgentLogEntry schema
# ---------------------------------------------------------------------------


class TestAgentLogEntrySchema:
    """AgentLogEntry pydantic model must have the required fields."""

    def test_fields_present(self) -> None:
        from schemas.generate import AgentLogEntry

        entry = AgentLogEntry(
            phase="C",
            action="complete",
            content="{}",
            timestamp="2024-01-01T00:00:00",
        )
        assert entry.phase == "C"
        assert entry.action == "complete"
        assert entry.content == "{}"
        assert entry.timestamp == "2024-01-01T00:00:00"

    def test_serializable_to_dict(self) -> None:
        from schemas.generate import AgentLogEntry

        entry = AgentLogEntry(
            phase="A",
            action="start",
            content="探索開始",
            timestamp="2024-01-01T00:00:00",
        )
        d = entry.model_dump()
        assert d["phase"] == "A"
        assert d["action"] == "start"


# ---------------------------------------------------------------------------
# GenerateResponse schema update
# ---------------------------------------------------------------------------


class TestGenerateResponseSchemaUpdate:
    """GenerateResponse must include agent_log and reflection_steps."""

    def test_agent_log_defaults_empty(self) -> None:
        from schemas.generate import GenerateResponse

        resp = GenerateResponse(
            id="abc",
            summary="s",
            python_code="c",
            steps=["s1"],
            tips="t",
        )
        assert resp.agent_log == []
        assert resp.reflection_steps == 0

    def test_agent_log_with_entries(self) -> None:
        from schemas.generate import AgentLogEntry, GenerateResponse

        entry = AgentLogEntry(
            phase="C",
            action="complete",
            content="{}",
            timestamp="2024-01-01T00:00:00",
        )
        resp = GenerateResponse(
            id="abc",
            summary="s",
            python_code="c",
            steps=["s1"],
            tips="t",
            agent_log=[entry],
            reflection_steps=1,
        )
        assert len(resp.agent_log) == 1
        assert resp.reflection_steps == 1


# ---------------------------------------------------------------------------
# POST /api/generate — JSON mode (backward compat)
# ---------------------------------------------------------------------------


class TestGenerateJsonMode:
    """Backward-compatible JSON response when Accept is application/json."""

    def _make_client(self, settings: Settings) -> TestClient:
        from core.deps import get_settings
        from main import app

        app.dependency_overrides[get_settings] = lambda: settings
        client = TestClient(app)
        return client

    def test_json_mode_returns_200(self) -> None:
        settings = _make_settings(reflection_enabled=False)
        client = self._make_client(settings)

        with patch("services.openai_client.OpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance
            mock_choice = MagicMock()
            mock_choice.message.content = _phase_c_json()
            mock_instance.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice]
            )

            response = client.post(
                "/api/generate",
                json={"task": "集計する"},
                headers={"Accept": "application/json"},
            )

        from main import app

        app.dependency_overrides.clear()
        assert response.status_code == 200

    def test_json_mode_response_has_required_fields(self) -> None:
        settings = _make_settings(reflection_enabled=False)
        client = self._make_client(settings)

        with patch("services.openai_client.OpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance
            mock_choice = MagicMock()
            mock_choice.message.content = _phase_c_json(summary="テスト集計")
            mock_instance.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice]
            )

            response = client.post(
                "/api/generate",
                json={"task": "集計する"},
                headers={"Accept": "application/json"},
            )

        from main import app

        app.dependency_overrides.clear()
        data = response.json()
        assert "id" in data
        assert "summary" in data
        assert "python_code" in data
        assert "steps" in data
        assert "tips" in data
        assert "agent_log" in data

    def test_json_mode_default_no_accept_header(self) -> None:
        """No Accept header defaults to JSON response (200, has id field)."""
        settings = _make_settings(reflection_enabled=False)
        client = self._make_client(settings)

        with patch("services.openai_client.OpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance
            mock_choice = MagicMock()
            mock_choice.message.content = _phase_c_json()
            mock_instance.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice]
            )

            response = client.post(
                "/api/generate",
                json={"task": "集計する"},
            )

        from main import app

        app.dependency_overrides.clear()
        assert response.status_code == 200
        assert "id" in response.json()


# ---------------------------------------------------------------------------
# POST /api/generate — SSE streaming mode
# ---------------------------------------------------------------------------


class TestGenerateSseMode:
    """SSE streaming response when Accept is text/event-stream."""

    def _make_client(self, settings: Settings) -> TestClient:
        from core.deps import get_settings
        from main import app

        app.dependency_overrides[get_settings] = lambda: settings
        client = TestClient(app)
        return client

    def test_sse_mode_returns_200(self) -> None:
        settings = _make_settings(reflection_enabled=False)
        client = self._make_client(settings)

        with patch("services.openai_client.OpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance
            mock_choice = MagicMock()
            mock_choice.message.content = _phase_c_json()
            mock_instance.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice]
            )

            response = client.post(
                "/api/generate",
                json={"task": "集計する"},
                headers={"Accept": "text/event-stream"},
            )

        from main import app

        app.dependency_overrides.clear()
        assert response.status_code == 200

    def test_sse_mode_content_type(self) -> None:
        """SSE response must have text/event-stream content type."""
        settings = _make_settings(reflection_enabled=False)
        client = self._make_client(settings)

        with patch("services.openai_client.OpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance
            mock_choice = MagicMock()
            mock_choice.message.content = _phase_c_json()
            mock_instance.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice]
            )

            response = client.post(
                "/api/generate",
                json={"task": "集計する"},
                headers={"Accept": "text/event-stream"},
            )

        from main import app

        app.dependency_overrides.clear()
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_sse_events_are_parseable(self) -> None:
        """Each SSE event data line must be valid JSON."""
        settings = _make_settings(reflection_enabled=False)
        client = self._make_client(settings)

        with patch("services.openai_client.OpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance
            mock_choice = MagicMock()
            mock_choice.message.content = _phase_c_json()
            mock_instance.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice]
            )

            response = client.post(
                "/api/generate",
                json={"task": "集計する"},
                headers={"Accept": "text/event-stream"},
            )

        from main import app

        app.dependency_overrides.clear()

        body = response.text
        data_lines = [
            line[len("data: "):].strip()
            for line in body.splitlines()
            if line.startswith("data: ")
        ]

        assert len(data_lines) >= 1
        for line in data_lines:
            parsed = json.loads(line)  # must not raise
            assert isinstance(parsed, dict)

    def test_sse_final_event_has_python_code(self) -> None:
        """The last SSE data event must contain python_code."""
        settings = _make_settings(reflection_enabled=False)
        client = self._make_client(settings)

        expected_code = "print('sse test code')"

        with patch("services.openai_client.OpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance
            mock_choice = MagicMock()
            mock_choice.message.content = _phase_c_json(python_code=expected_code)
            mock_instance.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice]
            )

            response = client.post(
                "/api/generate",
                json={"task": "集計する"},
                headers={"Accept": "text/event-stream"},
            )

        from main import app

        app.dependency_overrides.clear()

        body = response.text
        data_lines = [
            line[len("data: "):].strip()
            for line in body.splitlines()
            if line.startswith("data: ")
        ]

        last = json.loads(data_lines[-1])
        assert "python_code" in last
        assert last["python_code"] == expected_code

    def test_sse_events_have_phase_field(self) -> None:
        """Each SSE data event must have a phase field."""
        settings = _make_settings(reflection_enabled=False)
        client = self._make_client(settings)

        with patch("services.openai_client.OpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance
            mock_choice = MagicMock()
            mock_choice.message.content = _phase_c_json()
            mock_instance.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice]
            )

            response = client.post(
                "/api/generate",
                json={"task": "集計する"},
                headers={"Accept": "text/event-stream"},
            )

        from main import app

        app.dependency_overrides.clear()

        body = response.text
        data_lines = [
            line[len("data: "):].strip()
            for line in body.splitlines()
            if line.startswith("data: ")
        ]

        for line in data_lines:
            parsed = json.loads(line)
            assert "phase" in parsed, f"Missing 'phase' in: {parsed}"
