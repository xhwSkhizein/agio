"""Web fetch 工具函数"""


def truncate_middle(text: str, max_length: int, ellipsis: str = "...") -> str:
    """从中间截断文本，保留开头和结尾

    Args:
        text: 要截断的文本
        max_length: 最大长度
        ellipsis: 省略号

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text

    if max_length < len(ellipsis):
        return ellipsis[:max_length]

    available_length = max_length - len(ellipsis)

    front_length = (available_length + 1) // 2
    back_length = available_length // 2

    front_part = text[:front_length]
    back_part = text[-back_length:] if back_length > 0 else ""

    return front_part + ellipsis + back_part
