"""Pydantic schemas for the skills endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class SkillItem(BaseModel):
    """Full representation of a skill, returned from GET and POST endpoints."""

    id: str
    created_at: str
    title: str
    tags: list[str]
    python_code: str
    file_schema: str | None
    task_summary: str | None
    use_count: int
    success_rate: float


class SkillCreateRequest(BaseModel):
    """Request body for POST /api/skills."""

    title: str
    tags: list[str] = []
    python_code: str
    file_schema: str | None = None
    task_summary: str | None = None
    source_history_id: str | None = None


class SkillUseRequest(BaseModel):
    """Optional request body for POST /api/skills/{id}/use."""

    success: bool = True


class SkillSuggestion(BaseModel):
    """A suggested skill returned after file upload similarity matching."""

    id: str
    title: str
    tags: list[str]
    similarity: float


class SkillsListResponse(BaseModel):
    """Response body for GET /api/skills."""

    items: list[SkillItem]
    total: int
