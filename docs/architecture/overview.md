# Agio 架构设计

Agio 是一个**简洁、强大**的 Agent 框架，专注于核心功能：Agent 执行、事件流和可观测性。

## 设计哲学

**简单优于复杂**：Agio 主动移除了过度抽象（如 Runnable 协议、ConfigSystem），将重点放在实际需要的功能上。

**核心理念**：
- **Agent 优先**：Agent 是唯一的执行单元，不需要额外的抽象层
- **Wire 事件流**：所有执行通过 Wire 进行事件流式传输
- **直接编码**：通过代码直接创建和配置组件，而不是复杂的配置系统
- **组合能力**：通过 AgentTool 实现 Agent 嵌套和多 Agent 协作

---

## 核心架构

### 1. Wire-based 事件流

所有 Agent 执行都通过 `Wire` 进行事件流式传输：

```
API Entry Point
    │
    ├─► 创建 Wire
    │
    ├─► Agent.run_stream(input, wire=wire)
    │   └─► 写入 StepEvent 到 Wire
    │
    └─► API Layer 消费 Wire.read()
        └─► SSE 流式响应给前端
```

**Wire 特性**：
- **异步队列**：基于 asyncio.Queue 的事件通道
- **流式传输**：支持 SSE（Server-Sent Events）实时推送
- **嵌套共享**：嵌套执行（通过 AgentTool）共享同一个 Wire
- **生命周期管理**：自动处理 close 和清理

### 2. Agent 系统

**Agent 是唯一的执行单元**，负责：
- LLM 调用循环
- 工具执行
- 上下文管理
- 事件发射

**关键组件**：

```python
from agio import Agent, OpenAIModel

# 创建 Agent（直接代码配置）
agent = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    tools=[bash_tool, file_read_tool],
    session_store=session_store,
    name="my_agent",
    system_prompt="You are a helpful assistant.",
    max_steps=10,
)

# 运行 Agent（流式）
async for event in agent.run_stream("Hello!"):
    if event.type == "STEP_DELTA":
        print(event.delta.content)  # 增量内容
    elif event.type == "STEP_COMPLETED":
        print(event.snapshot.content)  # 完整步骤
```

### 3. Agent 嵌套：AgentTool

通过 `AgentTool` 将 Agent 包装为工具，实现多 Agent 协作：

```python
from agio import Agent, as_tool

# 创建专家 Agent
research_agent = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    name="research_agent",
    system_prompt="You are a research expert.",
)

# 转换为工具
research_tool = as_tool(
    research_agent,
    description="Expert at research tasks"
)

# 创建编排 Agent
orchestrator = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    tools=[research_tool],  # 使用 Agent 作为工具
    name="orchestrator",
)
```

**嵌套特性**：
- **Wire 共享**：嵌套执行共享父级的 Wire，所有事件统一流式传输
- **深度限制**：默认最多 5 层嵌套，防止无限递归
- **循环检测**：运行时检测循环引用（A → B → A）
- **上下文传递**：自动传递 session_id、trace_id、depth 等

---

## 系统架构图

```
┌─────────────────────────────────────────────────────┐
│              API Layer (FastAPI + SSE)              │
│  - RESTful API                                      │
│  - 流式事件推送 (SSE)                                │
│  - 会话管理                                          │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │         Agent                 │
        │  - run_stream()               │
        │  - Wire 事件发射               │
        └──────────┬────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌─────────┐
   │  LLM   │ │ Tools  │ │ Storage │
   │ Models │ │ System │ │ System  │
   └────────┘ └────────┘ └─────────┘
        │          │          │
        └──────────┼──────────┘
                   │
                   ▼
         ┌──────────────────────┐
         │   Runtime System     │
         │  - Wire (事件流)      │
         │  - ExecutionContext  │
         │  - StepPipeline      │
         │  - AgentExecutor     │
         └──────────┬───────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────┐
│ Traces  │  │ Sessions │  │Citations │
│  Store  │  │  Store   │  │  Store   │
└─────────┘  └──────────┘  └──────────┘
```

