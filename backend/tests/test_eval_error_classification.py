"""Tests for error classification in eval runner."""

from __future__ import annotations

import pytest

from eval.runner import classify_error


class TestClassifyError:
    def test_none_error_returns_none_category(self) -> None:
        assert classify_error(None, []) == "none"

    def test_json_parse_error(self) -> None:
        assert classify_error("Expecting value: line 1 column 1 (char 0)", []) == "json_parse"

    def test_json_decode_error(self) -> None:
        assert classify_error("json.decoder.JSONDecodeError: ...", []) == "json_parse"

    def test_syntax_error(self) -> None:
        assert classify_error("SyntaxError: invalid syntax", []) == "syntax_error"

    def test_syntax_error_in_traceback(self) -> None:
        err = "File \"script.py\", line 1\n    ```python\n    ^\nSyntaxError: invalid syntax"
        assert classify_error(err, []) == "syntax_error"

    def test_runtime_error_traceback(self) -> None:
        err = "Traceback (most recent call last):\n  File \"script.py\"\nValueError: bad value"
        assert classify_error(err, []) == "runtime_error"

    def test_timeout(self) -> None:
        assert classify_error("Execution timed out after 30s", []) == "timeout"

    def test_timeout_case_insensitive(self) -> None:
        assert classify_error("TIMEOUT exceeded", []) == "timeout"

    def test_api_error(self) -> None:
        assert classify_error("OpenAI API error: rate limit", []) == "api_error"

    def test_file_not_found(self) -> None:
        assert classify_error("Test case file not found: /path/to/file.xlsx", []) == "file_not_found"

    def test_unknown_error(self) -> None:
        assert classify_error("something completely unexpected", []) == "unknown"

    def test_phase_d_error_from_agent_log(self) -> None:
        """When error is None but Phase D had errors, classify from log."""
        log = [
            {"phase": "D", "action": "error", "content": "3回リトライしましたが解決できませんでした"},
        ]
        assert classify_error(None, log) == "runtime_error"

    def test_empty_string_error_returns_none(self) -> None:
        assert classify_error("", []) == "none"
