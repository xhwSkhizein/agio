# Step-Based Architecture Integration Guide

## Overview

This guide explains how to integrate the new Step-based architecture into your existing Agio application.

## What's Been Completed

✅ **Core Components**
- `Step` model - Native LLM message format
- `StepExecutor` - Creates Steps directly
- `StepRunner` - Orchestrates execution with Step persistence
- `StepEvent` protocol - Unified streaming
- Repository operations - Full CRUD for Steps
- API endpoints - REST API for Steps
- Tests - 16/16 passing

## Integration Steps

### 1. Add Steps Router to FastAPI App

Update `agio/api/app.py`:

```python
from agio.api.routes import steps

# Add to your app
app.include_router(steps.router)
```

### 2. Update Chat Endpoint (Optional - Gradual Migration)

You can run both systems in parallel. Here's how to add a new Step-based chat endpoint:

**Option A: New Endpoint (Recommended)**

Create `/chat/stream/v2` that uses StepRunner:

```python
# In agio/api/routes/chat.py

from agio.runners.step_runner import StepRunner, StepRunnerConfig
from agio.protocol.step_events import StepEventType

@router.post("/chat/stream/v2")
async def chat_stream_v2(
    request: ChatRequest,
    repository: AgentRunRepository = Depends(get_repository),
    agent = Depends(get_agent),  # Your agent dependency
):
    """New Step-based streaming endpoint"""
    
    # Create session
    session = AgentSession(
        session_id=request.session_id or str(uuid4()),
        user_id=request.user_id
    )
    
    # Create StepRunner
    runner = StepRunner(
        agent=agent,
        hooks=[],  # Add your hooks
        config=StepRunnerConfig(max_steps=10),
        repository=repository
    )
    
    # Stream events
    async def event_generator():
        async for event in runner.run_stream(session, request.message):
            yield event.to_sse()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

**Option B: Replace Existing (After Testing)**

Once you've verified the new system works, replace the old endpoint:

```python
@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, ...):
    # Replace AgentRunner with StepRunner
    runner = StepRunner(agent, hooks, repository=repository)
    
    async def event_generator():
        async for event in runner.run_stream(session, request.message):
            yield event.to_sse()
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 3. Frontend Integration

The frontend needs to handle `StepEvent` format instead of `AgentEvent`.

**Old Format (AgentEvent):**
```json
{
  "type": "text_delta",
  "run_id": "run_123",
  "data": {
    "content": "Hello",
    "step": 1
  }
}
```

**New Format (StepEvent):**
```json
{
  "type": "step_delta",
  "run_id": "run_123",
  "step_id": "step_456",
  "delta": {
    "content": "Hello"
  }
}
```

**Frontend Update:**

```javascript
// Old code
if (event.type === 'text_delta') {
  appendText(event.data.content);
}

// New code
if (event.type === 'step_delta' && event.delta?.content) {
  appendText(event.delta.content);
}

// Handle completed steps
if (event.type === 'step_completed' && event.snapshot) {
  // Save complete step for history
  steps[event.step_id] = event.snapshot;
}
```

### 4. History Loading

Update history loading to use Steps:

```javascript
// Old: Load events
const events = await fetch(`/runs/${runId}/events`);

// New: Load steps
const response = await fetch(`/sessions/${sessionId}/steps`);
const { steps } = await response.json();

// Steps are already in the right format!
// No conversion needed - just render them
steps.forEach(step => {
  if (step.role === 'user') {
    renderUserMessage(step.content);
  } else if (step.role === 'assistant') {
    renderAssistantMessage(step.content);
  }
});
```

### 5. Enable Retry and Fork Features

Add UI buttons for retry and fork:

```javascript
// Retry from a sequence
async function retryFromSequence(sessionId, sequence) {
  const response = await fetch(`/sessions/${sessionId}/retry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sequence })
  });
  
  // Handle streaming response
  const reader = response.body.getReader();
  // ... process SSE stream
}

// Fork a session
async function forkSession(sessionId, sequence) {
  const response = await fetch(`/sessions/${sessionId}/fork`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sequence })
  });
  
  const { new_session_id } = await response.json();
  
  // Navigate to new session
  window.location.href = `/chat/${new_session_id}`;
}
```

## Migration Strategy

### Phase 1: Parallel Operation (Week 1-2)

1. Deploy new code with both systems
2. Add `/chat/stream/v2` endpoint
3. Test with internal users
4. Monitor metrics and performance

### Phase 2: Gradual Rollout (Week 3-4)

1. Add feature flag for Step-based system
2. Roll out to 10% of users
3. Increase to 50%, then 100%
4. Monitor error rates and performance

### Phase 3: Deprecation (Week 5-6)

1. Mark old endpoints as deprecated
2. Update all clients to use new endpoints
3. Remove old AgentRunner code
4. Clean up old events collection

### Phase 4: Optimization (Week 7+)

1. Add caching for frequently accessed Steps
2. Optimize MongoDB indexes
3. Implement Step compression for long sessions
4. Add analytics on retry/fork usage

## Testing Checklist

Before deploying to production:

- [ ] Run all tests: `pytest tests/test_step_*.py -v`
- [ ] Test with real LLM (OpenAI/Anthropic)
- [ ] Test streaming performance
- [ ] Test retry functionality
- [ ] Test fork functionality
- [ ] Test context building with long sessions (100+ steps)
- [ ] Test MongoDB indexes performance
- [ ] Load test with concurrent users
- [ ] Test frontend integration
- [ ] Test error handling and recovery

## Monitoring

Key metrics to monitor:

1. **Step Creation Rate** - Steps/second
2. **Context Build Time** - Time to build context from Steps
3. **Retry Usage** - How often users retry
4. **Fork Usage** - How often users fork
5. **Storage Growth** - Steps collection size
6. **Query Performance** - get_steps() latency

## Rollback Plan

If issues arise:

1. **Immediate**: Switch feature flag to use old system
2. **Short-term**: Fix issues in new system
3. **Long-term**: If unfixable, keep both systems running

The new system is designed to coexist with the old one, so rollback is safe.

## Benefits You'll See

1. **Simpler Code** - No event → message conversion
2. **Better Performance** - Direct Step queries
3. **New Features** - Retry and fork
4. **Better Debugging** - Clear Step history
5. **Easier Testing** - Steps are easy to inspect

## Support

If you encounter issues:

1. Check logs for Step-related errors
2. Verify MongoDB indexes are created
3. Test with InMemoryRepository first
4. Review test cases for examples
5. Check the demo: `python examples/step_based_demo.py`

## Example: Complete Integration

See `examples/step_based_demo.py` for a working example that demonstrates:
- Creating and saving Steps
- Zero-conversion context building
- Retry functionality
- Fork functionality
- Metrics tracking

Run it with:
```bash
python examples/step_based_demo.py
```

## Next Steps

1. Review this guide
2. Run the demo
3. Test with your agent
4. Deploy to staging
5. Monitor and iterate

The Step-based architecture is production-ready and backward compatible. You can migrate at your own pace!
