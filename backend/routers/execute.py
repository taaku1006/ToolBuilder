"""POST /api/execute, GET /api/download, POST /api/package-tool."""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from core.config import Settings
from core.deps import get_settings
from schemas.execute import ExecuteRequest, ExecuteResponse
from infra.sandbox import execute_code

router = APIRouter()


@router.post("/execute", response_model=ExecuteResponse)
def execute(
    request: ExecuteRequest,
    settings: Settings = Depends(get_settings),
) -> ExecuteResponse:
    """Execute user-provided Python code in a sandboxed subprocess."""
    logger.info("Execute request", extra={"file_id": request.file_id, "code_length": len(request.code)})
    result = execute_code(
        code=request.code,
        file_id=request.file_id,
        upload_dir=settings.upload_dir,
        output_dir=settings.output_dir,
        timeout=settings.exec_timeout,
    )

    logger.info("Execute completed", extra={"success": result.success, "elapsed_ms": result.elapsed_ms})

    return ExecuteResponse(
        stdout=result.stdout,
        stderr=result.stderr,
        elapsed_ms=result.elapsed_ms,
        output_files=result.output_files,
        success=result.success,
    )


@router.get("/download/{file_path:path}")
def download_file(
    file_path: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """Download an output file produced by sandbox execution.

    file_path is relative, e.g. outputs/<exec_id>/output.xlsx
    """
    resolved = Path(file_path).resolve()
    output_root = Path(settings.output_dir).resolve()

    # Prevent path traversal — file must be under the output directory
    if not str(resolved).startswith(str(output_root)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    logger.info("File download", extra={"file_path": str(resolved)})

    return FileResponse(
        path=str(resolved),
        filename=resolved.name,
        media_type="application/octet-stream",
    )


# ---------------------------------------------------------------------------
# POST /api/package-tool — bundle tool.py + run.bat + README into a zip
# ---------------------------------------------------------------------------


class PackageToolRequest(BaseModel):
    tool_py: str
    run_bat: str
    readme: str


@router.post("/package-tool")
def package_tool(request: PackageToolRequest) -> StreamingResponse:
    """Create a ZIP archive containing the tool files."""
    logger.info("Package tool request")

    buf = io.BytesIO()
    # BOM prefix for UTF-8 files so Windows Notepad/Excel display them correctly
    utf8_bom = b"\xef\xbb\xbf"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("tool/tool.py", utf8_bom + request.tool_py.encode("utf-8"))
        zf.writestr("tool/run.bat", request.run_bat.encode("ascii", errors="replace"))
        zf.writestr("tool/README.txt", utf8_bom + request.readme.encode("utf-8"))
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=tool.zip"},
    )
