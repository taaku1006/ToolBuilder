"""Pydantic schemas for the upload endpoint."""

from pydantic import BaseModel


class SheetInfoSchema(BaseModel):
    """Serialisable representation of a parsed sheet."""

    name: str
    total_rows: int
    headers: list[str]
    types: dict[str, str]
    preview: list[dict[str, str | int | float | None]]


class UploadResponse(BaseModel):
    """Response body for POST /api/upload."""

    file_id: str
    filename: str
    sheets: list[SheetInfoSchema]
