"""Unit tests for services.prompt_loader.

TDD: tests written FIRST, implementation follows.

Test cases:
- load_prompt(name) without settings reads from prompts/{name}.txt
- load_prompt(name, settings) calls prompt_manager.get_prompt
- When get_prompt raises an exception, falls back to file
- When prompt file does not exist, raises FileNotFoundError
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings():
    """Return a minimal Settings-like mock."""
    from core.config import Settings

    return Settings(
        openai_api_key="test-key-123",
        openai_model="gpt-4o",
        cors_origins="http://localhost:5173",
    )


# ---------------------------------------------------------------------------
# load_prompt without settings — reads from file
# ---------------------------------------------------------------------------


class TestLoadPromptNoSettings:
    """When settings is None (or omitted), load_prompt reads from the local file."""

    def test_returns_file_content_when_no_settings(self, tmp_path: Path) -> None:
        from services.prompt_loader import load_prompt

        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "test_prompt.txt").write_text("hello from file", encoding="utf-8")

        with patch("services.prompt_loader._PROMPTS_DIR", prompt_dir):
            result = load_prompt("test_prompt")

        assert result == "hello from file"

    def test_settings_none_skips_prompt_manager(self, tmp_path: Path) -> None:
        from services.prompt_loader import load_prompt

        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "any_prompt.txt").write_text("file content", encoding="utf-8")

        with patch("services.prompt_loader._PROMPTS_DIR", prompt_dir):
            with patch("services.prompt_loader.get_prompt") as mock_get:
                load_prompt("any_prompt", settings=None)
                mock_get.assert_not_called()

    def test_default_settings_is_none(self, tmp_path: Path) -> None:
        """load_prompt(name) with no settings kwarg defaults to None."""
        from services.prompt_loader import load_prompt

        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "default_test.txt").write_text("default content", encoding="utf-8")

        with patch("services.prompt_loader._PROMPTS_DIR", prompt_dir):
            result = load_prompt("default_test")

        assert result == "default content"


# ---------------------------------------------------------------------------
# load_prompt with settings — calls prompt_manager.get_prompt
# ---------------------------------------------------------------------------


class TestLoadPromptWithSettings:
    """When settings is provided, load_prompt tries get_prompt first."""

    def test_calls_get_prompt_with_name_and_settings(self, tmp_path: Path) -> None:
        from services.prompt_loader import load_prompt

        settings = _make_settings()
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "phase_d_debug.txt").write_text("file fallback", encoding="utf-8")

        with patch("services.prompt_loader._PROMPTS_DIR", prompt_dir):
            with patch("services.prompt_loader.get_prompt", return_value="from langfuse") as mock_get:
                result = load_prompt("phase_d_debug", settings=settings)

        mock_get.assert_called_once_with("phase_d_debug", settings)
        assert result == "from langfuse"

    def test_returns_get_prompt_result_when_successful(self, tmp_path: Path) -> None:
        from services.prompt_loader import load_prompt

        settings = _make_settings()
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "some_prompt.txt").write_text("file content", encoding="utf-8")

        with patch("services.prompt_loader._PROMPTS_DIR", prompt_dir):
            with patch("services.prompt_loader.get_prompt", return_value="langfuse content"):
                result = load_prompt("some_prompt", settings=settings)

        assert result == "langfuse content"


# ---------------------------------------------------------------------------
# load_prompt — fallback when get_prompt raises
# ---------------------------------------------------------------------------


class TestLoadPromptFallback:
    """When get_prompt raises any exception, load_prompt falls back to the local file."""

    def test_falls_back_to_file_when_get_prompt_raises(self, tmp_path: Path) -> None:
        from services.prompt_loader import load_prompt

        settings = _make_settings()
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "fallback_prompt.txt").write_text("fallback content", encoding="utf-8")

        with patch("services.prompt_loader._PROMPTS_DIR", prompt_dir):
            with patch("services.prompt_loader.get_prompt", side_effect=Exception("Langfuse error")):
                result = load_prompt("fallback_prompt", settings=settings)

        assert result == "fallback content"

    def test_falls_back_on_connection_error(self, tmp_path: Path) -> None:
        from services.prompt_loader import load_prompt

        settings = _make_settings()
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "conn_test.txt").write_text("connection fallback", encoding="utf-8")

        with patch("services.prompt_loader._PROMPTS_DIR", prompt_dir):
            with patch(
                "services.prompt_loader.get_prompt",
                side_effect=ConnectionError("network down"),
            ):
                result = load_prompt("conn_test", settings=settings)

        assert result == "connection fallback"

    def test_falls_back_on_value_error(self, tmp_path: Path) -> None:
        from services.prompt_loader import load_prompt

        settings = _make_settings()
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "val_error_test.txt").write_text("value error fallback", encoding="utf-8")

        with patch("services.prompt_loader._PROMPTS_DIR", prompt_dir):
            with patch(
                "services.prompt_loader.get_prompt",
                side_effect=ValueError("unknown prompt"),
            ):
                result = load_prompt("val_error_test", settings=settings)

        assert result == "value error fallback"


# ---------------------------------------------------------------------------
# load_prompt — FileNotFoundError when file does not exist
# ---------------------------------------------------------------------------


class TestLoadPromptFileNotFound:
    """When the prompt file does not exist and get_prompt also fails (or no settings),
    load_prompt should raise FileNotFoundError."""

    def test_raises_file_not_found_when_no_settings_and_no_file(self, tmp_path: Path) -> None:
        from services.prompt_loader import load_prompt

        empty_dir = tmp_path / "prompts"
        empty_dir.mkdir()

        with patch("services.prompt_loader._PROMPTS_DIR", empty_dir):
            with pytest.raises(FileNotFoundError):
                load_prompt("nonexistent_prompt")

    def test_raises_file_not_found_when_get_prompt_raises_and_no_file(
        self, tmp_path: Path
    ) -> None:
        from services.prompt_loader import load_prompt

        settings = _make_settings()
        empty_dir = tmp_path / "prompts"
        empty_dir.mkdir()

        with patch("services.prompt_loader._PROMPTS_DIR", empty_dir):
            with patch(
                "services.prompt_loader.get_prompt",
                side_effect=Exception("Langfuse unavailable"),
            ):
                with pytest.raises(FileNotFoundError):
                    load_prompt("missing_prompt", settings=settings)
