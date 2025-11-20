# Agio 开发文档 03: 核心抽象接口 (Core Interfaces)

本模块定义 Agent、Model、Tool、Storage 等组件的抽象契约。
**变更日志**:
- 明确拆分 `Memory` 接口为 `ChatHistory` (Short-term) 和 `SemanticMemory` (Long-term)。
- 保持 Memory 与 Knowledge 的界限。

## 1. Model 抽象 (`models/base.py`)

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any
from agio.domain.messages import Message

class ModelResponse(BaseModel):
    content: str
    raw_response: Any
    usage: dict[str, int]
    first_token_timestamp: float | None = None # timestamp

class Model(ABC):
    id: str
    name: str
    
    @abstractmethod
    async def aresponse(self, messages: list[Message], tools: list[Any] | None = None, **kwargs) -> ModelResponse:
        """非流式异步响应"""
        pass

    @abstractmethod
    async def astream(self, messages: list[Message], tools: list[Any] | None = None, **kwargs) -> AsyncIterator[Any]:
        """
        流式异步响应. 
        Yields: 应该是统一的 Chunk 对象，包含 content_delta 或 tool_call_delta
        """
        pass
```

## 2. Tool 抽象 (`tools/base.py`)

(保持不变，略)

## 3. Storage 抽象 (`db/base.py`)

(保持不变，略)

## 4. Memory 体系抽象 (`memory/base.py`)

我们将 Memory 拆分为两个明确的职责接口，以避免混淆“上下文窗口”和“长期记忆”。

```python
from abc import ABC, abstractmethod
from agio.domain.messages import Message
from agio.domain.memory import AgentMemoriedContent, MemoryCategory

class ChatHistoryManager(ABC):
    """
    Short-term Memory: 管理当前会话的上下文窗口。
    职责：存储原始对话流，提供滑动窗口或 Token 截断。
    """
    @abstractmethod
    async def add_messages(self, session_id: str, messages: list[Message]):
        pass
        
    @abstractmethod
    async def get_recent_history(self, session_id: str, limit: int = 10, max_tokens: int | None = None) -> list[Message]:
        pass
        
    @abstractmethod
    async def clear_history(self, session_id: str):
        pass

class SemanticMemoryManager(ABC):
    """
    Long-term Memory: 管理基于向量的用户记忆。
    职责：存储、检索个性化事实和偏好。
    """
    @abstractmethod
    async def remember(self, user_id: str, memory: AgentMemoriedContent):
        """写入一条新记忆"""
        pass
        
    @abstractmethod
    async def recall(self, user_id: str, query: str, limit: int = 5, categories: list[MemoryCategory] | None = None) -> list[AgentMemoriedContent]:
        """基于语义检索相关记忆"""
        pass

class Memory(ABC):
    """
    聚合接口：Agent 通常持有这个聚合对象
    """
    history: ChatHistoryManager
    semantic: SemanticMemoryManager
```

## 5. Knowledge 体系抽象 (`knowledge/base.py`)

Knowledge 与 Memory (SemanticMemoryManager) 的接口可能很像（都是 Vector Search），但用途不同。
Knowledge 通常是 Read-Only (对于 Agent 运行期间而言)，且数据源是外部文档。

```python
class Knowledge(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[str]:
        """
        检索外部知识库 (RAG)
        """
        pass
```

## 6. Agent 接口概览 (`agent/base.py`)

```python
class Agent:
    def __init__(
        self,
        model: Model,
        tools: list[Tool] = [],
        memory: Memory | None = None,      # 包含 History + User Semantic Memory
        knowledge: Knowledge | None = None, # 包含 External Docs
        storage: Storage | None = None,
        # ...
    ):
        ...
```
