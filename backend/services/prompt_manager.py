"""Prompt management with Langfuse integration.

When Langfuse is enabled, prompts are fetched from Langfuse (with file fallback).
When disabled, prompts are read directly from prompts/*.txt files.

On first run with Langfuse enabled, file prompts are automatically seeded
into Langfuse so they can be edited from the Langfuse UI.
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.config import Settings

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Mapping: prompt name → file name
PROMPT_FILES = {
    "phase_a_exploration": "phase_a_exploration.txt",
    "phase_b_reflect": "phase_b_reflect.txt",
    "phase_c_generate": "phase_c_generate.txt",
    "phase_d_debug": "phase_d_debug.txt",
    "phase_p_plan": "phase_p_plan.txt",
    "phase_p_subtask": "phase_p_subtask.txt",
    "phase_p_replan": "phase_p_replan.txt",
    "phase_c_subtask": "phase_c_subtask.txt",
    "eval_agent": "eval_agent.txt",
    "phase_f_eval_debug": "phase_f_eval_debug.txt",
}

_langfuse_client = None


def _get_langfuse(settings: Settings):
    """Get or create the Langfuse client (cached)."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client
    if not settings.langfuse_enabled:
        return None
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        return _langfuse_client
    except Exception:
        logger.warning("Failed to init Langfuse for prompt management", exc_info=True)
        return None


def _read_file_prompt(name: str) -> str:
    """Read prompt from local file."""
    filename = PROMPT_FILES.get(name)
    if not filename:
        raise ValueError(f"Unknown prompt name: {name}")
    path = _PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def seed_prompts(settings: Settings) -> None:
    """Register file-based prompts in Langfuse if they don't exist yet.

    Safe to call multiple times — skips prompts that already exist.
    """
    lf = _get_langfuse(settings)
    if lf is None:
        return

    for name, filename in PROMPT_FILES.items():
        try:
            # Check if prompt already exists
            lf.get_prompt(name)
            logger.debug(f"Prompt '{name}' already exists in Langfuse")
        except Exception:
            # Doesn't exist → create it
            try:
                content = _read_file_prompt(name)
                lf.create_prompt(
                    name=name,
                    prompt=content,
                    labels=["production"],
                    config={"source": "file_seed"},
                )
                logger.info(f"Seeded prompt '{name}' into Langfuse")
            except Exception:
                logger.warning(f"Failed to seed prompt '{name}'", exc_info=True)

    try:
        lf.flush()
    except Exception:
        pass


def get_prompt(name: str, settings: Settings) -> str:
    """Fetch a prompt by name.

    Priority: Langfuse (production label) → local file fallback.
    """
    if settings.langfuse_enabled:
        lf = _get_langfuse(settings)
        if lf is not None:
            try:
                prompt_obj = lf.get_prompt(name)
                content = prompt_obj.prompt
                if content:
                    return content
            except Exception:
                logger.debug(f"Prompt '{name}' not found in Langfuse, using file fallback")

    return _read_file_prompt(name)
