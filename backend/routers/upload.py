"""POST /api/upload router.

Validates, saves, and parses uploaded xlsx / xls / csv files.
After parsing, queries the skills database to find similar skills.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from core.deps import get_settings
from db.engine import get_db
from db.models import Skill
from schemas.skills import SkillSuggestion
from schemas.upload import SheetInfoSchema, UploadResponse
from services.skills_engine import match_skills
from services.xlsx_parser import SheetInfo, parse_file

router = APIRouter()

_ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """Accept a multipart file upload, validate, save, and parse it.

    Also queries the skills database for similar skills based on
    file column headers and returns them as suggested_skills.
    """
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

    # Gather all headers from all sheets for skills matching
    all_headers: list[str] = []
    for sheet in sheets:
        all_headers.extend(sheet.headers)

    # Query skills and compute similarity suggestions
    suggested_skills: list[SkillSuggestion] = []
    if settings.skills_enabled and all_headers:
        stmt = select(Skill)
        result = await db.execute(stmt)
        skill_records = result.scalars().all()

        if skill_records:
            skill_dicts = [
                {
                    "id": s.id,
                    "title": s.title,
                    "tags": s.tags,
                    "file_schema": s.file_schema,
                    "task_summary": s.task_summary,
                }
                for s in skill_records
            ]
            matches = match_skills(
                file_headers=all_headers,
                task_text="",
                skills=skill_dicts,
                threshold=settings.skills_similarity_threshold,
            )
            suggested_skills = [
                SkillSuggestion(
                    id=m.skill_id,
                    title=m.title,
                    tags=m.tags,
                    similarity=m.similarity,
                )
                for m in matches
            ]

    return UploadResponse(
        file_id=file_id,
        filename=filename,
        sheets=sheet_schemas,
        suggested_skills=suggested_skills,
    )
