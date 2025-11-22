"""
API tests for FastAPI backend.
"""

import pytest
from fastapi.testclient import TestClient
from agio.api.app import create_app

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
        assert response.status_code == 400
    
    def test_resume_nonexistent_run(self):
        response = client.post("/api/runs/nonexistent/resume")
        assert response.status_code == 400
    
    def test_cancel_nonexistent_run(self):
        response = client.post("/api/runs/nonexistent/cancel")
        assert response.status_code == 400


class TestCheckpointEndpoints:
    """Test checkpoint endpoints."""
    
    def test_list_checkpoints(self):
        response = client.get("/api/checkpoints/runs/test_run/checkpoints")
        assert response.status_code == 200
        
        data = response.json()
        assert "total" in data
        assert "items" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
