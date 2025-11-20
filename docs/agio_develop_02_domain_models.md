# Agio 开发文档 02: 核心领域模型 (Core Domain Models)

本模块定义了框架中所有流动的数据结构。
**变更日志**:
- 增加 `first_token_timestamp` 到 Metrics。
- 增强 `AgentRunStep` 以支持 100% 请求重放 (Replayability)。
- 为 Summary 和 Memory 增加溯源信息 (`reference`)。

## 1. 基础消息模型 (`domain/messages.py`)

```python
from typing import Literal, Any
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime

class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    # 额外元数据，用于存储 token 统计等
    meta: dict[str, Any] = Field(default_factory=dict)

class UserMessage(Message):
    role: Literal["user"] = "user"

class SystemMessage(Message):
    role: Literal["system"] = "system"

class AssistantMessage(Message):
    role: Literal["assistant"] = "assistant"
    tool_calls: list[dict[str, Any]] | None = None

class ToolMessage(Message):
    role: Literal["tool"] = "tool"
    tool_call_id: str
```

## 2. 工具执行结果 (`domain/tools.py`)

```python
class ToolResult(BaseModel):
    tool_name: str
    tool_call_id: str
    input_args: dict[str, Any]
    content: str  # 给 LLM 看的结果
    output: Any   # 原始执行结果
    error: str | None = None
    start_time: float
    end_time: float
    duration: float
    is_success: bool = True
```

## 3. 运行指标 (`domain/metrics.py`)

增加 `first_token_timestamp`，明确区分 Model 层和 Agent 层。

```python
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
```

## 4. 溯源元数据 (`domain/common.py`)

用于 Summary 和 Memory 追溯其生成的源头。

```python
class GenerationReference(BaseModel):
    """指向生成该内容的 LLM 调用记录"""
    run_id: str  # 所属的 Run ID (可能是后台任务的 Run)
    step_id: str # 具体执行生成的 Step ID
    model_id: str
    # 关键参数快照，便于快速查看
    context_window_size: int | None = None 
    citations: list[str] = Field(default_factory=list)
```

## 5. 运行过程记录 (`domain/run.py`)

核心变更：`raw_request` 包含完整配置快照。

```python
from enum import Enum
from .common import GenerationReference

class RunStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AgentRunSummary(BaseModel):
    content: str
    created_at: datetime = Field(default_factory=datetime.now)
    # 溯源：指向生成这个 Summary 的那次 LLM 调用
    reference: GenerationReference | None = None 

class RequestSnapshot(BaseModel):
    """完全复现一次 LLM 调用所需的所有参数"""
    url: str
    model: str
    model_settings: dict[str, Any]  # temperature, top_p, max_tokens, etc.
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    # 注意：敏感信息如 api_key 应脱敏 (sk-***)
    auth_context: dict[str, str] | None = None 

class ResponseSnapshot(BaseModel):
    """LLM 原始响应"""
    content: str | None
    tool_calls: list[dict] | None
    raw_api_response: dict[str, Any] # 供应商返回的原始 JSON

class AgentRunStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    agent_id: str
    step_num: int
    
    # 100% Replayability Request Log
    request_snapshot: RequestSnapshot
    # Raw Response Log
    response_snapshot: ResponseSnapshot | None = None
    
    # 结构化视图 (用于内部逻辑处理)
    messages_context: list[Message]
    model_response: AssistantMessage | None = None
    tool_results: list[ToolResult] = Field(default_factory=list)
    
    metrics: LLMCallMetrics = Field(default_factory=LLMCallMetrics)
    error: str | None = None
    
    def raw_request(self) -> dict:
        return self.request_snapshot.model_dump()

    def raw_response(self) -> dict:
        return self.response_snapshot.model_dump() if self.response_snapshot else {}

class AgentRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    session_id: str | None = None
    user_id: str | None = None
    
    input_query: str
    status: RunStatus = RunStatus.STARTING
    
    steps: list[AgentRunStep] = Field(default_factory=list)
    
    response_content: str | None = None
    metrics: AgentRunMetrics = Field(default_factory=AgentRunMetrics)
    summary: AgentRunSummary | None = None
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
```

## 6. 记忆模型 (`domain/memory.py`)

核心变更：增加 `category` 和 `reference`。

```python
from enum import Enum
from .common import GenerationReference

class MemoryCategory(str, Enum):
    USER_PREFERENCE = "user_preference" # 用户偏好 (喜欢 Python, 讨厌啰嗦)
    FACT = "fact"                       # 事实信息 (用户住在北京)
    SUMMARY = "summary"                 # 对话片段总结
    CONCEPT = "concept"                 # 抽象概念
    OTHER = "other"

class AgentMemoriedContent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    category: MemoryCategory = MemoryCategory.OTHER
    tags: list[str] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.now)
    source_run_id: str | None = None # 原始对话的 Run ID
    
    # 溯源：指向提取这条记忆的那次 LLM 调用 (Extraction Process)
    reference: GenerationReference | None = None
```
