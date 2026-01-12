# Agio 快速开始

5 分钟快速上手 Agio Agent 框架。

---

## 安装

### 系统要求

- Python 3.11+
- ripgrep（用于 grep 工具）：
  - macOS: `brew install ripgrep`
  - Ubuntu/Debian: `sudo apt-get install ripgrep`
  - Windows: `choco install ripgrep`

### 安装 Agio

```bash
pip install agio
```

---

## 第一个 Agent

### 1. 创建最简单的 Agent

```python
import asyncio
from agio import Agent, OpenAIModel

async def main():
    # 创建 Agent
    agent = Agent(
        model=OpenAIModel(
            model_name="gpt-4o",
            api_key="your-api-key"  # 或设置环境变量 OPENAI_API_KEY
        ),
        name="my_first_agent",
        system_prompt="You are a helpful assistant.",
    )
    
    # 运行 Agent（流式输出）
    async for event in agent.run_stream("Hello! What is 2+2?"):
        if event.type == "STEP_CREATED" and event.step:
            print(f"{event.step.role}: {event.step.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

**输出**：
```
USER: Hello! What is 2+2?
ASSISTANT: Hello! 2+2 equals 4.
```

---

## 使用工具

### 2. 添加工具增强 Agent 能力

```python
import asyncio
from agio import Agent, OpenAIModel
from agio.tools import get_tool_registry

