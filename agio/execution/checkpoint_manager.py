"""
Checkpoint Manager for creating and managing checkpoints.
"""

from typing import Optional
from datetime import datetime
from .checkpoint import ExecutionCheckpoint, CheckpointMetadata
from .checkpoint_policy import CheckpointPolicy, CheckpointStrategy
from .serializer import MessageSerializer


class CheckpointManager:
    """
    Checkpoint Manager.
    
    Responsibilities:
    1. Create checkpoints
    2. Store and load checkpoints
    3. List and search checkpoints
    4. Manage checkpoint lifecycle
    """
    
    def __init__(
        self,
        repository,
        policy: CheckpointPolicy | None = None
    ):
        self.repository = repository
        self.policy = policy or CheckpointPolicy(CheckpointStrategy.MANUAL)
    
    async def create_checkpoint(
        self,
        run_id: str,
        step_num: int,
        messages: list,
        metrics: dict,
        agent_config: dict,
        status: str = "running",
        description: str | None = None,
        tags: list[str] | None = None
    ) -> ExecutionCheckpoint:
        """
        Create a checkpoint.
        
        Args:
            run_id: Run ID
            step_num: Step number
            messages: Message history
            metrics: Metrics snapshot
            agent_config: Agent configuration
            status: Run status
            description: Description
            tags: Tags
        
        Returns:
            ExecutionCheckpoint
        """
        from agio.domain.run import RunStatus
        
        # Serialize messages
        serialized_messages = MessageSerializer.serialize_messages(messages)
        
        checkpoint = ExecutionCheckpoint(
            run_id=run_id,
            step_num=step_num,
            status=RunStatus(status) if isinstance(status, str) else status,
            messages=serialized_messages,
            metrics=metrics,
            agent_config=agent_config,
            description=description,
            tags=tags or []
        )
        
        # Persist
        await self.repository.save_checkpoint(checkpoint)
        
        return checkpoint
    
    async def get_checkpoint(self, checkpoint_id: str) -> Optional[ExecutionCheckpoint]:
        """Get checkpoint by ID."""
        return await self.repository.get_checkpoint(checkpoint_id)
    
    async def list_checkpoints(
        self,
        run_id: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
        offset: int = 0
    ) -> list[CheckpointMetadata]:
        """
        List checkpoints.
        
        Args:
            run_id: Filter by Run ID
            tags: Filter by tags
            limit: Limit count
            offset: Offset
        
        Returns:
            Checkpoint metadata list
        """
        checkpoints = await self.repository.list_checkpoints(
            run_id=run_id,
            tags=tags,
            limit=limit,
            offset=offset
        )
        
        # Convert to metadata
        metadata_list = []
        for ckpt in checkpoints:
            metadata = CheckpointMetadata(
                id=ckpt.id,
                run_id=ckpt.run_id,
                step_num=ckpt.step_num,
                created_at=ckpt.created_at,
                status=ckpt.status,
                description=ckpt.description,
                tags=ckpt.tags,
                message_count=len(ckpt.messages),
                total_tokens=ckpt.metrics.get("total_tokens", 0),
                has_modifications=ckpt.user_modifications is not None
            )
            metadata_list.append(metadata)
        
        return metadata_list
    
    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete checkpoint."""
        return await self.repository.delete_checkpoint(checkpoint_id)
    
    async def should_create_auto_checkpoint(self, context: dict) -> bool:
        """Determine if auto-checkpoint should be created."""
        return self.policy.should_create_checkpoint(context)
