"""Integration tests for POST /api/execute endpoint.

TDD order: tests written FIRST, implementation follows.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.config import Settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def execute_settings(tmp_path: Path) -> Settings:
    """Settings wired to temporary upload/output dirs."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    return Settings(
        openai_api_key="test-key",
        upload_dir=str(upload_dir),
        output_dir=str(output_dir),
        exec_timeout=10,
    )


@pytest.fixture
def execute_client(
    execute_settings: Settings,
    mock_openai_client: MagicMock,
) -> TestClient:
    """TestClient for the execute endpoint with temp dirs."""
    from core.deps import get_settings
    from main import app

    app.dependency_overrides[get_settings] = lambda: execute_settings

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Integration tests: POST /api/execute
# ---------------------------------------------------------------------------


class TestExecuteEndpoint:
    """Integration tests for POST /api/execute."""

    def test_success_returns_200(self, execute_client: TestClient) -> None:
        """Valid code returns HTTP 200."""
        response = execute_client.post(
            "/api/execute",
            json={"code": "print('hello')"},
        )
        assert response.status_code == 200

    def test_response_schema(self, execute_client: TestClient) -> None:
        """Response contains all required fields."""
        response = execute_client.post(
            "/api/execute",
            json={"code": "print('test')"},
        )
        data = response.json()

        assert "stdout" in data
        assert "stderr" in data
        assert "elapsed_ms" in data
        assert "output_files" in data
        assert "success" in data

    def test_stdout_captured(self, execute_client: TestClient) -> None:
        """stdout from executed code appears in response."""
        response = execute_client.post(
            "/api/execute",
            json={"code": "print('captured')"},
        )
        data = response.json()

        assert "captured" in data["stdout"]
        assert data["success"] is True

    def test_success_false_on_runtime_error(self, execute_client: TestClient) -> None:
        """Code that raises returns success=False."""
        response = execute_client.post(
            "/api/execute",
            json={"code": "raise ValueError('test error')"},
        )
        data = response.json()

        assert data["success"] is False
        assert data["stderr"] != ""

    def test_elapsed_ms_is_integer(self, execute_client: TestClient) -> None:
        """elapsed_ms field must be an integer."""
        response = execute_client.post(
            "/api/execute",
            json={"code": "pass"},
        )
        data = response.json()

        assert isinstance(data["elapsed_ms"], int)

    def test_output_files_is_list(self, execute_client: TestClient) -> None:
        """output_files field must be a list."""
        response = execute_client.post(
            "/api/execute",
            json={"code": "pass"},
        )
        data = response.json()

        assert isinstance(data["output_files"], list)

    def test_missing_code_returns_422(self, execute_client: TestClient) -> None:
        """Request without code field returns HTTP 422."""
        response = execute_client.post("/api/execute", json={})
        assert response.status_code == 422

    def test_empty_code_returns_200(self, execute_client: TestClient) -> None:
        """Empty string code is valid Python and returns 200."""
        response = execute_client.post(
            "/api/execute",
            json={"code": ""},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_optional_file_id_accepted(
        self, execute_client: TestClient, execute_settings: Settings
    ) -> None:
        """file_id is optional and accepted."""
        # Create a fake uploaded file
        upload_dir = Path(execute_settings.upload_dir)
        (upload_dir / "testfile123_data.csv").write_text("a,b\n1,2\n")

        import textwrap

        code = textwrap.dedent(
            """\
            import os
            inp = os.environ.get('INPUT_FILE', 'NOT_SET')
            print(f'got={inp}')
            """
        )

        response = execute_client.post(
            "/api/execute",
            json={"code": code, "file_id": "testfile123"},
        )
        data = response.json()

        assert response.status_code == 200
        assert "NOT_SET" not in data["stdout"]
        assert "got=" in data["stdout"]

    def test_file_id_none_accepted(self, execute_client: TestClient) -> None:
        """file_id=null is accepted."""
        response = execute_client.post(
            "/api/execute",
            json={"code": "print('ok')", "file_id": None},
        )
        assert response.status_code == 200

    def test_syntax_error_returns_200_with_failure(
        self, execute_client: TestClient
    ) -> None:
        """Syntax error in code returns 200 with success=False (execution attempted)."""
        response = execute_client.post(
            "/api/execute",
            json={"code": "def bad(:\n    pass"},
        )
        data = response.json()

        assert response.status_code == 200
        assert data["success"] is False

    def test_unicode_output(self, execute_client: TestClient) -> None:
        """Unicode characters in stdout are preserved."""
        response = execute_client.post(
            "/api/execute",
            json={"code": "print('日本語テスト')"},
        )
        data = response.json()

        assert "日本語テスト" in data["stdout"]
