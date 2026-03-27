"""POST /api/execute — run code in the sandbox and return the result."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.config import Settings
from core.deps import get_settings
from schemas.execute import ExecuteRequest, ExecuteResponse
from services.sandbox import execute_code

router = APIRouter()


@router.post("/execute", response_model=ExecuteResponse)
def execute(
    request: ExecuteRequest,
    settings: Settings = Depends(get_settings),
) -> ExecuteResponse:
    """Execute user-provided Python code in a sandboxed subprocess."""
    result = execute_code(
        code=request.code,
        file_id=request.file_id,
        upload_dir=settings.upload_dir,
        output_dir=settings.output_dir,
        timeout=settings.exec_timeout,
    )

    return ExecuteResponse(
        stdout=result.stdout,
        stderr=result.stderr,
        elapsed_ms=result.elapsed_ms,
        output_files=result.output_files,
        success=result.success,
    )
