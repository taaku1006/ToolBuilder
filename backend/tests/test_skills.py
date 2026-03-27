"""Integration tests for /api/skills CRUD endpoints.

TDD order: tests written FIRST, implementation follows.
Uses in-memory SQLite for isolation.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.engine import Base, get_db


# ---------------------------------------------------------------------------
# In-memory DB fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine():
    """Create an in-memory SQLite engine with all tables."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    """Return an async_sessionmaker bound to the in-memory engine."""
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
def skills_client(
    test_session_factory,
    mock_openai_client: MagicMock,
) -> TestClient:
    """TestClient with in-memory DB injected via dependency override."""
    from main import app

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_SKILL = {
    "title": "Sales Aggregation Tool",
    "tags": ["sales", "aggregation", "excel"],
    "python_code": "import openpyxl\nprint('aggregate')",
    "file_schema": '["date", "product", "quantity", "price"]',
    "task_summary": "aggregate sales by product and date",
    "source_history_id": None,
}


def _create_skill(client: TestClient, payload: dict | None = None) -> dict:
    """Helper: POST /api/skills and return the created item."""
    body = payload or SAMPLE_SKILL
    resp = client.post("/api/skills", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/skills
# ---------------------------------------------------------------------------


class TestSkillsCreate:
    """Tests for POST /api/skills."""

    def test_create_returns_201(self, skills_client: TestClient) -> None:
        """Creating a skill returns HTTP 201."""
        resp = skills_client.post("/api/skills", json=SAMPLE_SKILL)
        assert resp.status_code == 201

    def test_create_returns_id(self, skills_client: TestClient) -> None:
        """Created skill has an id field."""
        item = _create_skill(skills_client)
        assert "id" in item
        assert len(item["id"]) > 0

    def test_create_id_is_uuid(self, skills_client: TestClient) -> None:
        """Created skill id is a valid UUID."""
        import re

        item = _create_skill(skills_client)
        uuid_re = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        assert uuid_re.match(item["id"]), f"Not a UUID: {item['id']}"

    def test_create_returns_title(self, skills_client: TestClient) -> None:
        """Created skill echoes back the title."""
        item = _create_skill(skills_client)
        assert item["title"] == SAMPLE_SKILL["title"]

    def test_create_returns_tags_as_list(self, skills_client: TestClient) -> None:
        """Created skill returns tags as a list."""
        item = _create_skill(skills_client)
        assert isinstance(item["tags"], list)
        assert item["tags"] == SAMPLE_SKILL["tags"]

    def test_create_returns_python_code(self, skills_client: TestClient) -> None:
        """Created skill echoes back python_code."""
        item = _create_skill(skills_client)
        assert item["python_code"] == SAMPLE_SKILL["python_code"]

    def test_create_defaults_use_count_zero(self, skills_client: TestClient) -> None:
        """Newly created skill has use_count of 0."""
        item = _create_skill(skills_client)
        assert item["use_count"] == 0

    def test_create_defaults_success_rate_one(self, skills_client: TestClient) -> None:
        """Newly created skill has success_rate of 1.0."""
        item = _create_skill(skills_client)
        assert item["success_rate"] == pytest.approx(1.0)

    def test_create_has_created_at(self, skills_client: TestClient) -> None:
        """Created skill has a created_at timestamp."""
        item = _create_skill(skills_client)
        assert "created_at" in item
        assert item["created_at"] is not None

    def test_create_with_empty_tags(self, skills_client: TestClient) -> None:
        """Skill can be created with empty tags list."""
        payload = {**SAMPLE_SKILL, "tags": []}
        item = _create_skill(skills_client, payload)
        assert item["tags"] == []

    def test_create_with_no_file_schema(self, skills_client: TestClient) -> None:
        """Skill can be created without file_schema."""
        payload = {**SAMPLE_SKILL, "file_schema": None}
        item = _create_skill(skills_client, payload)
        assert item["file_schema"] is None

    def test_create_with_no_task_summary(self, skills_client: TestClient) -> None:
        """Skill can be created without task_summary."""
        payload = {**SAMPLE_SKILL, "task_summary": None}
        item = _create_skill(skills_client, payload)
        assert item["task_summary"] is None

    def test_create_missing_title_returns_422(self, skills_client: TestClient) -> None:
        """Missing title field returns 422."""
        resp = skills_client.post(
            "/api/skills",
            json={"python_code": "pass"},
        )
        assert resp.status_code == 422

    def test_create_missing_python_code_returns_422(
        self, skills_client: TestClient
    ) -> None:
        """Missing python_code field returns 422."""
        resp = skills_client.post(
            "/api/skills",
            json={"title": "some skill"},
        )
        assert resp.status_code == 422

    def test_two_creates_have_different_ids(self, skills_client: TestClient) -> None:
        """Two created skills have distinct ids."""
        item1 = _create_skill(skills_client)
        item2 = _create_skill(skills_client)
        assert item1["id"] != item2["id"]


# ---------------------------------------------------------------------------
# GET /api/skills
# ---------------------------------------------------------------------------


class TestSkillsList:
    """Tests for GET /api/skills."""

    def test_empty_list(self, skills_client: TestClient) -> None:
        """Returns empty list when no skills exist."""
        resp = skills_client.get("/api/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_after_create(self, skills_client: TestClient) -> None:
        """After creating one skill, list returns it."""
        _create_skill(skills_client)
        resp = skills_client.get("/api/skills")
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_list_total_matches_items(self, skills_client: TestClient) -> None:
        """total field matches the number of items."""
        _create_skill(skills_client)
        _create_skill(skills_client)
        _create_skill(skills_client)
        resp = skills_client.get("/api/skills")
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_items_have_required_fields(self, skills_client: TestClient) -> None:
        """Each item in the list has required fields."""
        _create_skill(skills_client)
        resp = skills_client.get("/api/skills")
        item = resp.json()["items"][0]

        assert "id" in item
        assert "title" in item
        assert "python_code" in item
        assert "created_at" in item
        assert "tags" in item
        assert "use_count" in item
        assert "success_rate" in item

    def test_list_tags_are_lists(self, skills_client: TestClient) -> None:
        """Tags in listed items are lists, not raw JSON strings."""
        _create_skill(skills_client)
        resp = skills_client.get("/api/skills")
        item = resp.json()["items"][0]
        assert isinstance(item["tags"], list)


# ---------------------------------------------------------------------------
# GET /api/skills/{id}
# ---------------------------------------------------------------------------


class TestSkillsGet:
    """Tests for GET /api/skills/{id}."""

    def test_get_existing_returns_200(self, skills_client: TestClient) -> None:
        """Getting an existing skill returns HTTP 200."""
        created = _create_skill(skills_client)
        resp = skills_client.get(f"/api/skills/{created['id']}")
        assert resp.status_code == 200

    def test_get_existing_returns_correct_item(
        self, skills_client: TestClient
    ) -> None:
        """Getting an existing skill returns the correct data."""
        created = _create_skill(skills_client)
        resp = skills_client.get(f"/api/skills/{created['id']}")
        data = resp.json()

        assert data["id"] == created["id"]
        assert data["title"] == SAMPLE_SKILL["title"]
        assert data["python_code"] == SAMPLE_SKILL["python_code"]

    def test_get_nonexistent_returns_404(self, skills_client: TestClient) -> None:
        """Getting a non-existent id returns HTTP 404."""
        resp = skills_client.get("/api/skills/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_get_tags_is_list(self, skills_client: TestClient) -> None:
        """tags field in single item is a list."""
        created = _create_skill(skills_client)
        resp = skills_client.get(f"/api/skills/{created['id']}")
        data = resp.json()
        assert isinstance(data["tags"], list)


# ---------------------------------------------------------------------------
# DELETE /api/skills/{id}
# ---------------------------------------------------------------------------


class TestSkillsDelete:
    """Tests for DELETE /api/skills/{id}."""

    def test_delete_existing_returns_204(self, skills_client: TestClient) -> None:
        """Deleting an existing skill returns HTTP 204."""
        created = _create_skill(skills_client)
        resp = skills_client.delete(f"/api/skills/{created['id']}")
        assert resp.status_code == 204

    def test_delete_removes_item(self, skills_client: TestClient) -> None:
        """After deletion, the skill is no longer retrievable."""
        created = _create_skill(skills_client)
        skills_client.delete(f"/api/skills/{created['id']}")

        resp = skills_client.get(f"/api/skills/{created['id']}")
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, skills_client: TestClient) -> None:
        """Deleting a non-existent skill returns HTTP 404."""
        resp = skills_client.delete(
            "/api/skills/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    def test_delete_reduces_list_count(self, skills_client: TestClient) -> None:
        """After deletion, list count decreases by 1."""
        item1 = _create_skill(skills_client)
        _create_skill(skills_client)

        skills_client.delete(f"/api/skills/{item1['id']}")

        resp = skills_client.get("/api/skills")
        assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# POST /api/skills/{id}/use
# ---------------------------------------------------------------------------


class TestSkillsUse:
    """Tests for POST /api/skills/{id}/use."""

    def test_use_existing_returns_200(self, skills_client: TestClient) -> None:
        """Using a skill returns HTTP 200."""
        created = _create_skill(skills_client)
        resp = skills_client.post(f"/api/skills/{created['id']}/use")
        assert resp.status_code == 200

    def test_use_increments_use_count(self, skills_client: TestClient) -> None:
        """Using a skill increments use_count by 1."""
        created = _create_skill(skills_client)
        assert created["use_count"] == 0

        skills_client.post(f"/api/skills/{created['id']}/use")
        resp = skills_client.get(f"/api/skills/{created['id']}")
        assert resp.json()["use_count"] == 1

    def test_use_multiple_times_accumulates(self, skills_client: TestClient) -> None:
        """Multiple uses accumulate use_count."""
        created = _create_skill(skills_client)

        for _ in range(3):
            skills_client.post(f"/api/skills/{created['id']}/use")

        resp = skills_client.get(f"/api/skills/{created['id']}")
        assert resp.json()["use_count"] == 3

    def test_use_with_success_true_keeps_rate(
        self, skills_client: TestClient
    ) -> None:
        """Using with success=true keeps success_rate at 1.0 if first use."""
        created = _create_skill(skills_client)
        skills_client.post(
            f"/api/skills/{created['id']}/use",
            json={"success": True},
        )
        resp = skills_client.get(f"/api/skills/{created['id']}")
        assert resp.json()["success_rate"] == pytest.approx(1.0)

    def test_use_with_success_false_reduces_rate(
        self, skills_client: TestClient
    ) -> None:
        """Using with success=false reduces success_rate."""
        created = _create_skill(skills_client)
        # First: use once with success=True to establish base
        skills_client.post(
            f"/api/skills/{created['id']}/use",
            json={"success": True},
        )
        # Second: use with failure
        skills_client.post(
            f"/api/skills/{created['id']}/use",
            json={"success": False},
        )
        resp = skills_client.get(f"/api/skills/{created['id']}")
        # After 1 success + 1 failure -> success_rate = 0.5
        assert resp.json()["success_rate"] == pytest.approx(0.5)

    def test_use_nonexistent_returns_404(self, skills_client: TestClient) -> None:
        """Using a non-existent skill returns 404."""
        resp = skills_client.post(
            "/api/skills/00000000-0000-0000-0000-000000000000/use"
        )
        assert resp.status_code == 404

    def test_use_returns_updated_skill(self, skills_client: TestClient) -> None:
        """POST /use returns the updated skill data."""
        created = _create_skill(skills_client)
        resp = skills_client.post(f"/api/skills/{created['id']}/use")
        data = resp.json()
        assert data["use_count"] == 1
        assert "id" in data
        assert "title" in data
