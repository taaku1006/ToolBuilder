"""Unit tests for skills_engine module.

TDD order: tests written FIRST, implementation follows.
Tests cover compute_similarity and match_skills functions.
"""

from __future__ import annotations

import pytest

from services.skills_engine import SkillMatch, compute_similarity, match_skills


# ---------------------------------------------------------------------------
# compute_similarity tests
# ---------------------------------------------------------------------------


class TestComputeSimilarity:
    """Tests for compute_similarity function."""

    def test_identical_headers_and_task_returns_high_score(self) -> None:
        """Identical file headers and task text returns score close to 1.0."""
        headers = ["date", "product", "quantity", "price"]
        task = "aggregate sales by product"
        schema = '["date", "product", "quantity", "price"]'
        summary = "aggregate sales by product"
        score = compute_similarity(headers, task, schema, summary)
        assert score > 0.8

    def test_no_overlap_returns_zero(self) -> None:
        """No column overlap and no keyword overlap returns 0.0."""
        headers = ["alpha", "beta", "gamma"]
        task = "compute delta epsilon"
        schema = '["x", "y", "z"]'
        summary = "transform omega"
        score = compute_similarity(headers, task, schema, summary)
        assert score == pytest.approx(0.0)

    def test_partial_header_overlap_returns_medium_score(self) -> None:
        """Partial column overlap gives a score between 0 and 1."""
        headers = ["date", "product", "quantity"]
        task = "sum quantity"
        schema = '["date", "product", "revenue"]'
        summary = "sum revenue"
        score = compute_similarity(headers, task, schema, summary)
        assert 0.0 < score < 1.0

    def test_none_schema_uses_zero_jaccard(self) -> None:
        """When skill has no file_schema, Jaccard part is 0, keyword part drives score."""
        headers = ["date", "product"]
        task = "find product totals"
        score_with_schema = compute_similarity(headers, task, '["date", "product"]', "find product totals")
        score_without_schema = compute_similarity(headers, task, None, "find product totals")
        # Without schema, score should be lower (no Jaccard contribution)
        assert score_without_schema < score_with_schema

    def test_none_summary_uses_zero_keyword(self) -> None:
        """When skill has no task_summary, keyword part is 0, Jaccard part drives score."""
        headers = ["date", "product"]
        task = "find product totals"
        score_with_summary = compute_similarity(headers, task, '["date", "product"]', "find product totals")
        score_without_summary = compute_similarity(headers, task, '["date", "product"]', None)
        # Without summary, score should be lower (no keyword contribution)
        assert score_without_summary < score_with_summary

    def test_both_none_returns_zero(self) -> None:
        """When both skill_file_schema and skill_task_summary are None, returns 0.0."""
        score = compute_similarity(["a", "b"], "do something", None, None)
        assert score == pytest.approx(0.0)

    def test_empty_headers_with_matching_task(self) -> None:
        """Empty file headers results in zero Jaccard but keyword overlap still counts."""
        score = compute_similarity([], "aggregate data", None, "aggregate data")
        # No Jaccard (empty headers), but keyword overlap should be 1.0
        expected = pytest.approx(0.4 * 1.0)
        assert score == expected

    def test_return_type_is_float(self) -> None:
        """Return value is always a float."""
        score = compute_similarity(["a"], "task", '["a"]', "task")
        assert isinstance(score, float)

    def test_score_bounded_zero_to_one(self) -> None:
        """Score is always in [0.0, 1.0]."""
        for headers, task, schema, summary in [
            ([], "", None, None),
            (["x"], "x", '["x"]', "x"),
            (["a", "b"], "c d", '["e", "f"]', "g h"),
        ]:
            score = compute_similarity(headers, task, schema, summary)
            assert 0.0 <= score <= 1.0, f"Score out of bounds: {score}"

    def test_jaccard_formula(self) -> None:
        """Verify Jaccard similarity: intersection / union on column names."""
        # A = {a, b, c}, B = {b, c, d} -> intersection=2, union=4 -> 0.5
        headers = ["a", "b", "c"]
        schema = '["b", "c", "d"]'
        score = compute_similarity(headers, "", schema, None)
        assert score == pytest.approx(0.6 * 0.5, abs=1e-6)

    def test_keyword_overlap_formula(self) -> None:
        """Verify keyword overlap: matching words / total words in task."""
        # task = "find product totals" (3 words), summary has "product totals" (2 match)
        # overlap = 2/3
        headers = []
        task = "find product totals"
        summary = "product totals summary"
        score = compute_similarity(headers, task, None, summary)
        assert score == pytest.approx(0.4 * (2 / 3), abs=1e-6)

    def test_combined_weight(self) -> None:
        """Combined score uses 0.6 * jaccard + 0.4 * keyword."""
        # Jaccard = 1.0 (identical headers), keyword = 1.0 (identical task)
        headers = ["a", "b"]
        task = "do thing"
        schema = '["a", "b"]'
        summary = "do thing"
        score = compute_similarity(headers, task, schema, summary)
        assert score == pytest.approx(0.6 * 1.0 + 0.4 * 1.0, abs=1e-6)

    def test_case_insensitive_keyword_matching(self) -> None:
        """Keyword matching is case-insensitive."""
        score_lower = compute_similarity([], "aggregate data", None, "aggregate data")
        score_mixed = compute_similarity([], "Aggregate Data", None, "aggregate data")
        assert score_lower == pytest.approx(score_mixed, abs=1e-6)

    def test_empty_task_with_matching_headers(self) -> None:
        """Empty task text results in zero keyword overlap."""
        score = compute_similarity(["a", "b"], "", '["a", "b"]', None)
        # No keywords to match -> keyword overlap = 0
        # Jaccard = 1.0 -> score = 0.6 * 1.0 + 0.4 * 0
        assert score == pytest.approx(0.6, abs=1e-6)

    def test_schema_with_extra_whitespace(self) -> None:
        """Schema JSON with extra whitespace is parsed correctly."""
        score = compute_similarity(["a", "b"], "", '[ "a" , "b" ]', None)
        assert score == pytest.approx(0.6, abs=1e-6)


