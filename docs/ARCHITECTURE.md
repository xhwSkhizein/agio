# Agio 架构设计

## 概述

Agio 采用清晰的四层架构，遵循 SOLID 和 KISS 原则：

```
┌─────────────────────────────────────────────────────────────┐
│                        agent.py                              │
│                    (顶层入口，编排层)                          │
├─────────────────────────────────────────────────────────────┤
│  domain/          │  runtime/         │  config/            │
│  (纯领域模型)      │  (执行引擎)        │  (配置系统)          │
├─────────────────────────────────────────────────────────────┤
│                      providers/                              │
│              (外部服务适配器: LLM, Storage, Tools)            │
└─────────────────────────────────────────────────────────────┘
```

## 模块职责

### 1. `agent.py` - 顶层入口

Agent 类是用户的主要入口点，负责：
- 持有配置（Model, Tools, Memory, Knowledge）
- 委托执行给 StepRunner
- 提供简洁的 API（`arun`, `arun_stream`）

```python
from agio import Agent, OpenAIModel

agent = Agent(
    model=OpenAIModel(model_name="gpt-4"),
    tools=[...],
    system_prompt="You are helpful."
)

async for text in agent.arun("Hello"):
    print(text)
```

### 2. `domain/` - 纯领域模型

**零外部依赖**，只包含核心数据结构：

| 文件 | 内容 |
|------|------|
| `models.py` | Step, AgentRun, AgentSession, StepMetrics |
| `events.py` | StepEvent, StepDelta, ToolResult |
| `adapters.py` | StepAdapter (Step ↔ LLM Message 转换) |

#### Step 模型

Step 是核心数据单元，直接映射 LLM 消息格式：

```python
class Step(BaseModel):
    id: str
    session_id: str
    run_id: str
    sequence: int
    role: MessageRole  # USER, ASSISTANT, TOOL, SYSTEM
    content: str | None
    tool_calls: list[dict] | None  # 助手发起的工具调用
    tool_call_id: str | None       # 工具结果关联的调用 ID
    name: str | None               # 工具名称
    metrics: StepMetrics | None
```

#### StepAdapter

保持 Domain 模型纯粹，转换逻辑集中在 Adapter：

```python
# Step → LLM Message
message = StepAdapter.to_llm_message(step)

# Steps → Messages (批量)
messages = StepAdapter.steps_to_messages(steps)
```

### 3. `runtime/` - 执行引擎

负责 Agent 的运行时执行：

| 文件 | 职责 |
|------|------|
| `runner.py` | StepRunner - 管理 Run 生命周期 |
| `executor.py` | StepExecutor - LLM 调用循环 |
| `tool_executor.py` | ToolExecutor - 并行工具执行 |
| `context.py` | 从 Steps 构建 LLM 上下文 |
| `control.py` | AbortSignal, retry_from_sequence, fork_session |

#### 执行流程

```
Agent.arun_stream()
    │
    ▼
StepRunner.run_stream()
    │
    ├── 创建 AgentRun
    ├── 保存 User Step
    │
    ▼
StepExecutor.execute_step()
    │
    ├── 构建上下文 (context.py)
    ├── 调用 LLM (Model.arun_stream)
    ├── 流式输出 StepEvent
    │
    ▼ (如果有 tool_calls)
ToolExecutor.execute_tools()
    │
    ├── 并行执行工具
    ├── 保存 Tool Steps
    │
    ▼ (循环直到无 tool_calls)
```

### 4. `providers/` - 外部服务适配器

封装所有外部依赖：

#### `providers/llm/`

```python
from agio.providers.llm import OpenAIModel, AnthropicModel, DeepseekModel

model = OpenAIModel(
    model_name="gpt-4",
    api_key="sk-...",
    temperature=0.7
)

async for chunk in model.arun_stream(messages, tools):
    print(chunk.content)
```

#### `providers/storage/`

```python
from agio.providers.storage import InMemorySessionStore, MongoSessionStore

# 内存存储（开发/测试）
store = InMemorySessionStore()

# MongoDB（生产）
store = MongoSessionStore(uri="mongodb://...", db_name="agio")

# 统一接口
await store.save_step(step)
steps = await store.get_steps(session_id)
```

