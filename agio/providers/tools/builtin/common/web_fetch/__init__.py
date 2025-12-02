"""Web fetch 公共组件"""

from agio.providers.tools.builtin.common.web_fetch.curl_cffi_client import (
    SimpleAsyncClient,
    fetch,
    get_default_client,
)
from agio.providers.tools.builtin.common.web_fetch.html_extract import (
    HtmlContent,
    extract_content_from_html,
)
from agio.providers.tools.builtin.common.web_fetch.utils import truncate_middle

__all__ = [
    "SimpleAsyncClient",
    "fetch",
    "get_default_client",
    "HtmlContent",
    "extract_content_from_html",
    "truncate_middle",
]
