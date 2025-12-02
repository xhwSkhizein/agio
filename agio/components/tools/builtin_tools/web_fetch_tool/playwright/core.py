import asyncio
import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Any

from playwright.async_api import Page

from agio.components.tools.builtin_tools.adapter import SettingsRegistry
from agio.components.tools.builtin_tools.adapter import AppSettings
from agio.components.tools.builtin_tools.adapter import get_logger
from agio.components.tools.builtin_tools.web_fetch_tool.html_extract import (
    HtmlContent,
    extract_content_from_html,
)
from agio.components.tools.builtin_tools.web_fetch_tool.playwright.exceptions import (
    SessionInvalidException,
    BlockedException,
)
from agio.components.tools.builtin_tools.web_fetch_tool.playwright.chrome_session import (
    ChromeSessionManager,
)


# ==================== 核心爬虫类 ====================
class PlaywrightCrawler:
    """生产级爬虫"""

    def __init__(self, settings: Optional[AppSettings] = None):
        self.logger = get_logger(__name__)
        self._settings = settings or SettingsRegistry.get()
        self.session_manager: Optional[ChromeSessionManager] = None
        self._start_lock = asyncio.Lock()
        self._started = False
        self.site_configs: Dict[str, Dict[str, Any]] = {
            "wechat": {
                "login_url": "https://mp.weixin.qq.com/",
                "content_selectors": ["#js_content", ".rich_media_content"],
                "title_selectors": ["#activity-name", ".rich_media_title"],
                "auth_indicators": [".user_info", ".account_meta_value"],
                "name": "微信公众号",
            },
            "zhihu": {
                "login_url": "https://www.zhihu.com/",
                "content_selectors": [".RichContent-inner", ".Post-RichText"],
                "title_selectors": [".QuestionHeader-title", ".Post-Title"],
                "auth_indicators": [".AppHeader-userInfo", ".Avatar"],
                "name": "知乎",
            },
            "weibo": {
                "login_url": "https://weibo.com/",
                "content_selectors": [".WB_text", ".WB_detail"],
                "title_selectors": [".WB_text", ".WB_info"],
                "auth_indicators": [".gn_name", ".username"],
                "name": "微博",
            },
        }

        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "blocked_requests": 0,
            "start_time": None,
        }

    async def __aenter__(self):
        """上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        await self.stop()

    async def start(self):
        """启动爬虫（线程安全，确保只启动一次）"""
        async with self._start_lock:
            # 如果已经启动，直接返回
            if (
                self._started
                and self.session_manager
                and self.session_manager.is_connected()
            ):
                return

            self.stats["start_time"] = time.time()
            self.logger.info("🚀 启动生产级爬虫")
            if not self.session_manager:
                self.session_manager = ChromeSessionManager(settings=self._settings)

            # 连接到Chrome
            await self.session_manager.connect()
            self._started = True

    async def stop(self):
        """停止爬虫"""
        async with self._start_lock:
            if not self._started:
                return

            self.logger.info("🛑 停止爬虫")

            # 打印统计信息
            self._print_stats()

            # 断开连接
            if self.session_manager:
                await self.session_manager.disconnect()

            self._started = False

    def _print_stats(self):
        """打印统计信息"""
        if not self.stats["start_time"]:
            return

        duration = time.time() - self.stats["start_time"]
        success_rate = (
            (self.stats["successful_requests"] / self.stats["total_requests"] * 100)
            if self.stats["total_requests"] > 0
            else 0
        )

        self.logger.info(
            f"\n📊 爬虫统计:\n"
            f"   总请求: {self.stats['total_requests']}\n"
            f"   成功: {self.stats['successful_requests']}\n"
            f"   失败: {self.stats['failed_requests']}\n"
            f"   被拦截: {self.stats['blocked_requests']}\n"
            f"   成功率: {success_rate:.1f}%\n"
            f"   运行时间: {duration:.1f}s"
        )

    def _is_blocked(self, page: Page) -> bool:
        """检查是否被拦截"""
        url = page.url.lower()
        blocked_keywords = [
            "captcha",
            "verify",
            "validation",
            "robots",
            "checkpoint",
            "challenge",
            "recaptcha",
        ]
        return any(keyword in url for keyword in blocked_keywords)

    async def _extract_content(self, page: Page, url: str) -> HtmlContent | None:
        """提取页面内容"""

        # FIXME use Trafilatura to extract content
        original_html = await page.content()

        content: HtmlContent = extract_content_from_html(
            html=original_html, original_url=url
        )
        if not content:
            return None
        return content

    async def crawl_url(self, url: str, retries: int = 0) -> HtmlContent | None:
        """
        爬取单个URL

        Args:
            url: 目标URL
            retries: 重试次数

        Returns:
            提取的内容数据或None
        """
        if not self.session_manager.is_connected():
            raise SessionInvalidException("未连接到Chrome")

        self.stats["total_requests"] += 1
        self.logger.info(f"正在爬取: {url}")
        try:
            page = await self.session_manager.context.new_page()
            # 设置页面超时
            page.set_default_timeout(
                self._settings.tool.web_fetch_tool_timeout_seconds * 1000
            )

            # 访问页面
            response = await page.goto(
                url, wait_until=self._settings.tool.web_fetch_wait_strategy
            )

            if not response or response.status != 200:
                self.logger.warning(
                    f"HTTP状态异常: {response.status if response else 'None'}"
                )

                self.stats["failed_requests"] += 1
                return None

            # 检查是否被拦截
            if self._is_blocked(page):
                self.logger.warning(f"🚫 请求被拦截: {page.url}")
                self.stats["blocked_requests"] += 1
                raise BlockedException("请求被拦截")

            # 提取内容
            content = await self._extract_content(page, url)
            self.stats["successful_requests"] += 1
            self.logger.info(
                f"✅ 爬取成功: title:{content.title if content else 'None'}", url=url
            )

            return content

        except BlockedException:
            if retries < self._settings.tool.web_fetch_max_retries:
                self.logger.info(
                    f"重试 {retries + 1}/{self._settings.tool.web_fetch_max_retries}"
                )
                await asyncio.sleep(5 * (retries + 1))  # 指数退避
                return await self.crawl_url(url, retries + 1)

        except Exception as e:
            self.logger.error(f"爬取失败: {e}", url=url)
            self.stats["failed_requests"] += 1

            # 健康检查，如果连接断开则重连
            if not await self.session_manager.health_check():
                self.logger.info("检测到连接断开，尝试重连...")
                await self.session_manager.connect()

        finally:
            await page.close()

    async def crawl_batch(
        self, urls: List[str], save_dir: Optional[Path] = None
    ) -> List[Dict[str, Any]]:
        """
        批量爬取URL

        Args:
            urls: URL列表
            save_dir: 保存目录

        Returns:
            成功爬取的内容列表
        """
        results = []
        save_dir = save_dir or Path("crawled_data")
        save_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"开始批量爬取，共 {len(urls)} 个URL")

        for i, url in enumerate(urls, 1):
            self.logger.info(f"\n[{i}/{len(urls)}] 处理 {url}")

            try:
                content = await self.crawl_url(
                    url, retries=self._settings.tool.web_fetch_max_retries
                )
                if content:
                    results.append(content)

                    # 保存到文件
                    file_name = f"{content['timestamp']}_{hash(url)}.json"
                    (save_dir / file_name).write_text(
                        json.dumps(content, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
            except Exception as e:
                self.logger.error(f"处理URL失败: {e}")

        self.logger.info(f"批量爬取完成，成功 {len(results)}/{len(urls)}")
        return results
