# Multi-Agent 编排系统设计方案

> 版本: v1.0  
> 日期: 2024-12-04  
> 状态: Final Draft

## 目录

1. [概述与目标](#1-概述与目标)
2. [核心概念与术语](#2-核心概念与术语)
3. [Runnable 协议](#3-runnable-协议)
4. [InputMapping 与 OutputStore](#4-inputmapping-与-outputstore)
5. [Stage 与条件表达式](#5-stage-与条件表达式)
6. [Workflow 类型](#6-workflow-类型)
7. [配置系统设计](#7-配置系统设计)
8. [执行引擎](#8-执行引擎)
9. [可观测性设计](#9-可观测性设计)
10. [API 与 Web 集成](#10-api-与-web-集成)
11. [数据模型扩展](#11-数据模型扩展)
12. [模块结构与实施计划](#12-模块结构与实施计划)

---

## 1. 概述与目标

### 1.1 背景

当前 Agio 系统支持单 Agent 与用户交互，具备完整的 Step-based 执行模型、流式输出、Fork/Resume 等能力。为支持更复杂的 AI 应用场景，需要扩展支持多 Agent 协作编排。

### 1.2 设计目标

| 目标 | 说明 |
|------|------|
| **统一抽象** | Agent 和 Workflow 实现相同的 Runnable 协议，可互相嵌套 |
| **YAML 配置化** | 通过 YAML 配置构建复杂执行流程，无需编写代码 |
| **流式输出** | 多 Agent 执行过程实时流式返回，复用现有 SSE 机制 |
| **基础设施复用** | Workflow 复用 Agent 的 API/Web 基础设施 |
| **独立 Session** | 每个 Agent 有独立的 Session，便于隔离、Fork/Resume |
| **可观测性** | 预留 Trace/Span 设计空间，后续可无缝添加 |

### 1.3 设计原则

- **SOLID** - 单一职责，开闭原则
- **KISS** - 保持简单，避免过度设计
- **输入驱动** - Agent 只关心收到什么输入，不关心上下文策略
- **显式配置** - 输入来源必须显式声明，没有隐式继承

### 1.4 核心洞察

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│   每个 Runnable 就是一个函数：                                │
│                                                              │
│       output = runnable(input)                               │
│                                                              │
│   Workflow 的职责就是"连线"：                                 │
│                                                              │
│       把上游的 output 映射到下游的 input                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 1.5 Wire-based 架构

Agio 采用 **Wire-based** 事件流架构，核心设计：

```
API 入口
    │
    ├── 创建 Wire（事件通道）
    ├── 创建 ExecutionContext（包含 wire）
    │
    ▼
Runnable.run(input, context)
    │
    ├── 写入事件到 context.wire
    ├── 所有嵌套执行共享同一个 wire
    │
    ▼
返回 RunOutput（response + metrics）
    │
    ▼
API 层从 wire.read() 读取事件并流式返回
```

**优势**：
- 统一的事件通道，避免 AsyncIterator 链式传递的复杂性
- 所有嵌套执行共享同一个 Wire，事件自然聚合
- API 层统一处理事件流，简化 SSE 实现
- 支持非阻塞执行，执行和流式返回解耦

---

## 2. 核心概念与术语

### 2.1 概念模型

```
┌─────────────────────────────────────────────────────────────┐
│                         Workflow                             │
│                                                              │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐            │
│   │ Stage A │ ──▶  │ Stage B │ ──▶  │ Stage C │            │
│   └────┬────┘      └────┬────┘      └────┬────┘            │
│        │                │                │                  │
│        ▼                ▼                ▼                  │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐            │
│   │Runnable │      │Runnable │      │Runnable │            │
│   │ (Agent) │      │(Workflow)│     │ (Agent) │            │
│   └─────────┘      └─────────┘      └─────────┘            │
│                                                              │
│   OutputStore: { "a": "...", "b": "...", "c": "..." }       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 术语定义

| 术语 | 定义 |
|------|------|
| **Runnable** | 可执行单元协议，接收 input 产出 output（Agent 或 Workflow 都实现此协议） |
| **Stage** | Workflow 中的一个执行阶段，包含 Runnable 引用 + InputMapping + Condition |
| **InputMapping** | 定义如何从 OutputStore 构建当前 Stage 的输入（模板字符串） |
| **OutputStore** | 存储所有 Stage 输出的容器，供后续 Stage 引用 |
| **RunContext** | 执行上下文，携带 trace_id、parent 信息等元数据 |

### 2.3 Workflow 与 Agent 的关系

```
┌─────────────────────────────────────────────────────────────┐
│                      Runnable Protocol                       │
│                                                              │
│         ┌─────────────┐         ┌─────────────┐             │
│         │    Agent    │         │  Workflow   │             │
│         │             │         │             │             │
│         │ - model     │         │ - stages    │             │
│         │ - tools     │         │ - type      │             │
│         │ - prompt    │         │             │             │
│         └──────┬──────┘         └──────┬──────┘             │
│                │                       │                     │
│                └───────────┬───────────┘                     │
│                            │                                 │
│                    ┌───────▼───────┐                        │
│                    │  Unified API  │                        │
│                    │  (run, SSE)   │                        │
│                    └───────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

- **分开配置**：agents.yaml 和 workflows.yaml 分别配置
- **共享协议**：都实现 Runnable 接口
- **复用基础设施**：共享 API 路由、SSE 流、Web UI

---

## 3. Runnable 协议

### 3.1 协议定义

```python
# agio/workflow/protocol.py

from typing import Protocol
from dataclasses import dataclass, field
from agio.runtime.execution_context import ExecutionContext

# RunContext 是 ExecutionContext 的别名（向后兼容）
RunContext = ExecutionContext


@dataclass
class RunMetrics:
    """执行指标"""
    duration: float = 0.0  # 秒
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls_count: int = 0
    # Workflow 专用
    iterations: int | None = None
    stages_executed: int | None = None


@dataclass
class RunOutput:
    """
    执行结果
    
    包含响应和执行指标，替代之前的 str | None 返回类型
    """
    response: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    metrics: RunMetrics = field(default_factory=RunMetrics)
    
    # 额外上下文
    workflow_id: str | None = None
    termination_reason: str | None = None  # "max_steps", "max_iterations" 等
    error: str | None = None


class Runnable(Protocol):
    """
    统一的可执行单元协议
    
    Agent 和 Workflow 都实现此接口，使得：
    1. 可以通过统一的 API 调用
    2. 可以互相嵌套组合
    3. 可以作为 Tool 使用（AgentAsTool、WorkflowAsTool）
    
    Wire-based 执行架构：
    - run() 需要 context.wire（必需）
    - 事件写入到 wire
    - 返回 RunOutput（response + metrics）
    """
    
    @property
    def id(self) -> str:
        """唯一标识"""
        ...
    
    async def run(
        self, 
        input: str,
        *,
        context: ExecutionContext,  # 必需，包含 wire
    ) -> RunOutput:
        """
        执行并写入事件到 context.wire
        
        Args:
            input: 构建好的输入字符串
            context: 执行上下文（必需，必须包含 wire）
            
        Returns:
            RunOutput: 包含响应和执行指标
        """
        ...
```

### 3.2 Agent 实现 Runnable

```python
# agio/agent.py

class Agent:
    """
    Agent 实现 Runnable 协议
    
    要点：
    1. run() 方法实现 Runnable 协议
    2. 使用 context.wire 写入事件
    3. 返回 RunOutput（response + metrics）
    """
    
    def __init__(
        self,
        model: Model,
        tools: list[BaseTool] | None = None,
        name: str = "agio_agent",
        system_prompt: str | None = None,
        session_store: SessionStore | None = None,
        user_id: str | None = None,
    ):
        self._id = name
        self.model = model
        self.tools = tools or []
        self.session_store = session_store
        self.user_id = user_id
        self.system_prompt = system_prompt
    
    @property
    def id(self) -> str:
        return self._id
    
    async def run(
        self, 
        input: str,
        *,
        context: ExecutionContext,  # 必需，包含 wire
    ) -> RunOutput:
        """
        Runnable 协议实现
        
        执行逻辑：
        1. 使用 context.session_id（必需）
        2. 创建 StepRunner
        3. 执行并写入事件到 context.wire
        4. 返回 RunOutput
        """
        from agio.config import ExecutionConfig
        from agio.runtime import StepRunner
        
        session_id = context.session_id  # ExecutionContext 保证 session_id 存在
        current_user_id = context.user_id or self.user_id
        
        session = AgentSession(session_id=session_id, user_id=current_user_id)
        
        runner = StepRunner(
            agent=self,
            config=ExecutionConfig(),
            session_store=self.session_store,
        )
        
        # 执行并写入事件到 wire，返回 RunOutput
        return await runner.run(session, input, context.wire, context=context)
```

### 3.3 StepEvent 扩展

```python
# agio/domain/events.py

class StepEventType(str, Enum):
    """事件类型"""
    
    # Step 级别事件
    STEP_DELTA = "step_delta"  # Step 增量更新
    STEP_COMPLETED = "step_completed"  # Step 完成（最终快照）
    
    # Run 级别事件
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    
    # Workflow 事件
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_SKIPPED = "stage_skipped"  # 条件不满足时跳过
    ITERATION_STARTED = "iteration_started"  # Loop 专用
    BRANCH_STARTED = "branch_started"  # Parallel 专用
    BRANCH_COMPLETED = "branch_completed"
    
    # 错误事件
    ERROR = "error"


class StepEvent(BaseModel):
    """
    统一事件模型
    
    用于实时流式传输 Agent 执行过程到客户端（通过 SSE）
    """
    
    type: StepEventType
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # Step 相关
    step_id: str | None = None
    delta: StepDelta | None = None  # STEP_DELTA 使用
    snapshot: Step | None = None  # STEP_COMPLETED 使用
    data: dict | None = None  # RUN_* 和 ERROR 事件使用
    
    # Workflow 上下文
    stage_id: str | None = None
    branch_id: str | None = None
    iteration: int | None = None
    
    # Workflow 层级信息（前端构建树结构用）
    workflow_type: str | None = None  # "pipeline" | "parallel" | "loop"
    workflow_id: str | None = None
    parent_run_id: str | None = None
    stage_name: str | None = None
    stage_index: int | None = None
    total_stages: int | None = None
    
    # 可观测性
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    depth: int = 0
    
    # 嵌套执行上下文
    nested_runnable_id: str | None = None  # 嵌套的 Agent/Workflow ID
```

---

## 4. InputMapping 与 OutputStore

### 4.1 InputMapping

InputMapping 是连接上下游的关键，使用模板字符串定义如何从已有输出构建当前 Stage 的输入。

```python
# agio/workflow/mapping.py

import re
from dataclasses import dataclass

@dataclass
class InputMapping:
    """
    输入映射 - 定义一个 Stage 的输入来源
    
    模板语法：
    - {query}              : 原始用户输入
    - {stage_id}           : 引用某个 stage 的输出
    - {loop.iteration}     : 当前循环迭代次数
    - {loop.last.stage_id} : 上一次迭代某 stage 的输出
    """
    
    template: str
    
    # 变量匹配正则
    VAR_PATTERN = re.compile(r'\{([^}]+)\}')
    
    def build(self, outputs: dict[str, Any]) -> str:
        """
        根据模板和已有输出构建输入
        
        Args:
            outputs: 已有的输出存储 {"stage_id": "output_content", ...}
            
        Returns:
            构建好的输入字符串
        """
        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            
            # 支持点号访问，如 loop.last.retrieve
            if '.' in var_name:
                return self._resolve_nested(var_name, outputs)
            
            return str(outputs.get(var_name, ""))
        
        return self.VAR_PATTERN.sub(replace_var, self.template)
    
    def _resolve_nested(self, var_path: str, outputs: dict) -> str:
        """解析嵌套变量，如 loop.last.retrieve"""
        parts = var_path.split('.')
        current = outputs
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return ""
            else:
                return ""
        
        return str(current) if current is not None else ""
    
    def get_dependencies(self) -> list[str]:
        """获取模板中引用的所有变量名（用于依赖分析）"""
        return self.VAR_PATTERN.findall(self.template)
```

### 4.2 OutputStore

```python
# agio/workflow/store.py

from dataclasses import dataclass, field
from typing import Any

@dataclass
class OutputStore:
    """
    输出存储 - 管理 Workflow 执行过程中的所有输出
    
    功能：
    1. 存储 stage 输出
    2. 支持循环迭代历史
    3. 提供快照用于并行执行隔离
    """
    
    # 主输出存储
    _outputs: dict[str, Any] = field(default_factory=dict)
    
    # 循环相关
    _loop_iteration: int = 0
    _loop_history: list[dict[str, str]] = field(default_factory=list)
    _loop_last: dict[str, str] = field(default_factory=dict)
    
    def set(self, key: str, value: str):
        """存储输出"""
        self._outputs[key] = value
    
    def get(self, key: str, default: str = "") -> str:
        """获取输出"""
        return self._outputs.get(key, default)
    
    def has(self, key: str) -> bool:
        """检查是否存在某个输出"""
        return key in self._outputs and bool(self._outputs[key])
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典，供 InputMapping 使用"""
        result = dict(self._outputs)
        
        # 添加循环相关变量
        result["loop"] = {
            "iteration": self._loop_iteration,
            "last": self._loop_last,
        }
        
        return result
    
    def start_iteration(self):
        """开始新的循环迭代"""
        if self._loop_iteration > 0:
            # 保存当前迭代的输出到历史
            current_outputs = {
                k: v for k, v in self._outputs.items()
                if k not in ("query", "loop")
            }
            self._loop_history.append(current_outputs)
            self._loop_last = current_outputs
        
        self._loop_iteration += 1
    
    def snapshot(self) -> dict[str, str]:
        """创建当前状态的快照（用于并行执行隔离）"""
        return dict(self._outputs)
    
    def merge(self, branch_id: str, output: str):
        """合并分支输出"""
        self._outputs[branch_id] = output
```

---

## 5. Stage 与条件表达式

### 5.1 Stage 定义

```python
# agio/workflow/stage.py

from dataclasses import dataclass
from typing import Union

@dataclass
class Stage:
    """
    Workflow 中的一个执行阶段
    
    每个 Stage 包含：
    1. id: 唯一标识，也是输出的引用名
    2. runnable: 要执行的单元（Agent/Workflow 的 ID 或实例）
    3. input: 输入模板
    4. condition: 可选的执行条件
    """
    
    id: str
    runnable: Union["Runnable", str]  # Runnable 实例或引用 ID
    input: str  # 模板字符串，如 "{query}\n{intent}"
    condition: str | None = None  # 条件表达式
    
    def get_input_mapping(self) -> InputMapping:
        """获取输入映射"""
        return InputMapping(template=self.input)
    
    def should_execute(self, outputs: dict[str, Any]) -> bool:
        """检查是否应该执行"""
        if self.condition is None:
            return True
        return ConditionEvaluator.evaluate(self.condition, outputs)
```

### 5.2 条件表达式求值器

```python
# agio/workflow/condition.py

import re
import operator
from typing import Any

class ConditionEvaluator:
    """
    条件表达式求值器
    
    支持的语法：
    1. 布尔常量：true, false
    2. 变量引用：{stage_id}（非空为 true）
    3. 否定：not {stage_id}
    4. 比较：{score} > 0.8, {score} >= 0.8, {score} < 0.5
    5. 相等：{result} == 'success', {count} == 5
    6. 不等：{result} != 'error'
    7. 包含：{text} contains 'keyword'
    8. 逻辑与：{a} and {b}
    9. 逻辑或：{a} or {b}
    """
    
    # 变量替换正则
    VAR_PATTERN = re.compile(r'\{([^}]+)\}')
    
    # 操作符映射
    OPERATORS = {
        '==': operator.eq,
        '!=': operator.ne,
        '>': operator.gt,
        '<': operator.lt,
        '>=': operator.ge,
        '<=': operator.le,
    }
    
    @classmethod
    def evaluate(cls, condition: str, outputs: dict[str, Any]) -> bool:
        """
        求值条件表达式
        
        Examples:
            evaluate("true", {})  # True
            evaluate("{intent}", {"intent": "tech"})  # True
            evaluate("not {error}", {"error": ""})  # True
            evaluate("{score} > 0.8", {"score": "0.9"})  # True
            evaluate("{category} == 'tech'", {"category": "tech"})  # True
            evaluate("{text} contains 'error'", {"text": "no error here"})  # True
            evaluate("{a} and {b}", {"a": "yes", "b": "yes"})  # True
        """
        # 1. 处理布尔常量
        condition_lower = condition.strip().lower()
        if condition_lower == "true":
            return True
        if condition_lower == "false":
            return False
        
        # 2. 先进行变量替换（仅替换为值，不求值）
        resolved = cls._resolve_variables(condition, outputs)
        
        # 3. 处理逻辑运算符（按优先级：先 or 再 and）
        if " or " in resolved.lower():
            parts = re.split(r'\s+or\s+', resolved, flags=re.IGNORECASE)
            return any(cls._evaluate_simple(p.strip(), outputs) for p in parts)
        
        if " and " in resolved.lower():
            parts = re.split(r'\s+and\s+', resolved, flags=re.IGNORECASE)
            return all(cls._evaluate_simple(p.strip(), outputs) for p in parts)
        
        # 4. 处理单个条件
        return cls._evaluate_simple(resolved, outputs)
    
    @classmethod
    def _resolve_variables(cls, condition: str, outputs: dict[str, Any]) -> str:
        """替换变量为实际值"""
        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            
            # 处理嵌套访问
            if '.' in var_name:
                parts = var_name.split('.')
                current = outputs
                for part in parts:
                    if isinstance(current, dict):
                        current = current.get(part)
                    else:
                        return ""
                return str(current) if current is not None else ""
            
            value = outputs.get(var_name, "")
            return str(value) if value is not None else ""
        
        return cls.VAR_PATTERN.sub(replace_var, condition)
    
    @classmethod
    def _evaluate_simple(cls, condition: str, outputs: dict[str, Any]) -> bool:
        """求值简单条件（不含 and/or）"""
        condition = condition.strip()
        
        # 处理 not
        if condition.lower().startswith("not "):
            inner = condition[4:].strip()
            return not cls._evaluate_simple(inner, outputs)
        
        # 处理 contains
        if " contains " in condition.lower():
            left, right = re.split(r'\s+contains\s+', condition, flags=re.IGNORECASE)
            left = left.strip().strip("'\"")
            right = right.strip().strip("'\"")
            return right in left
        
        # 处理比较操作符
        for op_str, op_func in cls.OPERATORS.items():
            if op_str in condition:
                parts = condition.split(op_str, 1)
                if len(parts) == 2:
                    left = parts[0].strip().strip("'\"")
                    right = parts[1].strip().strip("'\"")
                    
                    # 尝试数值比较
                    try:
                        left_num = float(left)
                        right_num = float(right)
                        return op_func(left_num, right_num)
                    except ValueError:
                        # 字符串比较
                        return op_func(left, right)
        
        # 默认：非空字符串为 true
        return bool(condition.strip())
```

### 5.3 条件表达式语法速查

| 语法 | 示例 | 说明 |
|------|------|------|
| 布尔常量 | `true`, `false` | 始终为真/假 |
| 变量存在 | `{stage_id}` | 输出非空时为真 |
| 否定 | `not {error}` | 输出为空时为真 |
| 相等 | `{status} == 'success'` | 字符串相等 |
| 不等 | `{status} != 'error'` | 字符串不等 |
| 大于 | `{score} > 0.8` | 数值比较 |
| 小于等于 | `{count} <= 10` | 数值比较 |
| 包含 | `{text} contains 'keyword'` | 子串检查 |
| 逻辑与 | `{a} and {b}` | 都为真时为真 |
| 逻辑或 | `{a} or {b}` | 任一为真时为真 |

### 5.4 条件互斥示例

```yaml
# 使用 classifier 实现互斥分支
stages:
  - id: classifier
    runnable: classifier_agent
    input: "{query}"
    # classifier 输出格式：technical / business / general
    
  - id: tech_handler
    runnable: tech_agent
    input: "{query}"
    condition: "{classifier} == 'technical'"
    
  - id: biz_handler
    runnable: biz_agent
    input: "{query}"
    condition: "{classifier} == 'business'"
    
  - id: general_handler
    runnable: general_agent
    input: "{query}"
    condition: "{classifier} == 'general'"
```

---

## 6. Workflow 类型

### 6.1 类型概览

| 类型 | 说明 | 典型场景 |
|------|------|----------|
| **Pipeline** | 串行执行 A → B → C，按顺序执行通过条件的 Stage | 任务分解、多步处理 |
| **Loop** | 循环执行直到条件不满足 | 迭代优化、质量检查 |
| **Parallel** | 并行执行多个分支，合并结果 | 多视角分析、并发处理 |

### 6.2 BaseWorkflow

```python
# agio/workflow/base.py

from abc import ABC, abstractmethod
from uuid import uuid4

class BaseWorkflow(ABC):
    """
    Workflow 基类，实现 Runnable 协议
    """
    
    def __init__(self, id: str, stages: list[Stage]):
        self._id = id
        self._stages = stages
        self._last_output: str | None = None
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def last_output(self) -> str | None:
        return self._last_output
    
    @abstractmethod
    async def run(
        self, 
        input: str, 
        *, 
        context: RunContext | None = None,
    ) -> AsyncIterator[StepEvent]:
        """子类实现具体执行逻辑"""
        ...
    
    def _create_child_context(
        self, 
        context: RunContext | None, 
        stage: Stage,
    ) -> RunContext:
        """为子 Runnable 创建执行上下文"""
        return RunContext(
            session_id=str(uuid4()),  # 每个 Agent 独立 session
            user_id=context.user_id if context else None,
            trace_id=context.trace_id if context else str(uuid4()),
            parent_span_id=context.parent_span_id if context else None,
            parent_stage_id=stage.id,
            depth=(context.depth if context else 0) + 1,
        )
```

### 6.3 PipelineWorkflow

```python
# agio/workflow/pipeline.py

class PipelineWorkflow(BaseWorkflow):
    """
    串行 Pipeline Workflow
    
    按顺序执行所有 Stage：
    1. 检查每个 Stage 的 condition
    2. 满足条件则执行，不满足则跳过
    3. 每个 Stage 可引用前面所有 Stage 的输出
    """
    
    async def _execute(
        self, 
        input: str, 
        *, 
        context: ExecutionContext,
    ) -> RunOutput:
        from agio.workflow.store import OutputStore
        from agio.workflow.protocol import RunOutput, RunMetrics
        from agio.runtime.event_factory import EventFactory
        
        store = OutputStore()
        store.set("query", input)
        
        ef = EventFactory(context)
        
        # 写入 RUN_STARTED 事件
        await context.wire.write(ef.run_started(input))
        
        final_output = ""
        stages_executed = 0
        
        for idx, stage in enumerate(self._stages):
            outputs_dict = store.to_dict()
            
            # 检查条件
            if not stage.should_execute(outputs_dict):
                await context.wire.write(ef.stage_skipped(
                    stage_id=stage.id,
                    condition=stage.condition,
                    stage_index=idx,
                    total_stages=len(self._stages),
                    workflow_type="pipeline",
                    workflow_id=self._id,
                ))
                continue
            
            # 写入 STAGE_STARTED 事件
            await context.wire.write(ef.stage_started(
                stage_id=stage.id,
                stage_index=idx,
                total_stages=len(self._stages),
                workflow_type="pipeline",
                workflow_id=self._id,
            ))
            
            # 构建输入
            stage_input = stage.get_input_mapping().build(outputs_dict)
            
            # 获取 Runnable 实例
            runnable = self._resolve_runnable(stage.runnable)
            
            # 创建子上下文（独立 session，共享 wire）
            child_context = self._create_child_context(context, stage)
            
            # 执行 Runnable（事件写入到共享的 wire）
            result = await runnable.run(stage_input, context=child_context)
            stage_output = result.response or ""
            
            # 存储输出
            store.set(stage.id, stage_output)
            final_output = stage_output
            stages_executed += 1
            
            # 写入 STAGE_COMPLETED 事件
            await context.wire.write(ef.stage_completed(
                stage_id=stage.id,
                data={"output_length": len(stage_output)},
                stage_index=idx,
                total_stages=len(self._stages),
                workflow_type="pipeline",
                workflow_id=self._id,
            ))
        
        # 写入 RUN_COMPLETED 事件
        metrics = RunMetrics(
            stages_executed=stages_executed,
        )
        await context.wire.write(ef.run_completed(
            response=final_output,
            metrics=metrics.__dict__,
        ))
        
        return RunOutput(
            response=final_output,
            run_id=context.run_id,
            session_id=context.session_id,
            workflow_id=self._id,
            metrics=metrics,
        )
    
    def _resolve_runnable(self, ref: Runnable | str) -> Runnable:
        """解析 Runnable 引用"""
        if isinstance(ref, str):
            if ref not in self._registry:
                raise ValueError(f"Runnable not found in registry: {ref}")
            return self._registry[ref]
        return ref
```

### 6.4 LoopWorkflow

```python
# agio/workflow/loop.py

class LoopWorkflow(BaseWorkflow):
    """
    循环 Workflow
    
    重复执行 stages 直到条件不满足或达到最大迭代次数
    
    特殊变量：
    - {loop.iteration}: 当前迭代次数（从 1 开始）
    - {loop.last.stage_id}: 上一次迭代某 stage 的输出
    """
    
    def __init__(
        self, 
        id: str, 
        stages: list[Stage],
        condition: str = "true",
        max_iterations: int = 10,
    ):
        super().__init__(id, stages)
        self.condition = condition
        self.max_iterations = max_iterations
    
    async def run(
        self, 
        input: str, 
        *, 
        context: RunContext | None = None,
    ) -> AsyncIterator[StepEvent]:
        run_id = str(uuid4())
        store = OutputStore()
        store.set("query", input)
        
        trace_id = context.trace_id if context else str(uuid4())
        
        yield StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            trace_id=trace_id,
            data={
                "workflow_id": self._id, 
                "type": "loop",
                "max_iterations": self.max_iterations,
            },
        )
        
        final_output = ""
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            store.start_iteration()
            
            yield StepEvent(
                type=StepEventType.ITERATION_STARTED,
                run_id=run_id,
                iteration=iteration,
                trace_id=trace_id,
                data={"max_iterations": self.max_iterations},
            )
            
            # 执行所有 stages
            for stage in self._stages:
                outputs_dict = store.to_dict()
                
                if not stage.should_execute(outputs_dict):
                    yield StepEvent(
                        type=StepEventType.STAGE_SKIPPED,
                        run_id=run_id,
                        stage_id=stage.id,
                        iteration=iteration,
                        trace_id=trace_id,
                    )
                    continue
                
                yield StepEvent(
                    type=StepEventType.STAGE_STARTED,
                    run_id=run_id,
                    stage_id=stage.id,
                    iteration=iteration,
                    trace_id=trace_id,
                )
                
                stage_input = stage.get_input_mapping().build(outputs_dict)
                runnable = self._resolve_runnable(stage.runnable)
                child_context = self._create_child_context(context, stage)
                child_context.trace_id = trace_id
                
                stage_output = ""
                async for event in runnable.run(stage_input, context=child_context):
                    event.stage_id = stage.id
                    event.iteration = iteration
                    event.trace_id = trace_id
                    yield event
                    
                    if event.type == StepEventType.RUN_COMPLETED:
                        stage_output = event.data.get("response", "")
                
                store.set(stage.id, stage_output)
                final_output = stage_output
                
                yield StepEvent(
                    type=StepEventType.STAGE_COMPLETED,
                    run_id=run_id,
                    stage_id=stage.id,
                    iteration=iteration,
                    trace_id=trace_id,
                )
            
            # 检查退出条件
            if not ConditionEvaluator.evaluate(self.condition, store.to_dict()):
                break
        
        self._last_output = final_output
        
        yield StepEvent(
            type=StepEventType.RUN_COMPLETED,
            run_id=run_id,
            trace_id=trace_id,
            data={
                "response": final_output,
                "iterations": iteration,
            },
        )
```

### 6.5 ParallelWorkflow

```python
# agio/workflow/parallel.py

import asyncio

class ParallelWorkflow(BaseWorkflow):
    """
    并行 Workflow
    
    同时执行多个分支，每个分支独立运行，最后合并结果
    
    特性：
    1. 各分支使用执行前的快照，互不影响
    2. 结果按分支 ID 存储，可通过 {branch_id} 引用
    3. 支持自定义合并模板
    """
    
    def __init__(
        self, 
        id: str, 
        stages: list[Stage],  # 每个 stage 作为一个分支
        merge_template: str | None = None,
    ):
        super().__init__(id, stages)
        self.merge_template = merge_template
    
    async def run(
        self, 
        input: str, 
        *, 
        context: RunContext | None = None,
    ) -> AsyncIterator[StepEvent]:
        run_id = str(uuid4())
        trace_id = context.trace_id if context else str(uuid4())
        
        # 初始输出快照
        initial_outputs = {"query": input}
        
        yield StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            trace_id=trace_id,
            data={"workflow_id": self._id, "type": "parallel"},
        )
        
        async def run_branch(stage: Stage) -> tuple[str, str, list[StepEvent]]:
            """执行单个分支，收集事件和输出"""
            # 每个分支使用快照，确保隔离
            branch_input = stage.get_input_mapping().build(initial_outputs)
            runnable = self._resolve_runnable(stage.runnable)
            child_context = self._create_child_context(context, stage)
            child_context.trace_id = trace_id
            
            events = []
            output = ""
            
            async for event in runnable.run(branch_input, context=child_context):
                event.branch_id = stage.id
                event.trace_id = trace_id
                events.append(event)
                
                if event.type == StepEventType.RUN_COMPLETED:
                    output = event.data.get("response", "")
            
            return stage.id, output, events
        
        # 并行执行所有分支
        tasks = [run_branch(stage) for stage in self._stages]
        results = await asyncio.gather(*tasks)
        
        # 按完成顺序 yield 事件
        branch_outputs = {}
        for branch_id, output, events in results:
            yield StepEvent(
                type=StepEventType.BRANCH_STARTED,
                run_id=run_id,
                branch_id=branch_id,
                trace_id=trace_id,
            )
            
            for event in events:
                yield event
            
            branch_outputs[branch_id] = output
            
            yield StepEvent(
                type=StepEventType.BRANCH_COMPLETED,
                run_id=run_id,
                branch_id=branch_id,
                trace_id=trace_id,
                data={"output_length": len(output)},
            )
        
        # 合并输出
        if self.merge_template:
            merged = InputMapping(self.merge_template).build(branch_outputs)
        else:
            # 默认合并：按分支 ID 拼接
            merged = "\n\n".join(
                f"[{branch_id}]:\n{output}"
                for branch_id, output in branch_outputs.items()
            )
        
        self._last_output = merged
        
        yield StepEvent(
            type=StepEventType.RUN_COMPLETED,
            run_id=run_id,
            trace_id=trace_id,
            data={
                "response": merged,
                "branch_outputs": {k: len(v) for k, v in branch_outputs.items()},
            },
        )
```

### 6.6 嵌套组合示例

Workflow 可以任意嵌套，因为它们都实现 Runnable 协议：

```yaml
# 嵌套示例：Pipeline 包含 Loop，Loop 包含 Parallel
type: pipeline
id: research_workflow

stages:
  - id: intent
    runnable: intent_agent
    input: "{query}"
  
  - id: plan
    runnable: planner_agent
    input: "{query}\n{intent}"
  
  # 嵌套 Loop
  - id: research_loop
    runnable:
      type: loop
      id: inner_loop
      max_iterations: 3
      condition: "{reflection} contains 'CONTINUE'"
      stages:
        # 嵌套 Parallel
        - id: parallel_research
          runnable:
            type: parallel
            id: multi_source
            branches:
              - id: web
                runnable: web_search_agent
                input: "{plan}"
              - id: db
                runnable: db_search_agent
                input: "{plan}"
            merge_template: |
              Web 结果: {web}
              数据库结果: {db}
          input: "{plan}\n{loop.last.reflection}"
        
        - id: reflection
          runnable: reflection_agent
          input: "{parallel_research}"
    input: "{plan}"
  
  - id: summary
    runnable: summary_agent
    input: "{query}\n{research_loop}"
```

---

## 7. 配置系统设计

### 7.1 配置文件结构

```
configs/
├── agents/
│   ├── intent_agent.yaml
│   ├── planner_agent.yaml
│   └── ...
├── workflows/
│   ├── research_pipeline.yaml
│   ├── iterative_loop.yaml
│   └── ...
└── models/
    └── ...
```

### 7.2 Agent 配置（现有，保持不变）

```yaml
# configs/agents/intent_agent.yaml
id: intent_agent
model: gpt-4
system_prompt: |
  你是一个意图分析专家。
  分析用户输入，识别其核心意图。
tools: []
```

### 7.3 Workflow 配置规范

#### 7.3.1 基本结构

```yaml
# Workflow 基本结构
type: pipeline | loop | parallel
id: workflow_unique_id
stages: [...]         # pipeline 和 loop 使用
branches: [...]       # parallel 使用（或复用 stages）
condition: "..."      # loop 专用：继续条件
max_iterations: 10    # loop 专用：最大迭代次数
merge_template: "..." # parallel 专用：合并模板
```

#### 7.3.2 Stage 配置

```yaml
# Stage 配置
- id: stage_id              # 必填，输出引用名
  runnable: agent_id        # 必填，Agent/Workflow ID 或内联 workflow
  input: "{query}"          # 必填，输入模板
  condition: "..."          # 可选，执行条件
```

#### 7.3.3 变量引用语法

```yaml
# 变量引用
input: "{query}"                    # 原始输入
input: "{stage_id}"                 # 某个 stage 的输出
input: "{stage_a}\n{stage_b}"       # 多个 stage 组合
input: "{loop.iteration}"           # 循环迭代次数
input: "{loop.last.stage_id}"       # 上次迭代的输出
input: |                            # 多行模板
  任务: {query}
  计划: {planner}
  上次结果: {loop.last.research}
```

### 7.4 完整配置示例

#### 7.4.1 简单 Pipeline

```yaml
# configs/workflows/simple_pipeline.yaml
type: pipeline
id: simple_pipeline

stages:
  - id: analyze
    runnable: analyzer_agent
    input: "{query}"
  
  - id: process
    runnable: processor_agent
    input: |
      原始请求: {query}
      分析结果: {analyze}
  
  - id: format
    runnable: formatter_agent
    input: "{process}"
```

#### 7.4.2 迭代 Loop

```yaml
# configs/workflows/iterative_research.yaml
type: loop
id: iterative_research
max_iterations: 5
condition: "{reflection} contains 'CONTINUE'"

stages:
  - id: research
    runnable: research_agent
    input: |
      任务: {query}
      上次研究: {loop.last.research}
      上次反馈: {loop.last.reflection}
  
  - id: verify
    runnable: verify_agent
    input: "{research}"
  
  - id: reflection
    runnable: reflection_agent
    input: |
      研究结果: {research}
      验证结果: {verify}
      请判断是否需要继续研究，输出 CONTINUE 或 COMPLETE。
```

#### 7.4.3 并行 Parallel

```yaml
# configs/workflows/parallel_analysis.yaml
type: parallel
id: parallel_analysis
merge_template: |
  ## 技术分析
  {technical}
  
  ## 商业分析
  {business}
  
  ## 风险评估
  {risk}

stages:
  - id: technical
    runnable: technical_analyst
    input: "{query}"
  
  - id: business
    runnable: business_analyst
    input: "{query}"
  
  - id: risk
    runnable: risk_analyst
    input: "{query}"
```

#### 7.4.4 条件路由

```yaml
# configs/workflows/smart_router.yaml
type: pipeline
id: smart_router

stages:
  # 第一步：分类
  - id: classifier
    runnable: classifier_agent
    input: "{query}"
    # classifier 输出：technical / business / general
  
  # 互斥分支：只有一个会执行
  - id: tech_expert
    runnable: tech_expert_agent
    input: "{query}"
    condition: "{classifier} == 'technical'"
  
  - id: biz_expert
    runnable: biz_expert_agent
    input: "{query}"
    condition: "{classifier} == 'business'"
  
  - id: general_expert
    runnable: general_expert_agent
    input: "{query}"
    condition: "{classifier} == 'general'"
  
  # 最后：格式化输出（引用执行过的分支）
  - id: formatter
    runnable: formatter_agent
    input: |
      原始问题: {query}
      分类: {classifier}
      专家回答: {tech_expert}{biz_expert}{general_expert}
```

---

## 8. 执行引擎

### 8.1 WorkflowEngine

```python
# agio/workflow/engine.py

import yaml
from agio.workflow.protocol import Runnable, RunContext, RunOutput
from agio.workflow.base import BaseWorkflow

class WorkflowEngine:
    """
    Workflow 执行引擎
    
    职责：
    1. 管理 Runnable 注册表（Agent + Workflow）
    2. 从 YAML 加载 Workflow 配置
    3. 提供统一的执行入口
    """
    
    def __init__(self):
        self._registry: dict[str, Runnable] = {}
    
    def register(self, runnable: Runnable):
        """注册 Runnable（Agent 或 Workflow）"""
        self._registry[runnable.id] = runnable
    
    def get(self, id: str) -> Runnable:
        """获取已注册的 Runnable"""
        if id not in self._registry:
            raise ValueError(f"Runnable not found: {id}")
        return self._registry[id]
    
    def load_workflow(self, config_path: str) -> BaseWorkflow:
        """从 YAML 文件加载 Workflow"""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return self.load_workflow_from_dict(config)
    
    def load_workflow_from_dict(self, config: dict) -> BaseWorkflow:
        """从字典配置构建 Workflow"""
        workflow = self._build_workflow(config)
        workflow.set_registry(self._registry)  # 注入注册表
        return workflow
    
    def _build_workflow(self, config: dict) -> BaseWorkflow:
        """根据配置构建 Workflow"""
        workflow_type = config.get("type", "pipeline")
        
        if workflow_type == "pipeline":
            return self._build_pipeline(config)
        elif workflow_type == "loop":
            return self._build_loop(config)
        elif workflow_type == "parallel":
            return self._build_parallel(config)
        else:
            raise ValueError(f"Unknown workflow type: {workflow_type}")
    
    def _build_pipeline(self, config: dict) -> PipelineWorkflow:
        stages = [self._build_stage(s) for s in config.get("stages", [])]
        return PipelineWorkflow(id=config["id"], stages=stages)
    
    def _build_loop(self, config: dict) -> LoopWorkflow:
        stages = [self._build_stage(s) for s in config.get("stages", [])]
        return LoopWorkflow(
            id=config["id"],
            stages=stages,
            condition=config.get("condition", "true"),
            max_iterations=config.get("max_iterations", 10),
        )
    
    def _build_parallel(self, config: dict) -> ParallelWorkflow:
        # parallel 可以用 stages 或 branches
        stages_config = config.get("stages") or config.get("branches", [])
        stages = [self._build_stage(s) for s in stages_config]
        return ParallelWorkflow(
            id=config["id"],
            stages=stages,
            merge_template=config.get("merge_template"),
        )
    
    def _build_stage(self, config: dict) -> Stage:
        """构建 Stage"""
        runnable_config = config.get("runnable")
        
        # 如果 runnable 是嵌套 workflow 配置（dict）
        if isinstance(runnable_config, dict):
            nested_workflow = self._build_workflow(runnable_config)
            self.register(nested_workflow)  # 注册嵌套 workflow
            runnable_ref = nested_workflow.id
        else:
            runnable_ref = runnable_config
        
        return Stage(
            id=config["id"],
            runnable=runnable_ref,
            input=config.get("input", "{query}"),
            condition=config.get("condition"),
        )
    
    async def run(
        self, 
        runnable_id: str, 
        input: str,
        context: RunContext,  # 必需，包含 wire
    ) -> RunOutput:
        """
        执行 Runnable（Agent 或 Workflow）
        
        统一入口，不区分类型。
        事件写入到 context.wire，由 API 层读取并流式返回。
        """
        runnable = self.get(runnable_id)
        return await runnable.run(input, context=context)
```

### 8.2 与现有配置系统集成

```python
# agio/config/loader.py - 扩展

class ConfigLoader:
    """配置加载器，扩展支持 Workflow"""
    
    def __init__(self, config_dir: str):
        self.config_dir = Path(config_dir)
        self.engine = WorkflowEngine()
    
    def load_all(self):
        """加载所有配置"""
        # 1. 先加载 Agents
        self._load_agents()
        
        # 2. 再加载 Workflows（可能引用 Agents）
        self._load_workflows()
    
    def _load_agents(self):
        """加载所有 Agent 配置"""
        agents_dir = self.config_dir / "agents"
        if agents_dir.exists():
            for yaml_file in agents_dir.glob("*.yaml"):
                agent = self._build_agent_from_yaml(yaml_file)
                self.engine.register(agent)
    
    def _load_workflows(self):
        """加载所有 Workflow 配置"""
        workflows_dir = self.config_dir / "workflows"
        if workflows_dir.exists():
            for yaml_file in workflows_dir.glob("*.yaml"):
                workflow = self.engine.load_workflow(str(yaml_file))
                self.engine.register(workflow)
    
    def get_runnable(self, id: str) -> Runnable:
        """获取 Runnable（Agent 或 Workflow）"""
        return self.engine.get(id)
```

---

## 9. 可观测性设计

### 9.1 设计空间预留

可观测性系统将在 multi-agent 核心功能完成后添加，但需要提前预留设计空间。

#### 9.1.1 StepEvent 中的预留字段

```python
class StepEvent(BaseModel):
    # ... 现有字段 ...
    
    # 可观测性预留（已在 3.3 节定义）
    trace_id: str | None = None       # 顶层追踪 ID
    span_id: str | None = None        # 当前跨度 ID
    parent_span_id: str | None = None # 父跨度 ID
    depth: int = 0                    # 嵌套深度
```

#### 9.1.2 RunContext 中的预留字段

```python
@dataclass
class RunContext:
    # ... 现有字段 ...
    
    # 可观测性预留（已在 3.1 节定义）
    trace_id: str | None = None
    parent_span_id: str | None = None
```

### 9.2 Trace/Span 模型（后续实现）

```python
# agio/observability/trace.py （后续实现）

class SpanKind(str, Enum):
    WORKFLOW = "workflow"
    AGENT = "agent"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"

class SpanStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Span:
    """执行跨度 - 最小追踪单元"""
    
    span_id: str
    trace_id: str
    parent_span_id: str | None = None
    
    kind: SpanKind
    name: str  # e.g., "research_agent", "web_search"
    
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    
    status: SpanStatus = SpanStatus.RUNNING
    
    # 上下文属性
    attributes: dict = field(default_factory=dict)
    
    # 输入输出摘要
    input_preview: str | None = None
    output_preview: str | None = None
    
    # 错误信息
    error: str | None = None


@dataclass
class Trace:
    """完整执行追踪"""
    
    trace_id: str
    root_span_id: str
    
    workflow_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    
    start_time: datetime
    end_time: datetime | None = None
    
    spans: list[Span] = field(default_factory=list)
    
    # 聚合指标
    total_tokens: int = 0
    total_tool_calls: int = 0
    total_llm_calls: int = 0
    max_depth: int = 0
```

### 9.3 TraceCollector（后续实现）

```python
# agio/observability/collector.py （后续实现）

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
    ) -> AsyncIterator[StepEvent]:
        """包装事件流，自动收集追踪信息"""
        trace: Trace | None = None
        span_stack: dict[str, Span] = {}
        
        async for event in event_stream:
            # 根据事件类型构建/更新 Trace
            self._process_event(event, trace, span_stack)
            yield event
        
        # 保存完整 Trace
        if trace:
            trace.end_time = datetime.now()
            await self.store.save_trace(trace)
    
    def _process_event(self, event: StepEvent, trace: Trace, span_stack: dict):
        """处理单个事件，更新追踪信息"""
        # 后续实现
        pass
```

### 9.4 可视化：瀑布图（后续实现）

```
┌────────────────────────────────────────────────────────────────┐
│  Trace: abc123 | research_pipeline | 5.2s | ✓                  │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Timeline (ms)  0    1000   2000   3000   4000   5000          │
│                 │      │      │      │      │      │           │
│                                                                 │
│  workflow       ════════════════════════════════════           │
│  ├─ intent      ══════                                          │
│  │  └─ llm      ═════  (gpt-4, 120 tokens)                     │
│  │                                                              │
│  ├─ planner          ═══════════                               │
│  │  └─ llm                ══════  (gpt-4, 200 tokens)          │
│  │                                                              │
│  └─ research_loop              ═════════════════               │
│     ├─ iter 1                  ════════                        │
│     │  ├─ parallel             ═══════                         │
│     │  │  ├─ web               ══════  (web_search)            │
│     │  │  └─ db                ════  (db_search)               │
│     │  └─ reflection           ═════                           │
│     └─ iter 2                          ════════                │
│        └─ ...                                                  │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│  Metrics: 5 LLM calls | 2 Tool calls | 850 tokens | $0.03      │
└────────────────────────────────────────────────────────────────┘
```

---

## 10. API 与 Web 集成

### 10.1 统一 API 路由

Agent 和 Workflow 共享同一套 API，通过 `runnable_id` 调用：

```python
# agio/api/routes/runnables.py

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from agio.runtime.wire import Wire
from agio.runtime.execution_context import ExecutionContext

router = APIRouter(prefix="/runnables", tags=["Runnable"])


@router.post("/{runnable_id}/run")
async def run_runnable(
    runnable_id: str,
    request: RunRequest,
    config_system: ConfigSystem = Depends(get_config_system),
):
    """
    执行 Runnable（Agent 或 Workflow）
    
    统一入口，前端无需区分类型。
    使用 Wire-based 架构：创建 Wire，执行写入事件，API 层读取并流式返回。
    """
    # 创建 Wire（事件通道）
    wire = Wire()
    
    # 创建 ExecutionContext
    context = ExecutionContext(
        run_id=str(uuid4()),
        session_id=request.session_id or str(uuid4()),
        wire=wire,
        user_id=request.user_id,
        trace_id=str(uuid4()),
    )
    
    # 启动执行任务（非阻塞）
    async def execute():
        try:
            engine = config_system.workflow_engine
            await engine.run(
                runnable_id=runnable_id,
                input=request.query,
                context=context,
            )
        finally:
            await wire.close()
    
    task = asyncio.create_task(execute())
    
    # 流式返回事件
    async def event_generator():
        try:
            async for event in wire.read():
                yield {
                    "event": event.type.value,
                    "data": event.model_dump_json(),
                }
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    
    return EventSourceResponse(event_generator())


@router.get("/{runnable_id}/info")
async def get_runnable_info(runnable_id: str):
    """获取 Runnable 信息"""
    runnable = config_loader.engine.get(runnable_id)
    return describe_runnable(runnable)


@router.get("/")
async def list_runnables():
    """列出所有可用的 Runnable"""
    return {
        "agents": [...],
        "workflows": [...],
    }


# Request/Response 模型
class RunRequest(BaseModel):
    query: str
    session_id: str | None = None
    user_id: str | None = None
```

### 10.2 保留原有 Agent API

为保持兼容，原有 `/agents/{agent_id}/run` 路由保留：

```python
# agio/api/routes/agent.py

@router.post("/{agent_id}/run")
async def run_agent(agent_id: str, request: RunRequest):
    """
    原有 Agent API，内部转发到统一路由
    """
    # 转发到 runnable API
    return await run_runnable(agent_id, request)
```

### 10.3 Workflow 专用 API（可选）

```python
# agio/api/routes/workflow.py

router = APIRouter(prefix="/workflows", tags=["Workflow"])


@router.get("/{workflow_id}/structure")
async def get_workflow_structure(workflow_id: str):
    """
    获取 Workflow 结构（用于前端可视化）
    """
    workflow = config_loader.engine.get(workflow_id)
    return describe_workflow_structure(workflow)


def describe_workflow_structure(workflow: BaseWorkflow) -> dict:
    """描述 Workflow 结构"""
    return {
        "id": workflow.id,
        "type": workflow.__class__.__name__,
        "stages": [
            {
                "id": stage.id,
                "runnable": stage.runnable if isinstance(stage.runnable, str) else stage.runnable.id,
                "input_template": stage.input,
                "condition": stage.condition,
            }
            for stage in workflow._stages
        ],
    }
```

### 10.4 前端集成

```typescript
// 前端处理 Workflow 事件流

interface WorkflowEvent {
  type: 'run_started' | 'run_completed' | 'stage_started' | 'stage_completed' 
      | 'stage_skipped' | 'step_delta' | 'step_completed' | 'iteration_started'
      | 'branch_started' | 'branch_completed';
  run_id: string;
  stage_id?: string;
  branch_id?: string;
  iteration?: number;
  trace_id?: string;
  depth?: number;
  data?: Record<string, any>;
  delta?: { content?: string; tool_calls?: any[] };
  snapshot?: Step;
}

function WorkflowViewer({ runnableId, query }: Props) {
  const [stages, setStages] = useState<StageState[]>([]);
  const [currentIteration, setCurrentIteration] = useState(0);
  
  useEffect(() => {
    const eventSource = new EventSource(
      `/api/runnables/${runnableId}/run`,
      { method: 'POST', body: JSON.stringify({ query }) }
    );
    
    eventSource.onmessage = (e) => {
      const event: WorkflowEvent = JSON.parse(e.data);
      
      switch (event.type) {
        case 'stage_started':
          setStages(prev => [...prev, { 
            id: event.stage_id!, 
            status: 'running',
            iteration: event.iteration,
          }]);
          break;
          
        case 'stage_completed':
          setStages(prev => prev.map(s => 
            s.id === event.stage_id ? { ...s, status: 'completed' } : s
          ));
          break;
          
        case 'stage_skipped':
          setStages(prev => [...prev, { 
            id: event.stage_id!, 
            status: 'skipped',
          }]);
          break;
          
        case 'iteration_started':
          setCurrentIteration(event.iteration!);
          break;
          
        case 'step_delta':
          // 更新当前 stage 的输出内容
          updateStageContent(event.stage_id!, event.delta?.content);
          break;
      }
    };
    
    return () => eventSource.close();
  }, [runnableId, query]);
  
  return (
    <div className="workflow-viewer">
      {currentIteration > 0 && (
        <div className="iteration-badge">迭代 {currentIteration}</div>
      )}
      {stages.map(stage => (
        <StagePanel key={`${stage.id}-${stage.iteration}`} stage={stage} />
      ))}
    </div>
  );
}
```

---

## 11. 数据模型扩展

### 11.1 Step 模型扩展

```python
# agio/domain/models.py - Step 扩展

class Step(BaseModel):
    """
    Step - 核心数据单元
    
    多 Agent 场景扩展字段（所有新字段都有默认值，保持兼容）
    """
    
    # === 现有字段（保持不变） ===
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
    created_at: datetime
    
    # === 多 Agent 扩展 ===
    
    # Workflow 上下文
    workflow_id: str | None = None        # 所属 Workflow ID
    stage_id: str | None = None           # 所属 Stage ID
    
    # 可观测性
    trace_id: str | None = None           # 追踪 ID
    span_id: str | None = None            # 跨度 ID
    parent_span_id: str | None = None     # 父跨度 ID
    depth: int = 0                        # 嵌套深度
```

### 11.2 AgentRun 模型扩展

```python
# agio/domain/models.py - AgentRun 扩展

class AgentRun(BaseModel):
    """
    Run - 执行元数据
    
    多 Agent 场景扩展字段
    """
    
    # === 现有字段（保持不变） ===
    id: str
    agent_id: str
    session_id: str
    user_id: str | None
    input_query: str
    status: RunStatus
    response_content: str | None
    metrics: AgentRunMetrics
    created_at: datetime
    updated_at: datetime
    
    # === 多 Agent 扩展 ===
    
    # Workflow 上下文
    workflow_id: str | None = None        # 所属 Workflow ID
    stage_id: str | None = None           # 所属 Stage ID
    
    # 可观测性
    trace_id: str | None = None           # 关联的 Trace ID
```

### 11.3 Session 隔离设计

每个 Agent 在 Workflow 中执行时使用独立的 Session：

```
Workflow Run (trace_id = "trace_001")
│
├─► Stage: intent
│   └─► Agent: intent_agent
│       └─► Session: sess_001 (独立)
│           ├─► Step 1 (user)
│           └─► Step 2 (assistant)
│
├─► Stage: planner  
│   └─► Agent: planner_agent
│       └─► Session: sess_002 (独立)
│           ├─► Step 1 (user)
│           └─► Step 2 (assistant)
│
└─► Stage: researcher
    └─► Agent: researcher_agent
        └─► Session: sess_003 (独立)
            ├─► Step 1 (user)
            ├─► Step 2 (assistant, tool_calls)
            ├─► Step 3 (tool)
            └─► Step 4 (assistant)
```

**优势**：
- 每个 Agent 的历史独立，便于 Fork/Resume
- 便于单独查看某个 Agent 的执行过程
- 便于单独优化某个 Agent

**关联方式**：
- 通过 `trace_id` 关联同一 Workflow 执行的所有 Session
- 通过 `workflow_id` + `stage_id` 定位 Session 所属位置

### 11.4 SessionStore 扩展

```python
# agio/providers/storage/base.py - 扩展

class SessionStore(ABC):
    """扩展的 SessionStore 接口"""
    
    # === 现有方法（保持不变） ===
    async def save_step(self, step: Step): ...
    async def get_steps(self, session_id: str) -> list[Step]: ...
    async def save_run(self, run: AgentRun): ...
    async def get_last_step(self, session_id: str) -> Step | None: ...
    
    # === 多 Agent 扩展 ===
    
    async def get_sessions_by_trace(
        self, 
        trace_id: str,
    ) -> list[str]:
        """获取同一 Trace 下的所有 Session ID"""
        ...
    
    async def get_runs_by_trace(
        self, 
        trace_id: str,
    ) -> list[AgentRun]:
        """获取同一 Trace 下的所有 Run"""
        ...
    
    async def get_workflow_execution(
        self,
        trace_id: str,
    ) -> dict:
        """
        获取完整的 Workflow 执行信息
        
        Returns:
            {
                "trace_id": "...",
                "stages": [
                    {"stage_id": "...", "session_id": "...", "status": "..."},
                    ...
                ]
            }
        """
        ...
```

---

## 12. 模块结构与实施计划

### 12.1 最终模块结构

```
agio/
├── workflow/                        # 新增：Workflow 模块
│   ├── __init__.py                  # 导出公共接口
│   ├── protocol.py                  # Runnable 协议 + RunContext
│   ├── mapping.py                   # InputMapping
│   ├── store.py                     # OutputStore
│   ├── stage.py                     # Stage 定义
│   ├── condition.py                 # ConditionEvaluator
│   ├── base.py                      # BaseWorkflow
│   ├── pipeline.py                  # PipelineWorkflow
│   ├── loop.py                      # LoopWorkflow
│   ├── parallel.py                  # ParallelWorkflow
│   └── engine.py                    # WorkflowEngine
│
├── observability/                   # 预留：可观测性模块
│   ├── __init__.py
│   ├── trace.py                     # Trace/Span 模型（预留）
│   └── collector.py                 # TraceCollector（预留）
│
├── agent.py                         # 修改：实现 Runnable 协议
├── domain/
│   ├── models.py                    # 修改：扩展 Step/Run 字段
│   └── events.py                    # 修改：扩展事件类型
│
├── config/
│   └── loader.py                    # 修改：支持加载 Workflow
│
├── api/
│   └── routes/
│       ├── runnable.py              # 新增：统一 Runnable API
│       └── workflow.py              # 新增：Workflow 专用 API
│
└── runtime/
    └── runner.py                    # 小幅修改：支持 context 传递
```

### 12.2 实施阶段

#### 第一阶段：核心协议

| 任务 | 文件 | 说明 |
|------|------|------|
| 定义 Runnable 协议 | `workflow/protocol.py` | 包含 RunContext |
| 实现 InputMapping | `workflow/mapping.py` | 模板解析 |
| 实现 OutputStore | `workflow/store.py` | 输出存储 |
| 实现 Stage | `workflow/stage.py` | Stage 定义 |
| 实现 ConditionEvaluator | `workflow/condition.py` | 条件求值 |

#### 第二阶段：Workflow 类型

| 任务 | 文件 | 说明 |
|------|------|------|
| 实现 BaseWorkflow | `workflow/base.py` | 基类 |
| 实现 PipelineWorkflow | `workflow/pipeline.py` | 串行执行 |
| 实现 LoopWorkflow | `workflow/loop.py` | 循环执行 |
| 实现 ParallelWorkflow | `workflow/parallel.py` | 并行执行 |

#### 第三阶段：Agent 改造

| 任务 | 文件 | 说明 |
|------|------|------|
| Agent 实现 Runnable | `agent.py` | 添加 run() 方法 |
| 扩展 StepEvent | `domain/events.py` | 新增事件类型 |
| 扩展数据模型 | `domain/models.py` | 新增字段 |

#### 第四阶段：配置与引擎

| 任务 | 文件 | 说明 |
|------|------|------|
| 实现 WorkflowEngine | `workflow/engine.py` | YAML 加载、注册表 |
| 扩展 ConfigLoader | `config/loader.py` | 支持 Workflow |

#### 第五阶段：API 集成

| 任务 | 文件 | 说明 |
|------|------|------|
| 统一 Runnable API | `api/routes/runnable.py` | 新增 |
| Workflow API | `api/routes/workflow.py` | 新增 |

#### 第六阶段：测试与文档

| 任务 | 说明 |
|------|------|
| 单元测试 | 各模块单元测试 |
| 集成测试 | 完整 Workflow 执行测试 |
| 示例配置 | 创建示例 Workflow 配置 |

### 12.3 依赖关系

```
                    ┌─────────────────┐
                    │    protocol     │
                    │  (Runnable,     │
                    │   RunContext)   │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
   ┌───────────┐      ┌───────────┐      ┌───────────┐
   │  mapping  │      │   store   │      │ condition │
   └─────┬─────┘      └─────┬─────┘      └─────┬─────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                            ▼
                     ┌───────────┐
                     │   stage   │
                     └─────┬─────┘
                           │
                           ▼
                     ┌───────────┐
                     │   base    │
                     │(BaseWork- │
                     │  flow)    │
                     └─────┬─────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
   ┌───────────┐    ┌───────────┐    ┌───────────┐
   │ pipeline  │    │   loop    │    │ parallel  │
   └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
         │                │                │
         └────────────────┼────────────────┘
                          │
                          ▼
                    ┌───────────┐
                    │  engine   │
                    └───────────┘
```

### 12.4 改动清单汇总

| 模块 | 改动类型 | 说明 |
|------|----------|------|
| `workflow/` | 新增 | 整个 Workflow 模块 |
| `agent.py` | 修改 | 实现 Runnable 协议 |
| `domain/events.py` | 修改 | 新增事件类型和字段 |
| `domain/models.py` | 修改 | Step/Run 扩展字段 |
| `config/loader.py` | 修改 | 支持 Workflow 加载 |
| `api/routes/` | 新增 | 统一 API 路由 |
| `providers/storage/base.py` | 修改 | SessionStore 接口扩展 |

---

## 附录：设计决策记录

### A.1 为什么每个 Agent 使用独立 Session？

**决策**：Workflow 中每个 Agent 执行时创建独立的 Session

**理由**：
1. 隔离性好，各 Agent 历史不互相干扰
2. 便于单独 Fork/Resume 某个 Agent 的执行
3. 便于单独查看和优化某个 Agent
4. 通过 trace_id 仍可关联整个 Workflow 执行

### A.2 为什么用模板字符串而不是结构化配置？

**决策**：使用 `"{query}\n{intent}"` 模板语法

**理由**：
1. 直观易懂，降低学习成本
2. 灵活组合，无需预定义所有可能的组合方式
3. 与 prompt engineering 习惯一致

### A.3 为什么不用 DAG 而用嵌套结构？

**决策**：使用嵌套的 Pipeline/Loop/Parallel 结构

**理由**：
1. 嵌套结构更直观，符合人类思维
2. 避免 DAG 带来的复杂依赖分析
3. YAML 配置文件更易读写

### A.4 为什么保留条件表达式而不是全用代码？

**决策**：支持 `{score} > 0.8`、`{text} contains 'keyword'` 等条件语法

**理由**：
1. 简单条件无需写代码，配置即可
2. 表达力足够覆盖常见场景
3. 复杂逻辑可通过 classifier agent 转化为简单条件

---

## 附录：变量引用速查表

| 变量 | 说明 | 使用场景 |
|------|------|----------|
| `{query}` | 原始用户输入 | 任何 Stage |
| `{stage_id}` | 某个 Stage 的输出 | 引用前序 Stage |
| `{loop.iteration}` | 当前循环迭代次数 | Loop 内的 Stage |
| `{loop.last.stage_id}` | 上次迭代某 Stage 的输出 | Loop 内需要历史 |


