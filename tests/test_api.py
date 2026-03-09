"""
Tests for the FastAPI backend.

Coach Simple explains:
    "We're testing our web server to make sure it correctly handles
    file uploads, returns project info, and serves download links."
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from api.app import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_ifc_path():
    """Path to the sample IFC file."""
    return Path("tests/fixtures/simple_house.ifc")


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "Metraj AI"


class TestUploadEndpoint:
    def test_upload_ifc_file(self, client, sample_ifc_path):
        if not sample_ifc_path.exists():
            pytest.skip("Sample IFC file not found")

        with open(sample_ifc_path, "rb") as f:
            response = client.post(
                "/api/projects/upload",
                files={"file": ("simple_house.ifc", f, "application/octet-stream")},
            )

        assert response.status_code == 200
        data = response.json()
        assert "project_id" in data
        assert data["filename"] == "simple_house.ifc"
        assert data["status"] == "processing"

    def test_upload_rejects_non_ifc(self, client):
        response = client.post(
            "/api/projects/upload",
            files={"file": ("test.txt", b"not an ifc file", "text/plain")},
        )
        assert response.status_code == 400

    def test_list_projects(self, client):
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data


class TestDownloadEndpoint:
    def test_download_nonexistent_project(self, client):
        response = client.get("/api/projects/nonexistent/download/xlsx")
        assert response.status_code == 404
