"""
API tests for FastAPI backend.
"""

import pytest
from fastapi.testclient import TestClient

from agio.api.app import create_app
from agio.config import get_config_system


@pytest.fixture(scope="module", autouse=True)
def setup_config_system():
    """Initialize the config system before tests."""
    import asyncio
    import tempfile
    import os

    # Create a temporary config directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create empty subdirectories
        for subdir in ["models", "tools", "agents"]:
            os.makedirs(os.path.join(tmpdir, subdir), exist_ok=True)

        # Initialize config system
        config_sys = get_config_system()
        asyncio.get_event_loop().run_until_complete(
            config_sys.load_from_directory(tmpdir)
        )
        yield


client = TestClient(create_app())


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self):
        response = client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data


class TestAgentEndpoints:
    """Test agent endpoints."""

    def test_list_agents(self):
        response = client.get("/api/agents")
        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_get_nonexistent_agent(self):
        response = client.get("/api/agents/nonexistent")
        assert response.status_code == 404


class TestRunEndpoints:
    """Test run endpoints."""

    def test_pause_nonexistent_run(self):
        response = client.post("/api/runs/nonexistent/pause")
        assert response.status_code == 404

    def test_resume_nonexistent_run(self):
        response = client.post("/api/runs/nonexistent/resume")
        assert response.status_code == 404

    def test_cancel_nonexistent_run(self):
        response = client.post("/api/runs/nonexistent/cancel")
        assert response.status_code == 404


class TestCheckpointEndpoints:
    """Test checkpoint endpoints."""

    def test_list_checkpoints(self):
        response = client.get("/api/checkpoints/runs/test_run/checkpoints")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
