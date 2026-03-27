"""Sandboxed Python code execution via subprocess."""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


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
        "OUTPUT_DIR": str(exec_dir),
    }

    if file_id:
        upload_path = Path(upload_dir)
        matches = list(upload_path.glob(f"{file_id}_*"))
        if matches:
            env["INPUT_FILE"] = str(matches[0])

    return env


def _collect_output_files(exec_dir: Path) -> list[str]:
    """Return file names (not script.py itself) written to exec_dir."""
    return [
        str(p)
        for p in exec_dir.iterdir()
        if p.is_file() and p.name != "script.py"
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
    exec_dir = Path(output_dir) / exec_id
    exec_dir.mkdir(parents=True, exist_ok=True)

    script_path = exec_dir / "script.py"
    script_path.write_text(code, encoding="utf-8")

    env = _build_env(exec_dir, file_id, upload_dir)

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
        success = proc.returncode == 0
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
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
