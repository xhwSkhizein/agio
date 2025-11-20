"""
Example 3: Streaming Events

This example demonstrates how to use the event stream API for more control
over the agent's output.
"""
import asyncio
from agio.agent.base import Agent
from agio.models.openai import OpenAIModel
from agio.tools.local import tool
from agio.protocol.events import EventType


@tool
def search_database(query: str) -> str:
    """Search the database for information."""
    # Simulated database search
    return f"Found 3 results for '{query}': Result 1, Result 2, Result 3"


async def main():
    """Use event streaming for detailed control."""
    
    agent = Agent(
        model=OpenAIModel(),
        tools=[search_database],
        name="event_agent"
    )
    
    query = "Search for information about Python async programming"
    print(f"User: {query}\n")
    
    # Use event stream for fine-grained control
    async for event in agent.arun_stream(query):
        match event.type:
            case EventType.RUN_STARTED:
                print(f"🚀 Run started: {event.run_id}")
                print("-" * 60)
            
            case EventType.TEXT_DELTA:
                # Stream text as it arrives
                print(event.data.get("content", ""), end="", flush=True)
            
            case EventType.TOOL_CALL_STARTED:
                tool_name = event.data.get("tool_name")
                args = event.data.get("arguments", {})
                print(f"\n\n🔧 Calling tool: {tool_name}")
                print(f"   Arguments: {args}")
            
            case EventType.TOOL_CALL_COMPLETED:
                tool_name = event.data.get("tool_name")
                duration = event.data.get("duration", 0)
                print(f"✅ Tool completed: {tool_name} ({duration:.2f}s)\n")
            
            case EventType.USAGE_UPDATE:
                tokens = event.data.get("total_tokens", 0)
                print(f"\n📊 Tokens used: {tokens}")
            
            case EventType.METRICS_SNAPSHOT:
                metrics = event.data
                print(f"\n📈 Metrics Snapshot:")
                print(f"   - Total Tokens: {metrics.get('total_tokens')}")
                print(f"   - Step: {metrics.get('current_step')}")
                print(f"   - Duration: {metrics.get('step_duration')}s")
            
            case EventType.RUN_COMPLETED:
                print("\n" + "-" * 60)
                print(f"✅ Run completed")
                print(f"   Status: {event.data.get('status')}")
                print(f"   Duration: {event.data.get('metrics', {}).get('duration', 0):.2f}s")
                print(f"   Steps: {event.data.get('metrics', {}).get('steps_count', 0)}")
            
            case EventType.ERROR:
                error = event.data.get("error")
                print(f"\n❌ Error: {error}")


if __name__ == "__main__":
    asyncio.run(main())
