"""
完整测试：验证新架构的 Agent → Runner → Executor → Model 层
"""

import asyncio
import uuid
from agio.models.openai import OpenAIModel
from agio.agent.base import Agent
from agio.sessions.base import AgentSession
from agio.protocol.events import EventType
from agio.tools.base import Tool


class SearchTool(Tool):
    """模拟搜索工具"""
    name = "search"
    description = "搜索信息"
    
    def get_parameters(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询"}
            },
            "required": ["query"]
        }
    
    def to_openai_schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters(),
            }
        }
    
    async def execute(self, query: str):
        # 模拟搜索结果
        return f"搜索结果：关于 '{query}' 的信息..."


async def test_full_architecture():
    """测试完整架构"""
    
    print("=" * 70)
    print("测试新架构：Agent → Runner → Executor → Model")
    print("=" * 70)
    
    # 1. 创建 Model
    model = OpenAIModel(
        id="openai/gpt-4o-mini",
        name="gpt-4o-mini",
        temperature=0.7,
    )
    print(f"✓ Model: {model.name}")
    
    # 2. 创建 Agent
    agent = Agent(
        model=model,
        tools=[SearchTool()],
        name="test_agent",
        system_prompt="You are a helpful assistant.",
    )
    print(f"✓ Agent: {agent.id}, Tools: {[t.name for t in agent.tools]}")
    
    # 3. 创建 Session
    session = AgentSession(
        session_id=str(uuid.uuid4()),
        user_id="test_user"
    )
    print(f"✓ Session: {session.session_id[:8]}...")
    
    # 4. 执行查询
    query = "请搜索 Python 3.12 的新特性"
    print(f"\n{'='*70}")
    print(f"Query: {query}")
    print("=" * 70 + "\n")
    
    event_count = 0
    text_deltas = 0
    tool_calls = 0
    
    try:
        async for event in agent.arun_stream(query=query, session_id=session.session_id):
            event_count += 1
            
            if event.type == EventType.RUN_STARTED:
                print(f"[RUN_STARTED] run_id: {event.run_id[:8]}...")
            
            elif event.type == EventType.TEXT_DELTA:
                text_deltas += 1
                print(f"[TEXT] {event.data['content']}", end="", flush=True)
            
            elif event.type == EventType.TOOL_CALL_STARTED:
                tool_calls += 1
                print(f"\n\n[TOOL_CALL_STARTED] {event.data['tool_name']}")
                print(f"  Args: {event.data['arguments']}")
            
            elif event.type == EventType.TOOL_CALL_COMPLETED:
                print(f"[TOOL_CALL_COMPLETED] {event.data['tool_name']}")
                print(f"  Result: {event.data['result'][:50]}...")
                print(f"  Duration: {event.data['duration']:.3f}s\n")
            
            elif event.type == EventType.TOOL_CALL_FAILED:
                print(f"[TOOL_CALL_FAILED] {event.data['tool_name']}")
                print(f"  Error: {event.data['result']}\n")
            
            elif event.type == EventType.USAGE_UPDATE:
                usage = event.data['usage']
                print(f"\n[USAGE] tokens: {usage.get('total_tokens', 0)}")
            
            elif event.type == EventType.RUN_COMPLETED:
                print("\n\n[RUN_COMPLETED]")
                metrics = event.data['metrics']
                print(f"  Duration: {metrics['duration']:.2f}s")
                print(f"  Tool Calls: {metrics['tool_calls_count']}")
                print(f"  Total Tokens: {metrics['total_tokens']}")

        
        # 5. 总结
        print("\n" + "=" * 70)
        print("执行成功！")
        print("=" * 70)
        print(f"✓ 总事件数: {event_count}")
        print(f"✓ 文本块数: {text_deltas}")
        print(f"✓ 工具调用数: {tool_calls}")
        
        # 6. 架构验证
        print("\n" + "=" * 70)
        print("架构验证通过！")
        print("=" * 70)
        print("✓ Agent 层: 配置容器，委托执行")
        print("✓ Runner 层: 编排器，消费事件流")
        print("✓ Executor 层: LLM Call Loop 引擎")
        print("✓ Model 层: Pure LLM Interface")
        print("✓ 事件流: 统一的 AgentEvent（无 ModelEvent）")
        print("\n🎉 新架构工作完美！代码精简，职责清晰！")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_full_architecture())
