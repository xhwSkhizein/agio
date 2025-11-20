from agio.domain.run import AgentRun
from agio.domain.metrics import AgentRunMetrics  # Fixed: use AgentRunMetrics
from agio.protocol.events import AgentEvent, EventType


class RunStateTracker:
    """
    追踪 Run 状态和 Metrics。
    
    根据 AgentEvent 流更新 Run 和 Step 状态。
    
    Examples:
        >>> tracker = RunStateTracker(run)
        >>> async for event in executor.execute(messages, run_id):
        ...     tracker.update(event)
        >>> metrics = tracker.build_metrics()
    """
    
    def __init__(self, run: AgentRun):
        """
        初始化状态追踪器。
        
        Args:
            run: AgentRun 实例
        """
        self.run = run
        self._full_response = ""
        self._total_tokens = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._tool_calls_count = 0
        self._tool_errors_count = 0
        self._current_step = 0
    
    def update(self, event: AgentEvent):
        """
        根据事件更新状态。
        
        Args:
            event: AgentEvent 实例
        """
        if event.type == EventType.TEXT_DELTA:
            self._full_response += event.data["content"]
            self._current_step = max(self._current_step, event.data.get("step", 0))
        
        elif event.type == EventType.USAGE_UPDATE:
            usage = event.data["usage"]
            self._total_tokens += usage.get("total_tokens", 0)
            self._prompt_tokens += usage.get("prompt_tokens", 0)
            self._completion_tokens += usage.get("completion_tokens", 0)
        
        elif event.type == EventType.TOOL_CALL_COMPLETED:
            self._tool_calls_count += 1
        
        elif event.type == EventType.TOOL_CALL_FAILED:
            self._tool_calls_count += 1
            self._tool_errors_count += 1
    
    def get_full_response(self) -> str:
        """获取完整响应文本"""
        return self._full_response
    
    def build_metrics(self) -> AgentRunMetrics:  # Fixed: return AgentRunMetrics
        """
        构建 Metrics。
        
        Returns:
            AgentRunMetrics 实例 (not AgentMetrics)
        """
        return AgentRunMetrics(
            total_tokens=self._total_tokens,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            steps_count=self._current_step,
            tool_calls_count=self._tool_calls_count,
            tool_errors_count=self._tool_errors_count,
        )
    
    @property
    def current_step(self) -> int:
        """当前步数"""
        return self._current_step
