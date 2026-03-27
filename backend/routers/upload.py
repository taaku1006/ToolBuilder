"""POST /api/upload router.

Validates, saves, and parses uploaded xlsx / xls / csv files.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from core.config import Settings
from core.deps import get_settings
from schemas.upload import SheetInfoSchema, UploadResponse
from services.xlsx_parser import SheetInfo, parse_file

router = APIRouter()

_ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile,
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    """Accept a multipart file upload, validate, save, and parse it."""
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Allowed extensions: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            ),
        )

    # Read content and check size
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File size {len(content)} bytes exceeds the "
                f"{settings.max_upload_mb} MB limit."
            ),
        )

    # Persist to upload dir
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}_{filename}"
    dest = upload_dir / safe_filename
    dest.write_bytes(content)

    # Parse the saved file
    try:
        sheets: list[SheetInfo] = parse_file(str(dest))
    except ValueError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse file: {exc}",
        ) from exc

    sheet_schemas = [
        SheetInfoSchema(
            name=s.name,
            total_rows=s.total_rows,
            headers=s.headers,
            types=s.types,
            preview=s.preview,
        )
        for s in sheets
    ]

    return UploadResponse(
        file_id=file_id,
        filename=filename,
        sheets=sheet_schemas,
    )
