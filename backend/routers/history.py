"""History CRUD endpoints: GET/POST/DELETE/PATCH /api/history."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import get_db
from db.models import History
from schemas.history import (
    HistoryCreateRequest,
    HistoryItem,
    HistoryListResponse,
    HistoryUpdateMemo,
)

router = APIRouter()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_to_item(record: History) -> HistoryItem:
    """Convert a History ORM row to a HistoryItem schema."""
    steps: list[str] | None = None
    if record.steps is not None:
        try:
            steps = json.loads(record.steps)
        except (json.JSONDecodeError, ValueError):
            steps = None

    created_at_str = (
        record.created_at.isoformat()
        if isinstance(record.created_at, datetime)
        else str(record.created_at)
    )

    return HistoryItem(
        id=record.id,
        created_at=created_at_str,
        task=record.task,
        file_name=record.file_name,
        summary=record.summary,
        python_code=record.python_code,
        steps=steps,
        tips=record.tips,
        memo=record.memo,
        exec_stdout=record.exec_stdout,
        exec_stderr=record.exec_stderr,
    )


# ---------------------------------------------------------------------------
# GET /api/history
# ---------------------------------------------------------------------------


@router.get("/history", response_model=HistoryListResponse)
async def list_history(
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> HistoryListResponse:
    """List history items, optionally filtered by task text via ?q=."""
    stmt = select(History).order_by(History.created_at.desc())
    if q:
        stmt = stmt.where(History.task.contains(q))

    result = await db.execute(stmt)
    records = result.scalars().all()
    items = [_model_to_item(r) for r in records]
    logger.info("History list", extra={"query": q, "count": len(items)})
    return HistoryListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# GET /api/history/{id}
# ---------------------------------------------------------------------------


@router.get("/history/{item_id}", response_model=HistoryItem)
async def get_history(
    item_id: str,
    db: AsyncSession = Depends(get_db),
) -> HistoryItem:
    """Retrieve a single history item by its id."""
    record = await db.get(History, item_id)
    if record is None:
        raise HTTPException(status_code=404, detail="History item not found")
    return _model_to_item(record)


# ---------------------------------------------------------------------------
# POST /api/history
# ---------------------------------------------------------------------------


@router.post("/history", response_model=HistoryItem, status_code=201)
async def create_history(
    payload: HistoryCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> HistoryItem:
    """Create a new history record."""
    steps_json: str | None = None
    if payload.steps is not None:
        steps_json = json.dumps(payload.steps, ensure_ascii=False)

    record = History(
        id=str(uuid.uuid4()),
        task=payload.task,
        file_name=payload.file_name,
        summary=payload.summary,
        python_code=payload.python_code,
        steps=steps_json,
        tips=payload.tips,
        exec_stdout=payload.exec_stdout,
        exec_stderr=payload.exec_stderr,
    )

    db.add(record)
    await db.commit()
    await db.refresh(record)
    logger.info("History created", extra={"id": record.id})

    return _model_to_item(record)


# ---------------------------------------------------------------------------
# DELETE /api/history/{id}
# ---------------------------------------------------------------------------


@router.delete("/history/{item_id}", status_code=204)
async def delete_history(
    item_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a history item by id."""
    record = await db.get(History, item_id)
    if record is None:
        raise HTTPException(status_code=404, detail="History item not found")
    await db.delete(record)
    await db.commit()
    logger.info("History deleted", extra={"id": item_id})


# ---------------------------------------------------------------------------
# PATCH /api/history/{id} — update memo
# ---------------------------------------------------------------------------


@router.patch("/history/{item_id}", response_model=HistoryItem)
async def update_memo(
    item_id: str,
    payload: HistoryUpdateMemo,
    db: AsyncSession = Depends(get_db),
) -> HistoryItem:
    """Update the memo field of a history item."""
    record = await db.get(History, item_id)
    if record is None:
        raise HTTPException(status_code=404, detail="History item not found")

    record.memo = payload.memo
    await db.commit()
    await db.refresh(record)
    logger.info("History memo updated", extra={"id": item_id})

    return _model_to_item(record)
