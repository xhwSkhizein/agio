"""LLM 内容处理器

使用 LLM 对网页内容进行摘要和查询提取。
"""

import logging
from typing import TYPE_CHECKING

from agio.components.tools.builtin_tools.common.llm.model_adapter import (
    LLMMessage,
    ModelLLMAdapter,
)
from agio.components.tools.builtin_tools.common.web_fetch.html_extract import (
    HtmlContent,
)

if TYPE_CHECKING:
    from agio.execution.abort_signal import AbortSignal

logger = logging.getLogger(__name__)

SUMMARIZE_SYSTEM_PROMPT = """You are a professional content summarization assistant.
Your task is to:
1. Extract the core information and key insights from the content user provided
2. Maintain factual accuracy and preserve important details
3. Keep the summary comprehensive but concise (aim for 25-35% of original length)
"""

QUERY_SYSTEM_PROMPT = """You are a professional content extraction assistant.
Your task is to:
1. Extract content specifically relevant to the user's query from the content user provided
2. Maintain full context and accuracy of extracted information
3. Preserve technical details, data, and important specifics
4. If no relevant content exists, clearly state so
5. Focus on substantive information, not just keyword matches
"""


async def summarize_by_llm(
    llm_service: ModelLLMAdapter,
    content: HtmlContent,
    abort_signal: "AbortSignal | None" = None,
) -> HtmlContent:
    """使用 LLM 摘要内容

    Args:
        llm_service: LLM 服务
        content: HTML 内容
        abort_signal: 中断信号

    Returns:
        处理后的内容
    """
    text_to_summarize = content.text

    user_message = f"""summarize the following content:

{text_to_summarize}
"""
    try:
        result = await llm_service.invoke(
            messages=[LLMMessage(role="user", content=user_message)],
            system_prompt=SUMMARIZE_SYSTEM_PROMPT,
            abort_signal=abort_signal,
        )
        if result and result.content:
            content.raw_text = result.content
            return content
        else:
            return content
    except Exception as e:
        logger.error(f"Error summarizing content: {e}")
        return content


async def extract_by_query_use_llm(
    llm_service: ModelLLMAdapter,
    content: HtmlContent,
    query: str,
    abort_signal: "AbortSignal | None" = None,
) -> HtmlContent:
    """使用 LLM 根据查询提取内容

    Args:
        llm_service: LLM 服务
        content: HTML 内容
        query: 查询字符串
        abort_signal: 中断信号

    Returns:
        处理后的内容
    """
    text_to_query = content.text

    user_message = f"""the content is:

{text_to_query}

user's query is:
{query}
"""
    try:
        result = await llm_service.invoke(
            messages=[LLMMessage(role="user", content=user_message)],
            system_prompt=QUERY_SYSTEM_PROMPT,
            abort_signal=abort_signal,
        )
        if result and result.content:
            content.raw_text = result.content
            return content
        else:
            return content
    except Exception as e:
        logger.error(f"Error extracting content by query: {e}", extra={"query": query})
        return content
