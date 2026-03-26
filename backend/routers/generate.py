"""POST /api/generate router."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException

from core.config import Settings
from core.deps import get_settings
from core.exceptions import AppError
from schemas.generate import GenerateRequest, GenerateResponse
from services.openai_client import OpenAIClient
from services.prompt_builder import SYSTEM_PROMPT, build_user_prompt

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
def generate(
    request: GenerateRequest,
    settings: Settings = Depends(get_settings),
) -> GenerateResponse:
    """Generate Python code for Excel processing from a natural language task."""
    user_prompt = build_user_prompt(
        task=request.task,
        file_context=None,
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
