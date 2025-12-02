# Core Package

`agio.core` 包含 Agio 框架的核心数据模型、事件系统和配置管理。

## 📦 模块概览

### `models.py` - 核心数据模型

定义了 Agio 的核心领域模型：

#### Step
统一的步骤模型，直接映射 LLM 消息格式：

```python
from agio.core import Step, MessageRole

# 用户消息
step = Step(
    session_id="session_123",
    run_id="run_456",
    sequence=1,
    role=MessageRole.USER,
    content="Hello!"
)

# 转换为 LLM 消息（使用 StepAdapter）
from agio.core import StepAdapter
message = StepAdapter.to_llm_message(step)
# {"role": "user", "content": "Hello!"}
```

**字段说明**：
- `id`: 唯一标识符（自动生成）
- `session_id`: 会话 ID
- `run_id`: 运行 ID（一次用户查询到响应的完整周期）
- `sequence`: 全局序列号（在会话中递增）
- `role`: 消息角色（USER, ASSISTANT, TOOL, SYSTEM）
- `content`: 消息内容
- `tool_calls`: 工具调用列表（仅 ASSISTANT）
- `tool_call_id`: 工具调用 ID（仅 TOOL）
- `name`: 工具名称（仅 TOOL）
- `metrics`: 性能指标
- `created_at`: 创建时间

**方法**：
- `is_user_step()`: 是否为用户消息
- `is_assistant_step()`: 是否为助手消息
- `is_tool_step()`: 是否为工具结果
- `has_tool_calls()`: 是否包含工具调用

**注意**：格式转换请使用 `StepAdapter.to_llm_message(step)`，保持 Domain 模型纯粹

#### StepMetrics
步骤性能指标：

```python
from agio.core import StepMetrics

metrics = StepMetrics(
    duration_ms=150.5,
    input_tokens=100,
    output_tokens=50,
    total_tokens=150,
    model_name="gpt-4",
    provider="openai",
    first_token_latency_ms=25.3
)
```

#### AgentRun
Agent 运行状态：

```python
from agio.core import AgentRun, RunStatus

run = AgentRun(
    agent_id="assistant",
    session_id="session_123",
    input_query="Hello",
    status=RunStatus.RUNNING
)
```

#### AgentSession
会话状态：

```python
from agio.core import AgentSession

session = AgentSession(
    session_id="session_123",
    user_id="user_456"
)
```

### `events.py` - 事件系统

定义了执行过程中的事件流：

#### StepEvent
统一的事件模型：

```python
from agio.core import StepEvent, StepEventType

# 运行开始
event = StepEvent(
    type=StepEventType.RUN_STARTED,
    run_id="run_123"
)

# 内容增量
event = StepEvent(
    type=StepEventType.STEP_DELTA,
    run_id="run_123",
    delta=StepDelta(content="Hello")
)

# 步骤完成
event = StepEvent(
    type=StepEventType.STEP_COMPLETED,
    run_id="run_123",
    snapshot=step  # 完整的 Step 对象
)
```

**事件类型**：
- `RUN_STARTED`: 运行开始
- `RUN_COMPLETED`: 运行完成
- `RUN_FAILED`: 运行失败
- `STEP_STARTED`: 步骤开始
- `STEP_DELTA`: 内容增量（流式）
- `STEP_COMPLETED`: 步骤完成
- `TOOL_CALL_STARTED`: 工具调用开始
- `TOOL_CALL_COMPLETED`: 工具调用完成

#### StepDelta
增量数据：

```python
from agio.core import StepDelta

delta = StepDelta(
    content="Hello",
    tool_calls=[{"id": "call_123", ...}]
)
```

#### ToolResult
工具执行结果：

```python
from agio.core import ToolResult

result = ToolResult(
    tool_name="search",
    tool_call_id="call_123",
    content="Search results...",
    is_success=True
)
```

### `config.py` - 配置管理

统一的配置系统：

#### Settings
全局配置（从环境变量加载）：

```python
from agio.core.config import settings

# 访问配置
print(settings.log_level)  # INFO
print(settings.openai_api_key)  # sk-...
print(settings.mongo_uri)  # mongodb://...
```

**环境变量**：
- `AGIO_DEBUG`: 调试模式
- `AGIO_LOG_LEVEL`: 日志级别
- `AGIO_OPENAI_API_KEY`: OpenAI API Key
- `AGIO_OPENAI_BASE_URL`: OpenAI Base URL
- `AGIO_MONGO_URI`: MongoDB URI
- `AGIO_MONGO_DB_NAME`: MongoDB 数据库名

#### ExecutionConfig
运行时配置：

```python
from agio.core import ExecutionConfig

config = ExecutionConfig(
    max_steps=20,
    parallel_tool_calls=True,
    timeout_per_step=120.0,
    enable_retry=True,
    max_retries=3
)
```

### `adapters.py` - 格式转换

数据格式转换适配器：

#### StepAdapter
Step 和 LLM 消息之间的转换：

```python
from agio.core import StepAdapter

# Step → LLM Message
message = StepAdapter.to_llm_message(step)

# Steps → Messages
messages = StepAdapter.steps_to_messages(steps)

# LLM Response → Step
step = StepAdapter.from_llm_response(
    response_dict,
    session_id="session_123",
    run_id="run_456",
    sequence=2
)
```

## 🎯 设计原则

### 1. 零转换设计
Step 模型直接映射 LLM 消息格式，通过 StepAdapter 实现零开销转换：

```python
# Step 结构与 OpenAI 消息格式完全一致
step = Step(role=MessageRole.USER, content="Hello")

# 使用 StepAdapter 转换
message = StepAdapter.to_llm_message(step)
# {"role": "user", "content": "Hello"}
```

### 2. 适配器模式
使用 Adapter 处理格式转换，保持 Domain 模型纯粹：

```python
# ✅ Domain 模型只包含数据，不包含转换逻辑
step = Step(
    session_id="session_123",
    role=MessageRole.USER,
    content="Hello"
)

# ✅ Adapter 负责所有格式转换
message = StepAdapter.to_llm_message(step)
messages = StepAdapter.steps_to_messages([step1, step2, step3])
```

### 3. 事件驱动
所有执行过程通过事件流传递：

```python
async for event in runner.run_stream(session, query):
    if event.type == StepEventType.STEP_DELTA:
        print(event.delta.content, end="")
    elif event.type == StepEventType.STEP_COMPLETED:
        print(f"\nCompleted: {event.snapshot.role}")
```

### 4. 配置分离
全局配置（Settings）和运行时配置（ExecutionConfig）分离：

```python
# 全局配置（环境变量）
from agio.core.config import settings

# 运行时配置（代码）
config = ExecutionConfig(max_steps=20)
```

## 📊 数据流

```
User Input
    ↓
Step (USER)
    ↓
StepExecutor
    ↓
StepEvent (DELTA) → Frontend
    ↓
Step (ASSISTANT)
    ↓
ToolExecutor (if tool_calls)
    ↓
Step (TOOL)
    ↓
StepEvent (COMPLETED) → Frontend
    ↓
Repository (save)
```

## 🔗 相关文档

- [Execution Package](../execution/README.md) - 执行引擎
- [Storage Package](../storage/README.md) - 持久化层
- [API Package](../api/README.md) - Web API
