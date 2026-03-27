"""Integration tests for /api/history CRUD endpoints.

TDD order: tests written FIRST, implementation follows.
Uses in-memory SQLite for isolation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import Settings
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
def history_client(
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

SAMPLE_HISTORY = {
    "task": "売上データの集計",
    "python_code": "print('hello')",
    "summary": "テスト用サマリー",
    "steps": ["ステップ1", "ステップ2"],
    "tips": "テストヒント",
    "file_name": "data.xlsx",
    "exec_stdout": "hello",
    "exec_stderr": "",
}


def _create_history(client: TestClient, payload: dict | None = None) -> dict:
    """Helper: POST /api/history and return the created item."""
    body = payload or SAMPLE_HISTORY
    resp = client.post("/api/history", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/history
# ---------------------------------------------------------------------------


class TestHistoryCreate:
    """Tests for POST /api/history."""

    def test_create_returns_201(self, history_client: TestClient) -> None:
        """Creating a history item returns HTTP 201."""
        resp = history_client.post("/api/history", json=SAMPLE_HISTORY)
        assert resp.status_code == 201

    def test_create_returns_id(self, history_client: TestClient) -> None:
        """Created item has an id field."""
        item = _create_history(history_client)
        assert "id" in item
        assert len(item["id"]) > 0

    def test_create_id_is_uuid(self, history_client: TestClient) -> None:
        """Created item id is a valid UUID."""
        import re

        item = _create_history(history_client)
        uuid_re = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        assert uuid_re.match(item["id"]), f"Not a UUID: {item['id']}"

    def test_create_returns_task(self, history_client: TestClient) -> None:
        """Created item echoes back the task."""
        item = _create_history(history_client)
        assert item["task"] == SAMPLE_HISTORY["task"]

    def test_create_returns_python_code(self, history_client: TestClient) -> None:
        """Created item echoes back python_code."""
        item = _create_history(history_client)
        assert item["python_code"] == SAMPLE_HISTORY["python_code"]

    def test_create_with_minimal_fields(self, history_client: TestClient) -> None:
        """Only required fields (task, python_code) are sufficient."""
        resp = history_client.post(
            "/api/history",
            json={"task": "minimal task", "python_code": "pass"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["task"] == "minimal task"

    def test_create_steps_as_list(self, history_client: TestClient) -> None:
        """steps is returned as a list."""
        item = _create_history(history_client)
        assert isinstance(item["steps"], list)
        assert item["steps"] == SAMPLE_HISTORY["steps"]

    def test_create_missing_required_returns_422(
        self, history_client: TestClient
    ) -> None:
        """Missing required field python_code returns 422."""
        resp = history_client.post(
            "/api/history",
            json={"task": "no code"},
        )
        assert resp.status_code == 422

    def test_two_creates_have_different_ids(self, history_client: TestClient) -> None:
        """Two created items must have distinct ids."""
        item1 = _create_history(history_client)
        item2 = _create_history(history_client)
        assert item1["id"] != item2["id"]


# ---------------------------------------------------------------------------
# GET /api/history
# ---------------------------------------------------------------------------


class TestHistoryList:
    """Tests for GET /api/history."""

    def test_empty_list(self, history_client: TestClient) -> None:
        """Returns empty list when no history exists."""
        resp = history_client.get("/api/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_after_create(self, history_client: TestClient) -> None:
        """After creating one item, list returns it."""
        _create_history(history_client)
        resp = history_client.get("/api/history")
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_list_total_matches_items(self, history_client: TestClient) -> None:
        """total field matches the number of items."""
        _create_history(history_client)
        _create_history(history_client)
        _create_history(history_client)
        resp = history_client.get("/api/history")
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_search_by_task(self, history_client: TestClient) -> None:
        """?q= searches by task text."""
        history_client.post(
            "/api/history",
            json={"task": "売上データ集計", "python_code": "pass"},
        )
        history_client.post(
            "/api/history",
            json={"task": "顧客データ分析", "python_code": "pass"},
        )

        resp = history_client.get("/api/history?q=売上")
        data = resp.json()

        assert data["total"] == 1
        assert data["items"][0]["task"] == "売上データ集計"

    def test_search_no_match_returns_empty(self, history_client: TestClient) -> None:
        """?q= with no match returns empty list."""
        _create_history(history_client)
        resp = history_client.get("/api/history?q=存在しない検索語")
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_search_empty_q_returns_all(self, history_client: TestClient) -> None:
        """?q= with empty string returns all items."""
        _create_history(history_client)
        _create_history(history_client)
        resp = history_client.get("/api/history?q=")
        data = resp.json()
        assert data["total"] == 2

    def test_list_items_have_required_fields(self, history_client: TestClient) -> None:
        """Each item in the list has required fields."""
        _create_history(history_client)
        resp = history_client.get("/api/history")
        item = resp.json()["items"][0]

        assert "id" in item
        assert "task" in item
        assert "python_code" in item
        assert "created_at" in item


# ---------------------------------------------------------------------------
# GET /api/history/{id}
# ---------------------------------------------------------------------------


class TestHistoryGet:
    """Tests for GET /api/history/{id}."""

    def test_get_existing_returns_200(self, history_client: TestClient) -> None:
        """Getting an existing item returns HTTP 200."""
        created = _create_history(history_client)
        resp = history_client.get(f"/api/history/{created['id']}")
        assert resp.status_code == 200

    def test_get_existing_returns_correct_item(
        self, history_client: TestClient
    ) -> None:
        """Getting an existing item returns the correct data."""
        created = _create_history(history_client)
        resp = history_client.get(f"/api/history/{created['id']}")
        data = resp.json()

        assert data["id"] == created["id"]
        assert data["task"] == SAMPLE_HISTORY["task"]
        assert data["python_code"] == SAMPLE_HISTORY["python_code"]

    def test_get_nonexistent_returns_404(self, history_client: TestClient) -> None:
        """Getting a non-existent id returns HTTP 404."""
        resp = history_client.get("/api/history/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_get_steps_is_list(self, history_client: TestClient) -> None:
        """steps field in single item is a list."""
        created = _create_history(history_client)
        resp = history_client.get(f"/api/history/{created['id']}")
        data = resp.json()

        assert isinstance(data["steps"], list)


# ---------------------------------------------------------------------------
# DELETE /api/history/{id}
# ---------------------------------------------------------------------------


class TestHistoryDelete:
    """Tests for DELETE /api/history/{id}."""

    def test_delete_existing_returns_204(self, history_client: TestClient) -> None:
        """Deleting an existing item returns HTTP 204."""
        created = _create_history(history_client)
        resp = history_client.delete(f"/api/history/{created['id']}")
        assert resp.status_code == 204

    def test_delete_removes_item(self, history_client: TestClient) -> None:
        """After deletion, the item is no longer retrievable."""
        created = _create_history(history_client)
        history_client.delete(f"/api/history/{created['id']}")

        resp = history_client.get(f"/api/history/{created['id']}")
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, history_client: TestClient) -> None:
        """Deleting a non-existent item returns HTTP 404."""
        resp = history_client.delete(
            "/api/history/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    def test_delete_reduces_list_count(self, history_client: TestClient) -> None:
        """After deletion, list count decreases by 1."""
        item1 = _create_history(history_client)
        _create_history(history_client)

        history_client.delete(f"/api/history/{item1['id']}")

        resp = history_client.get("/api/history")
        assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# PATCH /api/history/{id} — update memo
# ---------------------------------------------------------------------------


class TestHistoryUpdateMemo:
    """Tests for PATCH /api/history/{id}."""

    def test_patch_memo_returns_200(self, history_client: TestClient) -> None:
        """Patching memo returns HTTP 200."""
        created = _create_history(history_client)
        resp = history_client.patch(
            f"/api/history/{created['id']}",
            json={"memo": "updated memo"},
        )
        assert resp.status_code == 200

    def test_patch_memo_updates_value(self, history_client: TestClient) -> None:
        """Patching memo updates the memo field."""
        created = _create_history(history_client)
        history_client.patch(
            f"/api/history/{created['id']}",
            json={"memo": "my new memo"},
        )

        resp = history_client.get(f"/api/history/{created['id']}")
        assert resp.json()["memo"] == "my new memo"

    def test_patch_nonexistent_returns_404(self, history_client: TestClient) -> None:
        """Patching a non-existent item returns 404."""
        resp = history_client.patch(
            "/api/history/00000000-0000-0000-0000-000000000000",
            json={"memo": "hello"},
        )
        assert resp.status_code == 404

    def test_patch_missing_memo_returns_422(self, history_client: TestClient) -> None:
        """Patching with missing memo field returns 422."""
        created = _create_history(history_client)
        resp = history_client.patch(
            f"/api/history/{created['id']}",
            json={},
        )
        assert resp.status_code == 422

    def test_patch_memo_empty_string(self, history_client: TestClient) -> None:
        """Memo can be set to empty string."""
        created = _create_history(history_client)
        resp = history_client.patch(
            f"/api/history/{created['id']}",
            json={"memo": ""},
        )
        assert resp.status_code == 200
        resp2 = history_client.get(f"/api/history/{created['id']}")
        assert resp2.json()["memo"] == ""

    def test_patch_does_not_change_other_fields(
        self, history_client: TestClient
    ) -> None:
        """Patching memo must not change task or python_code."""
        created = _create_history(history_client)
        history_client.patch(
            f"/api/history/{created['id']}",
            json={"memo": "changed"},
        )

        resp = history_client.get(f"/api/history/{created['id']}")
        data = resp.json()
        assert data["task"] == SAMPLE_HISTORY["task"]
        assert data["python_code"] == SAMPLE_HISTORY["python_code"]
