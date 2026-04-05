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

    # ---------------------------------------------------------------
    # Phase 3: Meta-Learning — Strategy Statistics
    # ---------------------------------------------------------------

    def test_strategy_stats_empty(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        stats = store.get_strategy_stats()
        assert stats == {}

    def test_strategy_stats_basic(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_session(task_type="pivot", complexity="standard", strategy="pandas", attempts=2, replan_count=0, final_score=0.9, passed=True)
        store.save_session(task_type="merge", complexity="standard", strategy="pandas", attempts=4, replan_count=1, final_score=0.5, passed=False)
        store.save_session(task_type="sum", complexity="simple", strategy="openpyxl", attempts=1, replan_count=0, final_score=1.0, passed=True)

        stats = store.get_strategy_stats()
        assert "pandas" in stats
        assert "openpyxl" in stats
        assert stats["pandas"]["total"] == 2
        assert stats["pandas"]["passed"] == 1
        assert stats["pandas"]["success_rate"] == 0.5
        assert stats["pandas"]["avg_attempts"] == 3.0
        assert stats["openpyxl"]["success_rate"] == 1.0

    def test_memory_context_includes_strategy_stats(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_session(task_type="pivot", complexity="standard", strategy="pandas", attempts=2, replan_count=0, final_score=0.9, passed=True)
        store.save_session(task_type="merge", complexity="standard", strategy="openpyxl", attempts=1, replan_count=0, final_score=1.0, passed=True)

        from pipeline.v2.models import MemoryContext
        ctx = MemoryContext(
            patterns=[], gotchas=[],
            strategy_stats=store.get_strategy_stats(),
        )
        prompt = ctx.to_prompt()
        assert "pandas" in prompt
        assert "openpyxl" in prompt
        assert "成功率" in prompt or "success" in prompt.lower()

    # ---------------------------------------------------------------
    # Existing tests
    # ---------------------------------------------------------------

    # ---------------------------------------------------------------
    # Phase 4: Semantic Search (with mock embedder)
    # ---------------------------------------------------------------

    def test_semantic_search_patterns_by_similarity(self, memory_dir):
        """Patterns should be ranked by embedding similarity when embedder is available."""
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_pattern(
            key="p_pivot", file_features=["multi_sheet"],
            task_type="pivot", winning_strategy={"approach": "pandas"},
            quality_score=0.9,
        )
        store.save_pattern(
            key="p_sum", file_features=["single_sheet"],
            task_type="aggregation", winning_strategy={"approach": "openpyxl"},
            quality_score=0.8,
        )

        from memory.embedder import Embedder
        from unittest.mock import MagicMock

        # Mock embedder: "pivot" query is closer to p_pivot than p_sum
        mock_embedder = MagicMock(spec=Embedder)
        mock_embedder.embed.side_effect = lambda text: (
            [1.0, 0.0] if "pivot" in text or "ピボット" in text else [0.0, 1.0]
        )

        from memory.search import search_patterns_semantic
        results = search_patterns_semantic(
            memory_dir, query="月別にピボット集計", embedder=mock_embedder,
        )
        assert len(results) >= 1
        # The pivot pattern should rank higher (closer embedding)
        assert results[0]["task_type"] == "pivot"

    def test_semantic_search_gotchas_by_similarity(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_gotcha(key="merged_cells", detection="MergedCell error", fix="unmerge first")
        store.save_gotcha(key="encoding_error", detection="UnicodeDecodeError", fix="use cp932")

        from memory.embedder import Embedder
        from unittest.mock import MagicMock

        mock_embedder = MagicMock(spec=Embedder)
        mock_embedder.embed.side_effect = lambda text: (
            [1.0, 0.0] if "merge" in text.lower() or "マージ" in text else [0.0, 1.0]
        )

        from memory.search import search_gotchas_semantic
        results = search_gotchas_semantic(
            memory_dir, query="マージセルの処理", embedder=mock_embedder,
        )
        assert len(results) >= 1
        assert results[0]["_key"] == "merged_cells"

    def test_semantic_search_fallback_to_keyword(self, memory_dir):
        """When embedder is None, semantic search falls back to keyword search."""
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_pattern(
            key="p1", file_features=["merged_cells"],
            task_type="pivot", winning_strategy={}, quality_score=0.9,
        )

        from memory.search import search_patterns_semantic
        results = search_patterns_semantic(
            memory_dir, query="pivot", embedder=None, file_features=["merged_cells"],
        )
        assert len(results) == 1

    # ---------------------------------------------------------------
    # Existing tests
    # ---------------------------------------------------------------

    def test_search_gotchas_returns_all_when_no_filter(self, memory_dir):
        from memory.store import MemoryStore
        store = MemoryStore(memory_dir)
        store.save_gotcha(key="g1", detection="d1", fix="f1")
        store.save_gotcha(key="g2", detection="d2", fix="f2")

        from memory.search import search_gotchas
        results = search_gotchas(memory_dir, file_features=[])
        assert len(results) == 2