#### `providers/tools/`

```python
from agio.providers.tools import BaseTool, get_tool_registry
from agio.providers.tools.builtin import FileReadTool, GrepTool

# 使用内置工具
tools = [FileReadTool(), GrepTool()]

# 或从注册表获取
registry = get_tool_registry()
tool = registry.create("file_read")
```

### 5. `config/` - 配置系统

#### 环境变量配置 (`settings.py`)

```python
from agio.config import settings

# 自动从环境变量加载
print(settings.openai_api_key)
print(settings.mongo_uri)
```

支持的环境变量：
- `AGIO_DEBUG` - 调试模式
- `AGIO_LOG_LEVEL` - 日志级别
- `AGIO_OPENAI_API_KEY` - OpenAI API Key
- `AGIO_ANTHROPIC_API_KEY` - Anthropic API Key
- `AGIO_DEEPSEEK_API_KEY` - Deepseek API Key
- `AGIO_MONGO_URI` - MongoDB 连接字符串

#### 运行时配置 (`schema.py`)

```python
from agio.config import ExecutionConfig

config = ExecutionConfig(
    max_steps=30,
    timeout_per_step=120.0,
    parallel_tool_calls=True,
    max_parallel_tools=10
)
```

#### 动态配置系统 (`system.py`)

支持从 YAML 文件加载组件配置：

```yaml
# configs/agents/my_agent.yaml
type: agent
name: my_agent
model: gpt4_model
tools:
  - file_read
  - grep
system_prompt: "You are helpful."
```

```python
from agio.config import init_config_system

# 加载配置并构建组件
config_sys = await init_config_system("configs/")

# 获取组件
agent = config_sys.get("my_agent")
```

## 依赖关系

```
agent.py
    ├── domain/      (数据模型)
    ├── runtime/     (执行引擎)
    ├── providers/   (外部服务)
    └── config/      (配置)

runtime/
    ├── domain/      (数据模型)
    └── providers/   (LLM, Storage, Tools)

providers/
    └── domain/      (数据模型)

config/
    └── providers/   (构建组件)
```

**关键原则**：
- `domain/` 不依赖任何其他模块
- `runtime/` 依赖 `domain/` 和 `providers/`
- `providers/` 只依赖 `domain/`
- `config/` 负责组装所有组件

## 扩展指南

### 添加新的 LLM Provider

1. 在 `providers/llm/` 创建新文件
2. 继承 `Model` 基类
3. 实现 `arun_stream` 方法
4. 在 `providers/llm/__init__.py` 导出

```python
# providers/llm/my_provider.py
from agio.providers.llm.base import Model, StreamChunk

class MyProviderModel(Model):
    async def arun_stream(self, messages, tools=None):
        # 实现流式调用
        yield StreamChunk(content="Hello")
```

### 添加新的工具

1. 继承 `BaseTool`
2. 实现必要方法
3. 可选：注册到 ToolRegistry

```python
from agio.providers.tools import BaseTool
from agio.domain import ToolResult

class MyTool(BaseTool):
    def get_name(self) -> str:
        return "my_tool"
    
    def get_description(self) -> str:
        return "My custom tool"
    
    def get_parameters(self) -> dict:
        return {"type": "object", "properties": {...}}
    
    async def execute(self, parameters, abort_signal=None) -> ToolResult:
        # 实现工具逻辑
        return ToolResult(content="result", is_success=True)
```

### 添加新的存储后端

1. 在 `providers/storage/` 创建新文件
2. 继承 `SessionStore`
3. 实现所有抽象方法

```python
from agio.providers.storage.base import SessionStore

class MySessionStore(SessionStore):
    async def save_step(self, step): ...
    async def get_steps(self, session_id): ...
    # ... 其他方法
```

## 测试

```bash
# 运行所有测试
pytest tests/

# 运行特定模块测试
pytest tests/tools/
pytest tests/config/
```
