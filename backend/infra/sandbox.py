"""Sandboxed Python code execution via subprocess."""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable result of a sandboxed code execution."""

    stdout: str
    stderr: str
    elapsed_ms: int
    output_files: list[str]
    success: bool


def _build_env(
    exec_dir: Path,
    file_id: str | None,
    upload_dir: str,
) -> dict[str, str]:
    """Build a minimal environment dict for the sandboxed subprocess.

    Only PATH, INPUT_FILE, and OUTPUT_DIR are passed through.
    All other environment variables (including OPENAI_API_KEY) are excluded.
    """
    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "OUTPUT_DIR": str(exec_dir.resolve()),
    }

    if file_id:
        upload_path = Path(upload_dir).resolve()
        matches = list(upload_path.glob(f"{file_id}_*"))
        if matches:
            env["INPUT_FILE"] = str(matches[0].resolve())

    return env


_ERROR_PATTERNS = (
    "エラーが発生しました",
    "Traceback (most recent call last)",
    "Error:",
    "Exception:",
)


def _stdout_has_error(stdout: str) -> bool:
    """Check if stdout contains error messages from a broad try/except."""
    return any(pat in stdout for pat in _ERROR_PATTERNS)


_SCRIPT_FILENAMES = {"script.py", "script.sh"}


def _collect_output_files(exec_dir: Path) -> list[str]:
    """Return file names (not the script itself) written to exec_dir."""
    return [
        str(p)
        for p in exec_dir.iterdir()
        if p.is_file() and p.name not in _SCRIPT_FILENAMES
    ]


def execute_code(
    code: str,
    file_id: str | None = None,
    upload_dir: str = "./uploads",
    output_dir: str = "./outputs",
    timeout: int = 30,
) -> ExecutionResult:
    """Execute Python code in a sandboxed subprocess.

    - Creates a temp directory under output_dir/{exec_id}/
    - Writes code to script.py in that directory
    - Optionally injects INPUT_FILE env var if file_id matches a file
    - Only passes PATH, INPUT_FILE, OUTPUT_DIR to the subprocess
    - Returns an immutable ExecutionResult

    Args:
        code: Python source code to execute.
        file_id: Optional upload file ID to find in upload_dir.
        upload_dir: Directory containing uploaded files.
        output_dir: Parent directory for execution temp dirs.
        timeout: Maximum execution time in seconds.

    Returns:
        Frozen ExecutionResult with stdout, stderr, elapsed_ms, output_files, success.
    """
    exec_id = str(uuid.uuid4())
    code_hash = hashlib.sha256(code.encode()).hexdigest()[:8]
    exec_dir = Path(output_dir) / exec_id
    exec_dir.mkdir(parents=True, exist_ok=True)

    script_path = exec_dir / "script.py"
    script_path.write_text(code, encoding="utf-8")

    env = _build_env(exec_dir, file_id, upload_dir)

    logger.info(
        "Sandbox execution started",
        extra={"exec_id": exec_id, "code_hash": code_hash, "file_id": file_id, "timeout": timeout},
    )

    start = time.monotonic()
    try:
        proc = subprocess.run(
            ["python", "script.py"],
            cwd=str(exec_dir),
            env=env,
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = proc.stdout
        stderr = proc.stderr

        # Detect failure even when returncode is 0 but code caught its own error
        success = proc.returncode == 0
        if success and _stdout_has_error(stdout):
            success = False
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.warning(
            "Sandbox execution timed out",
            extra={"exec_id": exec_id, "elapsed_ms": elapsed_ms, "timeout": timeout},
        )
        return ExecutionResult(
            stdout="",
            stderr="Execution timed out",
            elapsed_ms=elapsed_ms,
            output_files=[],
            success=False,
        )

    output_files = _collect_output_files(exec_dir)

    if success:
        logger.info(
            "Sandbox execution completed",
            extra={"exec_id": exec_id, "success": True, "elapsed_ms": elapsed_ms, "output_file_count": len(output_files)},
        )
    else:
        logger.warning(
            "Sandbox execution failed",
            extra={"exec_id": exec_id, "success": False, "elapsed_ms": elapsed_ms, "stderr_preview": stderr[:200]},
        )

    return ExecutionResult(
        stdout=stdout,
        stderr=stderr,
        elapsed_ms=elapsed_ms,
        output_files=output_files,
        success=success,
    )


# ---------------------------------------------------------------------------
# Language-aware code block execution
# ---------------------------------------------------------------------------

_LANG_TO_CMD: dict[str, tuple[str, str]] = {
    "python": ("script.py", "python"),
    "sh": ("script.sh", "sh"),
}


def execute_code_block(
    code: str,
    language: str = "python",
    file_id: str | None = None,
    upload_dir: str = "./uploads",
    output_dir: str = "./outputs",
    timeout: int = 30,
) -> ExecutionResult:
    """Execute a single code block with the specified language interpreter.

    Mirrors autogen's LocalCommandLineCodeExecutor._execute_code_dont_check_setup():
      - Each block is written to a separate file (script.py or script.sh)
      - Executed with the appropriate interpreter (python or sh)
      - Same sandboxed environment as execute_code() (PATH, OUTPUT_DIR, INPUT_FILE only)

    Args:
        code: Source code to execute.
        language: Language of the code block ("python" or "sh").
        file_id: Optional upload file ID to find in upload_dir.
        upload_dir: Directory containing uploaded files.
        output_dir: Parent directory for execution temp dirs.
        timeout: Maximum execution time in seconds.

    Returns:
        Frozen ExecutionResult.
    """
    lang_key = language.lower()
    if lang_key not in _LANG_TO_CMD:
        return ExecutionResult(
            stdout="",
            stderr=f"Unsupported language: {language}",
            elapsed_ms=0,
            output_files=[],
            success=False,
        )

    script_name, cmd = _LANG_TO_CMD[lang_key]

    exec_id = str(uuid.uuid4())
    exec_dir = Path(output_dir) / exec_id
    exec_dir.mkdir(parents=True, exist_ok=True)

    script_path = exec_dir / script_name
    script_path.write_text(code, encoding="utf-8")

    env = _build_env(exec_dir, file_id, upload_dir)

    logger.info(
        "Sandbox block execution started",
        extra={"exec_id": exec_id, "language": lang_key, "timeout": timeout},
    )

    start = time.monotonic()
    try:
        proc = subprocess.run(
            [cmd, script_name],
            cwd=str(exec_dir),
            env=env,
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = proc.stdout
        stderr = proc.stderr
        success = proc.returncode == 0
        if success and lang_key == "python" and _stdout_has_error(stdout):
            success = False
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.warning(
            "Sandbox block execution timed out",
            extra={"exec_id": exec_id, "elapsed_ms": elapsed_ms, "timeout": timeout},
        )
        return ExecutionResult(
            stdout="",
            stderr="Execution timed out",
            elapsed_ms=elapsed_ms,
            output_files=[],
            success=False,
        )

    output_files = _collect_output_files(exec_dir)

    return ExecutionResult(
        stdout=stdout,
        stderr=stderr,
        elapsed_ms=elapsed_ms,
        output_files=output_files,
        success=success,
    )
