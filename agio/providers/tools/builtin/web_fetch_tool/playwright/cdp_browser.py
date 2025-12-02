import os
import asyncio
import socket
import httpx
from typing import Optional, Dict, Any
from playwright.async_api import Browser, BrowserContext, Playwright

from agio.providers.tools.builtin.adapter import SettingsRegistry
from agio.providers.tools.builtin.adapter import AppSettings
from agio.providers.tools.builtin.adapter import get_logger

logger = get_logger(__name__)


from .chrome_launcher import ChromeLauncher


class CDPBrowserManager:
    """CDP浏览器管理器"""

    def __init__(self, *, settings: AppSettings | None = None):
        self._settings = settings or SettingsRegistry.get()
        self.launcher = ChromeLauncher()
        self.browser: Optional[Browser] = None
        self.browser_context: Optional[BrowserContext] = None
        self.debug_port: Optional[int] = None

    async def launch_and_connect(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict] = None,
        user_agent: Optional[str] = None,
        headless: bool = True,
    ) -> BrowserContext:
        """
        启动浏览器并通过CDP连接
        """
        try:
            # 1. 检测浏览器路径
            browser_path = await self._get_browser_path()

            # 2. 获取可用端口
            self.debug_port = self.launcher.find_free_port(start_port=19222)

            # 3. 启动浏览器
            await self._launch_browser(browser_path, headless)

            # 4. 通过CDP连接
            await self._connect_via_cdp(playwright)

            # 5. 创建浏览器上下文
            browser_context = await self._create_browser_context(
                playwright_proxy, user_agent
            )

            self.browser_context = browser_context
            return browser_context

        except Exception as e:
            logger.error(f"[CDPBrowserManager] CDP浏览器启动失败: {e}")
            await self.cleanup()
            raise

    async def _get_browser_path(self) -> str:
        """
        获取浏览器路径
        """
        # 优先使用用户自定义路径
        custom_browser_path = self._settings.tool.web_fetch_custom_browser_path
        if custom_browser_path and os.path.isfile(custom_browser_path):
            logger.info(
                f"[CDPBrowserManager] 使用自定义浏览器路径: {custom_browser_path}"
            )
            return custom_browser_path

        # 自动检测浏览器路径
        browser_paths = self.launcher.detect_browser_paths()

        if not browser_paths:
            raise RuntimeError(
                "未找到可用的浏览器。请确保已安装Chrome或Edge浏览器，"
                "或在配置文件中设置CUSTOM_BROWSER_PATH指定浏览器路径。"
            )

        browser_path = browser_paths[0]  # 使用第一个找到的浏览器
        browser_name, browser_version = self.launcher.get_browser_info(browser_path)

        logger.info(
            f"[CDPBrowserManager] 检测到浏览器: {browser_name} ({browser_version})"
        )
        logger.info(f"[CDPBrowserManager] 浏览器路径: {browser_path}")

        return browser_path

    async def _test_cdp_connection(self, debug_port: int) -> bool:
        """
        测试CDP连接是否可用
        """
        try:
            # 简单的socket连接测试
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                result = s.connect_ex(("localhost", debug_port))
                if result == 0:
                    logger.info(f"[CDPBrowserManager] CDP端口 {debug_port} 可访问")
                    return True
                else:
                    logger.warning(f"[CDPBrowserManager] CDP端口 {debug_port} 不可访问")
                    return False
        except Exception as e:
            logger.warning(f"[CDPBrowserManager] CDP连接测试失败: {e}")
            return False

    async def _launch_browser(self, browser_path: str, headless: bool):
        """
        启动浏览器进程
        """
        save_login_state = self._settings.tool.web_fetch_save_login_state
        user_data_dir = self._settings.tool.web_fetch_user_data_dir
        browser_launch_timeout = self._settings.tool.web_fetch_browser_launch_timeout
        # 设置用户数据目录（如果启用了保存登录状态）
        user_data_dir = None
        if save_login_state:
            user_data_dir = os.path.join(
                os.getcwd(),
                f"{self._settings.tool.web_fetch_user_data_dir}",
            )
            os.makedirs(user_data_dir, exist_ok=True)
            logger.info(f"[CDPBrowserManager] 用户数据目录: {user_data_dir}")

        # 启动浏览器
        self.launcher.browser_process = self.launcher.launch_browser(
            browser_path=browser_path,
            debug_port=self.debug_port,
            headless=headless,
            user_data_dir=user_data_dir,
        )

        # 等待浏览器准备就绪
        if not self.launcher.wait_for_browser_ready(
            self.debug_port, browser_launch_timeout
        ):
            raise RuntimeError(f"浏览器在 {browser_launch_timeout} 秒内未能启动")

        # 额外等待一秒让CDP服务完全启动
        await asyncio.sleep(1)

        # 测试CDP连接
        if not await self._test_cdp_connection(self.debug_port):
            logger.warning("[CDPBrowserManager] CDP连接测试失败，但将继续尝试连接")

    async def _get_browser_websocket_url(self, debug_port: int) -> str:
        """
        获取浏览器的WebSocket连接URL
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://localhost:{debug_port}/json/version", timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    ws_url = data.get("webSocketDebuggerUrl")
                    if ws_url:
                        logger.info(
                            f"[CDPBrowserManager] 获取到浏览器WebSocket URL: {ws_url}"
                        )
                        return ws_url
                    else:
                        raise RuntimeError("未找到webSocketDebuggerUrl")
                else:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"[CDPBrowserManager] 获取WebSocket URL失败: {e}")
            raise

    async def _connect_via_cdp(self, playwright: Playwright):
        """
        通过CDP连接到浏览器
        """
        try:
            # 获取正确的WebSocket URL
            ws_url = await self._get_browser_websocket_url(self.debug_port)
            logger.info(f"[CDPBrowserManager] 正在通过CDP连接到浏览器: {ws_url}")

            # 使用Playwright的connectOverCDP方法连接
            self.browser = await playwright.chromium.connect_over_cdp(ws_url)

            if self.browser.is_connected():
                logger.info("[CDPBrowserManager] 成功连接到浏览器")
                logger.info(
                    f"[CDPBrowserManager] 浏览器上下文数量: {len(self.browser.contexts)}"
                )
            else:
                raise RuntimeError("CDP连接失败")

        except Exception as e:
            logger.error(f"[CDPBrowserManager] CDP连接失败: {e}")
            raise

    async def _create_browser_context(
        self, playwright_proxy: Optional[Dict] = None, user_agent: Optional[str] = None
    ) -> BrowserContext:
        """
        创建或获取浏览器上下文
        """
        if not self.browser:
            raise RuntimeError("浏览器未连接")

        # 获取现有上下文或创建新的上下文
        contexts = self.browser.contexts

        if contexts:
            # 使用现有的第一个上下文
            browser_context = contexts[0]
            logger.info("[CDPBrowserManager] 使用现有的浏览器上下文")
        else:
            # 创建新的上下文
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "accept_downloads": True,
            }

            # 设置用户代理
            if user_agent:
                context_options["user_agent"] = user_agent
                logger.info(f"[CDPBrowserManager] 设置用户代理: {user_agent}")

            # 注意：CDP模式下代理设置可能不生效，因为浏览器已经启动
            if playwright_proxy:
                logger.warning(
                    "[CDPBrowserManager] 警告: CDP模式下代理设置可能不生效，"
                    "建议在浏览器启动前配置系统代理或浏览器代理扩展"
                )

            browser_context = await self.browser.new_context(**context_options)
            logger.info("[CDPBrowserManager] 创建新的浏览器上下文")

        return browser_context

    async def add_stealth_script(self, script_path: str = "libs/stealth.min.js"):
        """
        添加反检测脚本
        """
        if self.browser_context and os.path.exists(script_path):
            try:
                await self.browser_context.add_init_script(path=script_path)
                logger.info(f"[CDPBrowserManager] 已添加反检测脚本: {script_path}")
            except Exception as e:
                logger.warning(f"[CDPBrowserManager] 添加反检测脚本失败: {e}")

    async def add_cookies(self, cookies: list):
        """
        添加Cookie
        """
        if self.browser_context:
            try:
                await self.browser_context.add_cookies(cookies)
                logger.info(f"[CDPBrowserManager] 已添加 {len(cookies)} 个Cookie")
            except Exception as e:
                logger.warning(f"[CDPBrowserManager] 添加Cookie失败: {e}")

    async def get_cookies(self) -> list:
        """
        获取当前Cookie
        """
        if self.browser_context:
            try:
                cookies = await self.browser_context.cookies()
                return cookies
            except Exception as e:
                logger.warning(f"[CDPBrowserManager] 获取Cookie失败: {e}")
                return []
        return []

    async def cleanup(self):
        """
        清理资源
        """
        try:
            # 关闭浏览器上下文
            if self.browser_context:
                try:
                    await self.browser_context.close()
                    logger.info("[CDPBrowserManager] 浏览器上下文已关闭")
                except Exception as context_error:
                    logger.warning(
                        f"[CDPBrowserManager] 关闭浏览器上下文失败: {context_error}"
                    )
                finally:
                    self.browser_context = None

            # 断开浏览器连接
            if self.browser:
                try:
                    await self.browser.close()
                    logger.info("[CDPBrowserManager] 浏览器连接已断开")
                except Exception as browser_error:
                    logger.warning(
                        f"[CDPBrowserManager] 关闭浏览器连接失败: {browser_error}"
                    )
                finally:
                    self.browser = None

            # 关闭浏览器进程（如果配置为自动关闭）
            if self._settings.tool.web_fetch_auto_close_browser:
                self.launcher.cleanup()
            else:
                logger.info(
                    "[CDPBrowserManager] 浏览器进程保持运行（AUTO_CLOSE_BROWSER=False）"
                )

        except Exception as e:
            logger.error(f"[CDPBrowserManager] 清理资源时出错: {e}")

    def is_connected(self) -> bool:
        """
        检查是否已连接到浏览器
        """
        return self.browser is not None and self.browser.is_connected()

    async def get_browser_info(self) -> Dict[str, Any]:
        """
        获取浏览器信息
        """
        if not self.browser:
            return {}

        try:
            version = self.browser.version
            contexts_count = len(self.browser.contexts)

            return {
                "version": version,
                "contexts_count": contexts_count,
                "debug_port": self.debug_port,
                "is_connected": self.is_connected(),
            }
        except Exception as e:
            logger.warning(f"[CDPBrowserManager] 获取浏览器信息失败: {e}")
            return {}
