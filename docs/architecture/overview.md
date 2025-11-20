# Agio 架构概览

**版本**: v0.4.0  
**最后更新**: 2025-11-21

---

## 📐 架构设计原则

Agio 采用**清晰的三层架构**设计，每层职责单一、高内聚低耦合：

### 核心原则

1. **职责分离** - 配置、编排、执行、接口四层分离
2. **事件驱动** - 统一的 AgentEvent 贯穿整个系统
3. **异步原生** - 全链路异步，天然支持流式输出
4. **类型安全** - Pydantic 模型保证类型正确性
5. **可插拔** - Tools、Storage、Memory 等可自由替换

---

## 🏗️ 系统架构

### 四层架构图

```
┌─────────────────────────────────────────────────────────┐
│                    Layer 1: Agent                       │
│              (Configuration Container)                  │
│                                                          │
│  • Model (LLM configuration)                            │
│  • Tools (available functions)                          │
│  • Memory (conversation history)                        │
│  • Knowledge (RAG knowledge base)                       │
│  • Storage (persistence backend)                        │
│  • Hooks (lifecycle callbacks)                          │
└────────────────────┬────────────────────────────────────┘
                     │ arun() / arun_stream()
                     ▼
┌─────────────────────────────────────────────────────────┐
│                 Layer 2: AgentRunner                    │
│                 (Orchestrator)                          │
│                                                          │
│  Components:                                            │
│  • ContextBuilder - 构建完整上下文                       │
│  • RunStateTracker - 追踪 Run 状态                      │
│  • Hook Dispatcher - 调度生命周期钩子                    │
│  • Event Storage - 持久化事件流                         │
│                                                          │
│  Responsibilities:                                      │
│  1. 创建和管理 AgentRun                                  │
│  2. 构建消息上下文 (System + History + RAG + Memory)    │
│  3. 调度 AgentExecutor                                  │
│  4. 消费 AgentEvent 流                                  │
│  5. 更新状态和 Metrics                                  │
│  6. 调用 Hooks                                          │
│  7. 持久化到 Repository                                 │
└────────────────────┬────────────────────────────────────┘
                     │ messages + run_id
                     ▼
┌─────────────────────────────────────────────────────────┐
│                Layer 3: AgentExecutor                   │
│              (LLM ↔ Tool Loop Engine)                   │
│                                                          │
│  Components:                                            │
│  • ToolCallAccumulator - 累加流式 tool calls             │
│  • ToolExecutor - 执行工具调用                           │
│  • Event Generator - 生成 AgentEvent                    │
│                                                          │
│  Loop Logic:                                            │
│  ┌─────────────────────────────────────┐               │
│  │  while step < max_steps:             │               │
│  │    1. Call Model.arun_stream()      │               │
│  │    2. Accumulate tool calls          │               │
│  │    3. Emit TEXT_DELTA events        │               │
│  │    4. Execute tools (if any)         │               │
│  │    5. Emit TOOL_CALL events         │               │
│  │    6. Add results to messages        │               │
│  │    7. Continue or finish             │               │
│  └─────────────────────────────────────┘               │
└────────────────────┬────────────────────────────────────┘
                     │ messages + tools
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  Layer 4: Model                         │
│              (Pure LLM Interface)                       │
│                                                          │
│  Interface:                                             │
│  • arun_stream(messages, tools) -> StreamChunk         │
│                                                          │
│  Implementations:                                       │
│  • OpenAIModel                                          │
│  • DeepseekModel                                        │
│  • (Extensible)                                         │
│                                                          │
│  Responsibilities:                                      │
│  • 调用 LLM API                                         │
│  • 返回标准化的 StreamChunk                             │
│  • 处理 API 错误和重试                                  │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 数据流

### 完整执行流程

```
1. User Query
   │
   ├─→ Agent.arun_stream(query)
   │
   ├─→ AgentRunner 创建 AgentRun
   │   • 触发 on_run_start hooks
   │   • 发送 RUN_STARTED event
   │
   ├─→ ContextBuilder 构建上下文
   │   • System Prompt
   │   • Chat History (from Memory)
   │   • RAG Documents (from Knowledge)
   │   • Semantic Memories
   │
   ├─→ AgentExecutor.execute(messages, run_id)
   │   │
   │   ├─→ Loop Start (step = 1)
   │   │
   │   ├─→ Model.arun_stream(messages, tools)
   │   │   └─→ 返回 StreamChunk 流
   │   │
   │   ├─→ 处理 StreamChunk
   │   │   ├─ content? → 发送 TEXT_DELTA event
   │   │   ├─ tool_calls? → 累加到 ToolCallAccumulator
   │   │   └─ usage? → 发送 USAGE_UPDATE event
   │   │
   │   ├─→ 有 tool calls?
   │   │   ├─ Yes:
   │   │   │   ├─→ 发送 TOOL_CALL_STARTED events
   │   │   │   ├─→ ToolExecutor.execute_batch(tool_calls)
   │   │   │   ├─→ 发送 TOOL_CALL_COMPLETED events
   │   │   │   ├─→ 将结果添加到 messages
   │   │   │   └─→ 继续下一个 step
   │   │   │
   │   │   └─ No:
   │   │       └─→ 结束循环
   │   │
   │   └─→ 发送 STEP_COMPLETED event
   │
   ├─→ RunStateTracker 更新状态
   │   • 累积 tokens
   │   • 记录 tool calls
   │   • 构建 response
   │
   ├─→ Repository 持久化
   │   • 保存 AgentRun
   │   • 保存所有 Events
   │
   ├─→ 触发 on_run_end hooks
   │
   └─→ 发送 RUN_COMPLETED event
