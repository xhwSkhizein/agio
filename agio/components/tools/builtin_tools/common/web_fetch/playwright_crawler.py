"""Playwright 爬虫

使用 Playwright 进行浏览器自动化爬取。
"""

import asyncio
import logging
import time

from playwright.async_api import Page, async_playwright

from agio.components.tools.builtin_tools.adapter import AppSettings, SettingsRegistry
from agio.components.tools.builtin_tools.common.web_fetch.html_extract import (
    HtmlContent,
    extract_content_from_html,
)

logger = logging.getLogger(__name__)


class PlaywrightCrawlerException(Exception):
    """爬虫异常基类"""
    pass


class BlockedException(PlaywrightCrawlerException):
    """被拦截异常"""
    pass


class SessionInvalidException(PlaywrightCrawlerException):
    """会话无效异常"""
    pass


class PlaywrightCrawler:
    """Playwright 爬虫（简化版）"""

    def __init__(self, settings: AppSettings | None = None):
        self._settings = settings or SettingsRegistry.get()
        self.playwright = None
        self.browser = None
        self.context = None
        self._start_lock = asyncio.Lock()
        self._started = False

        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "blocked_requests": 0,
            "start_time": None,
        }

    async def start(self):
        """启动爬虫"""
        async with self._start_lock:
            if self._started and self.context:
                return

            self.stats["start_time"] = time.time()
            logger.info("启动 Playwright 爬虫")

            try:
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(
                    headless=self._settings.tool.web_fetch_headless
                )
                self.context = await self.browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                )
                self._started = True
            except Exception as e:
                logger.error(f"启动失败: {e}")
                raise SessionInvalidException(f"无法启动: {e}")

    async def stop(self):
        """停止爬虫"""
        async with self._start_lock:
            if not self._started:
                return

            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()

            self._started = False

    def _is_blocked(self, page: Page) -> bool:
        """检查是否被拦截"""
        url = page.url.lower()
        blocked_keywords = ["captcha", "verify", "validation", "robots"]
        return any(keyword in url for keyword in blocked_keywords)

    async def crawl_url(self, url: str, retries: int = 0) -> HtmlContent | None:
        """爬取 URL"""
        if not self.context:
            raise SessionInvalidException("未启动爬虫")

        self.stats["total_requests"] += 1
        page = None
        
        try:
            page = await self.context.new_page()
            page.set_default_timeout(
                self._settings.tool.web_fetch_tool_timeout_seconds * 1000
            )

            response = await page.goto(url, wait_until="domcontentloaded")

            if not response or response.status != 200:
                self.stats["failed_requests"] += 1
                return None

            if self._is_blocked(page):
                self.stats["blocked_requests"] += 1
                raise BlockedException("请求被拦截")

            original_html = await page.content()
            content = extract_content_from_html(html=original_html, original_url=url)
            
            self.stats["successful_requests"] += 1
            return content

        except BlockedException:
            if retries < self._settings.tool.web_fetch_max_retries:
                await asyncio.sleep(5 * (retries + 1))
                return await self.crawl_url(url, retries + 1)
            return None

        except Exception as e:
            logger.error(f"爬取失败: {e}")
            self.stats["failed_requests"] += 1
            return None

        finally:
            if page:
                await page.close()
