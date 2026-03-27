"""POST /api/generate router."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from core.config import Settings
from core.deps import get_settings
from core.exceptions import AppError
from schemas.generate import GenerateRequest, GenerateResponse
from services.openai_client import OpenAIClient
from services.prompt_builder import SYSTEM_PROMPT, build_user_prompt
from services.xlsx_parser import SheetInfo, build_file_context, parse_file

router = APIRouter()


def _resolve_file_context(file_id: str | None, settings: Settings) -> str | None:
    """Look up the uploaded file by file_id and build a context string.

    Returns None when file_id is absent or the file cannot be found.
    """
    if not file_id:
        return None

    upload_dir = Path(settings.upload_dir)
    if not upload_dir.exists():
        return None

    # Files are saved as "{uuid}_{original_filename}"
    matches = list(upload_dir.glob(f"{file_id}_*"))
    if not matches:
        return None

    dest = matches[0]
    try:
        sheets: list[SheetInfo] = parse_file(str(dest))
        return build_file_context(sheets) or None
    except Exception:
        return None


@router.post("/generate", response_model=GenerateResponse)
def generate(
    request: GenerateRequest,
    settings: Settings = Depends(get_settings),
) -> GenerateResponse:
    """Generate Python code for Excel processing from a natural language task."""
    file_context = _resolve_file_context(request.file_id, settings)

    user_prompt = build_user_prompt(
        task=request.task,
        file_context=file_context,
    )

    client = OpenAIClient(settings)
    raw_response = client.generate_code(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    try:
        parsed = json.loads(raw_response)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI returned invalid JSON: {exc}",
        ) from exc

    try:
        return GenerateResponse(
            id=str(uuid.uuid4()),
            summary=parsed["summary"],
            python_code=parsed["python_code"],
            steps=parsed["steps"],
            tips=parsed["tips"],
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI response missing required field: {exc}",
        ) from exc
