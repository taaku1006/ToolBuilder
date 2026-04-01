"""Skills matching engine.

Computes similarity between an uploaded file + task and stored skill records
using Jaccard similarity on column names and keyword overlap on task text.

Combined score: 0.6 * jaccard + 0.4 * keyword
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillMatch:
    """Immutable result of matching a skill against a file + task."""

    skill_id: str
    title: str
    tags: list[str]
    similarity: float


def _parse_schema_headers(schema_json: str | None) -> set[str]:
    """Parse a JSON array string of column names into a lowercase set.

    Returns an empty set when schema_json is None or unparseable.
    """
    if not schema_json:
        return set()
    try:
        parsed = json.loads(schema_json)
        if isinstance(parsed, list):
            return {str(col).lower().strip() for col in parsed if col is not None}
    except (json.JSONDecodeError, TypeError):
        pass
    return set()


def _jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity: |intersection| / |union|.

    Returns 0.0 when both sets are empty.
    """
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _keyword_overlap(task_text: str, summary: str | None) -> float:
    """Compute keyword overlap: matching words / total words in task_text.

    Comparison is case-insensitive. Returns 0.0 when task_text is empty or
    summary is None.
    """
    if not task_text or not summary:
        return 0.0

    task_words = set(task_text.lower().split())
    if not task_words:
        return 0.0

    summary_words = set(summary.lower().split())
    overlap = task_words & summary_words
    return len(overlap) / len(task_words)


def compute_similarity(
    file_headers: list[str],
    task_text: str,
    skill_file_schema: str | None,
    skill_task_summary: str | None,
) -> float:
    """Compute combined similarity score in [0.0, 1.0].

    Uses:
    - Jaccard similarity on lowercase column name sets (weight 0.6)
    - Keyword overlap on task text vs skill task_summary (weight 0.4)

    Args:
        file_headers: Column names from the uploaded file.
        task_text: The natural-language task description entered by the user.
        skill_file_schema: JSON array string of column names stored in the skill.
        skill_task_summary: Free-text task summary stored in the skill.

    Returns:
        Combined similarity score between 0.0 and 1.0.
    """
    header_set = {h.lower().strip() for h in file_headers if h}
    skill_header_set = _parse_schema_headers(skill_file_schema)

    jaccard_score = _jaccard(header_set, skill_header_set)
    keyword_score = _keyword_overlap(task_text, skill_task_summary)

    return 0.6 * jaccard_score + 0.4 * keyword_score


def match_skills(
    file_headers: list[str],
    task_text: str,
    skills: list[dict],
    threshold: float = 0.4,
) -> list[SkillMatch]:
    """Return skills exceeding the similarity threshold, sorted by score descending.

    Args:
        file_headers: Column names from the uploaded file.
        task_text: The natural-language task description.
        skills: List of skill records from the database (dicts with at minimum
                id, title, tags, file_schema, task_summary keys).
        threshold: Minimum similarity score to include a skill (default 0.4).

    Returns:
        List of SkillMatch instances sorted by similarity descending.
    """
    results: list[SkillMatch] = []

    for skill in skills:
        score = compute_similarity(
            file_headers=file_headers,
            task_text=task_text,
            skill_file_schema=skill.get("file_schema"),
            skill_task_summary=skill.get("task_summary"),
        )

        if score < threshold:
            continue

        # Parse tags from JSON string stored in DB
        raw_tags = skill.get("tags") or "[]"
        try:
            tags: list[str] = json.loads(raw_tags) if isinstance(raw_tags, str) else raw_tags
            if not isinstance(tags, list):
                tags = []
        except (json.JSONDecodeError, TypeError):
            tags = []

        results.append(
            SkillMatch(
                skill_id=skill["id"],
                title=skill.get("title", ""),
                tags=[str(t) for t in tags],
                similarity=float(score),
            )
        )

    return sorted(results, key=lambda m: m.similarity, reverse=True)
