"""Pytest fixtures for backend tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.config import Settings


@pytest.fixture
def mock_settings() -> Settings:
    """Return a Settings instance with test values."""
    return Settings(
        openai_api_key="test-api-key-12345",
        openai_model="gpt-4o",
        cors_origins="http://localhost:5173",
    )


@pytest.fixture
def mock_openai_response() -> dict:
    """Return a mock OpenAI JSON response payload."""
    return {
        "summary": "Excelファイルの集計処理",
        "python_code": (
            "import os\n"
            "import openpyxl\n\n"
            "INPUT_FILE = os.environ['INPUT_FILE']\n"
            "OUTPUT_DIR = os.environ['OUTPUT_DIR']\n\n"
            "# Excelファイルを読み込む\n"
            "wb = openpyxl.load_workbook(INPUT_FILE)\n"
            "ws = wb.active\n"
            "print('処理完了')\n"
        ),
        "steps": ["ファイルを読み込む", "データを集計する", "結果を保存する"],
        "tips": "INPUT_FILE環境変数にExcelファイルのパスを設定してください。",
    }


@pytest.fixture
def mock_openai_json_str(mock_openai_response: dict) -> str:
    """Return mock OpenAI response as JSON string."""
    import json

    return json.dumps(mock_openai_response, ensure_ascii=False)


@pytest.fixture
def mock_openai_client(mock_openai_json_str: str) -> Generator[MagicMock, None, None]:
    """Patch OpenAIClient.generate_code to return a mock JSON string."""
    with patch(
        "services.openai_client.OpenAI",
        autospec=True,
    ) as mock_openai_cls:
        mock_instance = MagicMock()
        mock_openai_cls.return_value = mock_instance

        mock_choice = MagicMock()
        mock_choice.message.content = mock_openai_json_str
        mock_instance.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )
        yield mock_instance


@pytest.fixture
def test_client(
    mock_settings: Settings,
    mock_openai_client: MagicMock,
) -> Generator[TestClient, None, None]:
    """Return a FastAPI TestClient with mocked settings and OpenAI."""
    from core.deps import get_settings
    from main import app

    app.dependency_overrides[get_settings] = lambda: mock_settings

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
