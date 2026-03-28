"""Tests for eval.versioning — prompt/config snapshot capture and diffing.

TDD RED phase: defines the expected versioning API before implementation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from eval.versioning import (
    RunSnapshot,
    SnapshotDiff,
    capture_run_snapshot,
    diff_snapshots,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def prompt_dir(tmp_path: Path) -> Path:
    """Create a temporary prompts directory with phase files."""
    p = tmp_path / "prompts"
    p.mkdir()
    (p / "phase_a_exploration.txt").write_text("Phase A content", encoding="utf-8")
    (p / "phase_b_reflect.txt").write_text("Phase B content", encoding="utf-8")
    (p / "phase_c_generate.txt").write_text("Phase C content", encoding="utf-8")
    (p / "phase_d_debug.txt").write_text("Phase D content", encoding="utf-8")
    return p


@pytest.fixture
def arch_dir(tmp_path: Path) -> Path:
    """Create a temporary architectures directory with JSON configs."""
    a = tmp_path / "architectures"
    a.mkdir()
    (a / "v1_baseline.json").write_text(
        json.dumps({"id": "v1_baseline", "model": "gpt-4o", "phases": ["A", "B", "C", "D", "E"]}),
        encoding="utf-8",
    )
    (a / "v2_skip_b.json").write_text(
        json.dumps({"id": "v2_skip_b", "model": "gpt-4o", "phases": ["A", "C", "D", "E"]}),
        encoding="utf-8",
    )
    return a


@pytest.fixture
def snapshot(prompt_dir: Path, arch_dir: Path) -> RunSnapshot:
    """Capture a real snapshot from temp dirs."""
    return capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)


# ---------------------------------------------------------------------------
# RunSnapshot dataclass
# ---------------------------------------------------------------------------


class TestRunSnapshotStructure:
    def test_snapshot_has_prompt_hashes(self, snapshot: RunSnapshot) -> None:
        assert isinstance(snapshot.prompt_hashes, dict)
        assert len(snapshot.prompt_hashes) > 0

    def test_snapshot_has_prompt_contents(self, snapshot: RunSnapshot) -> None:
        assert isinstance(snapshot.prompt_contents, dict)
        assert len(snapshot.prompt_contents) > 0

    def test_snapshot_has_architecture_configs(self, snapshot: RunSnapshot) -> None:
        assert isinstance(snapshot.architecture_configs, dict)
        assert len(snapshot.architecture_configs) > 0

    def test_snapshot_has_snapshot_hash(self, snapshot: RunSnapshot) -> None:
        assert isinstance(snapshot.snapshot_hash, str)
        assert len(snapshot.snapshot_hash) == 64  # SHA-256 hex digest

    def test_snapshot_is_frozen(self, snapshot: RunSnapshot) -> None:
        """RunSnapshot must be immutable (frozen dataclass)."""
        with pytest.raises((AttributeError, TypeError)):
            snapshot.snapshot_hash = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# capture_run_snapshot — prompt hashes
# ---------------------------------------------------------------------------


class TestCaptureRunSnapshotPrompts:
    def test_captures_all_phase_prompts(self, snapshot: RunSnapshot) -> None:
        """All four phase prompts should be captured."""
        expected_keys = {"phase_a", "phase_b", "phase_c", "phase_d"}
        assert set(snapshot.prompt_hashes.keys()) == expected_keys

    def test_prompt_hashes_are_sha256(self, snapshot: RunSnapshot, prompt_dir: Path) -> None:
        """Each prompt hash must match the SHA-256 of the file content."""
        content = (prompt_dir / "phase_a_exploration.txt").read_text(encoding="utf-8")
        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        assert snapshot.prompt_hashes["phase_a"] == expected_hash

    def test_prompt_contents_match_files(self, snapshot: RunSnapshot, prompt_dir: Path) -> None:
        """prompt_contents must hold the full text of each prompt file."""
        assert snapshot.prompt_contents["phase_a"] == "Phase A content"
        assert snapshot.prompt_contents["phase_b"] == "Phase B content"
        assert snapshot.prompt_contents["phase_c"] == "Phase C content"
        assert snapshot.prompt_contents["phase_d"] == "Phase D content"

    def test_prompt_keys_use_short_names(self, snapshot: RunSnapshot) -> None:
        """Keys must be phase_a/b/c/d, not the full filename."""
        for key in snapshot.prompt_hashes:
            assert not key.endswith(".txt")
            assert not key.startswith("phase_a_exploration")


# ---------------------------------------------------------------------------
# capture_run_snapshot — architecture configs
# ---------------------------------------------------------------------------


class TestCaptureRunSnapshotArchitectures:
    def test_captures_all_architecture_configs(self, snapshot: RunSnapshot) -> None:
        """All architecture JSON files should be captured."""
        assert "v1_baseline" in snapshot.architecture_configs
        assert "v2_skip_b" in snapshot.architecture_configs

    def test_architecture_config_values_are_dicts(self, snapshot: RunSnapshot) -> None:
        """Each config value must be a parsed dict."""
        for arch_id, config in snapshot.architecture_configs.items():
            assert isinstance(config, dict), f"{arch_id} config is not a dict"

    def test_architecture_config_content_matches(
        self, snapshot: RunSnapshot, arch_dir: Path
    ) -> None:
        """Config dict must match the parsed JSON file."""
        raw = json.loads((arch_dir / "v1_baseline.json").read_text(encoding="utf-8"))
        assert snapshot.architecture_configs["v1_baseline"] == raw


# ---------------------------------------------------------------------------
# capture_run_snapshot — snapshot_hash
# ---------------------------------------------------------------------------


class TestCaptureRunSnapshotHash:
    def test_snapshot_hash_is_deterministic(
        self, prompt_dir: Path, arch_dir: Path
    ) -> None:
        """Same input → same snapshot_hash."""
        snap1 = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)
        snap2 = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)
        assert snap1.snapshot_hash == snap2.snapshot_hash

    def test_snapshot_hash_changes_when_prompt_changes(
        self, prompt_dir: Path, arch_dir: Path
    ) -> None:
        snap1 = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)
        (prompt_dir / "phase_a_exploration.txt").write_text(
            "CHANGED Phase A content", encoding="utf-8"
        )
        snap2 = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)
        assert snap1.snapshot_hash != snap2.snapshot_hash

    def test_snapshot_hash_changes_when_arch_changes(
        self, prompt_dir: Path, arch_dir: Path
    ) -> None:
        snap1 = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)
        (arch_dir / "v1_baseline.json").write_text(
            json.dumps({"id": "v1_baseline", "model": "gpt-4o-mini", "phases": ["C"]}),
            encoding="utf-8",
        )
        snap2 = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)
        assert snap1.snapshot_hash != snap2.snapshot_hash


# ---------------------------------------------------------------------------
# capture_run_snapshot — edge cases
# ---------------------------------------------------------------------------


class TestCaptureRunSnapshotEdgeCases:
    def test_empty_prompt_dir(self, tmp_path: Path, arch_dir: Path) -> None:
        """An empty prompts directory produces empty prompt_hashes."""
        empty = tmp_path / "empty_prompts"
        empty.mkdir()
        snap = capture_run_snapshot(prompt_dir=empty, arch_dir=arch_dir)
        assert snap.prompt_hashes == {}
        assert snap.prompt_contents == {}

    def test_empty_arch_dir(self, prompt_dir: Path, tmp_path: Path) -> None:
        """An empty architectures directory produces empty architecture_configs."""
        empty = tmp_path / "empty_archs"
        empty.mkdir()
        snap = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=empty)
        assert snap.architecture_configs == {}

    def test_missing_prompt_dir_raises(self, tmp_path: Path, arch_dir: Path) -> None:
        """A non-existent prompt directory raises FileNotFoundError."""
        missing = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            capture_run_snapshot(prompt_dir=missing, arch_dir=arch_dir)

    def test_missing_arch_dir_raises(self, prompt_dir: Path, tmp_path: Path) -> None:
        """A non-existent arch directory raises FileNotFoundError."""
        missing = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=missing)

    def test_unicode_prompt_content(self, tmp_path: Path, arch_dir: Path) -> None:
        """Prompts with Unicode/emoji content are hashed correctly."""
        p = tmp_path / "unicode_prompts"
        p.mkdir()
        (p / "phase_a_exploration.txt").write_text(
            "日本語テスト 🎉 prompt", encoding="utf-8"
        )
        snap = capture_run_snapshot(prompt_dir=p, arch_dir=arch_dir)
        assert "phase_a" in snap.prompt_hashes
        expected = hashlib.sha256("日本語テスト 🎉 prompt".encode()).hexdigest()
        assert snap.prompt_hashes["phase_a"] == expected

    def test_to_dict_is_json_serializable(self, snapshot: RunSnapshot) -> None:
        """snapshot.to_dict() must produce a JSON-serializable dict."""
        d = snapshot.to_dict()
        serialized = json.dumps(d)  # must not raise
        assert isinstance(serialized, str)

    def test_to_dict_contains_required_keys(self, snapshot: RunSnapshot) -> None:
        d = snapshot.to_dict()
        assert "prompt_hashes" in d
        assert "prompt_contents" in d
        assert "architecture_configs" in d
        assert "snapshot_hash" in d


# ---------------------------------------------------------------------------
# diff_snapshots
# ---------------------------------------------------------------------------


class TestDiffSnapshots:
    def test_identical_snapshots_produce_empty_diff(self, snapshot: RunSnapshot) -> None:
        diff = diff_snapshots(snapshot, snapshot)
        assert diff.is_identical is True
        assert diff.changed_prompts == []
        assert diff.changed_configs == []

    def test_diff_detects_changed_prompt(
        self, prompt_dir: Path, arch_dir: Path
    ) -> None:
        snap_a = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)
        (prompt_dir / "phase_c_generate.txt").write_text("New Phase C", encoding="utf-8")
        snap_b = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)

        diff = diff_snapshots(snap_a, snap_b)
        assert diff.is_identical is False
        assert "phase_c" in diff.changed_prompts
        assert diff.changed_configs == []

    def test_diff_detects_changed_config(
        self, prompt_dir: Path, arch_dir: Path
    ) -> None:
        snap_a = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)
        (arch_dir / "v2_skip_b.json").write_text(
            json.dumps({"id": "v2_skip_b", "model": "gpt-4o-mini", "phases": ["C"]}),
            encoding="utf-8",
        )
        snap_b = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)

        diff = diff_snapshots(snap_a, snap_b)
        assert diff.is_identical is False
        assert "v2_skip_b" in diff.changed_configs
        assert diff.changed_prompts == []

    def test_diff_detects_multiple_changes(
        self, prompt_dir: Path, arch_dir: Path
    ) -> None:
        snap_a = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)
        (prompt_dir / "phase_a_exploration.txt").write_text("new A", encoding="utf-8")
        (prompt_dir / "phase_b_reflect.txt").write_text("new B", encoding="utf-8")
        (arch_dir / "v1_baseline.json").write_text(
            json.dumps({"id": "v1_baseline", "model": "gpt-4-turbo"}),
            encoding="utf-8",
        )
        snap_b = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)

        diff = diff_snapshots(snap_a, snap_b)
        assert "phase_a" in diff.changed_prompts
        assert "phase_b" in diff.changed_prompts
        assert "v1_baseline" in diff.changed_configs
        assert diff.is_identical is False

    def test_diff_detects_added_prompt(
        self, prompt_dir: Path, arch_dir: Path
    ) -> None:
        """A prompt present in b but not in a should appear as changed."""
        snap_a = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)
        (prompt_dir / "phase_e_new.txt").write_text("Brand new phase", encoding="utf-8")
        snap_b = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)

        diff = diff_snapshots(snap_a, snap_b)
        # "phase_e" is new in b, not in a — must be flagged
        assert "phase_e" in diff.changed_prompts
        assert diff.is_identical is False

    def test_diff_detects_removed_prompt(
        self, prompt_dir: Path, arch_dir: Path
    ) -> None:
        """A prompt in a but missing from b should appear as changed."""
        snap_a = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)
        (prompt_dir / "phase_d_debug.txt").unlink()
        snap_b = capture_run_snapshot(prompt_dir=prompt_dir, arch_dir=arch_dir)

        diff = diff_snapshots(snap_a, snap_b)
        assert "phase_d" in diff.changed_prompts
        assert diff.is_identical is False

    def test_diff_is_frozen(self, snapshot: RunSnapshot) -> None:
        """SnapshotDiff must be immutable."""
        diff = diff_snapshots(snapshot, snapshot)
        with pytest.raises((AttributeError, TypeError)):
            diff.is_identical = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SnapshotDiff dataclass
# ---------------------------------------------------------------------------


class TestSnapshotDiffStructure:
    def test_snapshot_diff_fields(self, snapshot: RunSnapshot) -> None:
        diff = diff_snapshots(snapshot, snapshot)
        assert hasattr(diff, "changed_prompts")
        assert hasattr(diff, "changed_configs")
        assert hasattr(diff, "is_identical")

    def test_changed_prompts_is_list(self, snapshot: RunSnapshot) -> None:
        diff = diff_snapshots(snapshot, snapshot)
        assert isinstance(diff.changed_prompts, list)

    def test_changed_configs_is_list(self, snapshot: RunSnapshot) -> None:
        diff = diff_snapshots(snapshot, snapshot)
        assert isinstance(diff.changed_configs, list)


# ---------------------------------------------------------------------------
# Integration: save/load snapshot.json via to_dict / from_dict
# ---------------------------------------------------------------------------


class TestSnapshotSerialization:
    def test_roundtrip_via_to_dict(self, snapshot: RunSnapshot) -> None:
        """to_dict must produce enough data to reconstruct a matching snapshot_hash."""
        d = snapshot.to_dict()
        assert d["snapshot_hash"] == snapshot.snapshot_hash

    def test_prompt_hashes_preserved_in_dict(self, snapshot: RunSnapshot) -> None:
        d = snapshot.to_dict()
        assert d["prompt_hashes"] == snapshot.prompt_hashes

    def test_architecture_configs_preserved_in_dict(self, snapshot: RunSnapshot) -> None:
        d = snapshot.to_dict()
        assert d["architecture_configs"] == snapshot.architecture_configs
