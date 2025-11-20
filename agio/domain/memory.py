from enum import Enum
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field
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