async def main():
    # 获取工具注册表
    registry = get_tool_registry()
    
    # 获取内置工具
    bash_tool = registry.get("bash")
    file_read_tool = registry.get("file_read")
    
    # 创建带工具的 Agent
    agent = Agent(
        model=OpenAIModel(model_name="gpt-4o"),
        tools=[bash_tool, file_read_tool],
        system_prompt="You are a helpful assistant with access to bash and file reading.",
        max_steps=10,
    )
    
    # 运行 Agent
    async for event in agent.run_stream("List files in current directory"):
        if event.type == "STEP_CREATED" and event.step:
            if event.step.role == "TOOL":
                print(f"[Tool: {event.step.tool_name}]")
                print(event.step.content[:100] + "...")
            else:
                print(f"{event.step.role}: {event.step.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

**输出示例**：
```
USER: List files in current directory
ASSISTANT: Let me list the files for you.
[Tool: bash]
total 48
drwxr-xr-x  12 user  staff   384 Jan 12 00:00 .
drwxr-xr-x  10 user  staff   320 Jan 11 23:00 ..
...
ASSISTANT: Here are the files in the current directory: ...
```

---

## 多 Agent 协作

### 3. 使用 AgentTool 实现 Agent 嵌套

```python
import asyncio
from agio import Agent, OpenAIModel, as_tool

async def main():
    # 创建专家 Agent
    researcher = Agent(
        model=OpenAIModel(model_name="gpt-4o"),
        name="researcher",
        system_prompt="You are an expert researcher. Provide detailed, well-researched answers.",
    )
    
    coder = Agent(
        model=OpenAIModel(model_name="gpt-4o"),
        name="coder",
        system_prompt="You are an expert programmer. Write clean, efficient code.",
    )
    
    # 转换为工具
    research_tool = as_tool(researcher, "Expert at research tasks")
    code_tool = as_tool(coder, "Expert at coding tasks")
    
    # 创建编排 Agent
    orchestrator = Agent(
        model=OpenAIModel(model_name="gpt-4o"),
        tools=[research_tool, code_tool],
        name="orchestrator",
        system_prompt="""
You are a master orchestrator that coordinates between experts.
- Use 'call_researcher' for research tasks
- Use 'call_coder' for coding tasks
""",
    )
    
    # 运行编排 Agent
    async for event in orchestrator.run_stream("Research and build a simple web scraper"):
        if event.type == "STEP_CREATED" and event.step:
            print(f"[{event.step.runnable_id or 'orchestrator'}] {event.step.role}: {event.step.content[:80]}...")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 持久化会话

### 4. 使用 SessionStore 保存对话历史

```python
import asyncio
from agio import Agent, OpenAIModel, MongoSessionStore

async def main():
    # 创建 Session Store
    session_store = MongoSessionStore(
        uri="mongodb://localhost:27017",
        db_name="agio"
    )
    
    # 创建 Agent（带会话存储）
    agent = Agent(
        model=OpenAIModel(model_name="gpt-4o"),
        session_store=session_store,
        name="chat_agent",
        system_prompt="You are a helpful assistant.",
    )
    
    # 多轮对话（使用相同的 session_id）
    session_id = "user_123_session"
    
    # 第一轮
    print("=== Round 1 ===")
    async for event in agent.run_stream("My name is Alice", session_id=session_id):
        if event.type == "STEP_CREATED" and event.step and event.step.role == "ASSISTANT":
            print(f"Assistant: {event.step.content}")
    
    # 第二轮（Agent 记住之前的对话）
    print("\n=== Round 2 ===")
    async for event in agent.run_stream("What is my name?", session_id=session_id):
        if event.type == "STEP_CREATED" and event.step and event.step.role == "ASSISTANT":
            print(f"Assistant: {event.step.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

**输出**：
```
=== Round 1 ===
Assistant: Nice to meet you, Alice!

=== Round 2 ===
Assistant: Your name is Alice.
```

---

## 可用的内置工具

Agio 提供丰富的内置工具：

| 工具 | 功能 | 示例 |
|------|------|------|
| `bash` | 执行 shell 命令 | `bash_tool = registry.get("bash")` |
| `file_read` | 读取文件内容 | `file_read_tool = registry.get("file_read")` |
| `file_write` | 写入文件 | `file_write_tool = registry.get("file_write")` |
| `file_edit` | 编辑文件（查找替换） | `file_edit_tool = registry.get("file_edit")` |
| `grep` | 搜索文件内容 | `grep_tool = registry.get("grep")` |
| `glob` | 文件模式匹配 | `glob_tool = registry.get("glob")` |
| `ls` | 列出目录 | `ls_tool = registry.get("ls")` |
| `web_search` | 网页搜索（需要 API） | `web_search_tool = registry.get("web_search")` |
| `web_reader` | 提取网页内容 | `web_reader_tool = registry.get("web_reader")` |

---

## 使用其他 LLM Provider

### Anthropic Claude

```python
from agio import Agent, AnthropicModel

agent = Agent(
    model=AnthropicModel(
        model_name="claude-3-5-sonnet-20241022",
        api_key="your-anthropic-api-key"  # 或设置 ANTHROPIC_API_KEY
    ),
    name="claude_agent",
)
```

### Deepseek

```python
from agio import Agent, DeepseekModel

agent = Agent(
    model=DeepseekModel(
        model_name="deepseek-chat",
        api_key="your-deepseek-api-key"  # 或设置 DEEPSEEK_API_KEY
    ),
    name="deepseek_agent",
)
```

---

## 环境变量

建议将 API 密钥设置为环境变量：

```bash
# .env 文件
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=...

# MongoDB (可选)
AGIO_MONGO_URI=mongodb://localhost:27017
AGIO_MONGO_DB=agio

# Skills 目录 (可选)
AGIO_SKILLS_DIR=./skills
```

然后在代码中使用 `python-dotenv`：

```python
from dotenv import load_dotenv
load_dotenv()

# 现在可以直接使用，无需显式传递 api_key
agent = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    ...
)
```

---

## 使用 API 服务器

### 启动服务器

```bash
# 默认配置（0.0.0.0:8900）
agio-server

# 自定义配置
agio-server --host 127.0.0.1 --port 8000

# 开发模式（自动重载）
agio-server --reload

# 生产模式（多进程）
agio-server --workers 4
```

### 调用 API

```bash
# 创建会话
curl -X POST http://localhost:8900/agio/sessions \
  -H "Content-Type: application/json" \
  -d '{}'

# 运行 Agent (需要先通过配置文件或代码注册 Agent)
curl -X POST http://localhost:8900/agio/agents/my_agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Hello!",
    "session_id": "session_123"
  }'
```

---

## 下一步

- 📚 [架构设计](./ARCHITECTURE.md) - 了解 Agio 的设计理念
- 🚀 [Agent 系统](./AGENT_SYSTEM.md) - 深入了解 Agent 执行引擎
- 🔧 [工具配置](./TOOL_CONFIGURATION.md) - 学习如何配置和扩展工具
- 📊 [可观测性](./OBSERVABILITY.md) - 追踪和监控 Agent 执行
- 🌐 [API 文档](./API_CONTROL_PANEL.md) - 使用 RESTful API

---

## 常见问题

### Q: 如何限制 Agent 执行时间？

```python
agent = Agent(
    model=model,
    max_steps=10,  # 最多执行 10 个步骤
)
```

### Q: 如何处理工具执行失败？

工具执行失败不会中断 Agent，错误信息会返回给 LLM，LLM 可以决定如何处理。

### Q: 如何自定义工具？

```python
from agio.tools import BaseTool, ToolResult

class MyTool(BaseTool):
    def get_name(self) -> str:
        return "my_tool"
    
    def get_description(self) -> str:
        return "My custom tool"
    
    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            }
        }
    
    async def execute(self, parameters, context, abort_signal):
        # 实现工具逻辑
        result = f"Processed: {parameters['input']}"
        return ToolResult(
            tool_name=self.get_name(),
            tool_call_id=parameters.get("tool_call_id", ""),
            content=result,
            output=result,
            is_success=True,
        )

# 使用自定义工具
my_tool = MyTool()
agent = Agent(model=model, tools=[my_tool])
```

---

**祝你使用愉快！** 🎉
