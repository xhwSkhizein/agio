from typing import Optional


class BlockedException(Exception):
    """被拦截异常"""

    def __init__(self, message: str, **context):
        super().__init__(message, **context)


class SessionInvalidException(Exception):
    """会话无效异常"""

    def __init__(self, message: str, **context):
        super().__init__(message, **context)
