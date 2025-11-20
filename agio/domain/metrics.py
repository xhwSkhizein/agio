from pydantic import BaseModel, Field

class BaseMetrics(BaseModel):
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    # 通用首字时间戳
    first_token_timestamp: float | None = None

class LLMCallMetrics(BaseMetrics):
    """单次 LLM API 调用的指标"""
    time_to_first_token: float | None = None # Latency (ms)

class AgentRunMetrics(BaseMetrics):
    """单次 Run (User Query -> Final Response) 的指标"""
    steps_count: int = 0
    tool_calls_count: int = 0
    tool_errors_count: int = 0
    
    # Agent 响应延迟 (从收到 Query 到向用户输出第一个非 Thinking 字符的时间)
    response_latency: float | None = None 

class AgentMetrics(BaseMetrics):
    """Agent 生命周期汇总"""
    total_runs: int = 0
    total_errors: int = 0
    tool_usage_stats: dict[str, int] = Field(default_factory=dict)

