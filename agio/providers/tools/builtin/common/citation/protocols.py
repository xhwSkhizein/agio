"""Citation 系统存储协议

定义信息源存储的抽象接口。
"""

from typing import Any, Protocol

from agio.providers.tools.builtin.common.citation.models import (
    CitationSourceRaw,
    CitationSourceSimplified,
)


class CitationSourceRepository(Protocol):
    """信息源仓储抽象接口

    职责：
    - 存储信息源并生成 citation_id
    - 通过 citation_id 检索信息源
    - 提供简化结果（隐藏详细信息）
    - 支持更新信息源（用于 fetch 时补充完整内容）
    """

    async def store_citation_sources(
        self,
        session_id: str,
        sources: list[CitationSourceRaw],
    ) -> list[str]:
        """存储信息源并返回 citation_id 列表

        Args:
            session_id: 会话 ID
            sources: 信息源列表

        Returns:
            citation_id 列表
        """
        ...

    async def get_citation_source(
        self,
        citation_id: str,
        session_id: str,
    ) -> CitationSourceRaw | None:
        """通过 citation_id 获取原始信息源

        Args:
            citation_id: 引用 ID
            session_id: 会话 ID（用于验证）

        Returns:
            原始信息源或 None
        """
        ...

    async def get_simplified_sources(
        self,
        session_id: str,
        citation_ids: list[str],
    ) -> list[CitationSourceSimplified]:
        """获取简化版信息源（隐藏详细信息）

        Args:
            session_id: 会话 ID
            citation_ids: 引用 ID 列表

        Returns:
            简化版信息源列表
        """
        ...

    async def get_session_citations(
        self,
        session_id: str,
    ) -> list[CitationSourceSimplified]:
        """获取 session 的所有 citations

        Args:
            session_id: 会话 ID

        Returns:
            简化版信息源列表
        """
        ...

    async def update_citation_source(
        self,
        citation_id: str,
        session_id: str,
        updates: dict[str, Any],
    ) -> bool:
        """更新信息源（用于 fetch 时补充完整内容）

        Args:
            citation_id: 引用 ID
            session_id: 会话 ID（用于验证）
            updates: 要更新的字段字典

        Returns:
            是否更新成功
        """
        ...

    async def get_source_by_index(
        self,
        session_id: str,
        index: int,
    ) -> CitationSourceRaw | None:
        """通过索引获取信息源（用于 web_fetch(index=N)）

        Args:
            session_id: 会话 ID
            index: 数字索引

        Returns:
            原始信息源或 None
        """
        ...

    async def cleanup_session(self, session_id: str) -> None:
        """清理特定 session 的信息源

        Args:
            session_id: 要清理的会话 ID
        """
        ...
