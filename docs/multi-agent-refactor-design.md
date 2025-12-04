# Multi-Agent 协作系统重构设计方案

> 版本: v1.0  
> 日期: 2024-12-04  
> 状态: Draft

## 目录

1. [概述与目标](#1-概述与目标)
2. [当前架构分析](#2-当前架构分析)
3. [核心设计：Runnable 协议与 Workflow](#3-核心设计runnable-协议与-workflow)
4. [条件分支与 YAML 配置](#4-条件分支与-yaml-配置)
5. [可观测性设计：Trace/Span](#5-可观测性设计tracespan)
6. [数据模型扩展：Step/Run/Session](#6-数据模型扩展steprunsession)
7. [Fork/Resume 多 Agent 支持](#7-forkresume-多-agent-支持)
8. [前端展示设计](#8-前端展示设计)
9. [模块改动清单](#9-模块改动清单)

---

## 1. 概述与目标

### 1.1 背景

当前 Agio 系统支持单 Agent 与用户交互，具备完整的 Step-based 执行模型、流式输出、Fork/Resume 等能力。为了支持更复杂的 AI 应用场景，需要扩展支持多 Agent 协作。

### 1.2 多 Agent 协作模式

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| **Pipeline/Workflow** | 串行执行 A → B → C | 任务分解、审核流程 |
| **Parallel/Team** | 并行执行 [A, B, C] → merge | 多视角分析、投票决策 |
| **Agent as Tool** | Orchestra Agent 调用 SubAgent | 动态决策、复杂任务 |
| **Code-controlled** | for/while/if else 控制流 | 迭代优化、条件分支 |

### 1.3 设计目标

1. **统一抽象** - Agent 和 Workflow 实现相同协议，可互相嵌套
2. **流式输出** - 多 Agent 执行过程实时流式返回，前端无需特殊处理
3. **向后兼容** - 现有单 Agent 逻辑和 API 保持不变
4. **可观测性** - 完整的执行链路追踪
5. **低认知负荷** - 简单场景用 YAML 配置，复杂逻辑用代码

### 1.4 设计原则

- **SOLID** - 单一职责，开闭原则
- **KISS** - 保持简单，避免过度设计
- **组合优于继承** - 通过协议组合能力

---

## 2. 当前架构分析

### 2.1 现有架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        agent.py                              │
│                    (顶层入口，编排层)                         │
├─────────────────────────────────────────────────────────────┤
│  domain/          │  runtime/         │  config/            │
│  (纯领域模型)      │  (执行引擎)        │  (配置系统)         │
├─────────────────────────────────────────────────────────────┤
│                      providers/                              │
│              (外部服务适配器: LLM, Storage, Tools)           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件职责

| 组件 | 职责 |
|------|------|
| `Agent` | 配置容器，持有 Model/Tools/Memory，委托执行给 Runner |
| `StepRunner` | 管理 Run 生命周期，保存 Steps |
| `StepExecutor` | LLM ↔ Tool 循环，生成 StepEvent 流 |
| `Step` | 核心数据单元，直接映射 LLM 消息格式 |
| `StepEvent` | 流式事件（delta + snapshot） |

### 2.3 执行流程

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
StepExecutor.execute()
    │
    ├── 构建上下文
    ├── 调用 LLM (streaming)
    ├── 生成 StepEvent
    │
    ▼ (如果有 tool_calls)
ToolExecutor.execute_batch()
    │
    ├── 并行执行工具
    ├── 保存 Tool Steps
    │
    ▼ (循环直到无 tool_calls)
```

### 2.4 数据模型

```
Session (会话)
├── Run (一次请求的执行)
│   ├── Step (user)      ← 核心持久化单元
│   ├── Step (assistant)
│   ├── Step (tool)
│   └── Step (assistant)
└── Run
    └── ...
```

**优势**：
- Step 包含完整 LLM 消息，支持重放
- 支持从任意 Step Fork 新 Session
- 支持 Resume 继续执行

---

## 3. 核心设计：Runnable 协议与 Workflow

### 3.1 Runnable 协议

**核心洞察**：Agent 和 Workflow 应该实现相同的协议，使它们可以互相嵌套、作为 Tool 使用。

```python
# agio/workflow/base.py

from abc import ABC, abstractmethod
from typing import AsyncIterator, Protocol

class Runnable(Protocol):
    """
    统一的可执行单元协议
    
    Agent 和 Workflow 都实现此接口，使得：
    1. 前端无需区分 Agent 和 Workflow
    2. Workflow 可以包含 Agent 或其他 Workflow
    3. 任何 Runnable 都可以转为 Tool
    """
    
    @property
    def id(self) -> str:
        """唯一标识"""
        ...
    
    async def arun_stream(
        self, 
        query: str,
        user_id: str | None = None,
        session_id: str | None = None,
        context: dict | None = None,
    ) -> AsyncIterator[StepEvent]:
        """
        执行并返回事件流
        
        Args:
            query: 用户输入
            user_id: 用户 ID
            session_id: 会话 ID
            context: 上游传递的上下文（Workflow 场景）
        """
        ...
```

### 3.2 Agent 实现 Runnable

现有 Agent 类只需小幅调整即可实现 Runnable 协议：

```python
# agio/agent.py - 扩展

class Agent:
    """Agent 天然实现 Runnable 协议"""
    
    @property
    def id(self) -> str:
        return self._id  # 原 self.name
    
    async def arun_stream(
        self, 
        query: str,
        user_id: str | None = None,
        session_id: str | None = None,
        context: dict | None = None,  # 新增：接收上游上下文
    ) -> AsyncIterator[StepEvent]:
        # 现有实现基本不变
        # context 可用于 system_prompt 动态注入
        ...
```

### 3.3 Workflow 基类

```python
# agio/workflow/base.py

class BaseWorkflow(ABC):
    """Workflow 基类"""
    
    def __init__(self, name: str):
        self._id = name
    
    @property
    def id(self) -> str:
        return self._id
    
    @abstractmethod
    async def arun_stream(
        self,
        query: str,
        user_id: str | None = None,
        session_id: str | None = None,
        context: dict | None = None,
    ) -> AsyncIterator[StepEvent]:
        ...
```

### 3.4 Pipeline Workflow（串行）

```python
# agio/workflow/pipeline.py

class PipelineWorkflow(BaseWorkflow):
    """
    串行 Pipeline: A → B → C
    每个 Agent 的输出作为下一个 Agent 的输入
    """
    
    def __init__(
        self,
        name: str,
        agents: list[Runnable],
        transform_fn: Callable[[str, dict], str] | None = None,
    ):
        super().__init__(name)
        self.agents = agents
        self.transform_fn = transform_fn or (lambda output, ctx: output)
    
    async def arun_stream(self, query: str, **kwargs) -> AsyncIterator[StepEvent]:
        workflow_run_id = str(uuid4())
        
        yield create_workflow_started_event(
            workflow_id=self._id,
            run_id=workflow_run_id,
            agents=[a.id for a in self.agents],
        )
        
        current_input = query
        accumulated_context = kwargs.get("context") or {}
        
        for i, agent in enumerate(self.agents):
            yield create_agent_started_event(
                workflow_id=self._id, agent_id=agent.id, step_index=i, depth=1
            )
            
            agent_output = ""
            async for event in agent.arun_stream(query=current_input, **kwargs):
                event.workflow_id = self._id
                event.agent_id = agent.id
                event.depth = 1
                yield event
                
                if event.type == StepEventType.STEP_DELTA and event.delta:
                    agent_output += event.delta.content or ""
            
            yield create_agent_completed_event(
                workflow_id=self._id, agent_id=agent.id
            )
            
            accumulated_context[agent.id] = agent_output
            current_input = self.transform_fn(agent_output, accumulated_context)
        
        yield create_workflow_completed_event(workflow_id=self._id, run_id=workflow_run_id)
```

### 3.5 Parallel Workflow（并行）

```python
# agio/workflow/parallel.py

class ParallelWorkflow(BaseWorkflow):
    """
    并行执行: [A, B, C] → merge
    多个 Agent 同时执行，结果合并
    """
    
    def __init__(
        self,
        name: str,
        agents: list[Runnable],
        merge_fn: Callable[[dict[str, str]], str] | None = None,
    ):
        super().__init__(name)
        self.agents = agents
        self.merge_fn = merge_fn or self._default_merge
    
    def _default_merge(self, outputs: dict[str, str]) -> str:
        return "\n\n---\n\n".join(
            f"**{agent_id}**:\n{output}" 
            for agent_id, output in outputs.items()
        )
    
    async def arun_stream(self, query: str, **kwargs) -> AsyncIterator[StepEvent]:
        workflow_run_id = str(uuid4())
        
        yield create_workflow_started_event(
            workflow_id=self._id, run_id=workflow_run_id, mode="parallel"
        )
        
        async def run_agent(agent: Runnable, branch_id: str):
            events, output = [], ""
            async for event in agent.arun_stream(query=query, **kwargs):
                event.workflow_id = self._id
                event.agent_id = agent.id
                event.branch_id = branch_id
                event.depth = 1
                events.append(event)
                if event.type == StepEventType.STEP_DELTA and event.delta:
                    output += event.delta.content or ""
            return agent.id, events, output
        
        tasks = [
            asyncio.create_task(run_agent(agent, f"branch_{i}"))
            for i, agent in enumerate(self.agents)
        ]
        
        outputs = {}
        for coro in asyncio.as_completed(tasks):
            agent_id, events, output = await coro
            for event in events:
                yield event
            outputs[agent_id] = output
        
        merged = self.merge_fn(outputs)
        yield create_workflow_completed_event(
            workflow_id=self._id, run_id=workflow_run_id,
            data={"merged_output": merged, "agent_outputs": outputs}
        )
```

### 3.6 Agent/Workflow as Tool

```python
# agio/workflow/tools.py

def as_tool(runnable: Runnable, description: str | None = None) -> BaseTool:
    """
    将任意 Runnable (Agent 或 Workflow) 转为 Tool
    
    用法:
        research_tool = as_tool(research_agent, "Research expert")
        pipeline_tool = as_tool(research_pipeline, "Complete workflow")
        
        orchestra = Agent(model=gpt4, tools=[research_tool, pipeline_tool])
    """
    return RunnableTool(runnable, description)


class RunnableTool(BaseTool):
    """通用 Runnable -> Tool 适配器"""
    
    def __init__(
        self, 
        runnable: Runnable, 
        description: str | None = None,
        event_callback: Callable[[StepEvent], Awaitable[None]] | None = None,
    ):
        self.runnable = runnable
        self._description = description or f"Execute {runnable.id}"
        self.event_callback = event_callback  # 流式事件回调
        super().__init__()
    
    def get_name(self) -> str:
        return f"call_{self.runnable.id}"
    
    def get_description(self) -> str:
        return self._description
    
    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The task to delegate"},
                "context": {"type": "string", "description": "Optional context"}
            },
            "required": ["task"]
        }
    
    async def execute(self, parameters: dict, abort_signal=None) -> ToolResult:
        task = parameters.get("task", "")
        output = ""
        
        async for event in self.runnable.arun_stream(query=task):
            # 通过回调转发子事件（实现嵌套流式输出）
            if self.event_callback:
                event.parent_run_id = parameters.get("parent_run_id")
                event.depth = parameters.get("depth", 0) + 1
                await self.event_callback(event)
            
            if event.type == StepEventType.STEP_DELTA and event.delta:
                output += event.delta.content or ""
        
        return ToolResult(
            tool_name=self.get_name(),
            tool_call_id=parameters.get("tool_call_id", ""),
            content=output,
            is_success=True,
        )
```

### 3.7 StepEvent 扩展

```python
# agio/domain/events.py - 扩展

class StepEventType(str, Enum):
    # 现有事件
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    STEP_DELTA = "step_delta"
    STEP_COMPLETED = "step_completed"
    ERROR = "error"
    
    # 新增：多 Agent 事件
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    BRANCH_STARTED = "branch_started"
    BRANCH_COMPLETED = "branch_completed"
    LOOP_ITERATION = "loop_iteration"


class StepEvent(BaseModel):
    type: StepEventType
    run_id: str | None = None
    step_id: str | None = None
    
    # 新增：多 Agent 上下文
    workflow_id: str | None = None
    workflow_run_id: str | None = None
    agent_id: str | None = None
    branch_id: str | None = None
    depth: int = 0
    parent_run_id: str | None = None
    
    delta: StepDelta | None = None
    snapshot: Step | None = None
    data: dict | None = None
```

---

## 4. 条件分支与 YAML 配置

### 4.1 设计思路：混合模式

| 方案 | 优点 | 缺点 |
|------|------|------|
| **YAML DSL** | 配置化，低代码 | 复杂逻辑表达困难 |
| **Code-first** | 灵活，IDE 支持好 | 需要编程能力 |
| **混合模式** | 简单逻辑配置化，复杂逻辑代码化 | ✅ 最佳平衡 |

**推荐方案**：简单 Workflow 用 YAML，复杂逻辑用 Python 代码。

```
┌─────────────────────────────────────────────────────────────┐
│                    Workflow 复杂度谱系                       │
├─────────────────────────────────────────────────────────────┤
│  简单 ◄────────────────────────────────────────────► 复杂   │
│                                                              │
│  Pipeline      Router       Loop        Custom Code          │
│  (串行)        (条件分支)    (循环)      (任意逻辑)           │
│                                                              │
│  ═══════════════════════════════════════════════════════    │
│  │           YAML 配置              │    Python 代码    │    │
│  ═══════════════════════════════════════════════════════    │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 YAML 配置示例

#### Pipeline 配置

```yaml
# configs/workflows/research_pipeline.yaml
type: workflow
name: research_pipeline
mode: pipeline

stages:
  - name: classify
    agent: classifier_agent
    
  - name: research
    agent: researcher_agent
    
  - name: summarize
    agent: summarizer_agent
```

#### Router（条件分支）配置

```yaml
# configs/workflows/smart_router.yaml
type: workflow
name: smart_router
mode: router

input_stage:
  name: classify
  agent: classifier_agent

routes:
  - condition: "category == 'technical'"
    next: technical_expert
  - condition: "category == 'business'"
    next: business_analyst
  - default: general_assistant

output_stage:
  name: format
  agent: formatter_agent
```

#### 条件表达式语法（保持简单）

```yaml
# 支持的条件语法
condition: "category == 'technical'"           # 相等
condition: "score > 0.8"                       # 比较
condition: "contains(output, 'error')"         # 包含
condition: "len(items) > 5"                    # 长度
condition: "category in ['a', 'b']"            # 包含于
condition: "not is_empty(result)"              # 非空
```

### 4.3 条件表达式求值器

```python
# agio/workflow/conditions.py

import operator
from typing import Any

class ConditionEvaluator:
    """安全的条件表达式求值器（避免 eval 的安全问题）"""
    
    OPERATORS = {
        '==': operator.eq,
        '!=': operator.ne,
        '>': operator.gt,
        '<': operator.lt,
        '>=': operator.ge,
        '<=': operator.le,
    }
    
    FUNCTIONS = {
        'contains': lambda s, sub: sub in s,
        'len': len,
        'is_empty': lambda x: not x,
        'startswith': lambda s, prefix: s.startswith(prefix),
        'endswith': lambda s, suffix: s.endswith(suffix),
    }
    
    def evaluate(self, condition: str, context: dict[str, Any]) -> bool:
        """
        求值条件表达式
        
        Examples:
            evaluate("category == 'tech'", {"category": "tech"})  # True
            evaluate("score > 0.8", {"score": 0.9})  # True
            evaluate("contains(text, 'error')", {"text": "no error"})  # True
        """
        # 简单的词法分析和求值
        # 可使用 simpleeval 库或自定义解析器实现
        ...
```

### 4.4 Router Workflow 实现

```python
# agio/workflow/router.py

class RouterWorkflow(BaseWorkflow):
    """条件路由 Workflow"""
    
    def __init__(
        self,
        name: str,
        classifier: Runnable,
        routes: list[dict],  # [{"condition": "...", "agent": Runnable}]
        default_agent: Runnable,
    ):
        super().__init__(name)
        self.classifier = classifier
        self.routes = routes
        self.default_agent = default_agent
        self.evaluator = ConditionEvaluator()
    
    async def arun_stream(self, query: str, **kwargs) -> AsyncIterator[StepEvent]:
        # 1. 分类阶段
        classification = ""
        async for event in self.classifier.arun_stream(query=query, **kwargs):
            yield event
            if event.type == StepEventType.STEP_DELTA and event.delta:
                classification += event.delta.content or ""
        
        # 2. 解析分类结果
        context = self._parse_classification(classification)
        
        # 3. 选择路由
        selected_agent = self.default_agent
        for route in self.routes:
            if self.evaluator.evaluate(route["condition"], context):
                selected_agent = route["agent"]
                break
        
        # 4. 执行选中的 Agent
        async for event in selected_agent.arun_stream(query=query, **kwargs):
            yield event
```

### 4.5 复杂逻辑：Code-first + YAML 引用

对于循环、动态决策等复杂逻辑，推荐用 Python 实现：

```python
# agio/workflows/custom/iterative_research.py

class IterativeResearchWorkflow(BaseWorkflow):
    """迭代式研究 - 直到质量达标"""
    
    def __init__(
        self, 
        researcher: Runnable, 
        reviewer: Runnable, 
        max_iterations: int = 3
    ):
        super().__init__("iterative_research")
        self.researcher = researcher
        self.reviewer = reviewer
        self.max_iterations = max_iterations
    
    async def arun_stream(self, query: str, **kwargs) -> AsyncIterator[StepEvent]:
        iteration = 0
        current_input = query
        
        while iteration < self.max_iterations:
            iteration += 1
            
            yield create_loop_iteration_event(
                workflow_id=self._id,
                iteration=iteration,
                max_iterations=self.max_iterations,
            )
            
            # 研究阶段
            research_output = ""
            async for event in self.researcher.arun_stream(current_input, **kwargs):
                event.metadata = {"phase": "research", "iteration": iteration}
                yield event
                if event.type == StepEventType.STEP_DELTA and event.delta:
                    research_output += event.delta.content or ""
            
            # 评审阶段
            review_output = ""
            async for event in self.reviewer.arun_stream(
                f"Review:\n{research_output}", **kwargs
            ):
                event.metadata = {"phase": "review", "iteration": iteration}
                yield event
                if event.type == StepEventType.STEP_DELTA and event.delta:
                    review_output += event.delta.content or ""
            
            # 判断是否达标
            if "APPROVED" in review_output:
                break
            
            current_input = f"Improve based on:\n{review_output}"
        
        yield create_workflow_completed_event(
            workflow_id=self._id,
            data={"iterations": iteration}
        )
```

**YAML 引用代码定义的 Workflow**：

```yaml
# configs/workflows/advanced.yaml
type: workflow
name: my_iterative_workflow
class: agio.workflows.custom.iterative_research.IterativeResearchWorkflow
params:
  researcher: research_agent  # 引用已配置的 agent
  reviewer: review_agent
  max_iterations: 5
```

---

## 5. 可观测性设计：Trace/Span

### 5.1 设计思路

借鉴 OpenTelemetry 的分布式追踪模型，但与业务数据（Step）分离：

```
Workflow Run (Trace)
├── Agent A (Span)
│   ├── LLM Call (Span)
│   └── Tool Call (Span)
│       └── Sub-Agent B (Span)  // Agent as Tool
│           ├── LLM Call (Span)
│           └── Tool Call (Span)
├── Agent C (Span)
└── ...
```

### 5.2 Trace/Span 数据模型

```python
# agio/observability/trace.py

from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class SpanKind(str, Enum):
    WORKFLOW = "workflow"
    AGENT = "agent"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"

class SpanStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Span(BaseModel):
    """执行跨度 - 最小追踪单元"""
    
    span_id: str
    trace_id: str               # 顶层 Workflow/Agent Run ID
    parent_span_id: str | None = None
    
    kind: SpanKind
    name: str                   # e.g., "research_agent", "web_search"
    
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    
    status: SpanStatus = SpanStatus.RUNNING
    
    # 上下文属性
    attributes: dict = {}       # {"model": "gpt-4", "tokens": 150}
    
    # 输入输出摘要（不存全量）
    input_preview: str | None = None    # 前 500 字符
    output_preview: str | None = None
    
    # 错误信息
    error: str | None = None


class Trace(BaseModel):
    """完整执行追踪"""
    
    trace_id: str
    root_span_id: str
    
    workflow_id: str | None = None
    session_id: str
    user_id: str | None = None
    
    start_time: datetime
    end_time: datetime | None = None
    
    spans: list[Span] = []
    
    # 聚合指标
    total_tokens: int = 0
    total_tool_calls: int = 0
    total_llm_calls: int = 0
    max_depth: int = 0
```

### 5.3 TraceCollector

```python
# agio/observability/collector.py

class TraceCollector:
    """
    追踪收集器 - 从 StepEvent 流中构建 Trace
    
    设计为中间件模式，不侵入核心执行逻辑
    """
    
    def __init__(self, store: TraceStore):
        self.store = store
    
    async def wrap_stream(
        self, 
        event_stream: AsyncIterator[StepEvent],
        trace_id: str,
    ) -> AsyncIterator[StepEvent]:
        """包装事件流，自动收集追踪信息"""
        
        trace = Trace(
            trace_id=trace_id,
            root_span_id=trace_id,
            start_time=datetime.now(),
        )
        
        span_stack: dict[str, Span] = {}
        
        async for event in event_stream:
            # 根据事件类型更新 Trace
            self._process_event(event, trace, span_stack)
            yield event
        
        # 保存完整 Trace
        trace.end_time = datetime.now()
        await self.store.save_trace(trace)
    
    def _process_event(self, event: StepEvent, trace: Trace, span_stack: dict):
        if event.type == StepEventType.WORKFLOW_STARTED:
            span = Span(
                span_id=event.run_id,
                trace_id=trace.trace_id,
                kind=SpanKind.WORKFLOW,
                name=event.workflow_id,
                start_time=datetime.now(),
            )
            span_stack[event.run_id] = span
            trace.spans.append(span)
            
        elif event.type == StepEventType.AGENT_STARTED:
            parent = span_stack.get(event.workflow_run_id)
            span = Span(
                span_id=event.run_id,
                trace_id=trace.trace_id,
                parent_span_id=parent.span_id if parent else None,
                kind=SpanKind.AGENT,
                name=event.agent_id,
                start_time=datetime.now(),
                attributes={"depth": event.depth},
            )
            span_stack[event.run_id] = span
            trace.spans.append(span)
            trace.max_depth = max(trace.max_depth, event.depth)
            
        elif event.type == StepEventType.STEP_COMPLETED:
            if event.snapshot:
                kind = (
                    SpanKind.TOOL_CALL 
                    if event.snapshot.role.value == "tool" 
                    else SpanKind.LLM_CALL
                )
                span = Span(
                    span_id=event.step_id,
                    trace_id=trace.trace_id,
                    parent_span_id=span_stack.get(event.run_id, {}).span_id,
                    kind=kind,
                    name=event.snapshot.name or "llm_call",
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    status=SpanStatus.COMPLETED,
                )
                trace.spans.append(span)
                
                if kind == SpanKind.TOOL_CALL:
                    trace.total_tool_calls += 1
                else:
                    trace.total_llm_calls += 1
                    if event.snapshot.metrics:
                        trace.total_tokens += event.snapshot.metrics.total_tokens or 0
```

### 5.4 Step vs Trace：职责边界

| 层级 | 模型 | 职责 | 持久化 |
|------|------|------|--------|
| **业务层** | Session/Run/Step | 对话数据、重放、Fork | 完整持久化，永久保留 |
| **可观测层** | Trace/Span | 监控、调试、性能分析 | 精简持久化，可清理 |

```
┌─────────────────────────────────────────────────────────────┐
│  Step (业务数据)                  Trace/Span (可观测数据)    │
│  ═══════════════                  ═══════════════════════   │
│                                                             │
│  ✓ 完整 LLM 消息内容              ✓ 执行时间、延迟          │
│  ✓ Tool 调用参数和结果            ✓ Token 使用统计          │
│  ✓ 支持 Fork/Resume               ✓ 调用链瀑布图            │
│  ✓ 多轮对话历史                   ✓ 错误追踪                │
│  ✓ 永久保留                       ✓ 可定期清理              │
│                                                             │
│  用途：继续对话、重放、分支        用途：性能分析、排查      │
│                                                             │
│              关联方式：run.trace_id = trace.trace_id        │
└─────────────────────────────────────────────────────────────┘
```

### 5.5 可视化：瀑布图

```
┌────────────────────────────────────────────────────────────────┐
│  Trace: abc123 | research_pipeline | 5.2s | ✓                  │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Timeline (ms)  0    1000   2000   3000   4000   5000          │
│                 │      │      │      │      │      │           │
│                                                                 │
│  workflow       ════════════════════════════════════           │
│  ├─ classifier  ══════                                          │
│  │  └─ llm      ═════  (gpt-4, 120 tokens)                     │
│  │                                                              │
│  ├─ researcher       ═══════════════════                       │
│  │  ├─ llm                ══════════  (gpt-4, 450 tokens)      │
│  │  └─ web_search             ════  (3 results)                │
│  │                                                              │
│  └─ summarizer                           ══════════            │
│     └─ llm                               ═════════             │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│  Metrics: 3 LLM calls | 1 Tool call | 720 tokens | $0.02       │
└────────────────────────────────────────────────────────────────┘
```

---

## 6. 数据模型扩展：Step/Run/Session

### 6.1 Step 模型扩展

```python
# agio/domain/models.py - Step 扩展

class Step(BaseModel):
    """
    Step - 核心数据单元
    多 Agent 场景扩展字段（向后兼容，新字段都有默认值）
    """
    
    # === 现有字段 ===
    id: str
    session_id: str
    run_id: str
    sequence: int
    role: MessageRole
    content: str | None
    tool_calls: list[dict] | None
    tool_call_id: str | None
    name: str | None
    metrics: StepMetrics | None
    
    # === 多 Agent 扩展 ===
    
    # Workflow 上下文
    workflow_id: str | None = None        # 所属 Workflow
    workflow_run_id: str | None = None    # Workflow 的 Run ID
    
    # 嵌套上下文
    agent_id: str | None = None           # 执行此 Step 的 Agent ID
    parent_run_id: str | None = None      # 父 Run ID (Agent as Tool)
    depth: int = 0                         # 嵌套深度
    
    # Fork/Resume 支持
    forked_from: str | None = None        # Fork 来源的 Step ID
    branch_path: list[str] | None = None  # 分支路径
```

### 6.2 AgentRun 模型扩展

```python
# agio/domain/models.py - AgentRun 扩展

class AgentRun(BaseModel):
    """Run - 执行元数据"""
    
    # === 现有字段 ===
    id: str
    agent_id: str
    session_id: str
    user_id: str | None
    input_query: str
    status: RunStatus
    response_content: str | None
    metrics: AgentRunMetrics
    
    # === 多 Agent 扩展 ===
    
    # Workflow 上下文
    workflow_id: str | None = None
    workflow_run_id: str | None = None
    
    # 嵌套关系
    parent_run_id: str | None = None      # 父 Run (Agent as Tool)
    child_run_ids: list[str] = []         # 子 Run 列表
    depth: int = 0
    
    # 可观测关联
    trace_id: str | None = None           # 关联的 Trace ID
```

### 6.3 多 Agent Session 结构示例

```
Session (多 Agent 对话)
│
├── Run 1 (Workflow: research_pipeline)
│   │
│   │  workflow_run_id = "wf_001"
│   │
│   ├── Run 1.1 (Agent: classifier, depth=1)
│   │     ├── Step 1 (user)      agent_id="classifier"
│   │     └── Step 2 (assistant)
│   │
│   ├── Run 1.2 (Agent: researcher, depth=1)
│   │     ├── Step 3 (user)      agent_id="researcher"
│   │     ├── Step 4 (assistant) tool_calls=[call_fact_checker]
│   │     │
│   │     │  ┌─ Agent as Tool: fact_checker
│   │     │  │
│   │     │  └── Run 1.2.1 (Agent: fact_checker, depth=2)
│   │     │        ├── Step 5 (user)      parent_run_id="1.2"
│   │     │        └── Step 6 (assistant)
│   │     │
│   │     ├── Step 7 (tool)      tool_call_id=...
│   │     └── Step 8 (assistant)
│   │
│   └── Run 1.3 (Agent: summarizer, depth=1)
│         ├── Step 9 (user)
│         └── Step 10 (assistant)
│
└── Run 2 (继续对话)
    └── ...
```

### 6.4 Repository 接口扩展

```python
# agio/providers/storage/base.py

class AgentRunRepository(ABC):
    """扩展的 Repository 接口"""
    
    # === 现有方法 ===
    async def save_step(self, step: Step): ...
    async def get_steps(self, session_id: str) -> list[Step]: ...
    async def save_run(self, run: AgentRun): ...
    
    # === 多 Agent 扩展 ===
    
    async def get_steps_by_run(
        self, 
        run_id: str,
        include_nested: bool = False,
    ) -> list[Step]:
        """获取特定 Run 的 Steps，可选包含子 Run"""
        ...
    
    async def get_steps_by_depth(
        self,
        session_id: str,
        depth: int,
    ) -> list[Step]:
        """获取特定嵌套深度的 Steps"""
        ...
    
    async def get_run_tree(
        self,
        root_run_id: str,
    ) -> dict:
        """获取 Run 的完整树结构"""
        ...
    
    async def get_steps_until(
        self,
        session_id: str,
        end_step_id: str,
        include_nested: bool = True,
    ) -> list[Step]:
        """获取到指定 Step 为止的所有 Steps（Fork 用）"""
        ...
```

### 6.5 MongoDB Schema 示例

```javascript
// Steps Collection
{
    "_id": "step_001",
    "session_id": "sess_001",
    "run_id": "run_001",
    "sequence": 1,
    "role": "user",
    "content": "Research AI agents",
    
    // 多 Agent 字段
    "workflow_id": "research_pipeline",
    "workflow_run_id": "wf_run_001",
    "agent_id": "classifier",
    "parent_run_id": null,
    "depth": 1,
    
    // Fork 支持
    "forked_from": null,
    "branch_path": []
}

// Indexes
// - (session_id, sequence)
// - (run_id, sequence)
// - (workflow_run_id, depth, sequence)
// - (parent_run_id)
```

---

## 7. Fork/Resume 多 Agent 支持

### 7.1 Fork 策略

```python
# agio/runtime/control.py

async def fork_session(
    session_id: str,
    step_id: str,
    repository: AgentRunRepository,
    include_nested: bool = True,
) -> str:
    """
    从指定 Step 创建新 Session 分支
    
    Args:
        session_id: 原 Session ID
        step_id: Fork 起点的 Step ID
        repository: 存储仓库
        include_nested: 是否包含嵌套子 Run 的 Steps
    
    Returns:
        新 Session ID
    """
    new_session_id = str(uuid4())
    
    # 获取目标 Step
    target_step = await repository.get_step(step_id)
    
    # 获取到目标 Step 为止的所有 Steps
    steps = await repository.get_steps_until(
        session_id=session_id,
        end_step_id=step_id,
        include_nested=include_nested,
    )
    
    # 复制 Steps 到新 Session
    sequence = 1
    for step in steps:
        new_step = step.model_copy(update={
            "id": str(uuid4()),
            "session_id": new_session_id,
            "sequence": sequence,
            "forked_from": step.id,
            "branch_path": (step.branch_path or []) + [new_session_id],
        })
        await repository.save_step(new_step)
        sequence += 1
    
    return new_session_id
```

### 7.2 Resume 策略

```python
# agio/runtime/runner.py

async def resume_workflow(
    session_id: str,
    step_id: str,
    repository: AgentRunRepository,
    config_sys: ConfigSystem,
) -> AsyncIterator[StepEvent]:
    """
    从指定 Step 恢复 Workflow 执行
    """
    step = await repository.get_step(step_id)
    
    if step.workflow_id:
        # Workflow 场景：找到对应位置继续执行
        workflow = config_sys.get(step.workflow_id)
        context = await build_workflow_context_until(
            session_id, step_id, repository
        )
        
        async for event in workflow.resume_from(
            step.agent_id, step, context
        ):
            yield event
    else:
        # 单 Agent 场景：使用现有逻辑
        agent = config_sys.get(step.agent_id)
        async for event in agent.resume_from_step(session_id, step):
            yield event
```

---

## 8. 前端展示设计

### 8.1 多 Agent 执行视图

```
┌────────────────────────────────────────────────────────────┐
│  🔄 Workflow: research_pipeline                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  📍 Agent: researcher (Running...)                         │
│  │  ┌──────────────────────────────────────────────────┐  │
│  │  │ 🤖 Searching for information about AI agents...  │  │
│  │  │                                                   │  │
│  │  │ 🔧 Tool: call_fact_checker                       │  │
│  │  │    └─ 🤖 Sub-Agent: fact_checker                 │  │
│  │  │       │ Verifying claims...                      │  │
│  │  │       └─ ✓ Verified 3/3 claims                   │  │
│  │  │                                                   │  │
│  │  │ Continuing analysis...                           │  │
│  │  └──────────────────────────────────────────────────┘  │
│  │                                                         │
│  ▼                                                         │
│                                                            │
│  ⏳ Agent: summarizer (Pending)                            │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 8.2 前端组件设计

```tsx
// src/components/workflow/WorkflowView.tsx

interface WorkflowViewProps {
  events: StepEvent[];
}

export function WorkflowView({ events }: WorkflowViewProps) {
  // 按 agent_id 分组事件
  const agentGroups = groupEventsByAgent(events);
  
  return (
    <div className="workflow-container">
      {agentGroups.map((group, index) => (
        <AgentPanel
          key={group.agentId}
          agentId={group.agentId}
          events={group.events}
          depth={group.depth}
          status={group.status}
          isLast={index === agentGroups.length - 1}
        />
      ))}
    </div>
  );
}

function AgentPanel({ agentId, events, depth, status }) {
  return (
    <div 
      className="agent-panel"
      style={{ marginLeft: depth * 20 }}
    >
      <div className="agent-header">
        <StatusIcon status={status} />
        <span>Agent: {agentId}</span>
      </div>
      <div className="agent-content">
        {events.map(event => (
          <EventRenderer key={event.step_id} event={event} />
        ))}
      </div>
    </div>
  );
}
```

---


## 9. 模块改动清单

### 9.1 新增模块

| 模块 | 文件 | 职责 |
|------|------|------|
| `workflow/` | `base.py` | `Runnable` 协议、`BaseWorkflow` |
| | `pipeline.py` | `PipelineWorkflow` |
| | `parallel.py` | `ParallelWorkflow` |
| | `router.py` | `RouterWorkflow` |
| | `conditions.py` | 条件表达式求值器 |
| | `tools.py` | `as_tool()`、`RunnableTool` |
| | `introspection.py` | 结构描述、图表生成 |
| `observability/` | `trace.py` | `Trace`、`Span` 模型 |
| | `collector.py` | `TraceCollector` |

### 9.2 修改模块

| 模块 | 改动 | 向后兼容 |
|------|------|----------|
| `domain/events.py` | 新增 Workflow 事件类型、扩展 StepEvent | ✅ |
| `domain/models.py` | Step/Run 增加多 Agent 字段 | ✅ |
| `agent.py` | 实现 `Runnable` 协议，`context` 参数 | ✅ |
| `runtime/runner.py` | Workflow 上下文传递 | ✅ |
| `runtime/control.py` | Fork/Resume 多 Agent 支持 | ✅ |
| `providers/storage/base.py` | Repository 接口扩展 | ✅ |
| `config/builders.py` | 支持构建 Workflow | ✅ |
| `api/routes/chat.py` | 支持调用 Workflow | ✅ |

### 9.3 总体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           用户交互层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │   Web UI    │  │    API      │  │   CLI       │                  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                  │
├─────────┼────────────────┼────────────────┼─────────────────────────┤
│         └────────────────┴────────────────┘                          │
│                          │                                           │
│                    ┌─────▼─────┐                                     │
│                    │ ConfigSys │  ← YAML 配置加载                    │
│                    └─────┬─────┘                                     │
│                          │                                           │
│         ┌────────────────┼────────────────┐                          │
│         │                │                │                          │
│    ┌────▼────┐     ┌─────▼─────┐    ┌─────▼─────┐                   │
│    │  Agent  │     │ Pipeline  │    │ Parallel  │  ← Runnable       │
│    └────┬────┘     │ Workflow  │    │ Workflow  │                   │
│         │          └─────┬─────┘    └─────┬─────┘                   │
│         └────────────────┴────────────────┘                          │
│                          │                                           │
│                    ┌─────▼─────┐                                     │
│                    │StepRunner │  ← 执行引擎                         │
│                    └─────┬─────┘                                     │
│                          │                                           │
│              ┌───────────┴───────────┐                               │
│              │                       │                               │
│        ┌─────▼─────┐          ┌──────▼──────┐                       │
│        │StepExecutor│         │TraceCollector│  ← 可观测性           │
│        └─────┬─────┘          └──────┬──────┘                       │
│              │                       │                               │
│         StepEvent 流 ────────────────┼──────────►  SSE → 前端       │
│                                      │                               │
│                                ┌─────▼─────┐                        │
│                                │TraceStore │  → MongoDB              │
│                                └───────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 附录：复杂性管理策略

### A.1 层级限制

```python
# 运行时检查嵌套深度
def validate_workflow_depth(runnable: Runnable, max_depth: int = 3):
    """防止过深嵌套导致维护困难"""
    ...
```

### A.2 Workflow 图表生成

```python
def generate_workflow_diagram(runnable: Runnable) -> str:
    """生成 Mermaid 图表，帮助理解结构"""
    ...
```

### A.3 结构自省 API

```python
@router.get("/{workflow_name}/structure")
async def get_workflow_structure(workflow_name: str):
    """获取 Workflow 结构描述，用于前端展示和调试"""
    return describe_runnable(config_sys.get(workflow_name))
```

---

> **文档维护说明**  
> 本文档随实现迭代更新，如有变更请同步修改。
