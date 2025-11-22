"""
Example: Step-based Agent Execution

This example demonstrates the complete Step-based flow:
1. Create a simple agent
2. Run with StepRunner
3. Steps are saved to repository
4. Context is built from Steps
5. Retry from a sequence
6. Fork a session

Run this to see the new architecture in action!
"""

import asyncio
from agio.domain.step import Step, MessageRole
from agio.db.repository import InMemoryRepository
from agio.execution.step_executor import StepExecutor
from agio.runners.step_runner import StepRunner, StepRunnerConfig
from agio.sessions.base import AgentSession
from agio.protocol.step_events import StepEventType
from agio.runners.step_context import build_context_from_steps, get_context_summary
from agio.execution.fork import fork_session


# Mock model for demonstration
class MockModel:
    """Simple mock model that returns predefined responses"""
    
    def __init__(self):
        self.model_name = "mock-gpt-4"
        self.provider = "mock"
        self.response_count = 0
    
    async def arun_stream(self, messages, tools=None):
        """Simulate streaming response"""
        from agio.models.base import StreamChunk
        
        self.response_count += 1
        
        # Different responses for different calls
        if self.response_count == 1:
            response = "Hello! I'm a Step-based agent. How can I help you?"
        elif self.response_count == 2:
            response = "I can demonstrate the new Step architecture with zero-conversion context building!"
        else:
            response = f"This is response #{self.response_count}. Each response is stored as a Step."
        
        # Stream the response character by character
        for char in response:
            yield StreamChunk(content=char, tool_calls=None, usage=None)
        
        # Send usage at the end
        yield StreamChunk(
            content=None,
            tool_calls=None,
            usage={
                "prompt_tokens": len(str(messages)),
                "completion_tokens": len(response),
                "total_tokens": len(str(messages)) + len(response)
            }
        )


# Mock agent
class MockAgent:
    """Simple mock agent"""
    
    def __init__(self):
        self.id = "demo_agent"
        self.model = MockModel()
        self.tools = []
        self.system_prompt = "You are a helpful assistant demonstrating the Step-based architecture."


