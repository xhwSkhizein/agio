import pytest
from fastapi.testclient import TestClient
from agio.api.app import app
from agio.registry.manager import ConfigManager
import os
import shutil

# Setup test config directory
TEST_CONFIG_DIR = "tests/test_configs"

@pytest.fixture(scope="module")
def test_client():
    # Create test config dir
    if os.path.exists(TEST_CONFIG_DIR):
        shutil.rmtree(TEST_CONFIG_DIR)
    os.makedirs(TEST_CONFIG_DIR)
    
    # Create a dummy config
    with open(f"{TEST_CONFIG_DIR}/test_model.yaml", "w") as f:
        f.write("""
type: model
name: test-model
provider: openai
model: gpt-3.5-turbo
api_key: sk-test
""")

    # Set env var for config dir
    os.environ["AGIO_CONFIG_DIR"] = TEST_CONFIG_DIR
    
    with TestClient(app) as client:
        yield client
        
    # Cleanup
    if os.path.exists(TEST_CONFIG_DIR):
        shutil.rmtree(TEST_CONFIG_DIR)
    del os.environ["AGIO_CONFIG_DIR"]

def test_list_configs(test_client):
    response = test_client.get("/api/config/")
    assert response.status_code == 200
    data = response.json()
    assert "test-model" in data
    assert data["test-model"]["type"] == "model"

def test_get_config(test_client):
    response = test_client.get("/api/config/test-model")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-model"
    assert data["provider"] == "openai"

def test_get_nonexistent_config(test_client):
    response = test_client.get("/api/config/nonexistent")
    assert response.status_code == 404

def test_update_config(test_client):
    # Get original config
    response = test_client.get("/api/config/test-model")
    config = response.json()
    
    # Update it
    config["model"] = "gpt-4"
    response = test_client.put("/api/config/test-model", json={"config": config})
    assert response.status_code == 200
    
    # Verify update
    response = test_client.get("/api/config/test-model")
    assert response.json()["model"] == "gpt-4"

def test_update_config_mismatch(test_client):
    response = test_client.get("/api/config/test-model")
    config = response.json()
    
    # Try to update with different name
    config["name"] = "other-name"
    response = test_client.put("/api/config/test-model", json={"config": config})
    assert response.status_code == 400

def test_reload_configs(test_client):
    response = test_client.post("/api/config/reload")
    assert response.status_code == 200
    assert response.json()["message"] == "All configurations reloaded successfully"