```

---

## 📦 核心组件详解

### 1. Agent (配置容器)

**文件**: `agio/agent/base.py`

**职责**:
- 持有所有配置：Model、Tools、Memory、Knowledge、Hooks
- 提供执行入口：`arun()`, `arun_stream()`
- 提供历史查询：`get_run_history()`, `list_runs()`

**不负责**:
- ❌ 实际的执行逻辑
- ❌ 上下文构建
- ❌ 事件生成

```python
agent = Agent(
    model=OpenAIModel(),
    tools=[tool1, tool2],
    memory=SimpleMemory(),
    knowledge=VectorKnowledge(),
    repository=PostgreSQLRepository(),
    hooks=[LoggingHook(), MetricsHook()]
)

# 执行
async for event in agent.arun_stream(query):
    process(event)
```

### 2. AgentRunner (编排器)

**文件**: `agio/runners/base.py`

**职责**:
1. **生命周期管理**
   - 创建 AgentRun
   - 调用 Hooks (on_run_start, on_run_end, on_error)
   - 发送 Run 级别事件

2. **上下文构建** (通过 ContextBuilder)
   - 加载 System Prompt
   - 查询聊天历史
   - 检索 RAG 文档
   - 获取语义记忆

3. **状态管理** (通过 RunStateTracker)
   - 追踪执行状态
   - 累积 metrics
   - 构建最终响应

4. **事件处理**
   - 消费 AgentExecutor 的事件流
   - 持久化到 Repository
   - 转发给调用者

**不负责**:
- ❌ LLM 调用
- ❌ Tool 执行
- ❌ Tool calls 累加

```python
runner = AgentRunner(agent, hooks, config, repository)
async for event in runner.run_stream(session, query):
    yield event
```

### 3. AgentExecutor (执行引擎)

**文件**: `agio/execution/agent_executor.py`

**职责**:
1. **LLM ↔ Tool 循环**
   - 调用 Model.arun_stream()
   - 处理 StreamChunk
   - 管理 max_steps 限制

2. **Tool Call 处理**
   - 累加增量式 tool calls (ToolCallAccumulator)
   - 调用 ToolExecutor 执行
   - 将结果回写到 messages

3. **事件生成**
   - 直接生成所有 AgentEvent
   - TEXT_DELTA, TOOL_CALL_*, USAGE_UPDATE 等

**不负责**:
- ❌ Run 状态管理
- ❌ Hooks 调用
- ❌ Repository 持久化

```python
executor = AgentExecutor(model, tools, config)
async for event in executor.execute(messages, run_id):
    # event 是 AgentEvent
    handle(event)
