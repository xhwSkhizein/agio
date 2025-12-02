# Agio 架构文档

## 概览

Agio 采用 **Step-based 事件驱动架构**，核心理念是：
- **Step 即 Message** - 统一的数据模型直接映射 LLM 消息格式
- **零转换** - 减少数据转换开销
- **事件流** - 实时流式执行和观测

## 架构图

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                         User/Client                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                       Agent (配置容器)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Model   │  │  Tools   │  │  Memory  │  │  Hooks   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      StepRunner (编排层)                      │
│  • 管理 Run 生命周期                                          │
│  • 调用 Hooks                                                │
│  • 保存 Steps 到 Repository                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    StepExecutor (执行层)                      │
│  • 实现 LLM ↔ Tool 循环                                      │
│  • 创建 Steps (User, Assistant, Tool)                       │
│  • 发送 StepEvents (Delta + Snapshot)                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                ┌────────┴────────┐
                ▼                 ▼
        ┌──────────────┐  ┌──────────────┐
        │     Model    │  │ ToolExecutor │
        │   (LLM API)  │  │  (工具执行)   │
        └──────────────┘  └──────────────┘
                │                 │
                └────────┬────────┘
                         ▼
                  ┌──────────────┐
                  │  Repository  │
                  │  (持久化)     │
                  └──────────────┘
```

### 数据流

```
User Query
    │
    ▼
┌─────────────────┐
│  User Step      │  sequence=1, role=USER
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Context Build  │  Load history + Build messages
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Call       │  Stream response
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Assistant Step  │  sequence=2, role=ASSISTANT
│ (with tool_calls)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Tool Execution │  Execute tools in parallel
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Tool Steps     │  sequence=3,4,5... role=TOOL
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Call       │  Continue loop
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Final Response  │  No tool calls → Done
└─────────────────┘
```

### Step 模型

```
┌──────────────────────────────────────────────────────────┐
│                         Step                              │
├──────────────────────────────────────────────────────────┤
│  Indexing & Association                                   │
│  • id: str                                                │
│  • session_id: str                                        │
│  • run_id: str                                            │
│  • sequence: int                                          │
├──────────────────────────────────────────────────────────┤
│  Core Content (Standard LLM Message)                      │
│  • role: MessageRole (user/assistant/tool/system)        │
│  • content: str | None                                    │
│  • tool_calls: list[dict] | None  (assistant only)       │
│  • tool_call_id: str | None       (tool only)            │
│  • name: str | None                (tool only)            │
├──────────────────────────────────────────────────────────┤
│  Metadata                                                 │
│  • metrics: StepMetrics | None                            │
│  • created_at: datetime                                   │
└──────────────────────────────────────────────────────────┘
         │
         │ StepAdapter.to_llm_message()
         ▼
┌──────────────────────────────────────────────────────────┐
│              LLM Message (OpenAI Format)                  │
├──────────────────────────────────────────────────────────┤
│  {                                                        │
│    "role": "assistant",                                   │
│    "content": "Let me search for that",                   │
│    "tool_calls": [...]                                    │
│  }                                                        │
└──────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. Core Package

**职责**: 核心数据模型、事件、配置

**模块**:
- `models.py` - Step, AgentRun, Session 等领域模型
- `events.py` - StepEvent, StepDelta 等事件类型
- `config.py` - 统一配置管理
- `adapters.py` - 格式转换适配器

**设计原则**:
- Domain 模型保持纯粹（只有数据）
- 转换逻辑在 Adapter 中
- 配置分层：全局 → 运行时 → 组件

### 2. Agent Package

**职责**: Agent 配置容器和生命周期钩子

**组件**:
- `Agent` - 持有 Model, Tools, Memory 等配置
- `AgentHook` - 生命周期钩子基类
- `LoggingHook` - 日志钩子
- `StorageHook` - 存储钩子

**Hook 生命周期**:
```
on_run_start
    ↓
on_step_start
    ↓
on_model_start → on_model_end
    ↓
on_tool_start → on_tool_end (for each tool)
    ↓
on_step_end
    ↓
on_run_end (or on_error)
```

### 3. Execution Package

**职责**: 执行引擎，实现 LLM ↔ Tool 循环

**组件**:
- `StepRunner` - 管理 Run 生命周期，调用 Hooks
- `StepExecutor` - 实现 LLM 循环，创建 Steps
- `ToolExecutor` - 并行执行工具
- `context.py` - 从 Steps 构建 LLM 上下文

**执行流程**:
```python
# 1. Runner 创建 Run 和 User Step
run = AgentRun(...)
user_step = Step(role=USER, content=query)

# 2. 构建上下文
messages = build_context_from_steps(session_id, repository)

# 3. Executor 执行 LLM 循环
async for event in executor.execute(messages):
    # 4. 发送事件流
    yield event
    
    # 5. 保存 Steps
    if event.type == STEP_COMPLETED:
        await repository.save_step(event.snapshot)
```

### 4. Components Package

**职责**: 可插拔组件

**子包**:
- `models/` - LLM 模型适配器 (OpenAI, Anthropic, Deepseek)
- `tools/` - 工具实现 (builtin + custom)
- `memory/` - 记忆系统 (对话记忆 + 语义记忆)
- `knowledge/` - 知识库 (Vector DB)