---

## 核心模块详解

### 1. Agent (agio/agent/agent.py)

**职责**：
- 执行 LLM 调用循环
- 管理工具执行
- 发射事件到 Wire
- 管理执行生命周期

**关键方法**：

```python
class Agent:
    async def run(
        self,
        user_input: str,
        *,
        context: ExecutionContext,
        pipeline: StepPipeline | None = None,
        abort_signal: AbortSignal | None = None,
    ) -> RunOutput:
        """
        执行 Agent（需要外部提供 context 和 wire）。
        用于嵌套调用（AgentTool）。
        """
        ...
    
    async def run_stream(
        self,
        user_input: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        trace_store: TraceStore | None = None,
    ) -> AsyncIterator[StepEvent]:
        """
        流式执行 Agent（自动创建 wire）。
        这是顶层执行的入口。
        """
        ...
```

### 2. AgentExecutor (agio/agent/executor.py)

**职责**：
- LLM 调用循环的核心逻辑
- 工具批量执行
- 终止摘要生成

**执行流程**：

```
while step_count < max_steps:
    1. 调用 LLM
       └─► 流式接收响应
       └─► 累积 Tool Calls
    
    2. 创建 Assistant Step
       └─► 流式写入 STEP_DELTA 事件（增量更新）
       └─► 写入 STEP_COMPLETED 事件（完整快照）
       └─► 保存到 SessionStore
    
    3. 检查是否有 Tool Calls
       ├─► 有 Tool Calls
       │   ├─► 批量执行工具
       │   ├─► 创建 Tool Steps
       │   └─► 将结果添加到消息列表
       └─► 无 Tool Calls
           └─► 退出循环
```

### 3. Wire (agio/runtime/wire.py)

**职责**：
- 事件流的异步队列
- 支持多消费者读取
- 自动处理关闭和清理

**使用方式**：

```python
from agio.runtime import Wire

# 创建 Wire
wire = Wire()

# 写入事件
await wire.write(event)

# 读取事件流
async for event in wire.read():
    print(event)

# 关闭 Wire
await wire.close()
```

### 4. AgentTool (agio/runtime/agent_tool.py)

**职责**：
- 将 Agent 包装为 BaseTool
- 管理嵌套执行上下文
- 防止无限递归和循环引用

**安全特性**：
- **深度限制**：默认最多 5 层嵌套
- **循环检测**：运行时检测 Agent 调用链中的循环
- **错误隔离**：嵌套 Agent 错误不会中断父 Agent

### 5. StepPipeline (agio/runtime/pipeline.py)

**职责**：
- 统一的 Step 处理管道
- 解耦执行逻辑与存储、可观测性、事件流
- 管理事件发射、步骤持久化、追踪收集

**关键方法**：
```python
class StepPipeline:
    async def emit_run_started(run: Run)  # 发射 RUN_STARTED 事件
    async def emit_step_delta(step_id: str, delta: StepDelta)  # 流式增量更新
    async def commit_step(step: Step)  # 提交完整步骤
    async def emit_run_completed(run: Run, output: RunOutput)  # 运行完成
    async def emit_run_failed(run: Run, error: Exception)  # 运行失败
```

**设计优势**：
- 单一职责：每个方法只做一件事
- 解耦关注点：存储、追踪、事件流互不干扰
- 易于测试：可以 mock 各个依赖

### 6. 可观测性 (agio/observability/)

**职责**：
- 收集执行追踪（Trace/Span）
- 支持 OTLP 导出
- 事件流监控

**关键组件**：
- `TraceCollector`: 事件流收集器，自动从 Wire 收集事件
- `TraceStore`: 追踪数据存储（MongoDB/In-Memory）
- `OTLPExporter`: 导出到 OpenTelemetry 后端

**使用方式**：

