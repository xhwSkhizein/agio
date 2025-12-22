"""Test citation store configuration and dependency injection."""

import asyncio
from agio.config.system import ConfigSystem


async def test_citation_store_config():
    """Test citation store configuration loading and tool dependency injection."""
    
    print("=" * 60)
    print("Testing Citation Store Configuration")
    print("=" * 60)
    
    config_system = ConfigSystem()
    
    print("\n1. Loading configurations from configs/...")
    stats = await config_system.load_from_directory("configs")
    print(f"   Loaded: {stats['loaded']}, Failed: {stats['failed']}")
    
    print("\n2. Building all components...")
    try:
        build_stats = await config_system.build_all()
        print(f"   Built: {build_stats['built']}, Failed: {build_stats['failed']}")
    except Exception as e:
        print(f"   ✗ Failed to build components: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n3. Getting citation_store_mongodb instance...")
    try:
        citation_store = config_system.get("citation_store_mongodb")
        print(f"   ✓ Citation store retrieved: {type(citation_store).__name__}")
        print(f"   ✓ DB: {citation_store.db_name}, URI: {citation_store.uri}")
    except Exception as e:
        print(f"   ✗ Failed to get citation store: {e}")
        return False
    
    print("\n4. Getting web_search tool with citation_store dependency...")
    try:
        web_search = config_system.get("web_search")
        print(f"   ✓ web_search tool retrieved: {type(web_search).__name__}")
        has_store = hasattr(web_search, '_citation_source_store')
        store_value = getattr(web_search, '_citation_source_store', None)
        print(f"   ✓ Has _citation_source_store: {has_store}")
        print(f"   ✓ Store type: {type(store_value).__name__ if store_value else 'None'}")
        
        if store_value is None:
            print("   ✗ ERROR: citation_source_store is None!")
            return False
            
    except Exception as e:
        print(f"   ✗ Failed to get web_search: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n5. Getting web_fetch tool with citation_store dependency...")
    try:
        web_fetch = config_system.get("web_fetch")
        print(f"   ✓ web_fetch tool retrieved: {type(web_fetch).__name__}")
        has_store = hasattr(web_fetch, '_citation_source_store')
        store_value = getattr(web_fetch, '_citation_source_store', None)
        print(f"   ✓ Has _citation_source_store: {has_store}")
        print(f"   ✓ Store type: {type(store_value).__name__ if store_value else 'None'}")
        
        if store_value is None:
            print("   ✗ ERROR: citation_source_store is None!")
            return False
            
    except Exception as e:
        print(f"   ✗ Failed to get web_fetch: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n6. Testing citation store operations...")
    try:
        from agio.providers.tools.builtin.common.citation import CitationSourceRaw, CitationSourceType
        from datetime import datetime
        
        test_source = CitationSourceRaw(
            citation_id="test_citation_001",
            session_id="test_session",
            source_type=CitationSourceType.SEARCH,
            url="https://example.com",
            title="Test Article",
            snippet="Test snippet",
            index=0,
        )
        
        citation_ids = await citation_store.store_citation_sources(
            session_id="test_session",
            sources=[test_source],
        )
        print(f"   ✓ Stored citation: {citation_ids}")
        
        retrieved = await citation_store.get_source_by_index(
            session_id="test_session",
            index=0,
        )
        print(f"   ✓ Retrieved by index: {retrieved.title if retrieved else 'None'}")
        
        await citation_store.cleanup_session("test_session")
        print(f"   ✓ Cleaned up test session")
        
    except Exception as e:
        print(f"   ✗ Citation store operations failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_citation_store_config())
    exit(0 if success else 1)
