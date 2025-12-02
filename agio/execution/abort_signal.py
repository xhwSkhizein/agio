"""
中断信号机制，用于优雅地取消长时间运行的操作。

基于 asyncio.Event 实现，支持：
- 同步检查中断状态
- 异步等待中断信号
- 记录中断原因
"""

import asyncio
from typing import Optional


class AbortSignal:
    """
    中断信号，用于在执行过程中响应取消请求。
    
    Examples:
        >>> signal = AbortSignal()
        >>> 
        >>> # 在另一个任务中触发中断
        >>> signal.abort("User cancelled")
        >>> 
        >>> # 在工具执行中检查
        >>> if signal.is_aborted():
        >>>     return  # 提前退出
        >>> 
        >>> # 或异步等待
        >>> await signal.wait()
    """
    
    def __init__(self):
        self._event = asyncio.Event()
        self._reason: Optional[str] = None
    
    def abort(self, reason: str = "Operation cancelled"):
        """
        触发中断信号。
        
        Args:
            reason: 中断原因，用于日志和错误消息
        """
        self._reason = reason
        self._event.set()
    
    def is_aborted(self) -> bool:
        """
        检查是否已触发中断。
        
        Returns:
            bool: True 如果已中断，否则 False
        """
        return self._event.is_set()
    
    async def wait(self):
        """
        异步等待中断信号。
        
        这个方法会阻塞直到 abort() 被调用。
        """
        await self._event.wait()
    
    @property
    def reason(self) -> Optional[str]:
        """
        获取中断原因。
        
        Returns:
            Optional[str]: 中断原因，如果未中断则为 None
        """
        return self._reason
    
    def reset(self):
        """重置中断信号，允许重用。"""
        self._event.clear()
        self._reason = None


__all__ = ["AbortSignal"]
