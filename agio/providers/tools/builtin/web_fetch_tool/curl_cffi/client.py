from urllib.parse import urlparse
from curl_cffi.requests import Response
from typing import Optional
from agio.providers.tools.builtin.web_fetch_tool.html_extract import (
    HtmlContent,
    extract_content_from_html,
)

from agio.providers.tools.builtin.adapter import get_logger

logger = get_logger(__name__)


class SimpleAsyncClient:
    """极简异步 HTTP 客户端

    提供生产级的网页抓取能力，自动管理会话生命周期，
    支持自定义配置和上下文管理。
    """

    def __init__(self):
        self.timeout = 10  # seconds
        self.impersonate = "chrome"

    async def fetch(self, url: str, **kwargs) -> HtmlContent | None:
        """抓取指定 URL 并返回完整响应对象

        Args:
            url: 目标网址

        Returns:
            curl_cffi.requests.Response 对象，包含 content/text/json() 等方法
        """
        from curl_cffi import requests

        try:
            referer: str = f"https://{urlparse(url).netloc}/"
            response: Response = requests.get(
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
                    f"HTTP {response.status_code}: {response.text[:200]}", url=url
                )
                return None

            return extract_content_from_html(html=response.text, original_url=url)
        except Exception as e:
            logger.error(f"Error fetching content with curl_cffi: {e}", url=url)
            return None


# ==================== 全局共享实例 ====================

_default_client: Optional[SimpleAsyncClient] = None


async def get_default_client() -> SimpleAsyncClient:
    """获取全局默认客户端实例（懒加载）"""
    global _default_client
    if _default_client is None:
        _default_client = SimpleAsyncClient()
    return _default_client


async def fetch(url: str) -> Response:
    """最简单的全局抓取函数

    使用共享的默认客户端和 session，适合单次调用场景。
    对于多次请求，建议使用 SimpleAsyncClient 上下文管理器。
    """
    client = await get_default_client()
    return await client.fetch(url)
