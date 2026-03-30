"""Tests for eval API endpoints: POST /api/eval/test-cases and DELETE /api/eval/test-cases/{id}.

TDD RED phase: these tests define the expected API before implementation.
"""

from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import openpyxl
import pytest
from fastapi.testclient import TestClient

from core.config import Settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_xlsx_bytes() -> bytes:
    """Create a minimal xlsx file in memory and return its bytes."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["id", "value"])
    ws.append([1, 100])
    ws.append([2, 200])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def eval_settings(tmp_path: Path) -> Settings:
    """Settings with isolated upload and eval dirs inside tmp_path."""
    return Settings(
        openai_api_key="test-api-key-12345",
        openai_model="gpt-4o",
        cors_origins="http://localhost:5173",
        upload_dir=str(tmp_path / "uploads"),
    )


@pytest.fixture
def eval_cases_dir(tmp_path: Path) -> Path:
    """Temporary directory that acts as the eval test_cases directory."""
    d = tmp_path / "eval" / "test_cases"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def eval_client(
    eval_settings: Settings,
    eval_cases_dir: Path,
) -> TestClient:
    """TestClient for the eval router, isolated to tmp dirs."""
    from core.deps import get_settings
    from main import app

    app.dependency_overrides[get_settings] = lambda: eval_settings

    # Patch the eval router's _CASES_DIR to use the tmp dir
    with patch("routers.eval._CASES_DIR", eval_cases_dir):
        with TestClient(app) as client:
            yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/eval/test-cases — create without file
# ---------------------------------------------------------------------------


class TestCreateTestCase:
    """POST /api/eval/test-cases creates a new test case JSON."""

    def test_create_test_case_minimal(self, eval_client: TestClient, eval_cases_dir: Path) -> None:
        """Create a test case with only task and description (no file)."""
        resp = eval_client.post(
            "/api/eval/test-cases",
            data={
                "task": "売上を集計してください",
                "description": "Basic aggregation task",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["task"] == "売上を集計してください"
        assert body["description"] == "Basic aggregation task"
        assert body["file_path"] is None
        assert body["expected_success"] is True
        assert "id" in body

        # Should create a JSON file in eval_cases_dir
        case_id = body["id"]
        json_file = eval_cases_dir / f"{case_id}.json"
        assert json_file.exists(), f"Expected {json_file} to exist"
        saved = json.loads(json_file.read_text(encoding="utf-8"))
        assert saved["id"] == case_id
        assert saved["task"] == "売上を集計してください"

    def test_create_test_case_returns_unique_id(self, eval_client: TestClient) -> None:
        """Each created test case gets a unique ID."""
        r1 = eval_client.post(
            "/api/eval/test-cases",
            data={"task": "task A", "description": "d"},
        )
        r2 = eval_client.post(
            "/api/eval/test-cases",
            data={"task": "task B", "description": "d"},
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]

    def test_create_test_case_missing_task_returns_422(self, eval_client: TestClient) -> None:
        """Missing 'task' field should return 422."""
        resp = eval_client.post(
            "/api/eval/test-cases",
            data={"description": "no task provided"},
        )
        assert resp.status_code == 422

    def test_create_test_case_empty_task_returns_422(self, eval_client: TestClient) -> None:
        """Empty 'task' string should return 422."""
        resp = eval_client.post(
            "/api/eval/test-cases",
            data={"task": "   ", "description": "whitespace only"},
        )
        assert resp.status_code == 422

    def test_created_test_case_appears_in_list(self, eval_client: TestClient) -> None:
        """A newly created test case should appear in GET /api/eval/test-cases."""
        create_resp = eval_client.post(
            "/api/eval/test-cases",
            data={"task": "new task", "description": "desc"},
        )
        assert create_resp.status_code == 201
        new_id = create_resp.json()["id"]

        list_resp = eval_client.get("/api/eval/test-cases")
        assert list_resp.status_code == 200
        ids = [c["id"] for c in list_resp.json()]
        assert new_id in ids


# ---------------------------------------------------------------------------
# POST /api/eval/test-cases — create with file upload
# ---------------------------------------------------------------------------


class TestCreateTestCaseWithFile:
    """POST /api/eval/test-cases with an xlsx file attachment."""

    def test_create_with_xlsx_file(
        self, eval_client: TestClient, eval_cases_dir: Path, eval_settings: Settings
    ) -> None:
        """Create a test case with an xlsx file — file saved and path recorded."""
        xlsx_bytes = _make_xlsx_bytes()
        resp = eval_client.post(
            "/api/eval/test-cases",
            data={"task": "列Aでグループ化", "description": "with file"},
            files={"file": ("test.xlsx", xlsx_bytes, "application/octet-stream")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["file_path"] is not None

        # The referenced file should exist on disk
        file_path = Path(body["file_path"])
        assert file_path.exists(), f"Expected file at {file_path}"

    def test_create_with_xlsx_stores_in_files_subdir(
        self, eval_client: TestClient, eval_cases_dir: Path
    ) -> None:
        """The uploaded file should be saved inside eval_cases_dir/files/."""
        xlsx_bytes = _make_xlsx_bytes()
        resp = eval_client.post(
            "/api/eval/test-cases",
            data={"task": "任意のタスク", "description": "store location"},
            files={"file": ("data.xlsx", xlsx_bytes, "application/octet-stream")},
        )
        assert resp.status_code == 201
        file_path = Path(resp.json()["file_path"])
        # Parent dir must be eval_cases_dir/files
        assert file_path.parent == eval_cases_dir / "files"

    def test_create_with_non_xlsx_returns_400(self, eval_client: TestClient) -> None:
        """Non-Excel file upload should be rejected with 400."""
        resp = eval_client.post(
            "/api/eval/test-cases",
            data={"task": "タスク", "description": "bad file"},
            files={"file": ("notes.txt", b"some text", "text/plain")},
        )
        assert resp.status_code == 400

    def test_created_with_file_path_appears_in_list(
        self, eval_client: TestClient
    ) -> None:
        """Test case with file should appear in list with file_path set."""
        xlsx_bytes = _make_xlsx_bytes()
        create_resp = eval_client.post(
            "/api/eval/test-cases",
            data={"task": "file task", "description": "desc"},
            files={"file": ("sales.xlsx", xlsx_bytes, "application/octet-stream")},
        )
        assert create_resp.status_code == 201
        new_id = create_resp.json()["id"]

        list_resp = eval_client.get("/api/eval/test-cases")
        cases = {c["id"]: c for c in list_resp.json()}
        assert new_id in cases
        assert cases[new_id]["file_path"] is not None


# ---------------------------------------------------------------------------
# DELETE /api/eval/test-cases/{id}
# ---------------------------------------------------------------------------


class TestDeleteTestCase:
    """DELETE /api/eval/test-cases/{id} removes a test case."""

    def test_delete_existing_test_case(
        self, eval_client: TestClient, eval_cases_dir: Path
    ) -> None:
        """Deleting a created test case should return 204 and remove JSON file."""
        create_resp = eval_client.post(
            "/api/eval/test-cases",
            data={"task": "to be deleted", "description": "temp"},
        )
        assert create_resp.status_code == 201
        case_id = create_resp.json()["id"]

        del_resp = eval_client.delete(f"/api/eval/test-cases/{case_id}")
        assert del_resp.status_code == 204

        # JSON file should be gone
        json_file = eval_cases_dir / f"{case_id}.json"
        assert not json_file.exists()

    def test_delete_removes_from_list(
        self, eval_client: TestClient
    ) -> None:
        """After deletion, the test case should not appear in list."""
        create_resp = eval_client.post(
            "/api/eval/test-cases",
            data={"task": "will be gone", "description": ""},
        )
        case_id = create_resp.json()["id"]

        eval_client.delete(f"/api/eval/test-cases/{case_id}")

        list_resp = eval_client.get("/api/eval/test-cases")
        ids = [c["id"] for c in list_resp.json()]
        assert case_id not in ids

    def test_delete_with_file_removes_file_too(
        self, eval_client: TestClient, eval_cases_dir: Path
    ) -> None:
        """Deleting a test case with a file attachment should also remove the file."""
        xlsx_bytes = _make_xlsx_bytes()
        create_resp = eval_client.post(
            "/api/eval/test-cases",
            data={"task": "with attachment", "description": ""},
            files={"file": ("attach.xlsx", xlsx_bytes, "application/octet-stream")},
        )
        assert create_resp.status_code == 201
        body = create_resp.json()
        case_id = body["id"]
        file_path = Path(body["file_path"])
        assert file_path.exists()

        del_resp = eval_client.delete(f"/api/eval/test-cases/{case_id}")
        assert del_resp.status_code == 204
        assert not file_path.exists()

    def test_delete_nonexistent_returns_404(self, eval_client: TestClient) -> None:
        """Deleting a non-existent ID should return 404."""
        fake_id = "nonexistent_case_xyz"
        resp = eval_client.delete(f"/api/eval/test-cases/{fake_id}")
        assert resp.status_code == 404

    def test_delete_predefined_json_case(
        self, eval_client: TestClient, eval_cases_dir: Path
    ) -> None:
        """Should also be able to delete pre-defined test cases (JSON seeded cases)."""
        # Seed a pre-defined case directly
        case_data = {
            "id": "case_seed",
            "task": "seeded task",
            "description": "from fixture",
            "expected_success": True,
        }
        seed_file = eval_cases_dir / "case_seed.json"
        seed_file.write_text(json.dumps(case_data), encoding="utf-8")

        del_resp = eval_client.delete("/api/eval/test-cases/case_seed")
        assert del_resp.status_code == 204
        assert not seed_file.exists()


# ---------------------------------------------------------------------------
# Runner file_id integration: TestCase with file_path
# ---------------------------------------------------------------------------


class TestRunnerFileIdIntegration:
    """When a test case has file_path, runner passes a correct file_id to orchestrate()."""

    @pytest.mark.asyncio
    async def test_run_single_passes_file_id_when_file_path_set(
        self, tmp_path: Path
    ) -> None:
        """run_single() should copy/link the test-case file into upload_dir and pass file_id."""
        import openpyxl
        from unittest.mock import AsyncMock, patch, MagicMock

        from eval.models import ArchitectureConfig, TestCase
        from eval.runner import EvalRunner

        # Create real xlsx in a "test_cases/files" location
        xlsx_dir = tmp_path / "eval" / "test_cases" / "files"
        xlsx_dir.mkdir(parents=True)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["col"])
        ws.append([1])
        fpath = xlsx_dir / "test_file.xlsx"
        wb.save(str(fpath))

        arch = ArchitectureConfig(id="v1")
        case = TestCase(
            id="case_file",
            task="process file",
            description="",
            file_path=str(fpath),
        )

        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()

        called_with: dict = {}

        async def mock_orchestrate(task, file_id, settings, expected_file_path=None):
            called_with["file_id"] = file_id
            entry = MagicMock()
            entry.phase = "C"
            entry.action = "complete"
            entry.content = json.dumps({
                "python_code": "pass",
                "summary": "s",
                "steps": [],
                "tips": "",
                "debug_retries": 0,
            })
            entry.timestamp = "2026-03-28T00:00:00+00:00"
            yield entry

        def make_settings(overrides=None):
            s = MagicMock()
            s.upload_dir = str(upload_dir)
            s.exec_timeout = 30
            s.reflection_enabled = True
            s.debug_loop_enabled = True
            s.debug_retry_limit = 3
            s.skills_enabled = True
            if overrides:
                for k, v in overrides.items():
                    setattr(s, k, v)
            return s

        runner = EvalRunner(
            architectures=[arch],
            test_cases=[case],
            settings_factory=make_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            result = await runner.run_single(arch, case)

        # file_id must be non-None
        assert called_with.get("file_id") is not None, "file_id should be set when file_path is present"

        # The file must exist in upload_dir with the expected file_id prefix
        file_id = called_with["file_id"]
        matching = list(upload_dir.glob(f"{file_id}_*.xlsx"))
        assert len(matching) == 1, f"Expected one file in upload_dir with prefix {file_id}"

    @pytest.mark.asyncio
    async def test_run_single_passes_none_file_id_when_no_file(
        self, tmp_path: Path
    ) -> None:
        """run_single() should pass file_id=None when test case has no file."""
        from unittest.mock import MagicMock, patch

        from eval.models import ArchitectureConfig, TestCase
        from eval.runner import EvalRunner

        arch = ArchitectureConfig(id="v1")
        case = TestCase(id="c_nofile", task="no file task", description="")

        called_with: dict = {}

        async def mock_orchestrate(task, file_id, settings, expected_file_path=None):
            called_with["file_id"] = file_id
            entry = MagicMock()
            entry.phase = "C"
            entry.action = "complete"
            entry.content = json.dumps({
                "python_code": "pass",
                "summary": "s",
                "steps": [],
                "tips": "",
                "debug_retries": 0,
            })
            entry.timestamp = "2026-03-28T00:00:00+00:00"
            yield entry

        def make_settings(overrides=None):
            s = MagicMock()
            s.upload_dir = str(tmp_path / "uploads")
            s.exec_timeout = 30
            if overrides:
                for k, v in overrides.items():
                    setattr(s, k, v)
            return s

        runner = EvalRunner(
            architectures=[arch],
            test_cases=[case],
            settings_factory=make_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            await runner.run_single(arch, case)

        assert called_with.get("file_id") is None

    @pytest.mark.asyncio
    async def test_run_single_missing_file_path_records_error(
        self, tmp_path: Path
    ) -> None:
        """If file_path points to a nonexistent file, run_single captures an error."""
        from unittest.mock import MagicMock, patch

        from eval.models import ArchitectureConfig, TestCase
        from eval.runner import EvalRunner

        arch = ArchitectureConfig(id="v1")
        case = TestCase(
            id="c_missing",
            task="task",
            description="",
            file_path="/nonexistent/path/data.xlsx",
        )

        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()

        async def mock_orchestrate(task, file_id, settings):
            entry = MagicMock()
            entry.phase = "C"
            entry.action = "complete"
            entry.content = json.dumps({"python_code": "pass", "summary": "s", "steps": [], "tips": "", "debug_retries": 0})
            entry.timestamp = "2026-03-28T00:00:00+00:00"
            yield entry

        def make_settings(overrides=None):
            s = MagicMock()
            s.upload_dir = str(upload_dir)
            if overrides:
                for k, v in overrides.items():
                    setattr(s, k, v)
            return s

        runner = EvalRunner(
            architectures=[arch],
            test_cases=[case],
            settings_factory=make_settings,
        )

        with patch("eval.runner.orchestrate", side_effect=mock_orchestrate):
            result = await runner.run_single(arch, case)

        # Should capture an error since file is missing
        assert result.error is not None
        assert result.metrics.success is False
