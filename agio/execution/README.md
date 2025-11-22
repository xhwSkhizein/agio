# Agio Execution Control System

## Overview

The execution control system provides powerful checkpoint, resume, and fork capabilities for Agent runs. This enables:

- 💾 **Checkpoints** - Save complete execution state at any point
- ▶️ **Resume** - Continue execution from any checkpoint
- 🔀 **Fork** - Create execution branches for A/B testing
- ⏸️ **Pause/Resume** - Control execution flow
- 🔙 **Time Travel** - Debug by jumping to any execution point

## Quick Start

### 1. Create Checkpoints

```python
from agio.execution import CheckpointManager, CheckpointPolicy, CheckpointStrategy
from agio.db.repository import InMemoryRepository

# Create checkpoint manager
repository = InMemoryRepository()
checkpoint_manager = CheckpointManager(
    repository,
    policy=CheckpointPolicy(CheckpointStrategy.ON_TOOL_CALL)
)

# Manual checkpoint creation
checkpoint = await checkpoint_manager.create_checkpoint(
    run_id="run_123",
    step_num=2,
    messages=messages,
    metrics={"total_tokens": 100},
    agent_config={},
    description="Before tool call"
)
```

### 2. Resume from Checkpoint

```python
from agio.execution import ResumeRunner

resume_runner = ResumeRunner(agent, hooks=[], repository=repository)

# Load checkpoint
checkpoint = await checkpoint_manager.get_checkpoint(checkpoint_id)

# Resume execution
async for event in resume_runner.resume_from_checkpoint(checkpoint):
    print(event)
```

### 3. Fork Execution

```python
from agio.execution import ForkManager

fork_manager = ForkManager(checkpoint_manager, resume_runner)

# Fork with modifications
new_run_id, event_stream = await fork_manager.fork_from_checkpoint(
    checkpoint_id=checkpoint.id,
    modifications={"modified_query": "New query"},
    description="Testing different approach"
)

# Execute forked branch
async for event in event_stream:
    print(event)
```

### 4. Pause/Resume Execution

```python
from agio.execution import get_execution_controller

controller = get_execution_controller()

# Pause
controller.pause_run(run_id)

# Resume later
controller.resume_run(run_id)

# Cancel
controller.cancel_run(run_id)
```

## Features

### Checkpoint Strategies

```python
from agio.execution import CheckpointPolicy, CheckpointStrategy

# Manual only
policy = CheckpointPolicy(CheckpointStrategy.MANUAL)

# Auto-create after every step
policy = CheckpointPolicy(CheckpointStrategy.EVERY_STEP)

# Create before tool calls
policy = CheckpointPolicy(CheckpointStrategy.ON_TOOL_CALL)

# Create on errors
policy = CheckpointPolicy(CheckpointStrategy.ON_ERROR)

# Custom strategy
policy = CheckpointPolicy(CheckpointStrategy.CUSTOM)
policy.set_custom_predicate(lambda ctx: ctx.get("step_num", 0) % 2 == 0)
```

### Checkpoint Management

```python
# List checkpoints
checkpoints = await checkpoint_manager.list_checkpoints(
    run_id="run_123",
    tags=["important"],
    limit=20
)

# Get specific checkpoint
checkpoint = await checkpoint_manager.get_checkpoint(checkpoint_id)

# Delete checkpoint
await checkpoint_manager.delete_checkpoint(checkpoint_id)
```

### Fork Comparison

```python
# Compare two forks
comparison = await fork_manager.compare_forks(run_id_1, run_id_2)

print(comparison["differences"]["response_diff"])
print(comparison["differences"]["token_diff"])
```

## Use Cases

### 1. Debugging Failed Runs

```python
# Find the last successful checkpoint before failure
checkpoints = await checkpoint_manager.list_checkpoints(run_id=failed_run_id)
last_good_checkpoint = checkpoints[-1]

# Resume from there
async for event in resume_runner.resume_from_checkpoint(last_good_checkpoint):
    print(event)
```

### 2. A/B Testing Prompts

```python
# Create base checkpoint
base_checkpoint = await checkpoint_manager.create_checkpoint(...)

# Fork A: Prompt A
run_a_id, stream_a = await fork_manager.fork_from_checkpoint(
    checkpoint_id=base_checkpoint.id,
    modifications={"system_prompt": "Prompt A"}
)

# Fork B: Prompt B
run_b_id, stream_b = await fork_manager.fork_from_checkpoint(
    checkpoint_id=base_checkpoint.id,
    modifications={"system_prompt": "Prompt B"}
)

# Compare results
comparison = await fork_manager.compare_forks(run_a_id, run_b_id)
```

### 3. Long-Running Tasks

```python
# Start execution
controller = get_execution_controller()
controller.start_run(run_id)

# Pause after some time
await asyncio.sleep(300)
controller.pause_run(run_id)

# Create checkpoint
checkpoint = await checkpoint_manager.create_checkpoint(...)

# Resume later
controller.resume_run(run_id)
```

## API Reference

### ExecutionCheckpoint

```python
class ExecutionCheckpoint(BaseModel):
    id: str
    run_id: str
    step_num: int
    status: RunStatus
    messages: list[dict]
    metrics: dict
    agent_config: dict
    user_modifications: dict | None
    tags: list[str]
    description: str | None
```

### CheckpointManager

```python
class CheckpointManager:
    async def create_checkpoint(...) -> ExecutionCheckpoint
    async def get_checkpoint(checkpoint_id: str) -> ExecutionCheckpoint | None
    async def list_checkpoints(...) -> list[CheckpointMetadata]
    async def delete_checkpoint(checkpoint_id: str) -> bool
```

### ExecutionController

```python
class ExecutionController:
    def start_run(run_id: str) -> None
    def pause_run(run_id: str) -> bool
    def resume_run(run_id: str) -> bool
    def cancel_run(run_id: str) -> bool
    async def check_pause(run_id: str) -> None
    def is_cancelled(run_id: str) -> bool
```

## Testing

Run the execution control tests:

```bash
pytest tests/test_execution.py -v
```

## Next Steps

- Check out `agio/execution/DESIGN.md` for detailed design documentation
- Explore the FastAPI backend for API endpoints
- Learn about the React frontend for visual time-travel debugging
