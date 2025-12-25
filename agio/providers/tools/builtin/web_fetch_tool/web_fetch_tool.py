"""
WebFetchTool - Advanced Web Content Extraction Tool

Complete rewrite with improved content extraction, quality validation, and smart filtering.
Supports multiple extraction strategies and content type detection.
"""

import time
from datetime import datetime
from typing import Any

from agio.providers.tools.base import BaseTool, RiskLevel, ToolCategory
from agio.providers.tools.builtin.adapter import AppSettings, SettingsRegistry
from agio.storage.citation import (
    CitationSourceRaw,
    CitationSourceType,
    generate_citation_id,
)
from agio.providers.tools.builtin.common.llm.model_adapter import (
    ModelLLMAdapter,
)
from agio.providers.tools.builtin.common.web_fetch import (
    HtmlContent,
    SimpleAsyncClient,
    truncate_middle,
)
from agio.providers.tools.builtin.common.web_fetch.llm_processors import (
    extract_by_query_use_llm,
    summarize_by_llm,
)
from agio.providers.tools.builtin.common.web_fetch.playwright_crawler import (
    PlaywrightCrawler,
)
from agio.utils.logging import get_logger
from agio.domain import ToolResult

from agio.providers.llm.base import Model
from agio.storage.citation import CitationSourceRepository
from agio.runtime.control import AbortSignal
from agio.runtime.protocol import ExecutionContext


logger = get_logger(__name__)


