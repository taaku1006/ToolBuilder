"""GET /api/models — available LLM model listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.config import Settings
from core.deps import get_settings
from eval.models import MODEL_PRICING
from pipeline.v2.config import STAGE_CONFIGS

router = APIRouter()


class ModelInfo(BaseModel):
    id: str
    provider: str
    display_name: str
    input_per_1m: float
    output_per_1m: float


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    default_model: str
    stage_defaults: dict[str, str]


def _detect_provider(model_id: str) -> str:
    if model_id.startswith("anthropic/"):
        return "anthropic"
    if model_id.startswith("gemini/") or model_id.startswith("vertex_ai/"):
        return "google"
    if model_id.startswith("ollama/"):
        return "ollama"
    return "openai"


def _display_name(model_id: str) -> str:
    return model_id.split("/")[-1] if "/" in model_id else model_id


def _available_models(settings: Settings) -> list[ModelInfo]:
    """Filter models based on configured API keys."""
    result: list[ModelInfo] = []
    for model_id, (inp, out) in MODEL_PRICING.items():
        provider = _detect_provider(model_id)
        if provider == "openai" and not settings.openai_api_key:
            continue
        if provider == "anthropic" and not settings.anthropic_api_key:
            continue
        if provider == "google" and not settings.gemini_api_key:
            continue
        # Ollama is always available (local)
        result.append(
            ModelInfo(
                id=model_id,
                provider=provider,
                display_name=_display_name(model_id),
                input_per_1m=inp,
                output_per_1m=out,
            )
        )
    return result


@router.get("/models")
async def list_models(
    settings: Settings = Depends(get_settings),
) -> ModelsResponse:
    return ModelsResponse(
        models=_available_models(settings),
        default_model=settings.active_model,
        stage_defaults={k: v["model"] for k, v in STAGE_CONFIGS.items()},
    )
