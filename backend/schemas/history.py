"""Schemas for the /api/history endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class HistoryItem(BaseModel):
    id: str
    created_at: str
    task: str
    file_name: str | None
    summary: str | None
    python_code: str
    steps: list[str] | None  # parsed from JSON stored in DB
    tips: str | None
    memo: str | None
    exec_stdout: str | None
    exec_stderr: str | None


class HistoryListResponse(BaseModel):
    items: list[HistoryItem]
    total: int


class HistoryCreateRequest(BaseModel):
    task: str
    file_name: str | None = None
    summary: str | None = None
    python_code: str
    steps: list[str] | None = None
    tips: str | None = None
    exec_stdout: str | None = None
    exec_stderr: str | None = None


class HistoryUpdateMemo(BaseModel):
    memo: str
