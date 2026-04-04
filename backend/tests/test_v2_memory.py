"""Tests for memory/store.py and memory/search.py — RED phase."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def memory_dir(tmp_path):
    """Create a temporary memory data directory with empty JSON files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "patterns.json").write_text("{}")
    (data_dir / "gotchas.json").write_text("{}")
    (data_dir / "session_log.json").write_text("[]")
    return data_dir


class TestMemoryStore:
    def test_load_empty_patterns(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        assert store.load_patterns() == {}

    def test_load_empty_gotchas(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        assert store.load_gotchas() == {}

    def test_load_empty_session_log(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        assert store.load_session_log() == []

    def test_save_pattern(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_pattern(
            key="merged_cells_pivot",
            file_features=["merged_cells", "multi_sheet"],
            task_type="pivot",
            winning_strategy={"approach": "pandas", "preprocessing": ["unmerge_cells"]},
            quality_score=0.95,
        )
        patterns = store.load_patterns()
        assert "merged_cells_pivot" in patterns
        assert patterns["merged_cells_pivot"]["task_type"] == "pivot"
        assert patterns["merged_cells_pivot"]["quality_score"] == 0.95
        assert patterns["merged_cells_pivot"]["occurrences"] == 1

    def test_save_pattern_increments_occurrences(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        for _ in range(3):
            store.save_pattern(
                key="simple_sum",
                file_features=["single_sheet"],
                task_type="aggregation",
                winning_strategy={"approach": "pandas"},
                quality_score=0.9,
            )
        patterns = store.load_patterns()
        assert patterns["simple_sum"]["occurrences"] == 3

    def test_save_gotcha(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_gotcha(
            key="merged_cells",
            detection="openpyxl.cell.MergedCell type in cells",
            fix="ws.unmerge_cells() before reading values",
        )
        gotchas = store.load_gotchas()
        assert "merged_cells" in gotchas
        assert gotchas["merged_cells"]["fix"] == "ws.unmerge_cells() before reading values"
        assert gotchas["merged_cells"]["occurrences"] == 1

    def test_save_gotcha_increments_confidence(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        for _ in range(5):
            store.save_gotcha(
                key="pivot_nan",
                detection="NaN values after pivot_table",
                fix="fillna(0) after pivot",
            )
        gotchas = store.load_gotchas()
        assert gotchas["pivot_nan"]["occurrences"] == 5
        # Confidence should increase with more occurrences
        assert gotchas["pivot_nan"]["confidence"] > 0.5

    def test_save_session(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_session(
            task_type="pivot",
            complexity="standard",
            strategy="pandas",
            attempts=2,
            replan_count=0,
            final_score=0.9,
            passed=True,
        )
        log = store.load_session_log()
        assert len(log) == 1
        assert log[0]["task_type"] == "pivot"
        assert log[0]["passed"] is True

    def test_session_log_max_entries(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir, max_session_entries=5)
        for i in range(10):
            store.save_session(
                task_type=f"type_{i}",
                complexity="simple",
                strategy="pandas",
                attempts=1,
                replan_count=0,
                final_score=0.8,
                passed=True,
            )
        log = store.load_session_log()
        assert len(log) == 5
        # Should keep the latest 5
        assert log[-1]["task_type"] == "type_9"

    def test_persistence_across_instances(self, memory_dir):
        from memory.store import MemoryStore
        store1 = MemoryStore(memory_dir)
        store1.save_pattern(
            key="test_key", file_features=["a"], task_type="test",
            winning_strategy={"approach": "pandas"}, quality_score=0.8,
        )
        # New instance should see saved data
        store2 = MemoryStore(memory_dir)
        patterns = store2.load_patterns()
        assert "test_key" in patterns


class TestMemorySearch:
    def test_search_patterns_empty(self, memory_dir):
        from memory.search import search_patterns
        results = search_patterns(memory_dir, task_type="pivot", file_features=["merged_cells"])
        assert results == []

    def test_search_patterns_by_task_type(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_pattern(
            key="pivot_pattern", file_features=["multi_sheet"],
            task_type="pivot", winning_strategy={"approach": "pandas"},
            quality_score=0.9,
        )
        store.save_pattern(
            key="merge_pattern", file_features=["multi_sheet"],
            task_type="merge", winning_strategy={"approach": "pandas"},
            quality_score=0.85,
        )

        from memory.search import search_patterns
        results = search_patterns(memory_dir, task_type="pivot", file_features=[])
        assert len(results) == 1
        assert results[0]["task_type"] == "pivot"

    def test_search_patterns_by_file_features(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_pattern(
            key="p1", file_features=["merged_cells", "multi_sheet"],
            task_type="pivot", winning_strategy={}, quality_score=0.9,
        )
        store.save_pattern(
            key="p2", file_features=["single_sheet"],
            task_type="aggregation", winning_strategy={}, quality_score=0.8,
        )

        from memory.search import search_patterns
        results = search_patterns(memory_dir, task_type="", file_features=["merged_cells"])
        assert len(results) == 1

    def test_search_gotchas_by_features(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_gotcha(key="merged_cells", detection="MergedCell", fix="unmerge first")
        store.save_gotcha(key="pivot_nan", detection="NaN after pivot", fix="fillna(0)")

        from memory.search import search_gotchas
        results = search_gotchas(memory_dir, file_features=["merged_cells"])
        assert len(results) == 1
        assert results[0]["fix"] == "unmerge first"

    def test_search_gotchas_returns_all_when_no_filter(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_gotcha(key="g1", detection="d1", fix="f1")
        store.save_gotcha(key="g2", detection="d2", fix="f2")

        from memory.search import search_gotchas
        results = search_gotchas(memory_dir, file_features=[])
        assert len(results) == 2