**扩展性**:
```python
# 自定义模型
class MyModel(Model):
    async def arun_stream(self, messages, tools=None):
        # 实现流式调用
        yield StreamChunk(...)

# 自定义工具
class MyTool(Tool):
    name = "my_tool"
    async def execute(self, **kwargs):
        return result
```

### 5. Storage Package

**职责**: 持久化层

**组件**:
- `Storage` - 存储接口 (for AgentRun)
- `AgentRunRepository` - Repository 接口 (for Steps + Runs)
- `MongoDBRepository` - MongoDB 实现
- `InMemoryRepository` - 内存实现

**数据模型**:
```
AgentRun (1) ──┬──> Steps (N)
               │
               └──> Metrics
```

## 设计模式

### 1. 适配器模式

**问题**: Domain 模型不应包含转换逻辑

**解决方案**: StepAdapter

```python
# Domain 模型 (纯数据)
class Step(BaseModel):
    role: MessageRole
    content: str | None
    # ...

# 适配器 (转换逻辑)
class StepAdapter:
    @staticmethod
    def to_llm_message(step: Step) -> dict:
        return {"role": step.role.value, "content": step.content, ...}
```

### 2. 策略模式

**问题**: 支持多种 LLM 提供商

**解决方案**: Model 基类 + 具体实现

```python
class Model(ABC):
    @abstractmethod
    async def arun_stream(self, messages, tools=None):
        pass

class OpenAIModel(Model):
    async def arun_stream(self, messages, tools=None):
        # OpenAI specific implementation
        
class AnthropicModel(Model):
    async def arun_stream(self, messages, tools=None):
        # Anthropic specific implementation
```

### 3. 观察者模式

**问题**: 需要在执行过程中插入自定义逻辑

**解决方案**: Hook 系统

```python
class AgentHook(ABC):
    async def on_run_start(self, run): pass
    async def on_step_end(self, run, step): pass
    # ...

# 使用
agent = Agent(
    model=model,
    hooks=[LoggingHook(), MetricsHook(), CustomHook()]
)
```

### 4. 仓储模式

**问题**: 持久化逻辑与业务逻辑分离

**解决方案**: Repository 接口

```python
class AgentRunRepository(ABC):
    @abstractmethod
    async def save_step(self, step: Step): pass
    
    @abstractmethod
    async def get_steps(self, session_id: str) -> list[Step]: pass

# 实现可以是 MongoDB, PostgreSQL, Redis 等
```

## 性能优化

### 1. 零转换设计

Step 模型直接映射 LLM 消息格式，避免多次转换：

```python
# 传统方式 (多次转换)
Event → Message → Dict → JSON → LLM

# Agio 方式 (零转换)
Step → Dict → LLM  # Step.to_message_dict() 已移除
Step → LLM         # 通过 StepAdapter
```

### 2. 流式处理

所有 LLM 调用都是流式的，减少首字延迟：

```python
async for chunk in model.arun_stream(messages):
    # 立即发送给客户端
    yield create_step_delta_event(chunk)
```

### 3. 并行工具执行

多个工具调用并行执行：

```python
results = await asyncio.gather(*[
    tool_executor.execute(tc) for tc in tool_calls
])
```

## 可扩展性

### 1. 水平扩展

- **无状态 API** - 可以部署多个实例
- **Repository 抽象** - 支持分布式存储
- **Session 隔离** - 不同 session 独立执行

### 2. 组件扩展

- **自定义 Model** - 实现 Model 接口
- **自定义 Tool** - 实现 Tool 接口
- **自定义 Hook** - 实现 AgentHook 接口
- **自定义 Storage** - 实现 Repository 接口

### 3. 功能扩展

- **Retry/Fork** - 基于 Step sequence 实现
- **Time Travel** - 基于 Step 历史实现
- **A/B Testing** - Fork session 并比较结果

## 最佳实践

### 1. 配置管理

```python
# 使用环境变量
from agio.core.config import settings

# 运行时配置
config = ExecutionConfig(
    max_steps=20,
    parallel_tool_calls=True
)
```

### 2. 错误处理

```python
try:
    async for event in agent.arun_stream(query):
        if event.type == StepEventType.ERROR:
            logger.error(f"Error: {event.data['error']}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
```

### 3. 性能监控

```python
class MetricsHook(AgentHook):
    async def on_run_end(self, run):
        metrics = run.metrics
        logger.info(f"Duration: {metrics.duration}s")
        logger.info(f"Tokens: {metrics.total_tokens}")
        logger.info(f"Tool calls: {metrics.tool_calls_count}")
```

## 未来规划

### 短期
- [ ] 完善测试覆盖率
- [ ] 添加更多内置工具
- [ ] 支持更多 LLM 提供商

### 中期
- [ ] 分布式执行支持
- [ ] 高级记忆系统
- [ ] 可视化调试工具

### 长期
- [ ] Multi-agent 协作
- [ ] 自动化测试和评估
- [ ] 生产级监控和告警

## 参考资料

- [REFACTORING_SUMMARY.md](../REFACTORING_SUMMARY.md) - 重构详细说明
- [TEST_SUMMARY.md](../TEST_SUMMARY.md) - 测试结果
- [README.md](../README.md) - 快速开始指南
