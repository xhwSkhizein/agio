
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from agio.config.system import ConfigSystem
from agio.config.schema import ComponentType, CitationStoreConfig, SessionStoreConfig, TraceStoreConfig
from agio.storage.citation.mongo_store import MongoCitationStore
from agio.storage.session.mongo import MongoSessionStore
from agio.storage.trace.store import TraceStore

class MockCollection:
    def __init__(self):
        self.create_index = AsyncMock()
        self.find_one = AsyncMock(return_value=None)
        self.insert_one = AsyncMock()
        self.update_one = AsyncMock()
        self.bulk_write = AsyncMock()
        self.delete_many = AsyncMock()
        self.find = MagicMock(return_value=self)
        self.sort = MagicMock(return_value=self)
        self.skip = MagicMock(return_value=self)
        self.limit = MagicMock(return_value=self)
    
    def __aiter__(self):
        return iter([]).__iter__()

    async def to_list(self, length):
        return []

class MockDatabase:
    def __init__(self):
        self._collections = {}

    def __getitem__(self, key):
        if key not in self._collections:
            self._collections[key] = MockCollection()
        return self._collections[key]

class MockClient:
    def __init__(self, *args, **kwargs):
        self.closed = False
        self._db = MockDatabase()
    
    def __getitem__(self, key):
        return self._db

    def close(self):
        self.closed = True

@pytest.mark.asyncio
async def test_startup_no_unnecessary_disconnect(monkeypatch):
    """
    Test that the initial build_all() does not trigger a disconnect on 
    newly built components due to draining the initial empty container.
    """
    system = ConfigSystem()
    
    # Mock MongoCitationStore to track disconnects
    disconnect_calls = []
    original_disconnect = MongoCitationStore.disconnect
    
    async def tracked_disconnect(self):
        disconnect_calls.append(self)
        self.client = None
        self.db = None
        self.citations_collection = None
        
    monkeypatch.setattr(MongoCitationStore, "disconnect", tracked_disconnect)

    # Register a citation store config
    config = CitationStoreConfig(
        name="test_store",
        backend={"type": "mongodb", "uri": "mongodb://localhost:27017", "db_name": "test_db"}
    )
    system.registry.register(config)

    # First build_all
    await system.build_all()
    await asyncio.sleep(0.1)
    
    assert len(disconnect_calls) == 0, "Should not disconnect on first build"
    
    # Second build_all (simulating a reload)
    await system.build_all()
    await asyncio.sleep(0.1)
    
    assert len(disconnect_calls) >= 1, "Should disconnect old instance on reload"

@pytest.mark.asyncio
async def test_mongo_citation_store_reconnect(monkeypatch):
    """Verify MongoCitationStore reconnection after disconnect."""
    store = MongoCitationStore(uri="mongodb://localhost:27017", db_name="test_db")
    
    # Mock client creation
    mock_client = MockClient()
    monkeypatch.setattr("motor.motor_asyncio.AsyncIOMotorClient", MagicMock(return_value=mock_client))
    
    await store._ensure_connection()
    assert store.client is not None
    
    await store.disconnect()
    assert store.client is None
    assert store.db is None
    
    await store._ensure_connection()
    assert store.client is not None

@pytest.mark.asyncio
async def test_mongo_session_store_reconnect(monkeypatch):
    """Verify MongoSessionStore reconnection after disconnect."""
    store = MongoSessionStore(uri="mongodb://localhost:27017", db_name="test_db")
    
    mock_client = MockClient()
    monkeypatch.setattr("motor.motor_asyncio.AsyncIOMotorClient", MagicMock(return_value=mock_client))
    
    await store._ensure_connection()
    assert store.client is not None
    
    await store.disconnect()
    assert store.client is None
    assert store.runs_collection is None
    
    await store._ensure_connection()
    assert store.client is not None

@pytest.mark.asyncio
async def test_trace_store_reconnect(monkeypatch):
    """Verify TraceStore reconnection after close."""
    store = TraceStore(mongo_uri="mongodb://localhost:27017", db_name="test_db")
    
    mock_client = MockClient()
    monkeypatch.setattr("motor.motor_asyncio.AsyncIOMotorClient", MagicMock(return_value=mock_client))
    
    await store.initialize()
    assert store._client is not None
    
    await store.close()
    assert store._client is None
    assert store._initialized is False
    
    await store.initialize()
    assert store._client is not None


if __name__ == "__main__":
    pytest.main([__file__])
