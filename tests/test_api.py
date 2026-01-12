"""
API tests for FastAPI backend.
"""

import pytest
from fastapi.testclient import TestClient

from agio.api.app import create_app
# from agio.config import get_config_system  # Unused and problematic


@pytest.fixture(scope="module", autouse=True)
def setup_config_system():
    """Initialize the config system before tests."""
    # ConfigSystem is currently missing from the codebase.
    # We skip initialization as the app handles missing config gracefully.
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client):
        response = client.get("/agio/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data


class TestAgentEndpoints:
    """Test agent endpoints."""

    def test_list_agents(self, client):
        response = client.get("/agio/agents")
        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_get_nonexistent_agent(self, client):
        response = client.get("/agio/agents/nonexistent")
        assert response.status_code == 404


class TestRunEndpoints:
    """Test run endpoints."""

    def test_pause_nonexistent_run(self, client):
        response = client.post("/agio/runs/nonexistent/pause")
        assert response.status_code == 404

    def test_resume_nonexistent_run(self, client):
        response = client.post("/agio/runs/nonexistent/resume")
        assert response.status_code == 404

    def test_cancel_nonexistent_run(self, client):
        response = client.post("/agio/runs/nonexistent/cancel")
        assert response.status_code == 404


class TestCheckpointEndpoints:
    """Test checkpoint endpoints."""

    def test_list_checkpoints(self, client):
        response = client.get("/agio/checkpoints/runs/test_run/checkpoints")
        assert response.status_code == 404



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
