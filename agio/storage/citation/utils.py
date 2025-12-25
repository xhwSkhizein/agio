"""Citation 系统工具函数"""

import secrets
from datetime import datetime


def generate_citation_id(prefix: str = "cite") -> str:
    """生成唯一的 citation ID

    Args:
        prefix: ID 前缀（如 "search", "fetch"）

    Returns:
        格式为 "{prefix}-{timestamp}-{random}" 的唯一 ID
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = secrets.token_hex(4)
    return f"{prefix}-{timestamp}-{random_suffix}"

