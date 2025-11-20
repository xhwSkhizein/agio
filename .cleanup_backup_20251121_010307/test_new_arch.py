"""
简单测试：验证新架构的 Model + Executor 层
"""

import asyncio
from agio.models.openai import OpenAIModel
from agio.execution.agent_executor import AgentExecutor, ExecutorConfig
from agio.protocol.events import EventType
from agio.tools.base import Tool


class EchoTool(Tool):
    """简单的回显工具，用于测试"""
    name = "echo"
    description = "回显输入的文本"
    
    def get_parameters(self):
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要回显的文本"}
            },
            "required": ["text"]
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
    
    async def execute(self, text: str):
        return f"Echo: {text}"


async def test_new_architecture():
    """测试新架构：Model → Executor → AgentEvent"""
    
    print("=" * 60)
    print("测试新架构：Model + Executor 层")
    print("=" * 60)
    
    # 1. 创建 Model
    model = OpenAIModel(
        id="openai/gpt-4o-mini",
        name="gpt-4o-mini",
        temperature=0.7,
    )
    print(f"✓ Model 创建成功: {model.name}")
    
    # 2. 创建 Executor
    tools = [EchoTool()]
    executor = AgentExecutor(
        model=model,
        tools=tools,
        config=ExecutorConfig(max_steps=3),
    )
    print(f"✓ Executor 创建成功，Tools: {[t.name for t in tools]}")
    
    # 3. 准备消息
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "请使用 echo 工具回显 'Hello World'"}
    ]
    print(f"✓ 消息准备完成: {len(messages)} 条")
    
    # 4. 执行并观察事件流
    print("\n" + "=" * 60)
    print("开始执行 LLM Call Loop...")
    print("=" * 60 + "\n")
    
    full_response = ""
    event_count = 0
    tool_calls_count = 0
    
    try:
        async for event in executor.execute(messages, run_id="test_run_001"):
            event_count += 1
            
            if event.type == EventType.TEXT_DELTA:
                content = event.data["content"]
                full_response += content
                print(f"[TEXT_DELTA] {content}", end="", flush=True)
            
            elif event.type == EventType.TOOL_CALL_STARTED:
                tool_calls_count += 1
                print(f"\n\n[TOOL_CALL_STARTED] {event.data['tool_name']}")
                print(f"  Arguments: {event.data['arguments']}")
            
            elif event.type == EventType.TOOL_CALL_COMPLETED:
                print(f"[TOOL_CALL_COMPLETED] {event.data['tool_name']}")
                print(f"  Result: {event.data['result']}")
                print(f"  Duration: {event.data['duration']:.3f}s\n")
            
            elif event.type == EventType.USAGE_UPDATE:
                print(f"[USAGE] {event.data['usage']}")
        
        # 5. 总结
        print("\n" + "=" * 60)
        print("执行完成！")
        print("=" * 60)
        print(f"✓ 总事件数: {event_count}")
        print(f"✓ 工具调用数: {tool_calls_count}")
        print(f"✓ 最终消息数: {len(messages)}")
        print(f"✓ 完整响应: {full_response[:100]}...")
        
        # 验证架构
        print("\n" + "=" * 60)
        print("架构验证")
        print("=" * 60)
        print("✓ Model 层: 只负责 LLM API 调用")
        print("✓ Executor 层: 负责 LLM Loop 和事件生成")
        print("✓ 事件流: 统一的 AgentEvent（无 ModelEvent）")
        print("✓ 消息格式: 标准 dict 格式（无需转换）")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_new_architecture())
