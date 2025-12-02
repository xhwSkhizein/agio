"""curl_cffi HTTP 客户端

使用 curl_cffi 进行高性能 HTTP 请求。
"""

import logging
from urllib.parse import urlparse

from agio.components.tools.builtin_tools.common.web_fetch.html_extract import (
    HtmlContent,
    extract_content_from_html,
)

logger = logging.getLogger(__name__)


class SimpleAsyncClient:
    """极简异步 HTTP 客户端

    提供生产级的网页抓取能力，自动管理会话生命周期。
    """

    def __init__(self):
        self.timeout = 10  # seconds
        self.impersonate = "chrome"

    async def fetch(self, url: str, **kwargs) -> HtmlContent | None:
        """抓取指定 URL 并返回内容

        Args:
            url: 目标网址
            **kwargs: 额外参数

        Returns:
            HtmlContent 对象或 None
        """
        from curl_cffi import requests

        try:
            referer: str = f"https://{urlparse(url).netloc}/"
            response = requests.get(
                url,
                timeout=self.timeout,
                impersonate=self.impersonate,
                headers=kwargs.get(
                    "headers",
                    {
                        "Referer": referer,
                    },
                ),
                **kwargs,
            )
            if response.status_code != 200:
                logger.warning(
                    f"HTTP {response.status_code}: {response.text[:200]}", extra={"url": url}
                )
                return None

            return extract_content_from_html(html=response.text, original_url=url)
        except Exception as e:
            logger.error(f"Error fetching content with curl_cffi: {e}", extra={"url": url})
            return None


# 全局共享实例
_default_client: SimpleAsyncClient | None = None


async def get_default_client() -> SimpleAsyncClient:
    """获取全局默认客户端实例（懒加载）"""
    global _default_client
    if _default_client is None:
        _default_client = SimpleAsyncClient()
    return _default_client


async def fetch(url: str) -> HtmlContent | None:
    """最简单的全局抓取函数

    使用共享的默认客户端，适合单次调用场景。
    """
    client = await get_default_client()
    return await client.fetch(url)
