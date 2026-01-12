"""WebSearchApiTool 测试用例"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agio.tools.builtin.web_search_api_tool import WebSearchApiTool
from agio.tools.builtin.config import WebSearchApiConfig


class TestWebSearchApiTool:
    """WebSearchApiTool 测试用例"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        config = WebSearchApiConfig(
            base_url="https://test.api.com",
            timeout_seconds=30,
            max_results=5,
        )
        return WebSearchApiTool(config=config)

    @pytest.mark.asyncio
    async def test_basic_info(self, tool):
        """测试工具基本信息"""
        assert tool.get_name() == "web_search"
        assert "web" in tool.get_description().lower()
        params = tool.get_parameters()
        assert params["type"] == "object"
        assert "query" in params["properties"]

    @pytest.mark.asyncio
    async def test_concurrency_and_permissions(self, tool):
        """测试并发和权限"""
        assert tool.is_concurrency_safe() is True
        assert tool.needs_permissions({}) is False

    @pytest.mark.asyncio
    async def test_search_api_call(self, tool):
        """测试 API 调用"""
        mock_response = {
            "results": [
                {
                    "url": "https://example.com/1",
                    "name": "Test Page 1",
                    "snippet": "Test snippet 1",
                    "host_name": "example.com",
                    "date": "2024-01-01",
                    "rank": 0,
                },
                {
                    "url": "https://example.com/2",
                    "name": "Test Page 2",
                    "snippet": "Test snippet 2",
                    "host_name": "example.com",
                    "date": "2024-01-02",
                    "rank": 1,
                },
            ],
            "count": 2,
        }

        with patch.object(
            tool._http_client, "post_json", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            results = await tool._call_search_api("test query")

            assert len(results) == 2
            assert results[0]["name"] == "Test Page 1"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_convert_api_results_to_citations(self, tool):
        """测试结果转换"""
        api_results = [
            {
                "url": "https://example.com",
                "name": "Test Page",
                "snippet": "Test snippet",
                "host_name": "example.com",
                "date": "2024-01-01",
            }
        ]

        citations = tool._convert_api_results_to_citations(
            api_results, "test query", "session_123", start_index=0
        )

        assert len(citations) == 1
        assert citations[0].url == "https://example.com"
        assert citations[0].title == "Test Page"
        assert citations[0].query == "test query"
        assert citations[0].session_id == "session_123"
        assert citations[0].index == 0

    @pytest.mark.asyncio
    async def test_format_fallback_results(self, tool):
        """测试回退格式化"""
        api_results = [
            {
                "url": "https://example.com",
                "name": "Test Page",
                "snippet": "Test snippet",
                "host_name": "example.com",
                "date": "2024-01-01",
            }
        ]

        result = tool._format_fallback_results("test query", api_results)

        assert "test query" in result
        assert "Test Page" in result
        assert "https://example.com" in result
        assert "Test snippet" in result

    @pytest.mark.asyncio
    async def test_execute_without_citation_store(self, tool):
        """测试无 citation store 的执行"""
        mock_response = {
            "results": [
                {
                    "url": "https://example.com",
                    "name": "Test Page",
                    "snippet": "Test snippet",
                    "host_name": "example.com",
                    "date": "",
                    "rank": 0,
                }
            ],
            "count": 1,
        }

        with patch.object(
            tool._http_client, "post_json", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await tool.execute(
                parameters={"query": "test query", "session_id": "session_123"},
                context=MagicMock(),
            )

            assert result.is_success is True
            assert "Test Page" in result.content
            assert result.output["result_count"] == 1

    @pytest.mark.asyncio
    async def test_execute_with_citation_store(self, tool):
        """测试有 citation store 的执行"""
        # 模拟 citation store
        mock_store = AsyncMock()
        mock_store.get_session_citations.return_value = []
        mock_store.store_citation_sources.return_value = ["cite_123"]
        mock_store.get_simplified_sources.return_value = [
            MagicMock(
                index=0,
                title="Test Page",
                citation_id="cite_123",
                snippet="Test snippet",
                date_published="2024-01-01",
                source="example.com",
            )
        ]

        tool._citation_source_store = mock_store

        mock_response = {
            "results": [
                {
                    "url": "https://example.com",
                    "name": "Test Page",
                    "snippet": "Test snippet",
                    "host_name": "example.com",
                    "date": "2024-01-01",
                    "rank": 0,
                }
            ],
            "count": 1,
        }

        with patch.object(
            tool._http_client, "post_json", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await tool.execute(
                parameters={"query": "test query", "session_id": "session_123"},
                context=MagicMock(),
            )

            assert result.is_success is True
            assert "[cite:cite_123]" in result.content
            assert result.output["citation_ids"] == ["cite_123"]
            mock_store.store_citation_sources.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_error(self, tool):
        """测试错误处理"""
        with patch.object(
            tool._http_client, "post_json", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = Exception("API Error")

            result = await tool.execute(
                parameters={"query": "test query"},
                context=MagicMock(),
            )

            assert result.is_success is False
            assert "Error" in result.content

    @pytest.mark.asyncio
    async def test_execute_no_results(self, tool):
        """测试无结果情况"""
        mock_response = {"results": [], "count": 0}

        with patch.object(
            tool._http_client, "post_json", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await tool.execute(
                parameters={"query": "test query"},
                context=MagicMock(),
            )

            assert result.is_success is False
            assert "No results found" in result.content