class WebFetchTool(BaseTool):
    """网页内容获取工具
    
    核心功能：
    1. 使用 curl_cffi 快速获取内容，失败时降级到 Playwright
    2. 使用 trafilatura 提取主要内容
    3. 支持 LLM 摘要和查询提取（可选）
    4. 支持 Citation 系统（可选）
    """

    # Enable caching - web page content is stable within a session
    cacheable = True

    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        citation_source_store: "CitationSourceRepository | None" = None,
        llm_model: "Model | None" = None,
    ) -> None:
        super().__init__()
        self._settings = settings or SettingsRegistry.get()
        self._citation_source_store = citation_source_store
        # 使用适配器包装 Model
        self._llm_service = ModelLLMAdapter(llm_model) if llm_model else None
        self.category = ToolCategory.WEB
        self.risk_level = RiskLevel.MEDIUM

        # Core configuration
        self.timeout_seconds = self._settings.tool.web_fetch_tool_timeout_seconds
        self.max_length = self._settings.tool.web_fetch_max_content_length

        # HTTP 客户端和爬虫
        self._curl_cffi_client = SimpleAsyncClient()
        self._playwright_crawl = PlaywrightCrawler(settings=self._settings)

    def get_name(self) -> str:
        return "web_fetch"

    def get_description(self) -> str:
        return """Fetch web content into text only format.
**Usage modes:**
1. **By search index**: `index=0` (recommended, uses web_search results)
2. **By direct URL**: `url="https://..."` (backward compatible)

**Content processing options:**
- `search_query`: if provided, return content relevant to your specific query
- `summarize`: if provided, generate concise summary of main content
- Note: These options are mutually exclusive
"""

    def get_parameters(self) -> dict[str, Any]:
        """Return tool parameters JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "index": {
                    "type": "integer",
                    "description": "Search result index from web_search (0, 1, 2...)",
                    "minimum": 0,
                },
                "url": {
                    "oneOf": [
                        {"type": "string", "description": "Single URL"},
                        {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Multiple URLs",
                        },
                    ],
                    "description": "Direct URL (backward compatible)",
                },
                "search_query": {
                    "type": "string",
                    "description": "Extract content relevant to this query (mutually exclusive with summarize)",
                },
                "summarize": {
                    "type": "boolean",
                    "description": "Generate concise summary (mutually exclusive with search_query, default: false)",
                    "default": False,
                },
            },
            "oneOf": [
                {"required": ["index"]},
                {"required": ["url"]},
            ],
        }

    def is_concurrency_safe(self) -> bool:
        return True

    def needs_permissions(self, parameters: dict[str, Any]) -> bool:
        return False

    async def execute(
        self,
        parameters: dict[str, Any],
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """执行网页内容获取"""
        start_time = time.time()

        try:
            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 获取参数
            session_id = parameters.get("session_id", "default")
            index = parameters.get("index")
            url = parameters.get("url")
            search_query = parameters.get("search_query")
            summarize = parameters.get("summarize", False)

            # 通过 index 获取 URL（如果有 store）
            existing_source: CitationSourceRaw | None = None
            if index is not None:
                if not self._citation_source_store:
                    return self._create_error_result(
                        parameters,
                        "Citation store not available, cannot use index",
                        start_time,
                    )

                existing_source = await self._citation_source_store.get_source_by_index(
                    session_id, index
                )
                if not existing_source:
                    return self._create_error_result(
                        parameters,
                        f"Search result with index {index} not found",
                        start_time,
                    )
                url = existing_source.url
                logger.info(f"Found source by index {index}: {url}")

            if not url:
                return self._create_error_result(
                    parameters, "Error: url parameter is required", start_time
                )

            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 获取内容：先用 curl_cffi，失败则用 Playwright
            content: HtmlContent | None = await self._curl_cffi_client.fetch(url)
            if content:
                logger.info(f"curl_cffi 获取成功: {url}")
            else:
                # 降级使用 playwright
                logger.info(f"curl_cffi 失败，使用 Playwright: {url}")
                await self._playwright_crawl.start()
                content = await self._playwright_crawl.crawl_url(url)

            if not content:
                return self._create_error_result(
                    parameters, "Failed to fetch content", start_time
                )

            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 内容处理：摘要或查询提取
            if self._llm_service:
                if summarize or len(content.text or "") > self.max_length:
                    content = await summarize_by_llm(
                        self._llm_service, content, abort_signal
                    )
                elif search_query:
                    content = await extract_by_query_use_llm(
                        self._llm_service, content, search_query, abort_signal
                    )

            # 截断内容
            processed_content = content.raw_text or content.text or ""
            if len(processed_content) > self.max_length:
                processed_content = truncate_middle(processed_content, self.max_length)

            # 准备元数据
            original_content_dict = content.model_dump(exclude_none=True)
            original_content_dict.pop("raw_html", None)
            original_content_dict.pop("text", None)

            # 存储/更新 citation（如果有 store）
            citation_id = None
            if self._citation_source_store:
                try:
                    if existing_source:
                        # 更新现有记录
                        citation_id = existing_source.citation_id
                        await self._citation_source_store.update_citation_source(
                            citation_id=citation_id,
                            session_id=session_id,
                            updates={
                                "full_content": processed_content,
                                "processed_content": processed_content,
                                "original_content": original_content_dict,
                                "parameters": {
                                    "search_query": search_query,
                                    "summarize": summarize,
                                },
                            },
                        )
                        logger.info(f"Updated citation {citation_id}")
                    else:
                        # 创建新记录
                        citation_id = generate_citation_id(prefix="fetch")
                        new_source = CitationSourceRaw(
                            citation_id=citation_id,
                            session_id=session_id,
                            source_type=CitationSourceType.DIRECT_URL,
                            url=url,
                            title=content.title,
                            full_content=processed_content,
                            processed_content=processed_content,
                            original_content=original_content_dict,
                            parameters={
                                "search_query": search_query,
                                "summarize": summarize,
                            },
                            created_at=datetime.now(),
                        )
                        await self._citation_source_store.store_citation_sources(
                            session_id=session_id,
                            sources=[new_source],
                        )
                        logger.info(f"Created citation {citation_id}")
                except Exception as e:
                    logger.error(f"Citation store failed: {e}")

            # 格式化结果
            result_content = processed_content
            if citation_id:
                result_content = f"[cite:{citation_id}]\n\n{processed_content}"

            return ToolResult(
                tool_name=self.name,
                tool_call_id=parameters.get("tool_call_id", ""),
                input_args=parameters,
                content=result_content,
                output={
                    "url": url,
                    "title": content.title,
                    "content_length": len(processed_content),
                    "citation_id": citation_id,
                    "truncated": len(processed_content) >= self.max_length,
                },
                start_time=start_time,
                end_time=time.time(),
                duration=time.time() - start_time,
                is_success=True,
            )

        except Exception as e:
            return self._create_error_result(
                parameters, f"Error: {e!s}", start_time
            )
