"""
WebSearchTool - 网页搜索工具

使用 Serper API 进行 Google 搜索
"""

import http.client
import json
from agio.utils.logging import get_logger
import os
import time
from datetime import datetime
from typing import Any

from agio.providers.tools.base import BaseTool, RiskLevel, ToolCategory
from agio.providers.tools.builtin.adapter import AppSettings, SettingsRegistry
from agio.storage.citation import (
    CitationSourceRaw,
    CitationSourceSimplified,
    CitationSourceType,
    generate_citation_id,
)
from agio.domain import ToolResult

from agio.storage.citation import CitationSourceRepository
from agio.runtime.control import AbortSignal
from agio.runtime.protocol import ExecutionContext

logger = get_logger(__name__)


class WebSearchTool(BaseTool):
    """网页搜索工具，使用 Serper API 进行 Google 搜索

    优化特性：
    - 搜索结果存储到 MongoDB（支持 TTL 自动清理）
    - 使用数字索引（0, 1, 2...）最小化 token 占用
    - 向 LLM 隐藏 URL，减少 60-70% token 消耗
    - 支持通过索引在 web_fetch 中获取完整内容
    """

    # Enable caching - search results are stable within a session
    cacheable = True

    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        citation_source_store: "CitationSourceRepository | None" = None,
    ) -> None:
        super().__init__()
        self._settings = settings or SettingsRegistry.get()
        self.category = ToolCategory.WEB
        self.risk_level = RiskLevel.LOW
        self.timeout_seconds = self._settings.tool.web_search_tool_timeout_seconds
        self.max_results = self._settings.tool.web_search_max_results
        self.serper_api_key = os.getenv("SERPER_API_KEY", "")
        self._citation_source_store = citation_source_store

    def get_name(self) -> str:
        """返回工具名称"""
        return "web_search"

    def get_description(self) -> str:
        """返回工具描述"""
        return """This tool performs Google searches and returns:
- Numbered search results (0, 1, 2...) with titles and snippets
- Publication dates (when available)
- Source information

Use this tool when you need to:
- Find current information not in your training data
- Research topics or gather facts
- Discover relevant web resources
- Get multiple perspectives on a topic

To fetch full content from a search result, use web_fetch tool with the result index:
> web_fetch(index=0) => Fetch content from the first search result"""

    def get_parameters(self) -> dict[str, Any]:
        """返回工具参数 JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "oneOf": [
                        {"type": "string", "description": "single search query"},
                        {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "multiple search queries list",
                        },
                    ],
                    "description": "search query (single or multiple)",
                },
            },
            "required": ["query"],
        }

    def is_concurrency_safe(self) -> bool:
        """是否支持并发"""
        return True

    def needs_permissions(self, parameters: dict[str, Any]) -> bool:
        """检查工具是否需要权限检查"""
        # 网络搜索是低风险操作
        return False

    def _contains_chinese(self, text: str) -> bool:
        """检查文本是否包含中文字符"""
        return any("\u4e00" <= char <= "\u9fff" for char in text)

    def _google_search_with_serp(self, query: str) -> list[dict] | str:
        """使用 Serper API 执行 Google 搜索"""
        if not self.serper_api_key:
            return "Error: SERPER_API_KEY is not set. Please set the SERPER_API_KEY environment variable."

        try:
            conn = http.client.HTTPSConnection("google.serper.dev")

            # 根据查询语言设置地区和语言
            # if self._contains_chinese(query):
            #     payload = json.dumps(
            #         {
            #             "q": query,
            #             "location": "China",
            #             "gl": "cn",
            #             "hl": "zh-cn",
            #             "tbs": "qdr:y",
            #         }
            #     )
            # else:
            payload = json.dumps(
                {
                    "q": query,
                    "location": "United States",
                    "gl": "us",
                    "hl": "en",
                    "tbs": "qdr:y",
                }
            )

            headers = {
                "X-API-KEY": self.serper_api_key,
                "Content-Type": "application/json",
            }

            # 重试机制（最多 5 次）
            res = None
            for i in range(5):
                try:
                    conn.request("POST", "/search", payload, headers)
                    res = conn.getresponse()
                    break
                except Exception as e:
                    logger.warning(f"Search attempt {i + 1} failed: {e!s}")
                    if i == 4:
                        return "Error: Google search timeout. Please try again later."
                    continue

            if res is None:
                return "Error: Failed to connect to search service."

            data = res.read()
            results = json.loads(data.decode("utf-8"))

            # 检查是否有搜索结果
            if "organic" not in results:
                return (
                    f"No results found for query: '{query}'. Try a less specific query."
                )

            # 提取搜索结果（返回原始数据）
            search_results = []
            for page in results.get("organic", []):
                if len(search_results) >= self.max_results:
                    break

                # 提取结果数据
                title = page.get("title", "No title")
                link = page.get("link", "")
                snippet = page.get("snippet", "")
                # 清理无用内容
                snippet = snippet.replace("Your browser can't play this video.", "")
                date_published = page.get("date", "")
                source = page.get("source", "")

                search_results.append(
                    {
                        "url": link,
                        "title": title,
                        "snippet": snippet,
                        "date_published": date_published,
                        "source": source,
                    }
                )

            return search_results

        except Exception as e:
            logger.error(f"Error during search: {e!s}")
            raise

    def _format_simplified_results(
        self,
        query: str,
        simplified_results: list[CitationSourceSimplified],
        citation_ids: list[str],
    ) -> str:
        """格式化简化结果（不包含 URL，使用数字索引和 citation 标记）"""
        content_parts = [
            f"A Google search for '{query}' found {len(simplified_results)} results:",
            "\n## Web Results\n",
        ]

        for i, result in enumerate(simplified_results):
            citation_id = (
                citation_ids[i] if i < len(citation_ids) else result.citation_id
            )
            citation_mark = f"[cite:{citation_id}] " if citation_id else ""

            index_str = f"{result.index}. " if result.index is not None else ""
            parts = [f"{index_str}{citation_mark}{result.title or 'No title'}"]
            if result.date_published:
                parts.append(f"\nDate published: {result.date_published}")
            if result.source:
                parts.append(f"\nSource: {result.source}")
            if result.snippet:
                parts.append(f"\n{result.snippet}")

            content_parts.append("".join(parts))

        content_parts.append(
            "\n\n**Note**: To fetch full content from any result, use: web_fetch(index=N)"
        )

        return "\n\n".join(content_parts)

    def _format_fallback_results(
        self,
        query: str,
        raw_results: list[dict],
    ) -> str:
        """降级格式化（包含 URL，用于存储失败时）"""
        content_parts = [
            f"A Google search for '{query}' found {len(raw_results)} results:",
            "\n## Web Results\n",
        ]

        for idx, item in enumerate(raw_results):
            parts = [f"{idx}. [{item['title']}]({item['url']})"]
            if item.get("date_published"):
                parts.append(f"\nDate published: {item['date_published']}")
            if item.get("source"):
                parts.append(f"\nSource: {item['source']}")
            if item.get("snippet"):
                parts.append(f"\n{item['snippet']}")

            content_parts.append("".join(parts))

        return "\n\n".join(content_parts)

    def _convert_to_citation_sources(
        self,
        raw_results: list[dict],
        query: str,
        session_id: str,
        start_index: int = 0,
    ) -> list[CitationSourceRaw]:
        """转换原始结果为 CitationSourceRaw 模型"""
        citation_sources = []
        for offset, item in enumerate(raw_results):
            citation_id = generate_citation_id(prefix="search")
            citation_sources.append(
                CitationSourceRaw(
                    citation_id=citation_id,
                    session_id=session_id,
                    source_type=CitationSourceType.SEARCH,
                    url=item["url"],
                    title=item["title"],
                    snippet=item["snippet"],
                    date_published=item.get("date_published"),
                    source=item.get("source"),
                    query=query,
                    index=start_index + offset,
                    created_at=datetime.now(),
                )
            )
        return citation_sources

    async def _process_and_format_results(
        self,
        query: str,
        raw_results: list[dict],
        session_id: str,
    ) -> tuple[str, list[str]]:
        """处理并格式化搜索结果（存储 + 格式化，带降级）

        Returns:
            (格式化后的结果文本, citation_id 列表)
        """
        # 尝试存储并返回简化格式
        if self._citation_source_store:
            try:
                # 获取当前 session 的最大 index
                existing_sources = (
                    await self._citation_source_store.get_session_citations(session_id)
                )
                start_index = (
                    max(
                        (s.index for s in existing_sources if s.index is not None),
                        default=-1,
                    )
                    + 1
                    if existing_sources
                    else 0
                )

                # 转换为 CitationSourceRaw 模型
                citation_sources = self._convert_to_citation_sources(
                    raw_results, query, session_id, start_index
                )

                # 存储并获取 citation_ids
                citation_ids = await self._citation_source_store.store_citation_sources(
                    session_id=session_id,
                    sources=citation_sources,
                )

                # 获取简化结果
                simplified_results = (
                    await self._citation_source_store.get_simplified_sources(
                        session_id=session_id,
                        citation_ids=citation_ids,
                    )
                )

                logger.info(
                    "citation_sources_stored_and_simplified",
                    query=query,
                    result_count=len(simplified_results),
                    citation_ids=citation_ids,
                )

                result_text = self._format_simplified_results(
                    query=query,
                    simplified_results=simplified_results,
                    citation_ids=citation_ids,
                )
                return result_text, citation_ids

            except Exception as e:
                logger.error(
                    "citation_source_store_failed",
                    query=query,
                    error=str(e),
                )
                # 降级：返回原始格式
                return self._format_fallback_results(query, raw_results), []
        else:
            # 无存储实例：返回原始格式
            return self._format_fallback_results(query, raw_results), []

    async def execute(
        self,
        parameters: dict[str, Any],
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """执行网页搜索"""
        start_time = time.time()

        try:
            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 获取参数
            session_id = parameters.get("session_id", "default")
            query = parameters.get("query")

            if not query:
                return self._create_error_result(
                    parameters, "Error: No query provided", start_time
                )

            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 处理单个查询
            if isinstance(query, str):
                raw_results = self._google_search_with_serp(query)

                if isinstance(raw_results, str):  # 错误消息
                    return self._create_error_result(parameters, raw_results, start_time)

                # 检查中断
                if abort_signal and abort_signal.is_aborted():
                    return self._create_abort_result(parameters, start_time)

                # 处理并格式化结果
                result_text, citation_ids = await self._process_and_format_results(
                    query=query,
                    raw_results=raw_results,
                    session_id=session_id,
                )

                return ToolResult(
                    tool_name=self.name,
                    tool_call_id=parameters.get("tool_call_id", ""),
                    input_args=parameters,
                    content=result_text,
                    output={
                        "query": query,
                        "result_count": len(raw_results),
                        "citation_ids": citation_ids,
                    },
                    start_time=start_time,
                    end_time=time.time(),
                    duration=time.time() - start_time,
                    is_success=True,
                )

            # 处理多个查询（暂不支持）
            return self._create_error_result(
                parameters,
                "Error: Multiple queries not yet supported in refactored version",
                start_time,
            )

        except Exception as exc:
            error_message = str(exc) if str(exc) else "Unknown error occurred"
            return self._create_error_result(
                parameters, f"Error performing web search: {error_message}", start_time
            )