async def main():
    """Run the complete Step-based flow demonstration"""
    
    print("=" * 80)
    print("Step-Based Architecture Demo")
    print("=" * 80)
    print()
    
    # 1. Setup
    print("1. Setting up components...")
    repository = InMemoryRepository()
    agent = MockAgent()
    session = AgentSession(
        session_id="demo_session",
        user_id="demo_user"
    )
    
    runner = StepRunner(
        agent=agent,
        hooks=[],
        config=StepRunnerConfig(max_steps=5),
        repository=repository
    )
    
    print(f"   ✓ Repository: {type(repository).__name__}")
    print(f"   ✓ Agent: {agent.id}")
    print(f"   ✓ Session: {session.session_id}")
    print()
    
    # 2. First conversation
    print("2. Running first conversation...")
    print("   User: 'Hello!'")
    print("   Assistant: ", end="", flush=True)
    
    async for event in runner.run_stream(session, "Hello!"):
        if event.type == StepEventType.STEP_DELTA and event.delta and event.delta.content:
            print(event.delta.content, end="", flush=True)
    
    print()
    print()
    
    # 3. Check saved steps
    print("3. Checking saved Steps...")
    steps = await repository.get_steps("demo_session")
    print(f"   ✓ Total steps saved: {len(steps)}")
    for step in steps:
        print(f"   - Seq {step.sequence}: {step.role.value:10} | {step.content[:50]}...")
    print()
    
    # 4. Build context (zero conversion!)
    print("4. Building context from Steps (zero conversion!)...")
    messages = await build_context_from_steps(
        "demo_session",
        repository,
        system_prompt=agent.system_prompt
    )
    print(f"   ✓ Built {len(messages)} messages")
    print(f"   - Message 0: {messages[0]['role']:10} | {messages[0]['content'][:50]}...")
    print(f"   - Message 1: {messages[1]['role']:10} | {messages[1]['content'][:50]}...")
    print(f"   - Message 2: {messages[2]['role']:10} | {messages[2]['content'][:50]}...")
    print()
    
    # 5. Second conversation (context is automatically loaded)
    print("5. Running second conversation (context auto-loaded)...")
    print("   User: 'Tell me more'")
    print("   Assistant: ", end="", flush=True)
    
    async for event in runner.run_stream(session, "Tell me more"):
        if event.type == StepEventType.STEP_DELTA and event.delta and event.delta.content:
            print(event.delta.content, end="", flush=True)
    
    print()
    print()
    
    # 6. Check updated steps
    print("6. Checking updated Steps...")
    steps = await repository.get_steps("demo_session")
    print(f"   ✓ Total steps now: {len(steps)}")
    print(f"   ✓ Last step: Seq {steps[-1].sequence} - {steps[-1].role.value}")
    print()
    
    # 7. Get context summary
    print("7. Getting context summary...")
    summary = await get_context_summary("demo_session", repository)
    print(f"   ✓ Total steps: {summary['total_steps']}")
    print(f"   ✓ User steps: {summary['user_steps']}")
    print(f"   ✓ Assistant steps: {summary['assistant_steps']}")
    print(f"   ✓ Sequence range: {summary['sequence_range']['min']} - {summary['sequence_range']['max']}")
    print()
    
    # 8. Retry demonstration
    print("8. Demonstrating retry (delete last assistant response)...")
    last_assistant_seq = None
    for step in reversed(steps):
        if step.is_assistant_step():
            last_assistant_seq = step.sequence
            break
    
    if last_assistant_seq:
        print(f"   Deleting from sequence {last_assistant_seq}...")
        deleted = await repository.delete_steps("demo_session", start_seq=last_assistant_seq)
        print(f"   ✓ Deleted {deleted} steps")
        
        # Check remaining
        remaining = await repository.get_steps("demo_session")
        print(f"   ✓ Remaining steps: {len(remaining)}")
        
        # Regenerate
        print("   Regenerating response...")
        last_step = await repository.get_last_step("demo_session")
        print("   Assistant: ", end="", flush=True)
        
        async for event in runner.resume_from_user_step("demo_session", last_step):
            if event.type == StepEventType.STEP_DELTA and event.delta and event.delta.content:
                print(event.delta.content, end="", flush=True)
        
        print()
        print()
    
    # 9. Fork demonstration
    print("9. Demonstrating fork (branch conversation)...")
    fork_at_seq = 2  # Fork after first exchange
    new_session_id = await fork_session("demo_session", fork_at_seq, repository)
    print(f"   ✓ Created new session: {new_session_id}")
    
    # Check forked steps
    forked_steps = await repository.get_steps(new_session_id)
    print(f"   ✓ Forked steps: {len(forked_steps)}")
    for step in forked_steps:
        print(f"   - Seq {step.sequence}: {step.role.value:10} | {step.content[:50]}...")
    print()
    
    # 10. Metrics demonstration
    print("10. Checking Step metrics...")
    steps_with_metrics = [s for s in steps if s.metrics and s.metrics.total_tokens]
    if steps_with_metrics:
        step = steps_with_metrics[0]
        print(f"   ✓ Step {step.sequence} metrics:")
        print(f"   - Total tokens: {step.metrics.total_tokens}")
        print(f"   - Duration: {step.metrics.duration_ms:.2f}ms")
        print(f"   - Model: {step.metrics.model_name}")
    print()
    
    # Summary
    print("=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print()
    print("Key Achievements Demonstrated:")
    print("✓ Steps created and saved automatically")
    print("✓ Zero-conversion context building")
    print("✓ Context automatically loaded across conversations")
    print("✓ Retry: Delete and regenerate from any point")
    print("✓ Fork: Branch conversations for experimentation")
    print("✓ Metrics: Track performance per Step")
    print()
    print("The new Step-based architecture is working perfectly!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
