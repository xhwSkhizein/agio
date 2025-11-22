"""
Fork logic for creating session branches from a specific sequence point.

This module implements the fork functionality as specified in the refactor design:
1. Create new session ID
2. Copy steps up to sequence N
3. Return new session ID for continued execution
"""

from uuid import uuid4
from typing import List
from agio.domain.step import Step
from agio.db.repository import AgentRunRepository
from agio.utils.logging import get_logger

logger = get_logger(__name__)


async def fork_session(
    original_session_id: str,
    sequence: int,
    repository: AgentRunRepository
) -> str:
    """
    Fork a session at a specific sequence.
    
    This creates a new session with a copy of all steps up to and including
    the specified sequence. The new session can then be continued independently.
    
    Args:
        original_session_id: Original session ID to fork from
        sequence: Sequence number to fork at (inclusive)
        repository: Repository for step operations
    
    Returns:
        str: New session ID
    
    Example:
        # Original session has steps 1-10
        # Fork at sequence 5
        new_session_id = await fork_session(original_session_id, 5, repo)
        # New session now has steps 1-5
        # Can continue execution in new session independently
    
    Raises:
        ValueError: If no steps found or sequence is invalid
    """
    logger.info(
        "fork_started",
        original_session_id=original_session_id,
        sequence=sequence
    )
    
    # 1. Get steps up to sequence
    steps = await repository.get_steps(
        original_session_id,
        end_seq=sequence
    )
    
    if not steps:
        raise ValueError(
            f"No steps found in session {original_session_id} up to sequence {sequence}"
        )
    
    # 2. Create new session ID
    new_session_id = str(uuid4())
    
    logger.info(
        "fork_creating_session",
        original_session_id=original_session_id,
        new_session_id=new_session_id,
        steps_to_copy=len(steps)
    )
    
    # 3. Copy steps to new session
    new_steps: List[Step] = []
    for step in steps:
        # Create a copy with new session_id
        # Keep the same sequence numbers for consistency
        new_step = step.model_copy(update={"session_id": new_session_id})
        new_steps.append(new_step)
    
    # 4. Batch save to new session
    await repository.save_steps_batch(new_steps)
    
    logger.info(
        "fork_completed",
        original_session_id=original_session_id,
        new_session_id=new_session_id,
        copied_steps=len(new_steps),
        last_sequence=steps[-1].sequence if steps else None
    )
    
    return new_session_id


async def fork_from_step_id(
    step_id: str,
    repository: AgentRunRepository
) -> str:
    """
    Fork a session from a specific step ID.
    
    This is a convenience function that looks up the step by ID,
    finds its sequence, and forks at that point.
    
    Args:
        step_id: Step ID to fork from
        repository: Repository
    
    Returns:
        str: New session ID
    
    Raises:
        ValueError: If step not found
    """
    # This would require a get_step_by_id method in the repository
    # For now, we'll need to scan through sessions
    # In practice, you'd want to add an index on step.id
    
    # TODO: Implement get_step_by_id in repository
    raise NotImplementedError(
        "fork_from_step_id requires get_step_by_id in repository"
    )


async def list_fork_tree(
    session_id: str,
    repository: AgentRunRepository
) -> dict:
    """
    Get the fork tree for a session.
    
    This would show all forks created from this session and their relationships.
    
    Args:
        session_id: Session ID
        repository: Repository
    
    Returns:
        dict: Fork tree structure
    
    Note:
        This requires additional metadata tracking (parent_session_id, fork_point)
        which is not in the current Step model. This is a future enhancement.
    """
    # TODO: Add fork tracking metadata to Step or separate ForkMetadata model
    raise NotImplementedError(
        "Fork tree tracking requires additional metadata"
    )


# Old checkpoint-based fork manager (DEPRECATED)
# Kept for backward compatibility

from typing import AsyncIterator
from .checkpoint import ExecutionCheckpoint
from agio.protocol.events import AgentEvent


class ForkManager:
    """
    Fork Manager (DEPRECATED - use fork_session instead).
    
    Creates new execution branches from checkpoints.
    """
    
    def __init__(self, checkpoint_manager, resume_runner):
        self.checkpoint_manager = checkpoint_manager
        self.resume_runner = resume_runner
    
    async def fork_from_checkpoint(
        self,
        checkpoint_id: str,
        modifications: dict | None = None,
        description: str | None = None
    ) -> tuple[str, AsyncIterator[AgentEvent]]:
        """
        Fork new branch from checkpoint.
        
        Args:
            checkpoint_id: Checkpoint ID
            modifications: User modifications
            description: Fork description
        
        Returns:
            (new_run_id, event_stream)
        """
        # Load checkpoint
        checkpoint = await self.checkpoint_manager.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")
        
        # Apply modifications
        if modifications:
            checkpoint.user_modifications = modifications
        
        # Generate new Run ID
        new_run_id = str(uuid4())
        
        # Create Fork checkpoint (record branch relationship)
        fork_checkpoint = await self.checkpoint_manager.create_checkpoint(
            run_id=new_run_id,
            step_num=0,
            messages=checkpoint.messages,
            metrics=checkpoint.metrics,
            agent_config=checkpoint.agent_config,
            description=description or f"Forked from {checkpoint.id}",
            tags=["fork", f"parent:{checkpoint.run_id}"]
        )
        
        # Resume execution
        event_stream = self.resume_runner.resume_from_checkpoint(
            checkpoint,
            new_run_id=new_run_id
        )
        
        return new_run_id, event_stream
    
    async def compare_forks(
        self,
        run_id_1: str,
        run_id_2: str
    ) -> dict:
        """
        Compare two fork results.
        
        Args:
            run_id_1: Run ID 1
            run_id_2: Run ID 2
        
        Returns:
            Comparison results
        """
        # Load two Runs
        run1 = await self.checkpoint_manager.repository.get_run(run_id_1)
        run2 = await self.checkpoint_manager.repository.get_run(run_id_2)
        
        if not run1 or not run2:
            raise ValueError("One or both runs not found")
        
        # Compare
        comparison = {
            "run_1": {
                "id": run1.id,
                "status": run1.status,
                "response": run1.response_content,
                "metrics": run1.metrics.model_dump() if hasattr(run1.metrics, 'model_dump') else run1.metrics
            },
            "run_2": {
                "id": run2.id,
                "status": run2.status,
                "response": run2.response_content,
                "metrics": run2.metrics.model_dump() if hasattr(run2.metrics, 'model_dump') else run2.metrics
            },
            "differences": {
                "response_diff": run1.response_content != run2.response_content,
                "token_diff": getattr(run1.metrics, 'total_tokens', 0) - getattr(run2.metrics, 'total_tokens', 0),
                "duration_diff": getattr(run1.metrics, 'duration', 0) - getattr(run2.metrics, 'duration', 0)
            }
        }
        
        return comparison
