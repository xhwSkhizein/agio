# Agio Observability

完整的可观测性解决方案，支持 LLM 调用追踪和分布式 Trace。

## 功能特性

### 1. LLM Call Logging

追踪所有 LLM 调用的详细信息：

- 完整的请求/响应
- Token 使用统计
- 延迟指标
- 模型信息

### 2. Distributed Tracing

端到端的执行链路追踪：

- Agent → LLM/Tool 完整层级
- 瀑布图可视化
- 性能分析
- 错误追踪

### 3. OTLP Export

导出到 OpenTelemetry 兼容后端：

- ✅ Jaeger
- ✅ Zipkin
- ✅ SkyWalking
- ✅ 任何 OTLP 兼容后端

---

## 快速开始

### 安装依赖

```bash
# 基础功能
pip install motor  # MongoDB 支持

# OTLP 导出（可选）
pip install opentelemetry-exporter-otlp-proto-grpc
```

### 配置

在 `.env` 文件中：

```bash
# MongoDB（用于持久化）
AGIO_MONGO_URI=mongodb://localhost:27017

# OTLP 导出（可选）
AGIO_OTLP_ENABLED=true
AGIO_OTLP_ENDPOINT=http://localhost:4317
AGIO_OTLP_PROTOCOL=grpc
```

### 使用示例

```python
from agio.observability import TraceCollector, get_trace_store

# 初始化
store = await get_trace_store().initialize()
collector = TraceCollector(store=store)

# 包装事件流
async for event in collector.wrap_stream(
    event_stream,
    trace_id="trace_123",
    agent_id="my_agent",
    input_query="User query",
):
    yield event  # 事件透传，同时构建 Trace
```

---

## 架构设计

### 数据模型

```
Trace
├── trace_id
├── agent_id
├── session_id
├── start_time / end_time
├── status
└── spans[]
    ├── Span (AGENT)
    │   ├── Span (LLM_CALL)
    │   └── Span (TOOL_CALL)
    └── ...
```

### 组件

| 组件 | 职责 |
|------|------|
| `Trace/Span` | 数据模型 |
| `TraceCollector` | 从 StepEvent 流构建 Trace |
| `TraceStore` | MongoDB 持久化 + 内存缓存 |
| `OTLPExporter` | 导出到 OTLP 后端 |
| `traces.py` | REST API |

### 工作流程

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

---

## API 端点

### 查询 Trace 列表

```http
GET /api/traces?agent_id=xxx&limit=50
```

### 获取 Trace 详情

```http
GET /api/traces/{trace_id}
```

### 获取瀑布图数据

```http
GET /api/traces/{trace_id}/waterfall
```

### 实时订阅

```http
GET /api/traces/stream
```

---

## OTLP 导出

### 支持的后端

#### Jaeger

```bash
docker run -d -p 16686:16686 -p 4317:4317 \
  -e COLLECTOR_OTLP_ENABLED=true \
  jaegertracing/all-in-one:latest
```

配置：

```bash
AGIO_OTLP_ENDPOINT=http://localhost:4317
AGIO_OTLP_PROTOCOL=grpc
```

访问 UI：`http://localhost:16686`

#### Zipkin

```bash
docker run -d -p 9411:9411 openzipkin/zipkin:latest
```

配置：

```bash
AGIO_OTLP_ENDPOINT=http://localhost:9411/api/v2/spans
AGIO_OTLP_PROTOCOL=http
```

访问 UI：`http://localhost:9411`

#### SkyWalking

参见 [OTLP_SETUP.md](../../docs/OTLP_SETUP.md)

---

## Span 类型

| SpanKind | 说明 | OTLP 映射 |
|----------|------|-----------|
| AGENT | Agent 执行 | INTERNAL |
| LLM_CALL | LLM API 调用 | CLIENT |
| TOOL_CALL | Tool 执行 | CLIENT |

---

## 性能考虑

### 内存占用

- TraceStore 使用环形缓冲区（默认 200 条）
- 输入/输出预览截断到 500 字符
- 完整数据存储在 MongoDB

### 查询性能

MongoDB 索引：

- `trace_id` (unique)
- `start_time`
- `session_id`
- `status`
- `duration_ms`

### OTLP 导出

- 异步导出，不阻塞主流程
- 导出失败不影响 Trace 存储
- 建议生产环境使用采样

---

## 示例

### 运行示例

```bash
python examples/trace_example.py
```

### 查看输出

```
=== Agio Trace Example ===

1. Initializing TraceStore...
   ✓ TraceStore initialized (MongoDB: True)

2. Creating TraceCollector...
   ✓ TraceCollector created

3. Simulating agent execution...
   ✓ Generated 3 events

4. Collecting trace from events...
   - Event: run_started (trace_id=abc12345...)
   - Event: step_completed (trace_id=abc12345...)
   - Event: run_completed (trace_id=abc12345...)
   ✓ Collected 3 events

5. Querying trace from store...
   ✓ Trace found: abc12345-...
     - Status: ok
     - Duration: 1500.00ms
     - Spans: 2
     - Total tokens: 300
     - LLM calls: 1

     Span 1:
       - Kind: agent
       - Name: research_agent
       - Duration: 1500.00ms
       - Status: ok

     Span 2:
       - Kind: llm_call
       - Name: gpt-4o
       - Duration: 1500.00ms
       - Status: ok

6. Exporting to OTLP...
   ✓ Trace exported to http://localhost:4317

=== Example Complete ===
```

---

## 未来计划

- [ ] 前端瀑布图组件
- [ ] 采样策略配置
- [ ] BatchSpanProcessor
- [ ] Metrics 聚合
- [ ] 告警规则

---

## 参考文档

- [OBSERVABILITY.md](../../docs/OBSERVABILITY.md) - 完整设计方案
- [OTLP_SETUP.md](../../docs/OTLP_SETUP.md) - OTLP 配置指南
- [OpenTelemetry Specification](https://opentelemetry.io/docs/specs/otel/)
