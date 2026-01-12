# 可观测性

Agio 提供完整的可观测性解决方案，支持分布式追踪、事件流收集和 OTLP 导出。

## 架构设计

```
StepEvent Stream
    │
    ▼
TraceCollector.wrap_stream()
    │
    ├─► 构建 Trace/Span
    ├─► 注入 trace_id/span_id
    └─► 保存到 TraceStore
          │
          ├─► MongoDB 持久化
          └─► OTLP 导出（可选）
```

## 核心组件

### TraceCollector

**职责**：从 StepEvent 流构建 Trace

```python
class TraceCollector:
    def __init__(self, store: TraceStore | None = None):
        ...
    
    async def wrap_stream(
        self,
        event_stream: AsyncIterator[StepEvent],
        trace_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        input_query: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        ...
```

**工作流程**：

1. **创建 Trace**：
   - 生成或使用提供的 `trace_id`
   - 设置 Trace 元数据（agent_id, session_id 等）

2. **处理事件流**：
   - 监听 `StepEvent` 事件
   - 根据事件类型创建/更新 Span
   - 注入 `trace_id` 和 `span_id` 到事件

3. **保存 Trace**：
   - 执行完成后保存到 TraceStore
   - 异步导出到 OTLP（如果启用）

### Trace 和 Span

**Trace**：完整的执行追踪

```python
class Trace(BaseModel):
    trace_id: str
    agent_id: str | None
    session_id: str | None
    user_id: str | None
    start_time: datetime
    end_time: datetime | None
    duration_ms: float | None
    status: SpanStatus
    root_span_id: str | None
    spans: list[Span]
    
    # 聚合指标
    total_tokens: int
    total_llm_calls: int
    total_tool_calls: int
    max_depth: int
    
    # 输入/输出
    input_query: str | None
    final_output: str | None
```

**Span**：执行单元（最小追踪单位）

```python
class Span(BaseModel):
    span_id: str
    trace_id: str
    parent_span_id: str | None
    
    # 类型和名称
    kind: SpanKind  # AGENT, LLM_CALL, TOOL_CALL
    name: str
    
    # 时间
    start_time: datetime
    end_time: datetime | None
    duration_ms: float | None
    
    # 状态
    status: SpanStatus  # RUNNING, OK, ERROR
    error_message: str | None
    
    # 层级
    depth: int
    
    # 上下文属性
    attributes: dict[str, Any]
    
    # 输入/输出预览
    input_preview: str | None  # 前 500 字符
    output_preview: str | None
    
    # 指标
    metrics: dict[str, Any]
    
    # 详细信息（LLM_CALL/TOOL_CALL）
    llm_details: dict[str, Any] | None
    tool_details: dict[str, Any] | None
```

### SpanKind

支持的 Span 类型：

- `AGENT`: Agent 执行 Span
- `LLM_CALL`: LLM API 调用 Span
- `TOOL_CALL`: Tool 执行 Span

### TraceStore

**职责**：Trace 数据存储和查询

```python
class TraceStore:
    def __init__(
        self,
        mongo_uri: str,
        db_name: str,
        ring_buffer_size: int = 200,
    ):
        ...
    
    async def initialize(self) -> None:
        """初始化 MongoDB 连接"""
    
    async def save_trace(self, trace: Trace) -> None:
        """保存 Trace 到 MongoDB"""
    
    async def get_trace(self, trace_id: str) -> Trace | None:
        """获取 Trace"""
    
    async def query_traces(self, query: TraceQuery) -> list[Trace]:
        """查询 Traces"""
```

**特点**：
- MongoDB 持久化
- 内存环形缓冲区（实时访问）
- 支持复杂查询（agent_id, session_id, status, 时间范围等）

### OTLPExporter

**职责**：导出 Trace 到 OpenTelemetry 兼容后端

```python
class OTLPExporter:
    def __init__(
        self,
        endpoint: str,
        protocol: str = "grpc",
        enabled: bool = True,
    ):
        ...
    
    async def export_trace(self, trace: Trace) -> None:
        """导出 Trace 到 OTLP 后端"""
```

**支持的后端**：
- Jaeger
- Zipkin
- SkyWalking
- 任何 OTLP 兼容后端

## 事件到 Span 映射

### RUN_STARTED 事件

**Agent（顶层）**：
```python
Span(
    kind=SpanKind.AGENT,
    name=agent_id,
    depth=0,
    attributes={
        "agent_id": agent_id,
    },
)
```

**Agent（嵌套）**：
```python
Span(
    kind=SpanKind.AGENT,
    name=nested_runnable_id,
    depth=parent.depth + 1,
    parent_span_id=parent.span_id,
    attributes={
        "agent_id": nested_runnable_id,
        "nested": True,
        "parent_run_id": parent_run_id,
    },
)
```

### STEP_COMPLETED 事件

**Assistant Step（LLM 调用）**：
```python
Span(
    kind=SpanKind.LLM_CALL,
    name=model_id,
    depth=parent.depth + 1,
    parent_span_id=parent.span_id,
    attributes={
        "model_id": model_id,
        "agent_id": agent_id,
    },
    metrics={
        "tokens.input": input_tokens,
        "tokens.output": output_tokens,
        "tokens.total": total_tokens,
    },
    llm_details={
        "request": {...},
        "messages": [...],
        "response_content": "...",
        "tool_calls": [...],
    },
)
```