# ---------------------------------------------------------------------------
# match_skills tests
# ---------------------------------------------------------------------------


SAMPLE_SKILLS = [
    {
        "id": "skill-1",
        "title": "Sales Aggregation",
        "tags": '["sales", "aggregation"]',
        "file_schema": '["date", "product", "quantity", "price"]',
        "task_summary": "aggregate sales by product and date",
    },
    {
        "id": "skill-2",
        "title": "Customer Analysis",
        "tags": '["customer", "analysis"]',
        "file_schema": '["customer_id", "name", "email", "purchase"]',
        "task_summary": "analyze customer purchase behavior",
    },
    {
        "id": "skill-3",
        "title": "No Schema Skill",
        "tags": "[]",
        "file_schema": None,
        "task_summary": None,
    },
]


class TestMatchSkills:
    """Tests for match_skills function."""

    def test_returns_list(self) -> None:
        """match_skills always returns a list."""
        result = match_skills(["date"], "task", SAMPLE_SKILLS)
        assert isinstance(result, list)

    def test_all_items_are_skill_match(self) -> None:
        """All items in the result are SkillMatch instances."""
        result = match_skills(["date", "product"], "aggregate sales", SAMPLE_SKILLS)
        for item in result:
            assert isinstance(item, SkillMatch)

    def test_empty_skills_returns_empty(self) -> None:
        """Empty skill list returns empty result."""
        result = match_skills(["date"], "aggregate data", [])
        assert result == []

    def test_threshold_filters_low_scores(self) -> None:
        """Skills below threshold are excluded."""
        result = match_skills(
            ["totally", "unrelated", "headers"],
            "completely different task",
            SAMPLE_SKILLS,
            threshold=0.4,
        )
        # skill-3 has no schema/summary (score 0.0), others should also score low
        for item in result:
            assert item.similarity >= 0.4

    def test_high_similarity_skill_included(self) -> None:
        """Skill with high similarity is included in results."""
        headers = ["date", "product", "quantity", "price"]
        task = "aggregate sales by product and date"
        result = match_skills(headers, task, SAMPLE_SKILLS)
        ids = [m.skill_id for m in result]
        assert "skill-1" in ids

    def test_low_similarity_skill_excluded(self) -> None:
        """Skill with very low similarity is excluded."""
        headers = ["date", "product", "quantity", "price"]
        task = "aggregate sales by product and date"
        result = match_skills(headers, task, SAMPLE_SKILLS, threshold=0.4)
        ids = [m.skill_id for m in result]
        # skill-3 has no schema/summary so similarity=0.0
        assert "skill-3" not in ids

    def test_sorted_by_similarity_descending(self) -> None:
        """Results are sorted by similarity in descending order."""
        headers = ["date", "product", "quantity", "price"]
        task = "aggregate sales by product"
        result = match_skills(headers, task, SAMPLE_SKILLS)
        similarities = [m.similarity for m in result]
        assert similarities == sorted(similarities, reverse=True)

    def test_skill_match_fields(self) -> None:
        """SkillMatch has correct field values."""
        headers = ["date", "product", "quantity", "price"]
        task = "aggregate sales by product and date"
        result = match_skills(headers, task, SAMPLE_SKILLS)
        if result:
            match = next(m for m in result if m.skill_id == "skill-1")
            assert match.title == "Sales Aggregation"
            assert isinstance(match.tags, list)
            assert isinstance(match.similarity, float)

    def test_tags_parsed_from_json_string(self) -> None:
        """Tags are returned as a list even though stored as JSON string in DB."""
        headers = ["date", "product", "quantity", "price"]
        task = "aggregate sales"
        result = match_skills(headers, task, SAMPLE_SKILLS)
        for match in result:
            assert isinstance(match.tags, list)

    def test_custom_threshold(self) -> None:
        """Custom threshold changes filter behavior."""
        headers = ["date", "product"]
        task = "any task"
        result_strict = match_skills(headers, task, SAMPLE_SKILLS, threshold=0.9)
        result_loose = match_skills(headers, task, SAMPLE_SKILLS, threshold=0.0)
        assert len(result_loose) >= len(result_strict)

    def test_skill_match_is_frozen(self) -> None:
        """SkillMatch instances are immutable (frozen dataclass)."""
        match = SkillMatch(
            skill_id="x",
            title="T",
            tags=["a"],
            similarity=0.5,
        )
        with pytest.raises((AttributeError, TypeError)):
            match.skill_id = "y"  # type: ignore[misc]

    def test_empty_headers_still_matches_on_task(self) -> None:
        """Empty headers can still match based on task keyword overlap."""
        headers = []
        task = "aggregate sales by product and date"
        result = match_skills(headers, task, SAMPLE_SKILLS, threshold=0.1)
        # skill-1 has "aggregate sales" in summary -> some keyword match
        ids = [m.skill_id for m in result]
        assert "skill-1" in ids

    def test_empty_task_still_matches_on_headers(self) -> None:
        """Empty task can still match based on header Jaccard similarity."""
        headers = ["date", "product", "quantity", "price"]
        task = ""
        result = match_skills(headers, task, SAMPLE_SKILLS, threshold=0.1)
        ids = [m.skill_id for m in result]
        # skill-1 shares headers -> Jaccard > 0
        assert "skill-1" in ids

    def test_similarity_value_is_float(self) -> None:
        """similarity field in SkillMatch is a float."""
        headers = ["date"]
        task = "task"
        result = match_skills(headers, task, SAMPLE_SKILLS)
        for match in result:
            assert isinstance(match.similarity, float)
