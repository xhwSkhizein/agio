import os
import platform
import subprocess
import time
import socket
import signal
from typing import Optional, Tuple
from agio.providers.tools.builtin.adapter import SettingsRegistry
from agio.providers.tools.builtin.adapter import AppSettings
from agio.providers.tools.builtin.adapter import get_logger

logger = get_logger(__name__)


class ChromeLauncher:
    """Chrome 启动器"""

    def __init__(self, *, settings: AppSettings | None = None):
        self._settings = settings or SettingsRegistry.get()
        self.system = platform.system()
        self.browser_process = None
        self.debug_port = None

    def detect_browser_paths(self) -> list[str]:
        """
        检测系统中可用的浏览器路径
        返回按优先级排序的浏览器路径列表
        """
        paths = []

        if self.system == "Windows":
            # Windows下的常见Chrome/Edge安装路径
            possible_paths = [
                # Chrome路径
                os.path.expandvars(
                    r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"
                ),
                os.path.expandvars(
                    r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"
                ),
                os.path.expandvars(
                    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
                ),
                # Edge路径
                os.path.expandvars(
                    r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"
                ),
                os.path.expandvars(
                    r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"
                ),
                # Chrome Beta/Dev/Canary
                os.path.expandvars(
                    r"%LOCALAPPDATA%\Google\Chrome Beta\Application\chrome.exe"
                ),
                os.path.expandvars(
                    r"%LOCALAPPDATA%\Google\Chrome Dev\Application\chrome.exe"
                ),
                os.path.expandvars(
                    r"%LOCALAPPDATA%\Google\Chrome SxS\Application\chrome.exe"
                ),
            ]
        elif self.system == "Darwin":  # macOS
            # macOS下的常见Chrome/Edge安装路径
            possible_paths = [
                # Chrome路径
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
                "/Applications/Google Chrome Dev.app/Contents/MacOS/Google Chrome Dev",
                "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
                # Edge路径
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "/Applications/Microsoft Edge Beta.app/Contents/MacOS/Microsoft Edge Beta",
                "/Applications/Microsoft Edge Dev.app/Contents/MacOS/Microsoft Edge Dev",
                "/Applications/Microsoft Edge Canary.app/Contents/MacOS/Microsoft Edge Canary",
            ]
        else:
            # Linux等其他系统
            possible_paths = [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/google-chrome-beta",
                "/usr/bin/google-chrome-unstable",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
                "/snap/bin/chromium",
                "/usr/bin/microsoft-edge",
                "/usr/bin/microsoft-edge-stable",
                "/usr/bin/microsoft-edge-beta",
                "/usr/bin/microsoft-edge-dev",
            ]

        # 检查路径是否存在且可执行
        for path in possible_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                paths.append(path)

        return paths

    def find_free_port(self, start_port: int = 9222) -> int:
        """找到一个可用的端口"""
        for port in range(start_port, start_port + 100):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("localhost", port)) != 0:
                    return port
        raise RuntimeError("找不到可用的端口")

    def launch_browser(
        self,
        browser_path: str,
        debug_port: int,
        headless: bool = False,
        user_data_dir: Optional[str] = None,
    ) -> subprocess.Popen:
        """
        启动浏览器进程
        """
        # 基本启动参数
        args = [
            browser_path,
            f"--remote-debugging-port={debug_port}",
            "--remote-debugging-address=127.0.0.1",  # 仅允许本地访问，修复安全漏洞
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=TranslateUI",
            "--disable-ipc-flooding-protection",
            "--disable-hang-monitor",
            "--disable-prompt-on-repost",
            "--disable-sync",
            "--disable-dev-shm-usage",  # 避免共享内存问题
            "--no-sandbox",  # 在CDP模式下关闭沙箱
            # 🔥 关键反检测参数
            "--disable-blink-features=AutomationControlled",  # 禁用自动化控制标记
            "--exclude-switches=enable-automation",  # 排除自动化开关
            "--disable-infobars",  # 禁用信息栏
            "--disable-setuid-sandbox",  # 禁用setuid沙箱
        ]

        # 无头模式
        if headless:
            args.extend(
                [
                    "--headless=new",  # 使用新的headless模式
                    "--disable-gpu",
                ]
            )
        else:
            # 非无头模式的额外参数
            args.extend(
                [
                    "--start-maximized",  # 最大化窗口,更像真实用户
                ]
            )

        # 用户数据目录
        if user_data_dir:
            args.append(f"--user-data-dir={user_data_dir}")

        logger.info(f"[BrowserLauncher] 启动浏览器: {browser_path}")
        logger.info(f"[BrowserLauncher] 调试端口: {debug_port}")
        logger.info(f"[BrowserLauncher] 无头模式: {headless}")

        try:
            # 在Windows上，使用CREATE_NEW_PROCESS_GROUP避免Ctrl+C影响子进程
            if self.system == "Windows":
                process = subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:
                process = subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid,  # 创建新的进程组
                )

            self.browser_process = process
            return process

        except Exception as e:
            logger.error(f"[BrowserLauncher] 启动浏览器失败: {e}")
            raise

    def wait_for_browser_ready(self, debug_port: int, timeout: int = 30) -> bool:
        """
        等待浏览器准备就绪
        """
        logger.info(f"[BrowserLauncher] 等待浏览器在端口 {debug_port} 上准备就绪...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(("localhost", debug_port))
                    if result == 0:
                        logger.info(
                            f"[BrowserLauncher] 浏览器已在端口 {debug_port} 上准备就绪"
                        )
                        return True
            except Exception:
                pass

            time.sleep(0.5)

        logger.error(f"[BrowserLauncher] 浏览器在 {timeout} 秒内未能准备就绪")
        return False

    def get_browser_info(self, browser_path: str) -> Tuple[str, str]:
        """
        获取浏览器信息（名称和版本）
        """
        try:
            if "chrome" in browser_path.lower():
                name = "Google Chrome"
            elif "edge" in browser_path.lower() or "msedge" in browser_path.lower():
                name = "Microsoft Edge"
            elif "chromium" in browser_path.lower():
                name = "Chromium"
            else:
                name = "Unknown Browser"

            # 尝试获取版本信息
            try:
                result = subprocess.run(
                    [browser_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                version = result.stdout.strip() if result.stdout else "Unknown Version"
            except:
                version = "Unknown Version"

            return name, version

        except Exception:
            return "Unknown Browser", "Unknown Version"

    def cleanup(self):
        """
        清理资源，关闭浏览器进程
        """
        if not self.browser_process:
            return

        process = self.browser_process

        if process.poll() is not None:
            logger.info("[BrowserLauncher] 浏览器进程已退出，无需清理")
            self.browser_process = None
            return

        logger.info("[BrowserLauncher] 正在关闭浏览器进程...")

        try:
            if self.system == "Windows":
                # 先尝试正常终止
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(
                        "[BrowserLauncher] 正常终止超时，使用taskkill强制结束"
                    )
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                        capture_output=True,
                        check=False,
                    )
                    process.wait(timeout=5)
            else:
                pgid = os.getpgid(process.pid)
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except ProcessLookupError:
                    logger.info("[BrowserLauncher] 浏览器进程组不存在，可能已退出")
                else:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.warning("[BrowserLauncher] 优雅关闭超时，发送SIGKILL")
                        os.killpg(pgid, signal.SIGKILL)
                        process.wait(timeout=5)

            logger.info("[BrowserLauncher] 浏览器进程已关闭")
        except Exception as e:
            logger.warning(f"[BrowserLauncher] 关闭浏览器进程时出错: {e}")
        finally:
            self.browser_process = None