**Tool Step（工具调用）**：
```python
Span(
    kind=SpanKind.TOOL_CALL,
    name=tool_name,
    depth=parent.depth + 1,
    parent_span_id=parent.span_id,
    attributes={
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
    },
    tool_details={
        "tool_name": tool_name,
        "input_args": {...},
        "output": "...",
        "error": "...",
    },
)
```

## 使用方式

### 基本使用

```python
from agio.observability import TraceCollector, TraceStore

# 初始化 TraceStore
store = TraceStore(
    mongo_uri="mongodb://localhost:27017",
    db_name="agio",
)
await store.initialize()

# 创建 TraceCollector
collector = TraceCollector(store=store)

# 包装事件流
async for event in collector.wrap_stream(
    event_stream,
    trace_id="trace_123",
    agent_id="research_agent",
    input_query="Research AI trends",
):
    yield event  # 事件透传，同时构建 Trace
```

### 在 API 中使用

```python
from agio.observability import create_collector

# 创建 Collector
collector = create_collector()

# 包装事件流
event_stream = wire.read()
traced_stream = collector.wrap_stream(
    event_stream,
    trace_id=trace_id,
    agent_id=agent_id,
    session_id=session_id,
    input_query=query,
)

# SSE 响应
async for event in traced_stream:
    yield f"data: {event.json()}\n\n"
```

### 查询 Traces

```python
from agio.observability import TraceQuery, TraceStore

store = TraceStore(...)

# 查询特定 Agent 的 Traces
query = TraceQuery(
    agent_id="research_agent",
    limit=50,
)
traces = await store.query_traces(query)

# 查询特定时间范围的 Traces
query = TraceQuery(
    start_time=datetime(2024, 1, 1),
    end_time=datetime(2024, 1, 31),
    min_duration_ms=1000,
)
traces = await store.query_traces(query)
```

## OTLP 导出

### 配置

```bash
# .env
AGIO_OTLP_ENABLED=true
AGIO_OTLP_ENDPOINT=http://localhost:4317
AGIO_OTLP_PROTOCOL=grpc
```

### Jaeger

```bash
# 启动 Jaeger
docker run -d -p 16686:16686 -p 4317:4317 \
  -e COLLECTOR_OTLP_ENABLED=true \
  jaegertracing/all-in-one:latest

# 配置
AGIO_OTLP_ENDPOINT=http://localhost:4317
AGIO_OTLP_PROTOCOL=grpc

# 访问 UI
http://localhost:16686
```

### Zipkin

```bash
# 启动 Zipkin
docker run -d -p 9411:9411 openzipkin/zipkin:latest

# 配置
AGIO_OTLP_ENDPOINT=http://localhost:9411/api/v2/spans
AGIO_OTLP_PROTOCOL=http

# 访问 UI
http://localhost:9411
```

## API 端点

### 查询 Trace 列表

```http
GET /agio/traces?agent_id=xxx&limit=50
```

**查询参数**：
- `agent_id`: Agent ID
- `session_id`: Session ID
- `status`: 状态（running, ok, error）
- `start_time`: 开始时间
- `end_time`: 结束时间
- `min_duration_ms`: 最小持续时间
- `limit`: 返回数量限制

### 获取 Trace 详情

```http
GET /agio/traces/{trace_id}
```

### 获取瀑布图数据

```http
GET /agio/traces/{trace_id}/waterfall
```

返回格式：
```json
{
  "spans": [
    {
      "span_id": "...",
      "name": "...",
      "kind": "AGENT|LLM_CALL|TOOL_CALL",
      "start_time": "...",
      "duration_ms": 123.45,
      "parent_span_id": "...",
      "depth": 0,
      ...
    }
  ]
}
```

### 实时订阅

```http
GET /agio/traces/stream
```

Server-Sent Events (SSE) 流，实时推送新的 Trace。

## 性能考虑

### 内存占用

- TraceStore 使用环形缓冲区（默认 200 条）
- 输入/输出预览截断到 500 字符
- 完整数据存储在 MongoDB

### 查询性能

MongoDB 索引：
- `trace_id` (unique)
- `start_time`
- `agent_id`
- `session_id`
- `status`
- `duration_ms`

### OTLP 导出

- 异步导出，不阻塞主流程
- 导出失败不影响 Trace 存储
- 建议生产环境使用采样

## 最佳实践

1. **Trace ID 生成**：使用 UUID 确保唯一性
2. **Span 命名**：使用有意义的名称（agent_id, tool_name）
3. **属性设置**：设置必要的上下文属性（agent_id, session_id 等）
4. **错误处理**：正确设置 `status=ERROR` 和 `error_message`
5. **性能监控**：关注 `duration_ms` 和 Token 使用
6. **采样策略**：生产环境使用采样，避免过多 Trace

## 相关代码

- `agio/observability/trace.py`: Trace 和 Span 模型
- `agio/observability/collector.py`: TraceCollector
- `agio/observability/trace_store.py`: TraceStore
- `agio/observability/otlp_exporter.py`: OTLPExporter
- `agio/api/routes/traces.py`: Trace API 路由

