"""Skills CRUD + execution endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from core.deps import get_settings
from db.engine import get_db
from db.models import Skill
from schemas.execute import ExecuteResponse
from schemas.skills import (
    SkillCreateRequest,
    SkillItem,
    SkillsListResponse,
    SkillUseRequest,
)
from infra.sandbox import execute_code

router = APIRouter()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_to_item(record: Skill) -> SkillItem:
    """Convert a Skill ORM row to a SkillItem schema."""
    tags: list[str] = []
    if record.tags is not None:
        try:
            parsed = json.loads(record.tags)
            if isinstance(parsed, list):
                tags = [str(t) for t in parsed]
        except (json.JSONDecodeError, ValueError):
            tags = []

    created_at_str = (
        record.created_at.isoformat()
        if isinstance(record.created_at, datetime)
        else str(record.created_at)
    )

    return SkillItem(
        id=record.id,
        created_at=created_at_str,
        title=record.title,
        tags=tags,
        python_code=record.python_code,
        file_schema=record.file_schema,
        task_summary=record.task_summary,
        use_count=record.use_count,
        success_rate=record.success_rate,
    )


# ---------------------------------------------------------------------------
# GET /api/skills
# ---------------------------------------------------------------------------


@router.get("/skills", response_model=SkillsListResponse)
async def list_skills(
    db: AsyncSession = Depends(get_db),
) -> SkillsListResponse:
    """List all skill records ordered by created_at descending."""
    stmt = select(Skill).order_by(Skill.created_at.desc())
    result = await db.execute(stmt)
    records = result.scalars().all()
    items = [_model_to_item(r) for r in records]
    logger.info("Skills list", extra={"count": len(items)})
    return SkillsListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# GET /api/skills/{id}
# ---------------------------------------------------------------------------


@router.get("/skills/{skill_id}", response_model=SkillItem)
async def get_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
) -> SkillItem:
    """Retrieve a single skill by its id."""
    record = await db.get(Skill, skill_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return _model_to_item(record)


# ---------------------------------------------------------------------------
# POST /api/skills
# ---------------------------------------------------------------------------


@router.post("/skills", response_model=SkillItem, status_code=201)
async def create_skill(
    payload: SkillCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> SkillItem:
    """Create a new skill record."""
    tags_json = json.dumps(payload.tags, ensure_ascii=False)

    record = Skill(
        id=str(uuid.uuid4()),
        title=payload.title,
        tags=tags_json,
        python_code=payload.python_code,
        file_schema=payload.file_schema,
        task_summary=payload.task_summary,
        source_history_id=payload.source_history_id,
        use_count=0,
        success_rate=1.0,
    )

    db.add(record)
    await db.commit()
    await db.refresh(record)
    logger.info("Skill created", extra={"id": record.id, "title": payload.title})

    return _model_to_item(record)


# ---------------------------------------------------------------------------
# DELETE /api/skills/{id}
# ---------------------------------------------------------------------------


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a skill by id."""
    record = await db.get(Skill, skill_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    await db.delete(record)
    await db.commit()
    logger.info("Skill deleted", extra={"id": skill_id})


# ---------------------------------------------------------------------------
# POST /api/skills/{id}/use
# ---------------------------------------------------------------------------


@router.post("/skills/{skill_id}/use", response_model=SkillItem)
async def use_skill(
    skill_id: str,
    payload: SkillUseRequest = SkillUseRequest(),
    db: AsyncSession = Depends(get_db),
) -> SkillItem:
    """Increment use_count and update success_rate for a skill.

    success_rate is recalculated as: successful_uses / total_uses
    where total_uses includes this new invocation.
    """
    record = await db.get(Skill, skill_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    # Derive current successful_uses count from existing success_rate and use_count
    current_successes = round(record.success_rate * record.use_count)
    new_total = record.use_count + 1
    new_successes = current_successes + (1 if payload.success else 0)

    record.use_count = new_total
    record.success_rate = new_successes / new_total

    await db.commit()
    await db.refresh(record)
    logger.info("Skill used", extra={"id": skill_id, "success": payload.success, "new_use_count": new_total})

    return _model_to_item(record)


# ---------------------------------------------------------------------------
# POST /api/skills/{id}/run — execute skill code against an uploaded file
# ---------------------------------------------------------------------------


@router.post("/skills/{skill_id}/run", response_model=ExecuteResponse)
async def run_skill(
    skill_id: str,
    file: UploadFile,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> ExecuteResponse:
    """Run a saved skill against an uploaded file and return the result.

    The file is temporarily saved, the skill's python_code is executed in
    the sandbox with INPUT_FILE pointing to it, and the result is returned.
    use_count and success_rate are updated accordingly.
    """
    record = await db.get(Skill, skill_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    # Save uploaded file temporarily
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    filename = file.filename or "upload.xlsx"
    safe_filename = f"{file_id}_{filename}"
    dest = upload_dir / safe_filename
    content = await file.read()
    dest.write_bytes(content)

    logger.info(
        "Skill run started",
        extra={"skill_id": skill_id, "title": record.title, "upload_filename": filename, "file_id": file_id},
    )

    # Execute the skill's code in the sandbox
    result = execute_code(
        code=record.python_code,
        file_id=file_id,
        upload_dir=settings.upload_dir,
        output_dir=settings.output_dir,
        timeout=settings.exec_timeout,
    )

    # Update use_count and success_rate
    current_successes = round(record.success_rate * record.use_count)
    new_total = record.use_count + 1
    new_successes = current_successes + (1 if result.success else 0)
    record.use_count = new_total
    record.success_rate = new_successes / new_total
    await db.commit()

    logger.info(
        "Skill run completed",
        extra={"skill_id": skill_id, "success": result.success, "elapsed_ms": result.elapsed_ms},
    )

    return ExecuteResponse(
        stdout=result.stdout,
        stderr=result.stderr,
        elapsed_ms=result.elapsed_ms,
        output_files=result.output_files,
        success=result.success,
    )
