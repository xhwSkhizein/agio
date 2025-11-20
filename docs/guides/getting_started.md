# 快速开始指南

欢迎使用 Agio！本指南将帮助你在 5 分钟内创建第一个 AI Agent。

---

## 📦 安装

### 使用 pip

```bash
pip install agio
```

### 从源码安装

```bash
git clone https://github.com/yourusername/agio.git
cd agio
pip install -e .
```

### 依赖要求

- Python 3.9+
- OpenAI API Key (或其他支持的 LLM provider)

---

## 🚀 第一个 Agent（30秒）

创建 `hello.py`:

```python
import asyncio
from agio.agent import Agent
from agio.models import OpenAIModel

async def main():
    # 1. 创建 Agent
    agent = Agent(
        model=OpenAIModel(name="gpt-4"),
        name="my_first_agent"
    )
    
    # 2. 运行
    async for chunk in agent.arun("Hello! Who are you?"):
        print(chunk, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```bash
export OPENAI_API_KEY="sk-..."
python hello.py
```

---

## 🔧 添加工具

Agents 的真正威力在于使用工具。让我们添加一些：

```python
import asyncio
from agio.agent import Agent
from agio.models import OpenAIModel
from agio.tools import FunctionTool

# 定义工具函数
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    # 这里可以调用真实的天气 API
    return f"The weather in {city} is sunny, 25°C"

def calculate(expression: str) -> str:
    """Calculate a mathematical expression."""
    try:
        result = eval(expression)  # 注意：生产环境应使用安全的计算库
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error: {e}"

