"""Memory search — query patterns and gotchas by task type and file features."""

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
