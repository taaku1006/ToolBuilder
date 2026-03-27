"""Schemas for the /api/execute endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class ExecuteRequest(BaseModel):
    code: str
    file_id: str | None = None


class ExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    elapsed_ms: int
    output_files: list[str]
    success: bool
