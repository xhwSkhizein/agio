# Agio 可观测性设计方案：Trace/Span

> 版本: v1.0  
> 日期: 2024-12-05  
> 状态: Draft

## 目录

1. [概述与目标](#1-概述与目标)
2. [现有系统分析](#2-现有系统分析)
3. [Trace/Span 数据模型](#3-tracespan-数据模型)
4. [TraceCollector 实现](#4-tracecollector-实现)
5. [TraceStore 持久化](#5-tracestore-持久化)
6. [API 设计](#6-api-设计)
7. [前端可视化](#7-前端可视化)
8. [实施计划](#8-实施计划)

---

## 1. 概述与目标

### 1.1 背景

Agio 系统已支持单 Agent 和多 Agent Workflow 协作执行。现有 `observability` 模块提供了 LLM 调用级别的追踪（`LLMCallLog`），但缺乏完整的分布式追踪能力来可视化 Workflow → Agent → LLM/Tool 的完整执行链路。

### 1.2 目标

| 目标 | 说明 |
|------|------|
| **端到端追踪** | 从 Workflow 顶层到每个 LLM/Tool 调用的完整执行链路 |
| **层级可视化** | 瀑布图展示 Workflow → Stage → Agent → LLM/Tool 层级关系 |
| **性能分析** | 每个 Span 的耗时、Token 使用、延迟分布 |
| **问题排查** | 快速定位执行失败节点和错误详情 |
| **无侵入集成** | 通过中间件模式收集追踪，不修改核心执行逻辑 |

### 1.3 设计原则

- **OpenTelemetry 兼容** - 数据模型参考 OTEL 标准，便于后续对接外部 APM
- **与 LLMCallLog 整合** - 复用现有 LLM 追踪能力，避免重复记录
- **最小存储开销** - 只存储摘要和元数据，完整数据在 Step/LLMCallLog 中
- **实时流式** - 支持 SSE 实时推送追踪事件

---

## 2. 现有系统分析

### 2.1 已有基础设施

#### StepEvent 预留字段

```python
# agio/domain/events.py
class StepEvent(BaseModel):
    # ... 核心字段 ...
    
    # 可观测性预留（已存在）
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    depth: int = 0
```

#### Step/AgentRun 预留字段

```python
# agio/domain/models.py
class Step(BaseModel):
    # ... 核心字段 ...
    
    # 可观测性字段（已存在）
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    depth: int = 0

class AgentRun(BaseModel):
    # ...
    trace_id: str | None = None  # 已存在
```

#### LLMCallLog

```python
# agio/observability/models.py
class LLMCallLog(BaseModel):
    id: str
    agent_name: str | None
    session_id: str | None
    run_id: str | None
    model_id: str
    provider: str
    
    # 请求/响应
    request: dict
    messages: list[dict]
    response_content: str | None
    response_tool_calls: list[dict] | None
    
    # 性能指标
    duration_ms: float | None
    first_token_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
```

### 2.2 缺失能力

| 缺失 | 影响 |
|------|------|
| Trace/Span 模型 | 无法表示层级执行关系 |
| TraceCollector | 无法从事件流构建追踪 |
| TraceStore | 无法持久化和查询追踪 |
| 瀑布图 API | 前端无法获取可视化数据 |
| 前端组件 | 无法展示执行时间线 |

### 2.3 执行层级示意

```
Workflow Run (Trace)
├── Stage: intent (Span)
│   └── Agent: intent_agent (Span)
│       └── LLM Call (Span) → 关联 LLMCallLog
│
├── Stage: research (Span)
│   └── Agent: research_agent (Span)
│       ├── LLM Call (Span)
│       └── Tool: web_search (Span)
│           └── Sub-Agent (Span)  // Agent as Tool
│               └── LLM Call (Span)
│
└── Stage: summary (Span)
    └── Agent: summary_agent (Span)
        └── LLM Call (Span)
```

---

## 3. Trace/Span 数据模型

### 3.1 核心模型

```python
# agio/observability/trace.py

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class SpanKind(str, Enum):
    """Span 类型"""
    WORKFLOW = "workflow"      # Workflow 顶层
    STAGE = "stage"           # Workflow Stage
    AGENT = "agent"           # Agent 执行
    LLM_CALL = "llm_call"     # LLM 调用
    TOOL_CALL = "tool_call"   # Tool 调用


class SpanStatus(str, Enum):
    """Span 状态"""
    UNSET = "unset"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"


class Span(BaseModel):
    """
    执行跨度 - 分布式追踪最小单元
    
    设计参考 OpenTelemetry Span 规范，简化为 Agio 场景所需字段。
    """
    
    # === 标识 ===
    span_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str  # 所属 Trace ID
    parent_span_id: str | None = None  # 父 Span ID
    
    # === 类型与名称 ===
    kind: SpanKind
    name: str  # 可读名称，如 "research_agent", "web_search"
    
    # === 时间 ===
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    end_time: datetime | None = None
    duration_ms: float | None = None
    
    # === 状态 ===
    status: SpanStatus = SpanStatus.RUNNING
    error_message: str | None = None
    
    # === 层级 ===
    depth: int = 0  # 嵌套深度
    
    # === 上下文属性 ===
    attributes: dict[str, Any] = Field(default_factory=dict)
    # 常用属性:
    # - workflow_id: Workflow ID
    # - stage_id: Stage ID
    # - agent_id: Agent ID
    # - model_id: LLM 模型 ID
    # - tool_name: Tool 名称
    # - iteration: Loop 迭代次数
    # - branch_id: Parallel 分支 ID
    
    # === 输入输出摘要 ===
    input_preview: str | None = None   # 输入前 500 字符
    output_preview: str | None = None  # 输出前 500 字符
    
    # === 指标 ===
    metrics: dict[str, Any] = Field(default_factory=dict)
    # 常用指标:
    # - tokens.input: 输入 Token 数
    # - tokens.output: 输出 Token 数
    # - tokens.total: 总 Token 数
    # - first_token_ms: 首 Token 延迟
    
    # === 关联 ===
    llm_log_id: str | None = None  # 关联的 LLMCallLog ID
    run_id: str | None = None       # 关联的 AgentRun ID
    step_id: str | None = None      # 关联的 Step ID
    
    def complete(
        self, 
        status: SpanStatus = SpanStatus.OK,
        error_message: str | None = None,
        output_preview: str | None = None,
    ):
        """完成 Span"""
        self.end_time = datetime.now(timezone.utc)
        self.status = status
        self.error_message = error_message
        self.output_preview = output_preview
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            self.duration_ms = delta.total_seconds() * 1000


class Trace(BaseModel):
    """
    完整执行追踪
    
    一个 Trace 包含一次完整的用户请求处理过程，
    可能是单个 Agent Run 或完整的 Workflow 执行。
    """
    
    # === 标识 ===
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    
    # === 上下文 ===
    workflow_id: str | None = None  # Workflow ID（如果是 Workflow 执行）
    agent_id: str | None = None     # Agent ID（如果是单 Agent 执行）
    session_id: str | None = None
    user_id: str | None = None
    
    # === 时间 ===
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    end_time: datetime | None = None
    duration_ms: float | None = None
    
    # === 状态 ===
    status: SpanStatus = SpanStatus.RUNNING
    
    # === Span 列表 ===
    root_span_id: str | None = None
    spans: list[Span] = Field(default_factory=list)
    
    # === 聚合指标 ===
    total_tokens: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    max_depth: int = 0
    
    # === 输入输出 ===
    input_query: str | None = None
    final_output: str | None = None
    
    def add_span(self, span: Span):
        """添加 Span"""
        self.spans.append(span)
        self.max_depth = max(self.max_depth, span.depth)
        
        # 更新聚合指标
        if span.kind == SpanKind.LLM_CALL:
            self.total_llm_calls += 1
            if "tokens.total" in span.metrics:
                self.total_tokens += span.metrics["tokens.total"]
        elif span.kind == SpanKind.TOOL_CALL:
            self.total_tool_calls += 1
    
    def complete(
        self,
        status: SpanStatus = SpanStatus.OK,
        final_output: str | None = None,
    ):
        """完成 Trace"""
        self.end_time = datetime.now(timezone.utc)
        self.status = status
        self.final_output = final_output
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            self.duration_ms = delta.total_seconds() * 1000
```

### 3.2 模型关系图

```
┌─────────────────────────────────────────────────────────────────────┐
│                              Trace                                   │
│  trace_id, workflow_id, session_id, user_id                         │
│  start_time, end_time, duration_ms, status                          │
│  total_tokens, total_llm_calls, total_tool_calls                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Span (kind=WORKFLOW)                                         │   │
│  │  span_id, trace_id, parent_span_id=None, depth=0             │   │
│  │  name="research_pipeline"                                     │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │                                                               │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  Span (kind=STAGE)                                      │  │   │
│  │  │  span_id, parent_span_id=workflow, depth=1              │  │   │
│  │  │  name="intent", attributes={stage_id: "intent"}         │  │   │
│  │  ├────────────────────────────────────────────────────────┤  │   │
│  │  │                                                         │  │   │
│  │  │  ┌──────────────────────────────────────────────────┐  │  │   │
│  │  │  │  Span (kind=AGENT)                                │  │  │   │
│  │  │  │  name="intent_agent", depth=2                     │  │  │   │
│  │  │  ├──────────────────────────────────────────────────┤  │  │   │
│  │  │  │                                                   │  │  │   │
│  │  │  │  ┌────────────────────────────────────────────┐  │  │  │   │
│  │  │  │  │  Span (kind=LLM_CALL)                       │  │  │   │
│  │  │  │  │  name="gpt-4o", depth=3                     │  │  │   │
│  │  │  │  │  llm_log_id="xxx" ──────┐                   │  │  │   │
│  │  │  │  │  metrics={tokens: 150}  │                   │  │  │   │
│  │  │  │  └─────────────────────────│───────────────────┘  │  │   │
│  │  │  │                            ▼                      │  │   │
│  │  │  └──────────────────────  LLMCallLog ────────────────┘  │   │
│  │  │                                                         │   │
│  │  └─────────────────────────────────────────────────────────┘   │
│  │                                                               │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. TraceCollector 实现

### 4.1 设计思路

TraceCollector 采用**中间件模式**，包装 StepEvent 流，从事件中自动构建 Trace/Span 结构，不侵入核心执行逻辑。

```
┌─────────────────────────────────────────────────────────────────┐
│                        执行引擎                                   │
│                                                                  │
│   Workflow/Agent ──► StepEvent Stream                           │
│                            │                                     │
│                            ▼                                     │
│                   ┌────────────────┐                            │
│                   │ TraceCollector │  ◄── 中间件                │
│                   │   wrap_stream  │                            │
│                   └───────┬────────┘                            │
│                           │                                      │
│           ┌───────────────┼───────────────┐                     │
│           ▼               ▼               ▼                     │
│      StepEvent       构建 Trace     持久化到 Store              │
│      (透传)         (内部处理)                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 事件到 Span 映射

| StepEvent Type | Span 操作 | SpanKind |
|----------------|-----------|----------|
| `RUN_STARTED` (workflow) | 创建 Trace + WORKFLOW Span | WORKFLOW |
| `RUN_STARTED` (agent) | 创建 AGENT Span | AGENT |
| `STAGE_STARTED` | 创建 STAGE Span | STAGE |
| `STAGE_COMPLETED` | 完成 STAGE Span | - |
| `STAGE_SKIPPED` | 创建并立即完成 STAGE Span (status=skipped) | STAGE |
| `STEP_COMPLETED` (assistant) | 创建 LLM_CALL Span | LLM_CALL |
| `STEP_COMPLETED` (tool) | 创建 TOOL_CALL Span | TOOL_CALL |
| `RUN_COMPLETED` | 完成当前 Span | - |
| `RUN_FAILED` | 完成当前 Span (status=ERROR) | - |
| `ITERATION_STARTED` | 更新 attributes.iteration | - |
| `BRANCH_STARTED` | 创建 Span (with branch_id) | STAGE |
| `BRANCH_COMPLETED` | 完成分支 Span | - |

### 4.3 实现代码

```python
# agio/observability/collector.py

from typing import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from agio.domain.events import StepEvent, StepEventType
from agio.observability.trace import Trace, Span, SpanKind, SpanStatus
from agio.observability.store import TraceStore


class TraceCollector:
    """
    追踪收集器 - 从 StepEvent 流中构建 Trace
    
    使用方式:
        collector = TraceCollector(store)
        
        async for event in collector.wrap_stream(event_stream):
            yield event  # 事件透传，同时构建 Trace
    """
    
    PREVIEW_LENGTH = 500  # 输入/输出预览长度
    
    def __init__(self, store: TraceStore | None = None):
        self.store = store
    
    async def wrap_stream(
        self,
        event_stream: AsyncIterator[StepEvent],
        trace_id: str | None = None,
        workflow_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        input_query: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        """
        包装事件流，自动收集追踪信息
        
        Args:
            event_stream: 原始事件流
            trace_id: 可选，指定 Trace ID
            workflow_id: Workflow ID（如果是 Workflow 执行）
            agent_id: Agent ID（如果是单 Agent 执行）
            session_id: Session ID
            user_id: User ID
            input_query: 用户输入
            
        Yields:
            StepEvent: 透传原始事件，注入 trace_id/span_id
            
        注意：
        - 嵌套事件（nested_runnable_id 不为 None）会被跳过处理，因为它们已有自己的追踪上下文
        - 事件会被透传，同时构建 Trace
        """
        # 初始化 Trace
        trace = Trace(
            trace_id=trace_id or str(uuid4()),
            workflow_id=workflow_id,
            agent_id=agent_id,
            session_id=session_id,
            user_id=user_id,
            input_query=input_query,
        )
        
        # Span 栈：追踪当前活跃的 Span 层级
        span_stack: dict[str, Span] = {}  # key: run_id 或 stage_id
        current_span: Span | None = None
        
        try:
            async for event in event_stream:
                # 跳过嵌套事件的处理（它们已有自己的追踪上下文）
                # 但仍需透传以支持实时流式输出
                if event.nested_runnable_id:
                    yield event
                    continue
                
                # 处理事件，更新 Trace
                current_span = self._process_event(
                    event, trace, span_stack, current_span
                )
                
                # 注入追踪字段到事件
                event.trace_id = trace.trace_id
                if current_span:
                    event.span_id = current_span.span_id
                    event.parent_span_id = current_span.parent_span_id
                
                yield event
                
        except Exception as e:
            # 异常时标记 Trace 失败
            trace.complete(status=SpanStatus.ERROR)
            if current_span:
                current_span.complete(
                    status=SpanStatus.ERROR,
                    error_message=str(e),
                )
            raise
        finally:
            # 保存 Trace
            if not trace.end_time:
                trace.complete(status=SpanStatus.OK)
            
            if self.store:
                try:
                    await self.store.save_trace(trace)
                except Exception as e:
                    logger.error("trace_save_failed", trace_id=trace.trace_id, error=str(e))
            
            # 导出到 OTLP（异步，非阻塞）
            try:
                from agio.observability import get_otlp_exporter
                exporter = get_otlp_exporter()
                if exporter.enabled:
                    await exporter.export_trace(trace)
            except Exception as e:
                logger.warning("otlp_export_failed", trace_id=trace.trace_id, error=str(e))
    
    def _process_event(
        self,
        event: StepEvent,
        trace: Trace,
        span_stack: dict[str, Span],
        current_span: Span | None,
    ) -> Span | None:
        """处理单个事件，返回当前活跃的 Span"""
        
        event_type = event.type
        
        # === RUN_STARTED ===
        if event_type == StepEventType.RUN_STARTED:
            data = event.data or {}
            
            # 判断是 Workflow 还是 Agent
            if data.get("workflow_id") or data.get("type") in ("pipeline", "loop", "parallel"):
                # Workflow 顶层 Span
                span = Span(
                    trace_id=trace.trace_id,
                    kind=SpanKind.WORKFLOW,
                    name=data.get("workflow_id", "workflow"),
                    depth=0,
                    attributes={
                        "workflow_id": data.get("workflow_id"),
                        "workflow_type": data.get("type"),
                    },
                    input_preview=trace.input_query[:self.PREVIEW_LENGTH] 
                        if trace.input_query else None,
                )
                trace.root_span_id = span.span_id
            else:
                # Agent Span
                parent = current_span
                span = Span(
                    trace_id=trace.trace_id,
                    parent_span_id=parent.span_id if parent else None,
                    kind=SpanKind.AGENT,
                    name=data.get("agent_id", "agent"),
                    depth=(parent.depth + 1) if parent else 0,
                    attributes={
                        "agent_id": data.get("agent_id"),
                        "session_id": event.data.get("session_id"),
                    },
                )
                if not trace.root_span_id:
                    trace.root_span_id = span.span_id
            
            trace.add_span(span)
            span_stack[event.run_id] = span
            return span
        
        # === STAGE_STARTED ===
        elif event_type == StepEventType.STAGE_STARTED:
            parent = span_stack.get(event.run_id) or current_span
            span = Span(
                trace_id=trace.trace_id,
                parent_span_id=parent.span_id if parent else None,
                kind=SpanKind.STAGE,
                name=event.stage_id or "stage",
                depth=(parent.depth + 1) if parent else 1,
                attributes={
                    "stage_id": event.stage_id,
                    "iteration": event.iteration,
                },
            )
            trace.add_span(span)
            span_stack[f"stage:{event.stage_id}"] = span
            return span
        
        # === STAGE_COMPLETED ===
        elif event_type == StepEventType.STAGE_COMPLETED:
            span = span_stack.get(f"stage:{event.stage_id}")
            if span:
                output_len = event.data.get("output_length") if event.data else None
                span.complete(
                    status=SpanStatus.OK,
                    output_preview=f"[{output_len} chars]" if output_len else None,
                )
            return span_stack.get(event.run_id) or current_span
        
        # === STAGE_SKIPPED ===
        elif event_type == StepEventType.STAGE_SKIPPED:
            parent = span_stack.get(event.run_id) or current_span
            span = Span(
                trace_id=trace.trace_id,
                parent_span_id=parent.span_id if parent else None,
                kind=SpanKind.STAGE,
                name=event.stage_id or "stage",
                depth=(parent.depth + 1) if parent else 1,
                attributes={
                    "stage_id": event.stage_id,
                    "skipped": True,
                    "condition": event.data.get("condition") if event.data else None,
                },
            )
            span.complete(status=SpanStatus.OK)  # skipped 也是成功状态
            trace.add_span(span)
            return current_span
        
        # === STEP_COMPLETED ===
        elif event_type == StepEventType.STEP_COMPLETED:
            if not event.snapshot:
                return current_span
            
            step = event.snapshot
            parent = current_span
            
            if step.role.value == "tool":
                # Tool 调用 Span
                span = Span(
                    trace_id=trace.trace_id,
                    parent_span_id=parent.span_id if parent else None,
                    kind=SpanKind.TOOL_CALL,
                    name=step.name or "tool",
                    depth=(parent.depth + 1) if parent else 0,
                    attributes={
                        "tool_name": step.name,
                        "tool_call_id": step.tool_call_id,
                    },
                    step_id=step.id,
                    run_id=step.run_id,
                )
                if step.metrics:
                    span.duration_ms = step.metrics.tool_exec_time_ms
                span.complete(status=SpanStatus.OK)
                
            elif step.role.value == "assistant":
                # LLM 调用 Span
                from datetime import datetime, timezone, timedelta
                
                # 计算真实的开始时间（根据 duration 反推）
                end_time = datetime.now(timezone.utc)
                duration_ms = step.metrics.duration_ms if step.metrics else None
                if duration_ms is not None:
                    start_time = end_time - timedelta(milliseconds=duration_ms)
                else:
                    start_time = end_time
                
                span = Span(
                    trace_id=trace.trace_id,
                    parent_span_id=parent.span_id if parent else None,
                    kind=SpanKind.LLM_CALL,
                    name=step.metrics.model_name if step.metrics else "llm",
                    depth=(parent.depth + 1) if parent else 0,
                    attributes={
                        "model_name": step.metrics.model_name if step.metrics else None,
                        "provider": step.metrics.provider if step.metrics else None,
                        "has_tool_calls": bool(step.tool_calls),
                    },
                    step_id=step.id,
                    run_id=step.run_id,
                    output_preview=step.content[:self.PREVIEW_LENGTH] 
                        if step.content else None,
                )
                span.start_time = start_time
                span.end_time = end_time
                span.duration_ms = duration_ms or 0
                span.status = SpanStatus.OK
                
                if step.metrics:
                    span.metrics = {
                        "tokens.input": step.metrics.input_tokens,
                        "tokens.output": step.metrics.output_tokens,
                        "tokens.total": step.metrics.total_tokens,
                        "first_token_ms": step.metrics.first_token_latency_ms,
                    }
            else:
                return current_span
            
            trace.add_span(span)
            return current_span
        
        # === RUN_COMPLETED ===
        elif event_type == StepEventType.RUN_COMPLETED:
            span = span_stack.get(event.run_id)
            if span:
                response = event.data.get("response") if event.data else None
                span.complete(
                    status=SpanStatus.OK,
                    output_preview=response[:self.PREVIEW_LENGTH] if response else None,
                )
                trace.final_output = response
            return span_stack.get(event.run_id)
        
        # === RUN_FAILED ===
        elif event_type == StepEventType.RUN_FAILED:
            span = span_stack.get(event.run_id)
            if span:
                error = event.data.get("error") if event.data else "Unknown error"
                span.complete(status=SpanStatus.ERROR, error_message=error)
            return span_stack.get(event.run_id)
        
        # === ITERATION_STARTED ===
        elif event_type == StepEventType.ITERATION_STARTED:
            # 更新当前 Workflow Span 的迭代次数
            span = span_stack.get(event.run_id)
            if span:
                span.attributes["current_iteration"] = event.iteration
            return current_span
        
        # === BRANCH_STARTED ===
        elif event_type == StepEventType.BRANCH_STARTED:
            parent = span_stack.get(event.run_id) or current_span
            span = Span(
                trace_id=trace.trace_id,
                parent_span_id=parent.span_id if parent else None,
                kind=SpanKind.STAGE,
                name=f"branch:{event.branch_id}",
                depth=(parent.depth + 1) if parent else 1,
                attributes={
                    "branch_id": event.branch_id,
                    "parallel": True,
                },
            )
            trace.add_span(span)
            span_stack[f"branch:{event.branch_id}"] = span
            return span
        
        # === BRANCH_COMPLETED ===
        elif event_type == StepEventType.BRANCH_COMPLETED:
            span = span_stack.get(f"branch:{event.branch_id}")
            if span:
                span.complete(status=SpanStatus.OK)
            return span_stack.get(event.run_id) or current_span
        
        return current_span


# 便捷函数
def create_collector(store: TraceStore | None = None) -> TraceCollector:
    """创建 TraceCollector 实例"""
    return TraceCollector(store)
```

### 4.4 与现有 LLMCallTracker 整合

现有 `LLMCallTracker` 追踪 LLM 调用级别详情，`TraceCollector` 追踪完整执行链路。两者通过 `llm_log_id` 关联：

```python
# 在 LLMCallTracker._track_call 中添加 trace 上下文
log = LLMCallLog(
    id=str(uuid4()),
    # ... 现有字段 ...
    
    # 新增：追踪关联
    trace_id=_current_trace_id.get(),    # 从 context var 获取
    span_id=_current_span_id.get(),
)

# 在 Span 中记录关联
span.llm_log_id = log.id
```

---

## 5. TraceStore 持久化

### 5.1 存储设计

与现有 `LLMLogStore` 保持一致的设计模式：

```python
# agio/observability/trace_store.py

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any

from agio.observability.trace import Trace, Span, SpanStatus
from agio.utils.logging import get_logger

logger = get_logger(__name__)

# Global store instance
_trace_store: "TraceStore | None" = None


class TraceQuery(BaseModel):
    """Trace 查询参数"""
    
    workflow_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    status: SpanStatus | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    min_duration_ms: float | None = None
    max_duration_ms: float | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class TraceStore:
    """
    Trace 存储 - MongoDB 持久化 + 内存缓存
    
    特性:
    - 异步 MongoDB 操作
    - 内存环形缓冲区用于实时访问
    - SSE 订阅者支持
    """
    
    def __init__(
        self,
        mongo_uri: str | None = None,
        db_name: str = "agio",
        collection_name: str = "traces",
        buffer_size: int = 200,
    ):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.buffer_size = buffer_size
        
        # 内存环形缓冲区
        self._buffer: deque[Trace] = deque(maxlen=buffer_size)
        
        # SSE 订阅者
        self._subscribers: list[asyncio.Queue] = []
        
        # MongoDB 客户端（延迟初始化）
        self._client = None
        self._collection = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """初始化 MongoDB 连接"""
        if self._initialized:
            return
        
        if self.mongo_uri:
            try:
                from motor.motor_asyncio import AsyncIOMotorClient
                
                self._client = AsyncIOMotorClient(self.mongo_uri)
                db = self._client[self.db_name]
                self._collection = db[self.collection_name]
                
                # 创建索引
                await self._collection.create_index("trace_id", unique=True)
                await self._collection.create_index("start_time")
                await self._collection.create_index("workflow_id")
                await self._collection.create_index("agent_id")
                await self._collection.create_index("session_id")
                await self._collection.create_index("status")
                await self._collection.create_index("duration_ms")
                
                logger.info(
                    "trace_store_initialized",
                    db=self.db_name,
                    collection=self.collection_name,
                )
            except ImportError:
                logger.warning(
                    "motor_not_installed",
                    message="MongoDB tracing disabled. Install motor.",
                )
            except Exception as e:
                logger.error("trace_store_init_failed", error=str(e))
        
        self._initialized = True
    
    async def save_trace(self, trace: Trace) -> None:
        """保存 Trace"""
        # 添加到缓冲区
        self._buffer.append(trace)
        
        # 持久化到 MongoDB
        if self._collection is not None:
            try:
                doc = trace.model_dump(mode="json")
                await self._collection.replace_one(
                    {"trace_id": trace.trace_id},
                    doc,
                    upsert=True,
                )
            except Exception as e:
                logger.error(
                    "trace_persist_failed",
                    trace_id=trace.trace_id,
                    error=str(e),
                )
        
        # 通知订阅者
        await self._notify_subscribers(trace)
    
    async def get_trace(self, trace_id: str) -> Trace | None:
        """获取单个 Trace"""
        # 先查缓冲区
        for trace in self._buffer:
            if trace.trace_id == trace_id:
                return trace
        
        # 再查 MongoDB
        if self._collection is not None:
            try:
                doc = await self._collection.find_one({"trace_id": trace_id})
                if doc:
                    return Trace(**doc)
            except Exception as e:
                logger.error("trace_get_failed", trace_id=trace_id, error=str(e))
        
        return None
    
    async def query_traces(self, query: TraceQuery) -> list[Trace]:
        """查询 Traces"""
        mongo_query: dict[str, Any] = {}
        
        if query.workflow_id:
            mongo_query["workflow_id"] = query.workflow_id
        if query.agent_id:
            mongo_query["agent_id"] = query.agent_id
        if query.session_id:
            mongo_query["session_id"] = query.session_id
        if query.user_id:
            mongo_query["user_id"] = query.user_id
        if query.status:
            mongo_query["status"] = query.status.value
        
        # 时间范围
        if query.start_time or query.end_time:
            mongo_query["start_time"] = {}
            if query.start_time:
                mongo_query["start_time"]["$gte"] = query.start_time.isoformat()
            if query.end_time:
                mongo_query["start_time"]["$lte"] = query.end_time.isoformat()
        
        # 耗时范围
        if query.min_duration_ms or query.max_duration_ms:
            mongo_query["duration_ms"] = {}
            if query.min_duration_ms:
                mongo_query["duration_ms"]["$gte"] = query.min_duration_ms
            if query.max_duration_ms:
                mongo_query["duration_ms"]["$lte"] = query.max_duration_ms
        
        # 查询 MongoDB
        if self._collection is not None:
            try:
                cursor = (
                    self._collection.find(mongo_query)
                    .sort("start_time", -1)
                    .skip(query.offset)
                    .limit(query.limit)
                )
                docs = await cursor.to_list(length=query.limit)
                return [Trace(**doc) for doc in docs]
            except Exception as e:
                logger.error("trace_query_failed", error=str(e))
        
        # 回退到内存查询
        return self._query_buffer(query)
    
    def _query_buffer(self, query: TraceQuery) -> list[Trace]:
        """从内存缓冲区查询"""
        results = []
        for trace in reversed(self._buffer):
            if query.workflow_id and trace.workflow_id != query.workflow_id:
                continue
            if query.agent_id and trace.agent_id != query.agent_id:
                continue
            if query.session_id and trace.session_id != query.session_id:
                continue
            if query.status and trace.status != query.status:
                continue
            results.append(trace)
        
        start = query.offset
        end = start + query.limit
        return results[start:end]
    
    def get_recent(self, limit: int = 20) -> list[Trace]:
        """获取最近的 Traces"""
        return list(reversed(list(self._buffer)))[:limit]
    
    def subscribe(self) -> asyncio.Queue:
        """订阅实时 Trace 更新"""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue
    
    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """取消订阅"""
        if queue in self._subscribers:
            self._subscribers.remove(queue)
    
    async def _notify_subscribers(self, trace: Trace) -> None:
        """通知所有订阅者"""
        for queue in self._subscribers:
            try:
                queue.put_nowait(trace)
            except asyncio.QueueFull:
                pass
    
    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            self._client.close()


def get_trace_store() -> TraceStore:
    """获取全局 TraceStore 实例"""
    global _trace_store
    if _trace_store is None:
        from agio.config import settings
        _trace_store = TraceStore(
            mongo_uri=settings.mongo_uri,
            db_name=settings.mongo_db_name,
        )
    return _trace_store


async def initialize_trace_store() -> TraceStore:
    """初始化并返回全局 Store"""
    store = get_trace_store()
    await store.initialize()
    return store
```

### 5.2 MongoDB Schema

```javascript
// traces collection
{
    "trace_id": "tr_abc123",
    "workflow_id": "research_pipeline",
    "agent_id": null,
    "session_id": "sess_001",
    "user_id": "user_001",
    
    "start_time": "2024-12-05T10:00:00Z",
    "end_time": "2024-12-05T10:00:05Z",
    "duration_ms": 5200,
    "status": "ok",
    
    "root_span_id": "span_001",
    "spans": [
        {
            "span_id": "span_001",
            "trace_id": "tr_abc123",
            "parent_span_id": null,
            "kind": "workflow",
            "name": "research_pipeline",
            "start_time": "...",
            "end_time": "...",
            "duration_ms": 5200,
            "status": "ok",
            "depth": 0,
            "attributes": {"workflow_type": "pipeline"},
            "input_preview": "Research AI agents...",
            "output_preview": "AI agents are..."
        },
        {
            "span_id": "span_002",
            "trace_id": "tr_abc123",
            "parent_span_id": "span_001",
            "kind": "stage",
            "name": "intent",
            "depth": 1,
            // ...
        },
        // ... more spans
    ],
    
    "total_tokens": 850,
    "total_llm_calls": 3,
    "total_tool_calls": 1,
    "max_depth": 3,
    
    "input_query": "Research AI agents",
    "final_output": "AI agents are software..."
}

// Indexes
db.traces.createIndex({ "trace_id": 1 }, { unique: true })
db.traces.createIndex({ "start_time": -1 })
db.traces.createIndex({ "workflow_id": 1, "start_time": -1 })
db.traces.createIndex({ "session_id": 1 })
db.traces.createIndex({ "status": 1 })
db.traces.createIndex({ "duration_ms": 1 })
```

---

## 6. API 设计

### 6.1 Trace 查询 API

```python
# agio/api/routes/traces.py

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from agio.observability.trace_store import (
    get_trace_store,
    TraceQuery,
)
from agio.observability.trace import Trace, Span

router = APIRouter(prefix="/traces", tags=["Observability"])


@router.get("/")
async def list_traces(
    workflow_id: str | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    status: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    min_duration_ms: float | None = None,
    max_duration_ms: float | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[TraceSummary]:
    """
    查询 Trace 列表
    
    Returns:
        Trace 摘要列表（不包含完整 Span 详情）
    """
    store = get_trace_store()
    query = TraceQuery(
        workflow_id=workflow_id,
        agent_id=agent_id,
        session_id=session_id,
        status=SpanStatus(status) if status else None,
        start_time=start_time,
        end_time=end_time,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        limit=limit,
        offset=offset,
    )
    traces = await store.query_traces(query)
    return [_to_summary(t) for t in traces]


@router.get("/{trace_id}")
async def get_trace(trace_id: str) -> TraceDetail:
    """
    获取单个 Trace 详情
    
    Returns:
        完整 Trace（包含所有 Spans）
    """
    store = get_trace_store()
    trace = await store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return _to_detail(trace)


@router.get("/{trace_id}/waterfall")
async def get_trace_waterfall(trace_id: str) -> WaterfallData:
    """
    获取 Trace 瀑布图数据
    
    返回优化后的前端渲染格式
    """
    store = get_trace_store()
    trace = await store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return _build_waterfall(trace)


@router.get("/stream")
async def stream_traces():
    """
    SSE 实时推送新 Traces
    """
    store = get_trace_store()
    queue = store.subscribe()
    
    async def event_generator():
        try:
            while True:
                trace = await queue.get()
                yield {
                    "event": "trace",
                    "data": _to_summary(trace).model_dump_json(),
                }
        finally:
            store.unsubscribe(queue)
    
    return EventSourceResponse(event_generator())


# === Response Models ===

class TraceSummary(BaseModel):
    """Trace 摘要（列表展示用）"""
    trace_id: str
    workflow_id: str | None
    agent_id: str | None
    session_id: str | None
    start_time: datetime
    duration_ms: float | None
    status: str
    total_tokens: int
    total_llm_calls: int
    total_tool_calls: int
    max_depth: int
    input_preview: str | None
    output_preview: str | None


class SpanSummary(BaseModel):
    """Span 摘要"""
    span_id: str
    parent_span_id: str | None
    kind: str
    name: str
    depth: int
    start_time: datetime
    duration_ms: float | None
    status: str
    error_message: str | None
    attributes: dict
    metrics: dict


class TraceDetail(BaseModel):
    """Trace 详情（完整信息）"""
    trace_id: str
    workflow_id: str | None
    agent_id: str | None
    session_id: str | None
    user_id: str | None
    start_time: datetime
    end_time: datetime | None
    duration_ms: float | None
    status: str
    spans: list[SpanSummary]
    total_tokens: int
    total_llm_calls: int
    total_tool_calls: int
    max_depth: int
    input_query: str | None
    final_output: str | None


class WaterfallSpan(BaseModel):
    """瀑布图 Span 数据"""
    span_id: str
    parent_span_id: str | None
    kind: str
    name: str
    depth: int
    
    # 相对时间（相对于 Trace 开始）
    start_offset_ms: float
    duration_ms: float
    
    status: str
    error_message: str | None
    
    # 展示信息
    label: str
    sublabel: str | None
    tokens: int | None


class WaterfallData(BaseModel):
    """瀑布图完整数据"""
    trace_id: str
    total_duration_ms: float
    spans: list[WaterfallSpan]
    
    # 聚合指标
    metrics: dict


def _build_waterfall(trace: Trace) -> WaterfallData:
    """构建瀑布图数据"""
    trace_start = trace.start_time
    spans = []
    
    for span in trace.spans:
        # 计算相对偏移
        offset = (span.start_time - trace_start).total_seconds() * 1000
        
        # 构建标签
        label = span.name
        sublabel = None
        tokens = None
        
        if span.kind == SpanKind.LLM_CALL:
            tokens = span.metrics.get("tokens.total")
            sublabel = f"{tokens} tokens" if tokens else None
        elif span.kind == SpanKind.TOOL_CALL:
            sublabel = f"{span.duration_ms:.0f}ms" if span.duration_ms else None
        
        spans.append(WaterfallSpan(
            span_id=span.span_id,
            parent_span_id=span.parent_span_id,
            kind=span.kind.value,
            name=span.name,
            depth=span.depth,
            start_offset_ms=offset,
            duration_ms=span.duration_ms or 0,
            status=span.status.value,
            error_message=span.error_message,
            label=label,
            sublabel=sublabel,
            tokens=tokens,
        ))
    
    return WaterfallData(
        trace_id=trace.trace_id,
        total_duration_ms=trace.duration_ms or 0,
        spans=spans,
        metrics={
            "total_tokens": trace.total_tokens,
            "total_llm_calls": trace.total_llm_calls,
            "total_tool_calls": trace.total_tool_calls,
            "max_depth": trace.max_depth,
        },
    )
```

### 6.2 API 集成到主路由

```python
# agio/api/main.py

from agio.api.routes import traces

app.include_router(traces.router)
```

---

## 7. 前端可视化

### 7.1 页面结构

新增 `Traces` 页面，集成到现有导航：

```
/traces              → Trace 列表页
/traces/:trace_id    → Trace 详情页（瀑布图）
```

### 7.2 Trace 列表页

```tsx
// src/pages/Traces.tsx

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Table, TableBody, TableCell, TableHead, 
  TableHeader, TableRow 
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { 
  Select, SelectContent, SelectItem, 
  SelectTrigger, SelectValue 
} from '@/components/ui/select';

interface TraceSummary {
  trace_id: string;
  workflow_id: string | null;
  agent_id: string | null;
  start_time: string;
  duration_ms: number | null;
  status: string;
  total_tokens: number;
  total_llm_calls: number;
  total_tool_calls: number;
  input_preview: string | null;
}

export default function Traces() {
  const navigate = useNavigate();
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [filters, setFilters] = useState({
    workflow_id: '',
    status: '',
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTraces();
  }, [filters]);

  const fetchTraces = async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.workflow_id) params.set('workflow_id', filters.workflow_id);
    if (filters.status) params.set('status', filters.status);
    
    const res = await fetch(`/api/traces?${params}`);
    const data = await res.json();
    setTraces(data);
    setLoading(false);
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'default' | 'destructive' | 'secondary'> = {
      ok: 'default',
      error: 'destructive',
      running: 'secondary',
    };
    return <Badge variant={variants[status] || 'secondary'}>{status}</Badge>;
  };

  const formatDuration = (ms: number | null) => {
    if (!ms) return '-';
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  return (
    <div className="container mx-auto py-6">
      <h1 className="text-2xl font-bold mb-6">Traces</h1>
      
      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <Input
          placeholder="Filter by Workflow ID"
          value={filters.workflow_id}
          onChange={(e) => setFilters({ ...filters, workflow_id: e.target.value })}
          className="max-w-xs"
        />
        <Select
          value={filters.status}
          onValueChange={(v) => setFilters({ ...filters, status: v })}
        >
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All</SelectItem>
            <SelectItem value="ok">OK</SelectItem>
            <SelectItem value="error">Error</SelectItem>
            <SelectItem value="running">Running</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Trace ID</TableHead>
            <TableHead>Workflow/Agent</TableHead>
            <TableHead>Time</TableHead>
            <TableHead>Duration</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Tokens</TableHead>
            <TableHead>LLM/Tools</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {traces.map((trace) => (
            <TableRow
              key={trace.trace_id}
              className="cursor-pointer hover:bg-muted"
              onClick={() => navigate(`/traces/${trace.trace_id}`)}
            >
              <TableCell className="font-mono text-sm">
                {trace.trace_id.slice(0, 8)}...
              </TableCell>
              <TableCell>
                {trace.workflow_id || trace.agent_id || '-'}
              </TableCell>
              <TableCell>
                {new Date(trace.start_time).toLocaleString()}
              </TableCell>
              <TableCell>{formatDuration(trace.duration_ms)}</TableCell>
              <TableCell>{getStatusBadge(trace.status)}</TableCell>
              <TableCell>{trace.total_tokens}</TableCell>
              <TableCell>
                {trace.total_llm_calls} / {trace.total_tool_calls}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

### 7.3 瀑布图组件

```tsx
// src/components/Waterfall.tsx

import { useMemo } from 'react';
import { cn } from '@/lib/utils';

interface WaterfallSpan {
  span_id: string;
  parent_span_id: string | null;
  kind: string;
  name: string;
  depth: int;
  start_offset_ms: number;
  duration_ms: number;
  status: string;
  error_message: string | null;
  label: string;
  sublabel: string | null;
  tokens: number | null;
}

interface WaterfallProps {
  spans: WaterfallSpan[];
  totalDuration: number;
  onSpanClick?: (span: WaterfallSpan) => void;
}

const SPAN_HEIGHT = 32;
const LABEL_WIDTH = 200;
const MIN_BAR_WIDTH = 4;

const KIND_COLORS: Record<string, string> = {
  workflow: 'bg-purple-500',
  stage: 'bg-blue-500',
  agent: 'bg-green-500',
  llm_call: 'bg-amber-500',
  tool_call: 'bg-cyan-500',
};

export function Waterfall({ spans, totalDuration, onSpanClick }: WaterfallProps) {
  // 构建层级树
  const sortedSpans = useMemo(() => {
    // 按开始时间排序，保持层级顺序
    return [...spans].sort((a, b) => {
      if (a.depth !== b.depth) return a.depth - b.depth;
      return a.start_offset_ms - b.start_offset_ms;
    });
  }, [spans]);

  const formatDuration = (ms: number) => {
    if (ms < 1) return '<1ms';
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  return (
    <div className="w-full overflow-x-auto">
      {/* Timeline header */}
      <div className="flex border-b border-gray-200 dark:border-gray-700 mb-2">
        <div style={{ width: LABEL_WIDTH }} className="shrink-0 px-2 py-1 text-sm font-medium">
          Span
        </div>
        <div className="flex-1 relative h-6">
          {/* Time markers */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct) => (
            <div
              key={pct}
              className="absolute top-0 h-full border-l border-gray-300 dark:border-gray-600"
              style={{ left: `${pct * 100}%` }}
            >
              <span className="text-xs text-gray-500 ml-1">
                {formatDuration(totalDuration * pct)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Spans */}
      <div className="relative">
        {sortedSpans.map((span, index) => {
          const leftPct = (span.start_offset_ms / totalDuration) * 100;
          const widthPct = Math.max(
            (span.duration_ms / totalDuration) * 100,
            (MIN_BAR_WIDTH / 800) * 100
          );

          return (
            <div
              key={span.span_id}
              className={cn(
                'flex items-center h-8 hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer',
                span.status === 'error' && 'bg-red-50 dark:bg-red-900/20'
              )}
              onClick={() => onSpanClick?.(span)}
            >
              {/* Label */}
              <div
                style={{ 
                  width: LABEL_WIDTH,
                  paddingLeft: span.depth * 16 + 8,
                }}
                className="shrink-0 truncate text-sm"
              >
                <span className={cn(
                  'inline-block w-2 h-2 rounded-full mr-2',
                  KIND_COLORS[span.kind] || 'bg-gray-400'
                )} />
                <span className="font-medium">{span.label}</span>
                {span.sublabel && (
                  <span className="text-gray-500 ml-1 text-xs">
                    ({span.sublabel})
                  </span>
                )}
              </div>

              {/* Timeline bar */}
              <div className="flex-1 relative h-full">
                <div
                  className={cn(
                    'absolute top-1/2 -translate-y-1/2 h-4 rounded',
                    KIND_COLORS[span.kind] || 'bg-gray-400',
                    span.status === 'error' && 'bg-red-500'
                  )}
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    minWidth: MIN_BAR_WIDTH,
                  }}
                >
                  {/* Duration label on bar */}
                  {widthPct > 5 && (
                    <span className="absolute inset-0 flex items-center justify-center text-xs text-white font-medium">
                      {formatDuration(span.duration_ms)}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

### 7.4 Trace 详情页

```tsx
// src/pages/TraceDetail.tsx

import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Waterfall } from '@/components/Waterfall';
import { 
  Sheet, SheetContent, SheetHeader, 
  SheetTitle, SheetDescription 
} from '@/components/ui/sheet';

interface TraceDetail {
  trace_id: string;
  workflow_id: string | null;
  agent_id: string | null;
  session_id: string | null;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  status: string;
  total_tokens: number;
  total_llm_calls: number;
  total_tool_calls: number;
  max_depth: number;
  input_query: string | null;
  final_output: string | null;
}

interface WaterfallData {
  trace_id: string;
  total_duration_ms: number;
  spans: WaterfallSpan[];
  metrics: Record<string, any>;
}

export default function TraceDetail() {
  const { traceId } = useParams<{ traceId: string }>();
  const [trace, setTrace] = useState<TraceDetail | null>(null);
  const [waterfall, setWaterfall] = useState<WaterfallData | null>(null);
  const [selectedSpan, setSelectedSpan] = useState<WaterfallSpan | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (traceId) {
      fetchTrace(traceId);
    }
  }, [traceId]);

  const fetchTrace = async (id: string) => {
    setLoading(true);
    const [traceRes, waterfallRes] = await Promise.all([
      fetch(`/api/traces/${id}`),
      fetch(`/api/traces/${id}/waterfall`),
    ]);
    setTrace(await traceRes.json());
    setWaterfall(await waterfallRes.json());
    setLoading(false);
  };

  if (loading || !trace || !waterfall) {
    return <div className="p-6">Loading...</div>;
  }

  return (
    <div className="container mx-auto py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">
            {trace.workflow_id || trace.agent_id || 'Trace'}
          </h1>
          <p className="text-gray-500 font-mono text-sm">{trace.trace_id}</p>
        </div>
        <Badge variant={trace.status === 'ok' ? 'default' : 'destructive'}>
          {trace.status}
        </Badge>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              Duration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {trace.duration_ms 
                ? `${(trace.duration_ms / 1000).toFixed(2)}s`
                : '-'}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              Total Tokens
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{trace.total_tokens}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              LLM Calls
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{trace.total_llm_calls}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              Tool Calls
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{trace.total_tool_calls}</p>
          </CardContent>
        </Card>
      </div>

      {/* Input/Output */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Input</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-sm whitespace-pre-wrap bg-gray-50 dark:bg-gray-900 p-3 rounded">
              {trace.input_query || '-'}
            </pre>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Output</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-sm whitespace-pre-wrap bg-gray-50 dark:bg-gray-900 p-3 rounded max-h-48 overflow-y-auto">
              {trace.final_output || '-'}
            </pre>
          </CardContent>
        </Card>
      </div>

      {/* Waterfall Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Execution Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <Waterfall
            spans={waterfall.spans}
            totalDuration={waterfall.total_duration_ms}
            onSpanClick={setSelectedSpan}
          />
        </CardContent>
      </Card>

      {/* Span Detail Sheet */}
      <Sheet open={!!selectedSpan} onOpenChange={() => setSelectedSpan(null)}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{selectedSpan?.label}</SheetTitle>
            <SheetDescription>
              {selectedSpan?.kind} • {selectedSpan?.span_id.slice(0, 8)}
            </SheetDescription>
          </SheetHeader>
          <div className="mt-6 space-y-4">
            <div>
              <h4 className="font-medium mb-1">Duration</h4>
              <p>{selectedSpan?.duration_ms?.toFixed(0)}ms</p>
            </div>
            <div>
              <h4 className="font-medium mb-1">Status</h4>
              <Badge variant={selectedSpan?.status === 'ok' ? 'default' : 'destructive'}>
                {selectedSpan?.status}
              </Badge>
            </div>
            {selectedSpan?.error_message && (
              <div>
                <h4 className="font-medium mb-1 text-red-500">Error</h4>
                <pre className="text-sm bg-red-50 dark:bg-red-900/20 p-2 rounded">
                  {selectedSpan.error_message}
                </pre>
              </div>
            )}
            {selectedSpan?.tokens && (
              <div>
                <h4 className="font-medium mb-1">Tokens</h4>
                <p>{selectedSpan.tokens}</p>
              </div>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
```

### 7.5 导航集成

```tsx
// src/App.tsx - 添加路由

import Traces from './pages/Traces';
import TraceDetail from './pages/TraceDetail';

// 在 Routes 中添加
<Route path="/traces" element={<Traces />} />
<Route path="/traces/:traceId" element={<TraceDetail />} />

// src/components/Layout.tsx - 添加导航项
const navItems = [
  // ... 现有项目 ...
  { path: '/traces', label: 'Traces', icon: ActivityIcon },
];
```

### 7.6 瀑布图示意

```
┌────────────────────────────────────────────────────────────────────┐
│  Trace: tr_abc123 | research_pipeline | 5.2s | ✓ OK                │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─ Duration ─┐  ┌─ Tokens ─┐  ┌─ LLM ─┐  ┌─ Tools ─┐              │
│  │   5.20s    │  │   850    │  │   3   │  │    1    │              │
│  └────────────┘  └──────────┘  └───────┘  └─────────┘              │
│                                                                     │
├────────────────────────────────────────────────────────────────────┤
│  Execution Timeline                                                 │
│                                                                     │
│  Span                    0ms    1s     2s     3s     4s     5s     │
│  ─────────────────────────│──────│──────│──────│──────│──────│─────│
│                                                                     │
│  ● research_pipeline     ════════════════════════════════════      │
│    ● intent              ════                                       │
│      ● gpt-4o            ═══  (120 tokens)                         │
│    ● research                 ═══════════════════                  │
│      ● gpt-4o                 ═════════  (350 tokens)              │
│      ◆ web_search                  ════  (2 results)               │
│    ● summary                                    ═══════════        │
│      ● gpt-4o                                   ══════  (380 tkns) │
│                                                                     │
│  Legend: ● workflow/stage/agent  ◆ tool                            │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

---

## 8. 实施计划

### 8.1 开发阶段

| 阶段 | 任务 | 预估工时 | 依赖 |
|------|------|----------|------|
| **P1: 数据模型** | Trace/Span 模型定义 | 2h | - |
| **P2: TraceCollector** | 事件流处理、Span 构建 | 4h | P1 |
| **P3: TraceStore** | MongoDB 持久化、内存缓存 | 3h | P1 |
| **P4: API** | REST 端点、瀑布图数据 | 3h | P2, P3 |
| **P5: 集成** | 与 Workflow/Agent 执行流集成 | 2h | P2, P4 |
| **P6: 前端列表页** | Trace 列表、筛选 | 3h | P4 |
| **P7: 前端瀑布图** | 可视化组件、交互 | 4h | P4, P6 |
| **P8: 测试优化** | 单元测试、性能优化 | 3h | All |

**总计**: ~24h

### 8.2 文件清单

#### 新增文件

```
agio/observability/
├── trace.py            # Trace/Span 模型
├── collector.py        # TraceCollector
└── trace_store.py      # TraceStore

agio/api/routes/
└── traces.py           # Trace API

agio-frontend/src/
├── pages/
│   ├── Traces.tsx      # Trace 列表页
│   └── TraceDetail.tsx # Trace 详情页
└── components/
    └── Waterfall.tsx   # 瀑布图组件
```

#### 修改文件

```
agio/observability/__init__.py    # 导出新模块
agio/observability/models.py      # 添加 trace_id/span_id 到 LLMCallLog
agio/observability/tracker.py     # 添加 trace context
agio/api/main.py                  # 注册 traces 路由
agio-frontend/src/App.tsx         # 添加路由
agio-frontend/src/components/Layout.tsx  # 添加导航
```

### 8.3 测试策略

```python
# tests/observability/test_collector.py

import pytest
from agio.observability.collector import TraceCollector
from agio.observability.trace import SpanKind, SpanStatus
from agio.domain.events import StepEvent, StepEventType

@pytest.mark.asyncio
async def test_collector_builds_trace_from_events():
    """测试 TraceCollector 从事件流构建 Trace"""
    events = [
        StepEvent(type=StepEventType.RUN_STARTED, run_id="r1", data={"workflow_id": "wf1"}),
        StepEvent(type=StepEventType.STAGE_STARTED, run_id="r1", stage_id="s1"),
        StepEvent(type=StepEventType.STEP_COMPLETED, run_id="r1", snapshot=...),
        StepEvent(type=StepEventType.STAGE_COMPLETED, run_id="r1", stage_id="s1"),
        StepEvent(type=StepEventType.RUN_COMPLETED, run_id="r1", data={"response": "..."}),
    ]
    
    collector = TraceCollector()
    collected = []
    
    async def event_gen():
        for e in events:
            yield e
    
    async for event in collector.wrap_stream(event_gen(), workflow_id="wf1"):
        collected.append(event)
        assert event.trace_id is not None
    
    assert len(collected) == len(events)


@pytest.mark.asyncio
async def test_collector_handles_nested_agents():
    """测试嵌套 Agent 场景"""
    # Agent as Tool 场景
    ...


@pytest.mark.asyncio
async def test_collector_handles_errors():
    """测试错误处理"""
    ...
```

### 8.4 性能考虑

| 场景 | 优化策略 |
|------|----------|
| 大量 Spans | 分页加载，虚拟滚动 |
| 高频写入 | 批量写入 MongoDB |
| 内存占用 | 环形缓冲区限制，输入输出截断 |
| 查询性能 | 复合索引，聚合预计算 |

---

## 附录：与 OpenTelemetry 对比

| 特性 | Agio Trace | OpenTelemetry |
|------|------------|---------------|
| Span 类型 | 5 种（workflow/stage/agent/llm/tool） | 通用 Span |
| 存储 | MongoDB 自管理 | 需要后端（Jaeger/Zipkin） |
| 指标 | 内嵌（tokens/duration） | 独立 Metrics 系统 |
| 集成 | 与 StepEvent 紧密集成 | 需要 SDK 适配 |
| 复杂度 | 简单，Agio 专用 | 通用，学习曲线高 |

后续可考虑实现 OTLP 导出器，将 Trace 导出到外部 APM 系统。

---

> **文档维护说明**  
> 本文档随实现迭代更新，如有变更请同步修改。

