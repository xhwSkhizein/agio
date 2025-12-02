"""
Playwright 配置管理
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PlaywrightConfig:
    """Playwright 配置"""
    
    # 浏览器配置
    headless: bool = True
    """无头模式"""
    
    browser_type: str = "chromium"
    """浏览器类型"""
    
    browser_path: Optional[str] = None
    """自定义浏览器路径"""
    
    # 页面配置
    viewport_width: int = 1920
    """视口宽度"""
    
    viewport_height: int = 1080
    """视口高度"""
    
    # 性能优化
    disable_images: bool = True
    """禁用图片加载"""
    
    disable_fonts: bool = True
    """禁用字体加载"""
    
    disable_css: bool = False
    """禁用 CSS"""
    
    disable_javascript: bool = False
    """禁用 JavaScript"""
    
    # 等待配置
    wait_until: str = "domcontentloaded"
    """页面加载等待条件"""
    
    navigation_timeout: int = 30000
    """导航超时（毫秒）"""
    
    # 安全配置
    disable_sandbox: bool = False
    """禁用沙箱"""
    
    restrict_debug_access: bool = True
    """限制调试访问"""