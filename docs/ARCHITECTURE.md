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
| `execution_context.py` | ExecutionContext - 统一执行上下文 |
| `event_factory.py` | EventFactory - 上下文绑定的事件工厂 |
| `wire.py` | Wire - 事件流通道 |
| `context.py` | 从 Steps 构建 LLM 上下文 |
| `control.py` | AbortSignal, retry_from_sequence, fork_session |

#### ExecutionContext - 统一执行上下文

`ExecutionContext` 是一个不可变的数据类，封装所有执行相关的上下文信息：

```python
from agio.runtime.execution_context import ExecutionContext
from agio.runtime.wire import Wire

# 创建顶层执行上下文
wire = Wire()
ctx = ExecutionContext(
    run_id="run-001",
    session_id="session-001",
    wire=wire,  # 必需：事件流通道
    depth=0,  # 嵌套深度
)

# 创建嵌套执行上下文（用于 Agent 调用 Agent）
child_ctx = ctx.child(
    run_id="run-002",
    nested_runnable_id="research_agent",
    session_id=str(uuid4()),  # 可选：为嵌套执行创建新 session
)
# child_ctx.depth == 1, child_ctx.parent_run_id == "run-001"
```

**字段说明**：
- `run_id` - 当前 Run 唯一标识（必需）
- `session_id` - 会话标识（必需）
- `wire` - 事件流通道（必需），所有嵌套执行共享同一个 Wire
- `depth` - 嵌套深度，0 表示顶层
- `parent_run_id` - 父级 Run ID（嵌套时使用）
- `nested_runnable_id` - 被嵌套调用的 Runnable ID
- `parent_stage_id` - 父级 Stage ID（Workflow 中使用）
- `workflow_id` - Workflow ID（可选）
- `user_id` - 用户 ID（可选）
- `trace_id` / `span_id` / `parent_span_id` - 分布式追踪字段
- `metadata` - 扩展元数据字典

**注意**：`RunContext` 是 `ExecutionContext` 的别名，用于向后兼容。实际代码中统一使用 `ExecutionContext`。

#### EventFactory - 上下文绑定的事件工厂

`EventFactory` 绑定 `ExecutionContext`，简化事件创建：

```python
from agio.runtime.event_factory import EventFactory

ef = EventFactory(ctx)

# 创建事件无需重复传递上下文参数
await ctx.wire.write(ef.run_started(query="Hello"))
await ctx.wire.write(ef.step_delta(step_id, delta))
await ctx.wire.write(ef.step_completed(step_id, snapshot))
await ctx.wire.write(ef.run_completed(response="Done", metrics={}))
```

#### Wire - 事件流通道

`Wire` 是事件流通道，提供统一的异步事件传递机制：

```python
from agio.runtime.wire import Wire

# 在 API 入口创建 Wire
wire = Wire()

# 执行过程中写入事件
await wire.write(event)

# API 层读取事件并流式返回
async for event in wire.read():
    yield event

# 执行完成后关闭
await wire.close()
```

**设计要点**：
- 一个 Wire 对应一次顶层执行（在 API 入口创建）
- 所有嵌套执行共享同一个 Wire
- 通过 `context.wire` 传递给所有组件
- 组件直接写入事件到 Wire，而不是 yield

#### 执行流程

```
API 入口
    │
    ├── 创建 Wire
    ├── 创建 ExecutionContext (包含 wire)
    │
    ▼
Agent.run(input, context)
    │
    ▼
StepRunner.run(session, query, wire, context)
    │
    ├── 创建 AgentRun
    ├── 创建 ExecutionContext & EventFactory
    ├── 保存 User Step
    ├── 写入事件到 wire (via EventFactory)
    │
    ▼
StepExecutor.execute(messages, ctx)
    │
    ├── 构建上下文 (context.py)
    ├── 调用 LLM (Model.arun_stream)
    ├── 写入 StepEvent 到 ctx.wire (via EventFactory)
    │
    ▼ (如果有 tool_calls)
ToolExecutor.execute_tools()
    │
    ├── 并行执行工具
    ├── 嵌套 RunnableTool 使用 ctx.child() 创建子上下文
    │
    ▼ (循环直到无 tool_calls)
    │
    ▼
返回 RunOutput (response + metrics)
    │
    ▼
API 层从 wire.read() 读取事件并流式返回
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
