"""Memory search — query patterns and gotchas by task type and file features.

Supports both keyword-based search (default) and semantic search (when an
Embedder is provided).
"""

from __future__ import annotations

from pathlib import Path

from memory.store import MemoryStore


def search_patterns(
    data_dir: Path,
    *,
    task_type: str = "",
    file_features: list[str] | None = None,
) -> list[dict]:
    """Search patterns matching task_type and/or file_features."""
    store = MemoryStore(data_dir)
    patterns = store.load_patterns()
    results: list[dict] = []

    for key, p in patterns.items():
        match = True

        if task_type and p.get("task_type") != task_type:
            match = False

        if file_features:
            stored_features = set(p.get("file_features", []))
            if not stored_features.intersection(file_features):
                match = False

        if match:
            results.append({**p, "_key": key})

    # Sort by quality_score descending
    results.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
    return results


def search_gotchas(
    data_dir: Path,
    *,
    file_features: list[str] | None = None,
) -> list[dict]:
    """Search gotchas matching file_features. Returns all if no filter."""
    store = MemoryStore(data_dir)
    gotchas = store.load_gotchas()
    results: list[dict] = []

    for key, g in gotchas.items():
        if file_features:
            # Match if the gotcha key is related to any file feature
            if key not in file_features:
                continue
        results.append({**g, "_key": key})

    # Sort by confidence descending
    results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return results


# ---------------------------------------------------------------------------
# Semantic search (embedding-based)
# ---------------------------------------------------------------------------


def search_patterns_semantic(
    data_dir: Path,
    *,
    query: str,
    embedder=None,
    file_features: list[str] | None = None,
    top_k: int = 5,
) -> list[dict]:
    """Search patterns by embedding similarity. Falls back to keyword search."""
    if embedder is None:
        return search_patterns(data_dir, file_features=file_features)

    from memory.embedder import cosine_similarity

    store = MemoryStore(data_dir)
    patterns = store.load_patterns()
    if not patterns:
        return []

    query_vec = embedder.embed(query)
    if not query_vec:
        return search_patterns(data_dir, file_features=file_features)

    scored: list[tuple[float, str, dict]] = []
    for key, p in patterns.items():
        # Build a text representation for the pattern
        text = f"{p.get('task_type', '')} {p.get('winning_strategy', {}).get('approach', '')} {' '.join(p.get('file_features', []))}"
        pattern_vec = embedder.embed(text)
        if pattern_vec:
            score = cosine_similarity(query_vec, pattern_vec)
            scored.append((score, key, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [{**p, "_key": key, "_similarity": score} for score, key, p in scored[:top_k]]


def search_gotchas_semantic(
    data_dir: Path,
    *,
    query: str,
    embedder=None,
    file_features: list[str] | None = None,
    top_k: int = 5,
) -> list[dict]:
    """Search gotchas by embedding similarity. Falls back to keyword search."""
    if embedder is None:
        return search_gotchas(data_dir, file_features=file_features)

    from memory.embedder import cosine_similarity

    store = MemoryStore(data_dir)
    gotchas = store.load_gotchas()
    if not gotchas:
        return []

    query_vec = embedder.embed(query)
    if not query_vec:
        return search_gotchas(data_dir, file_features=file_features)

    scored: list[tuple[float, str, dict]] = []
    for key, g in gotchas.items():
        text = f"{key} {g.get('detection', '')} {g.get('fix', '')}"
        gotcha_vec = embedder.embed(text)
        if gotcha_vec:
            score = cosine_similarity(query_vec, gotcha_vec)
            scored.append((score, key, g))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [{**g, "_key": key, "_similarity": score} for score, key, g in scored[:top_k]]