async def main():
    agent = Agent(
        model=OpenAIModel(name="gpt-4"),
        tools=[
            FunctionTool(get_weather),
            FunctionTool(calculate)
        ],
        name="tool_agent"
    )
    
    query = "What's the weather in Beijing? Also, what is 123 * 456?"
    
    async for chunk in agent.arun(query):
        print(chunk, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🎯 使用事件流 API

获得更精细的控制和更好的用户体验：

```python
import asyncio
from agio.agent import Agent
from agio.models import OpenAIModel
from agio.tools import FunctionTool
from agio.protocol.events import EventType

def search_web(query: str) -> str:
    """Search the web for information."""
    return f"Search results for: {query}"

async def main():
    agent = Agent(
        model=OpenAIModel(name="gpt-4"),
        tools=[FunctionTool(search_web)]
    )
    
    print("🤖 Agent: ", end="", flush=True)
    
    async for event in agent.arun_stream("Search for Python async programming"):
        match event.type:
            case EventType.TEXT_DELTA:
                # 显示 AI 返回的文本
                print(event.data["content"], end="", flush=True)
            
            case EventType.TOOL_CALL_STARTED:
                # 显示工具调用
                tool_name = event.data["tool_name"]
                print(f"\n\n🔧 Calling tool: {tool_name}...", flush=True)
            
            case EventType.TOOL_CALL_COMPLETED:
                # 工具完成
                print("✅ Tool completed", flush=True)
                print("\n🤖 Agent: ", end="", flush=True)
            
            case EventType.USAGE_UPDATE:
                # 显示 token 使用
                usage = event.data
                tokens = usage.get("total_tokens", 0)
                print(f"\n\n📊 Tokens used: {tokens}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
```

输出示例：

```
🤖 Agent: Let me search for information about Python async programming.

🔧 Calling tool: search_web...
✅ Tool completed

🤖 Agent: Based on the search results, Python async programming...

📊 Tokens used: 245
```

---

## 💾 添加记忆

让 Agent 记住对话历史：

```python
import asyncio
from agio.agent import Agent
from agio.models import OpenAIModel
from agio.memory import SimpleMemory

async def main():
    agent = Agent(
        model=OpenAIModel(name="gpt-4"),
        memory=SimpleMemory(),  # 添加记忆
        name="memory_agent"
    )
    
    # 第一轮对话
    print("User: My name is Alice\n")
    async for chunk in agent.arun("My name is Alice", session_id="session_1"):
        print(chunk, end="", flush=True)
    
    print("\n\n---\n")
    
    # 第二轮对话 - Agent 会记住名字
    print("User: What's my name?\n")
    async for chunk in agent.arun("What's my name?", session_id="session_1"):
        print(chunk, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📚 添加知识库（RAG）

让 Agent 访问你的文档：

```python
import asyncio
from agio.agent import Agent
from agio.models import OpenAIModel
from agio.knowledge import VectorKnowledge

async def main():
    # 创建知识库
    knowledge = VectorKnowledge(
        collection_name="my_docs",
        embedding_model="text-embedding-3-small"
    )
    
    # 添加文档（只需要做一次）
    await knowledge.add_documents([
        "Agio is a Python agent framework.",
        "Agio supports async operations natively.",
        "Agio has built-in observability features."
    ])
    
    # 创建 Agent
    agent = Agent(
        model=OpenAIModel(name="gpt-4"),
        knowledge=knowledge,
        name="rag_agent"
    )
    
    # 查询 - Agent 会从知识库中检索相关信息
    async for chunk in agent.arun("What is Agio?"):
        print(chunk, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 💿 持久化和历史回放

保存所有对话，稍后回放：

```python
import asyncio
from agio.agent import Agent
from agio.models import OpenAIModel
from agio.db.repository import InMemoryRepository
from agio.protocol.events import EventType

async def main():
    # 创建 Repository
    repository = InMemoryRepository()
    
    # 创建 Agent
    agent = Agent(
        model=OpenAIModel(name="gpt-4"),
        repository=repository,  # 启用持久化
        name="persistent_agent"
    )
    
    # 执行并自动保存
    run_id = None
    async for event in agent.arun_stream("Hello!"):
        if event.type == EventType.RUN_STARTED:
            run_id = event.data["run_id"]
            print(f"Run ID: {run_id}\n")
        elif event.type == EventType.TEXT_DELTA:
            print(event.data["content"], end="", flush=True)
    
    print("\n\n--- Replay ---\n")
    
    # 回放历史
    async for event in agent.get_run_history(run_id):
        if event.type == EventType.TEXT_DELTA:
            print(event.data["content"], end="", flush=True)
    
    # 列出所有 runs
    print("\n\n--- All Runs ---\n")
    runs = await agent.list_runs(limit=10)
    for run in runs:
        print(f"- {run.id}: {run.input_query[:50]}... ({run.status})")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🎨 Web 集成示例

### FastAPI + SSE

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from agio.agent import Agent
from agio.models import OpenAIModel

app = FastAPI()
agent = Agent(model=OpenAIModel(name="gpt-4"))

@app.post("/chat")
async def chat(query: str):
    async def event_stream():
        async for event in agent.arun_stream(query):
            # 发送 Server-Sent Events
            yield f"data: {event.model_dump_json()}\n\n"
    
    return StreamingResponse(
        event_stream(), 
        media_type="text/event-stream"
    )
```

### Gradio UI

```python
import gradio as gr
from agio.agent import Agent
from agio.models import OpenAIModel

agent = Agent(model=OpenAIModel(name="gpt-4"))

async def chat(message, history):
    response = ""
    async for chunk in agent.arun(message):
        response += chunk
        yield response

demo = gr.ChatInterface(chat)
demo.launch()
```

---

## 🔍 调试和可观测性

使用 Hooks 实现自定义逻辑：

```python
import asyncio
from agio.agent import Agent
from agio.models import OpenAIModel
from agio.agent.hooks.base import AgentHook

class DebugHook(AgentHook):
    async def on_run_start(self, run):
        print(f"🚀 Run started: {run.id}")
    
    async def on_tool_start(self, run, step, tool_calls):
        for tc in tool_calls:
            print(f"🔧 Calling: {tc['name']}")
    
    async def on_run_end(self, run):
        print(f"✅ Run completed in {run.metrics.duration:.2f}s")
        print(f"   Tokens: {run.metrics.total_tokens}")
        print(f"   Tools: {run.metrics.tool_calls_count}")

async def main():
    agent = Agent(
        model=OpenAIModel(name="gpt-4"),
        hooks=[DebugHook()],
        name="debug_agent"
    )
    
    async for chunk in agent.arun("Hello!"):
        print(chunk, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📝 配置和环境变量

### 使用 .env 文件

创建 `.env`:

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1

# Deepseek
DEEPSEEK_API_KEY=sk-...

# 数据库
MONGODB_URI=mongodb://localhost:27017
```

### 使用配置文件

```python
from agio.agent import Agent
from agio.models import OpenAIModel
from agio.runners.config import AgentRunConfig

# 自定义配置
config = AgentRunConfig(
    max_steps=20,                    # 最大执行步数
    max_context_messages=50,         # 最大上下文消息数
    max_rag_docs=10,                 # 最大 RAG 文档数
    enable_memory_update=True,       # 启用记忆更新
)

agent = Agent(
    model=OpenAIModel(name="gpt-4", temperature=0.7),
    config=config
)
```

---

## 🎓 下一步

- 📖 阅读 [架构文档](../docs/architecture/overview.md)
- 🔧 查看 [完整示例](../examples/)
- 🛠️ 学习 [自定义扩展](../docs/guides/custom_extensions.md)
- 🤝 参与 [贡献](../CONTRIBUTING.md)

---

## 💡 常见问题

### Q: Agio 与 LangChain 有什么区别？

A: Agio 专注于：
- 🚀 **异步原生** - 全链路异步，天然支持流式
- 📊 **事件驱动** - 15种事件类型，完整的可观测性
- 🏗️ **架构清晰** - 三层设计，职责分离
- 💿 **历史回放** - 完整的事件存储和回放

### Q: 支持哪些 LLM？

A: 当前支持：
- ✅ OpenAI (GPT-4, GPT-3.5)
- ✅ Deepseek
- ⏳ Anthropic Claude (计划中)
- ⏳ Google Gemini (计划中)
- ✅ 任何兼容 OpenAI API 的模型

### Q: 如何部署到生产环境？

A: 参考我们的 [生产部署指南](../docs/guides/deployment.md)

---

**需要帮助？** [提交 Issue](https://github.com/yourusername/agio/issues) 或加入我们的 [Discord](https://discord.gg/agio)
