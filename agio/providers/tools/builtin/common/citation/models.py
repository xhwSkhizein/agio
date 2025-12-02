"""Citation 系统数据模型

用于 web_search 和 web_fetch 工具的引用管理，减少 Token 使用。
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CitationSourceType(str, Enum):
    """信息源类型"""

    SEARCH = "search"  # 来自 web_search 工具
    DIRECT_URL = "direct_url"  # 直接通过 URL fetch


class CitationSourceRaw(BaseModel):
    """完整的信息源模型（用于内部存储）"""

    citation_id: str = Field(description="唯一引用 ID")
    session_id: str = Field(description="会话 ID")
    source_type: CitationSourceType = Field(description="来源类型")

    # 基本信息
    url: str = Field(description="网页 URL")
    title: str | None = Field(default=None, description="标题")
    snippet: str | None = Field(default=None, description="摘要（search 结果）")
    date_published: str | None = Field(default=None, description="发布日期")
    source: str | None = Field(default=None, description="来源")

    # 内容信息
    full_content: str | None = Field(default=None, description="完整内容（fetch 结果）")
    processed_content: str | None = Field(
        default=None, description="处理后给 LLM 的内容"
    )
    original_content: dict[str, Any] | None = Field(
        default=None, description="原始内容元数据"
    )

    # 关联关系
    related_citation_id: str | None = Field(
        default=None, description="关联的 citation_id（fetch 关联到 search）"
    )
    related_index: int | None = Field(
        default=None, description="关联的索引（fetch 关联到 search 的 index）"
    )

    # 元数据
    query: str | None = Field(default=None, description="搜索查询（search 类型）")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="处理参数（search_query, summarize 等）"
    )
    index: int | None = Field(
        default=None, description="数字索引（search 结果使用，用于 web_fetch(index=N)）"
    )
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class CitationSourceSimplified(BaseModel):
    """简化的信息源模型（给 LLM，隐藏详细信息）"""

    citation_id: str = Field(description="引用 ID")
    source_type: CitationSourceType = Field(description="来源类型")
    url: str = Field(description="网页 URL")
    index: int | None = Field(
        default=None, description="数字索引（search 结果，用于 web_fetch(index=N)）"
    )
    title: str | None = Field(default=None, description="标题")
    snippet: str | None = Field(default=None, description="摘要")
    date_published: str | None = Field(default=None, description="发布日期")
    source: str | None = Field(default=None, description="来源")
    created_at: datetime | None = Field(default=None, description="创建时间")
