# Agio - Modern Agent Framework

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

**Agio** 是一个现代化、简洁的 Agent 框架，专注于核心功能和可扩展性。

## ✨ 核心特性

- **清晰分层** - domain/runtime/providers/config 四层架构
- **Step-based 执行** - 统一的消息模型，支持流式、重试、分支
- **可插拔组件** - LLM、存储、工具均可替换
- **配置驱动** - YAML 配置 + 环境变量，支持热重载

## 🚀 快速开始

### 安装

```bash
uv sync  # 推荐
# 或
pip install -r requirements.txt
```

### 基础使用

```python
from agio import Agent, OpenAIModel
from agio.providers.tools.builtin import FileReadTool, GrepTool

# 创建 Agent
agent = Agent(
    model=OpenAIModel(model_name="gpt-4"),
    tools=[FileReadTool(), GrepTool()],
    system_prompt="You are a helpful assistant.",
)

# 运行 (文本流)
async for text in agent.arun("What is 2+2?"):
    print(text, end="")

# 或获取完整事件流
async for event in agent.arun_stream("Search for Python tutorials"):
    if event.type == StepEventType.STEP_DELTA:
        print(event.delta.content, end="")
```

### 配置

```bash
# .env
AGIO_OPENAI_API_KEY=sk-...
AGIO_MONGO_URI=mongodb://localhost:27017  # 可选
```

```python
from agio.config import settings, ExecutionConfig

# 全局配置
print(settings.openai_api_key)

# 运行时配置
config = ExecutionConfig(max_steps=20, parallel_tool_calls=True)
```

## 📦 架构概览

```
agio/
├── __init__.py          # 顶层入口
├── agent.py             # Agent 类
│
├── domain/              # 纯领域模型（无外部依赖）
│   ├── models.py        # Step, AgentRun, AgentSession
│   ├── events.py        # StepEvent, StepDelta, ToolResult
│   └── adapters.py      # StepAdapter
│
├── runtime/             # 执行引擎
│   ├── runner.py        # StepRunner - Run 生命周期
│   ├── executor.py      # StepExecutor - LLM 调用循环
│   ├── tool_executor.py # ToolExecutor - 工具执行
│   ├── context.py       # 上下文构建
│   └── control.py       # AbortSignal, retry, fork
│
├── providers/           # 外部服务适配器
│   ├── llm/             # LLM 模型 (OpenAI, Anthropic, Deepseek)
│   ├── storage/         # 持久化 (InMemory, MongoDB)
│   └── tools/           # 工具 (base, registry, builtin/)
│
├── config/              # 配置系统
│   ├── settings.py      # AgioSettings (环境变量)
│   ├── schema.py        # ExecutionConfig, ComponentConfig
│   ├── system.py        # ConfigSystem (动态加载)
│   └── builders.py      # 组件构建器
│
├── api/                 # FastAPI 路由
└── utils/               # 工具函数
```

详细架构说明见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 🔧 核心概念

### Step 模型

```python
from agio.domain import Step, MessageRole

# 用户消息
user_step = Step(
    session_id="session_123",
    run_id="run_456",
    sequence=1,
    role=MessageRole.USER,
    content="Hello!"
)

# 助手响应（带工具调用）
assistant_step = Step(
    role=MessageRole.ASSISTANT,
    content="Let me search.",
    tool_calls=[{"id": "call_1", "type": "function", ...}]
)
```

### 自定义工具

```python
from agio.providers.tools import BaseTool
from agio.domain import ToolResult

class MyTool(BaseTool):
    def get_name(self) -> str:
        return "my_tool"
    
    def get_description(self) -> str:
        return "My custom tool"
    
    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    
    async def execute(self, parameters: dict, abort_signal=None) -> ToolResult:
        result = f"Result for: {parameters['query']}"
        return ToolResult(
            tool_name=self.name,
            content=result,
            is_success=True
        )
```

## 📚 文档

- [架构设计](docs/ARCHITECTURE.md) - 详细架构说明
- [API 文档](http://localhost:8900/docs) - 启动服务后访问

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md)

## 📄 许可证

MIT License