```python
from agio.observability import TraceCollector

# 创建 Collector
collector = TraceCollector(store=trace_store)

# 包装事件流
event_stream = collector.wrap_stream(
    agent.run_stream(input),
    agent_id="my_agent",
    session_id=session_id,
)

# 事件自动被收集到 TraceStore
async for event in event_stream:
    ...
```

### 7. 存储系统 (agio/storage/)

**SessionStore** - 存储会话、Run、Step：
- `MongoSessionStore`: MongoDB 实现
- `InMemorySessionStore`: 内存实现

**TraceStore** - 存储追踪数据：
- 用于可观测性和调试

**CitationStore** - 存储引用源：
- 用于 `web_search_api`、`web_reader_api` 等工具的源引用
- 支持引用溯源和内容验证

### 8. 工具系统 (agio/tools/)

**BaseTool** - 工具基类：
```python
class BaseTool(ABC):
    @abstractmethod
    def get_name(self) -> str: ...
    
    @abstractmethod
    def get_description(self) -> str: ...
    
    @abstractmethod
    def get_parameters(self) -> dict: ...
    
    @abstractmethod
    async def execute(
        self,
        parameters: dict,
        context: ExecutionContext,
        abort_signal: AbortSignal | None = None,
    ) -> ToolResult: ...
```

**内置工具**：
- `bash`: 执行 shell 命令
- `file_read`: 读取文件内容
- `file_write`: 写入文件
- `file_edit`: 编辑文件内容
- `grep`: 搜索文件内容（正则表达式）
- `glob`: 文件模式匹配
- `ls`: 列出目录内容
- `web_search_api`: 网页搜索（使用 Serper API）
- `web_reader_api`: 网页内容提取（使用 Jina Reader API）
- `get_tool_result`: 获取历史工具执行结果

**已弃用工具**：
- `web_search`: 已被 `web_search_api` 替代
- `web_fetch`: 已被 `web_reader_api` 替代

**工具注册表**：

```python
from agio.tools import get_tool_registry

# 获取工具注册表
registry = get_tool_registry()

# 获取工具实例
bash_tool = registry.create("bash")
```

---

## 执行流程详解

### 顶层执行（run_stream）

```python
# 用户代码
async for event in agent.run_stream("Hello!"):
    print(event)

# 内部流程
Agent.run_stream()
    ├─► 创建 Wire
    ├─► 创建 ExecutionContext
    ├─► 创建 StepPipeline
    ├─► 启动后台任务: Agent.run(context=ctx, pipeline=pipeline)
    ├─► 可选：TraceCollector 包装事件流
    └─► 流式返回 wire.read() 的事件
```

### 嵌套执行（AgentTool）

```python
# Orchestrator 调用 Research Agent
orchestrator = Agent(tools=[research_tool])

# 内部流程
OrchestratorAgentExecutor.execute()
    ├─► LLM 返回 tool_call: call_research_agent
    ├─► ToolExecutor 执行 research_tool
    │   └─► AgentTool.execute()
    │       ├─► 创建子 ExecutionContext (共享 wire)
    │       ├─► ResearchAgent.run(context=child_ctx)
    │       │   └─► 事件写入到同一个 wire
    │       └─► 返回 ToolResult
    └─► 继续 LLM 循环
```

**关键点**：
- 嵌套执行共享父级的 Wire
- 所有事件（包括嵌套 Agent 的）都发送到同一个 Wire
- 前端可以实时看到所有层级的执行过程

---

## 数据模型

### StepDelta - 增量更新

```python
class StepDelta:
    content: str | None  # 文本内容（追加）
    reasoning_content: str | None  # 推理内容（如 DeepSeek 思考模式）
    tool_calls: list[dict] | None  # 工具调用（追加/更新）
    usage: dict[str, int] | None  # Token 使用量
```

### StepEvent - 事件流

