from enum import Enum
from datetime import datetime
from uuid import uuid4
from typing import Any
from pydantic import BaseModel, Field, ConfigDict
from .common import GenerationReference
from .messages import Message, AssistantMessage
from .tools import ToolResult
from .metrics import AgentRunMetrics, LLMCallMetrics

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
    model_config = ConfigDict(protected_namespaces=())
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
    model_config = ConfigDict(protected_namespaces=())
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

    async def list_steps(self) -> list[AgentRunStep]:
        return self.steps
        
    async def get_metrics(self) -> AgentRunMetrics: # renamed to avoid conflict with field name
        return self.metrics
        
    async def get_summary(self) -> AgentRunSummary | None: # renamed to avoid conflict with field name
        return self.summary
