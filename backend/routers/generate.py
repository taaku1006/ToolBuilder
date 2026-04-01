"""POST /api/generate router."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from core.config import Settings
from core.deps import get_settings
from schemas.generate import AgentLogEntry as AgentLogEntrySchema
from schemas.generate import GenerateRequest, GenerateResponse
from infra.openai_client import OpenAIClient
from infra.prompt_builder import SYSTEM_PROMPT, build_user_prompt
from excel.xlsx_parser import SheetInfo, build_file_context, parse_file

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


def _build_sync_response(
    request: GenerateRequest,
    settings: Settings,
    agent_log: list[AgentLogEntrySchema] | None = None,
    reflection_steps: int = 0,
) -> GenerateResponse:
    """Shared logic: call OpenAI and build a GenerateResponse synchronously."""
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
        logger.error("OpenAI returned invalid JSON", extra={"error": str(exc)})
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
            agent_log=agent_log or [],
            reflection_steps=reflection_steps,
        )
    except KeyError as exc:
        logger.error("OpenAI response missing field", extra={"field": str(exc)})
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI response missing required field: {exc}",
        ) from exc


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    raw_request: Request,
    request: GenerateRequest,
    settings: Settings = Depends(get_settings),
) -> GenerateResponse | StreamingResponse:
    """Generate Python code — JSON or SSE streaming based on Accept header."""
    accept = raw_request.headers.get("accept", "")
    streaming = "text/event-stream" in accept
    logger.info(
        "Generate request",
        extra={"task_length": len(request.task), "file_id": request.file_id, "streaming": streaming},
    )

    if streaming:
        return _sse_response(request, settings)

    # Default: synchronous JSON response (backward compatible)
    return _build_sync_response(request, settings)


def _sse_response(request: GenerateRequest, settings: Settings) -> StreamingResponse:
    """Return an SSE StreamingResponse that streams orchestration progress."""

    async def event_stream():  # noqa: ANN202
        from pipeline.agent_orchestrator import orchestrate

        async for entry in orchestrate(
            task=request.task,
            file_id=request.file_id,
            settings=settings,
        ):
            # Build a flat dict for each event; always include phase
            event_dict: dict = {
                "phase": entry.phase,
                "action": entry.action,
                "timestamp": entry.timestamp,
            }

            # For the final result entry (phase=C, action=complete), also merge
            # the parsed content fields so python_code is accessible at top-level
            if entry.phase == "C" and entry.action == "complete":
                try:
                    content_parsed = json.loads(entry.content)
                    event_dict.update(content_parsed)
                except (json.JSONDecodeError, ValueError):
                    event_dict["content"] = entry.content
            else:
                event_dict["content"] = entry.content

            yield f"data: {json.dumps(event_dict, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
