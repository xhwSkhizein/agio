"""
Resume Runner for restoring execution from checkpoints.
"""

from typing import AsyncIterator
from uuid import uuid4
from .checkpoint import ExecutionCheckpoint
from agio.protocol.events import AgentEvent
from agio.domain.run import AgentRun, RunStatus


class ResumeRunner:
    """
    Resume Runner.
    
    Restores execution from a checkpoint.
    """
    
    def __init__(self, agent, hooks, repository):
        self.agent = agent
        self.hooks = hooks
        self.repository = repository
    
    async def resume_from_checkpoint(
        self,
        checkpoint: ExecutionCheckpoint,
        new_run_id: str | None = None
    ) -> AsyncIterator[AgentEvent]:
        """
        Resume execution from checkpoint.
        
        Args:
            checkpoint: Checkpoint object
            new_run_id: New Run ID (if None, continue original Run)
        
        Yields:
            AgentEvent
        """
        from agio.runners.state_tracker import RunStateTracker
        from agio.protocol.events import create_run_started_event
        from agio.execution.agent_executor import AgentExecutor, ExecutorConfig
        import time
        
        # Determine Run ID
        run_id = new_run_id or checkpoint.run_id
        is_new_run = new_run_id is not None
        
        # Create or load Run
        if is_new_run:
            # Create new Run
            run = AgentRun(
                id=run_id,
                agent_id=self.agent.id,
                input_query=f"Resumed from checkpoint {checkpoint.id}",
                status=RunStatus.RUNNING
            )
            run.metrics.start_time = time.time()
            
            # Send Run started event
            yield create_run_started_event(
                run_id=run_id,
                query=f"Resumed from step {checkpoint.step_num}"
            )
        else:
            # Load original Run
            run = await self.repository.get_run(checkpoint.run_id)
            if not run:
                raise ValueError(f"Run {checkpoint.run_id} not found")
            
            run.status = RunStatus.RUNNING
        
        # Rebuild message context
        messages = checkpoint.messages
        
        # Apply user modifications (if any)
        if checkpoint.user_modifications:
            messages = self._apply_modifications(
                messages,
                checkpoint.user_modifications
            )
        
        # Create Executor
        executor = AgentExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=ExecutorConfig(
                max_steps=10,  # Configurable
                start_step=checkpoint.step_num + 1  # Start from next step
            )
        )
        
        # State tracker
        state = RunStateTracker(run)
        
        # Execute
        async for event in executor.execute(messages, run_id=run_id):
            state.update(event)
            yield event
        
        # Complete
        run.status = RunStatus.COMPLETED
        run.response_content = state.get_full_response()
        run.metrics.end_time = time.time()
        
        # Save
        await self.repository.save_run(run)
    
    def _apply_modifications(
        self,
        messages: list,
        modifications: dict
    ) -> list:
        """Apply user modifications."""
        
        # Modify last user message
        if "modified_query" in modifications:
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    messages[i]["content"] = modifications["modified_query"]
                    break
        
        # Modify specific messages
        if "modified_messages" in modifications:
            messages = modifications["modified_messages"]
        
        return messages
