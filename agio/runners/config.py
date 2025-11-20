from pydantic import BaseModel, Field
from typing import Optional


class AgentRunConfig(BaseModel):
    """
    Agent 运行时配置。
    统一管理所有可配置参数。
    """
    
    # Loop 配置
    max_steps: int = Field(default=10, description="最大推理步数")
    
    # Context 配置
    max_history_messages: int = Field(default=10, description="最大历史消息数")
    max_rag_docs: int = Field(default=3, description="RAG 检索文档数")
    max_memories: int = Field(default=5, description="语义记忆检索数")
    
    # Memory 配置
    enable_memory_update: bool = Field(default=True, description="是否更新短期记忆")
    memory_update_async: bool = Field(default=True, description="是否异步更新记忆")
    
    # Timeout 配置
    tool_timeout: Optional[float] = Field(default=None, description="工具执行超时（秒）")
    step_timeout: Optional[float] = Field(default=None, description="单步执行超时（秒）")
    run_timeout: Optional[float] = Field(default=None, description="整体运行超时（秒）")
    
    # 并发配置
    max_parallel_tools: int = Field(default=10, description="最大并行工具数")
    
    # 调试配置
    debug_mode: bool = Field(default=False, description="调试模式")
    verbose_logging: bool = Field(default=False, description="详细日志")
    
    class Config:
        frozen = False  # 允许运行时修改
