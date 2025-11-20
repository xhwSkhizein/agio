from typing import TYPE_CHECKING
from agio.domain.messages import Message, SystemMessage, UserMessage
from agio.utils.logger import log_error, log_debug
from agio.runners.config import AgentRunConfig

if TYPE_CHECKING:
    from agio.agent.base import Agent
    from agio.sessions.base import AgentSession


class ContextBuilder:
    """
    负责构建 Agent 执行所需的完整上下文。
    包括：System Prompt + History + RAG + Semantic Memory + User Query
    """
    
    def __init__(self, agent: "Agent", config: AgentRunConfig):
        self.agent = agent
        self.config = config
    
    async def build(self, query: str, session: "AgentSession") -> list[Message]:
        """
        构建完整的消息上下文。
        
        执行顺序：
        1. System Prompt
        2. RAG Context (Knowledge)
        3. Semantic Memory
        4. Chat History
        5. User Query (可能包含增强的 RAG/Memory 信息)
        """
        messages: list[Message] = []
        
        # 1. System Prompt
        if self.agent.system_prompt:
            messages.append(SystemMessage(content=self.agent.system_prompt))
            log_debug(f"Added system prompt ({len(self.agent.system_prompt)} chars)")
        
        # 2. RAG Context
        rag_context = await self._get_rag_context(query)
        
        # 3. Semantic Memory
        memory_context = await self._get_memory_context(query, session)
        
        # 4. Enhance query with RAG and Memory
        enhanced_query = self._enhance_query(query, rag_context, memory_context)
        
        # 5. Chat History
        history = await self._get_chat_history(session)
        messages.extend(history)
        
        # 6. User Query
        messages.append(UserMessage(content=enhanced_query))
        
        log_debug(f"Context built: {len(messages)} messages")
        return messages
    
    async def _get_rag_context(self, query: str) -> str:
        """从知识库检索相关文档"""
        if not self.agent.knowledge:
            return ""
        
        try:
            docs = await self.agent.knowledge.search(query, limit=self.config.max_rag_docs)
            if docs:
                log_debug(f"Retrieved {len(docs)} documents from knowledge base")
                return "\n\nRelevant Knowledge:\n" + "\n".join([f"- {d}" for d in docs])
        except Exception as e:
            log_error(f"Knowledge search failed: {e}")
        
        return ""
    
    async def _get_memory_context(self, query: str, session: "AgentSession") -> str:
        """从语义记忆检索相关信息"""
        if not self.agent.memory or not session.user_id:
            return ""
        
        try:
            memories = await self.agent.memory.semantic.recall(
                user_id=session.user_id, 
                query=query, 
                limit=self.config.max_memories
            )
            if memories:
                log_debug(f"Retrieved {len(memories)} memories")
                return "\n\nUser Memories:\n" + "\n".join([f"- {m.content}" for m in memories])
        except Exception as e:
            log_error(f"Semantic memory recall failed: {e}")
        
        return ""
    
    def _enhance_query(self, query: str, rag_context: str, memory_context: str) -> str:
        """将 RAG 和 Memory 信息附加到查询中"""
        if not rag_context and not memory_context:
            return query
        
        enhanced = query
        if rag_context or memory_context:
            enhanced += f"\n\n<CONTEXT>"
            if rag_context:
                enhanced += f"\n{rag_context}"
            if memory_context:
                enhanced += f"\n{memory_context}"
            enhanced += "\n</CONTEXT>"
        
        return enhanced
    
    async def _get_chat_history(self, session: "AgentSession") -> list[Message]:
        """获取会话历史"""
        if not self.agent.memory:
            return []
        
        try:
            history = await self.agent.memory.history.get_recent_history(
                session_id=session.session_id, 
                limit=self.config.max_history_messages
            )
            if history:
                log_debug(f"Loaded {len(history)} history messages")
            return history
        except Exception as e:
            log_error(f"History load failed: {e}")
            return []
