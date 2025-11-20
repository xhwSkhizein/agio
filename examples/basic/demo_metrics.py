"""
Demo: Metrics 和可观测性

展示 Phase 5 的新功能：
1. Metrics 快照事件
2. 错误分类和恢复
3. 取消支持
"""
import asyncio
from agio.agent.base import Agent
from agio.models.openai import OpenAIModel
from agio.tools.local import tool
from agio.protocol.events import EventType


@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气"""
    return f"{city} 的天气是晴天"


@tool
def calculate(a: int, b: int, op: str = "add") -> int:
    """执行数学计算"""
    if op == "add":
        return a + b
    elif op == "mul":
        return a * b
    return 0


async def demo_metrics():
    """演示 metrics 收集"""
    print("=" * 60)
    print("Demo: Metrics 快照")
    print("=" * 60)
    
    agent = Agent(
        name="MetricsAgent",
        model=OpenAIModel(),
        tools=[get_weather, calculate],
        instruction="你是一个助手，可以查询天气和计算数学。"
    )
    
    query = "北京的天气怎么样？15 * 12 等于多少？"
    print(f"\nQuery: {query}\n")
    
    metrics_snapshots = []
    
    async for event in agent.arun_stream(query):
        if event.type == EventType.TEXT_DELTA:
            print(event.data.get("content", ""), end="", flush=True)
        
        elif event.type == EventType.METRICS_SNAPSHOT:
            metrics = event.data
            metrics_snapshots.append(metrics)
            print(f"\n\n📊 Metrics Snapshot (Step {metrics.get('current_step')}):")
            print(f"   - Total Tokens: {metrics.get('total_tokens')}")
            print(f"   - Prompt Tokens: {metrics.get('total_prompt_tokens')}")
            print(f"   - Completion Tokens: {metrics.get('total_completion_tokens')}")
            print(f"   - Tool Calls: {metrics.get('tool_calls_count')}")
            print(f"   - Step Duration: {metrics.get('step_duration')}s")
            print()
        
        elif event.type == EventType.TOOL_CALL_STARTED:
            tool_name = event.data.get("tool_name")
            print(f"\n🔧 Tool Call: {tool_name}")
        
        elif event.type == EventType.RUN_COMPLETED:
            print(f"\n\n✅ Run Completed")
            print(f"   Status: {event.data.get('status')}")
            print(f"   Duration: {event.data.get('duration', 0):.2f}s")
    
    # 汇总 metrics
    if metrics_snapshots:
        print("\n" + "=" * 60)
        print("Metrics Summary:")
        print("=" * 60)
        final_metrics = metrics_snapshots[-1]
        print(f"Total Steps: {final_metrics.get('current_step')}")
        print(f"Total Tokens: {final_metrics.get('total_tokens')}")
        print(f"Total Tool Calls: {sum(m.get('tool_calls_count', 0) for m in metrics_snapshots)}")
        print(f"Average Step Duration: {sum(m.get('step_duration', 0) for m in metrics_snapshots) / len(metrics_snapshots):.3f}s")


async def demo_error_handling():
    """演示错误处理"""
    print("\n\n" + "=" * 60)
    print("Demo: 错误处理（模拟）")
    print("=" * 60)
    print("\n注意：实际错误处理需要真实的 API 错误场景")
    print("当前实现支持：")
    print("  - 致命错误：AuthenticationError, RateLimitError 等")
    print("  - 非致命错误：TimeoutError, ConnectionError 等")
    print("  - 自动分类和恢复机制")


async def demo_cancellation():
    """演示取消支持"""
    print("\n\n" + "=" * 60)
    print("Demo: 取消支持")
    print("=" * 60)
    
    agent = Agent(
        name="CancellableAgent",
        model=OpenAIModel(),
        tools=[get_weather],
        instruction="你是一个助手。"
    )
    
    async def run_with_timeout():
        try:
            task = asyncio.create_task(
                agent.arun("请告诉我 10 个城市的天气")
            )
            # 模拟 1 秒后取消
            await asyncio.sleep(1)
            task.cancel()
            await task
        except asyncio.CancelledError:
            print("\n✅ Task cancelled successfully")
    
    print("\n模拟场景：启动任务后 1 秒取消")
    print("注意：实际演示需要长时间运行的任务\n")
    # await run_with_timeout()
    print("取消支持已实现，可通过 task.cancel() 触发")


async def main():
    """主函数"""
    await demo_metrics()
    await demo_error_handling()
    await demo_cancellation()
    
    print("\n\n" + "=" * 60)
    print("Phase 5 功能演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
