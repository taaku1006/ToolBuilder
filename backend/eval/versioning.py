"""Prompt versioning for eval harness.

Captures snapshots of prompt files and architecture configs used in a run,
enabling diff tracking between runs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunSnapshot:
    """Frozen snapshot of prompts and architecture configs at a point in time."""

    prompt_hashes: dict[str, str]
    """SHA-256 hash per prompt key, e.g. {"phase_a": "abc123..."}."""

    prompt_contents: dict[str, str]
    """Full text of each prompt file, keyed by phase name."""

    architecture_configs: dict[str, dict]
    """Parsed JSON config per architecture id."""

    snapshot_hash: str
    """Combined SHA-256 hash of all prompts and configs for quick equality check."""

    def to_dict(self) -> dict:
        """Serialize to a plain dict (JSON-safe)."""
        return {
            "prompt_hashes": dict(self.prompt_hashes),
            "prompt_contents": dict(self.prompt_contents),
            "architecture_configs": {k: dict(v) for k, v in self.architecture_configs.items()},
            "snapshot_hash": self.snapshot_hash,
        }


@dataclass(frozen=True)
class SnapshotDiff:
    """Difference between two RunSnapshots."""

    changed_prompts: list[str]
    """Names of prompts that differ (added, removed, or content-changed)."""

    changed_configs: list[str]
    """Architecture IDs whose configs differ (added, removed, or content-changed)."""

    is_identical: bool
    """True when no prompts or configs changed."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(text: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8 encoded string."""
    return hashlib.sha256(text.encode()).hexdigest()


def _prompt_key_from_path(path: Path) -> str:
    """Derive a short prompt key from a filename.

    e.g. "phase_a_exploration.txt" → "phase_a"
         "phase_b_reflect.txt"    → "phase_b"
    """
    stem = path.stem  # strip extension
    # Keep only the first two underscore-separated parts: "phase_X"
    parts = stem.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}_{parts[1]}"
    return stem


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def capture_run_snapshot(
    *,
    prompt_dir: Path,
    arch_dir: Path,
) -> RunSnapshot:
    """Read all prompt files and architecture configs and return a frozen snapshot.

    Parameters
    ----------
    prompt_dir:
        Directory containing phase_*.txt prompt files.
    arch_dir:
        Directory containing *.json architecture config files.

    Raises
    ------
    FileNotFoundError
        If either directory does not exist.
    """
    if not prompt_dir.exists():
        raise FileNotFoundError(f"Prompt directory not found: {prompt_dir}")
    if not arch_dir.exists():
        raise FileNotFoundError(f"Architecture directory not found: {arch_dir}")

    # --- Collect prompt hashes and contents ---
    prompt_hashes: dict[str, str] = {}
    prompt_contents: dict[str, str] = {}

    for txt_path in sorted(prompt_dir.glob("*.txt")):
        content = txt_path.read_text(encoding="utf-8")
        key = _prompt_key_from_path(txt_path)
        prompt_hashes[key] = _sha256(content)
        prompt_contents[key] = content

    # --- Collect architecture configs ---
    architecture_configs: dict[str, dict] = {}

    for json_path in sorted(arch_dir.glob("*.json")):
        config = json.loads(json_path.read_text(encoding="utf-8"))
        arch_id = config.get("id", json_path.stem)
        architecture_configs[arch_id] = config

    # --- Compute combined snapshot hash ---
    # Canonically serialize everything so order does not matter
    combined_parts: list[str] = []
    for key in sorted(prompt_hashes):
        combined_parts.append(f"prompt:{key}:{prompt_hashes[key]}")
    for arch_id in sorted(architecture_configs):
        config_str = json.dumps(architecture_configs[arch_id], sort_keys=True, ensure_ascii=False)
        combined_parts.append(f"arch:{arch_id}:{_sha256(config_str)}")

    snapshot_hash = _sha256("\n".join(combined_parts))

    return RunSnapshot(
        prompt_hashes=prompt_hashes,
        prompt_contents=prompt_contents,
        architecture_configs=architecture_configs,
        snapshot_hash=snapshot_hash,
    )


def diff_snapshots(a: RunSnapshot, b: RunSnapshot) -> SnapshotDiff:
    """Return which prompts and configs differ between two snapshots.

    Additions and removals are treated as changes.
    """
    all_prompt_keys = set(a.prompt_hashes) | set(b.prompt_hashes)
    changed_prompts = sorted(
        key
        for key in all_prompt_keys
        if a.prompt_hashes.get(key) != b.prompt_hashes.get(key)
    )

    all_arch_ids = set(a.architecture_configs) | set(b.architecture_configs)
    changed_configs = sorted(
        arch_id
        for arch_id in all_arch_ids
        if json.dumps(a.architecture_configs.get(arch_id), sort_keys=True)
        != json.dumps(b.architecture_configs.get(arch_id), sort_keys=True)
    )

    return SnapshotDiff(
        changed_prompts=changed_prompts,
        changed_configs=changed_configs,
        is_identical=len(changed_prompts) == 0 and len(changed_configs) == 0,
    )
