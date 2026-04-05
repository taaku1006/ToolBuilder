"""Tests for POST /api/generate endpoint.

TDD order: tests written FIRST, implementation follows.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Unit tests: prompt_builder
# ---------------------------------------------------------------------------


class TestBuildUserPrompt:
    """Unit tests for infra.prompt_builder.build_user_prompt."""

    def test_task_only(self) -> None:
        """Without file_context the prompt contains only the task section."""
        from infra.prompt_builder import build_user_prompt

        result = build_user_prompt("売上を集計する")

        assert "【タスク】" in result
        assert "売上を集計する" in result

    def test_with_file_context(self) -> None:
        """When file_context is given it is prepended before the task section."""
        from infra.prompt_builder import build_user_prompt

        result = build_user_prompt("集計する", file_context="A列: 日付, B列: 金額")

        assert "【対象ファイルの構造】" in result
        assert "A列: 日付, B列: 金額" in result
        assert "【タスク】" in result
        assert "集計する" in result
        # file_context section must come before task section
        assert result.index("【対象ファイルの構造】") < result.index("【タスク】")

    def test_file_context_none_excludes_structure_section(self) -> None:
        """None file_context must NOT include the structure section."""
        from infra.prompt_builder import build_user_prompt

        result = build_user_prompt("集計する", file_context=None)

        assert "【対象ファイルの構造】" not in result

    def test_empty_file_context_excludes_structure_section(self) -> None:
        """Empty string file_context must NOT include the structure section."""
        from infra.prompt_builder import build_user_prompt

        result = build_user_prompt("集計する", file_context="")

        assert "【対象ファイルの構造】" not in result

    def test_system_prompt_is_string(self) -> None:
        """SYSTEM_PROMPT must be a non-empty string."""
        from infra.prompt_builder import SYSTEM_PROMPT

        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 0

    def test_system_prompt_contains_json_instructions(self) -> None:
        """SYSTEM_PROMPT must instruct model to return JSON."""
        from infra.prompt_builder import SYSTEM_PROMPT

        assert "JSON" in SYSTEM_PROMPT
        assert "python_code" in SYSTEM_PROMPT
        assert "summary" in SYSTEM_PROMPT
        assert "steps" in SYSTEM_PROMPT
        assert "tips" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Integration tests: POST /api/generate
# ---------------------------------------------------------------------------


class TestGenerateEndpoint:
    """Integration tests for POST /api/generate."""

    def test_success_returns_200(self, test_client: TestClient) -> None:
        """Valid request returns HTTP 200."""
        response = test_client.post(
            "/api/generate",
            json={"task": "売上データを集計してください"},
        )
        assert response.status_code == 200

    def test_success_response_schema(self, test_client: TestClient) -> None:
        """Response body must conform to GenerateResponse schema."""
        response = test_client.post(
            "/api/generate",
            json={"task": "売上データを集計してください"},
        )
        data = response.json()

        assert "id" in data
        assert "summary" in data
        assert "python_code" in data
        assert "steps" in data
        assert "tips" in data

    def test_response_id_is_uuid(self, test_client: TestClient) -> None:
        """The id field must be a valid UUID string."""
        import re

        response = test_client.post(
            "/api/generate",
            json={"task": "集計する"},
        )
        data = response.json()
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        assert uuid_pattern.match(data["id"]), f"id '{data['id']}' is not a UUID"

    def test_response_contains_openai_content(
        self,
        test_client: TestClient,
        mock_openai_response: dict,
    ) -> None:
        """Response fields must match the mocked OpenAI output."""
        response = test_client.post(
            "/api/generate",
            json={"task": "売上データを集計してください"},
        )
        data = response.json()

        assert data["summary"] == mock_openai_response["summary"]
        assert data["python_code"] == mock_openai_response["python_code"]
        assert data["steps"] == mock_openai_response["steps"]
        assert data["tips"] == mock_openai_response["tips"]

    def test_steps_is_list(self, test_client: TestClient) -> None:
        """steps field must be a list."""
        response = test_client.post(
            "/api/generate",
            json={"task": "集計する"},
        )
        data = response.json()
        assert isinstance(data["steps"], list)

    def test_missing_task_returns_422(self, test_client: TestClient) -> None:
        """Request without task field returns HTTP 422 Unprocessable Entity."""
        response = test_client.post("/api/generate", json={})
        assert response.status_code == 422

    def test_empty_task_still_calls_openai(self, test_client: TestClient) -> None:
        """Empty string task is technically valid and calls OpenAI."""
        response = test_client.post("/api/generate", json={"task": ""})
        # Should not raise 422 – task field present
        assert response.status_code == 200

    def test_optional_file_id_accepted(self, test_client: TestClient) -> None:
        """file_id is optional and must be accepted."""
        response = test_client.post(
            "/api/generate",
            json={"task": "集計する", "file_id": "upload-123"},
        )
        assert response.status_code == 200

    def test_optional_skill_id_accepted(self, test_client: TestClient) -> None:
        """skill_id is optional and must be accepted."""
        response = test_client.post(
            "/api/generate",
            json={"task": "集計する", "skill_id": "skill-abc"},
        )
        assert response.status_code == 200

    def test_two_requests_have_different_ids(self, test_client: TestClient) -> None:
        """Each request generates a unique id."""
        r1 = test_client.post("/api/generate", json={"task": "タスク1"})
        r2 = test_client.post("/api/generate", json={"task": "タスク2"})
        assert r1.json()["id"] != r2.json()["id"]

    def test_invalid_json_body_returns_422(self, test_client: TestClient) -> None:
        """Malformed JSON body returns 422."""
        response = test_client.post(
            "/api/generate",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Integration tests: CORS headers
# ---------------------------------------------------------------------------


class TestCORS:
    """Smoke test that CORS middleware is configured."""

    def test_options_preflight_returns_200(self, test_client: TestClient) -> None:
        """OPTIONS preflight must return 200."""
        response = test_client.options(
            "/api/generate",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200

    def test_cors_header_present(self, test_client: TestClient) -> None:
        """POST response includes Access-Control-Allow-Origin header."""
        response = test_client.post(
            "/api/generate",
            json={"task": "集計する"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert "access-control-allow-origin" in response.headers


# ---------------------------------------------------------------------------
# Unit tests: OpenAI parse error handling
# ---------------------------------------------------------------------------


class TestGenerateEndpointErrorHandling:
    """Error path tests for the generate endpoint."""

    def test_openai_returns_invalid_json_causes_500(
        self,
        mock_settings,
        mock_openai_client: MagicMock,
    ) -> None:
        """When OpenAI returns non-JSON, endpoint returns HTTP 500."""
        mock_openai_client.completion.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not valid json at all"))]
        )

        from core.deps import get_settings
        from main import app

        app.dependency_overrides[get_settings] = lambda: mock_settings

        with TestClient(app) as client:
            response = client.post("/api/generate", json={"task": "集計する"})

        app.dependency_overrides.clear()

        assert response.status_code == 500

    def test_openai_returns_empty_string_causes_500(
        self,
        mock_settings,
        mock_openai_client: MagicMock,
    ) -> None:
        """When OpenAI returns empty string, endpoint returns HTTP 500."""
        mock_openai_client.completion.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=""))]
        )

        from core.deps import get_settings
        from main import app

        app.dependency_overrides[get_settings] = lambda: mock_settings

        with TestClient(app) as client:
            response = client.post("/api/generate", json={"task": "集計する"})

        app.dependency_overrides.clear()

        assert response.status_code == 500

    def test_openai_returns_json_missing_field_causes_500(
        self,
        mock_settings,
        mock_openai_client: MagicMock,
    ) -> None:
        """When OpenAI JSON is missing a required field, endpoint returns 500."""
        import json

        incomplete = json.dumps({"summary": "要約のみ"})  # missing python_code etc.
        mock_openai_client.completion.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=incomplete))]
        )

        from core.deps import get_settings
        from main import app

        app.dependency_overrides[get_settings] = lambda: mock_settings

        with TestClient(app) as client:
            response = client.post("/api/generate", json={"task": "集計する"})

        app.dependency_overrides.clear()

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# Unit tests: core.exceptions
# ---------------------------------------------------------------------------


class TestAppError:
    """Unit tests for AppError and its request handler."""

    def test_app_error_default_status_code(self) -> None:
        """AppError defaults to 400 status code."""
        from core.exceptions import AppError

        err = AppError("something went wrong")
        assert err.status_code == 400
        assert err.message == "something went wrong"
        assert str(err) == "something went wrong"

    def test_app_error_custom_status_code(self) -> None:
        """AppError accepts a custom status code."""
        from core.exceptions import AppError

        err = AppError("not found", status_code=404)
        assert err.status_code == 404

    def test_app_error_handler_returns_json_response(self) -> None:
        """app_error_handler returns a JSONResponse with correct status and body."""
        import asyncio

        from fastapi import Request
        from starlette.datastructures import Headers

        from core.exceptions import AppError, app_error_handler

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/generate",
            "query_string": b"",
            "headers": Headers({}).raw,
        }
        request = Request(scope=scope)
        exc = AppError("bad input", status_code=400)

        response = asyncio.run(app_error_handler(request, exc))

        assert response.status_code == 400
        import json

        body = json.loads(response.body)
        assert body["detail"] == "bad input"
