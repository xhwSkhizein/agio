# Step-Based Architecture Quick Reference

## Core Concepts

### Step = Native LLM Message + Metadata

```python
Step(
    # Identity
    id="step_123",
    session_id="session_456",
    run_id="run_789",
    sequence=1,
    
    # LLM Message (native format)
    role=MessageRole.USER,
    content="Hello",
    tool_calls=None,
    tool_call_id=None,
    name=None,
    
    # Metadata
    metrics=StepMetrics(...),
    created_at=datetime.now()
)
```

### Zero-Conversion Context Building

```python
# Old way (complex)
events = await repo.get_events(run_id)
messages = convert_events_to_messages(events)  # Complex logic!

# New way (simple)
steps = await repo.get_steps(session_id)
messages = [step.to_message_dict() for step in steps]  # Zero conversion!
```

## Common Operations

### 1. Run Agent with Steps

```python
from agio.runners.step_runner import StepRunner

runner = StepRunner(agent, hooks, repository=repo)

async for event in runner.run_stream(session, "Hello"):
    if event.type == StepEventType.STEP_DELTA:
        print(event.delta.content, end="")
```

### 2. Get Steps for a Session

```python
# All steps
steps = await repo.get_steps(session_id)

# Steps in range
steps = await repo.get_steps(session_id, start_seq=5, end_seq=10)

# Last step
last = await repo.get_last_step(session_id)
```

### 3. Build Context

```python
from agio.runners.step_context import build_context_from_steps

messages = await build_context_from_steps(
    session_id,
    repo,
    system_prompt="You are helpful"
)

# Ready to send to LLM!
response = await llm.chat(messages)
```

### 4. Retry from Sequence

```python
from agio.execution.retry import retry_from_sequence

# Delete steps >= sequence and regenerate
async for event in retry_from_sequence(session_id, 5, repo, runner):
    print(event)
```

### 5. Fork Session

```python
from agio.execution.fork import fork_session

# Create new session with steps up to sequence N
new_session_id = await fork_session(session_id, 5, repo)

# Continue in new session
async for event in runner.run_stream(new_session, "Continue here"):
    print(event)
```

### 6. Get Context Summary

```python
from agio.runners.step_context import get_context_summary

summary = await get_context_summary(session_id, repo)
# {
#   "total_steps": 10,
#   "user_steps": 5,
#   "assistant_steps": 4,
#   "tool_steps": 1,
#   "sequence_range": {"min": 1, "max": 10}
# }
```

## Event Types

### StepEvent

```python
# Delta (streaming)
StepEvent(
    type=StepEventType.STEP_DELTA,
    step_id="step_123",
    run_id="run_456",
    delta=StepDelta(content="Hello")
)

# Completed (final state)
StepEvent(
    type=StepEventType.STEP_COMPLETED,
    step_id="step_123",
    run_id="run_456",
    snapshot=Step(...)  # Complete Step
)

# Run events
StepEvent(type=StepEventType.RUN_STARTED, ...)
StepEvent(type=StepEventType.RUN_COMPLETED, ...)
```

## Repository Operations

```python
# Save
await repo.save_step(step)
await repo.save_steps_batch([step1, step2, step3])

# Get
steps = await repo.get_steps(session_id)
step = await repo.get_last_step(session_id)
count = await repo.get_step_count(session_id)

# Delete (for retry)
deleted = await repo.delete_steps(session_id, start_seq=5)
```

## API Endpoints

```bash
# List steps
GET /sessions/{session_id}/steps?start_seq=5&end_seq=10

# Get specific step
GET /sessions/{session_id}/steps/{sequence}

# Fork session
POST /sessions/{session_id}/fork
{"sequence": 5}

# Delete steps (retry)
DELETE /sessions/{session_id}/steps?start_seq=5

# Preview context
GET /sessions/{session_id}/context
```

## Step Roles

```python
MessageRole.USER       # User input
MessageRole.ASSISTANT  # LLM response (may have tool_calls)
MessageRole.TOOL       # Tool execution result
MessageRole.SYSTEM     # System prompt (usually not stored)
```

## Helper Methods

```python
step.is_user_step()      # True if role == USER
step.is_assistant_step() # True if role == ASSISTANT
step.is_tool_step()      # True if role == TOOL
step.has_tool_calls()    # True if assistant step with tool_calls
step.to_message_dict()   # Convert to LLM message format
```

## Metrics

```python
step.metrics = StepMetrics(
    # Timing
    duration_ms=150.5,
    first_token_latency_ms=25.3,
    
    # Tokens (for assistant)
    input_tokens=100,
    output_tokens=50,
    total_tokens=150,
    
    # Model
    model_name="gpt-4",
    provider="openai",
    
    # Tool execution (for tool steps)
    tool_exec_time_ms=500.0
)
```

## Testing

```python
# Unit tests
pytest tests/test_step_basics.py -v

# Integration tests
pytest tests/test_step_integration.py -v

# Demo
python examples/step_based_demo.py
```

## Common Patterns

### Pattern 1: Multi-turn Conversation

```python
runner = StepRunner(agent, hooks, repository=repo)

# Turn 1
async for event in runner.run_stream(session, "Hello"):
    pass

# Turn 2 (context auto-loaded!)
async for event in runner.run_stream(session, "Tell me more"):
    pass

# All steps are saved and context is built automatically
```

### Pattern 2: Regenerate Last Response

```python
# Get last assistant step
steps = await repo.get_steps(session_id)
last_assistant = next(s for s in reversed(steps) if s.is_assistant_step())

# Delete it
await repo.delete_steps(session_id, start_seq=last_assistant.sequence)

# Regenerate
last_step = await repo.get_last_step(session_id)
async for event in runner.resume_from_user_step(session_id, last_step):
    print(event)
```

### Pattern 3: Branch Conversation

```python
# Fork at sequence 5
new_session_id = await fork_session(session_id, 5, repo)

# Continue in both sessions independently
async for event in runner.run_stream(original_session, "Path A"):
    pass

async for event in runner.run_stream(new_session, "Path B"):
    pass
```

## Key Benefits

✅ **Zero Conversion** - Steps = Messages, no transformation needed
✅ **Unified Streaming** - Same structure for history and real-time
✅ **Retry** - Delete and regenerate from any point
✅ **Fork** - Branch conversations for experimentation
✅ **Metrics** - Track performance per Step
✅ **Simplicity** - One data model instead of three

## Migration Checklist

- [ ] Add Steps router to FastAPI app
- [ ] Create `/chat/stream/v2` endpoint with StepRunner
- [ ] Test with real LLM
- [ ] Update frontend to handle StepEvents
- [ ] Add retry/fork UI buttons
- [ ] Monitor performance
- [ ] Gradually roll out to users
- [ ] Deprecate old endpoints

## Resources

- **Demo**: `examples/step_based_demo.py`
- **Integration Guide**: `docs/STEP_INTEGRATION_GUIDE.md`
- **Tests**: `tests/test_step_*.py`
- **Walkthrough**: `.gemini/antigravity/brain/.../walkthrough.md`
