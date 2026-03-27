"""Tests for POST /api/upload endpoint — TDD: tests written FIRST.

Integration tests use TestClient and real temporary xlsx/csv files.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Integration tests: POST /api/upload — happy paths
# ---------------------------------------------------------------------------


class TestUploadEndpointSuccess:
    """Integration tests for successful uploads."""

    def test_upload_xlsx_returns_200(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """Uploading a valid xlsx file must return HTTP 200."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", f, "application/octet-stream")},
            )
        assert response.status_code == 200

    def test_upload_csv_returns_200(
        self, upload_client: TestClient, sample_csv: Path
    ) -> None:
        """Uploading a valid csv file must return HTTP 200."""
        with open(sample_csv, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("sample.csv", f, "text/csv")},
            )
        assert response.status_code == 200

    def test_upload_response_schema(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """Response must include file_id, filename, and sheets fields."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", f, "application/octet-stream")},
            )
        data = response.json()

        assert "file_id" in data
        assert "filename" in data
        assert "sheets" in data

    def test_upload_filename_preserved(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """Response filename must match the uploaded filename."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("my_data.xlsx", f, "application/octet-stream")},
            )
        data = response.json()

        assert data["filename"] == "my_data.xlsx"

    def test_upload_file_id_is_non_empty_string(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """file_id in response must be a non-empty string."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", f, "application/octet-stream")},
            )
        data = response.json()

        assert isinstance(data["file_id"], str)
        assert len(data["file_id"]) > 0

    def test_upload_sheets_is_list(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """sheets field must be a list."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", f, "application/octet-stream")},
            )
        data = response.json()

        assert isinstance(data["sheets"], list)

    def test_upload_xlsx_sheet_count(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """Single-sheet xlsx must return one sheet in response."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", f, "application/octet-stream")},
            )
        data = response.json()

        assert len(data["sheets"]) == 1

    def test_upload_sheet_has_required_fields(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """Each sheet in response must have name, total_rows, headers, types, preview."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", f, "application/octet-stream")},
            )
        sheet = response.json()["sheets"][0]

        assert "name" in sheet
        assert "total_rows" in sheet
        assert "headers" in sheet
        assert "types" in sheet
        assert "preview" in sheet

    def test_upload_sheet_name(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """Sheet name in response must match the actual sheet name."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", f, "application/octet-stream")},
            )
        sheet = response.json()["sheets"][0]

        assert sheet["name"] == "Sales"

    def test_upload_sheet_headers(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """Sheet headers must match the xlsx column headers."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", f, "application/octet-stream")},
            )
        sheet = response.json()["sheets"][0]

        assert sheet["headers"] == ["date", "product", "quantity", "price", "active"]

    def test_upload_sheet_total_rows(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """total_rows must equal the number of data rows in the sheet."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", f, "application/octet-stream")},
            )
        sheet = response.json()["sheets"][0]

        assert sheet["total_rows"] == 5

    def test_upload_sheet_preview_is_list(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """preview field must be a list of row dicts."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", f, "application/octet-stream")},
            )
        sheet = response.json()["sheets"][0]

        assert isinstance(sheet["preview"], list)
        assert all(isinstance(row, dict) for row in sheet["preview"])

    def test_upload_types_dict(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """types must be a dict mapping column names to type strings."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", f, "application/octet-stream")},
            )
        types = response.json()["sheets"][0]["types"]

        assert isinstance(types, dict)
        assert set(types.keys()) == {"date", "product", "quantity", "price", "active"}

    def test_upload_csv_sheet_name_is_sheet1(
        self, upload_client: TestClient, sample_csv: Path
    ) -> None:
        """CSV uploads must produce a sheet named 'Sheet1'."""
        with open(sample_csv, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("data.csv", f, "text/csv")},
            )
        sheet = response.json()["sheets"][0]

        assert sheet["name"] == "Sheet1"

    def test_two_uploads_have_different_file_ids(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """Each upload must produce a unique file_id."""
        with open(sample_xlsx, "rb") as f1, open(sample_xlsx, "rb") as f2:
            r1 = upload_client.post(
                "/api/upload",
                files={"file": ("a.xlsx", f1, "application/octet-stream")},
            )
            r2 = upload_client.post(
                "/api/upload",
                files={"file": ("b.xlsx", f2, "application/octet-stream")},
            )

        assert r1.json()["file_id"] != r2.json()["file_id"]

    def test_uploaded_file_saved_to_disk(
        self, upload_client: TestClient, sample_xlsx: Path, tmp_upload_dir: Path
    ) -> None:
        """Uploaded file must be persisted inside the uploads directory."""
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("save_test.xlsx", f, "application/octet-stream")},
            )

        assert response.status_code == 200
        # At least one file should exist in the tmp upload dir
        saved = list(tmp_upload_dir.iterdir())
        assert len(saved) >= 1


# ---------------------------------------------------------------------------
# Integration tests: POST /api/upload — validation errors
# ---------------------------------------------------------------------------


class TestUploadEndpointValidation:
    """Validation and error tests for the upload endpoint."""

    def test_missing_file_field_returns_422(
        self, upload_client: TestClient
    ) -> None:
        """Request without a file field must return HTTP 422."""
        response = upload_client.post("/api/upload", data={})
        assert response.status_code == 422

    def test_unsupported_extension_returns_400(
        self, upload_client: TestClient
    ) -> None:
        """Uploading a .txt file must return HTTP 400."""
        content = b"some text content"
        response = upload_client.post(
            "/api/upload",
            files={"file": ("data.txt", io.BytesIO(content), "text/plain")},
        )
        assert response.status_code == 400

    def test_unsupported_extension_error_message(
        self, upload_client: TestClient
    ) -> None:
        """400 error response must mention the allowed extensions."""
        content = b"some text content"
        response = upload_client.post(
            "/api/upload",
            files={"file": ("data.pdf", io.BytesIO(content), "application/pdf")},
        )
        detail = response.json().get("detail", "")
        assert any(ext in detail for ext in [".xlsx", ".xls", ".csv", "xlsx", "csv"])

    def test_file_too_large_returns_413(
        self, upload_client: TestClient
    ) -> None:
        """File exceeding max size limit must return HTTP 413."""
        # Create content larger than 50MB limit (51 MB)
        big_content = b"x" * (51 * 1024 * 1024)
        response = upload_client.post(
            "/api/upload",
            files={"file": ("big.xlsx", io.BytesIO(big_content), "application/octet-stream")},
        )
        assert response.status_code == 413

    def test_xls_extension_accepted(
        self, upload_client: TestClient, sample_xlsx: Path
    ) -> None:
        """Files with .xls extension must be accepted (200 or parsed correctly).

        Note: openpyxl cannot read legacy .xls; we expect either 200 (if format
        is actually xlsx rebranded) or a 400 with a parse-error message, but NOT
        a 422 or 500 from missing validation.
        """
        with open(sample_xlsx, "rb") as f:
            response = upload_client.post(
                "/api/upload",
                files={"file": ("data.xls", f, "application/octet-stream")},
            )
        # Either succeeds (xlsx bytes treated as xls) or returns 400 parse error
        assert response.status_code in (200, 400)


# ---------------------------------------------------------------------------
# Integration tests: generate endpoint with file_id
# ---------------------------------------------------------------------------


class TestGenerateWithFileId:
    """Tests that the generate endpoint correctly uses file_id context."""

    def test_generate_with_valid_file_id_returns_200(
        self,
        upload_client: TestClient,
        sample_xlsx: Path,
    ) -> None:
        """generate endpoint must accept file_id and return 200."""
        # Upload first
        with open(sample_xlsx, "rb") as f:
            upload_resp = upload_client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", f, "application/octet-stream")},
            )
        assert upload_resp.status_code == 200
        file_id = upload_resp.json()["file_id"]

        # Generate using file_id
        gen_resp = upload_client.post(
            "/api/generate",
            json={"task": "売上を集計する", "file_id": file_id},
        )
        assert gen_resp.status_code == 200

    def test_generate_with_unknown_file_id_still_returns_200(
        self,
        upload_client: TestClient,
    ) -> None:
        """generate endpoint with an unknown file_id must not crash (graceful)."""
        gen_resp = upload_client.post(
            "/api/generate",
            json={"task": "集計する", "file_id": "nonexistent-uuid"},
        )
        # Should still return 200; file context just not found
        assert gen_resp.status_code == 200
