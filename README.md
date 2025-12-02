# Agio - Modern Agent Framework

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61dafb.svg)](https://reactjs.org/)

**Agio** 是一个现代化、简洁的 Agent 框架，专注于核心功能和可扩展性。

> 🎉 **v2.0 重构完成！** 架构大幅简化，包数量减少 53%，更易理解和维护。

## ✨ 核心特性

### 🏗️ 简洁架构
- **7 个核心包** - 清晰的职责划分
- **统一配置** - 一个配置系统管理所有设置
- **零转换设计** - Step 模型直接映射 LLM 消息格式
- **适配器模式** - 数据模型和转换逻辑分离

### 💾 Step-based 执行
- **统一的 Step 模型** - 用户消息、助手响应、工具调用统一表示
- **流式执行** - 实时 SSE 事件流
- **完整追踪** - 每个 Step 包含详细的 metrics
- **Resume/Fork** - 从任意 Step 恢复或分支

### 🔌 可插拔组件
- **多模型支持** - OpenAI、Anthropic、Deepseek
- **丰富的工具** - 内置工具库 + 自定义工具
- **记忆系统** - 对话记忆 + 语义记忆
- **知识库** - Vector 知识库集成

### 🚀 FastAPI Backend
- **RESTful API** - 完整的 CRUD 操作
- **SSE 流式传输** - 实时 Chat 交互
- **自动文档** - Swagger UI + ReDoc

## 🚀 快速开始

### 安装

```bash
# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 基础使用

```python
from agio.agent import Agent
from agio.components.models.openai import OpenAIModel
from agio.components.tools.builtin import SearchTool, CalculatorTool
from agio.core import ExecutionConfig

# 创建 Agent
agent = Agent(
    model=OpenAIModel(model_name="gpt-4"),
    tools=[SearchTool(), CalculatorTool()],
    system_prompt="You are a helpful assistant.",
)

# 运行 Agent (文本流)
async for text in agent.arun("What is 2+2?"):
    print(text, end="", flush=True)

# 或获取完整的事件流
async for event in agent.arun_stream("Search for Python tutorials"):
    if event.type == "step_delta":
        print(event.delta.content, end="")
    elif event.type == "step_completed":
        print(f"\nStep completed: {event.snapshot.role}")
```

### 配置

使用环境变量或 `.env` 文件：

```bash
# .env
AGIO_DEBUG=false
AGIO_LOG_LEVEL=INFO

# OpenAI
AGIO_OPENAI_API_KEY=sk-...
AGIO_OPENAI_BASE_URL=https://api.openai.com/v1

# MongoDB (可选)
AGIO_MONGO_URI=mongodb://localhost:27017
AGIO_MONGO_DB_NAME=agio
```

在代码中使用：

```python
from agio.core.config import settings, ExecutionConfig

# 全局配置
print(settings.log_level)

# 运行时配置
config = ExecutionConfig(
    max_steps=20,
    parallel_tool_calls=True,
    timeout_per_step=120.0
)

agent = Agent(model=model, tools=tools)
runner = StepRunner(agent=agent, config=config)
```

## 📦 架构概览

```
agio/
├── core/          # 核心模型、事件、配置
│   ├── models.py      # Step, AgentRun, Session 等
│   ├── events.py      # StepEvent, StepDelta 等
│   ├── config.py      # 统一配置管理
│   └── adapters.py    # 格式转换适配器
│
├── agent/         # Agent 核心
│   ├── base.py        # Agent 类
│   └── hooks.py       # 生命周期钩子
│
├── execution/     # 执行引擎
│   ├── runner.py      # StepRunner - 管理 Run 生命周期
│   ├── executor.py    # StepExecutor - LLM 循环
│   ├── tools.py       # ToolExecutor - 工具执行
│   └── context.py     # 上下文构建
│
├── components/    # 可插拔组件
│   ├── models/        # LLM 模型适配器
│   ├── tools/         # 工具实现
│   ├── memory/        # 记忆系统
│   └── knowledge/     # 知识库
│
├── storage/       # 持久化层
│   ├── base.py        # Storage 接口
│   ├── repository.py  # AgentRunRepository
│   └── mongo.py       # MongoDB 实现
│
├── api/           # Web API
└── utils/         # 工具函数
```

## 🔧 核心概念

### Step 模型

Step 是 Agio 的核心数据模型，直接映射 LLM 消息格式：

```python
from agio.core import Step, MessageRole

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
    session_id="session_123",
    run_id="run_456",
    sequence=2,
    role=MessageRole.ASSISTANT,
    content="Let me search for that.",
    tool_calls=[{
        "id": "call_123",
        "type": "function",
        "function": {"name": "search", "arguments": "{}"}
    }]
)

