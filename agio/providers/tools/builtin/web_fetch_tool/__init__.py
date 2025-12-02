"""
Web Fetch Tool - 高级网页抓取工具

提供基于 curl_cffi 和 Playwright 的双重网页抓取方案：
- curl_cffi: 轻量级 HTTP 客户端，适合静态页面
- Playwright: 浏览器自动化，适合 JavaScript 渲染页面
"""

from .web_fetch_tool import WebFetchTool

__all__ = ["WebFetchTool"]