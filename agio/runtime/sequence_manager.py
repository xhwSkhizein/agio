"""
Sequence Manager for Agent execution.

Manages sequence allocation for all Steps within a Session.
"""

from agio.providers.storage.base import SessionStore


class SequenceManager:
    """Session-level sequence allocation service.
    
    Manages sequence allocation for all Steps within a Session:
    1. Normal allocation: atomic allocation via SessionStore.allocate_sequence
    2. Pre-allocation handling: ParallelWorkflow's seq_start mechanism
    
    This is a Session-level resource that should be shared across all
    nested Agent/Workflow executions within the same Session.
    """
    
    def __init__(self, session_store: SessionStore):
        """Initialize SequenceManager.
        
        Args:
            session_store: SessionStore instance for atomic sequence allocation
        """
        self.session_store = session_store
    
    async def allocate(self, session_id: str, context=None) -> int:
        """Allocate next sequence number.
        
        Args:
            session_id: Session ID
            context: ExecutionContext (optional). If provided and contains
                    seq_start in metadata, uses the pre-allocated sequence
                    for parallel workflow branches.
        
        Returns:
            Next sequence number
        """
        # Handle parallel workflow pre-allocated sequences
        # ParallelWorkflow pre-allocates sequence ranges before execution,
        # passing them via context.metadata
        if context and "seq_start" in context.metadata:
            seq_start = context.metadata.pop("seq_start")
            return seq_start
        
        # Use SessionStore's atomic allocation
        return await self.session_store.allocate_sequence(session_id)
