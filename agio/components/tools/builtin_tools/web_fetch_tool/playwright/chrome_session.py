import asyncio
import os
from typing import Dict, Optional

from agio.components.tools.builtin_tools.adapter import SettingsRegistry
from agio.components.tools.builtin_tools.adapter import AppSettings
from agio.components.tools.builtin_tools.adapter import get_logger
from playwright.async_api import (
    BrowserType,
    Playwright,
    async_playwright,
    Browser,
    BrowserContext,
)

from agio.components.tools.builtin_tools.web_fetch_tool.playwright.cdp_browser import (
    CDPBrowserManager,
)
from agio.components.tools.builtin_tools.web_fetch_tool.playwright.exceptions import (
    SessionInvalidException,
)


# ==================== Chrome会话管理器 ====================
class ChromeSessionManager:
    """Chrome会话管理器"""

    def __init__(self, *, settings: AppSettings | None = None):
        self._settings = settings or SettingsRegistry.get()
        self.logger = get_logger(__name__)
        self.cdp_browser: Optional[CDPBrowserManager] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        self._connected = False
        self._connect_lock = asyncio.Lock()

    async def connect(self) -> bool:
        """连接到Chrome浏览器（线程安全，确保只连接一次）"""
        async with self._connect_lock:
            # 如果已经连接且连接有效，直接返回
            if self._connected and self.is_connected():
                return True

            try:
                # 如果 playwright 已存在但连接断开，先清理
                if self.playwright and not self.is_connected():
                    await self.disconnect()

                self.playwright = await async_playwright().start()
                self.logger.info("[ChromeSessionManager] 使用CDP模式启动浏览器")
                self.context: BrowserContext = await self.launch_browser_with_cdp(
                    self.playwright,
                    None,
                    None,
                    headless=self._settings.tool.web_fetch_headless,
                )
                self._connected = True
                self.logger.info("✅ 成功连接到Chrome")
                return True

            except Exception as e:
                self.logger.error(f"连接失败: {e}")
                if self.cdp_browser:
                    self.logger.error(
                        "请确保Chrome已启动并开启远程调试: "
                        f"chrome --remote-debugging-port={self.cdp_browser.debug_port}"
                    )
                raise SessionInvalidException(f"无法连接到Chrome: {e}")

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """Launch browser and create browser context"""
        if self._settings.tool.web_fetch_save_login_state:
            user_data_dir = os.path.join(
                os.getcwd(), "browser_data", self._settings.tool.web_fetch_user_data_dir
            )  # type: ignore
            browser_context: BrowserContext = await chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                accept_downloads=True,
                headless=headless,
                proxy=playwright_proxy,
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent,
            )
            return browser_context
        else:
            browser = await chromium.launch(headless=headless, proxy=playwright_proxy)
            browser_context: BrowserContext = await browser.new_context(
                viewport={"width": 1920, "height": 1080}, user_agent=user_agent
            )
            return browser_context

    async def launch_browser_with_cdp(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """
        使用CDP模式启动浏览器
        """
        try:
            self.cdp_browser = CDPBrowserManager(settings=self._settings)
            self.context: BrowserContext = await self.cdp_browser.launch_and_connect(
                playwright=playwright,
                playwright_proxy=playwright_proxy,
                user_agent=user_agent,
                headless=headless,
            )
            # 添加反检测脚本
            await self.cdp_browser.add_stealth_script()

            # 显示浏览器信息
            browser_info = await self.cdp_browser.get_browser_info()
            self.logger.info(f"CDP浏览器信息: {browser_info}")

            return self.context

        except Exception as e:
            self.logger.error(f"CDP模式启动失败，回退到标准模式: {e}")
            # 回退到标准模式
            chromium = playwright.chromium
            self.context: BrowserContext = await self.launch_browser(
                chromium, playwright_proxy, user_agent, headless
            )
            return self.context

    async def disconnect(self):
        """断开连接（线程安全）"""
        async with self._connect_lock:
            if not self._connected:
                return

            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            if self.cdp_browser:
                await self.cdp_browser.cleanup()
                self.cdp_browser = None
            self.context = None
            self._connected = False

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected and self.context is not None

    async def health_check(self) -> bool:
        """健康检查"""
        if not self.is_connected():
            return False

        try:
            # 尝试创建新页面测试连接
            page = await self.context.new_page()
            await page.close()
            return True
        except Exception as e:
            self.logger.warning(f"健康检查失败: {e}")
            self._connected = False
            return False
