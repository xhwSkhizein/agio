"""WebReaderApiTool 测试用例"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agio.tools.builtin.web_reader_api_tool import WebReaderApiTool
from agio.tools.builtin.config import WebReaderApiConfig
from agio.tools.builtin.web_fetch_tool.html_extract import HtmlContent


class TestWebReaderApiTool:
    """WebReaderApiTool 测试用例"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        config = WebReaderApiConfig(
            base_url="https://test.api.com",
            timeout_seconds=30,
            max_content_length=4096,
        )
        return WebReaderApiTool(config=config)

    @pytest.fixture
    def mock_html_content(self):
        """模拟 HTML 内容"""
        return HtmlContent(
            title="Test Page",
            raw_text="This is test content for the page.",
            text="This is test content for the page.",
            hostname="example.com",
        )

    @pytest.mark.asyncio
    async def test_basic_info(self, tool):
        """测试工具基本信息"""
        assert tool.get_name() == "web_reader"
        assert "web" in tool.get_description().lower()
        params = tool.get_parameters()
        assert params["type"] == "object"
        assert "url" in params["properties"]
        assert "index" in params["properties"]

    @pytest.mark.asyncio
    async def test_concurrency_and_permissions(self, tool):
        """测试并发和权限"""
        assert tool.is_concurrency_safe() is True
        assert tool.needs_permissions({}) is False

    @pytest.mark.asyncio
    async def test_fetch_content_from_api(self, tool, mock_html_content):
        """测试从 API 获取内容"""
        mock_response = {
            "data": {
                "html": "<html><body>Test content</body></html>",
                "title": "Test Page",
                "url": "https://example.com",
            }
        }

        with patch.object(
            tool._http_client, "post_json", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            with patch(
                "agio.tools.builtin.web_reader_api_tool.web_reader_api_tool.extract_content_from_html"
            ) as mock_extract:
                mock_extract.return_value = mock_html_content

                content = await tool._fetch_content_from_api("https://example.com")

                assert content is not None
                assert content.title == "Test Page"
                mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_url(self, tool, mock_html_content):
        """测试使用 URL 直接执行"""
        mock_response = {
            "data": {
                "html": "<html><body>Test content</body></html>",
                "url": "https://example.com",
            }
        }

        with patch.object(
            tool._http_client, "post_json", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            with patch(
                "agio.tools.builtin.web_reader_api_tool.web_reader_api_tool.extract_content_from_html"
            ) as mock_extract:
                mock_extract.return_value = mock_html_content

                result = await tool.execute(
                    parameters={"url": "https://example.com", "session_id": "session_123"},
                    context=MagicMock(),
                )

                assert result.is_success is True
                assert "This is test content" in result.content
                assert result.output["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_execute_with_index(self, tool, mock_html_content):
        """测试使用索引执行"""
        # 模拟 citation store
        mock_store = AsyncMock()
        mock_source = MagicMock()
        mock_source.url = "https://example.com"
        mock_source.citation_id = "cite_123"
        mock_store.get_source_by_index.return_value = mock_source
        mock_store.update_citation_source.return_value = None

        tool._citation_source_store = mock_store

        mock_response = {
            "data": {
                "html": "<html><body>Test content</body></html>",
                "url": "https://example.com",
            }
        }

        with patch.object(
            tool._http_client, "post_json", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            with patch(
                "agio.tools.builtin.web_reader_api_tool.web_reader_api_tool.extract_content_from_html"
            ) as mock_extract:
                mock_extract.return_value = mock_html_content

                result = await tool.execute(
                    parameters={"index": 0, "session_id": "session_123"},
                    context=MagicMock(),
                )

                assert result.is_success is True
                assert "[cite:cite_123]" in result.content
                mock_store.get_source_by_index.assert_called_once()
                mock_store.update_citation_source.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_summarize(self, tool, mock_html_content):
        """测试带总结的执行"""
        mock_response = {
            "data": {
                "html": "<html><body>Long test content</body></html>",
                "url": "https://example.com",
            }
        }

        with patch.object(
            tool._http_client, "post_json", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            with patch(
                "agio.tools.builtin.web_reader_api_tool.web_reader_api_tool.extract_content_from_html"
            ) as mock_extract:
                mock_extract.return_value = mock_html_content

                with patch.object(
                    tool._llm_client, "summarize", new_callable=AsyncMock
                ) as mock_summarize:
                    mock_summarize.return_value = "Summarized content"

                    result = await tool.execute(
                        parameters={
                            "url": "https://example.com",
                            "summarize": True,
                            "session_id": "session_123",
                        },
                        context=MagicMock(),
                    )

                    assert result.is_success is True
                    assert "Summarized content" in result.content
                    mock_summarize.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_search_query(self, tool, mock_html_content):
        """测试带搜索查询的执行"""
        mock_response = {
            "data": {
                "html": "<html><body>Test content</body></html>",
                "url": "https://example.com",
            }
        }

        with patch.object(
            tool._http_client, "post_json", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            with patch(
                "agio.tools.builtin.web_reader_api_tool.web_reader_api_tool.extract_content_from_html"
            ) as mock_extract:
                mock_extract.return_value = mock_html_content

                with patch.object(
                    tool._llm_client, "extract_by_query", new_callable=AsyncMock
                ) as mock_extract_query:
                    mock_extract_query.return_value = "Extracted content"

                    result = await tool.execute(
                        parameters={
                            "url": "https://example.com",
                            "search_query": "test query",
                            "session_id": "session_123",
                        },
                        context=MagicMock(),
                    )

                    assert result.is_success is True
                    assert "Extracted content" in result.content
                    mock_extract_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_error(self, tool):
        """测试错误处理"""
        with patch.object(
            tool._http_client, "post_json", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = Exception("API Error")

            result = await tool.execute(
                parameters={"url": "https://example.com"},
                context=MagicMock(),
            )

            assert result.is_success is False
            assert "Error" in result.content

    @pytest.mark.asyncio
    async def test_execute_index_without_citation_store(self, tool):
        """测试无 citation store 时使用索引"""
        result = await tool.execute(
            parameters={"index": 0},
            context=MagicMock(),
        )

        assert result.is_success is False
        assert "Citation store not available" in result.content

    @pytest.mark.asyncio
    async def test_execute_index_not_found(self, tool):
        """测试索引未找到"""
        mock_store = AsyncMock()
        mock_store.get_source_by_index.return_value = None
        tool._citation_source_store = mock_store

        result = await tool.execute(
            parameters={"index": 0, "session_id": "session_123"},
            context=MagicMock(),
        )

        assert result.is_success is False
        assert "not found" in result.content
