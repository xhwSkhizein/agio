from agio.memory.base import ChatHistoryManager, SemanticMemoryManager, Memory
from agio.domain.messages import Message
from agio.domain.memory import AgentMemoriedContent, MemoryCategory
from typing import List

class SimpleChatHistory(ChatHistoryManager):
    def __init__(self):
        # Dict[session_id, List[Message]]
        self._storage = {}

    async def add_messages(self, session_id: str, messages: List[Message]):
        if session_id not in self._storage:
            self._storage[session_id] = []
        self._storage[session_id].extend(messages)

    async def get_recent_history(self, session_id: str, limit: int = 10, max_tokens: int | None = None) -> List[Message]:
        # TODO: Implement max_tokens logic
        if session_id not in self._storage:
            return []
        return self._storage[session_id][-limit:]

    async def clear_history(self, session_id: str):
        if session_id in self._storage:
            del self._storage[session_id]

class SimpleSemanticMemory(SemanticMemoryManager):
    def __init__(self):
        self._memories: List[AgentMemoriedContent] = []

    async def remember(self, user_id: str, memory: AgentMemoriedContent):
        # In simple memory, we ignore user_id partitioning for now or just store it
        self._memories.append(memory)

    async def recall(self, user_id: str, query: str, limit: int = 5, categories: List[MemoryCategory] | None = None) -> List[AgentMemoriedContent]:
        # Simple keyword matching
        results = []
        for mem in self._memories:
            if categories and mem.category not in categories:
                continue
            if query.lower() in mem.content.lower():
                results.append(mem)
            if len(results) >= limit:
                break
        return results

class SimpleMemory(Memory):
    def __init__(self):
        self.history = SimpleChatHistory()
        self.semantic = SimpleSemanticMemory()