```python
class StepEvent:
    type: StepEventType  # 事件类型
    run_id: str
    timestamp: datetime
    
    # For STEP_DELTA and STEP_COMPLETED
    step_id: str | None
    delta: StepDelta | None  # 增量更新（STEP_DELTA）
    snapshot: Step | None  # 完整快照（STEP_COMPLETED）
    
    # For RUN_* and ERROR events
    data: dict | None
    
    # 嵌套上下文
    parent_run_id: str | None
    nested_runnable_id: str | None
    runnable_type: str | None
    runnable_id: str | None
    nesting_type: str | None
    
    # 嵌套深度
    depth: int  # 0 = 顶层执行
    
    # 可观测性
    trace_id: str | None
    span_id: str | None
    parent_span_id: str | None
```

**事件类型**：
- `RUN_STARTED`: Run 开始
- `STEP_DELTA`: Step 增量更新（流式传输）
- `STEP_COMPLETED`: Step 完成（最终快照）
- `RUN_COMPLETED`: Run 成功完成
- `RUN_FAILED`: Run 失败
- `ERROR`: 错误事件
- `TOOL_AUTH_REQUIRED`: 工具需要授权
- `TOOL_AUTH_DENIED`: 工具授权被拒绝

### Step - 执行步骤

```python
class Step:
    role: MessageRole  # USER, ASSISTANT, TOOL
    content: str | None
    tool_calls: list[dict] | None
    tool_call_id: str | None
    name: str | None
    metrics: StepMetrics | None
    runnable_id: str | None
    # ...
```

### RunOutput - 执行结果

```python
class RunOutput:
    response: str | None
    run_id: str | None
    session_id: str | None
    metrics: RunMetrics | None
    termination_reason: str | None  # "max_steps", "max_iterations" 等
    error: str | None
```

---

## 扩展性

### 添加新工具

1. 继承 `BaseTool`
2. 实现必需方法
3. 注册到工具注册表

```python
from agio.tools import BaseTool, get_tool_registry

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
        return ToolResult(...)

# 注册工具
registry = get_tool_registry()
registry.register("my_tool", MyTool())
```

### 添加新 LLM Provider

1. 继承 `Model` 基类
2. 实现必需方法
3. 直接使用或创建工厂函数

```python
from agio.llm import Model

class MyModel(Model):
    async def arun_stream(self, messages, tools=None):
        # 实现流式调用
        # 必须 yield 包含 delta 的 chunk
        ...

# 直接使用
my_model = MyModel(api_key="xxx", model_name="my-model")
agent = Agent(model=my_model, tools=[...])
```

---

## 设计决策

### 为什么移除 Runnable 协议？

**问题**：
- 过度抽象：Agent 是唯一需要执行的对象
- 增加复杂度：RunnableExecutor、RunnableAsTool 等额外层次
- 难以理解：用户需要理解多个抽象层

**解决方案**：
- Agent 直接作为执行单元
- AgentTool 提供 Agent 嵌套能力
- 代码更简洁，概念更清晰

### 为什么移除 ConfigSystem？

**问题**：
- 重量级：ConfigRegistry、ComponentContainer、DependencyResolver 等
- 不必要：大多数用户直接用代码创建 Agent 更简单
- 维护成本高：热重载、依赖解析等功能复杂

**解决方案**：
- 直接用代码创建 Agent 和工具
- 保留简单的配置模型（`schema.py`）供需要时使用
- 保留模板渲染（`template.py`）用于 system_prompt

### Wire 设计

**为什么选择 Wire？**
- 简单：基于 asyncio.Queue 的异步队列
- 强大：支持流式传输、嵌套共享
- 灵活：可以轻松添加事件过滤、转换等

---

## 相关文档

- [Agent 系统](./agent-system.md) - Agent 执行引擎详解
- [快速开始](../guides/quick-start.md) - 5 分钟快速上手
- [API 指南](../guides/api-guide.md) - RESTful API 和 SSE 接口
- [可观测性](./observability.md) - 追踪和监控
- [工具配置](../guides/tool-configuration.md) - 工具使用和扩展
- [工具权限](../development/tool-permissions.md) - 工具权限管理系统
