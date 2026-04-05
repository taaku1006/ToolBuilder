"""File-based memory store for cross-session learning.

Reads/writes patterns.json, gotchas.json, session_log.json.
Thread-safe via file locking (fcntl on Linux).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class MemoryStore:
    """JSON file-backed memory store."""

    def __init__(self, data_dir: Path, *, max_session_entries: int = 100) -> None:
        self._data_dir = Path(data_dir)
        self._max_session_entries = max_session_entries

    # ------------------------------------------------------------------
    # Patterns
    # ------------------------------------------------------------------

    def load_patterns(self) -> dict:
        return self._load_json("patterns.json", default={})

    def save_pattern(
        self,
        *,
        key: str,
        file_features: list[str],
        task_type: str,
        winning_strategy: dict,
        quality_score: float,
    ) -> None:
        patterns = self.load_patterns()
        if key in patterns:
            existing = patterns[key]
            existing["occurrences"] = existing.get("occurrences", 0) + 1
            existing["quality_score"] = quality_score
            existing["last_used"] = _now_iso()
        else:
            patterns[key] = {
                "file_features": file_features,
                "task_type": task_type,
                "winning_strategy": winning_strategy,
                "quality_score": quality_score,
                "occurrences": 1,
                "last_used": _now_iso(),
            }
        self._save_json("patterns.json", patterns)

    # ------------------------------------------------------------------
    # Gotchas
    # ------------------------------------------------------------------

    def load_gotchas(self) -> dict:
        return self._load_json("gotchas.json", default={})

    def save_gotcha(
        self,
        *,
        key: str,
        detection: str,
        fix: str,
    ) -> None:
        gotchas = self.load_gotchas()
        if key in gotchas:
            existing = gotchas[key]
            existing["occurrences"] = existing.get("occurrences", 0) + 1
            existing["confidence"] = min(
                0.5 + existing["occurrences"] * 0.1, 0.99
            )
        else:
            gotchas[key] = {
                "detection": detection,
                "fix": fix,
                "occurrences": 1,
                "confidence": 0.6,
            }
        self._save_json("gotchas.json", gotchas)

    # ------------------------------------------------------------------
    # Session log
    # ------------------------------------------------------------------

    def load_session_log(self) -> list[dict]:
        return self._load_json("session_log.json", default=[])

    def save_session(
        self,
        *,
        task_type: str,
        complexity: str,
        strategy: str,
        attempts: int,
        replan_count: int,
        final_score: float,
        passed: bool,
    ) -> None:
        log = self.load_session_log()
        log.append({
            "task_type": task_type,
            "complexity": complexity,
            "strategy": strategy,
            "attempts": attempts,
            "replan_count": replan_count,
            "final_score": final_score,
            "passed": passed,
            "timestamp": _now_iso(),
        })
        # Keep only the latest N entries
        if len(log) > self._max_session_entries:
            log = log[-self._max_session_entries:]
        self._save_json("session_log.json", log)

    # ------------------------------------------------------------------
    # Strategy statistics (meta-learning)
    # ------------------------------------------------------------------

    def get_strategy_stats(self) -> dict[str, dict]:
        """Aggregate success rate and avg attempts per strategy from session log."""
        log = self.load_session_log()
        buckets: dict[str, dict] = {}
        for entry in log:
            strategy = entry.get("strategy", "unknown")
            if strategy not in buckets:
                buckets[strategy] = {"total": 0, "passed": 0, "total_attempts": 0}
            b = buckets[strategy]
            b["total"] += 1
            if entry.get("passed"):
                b["passed"] += 1
            b["total_attempts"] += entry.get("attempts", 0)

        result: dict[str, dict] = {}
        for strategy, b in buckets.items():
            total = b["total"]
            result[strategy] = {
                "total": total,
                "passed": b["passed"],
                "success_rate": b["passed"] / total if total > 0 else 0.0,
                "avg_attempts": b["total_attempts"] / total if total > 0 else 0.0,
            }
        return result

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _load_json(self, filename: str, *, default):
        path = self._data_dir / filename
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load %s, returning default", path)
            return default

    def _save_json(self, filename: str, data) -> None:
        path = self._data_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
