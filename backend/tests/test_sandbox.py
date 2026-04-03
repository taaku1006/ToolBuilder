"""Unit tests for infra.sandbox.execute_code.

TDD order: tests written FIRST, implementation follows.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Unit tests: ExecutionResult dataclass
# ---------------------------------------------------------------------------


class TestExecutionResult:
    """Tests for the frozen ExecutionResult dataclass."""

    def test_is_frozen(self) -> None:
        """ExecutionResult must be immutable (frozen dataclass)."""
        from infra.sandbox import ExecutionResult

        result = ExecutionResult(
            stdout="hello",
            stderr="",
            elapsed_ms=100,
            output_files=[],
            success=True,
        )

        with pytest.raises(Exception):
            result.stdout = "modified"  # type: ignore[misc]

    def test_fields_accessible(self) -> None:
        """All fields must be accessible as attributes."""
        from infra.sandbox import ExecutionResult

        result = ExecutionResult(
            stdout="out",
            stderr="err",
            elapsed_ms=42,
            output_files=["file.csv"],
            success=False,
        )

        assert result.stdout == "out"
        assert result.stderr == "err"
        assert result.elapsed_ms == 42
        assert result.output_files == ["file.csv"]
        assert result.success is False

    def test_success_true_when_no_error(self) -> None:
        """Constructing with success=True preserves the flag."""
        from infra.sandbox import ExecutionResult

        result = ExecutionResult(
            stdout="ok",
            stderr="",
            elapsed_ms=10,
            output_files=[],
            success=True,
        )

        assert result.success is True


# ---------------------------------------------------------------------------
# Unit tests: execute_code — happy path
# ---------------------------------------------------------------------------


class TestExecuteCodeHappyPath:
    """Happy-path tests for execute_code."""

    def test_simple_print(self, tmp_path: Path) -> None:
        """Code that prints a string returns stdout with that string."""
        from infra.sandbox import execute_code

        code = "print('hello world')"
        result = execute_code(
            code=code,
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.success is True
        assert "hello world" in result.stdout
        assert result.stderr == ""

    def test_elapsed_ms_is_non_negative(self, tmp_path: Path) -> None:
        """elapsed_ms must be >= 0."""
        from infra.sandbox import execute_code

        result = execute_code(
            code="pass",
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.elapsed_ms >= 0

    def test_output_files_empty_when_none_created(self, tmp_path: Path) -> None:
        """output_files must be empty when the script creates no files."""
        from infra.sandbox import execute_code

        result = execute_code(
            code="x = 1 + 1",
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.output_files == []

    def test_output_files_listed_when_created(self, tmp_path: Path) -> None:
        """output_files must contain files written to OUTPUT_DIR."""
        from infra.sandbox import execute_code

        code = textwrap.dedent(
            """\
            import os
            out_dir = os.environ['OUTPUT_DIR']
            with open(os.path.join(out_dir, 'result.txt'), 'w') as f:
                f.write('done')
            """
        )

        result = execute_code(
            code=code,
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.success is True
        assert any("result.txt" in f for f in result.output_files)

    def test_output_dir_env_var_set(self, tmp_path: Path) -> None:
        """The script can read OUTPUT_DIR from env and write files there."""
        from infra.sandbox import execute_code

        code = textwrap.dedent(
            """\
            import os
            d = os.environ.get('OUTPUT_DIR', '')
            print(f'OUTPUT_DIR={d}')
            """
        )

        result = execute_code(
            code=code,
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.success is True
        assert "OUTPUT_DIR=" in result.stdout
        # Must not be empty
        assert "OUTPUT_DIR=\n" not in result.stdout


# ---------------------------------------------------------------------------
# Unit tests: execute_code — file_id / INPUT_FILE
# ---------------------------------------------------------------------------


class TestExecuteCodeFileId:
    """Tests for INPUT_FILE env var injection when file_id is provided."""

    def test_input_file_env_set_when_file_id_given(self, tmp_path: Path) -> None:
        """When file_id matches a file in upload_dir, INPUT_FILE env var is set."""
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        upload_file = upload_dir / "abc123_data.xlsx"
        upload_file.write_text("fake xlsx")

        from infra.sandbox import execute_code

        code = textwrap.dedent(
            """\
            import os
            inp = os.environ.get('INPUT_FILE', 'NOT_SET')
            print(f'INPUT_FILE={inp}')
            """
        )

        result = execute_code(
            code=code,
            file_id="abc123",
            upload_dir=str(upload_dir),
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.success is True
        assert "NOT_SET" not in result.stdout
        assert "abc123_data.xlsx" in result.stdout

    def test_no_input_file_env_when_file_id_none(self, tmp_path: Path) -> None:
        """When file_id is None, INPUT_FILE env var must not be set."""
        from infra.sandbox import execute_code

        code = textwrap.dedent(
            """\
            import os
            inp = os.environ.get('INPUT_FILE', 'NOT_SET')
            print(f'INPUT_FILE={inp}')
            """
        )

        result = execute_code(
            code=code,
            file_id=None,
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.success is True
        assert "NOT_SET" in result.stdout

    def test_no_input_file_env_when_file_not_found(self, tmp_path: Path) -> None:
        """When file_id is given but no matching file exists, INPUT_FILE not set."""
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()

        from infra.sandbox import execute_code

        code = textwrap.dedent(
            """\
            import os
            inp = os.environ.get('INPUT_FILE', 'NOT_SET')
            print(f'INPUT_FILE={inp}')
            """
        )

        result = execute_code(
            code=code,
            file_id="missing-id",
            upload_dir=str(upload_dir),
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.success is True
        assert "NOT_SET" in result.stdout


# ---------------------------------------------------------------------------
# Unit tests: execute_code — environment isolation (security)
# ---------------------------------------------------------------------------


class TestExecuteCodeEnvIsolation:
    """Ensure only allowed env vars are passed to the subprocess."""

    def test_openai_api_key_not_leaked(self, tmp_path: Path, monkeypatch) -> None:
        """OPENAI_API_KEY must not be accessible inside the sandboxed script."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-key")

        from infra.sandbox import execute_code

        code = textwrap.dedent(
            """\
            import os
            key = os.environ.get('OPENAI_API_KEY', 'NOT_PRESENT')
            print(f'KEY={key}')
            """
        )

        result = execute_code(
            code=code,
            output_dir=str(tmp_path / "outputs"),
        )

        assert "sk-super-secret-key" not in result.stdout
        assert "NOT_PRESENT" in result.stdout

    def test_only_allowed_env_vars_present(self, tmp_path: Path) -> None:
        """Only PATH, INPUT_FILE, OUTPUT_DIR should be in the subprocess env."""
        from infra.sandbox import execute_code

        code = textwrap.dedent(
            """\
            import os, json
            keys = list(os.environ.keys())
            print(json.dumps(keys))
            """
        )

        result = execute_code(
            code=code,
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.success is True
        import json

        env_keys = json.loads(result.stdout.strip())
        # LC_CTYPE may be injected by the Python runtime on some platforms
        allowed = {"PATH", "INPUT_FILE", "OUTPUT_DIR", "LC_CTYPE"}
        unexpected = set(env_keys) - allowed
        assert unexpected == set(), f"Unexpected env vars leaked: {unexpected}"


# ---------------------------------------------------------------------------
# Unit tests: execute_code — error paths
# ---------------------------------------------------------------------------


class TestExecuteCodeErrors:
    """Error path tests for execute_code."""

    def test_syntax_error_returns_failure(self, tmp_path: Path) -> None:
        """Code with a syntax error returns success=False and stderr contains info."""
        from infra.sandbox import execute_code

        result = execute_code(
            code="def broken(:\n    pass",
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.success is False
        assert result.stderr != ""

    def test_runtime_error_returns_failure(self, tmp_path: Path) -> None:
        """Code that raises at runtime returns success=False."""
        from infra.sandbox import execute_code

        result = execute_code(
            code="raise ValueError('intentional error')",
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.success is False
        assert "ValueError" in result.stderr

    def test_timeout_returns_failure(self, tmp_path: Path) -> None:
        """Code that exceeds timeout returns success=False with timeout message."""
        from infra.sandbox import execute_code

        result = execute_code(
            code="import time; time.sleep(10)",
            output_dir=str(tmp_path / "outputs"),
            timeout=1,
        )

        assert result.success is False
        assert "timed out" in result.stderr.lower()

    def test_empty_code_runs_without_error(self, tmp_path: Path) -> None:
        """Empty string code is valid Python and must succeed."""
        from infra.sandbox import execute_code

        result = execute_code(
            code="",
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.success is True

    def test_unicode_in_code(self, tmp_path: Path) -> None:
        """Code containing unicode characters must execute correctly."""
        from infra.sandbox import execute_code

        result = execute_code(
            code="print('日本語テスト')",
            output_dir=str(tmp_path / "outputs"),
        )

        assert result.success is True
        assert "日本語テスト" in result.stdout

    def test_stdout_is_captured(self, tmp_path: Path) -> None:
        """stdout from the script is returned in the result."""
        from infra.sandbox import execute_code

        result = execute_code(
            code="print('captured output')",
            output_dir=str(tmp_path / "outputs"),
        )

        assert "captured output" in result.stdout

    def test_result_is_immutable(self, tmp_path: Path) -> None:
        """The returned ExecutionResult must be frozen."""
        from infra.sandbox import execute_code

        result = execute_code(
            code="pass",
            output_dir=str(tmp_path / "outputs"),
        )

        with pytest.raises(Exception):
            result.stdout = "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Unit tests: execute_code_block — language-aware execution
# ---------------------------------------------------------------------------


class TestExecuteCodeBlock:
    """Tests for execute_code_block() which supports python and sh."""

    def test_python_block_executes(self, tmp_path: Path) -> None:
        """Python code block should execute and return stdout."""
        from infra.sandbox import execute_code_block

        result = execute_code_block(
            code="print('hello from python')",
            language="python",
            output_dir=str(tmp_path / "outputs"),
        )
        assert result.success is True
        assert "hello from python" in result.stdout

    def test_sh_block_executes(self, tmp_path: Path) -> None:
        """Shell code block should execute via sh."""
        from infra.sandbox import execute_code_block

        result = execute_code_block(
            code="echo 'hello from sh'",
            language="sh",
            output_dir=str(tmp_path / "outputs"),
        )
        assert result.success is True
        assert "hello from sh" in result.stdout

    def test_sh_block_error_returns_failure(self, tmp_path: Path) -> None:
        """Shell block with a failing command returns success=False."""
        from infra.sandbox import execute_code_block

        result = execute_code_block(
            code="exit 1",
            language="sh",
            output_dir=str(tmp_path / "outputs"),
        )
        assert result.success is False

    def test_python_block_has_sandbox_env(self, tmp_path: Path) -> None:
        """Python block should have OUTPUT_DIR env var (same sandbox as execute_code)."""
        from infra.sandbox import execute_code_block

        code = textwrap.dedent("""\
            import os
            print(os.environ.get('OUTPUT_DIR', 'NOT_SET'))
        """)
        result = execute_code_block(
            code=code,
            language="python",
            output_dir=str(tmp_path / "outputs"),
        )
        assert result.success is True
        assert "NOT_SET" not in result.stdout

    def test_sh_block_has_sandbox_env(self, tmp_path: Path) -> None:
        """Shell block should also have OUTPUT_DIR env var."""
        from infra.sandbox import execute_code_block

        result = execute_code_block(
            code="echo $OUTPUT_DIR",
            language="sh",
            output_dir=str(tmp_path / "outputs"),
        )
        assert result.success is True
        assert result.stdout.strip() != ""

    def test_sh_block_no_api_key_leak(self, tmp_path: Path, monkeypatch) -> None:
        """Shell block must not leak OPENAI_API_KEY."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")

        from infra.sandbox import execute_code_block

        result = execute_code_block(
            code="echo $OPENAI_API_KEY",
            language="sh",
            output_dir=str(tmp_path / "outputs"),
        )
        assert "sk-secret" not in result.stdout

    def test_sh_block_collects_output_files(self, tmp_path: Path) -> None:
        """Shell block that creates files should have them in output_files."""
        from infra.sandbox import execute_code_block

        result = execute_code_block(
            code="echo 'data' > $OUTPUT_DIR/result.csv",
            language="sh",
            output_dir=str(tmp_path / "outputs"),
        )
        assert result.success is True
        assert any("result.csv" in f for f in result.output_files)

    def test_timeout_applies_to_sh(self, tmp_path: Path) -> None:
        """Shell block timeout should work the same as python."""
        from infra.sandbox import execute_code_block

        result = execute_code_block(
            code="sleep 10",
            language="sh",
            output_dir=str(tmp_path / "outputs"),
            timeout=1,
        )
        assert result.success is False
        assert "timed out" in result.stderr.lower()
