import asyncio
from agio.agent import Agent
from agio.models import Deepseek
from agio.tools import FunctionTool
from agio.db.repository import InMemoryRepository
from agio.protocol.events import EventType

def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"The weather in {city} is sunny"

async def main():
    print("=== Agio History & Replay Demo ===\n")
    
    # 创建 Repository
    repository = InMemoryRepository()
    
    # 创建 Agent（配置 repository）
    model = Deepseek(temperature=0.0)
    agent = Agent(
        model=model,
        tools=[FunctionTool(get_weather)],
        repository=repository,
        name="history_demo_agent"
    )

    # 第一次执行
    query = "What's the weather in Beijing?"
    print(f"Query: {query}\n")
    print("-" * 60)
    
    run_id = None
    async for event in agent.arun_stream(query):
        if event.type == EventType.RUN_STARTED:
            run_id = event.run_id
            print(f"[RUN STARTED] ID: {run_id}")
        elif event.type == EventType.TEXT_DELTA:
            print(event.data.get('content', ''), end='', flush=True)
        elif event.type == EventType.RUN_COMPLETED:
            print(f"\n\n[RUN COMPLETED]")
            print(f"Duration: {event.data['metrics']['duration']:.2f}s")
    
    print("\n" + "-" * 60)
    
    # 查看存储的事件数量
    event_count = await repository.get_event_count(run_id)
    print(f"\n✅ Stored {event_count} events for run {run_id}")
    
    # 历史回放
    print("\n" + "=" * 60)
    print("REPLAYING HISTORY...")
    print("=" * 60 + "\n")
    
    replay_count = 0
    async for event in agent.get_run_history(run_id):
        replay_count += 1
        if event.type == EventType.TEXT_DELTA:
            print(event.data.get('content', ''), end='', flush=True)
        elif event.type == EventType.TOOL_CALL_STARTED:
            print(f"\n[TOOL: {event.data['tool_name']}]", end='')
        elif event.type == EventType.RUN_COMPLETED:
            print(f"\n\n[REPLAY COMPLETED]")
    
    print(f"\n✅ Replayed {replay_count} events")
    
    # 列出所有 Runs
    print("\n" + "=" * 60)
    print("ALL RUNS:")
    print("=" * 60)
    
    runs = await agent.list_runs(limit=10)
    for i, run in enumerate(runs, 1):
        print(f"\n{i}. Run ID: {run.id}")
        print(f"   Query: {run.input_query}")
        print(f"   Status: {run.status}")
        print(f"   Duration: {run.metrics.duration:.2f}s")
        print(f"   Created: {run.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main())
