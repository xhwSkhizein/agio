import asyncio
import json
from agio.agent import Agent
from agio.models import Deepseek
from agio.tools import FunctionTool
from agio.protocol.events import EventType

def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"The weather in {city} is sunny"

def calculate(a: int, b: int, op: str) -> int:
    """Perform basic calculation (add, sub, mul)."""
    if op == "add":
        return a + b
    elif op == "sub":
        return a - b
    elif op == "mul":
        return a * b
    return 0

async def main():
    print("=== Agio Event Stream Demo ===\n")
    
    model = Deepseek(temperature=0.0)
    agent = Agent(
        model=model,
        tools=[
            FunctionTool(get_weather),
            FunctionTool(calculate)
        ],
        name="event_demo_agent"
    )

    query = "What's the weather in Beijing? And what is 15 * 12?"
    print(f"Query: {query}\n")
    print("-" * 60)
    
    # 使用新的事件流 API
    async for event in agent.arun_stream(query):
        print(f"\n[{event.type.value.upper()}]")
        print(f"  Timestamp: {event.timestamp.strftime('%H:%M:%S.%f')[:-3]}")
        print(f"  Run ID: {event.run_id}")
        
        if event.type == EventType.RUN_STARTED:
            print(f"  Query: {event.data.get('query')}")
        
        elif event.type == EventType.TEXT_DELTA:
            content = event.data.get('content', '')
            print(f"  Content: {repr(content)}")
            print(f"  Step: {event.data.get('step')}")
        
        elif event.type == EventType.TOOL_CALL_STARTED:
            print(f"  Tool: {event.data.get('tool_name')}")
            print(f"  Arguments: {json.dumps(event.data.get('arguments'), ensure_ascii=False)}")
        
        elif event.type == EventType.TOOL_CALL_COMPLETED:
            print(f"  Tool: {event.data.get('tool_name')}")
            print(f"  Result: {event.data.get('result')}")
            print(f"  Duration: {event.data.get('duration'):.3f}s")
        
        elif event.type == EventType.USAGE_UPDATE:
            print(f"  Tokens: {event.data.get('total_tokens')} "
                  f"(prompt: {event.data.get('prompt_tokens')}, "
                  f"completion: {event.data.get('completion_tokens')})")
        
        elif event.type == EventType.RUN_COMPLETED:
            print(f"  Response: {event.data.get('response')[:100]}...")
            metrics = event.data.get('metrics', {})
            print(f"  Metrics:")
            print(f"    - Duration: {metrics.get('duration', 0):.2f}s")
            print(f"    - Steps: {metrics.get('steps_count', 0)}")
            print(f"    - Tool Calls: {metrics.get('tool_calls_count', 0)}")
            print(f"    - Total Tokens: {metrics.get('total_tokens', 0)}")
            print(f"    - Response Latency: {metrics.get('response_latency', 0):.0f}ms")
        
        elif event.type == EventType.ERROR:
            print(f"  Error: {event.data.get('error')}")
            print(f"  Type: {event.data.get('error_type')}")
    
    print("\n" + "-" * 60)
    print("\n✅ Event stream completed!")

if __name__ == "__main__":
    asyncio.run(main())