```

### 4. Model (LLM 接口)

**文件**: `agio/models/openai.py`, `agio/models/base.py`

**职责**:
- 封装 LLM API 调用
- 返回标准化的 StreamChunk
- 处理错误和重试

**接口**:
```python
class Model(BaseModel):
    async def arun_stream(
        self, 
        messages: list[dict],
        tools: list[dict] | None = None
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(
            content="...",
            tool_calls=[...],
            usage={...},
            finish_reason="stop"
        )
```

---

## 🎯 事件系统

### AgentEvent 协议

**15 种事件类型**，覆盖完整的 Agent 生命周期：

```python
class EventType(str, Enum):
    # Run 级别
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    
    # Step 级别
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    
    # 流式输出
    TEXT_DELTA = "text_delta"
    TEXT_COMPLETED = "text_completed"
    
    # 工具调用
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_CALL_FAILED = "tool_call_failed"
    
    # Metrics
    USAGE_UPDATE = "usage_update"
    METRICS_SNAPSHOT = "metrics_snapshot"
    
    # 其他
    ERROR = "error"
    WARNING = "warning"
```

### 事件流示例

```python
async for event in agent.arun_stream("Hello"):
    match event.type:
        case EventType.RUN_STARTED:
            print("Run started")
        case EventType.TEXT_DELTA:
            print(event.data["content"], end="")
        case EventType.TOOL_CALL_STARTED:
            print(f"Calling {event.data['tool_name']}")
        case EventType.RUN_COMPLETED:
            print("Done!")
```

---

## 🔌 扩展点

### 1. 自定义 Model

```python
class CustomModel(Model):
    async def arun_stream(self, messages, tools):
        # 实现你的 LLM 调用逻辑
        yield StreamChunk(content="Hello")
```

### 2. 自定义 Tool

```python
class CustomTool(Tool):
    def execute(self, **kwargs):
        # 实现工具逻辑
        return result
```

### 3. 自定义 Repository

```python
class CustomRepository(AgentRunRepository):
    async def save_run(self, run):
        # 保存到你的存储
        pass
```

### 4. 自定义 Hook

```python
class CustomHook(AgentHook):
    async def on_run_start(self, run):
        # 在 Run 开始时执行
        pass
```

---

## 📊 与其他框架对比

| 特性 | Agio | LangChain | AutoGPT |
|------|------|-----------|---------|
| 异步原生 | ✅ 全链路异步 | ⚠️ 部分支持 | ❌ 同步为主 |
| 事件驱动 | ✅ 15种事件 | ❌ 无 | ❌ 无 |
| 类型安全 | ✅ Pydantic | ⚠️ 部分 | ❌ 弱类型 |
| 历史回放 | ✅ 完整支持 | ❌ 无 | ❌ 无 |
| 架构清晰度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 性能 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |

---

## 🚀 最佳实践

### 1. 使用事件流 API

推荐使用 `arun_stream()` 而不是 `arun()`，获得更好的控制：

```python
async for event in agent.arun_stream(query):
    if event.type == EventType.TEXT_DELTA:
        # 实时显示
        print(event.data["content"], end="")
    elif event.type == EventType.TOOL_CALL_STARTED:
        # 显示工具调用
        show_loading(event.data["tool_name"])
```

### 2. 配置 Repository 以支持历史回放

```python
agent = Agent(
    model=model,
    repository=PostgreSQLRepository(connection_string=...)
)

# 稍后回放
async for event in agent.get_run_history(run_id):
    replay(event)
```

### 3. 使用 Hooks 实现可观测性

```python
class MetricsHook(AgentHook):
    async def on_run_end(self, run):
        prometheus.record_duration(run.metrics.duration)
        prometheus.record_tokens(run.metrics.total_tokens)

agent = Agent(model=model, hooks=[MetricsHook()])
```

---

## 📖 相关文档

- [事件系统详解](event_system.md)
- [执行流程详解](execution_flow.md)
- [自定义扩展指南](../guides/custom_extensions.md)
- [API 参考](../api/)

---

**最后更新**: 2025-11-21  
**版本**: v0.4.0