# 工具结果
tool_step = Step(
    session_id="session_123",
    run_id="run_456",
    sequence=3,
    role=MessageRole.TOOL,
    content="Search results: ...",
    tool_call_id="call_123",
    name="search"
)
```

### StepAdapter

用于格式转换，保持 Domain 模型纯粹：

```python
from agio.core import StepAdapter

# Step → LLM Message
message = StepAdapter.to_llm_message(step)

# Steps → Messages
messages = StepAdapter.steps_to_messages(steps)

# 直接发送给 LLM
response = await llm.chat(messages)
```

### 自定义工具

```python
import time
from agio.components.tools import BaseTool
from agio.core.events import ToolResult

class MyTool(BaseTool):
    """My custom tool"""
    
    def get_name(self) -> str:
        return "my_tool"
    
    def get_description(self) -> str:
        return "My custom tool description"
    
    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "First parameter"},
                "param2": {"type": "integer", "description": "Second parameter"},
            },
            "required": ["param1", "param2"],
        }
    
    def is_concurrency_safe(self) -> bool:
        return True
    
    async def execute(self, parameters: dict, abort_signal=None) -> ToolResult:
        start_time = time.time()
        param1 = parameters.get("param1", "")
        param2 = parameters.get("param2", 0)
        result = f"Result: {param1} {param2}"
        
        return ToolResult(
            tool_name=self.name,
            tool_call_id=parameters.get("tool_call_id", ""),
            input_args=parameters,
            content=result,
            output=result,
            start_time=start_time,
            end_time=time.time(),
            duration=time.time() - start_time,
            is_success=True,
        )

# 使用
agent = Agent(
    model=model,
    tools=[MyTool()]
)
```

### 自定义 Hook

```python
from agio.agent.hooks import AgentHook
from agio.core import AgentRun, Step

class MyHook(AgentHook):
    async def on_run_start(self, run: AgentRun):
        print(f"Run started: {run.id}")
    
    async def on_step_end(self, run: AgentRun, step: Step):
        print(f"Step completed: {step.sequence}")

# 使用
agent = Agent(
    model=model,
    hooks=[MyHook()]
)
```

## 📚 文档

- [架构设计](REFACTORING_SUMMARY.md) - 详细的架构说明和重构总结
- [API 文档](http://localhost:8000/docs) - 启动服务后访问
- [测试总结](TEST_SUMMARY.md) - 测试套件运行结果

## 🔄 从 v1.x 迁移

### 主要变更

1. **包结构简化**
   - `domain/` → `core/models.py`
   - `protocol/` → `core/events.py`
   - `runners/` + `execution/` → `execution/`
   - `db/` → `storage/`
   - `models/` → `components/models/`

2. **配置统一**
   - `AgentRunConfig` + `StepExecutorConfig` → `ExecutionConfig`
   - 所有配置在 `core/config.py`

3. **API 变更**
   - `step.to_message_dict()` → `StepAdapter.to_llm_message(step)`
   - `from agio.domain.step import Step` → `from agio.core import Step`

4. **Registry 移除**
   - 动态配置管理系统已移除
   - 使用环境变量和代码配置

详见 [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md)

## 📄 许可证

MIT License

## 🙏 致谢

感谢所有贡献者！
