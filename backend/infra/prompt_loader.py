"""Shared prompt loader utility.

Consolidates the repeated _load_*_prompt() pattern from multiple services.
Tries prompt_manager.get_prompt (Langfuse) first when settings is provided,
falls back to reading from the local prompts/ directory.
"""

from __future__ import annotations

from pathlib import Path

from infra.prompt_manager import get_prompt

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str, settings=None) -> str:
    """Load a prompt template by name.

    Tries Langfuse first when settings is provided, falls back to local file.

    Args:
        name: Prompt name (without .txt extension).
        settings: Optional Settings instance. When provided, attempts to fetch
                  the prompt via prompt_manager.get_prompt (Langfuse). On any
                  exception, falls back to the local file.

    Returns:
        The prompt text content.

    Raises:
        FileNotFoundError: When settings is None (or get_prompt raises) and the
                           local file prompts/{name}.txt does not exist.
    """
    if settings is not None:
        try:
            return get_prompt(name, settings)
        except Exception:
            pass

    prompt_path = _PROMPTS_DIR / f"{name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path}"
        )
    return prompt_path.read_text(encoding="utf-8")
