# Multi-Agent 编排设计方案

> 版本: v1.0  
> 日期: 2024-12-04  
> 状态: Draft  
> 关联文档: [multi-agent-refactor-design.md](./multi-agent-refactor-design.md)

## 目录

1. [设计理念](#1-设计理念)
2. [核心概念](#2-核心概念)
3. [Runnable 协议](#3-runnable-协议)
4. [输入映射 InputMapping](#4-输入映射-inputmapping)
5. [Workflow 类型](#5-workflow-类型)
6. [执行引擎](#6-执行引擎)
7. [YAML 配置规范](#7-yaml-配置规范)
8. [完整示例：Research Workflow](#8-完整示例research-workflow)
9. [与现有架构集成](#9-与现有架构集成)

---

## 1. 设计理念

### 1.1 核心洞察

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

**类比编程**：

```python
# 传统函数调用
intent = intent_agent(query)
plan = planner_agent(f"需求: {query}\n意图: {intent}")
result = research_agent(f"计划: {plan}")

# Workflow 做的就是配置这个"连线"过程
```

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **输入驱动** | Agent 不关心"上下文策略"，只关心收到什么输入 |
| **显式配置** | 输入来源必须显式声明，没有隐式继承 |
| **最小权限** | 不配置输入来源，就看不到任何上游输出 |
| **统一模型** | Pipeline/Loop/Parallel 都遵循相同的输入输出规则 |
| **配置化** | 任意复杂的 Workflow 都可以通过 YAML 配置 |

### 1.3 与 ContextPolicy 方案的对比

| 方面 | ContextPolicy（废弃） | InputMapping（采用） |
|------|----------------------|---------------------|
| 核心概念 | 可见性策略 | 输入模板 |
| 思维模型 | "我能看到什么" | "我需要什么" |
| 配置复杂度 | 8 种 visibility + 多参数 | 1 个 template 字符串 |
| 默认行为 | 需理解各种策略 | 不配置就没有输入 |
| 学习成本 | 高 | 低（只需会写模板） |

---

## 2. 核心概念

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
│   输出存储: { "a": "...", "b": "...", "c": "..." }          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 术语定义

| 术语 | 定义 |
|------|------|
| **Runnable** | 可执行单元，接收 input 产出 output（Agent 或 Workflow） |
| **Stage** | Workflow 中的一个执行阶段，包含 Runnable + InputMapping |
| **InputMapping** | 定义如何从已有输出构建当前 Stage 的输入 |
| **OutputStore** | 存储所有 Stage 输出的容器，供后续 Stage 引用 |

### 2.3 执行流程

```
1. 用户输入 query
       │
       ▼
2. 初始化 OutputStore: {"query": query}
       │
       ▼
3. 遍历 Stages:
       │
       ├─▶ Stage A
       │      │
       │      ├─ 根据 InputMapping 从 OutputStore 构建 input
       │      ├─ 执行 Runnable(input)
       │      └─ 将 output 存入 OutputStore["a"]
       │
       ├─▶ Stage B
       │      │
       │      ├─ InputMapping 可引用 {query}, {a}
       │      ├─ 执行 Runnable(input)
       │      └─ 将 output 存入 OutputStore["b"]
       │
       └─▶ Stage C
              │
              └─ InputMapping 可引用 {query}, {a}, {b}
       │
       ▼
4. 返回最后一个 Stage 的 output
```

---

## 3. Runnable 协议

### 3.1 协议定义

```python
# agio/workflow/protocol.py

from typing import Protocol, AsyncIterator

class Runnable(Protocol):
    """
    统一的可执行单元协议
    
    核心约定：
    1. 接收字符串 input
    2. 流式返回 StepEvent
    3. 执行结束后可获取 final_output
    """
    
    @property
    def id(self) -> str:
        """唯一标识"""
        ...
    
    async def run(self, input: str) -> AsyncIterator[StepEvent]:
        """
        执行并返回事件流
        
        Args:
            input: 构建好的输入字符串
            
        Yields:
            StepEvent: 执行过程中的事件
            
        最后一个事件应为 RUN_COMPLETED，包含 final_output
        """
        ...
    
    @property
    def last_output(self) -> str | None:
        """获取最近一次执行的最终输出"""
        ...
```

### 3.2 Agent 实现 Runnable

```python
# agio/agent.py

class Agent:
    """Agent 实现 Runnable 协议"""
    
    def __init__(
        self,
        id: str,
        model: Model,
        system_prompt: str | None = None,
        tools: list[BaseTool] | None = None,
        # ... 其他配置
    ):
        self._id = id
        self._model = model
        self._system_prompt = system_prompt
        self._tools = tools or []
        self._last_output: str | None = None
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def last_output(self) -> str | None:
        return self._last_output
    
    async def run(self, input: str) -> AsyncIterator[StepEvent]:
        """
        执行 Agent
        
        关键逻辑：
        1. input 作为 user message
        2. 执行 LLM ↔ Tool 循环
        3. 最后一个无 tool_calls 的 assistant message 作为 final_output
        """
        self._last_output = None
        final_content: str | None = None
        
        # 创建 Run
        run_id = str(uuid4())
        yield StepEvent(type=StepEventType.RUN_STARTED, run_id=run_id)
        
        try:
            # 执行 LLM ↔ Tool 循环
            async for event in self._executor.execute(
                input=input,
                system_prompt=self._system_prompt,
                tools=self._tools,
            ):
                yield event
                
                # 追踪最终输出
                if event.type == StepEventType.STEP_COMPLETED:
                    step = event.snapshot
                    if step and step.role == MessageRole.ASSISTANT:
                        if not step.tool_calls:
                            # 没有 tool_calls 的 assistant message = 最终回答
                            final_content = step.content
            
            self._last_output = final_content
            
            yield StepEvent(
                type=StepEventType.RUN_COMPLETED,
                run_id=run_id,
                data={"output": final_content},
            )
            
        except Exception as e:
            yield StepEvent(
                type=StepEventType.RUN_FAILED,
                run_id=run_id,
                error=str(e),
            )
            raise
```

### 3.3 Workflow 实现 Runnable

```python
# agio/workflow/base.py

class BaseWorkflow(ABC):
    """Workflow 基类，实现 Runnable 协议"""
    
    def __init__(self, id: str):
        self._id = id
        self._last_output: str | None = None
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def last_output(self) -> str | None:
        return self._last_output
    
    @abstractmethod
    async def run(self, input: str) -> AsyncIterator[StepEvent]:
        """子类实现具体执行逻辑"""
        ...
```

### 3.4 StepEvent 扩展

```python
# agio/domain/events.py

class StepEventType(str, Enum):
    # 现有事件
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    STEP_DELTA = "step_delta"
    STEP_COMPLETED = "step_completed"
    
    # Workflow 事件
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    LOOP_ITERATION = "loop_iteration"
    BRANCH_STARTED = "branch_started"
    BRANCH_COMPLETED = "branch_completed"


@dataclass
class StepEvent:
    type: StepEventType
    run_id: str | None = None
    step_id: str | None = None
    
    # Workflow 上下文
    stage_id: str | None = None
    branch_id: str | None = None
    iteration: int | None = None
    depth: int = 0
    
    # 内容
    delta: StepDelta | None = None
    snapshot: Step | None = None
    data: dict | None = None
    error: str | None = None
```

---

## 4. 输入映射 InputMapping

### 4.1 核心设计

InputMapping 是连接上下游的关键，它定义了如何从已有输出构建当前 Stage 的输入。

```python
# agio/workflow/mapping.py

from dataclasses import dataclass
import re

@dataclass
class InputMapping:
    """
    输入映射 - 定义一个 Stage 的输入来源
    
    使用模板字符串，支持变量替换：
    - {query}          : 原始用户输入
    - {stage_id}       : 引用某个 stage 的输出
    - {loop.iteration} : 当前循环迭代次数
    - {loop.last.xxx}  : 上一次迭代某 stage 的输出
    """
    
    template: str
    
    # 变量匹配正则
    VAR_PATTERN = re.compile(r'\{([^}]+)\}')
    
    def build(self, outputs: dict[str, str]) -> str:
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
            
            return outputs.get(var_name, f"[未找到: {var_name}]")
        
        return self.VAR_PATTERN.sub(replace_var, self.template)
    
    def _resolve_nested(self, var_path: str, outputs: dict[str, str]) -> str:
        """解析嵌套变量，如 loop.last.retrieve"""
        parts = var_path.split('.')
        current = outputs
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return f"[未找到: {var_path}]"
            else:
                return f"[无法解析: {var_path}]"
        
        return str(current) if current is not None else ""
    
    def get_dependencies(self) -> list[str]:
        """获取模板中引用的所有变量名"""
        return self.VAR_PATTERN.findall(self.template)
    
    @classmethod
    def from_string(cls, template: str) -> "InputMapping":
        """从字符串创建"""
        return cls(template=template)
    
    @classmethod
    def passthrough(cls, stage_id: str) -> "InputMapping":
        """创建直接传递某个 stage 输出的映射"""
        return cls(template=f"{{{stage_id}}}")
```

### 4.2 Stage 定义

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
    2. runnable: 要执行的单元
    3. input: 输入映射
    4. condition: 可选的执行条件
    """
    
    id: str
    runnable: Union["Runnable", str]  # Runnable 实例或引用名
    input: Union[InputMapping, str]   # InputMapping 或简化的模板字符串
    condition: str | None = None      # 条件表达式
    
    def __post_init__(self):
        # 自动转换字符串为 InputMapping
        if isinstance(self.input, str):
            self.input = InputMapping(template=self.input)
    
    def should_execute(self, outputs: dict[str, str]) -> bool:
        """检查是否应该执行"""
        if self.condition is None:
            return True
        return evaluate_condition(self.condition, outputs)


def evaluate_condition(condition: str, outputs: dict[str, str]) -> bool:
    """
    安全地求值条件表达式
    
    支持的语法：
    - "true" / "false"
    - "{stage_id}"  (非空则为 true)
    - "not {stage_id}"
    - "{stage_id} == 'value'"
    - "{score} > 0.8"
    - "{stage_id} contains 'keyword'"
    """
    # 先进行变量替换
    mapping = InputMapping(template=condition)
    resolved = mapping.build(outputs)
    
    # 简单的条件求值（生产环境建议用 simpleeval 等安全库）
    resolved_lower = resolved.strip().lower()
    
    if resolved_lower == "true":
        return True
    if resolved_lower == "false":
        return False
    if resolved_lower.startswith("not "):
        inner = resolved_lower[4:].strip()
        return not bool(inner)
    if " == " in resolved:
        left, right = resolved.split(" == ", 1)
        return left.strip().strip("'\"") == right.strip().strip("'\"")
    if " > " in resolved:
        left, right = resolved.split(" > ", 1)
        try:
            return float(left.strip()) > float(right.strip())
        except ValueError:
            return False
    if " contains " in resolved_lower:
        left, right = resolved.lower().split(" contains ", 1)
        return right.strip().strip("'\"") in left.strip()
    
    # 默认：非空字符串为 true
    return bool(resolved.strip())
```

### 4.3 OutputStore

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
    3. 支持嵌套访问
    """
    
    # 主输出存储
    _outputs: dict[str, str] = field(default_factory=dict)
    
    # 循环相关
    _loop_iteration: int = 0
    _loop_history: list[dict[str, str]] = field(default_factory=list)
    _loop_last: dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        # 初始化特殊变量
        self._outputs["loop"] = {}
    
    def set(self, key: str, value: str):
        """存储输出"""
        self._outputs[key] = value
    
    def get(self, key: str, default: str = "") -> str:
        """获取输出"""
        return self._outputs.get(key, default)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典，供 InputMapping 使用"""
        result = dict(self._outputs)
        
        # 添加循环相关变量
        result["loop"] = {
            "iteration": str(self._loop_iteration),
            "last": self._loop_last,
        }
        
        return result
    
    def start_iteration(self):
        """开始新的循环迭代"""
        # 保存当前迭代的输出到历史
        if self._loop_iteration > 0:
            current_outputs = {
                k: v for k, v in self._outputs.items()
                if k not in ("query", "loop")
            }
            self._loop_history.append(current_outputs)
            self._loop_last = current_outputs
        
        self._loop_iteration += 1
        
        # 清除当前迭代的输出（保留 query 和全局输出）
        preserved = {
            "query": self._outputs.get("query", ""),
        }
        # 保留循环外的输出（通过 preserve_keys 配置）
        self._outputs = preserved
    
    def get_iteration_history(self, count: int = 1) -> list[dict[str, str]]:
        """获取最近 N 次迭代的历史"""
        return self._loop_history[-count:] if self._loop_history else []
    
    def snapshot(self) -> dict[str, str]:
        """创建当前状态的快照（用于并行执行）"""
        return dict(self._outputs)
    
    def merge(self, other: dict[str, str]):
        """合并其他输出（用于并行结果合并）"""
        self._outputs.update(other)
```

### 4.4 使用示例

```python
# 创建 Stage
stage = Stage(
    id="planner",
    runnable="planner_agent",  # 引用已注册的 agent
    input="{query}\n\n意图分析结果:\n{intent}",  # 简化语法
)

# 或使用 InputMapping
stage = Stage(
    id="planner",
    runnable=planner_agent,
    input=InputMapping(
        template="""
用户需求: {query}

意图分析:
{intent}

请制定研究计划。
"""
    ),
)

# 条件执行
stage = Stage(
    id="deep_research",
    runnable="deep_research_agent",
    input="{planner}",
    condition="{intent} contains 'complex'",  # 仅当意图包含 'complex' 时执行
)
```

---

## 5. Workflow 类型

### 5.1 类型概览

| 类型 | 说明 | 典型场景 |
|------|------|----------|
| **Pipeline** | 串行执行 A → B → C | 任务分解、多步处理 |
| **Loop** | 循环执行直到条件满足 | 迭代优化、质量检查 |
| **Parallel** | 并行执行多个分支 | 多视角分析、并发处理 |
| **Conditional** | 条件分支选择 | 路由、动态选择 |

### 5.2 Pipeline Workflow

```python
# agio/workflow/pipeline.py

from dataclasses import dataclass

@dataclass
class PipelineWorkflow(BaseWorkflow):
    """
    串行 Pipeline Workflow
    
    按顺序执行所有 Stage，每个 Stage 可引用前面所有 Stage 的输出
    """
    
    stages: list[Stage]
    
    async def run(self, input: str) -> AsyncIterator[StepEvent]:
        run_id = str(uuid4())
        store = OutputStore()
        store.set("query", input)
        
        yield StepEvent(type=StepEventType.RUN_STARTED, run_id=run_id)
        
        final_output = ""
        
        for stage in self.stages:
            # 检查条件
            if not stage.should_execute(store.to_dict()):
                continue
            
            yield StepEvent(
                type=StepEventType.STAGE_STARTED,
                stage_id=stage.id,
            )
            
            # 构建输入
            stage_input = stage.input.build(store.to_dict())
            
            # 执行
            runnable = self._resolve_runnable(stage.runnable)
            stage_output = ""
            
            async for event in runnable.run(stage_input):
                # 添加 stage 上下文
                event.stage_id = stage.id
                yield event
                
                # 提取输出
                if event.type == StepEventType.RUN_COMPLETED:
                    stage_output = event.data.get("output", "")
            
            # 存储输出
            store.set(stage.id, stage_output)
            final_output = stage_output
            
            yield StepEvent(
                type=StepEventType.STAGE_COMPLETED,
                stage_id=stage.id,
                data={"output": stage_output},
            )
        
        self._last_output = final_output
        
        yield StepEvent(
            type=StepEventType.RUN_COMPLETED,
            run_id=run_id,
            data={"output": final_output},
        )
```

### 5.3 Loop Workflow

```python
# agio/workflow/loop.py

@dataclass
class LoopWorkflow(BaseWorkflow):
    """
    循环 Workflow
    
    重复执行 stages 直到条件不满足或达到最大迭代次数
    
    特殊变量：
    - {loop.iteration}: 当前迭代次数（从 1 开始）
    - {loop.last.stage_id}: 上一次迭代某 stage 的输出
    """
    
    stages: list[Stage]
    condition: str = "true"       # 继续条件，false 时退出
    max_iterations: int = 10
    
    # 可选：从父级继承的输出键（循环内可访问）
    inherit_keys: list[str] | None = None
    
    async def run(self, input: str) -> AsyncIterator[StepEvent]:
        run_id = str(uuid4())
        store = OutputStore()
        store.set("query", input)
        
        # 如果有父级传入的输出，解析并存储
        if self.inherit_keys:
            parent_outputs = self._parse_inherited(input)
            for key in self.inherit_keys:
                if key in parent_outputs:
                    store.set(key, parent_outputs[key])
        
        yield StepEvent(type=StepEventType.RUN_STARTED, run_id=run_id)
        
        final_output = ""
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            store.start_iteration()
            
            yield StepEvent(
                type=StepEventType.LOOP_ITERATION,
                iteration=iteration,
                data={"max_iterations": self.max_iterations},
            )
            
            # 执行所有 stages
            for stage in self.stages:
                if not stage.should_execute(store.to_dict()):
                    continue
                
                stage_input = stage.input.build(store.to_dict())
                runnable = self._resolve_runnable(stage.runnable)
                stage_output = ""
                
                async for event in runnable.run(stage_input):
                    event.stage_id = stage.id
                    event.iteration = iteration
                    yield event
                    
                    if event.type == StepEventType.RUN_COMPLETED:
                        stage_output = event.data.get("output", "")
                
                store.set(stage.id, stage_output)
                final_output = stage_output
            
            # 检查退出条件
            if not evaluate_condition(self.condition, store.to_dict()):
                break
        
        self._last_output = final_output
        
        yield StepEvent(
            type=StepEventType.RUN_COMPLETED,
            run_id=run_id,
            data={
                "output": final_output,
                "iterations": iteration,
            },
        )
```

### 5.4 Parallel Workflow

```python
# agio/workflow/parallel.py

@dataclass
class ParallelWorkflow(BaseWorkflow):
    """
    并行 Workflow
    
    同时执行多个分支，每个分支独立运行，最后合并结果
    
    关键特性：
    1. 各分支使用执行前的快照，互不影响
    2. 结果按分支 ID 存储，可通过 {branch_id} 引用
    3. 支持自定义合并策略
    """
    
    branches: list[Stage]  # 每个分支是一个 Stage
    merge_template: str | None = None  # 自定义合并模板
    
    async def run(self, input: str) -> AsyncIterator[StepEvent]:
        run_id = str(uuid4())
        
        # 创建初始输出存储
        initial_outputs = {"query": input}
        
        yield StepEvent(type=StepEventType.RUN_STARTED, run_id=run_id)
        
        async def run_branch(branch: Stage) -> tuple[str, str, list[StepEvent]]:
            """执行单个分支"""
            # 每个分支使用快照，确保隔离
            branch_input = branch.input.build(initial_outputs)
            runnable = self._resolve_runnable(branch.runnable)
            
            events = []
            output = ""
            
            async for event in runnable.run(branch_input):
                event.branch_id = branch.id
                events.append(event)
                
                if event.type == StepEventType.RUN_COMPLETED:
                    output = event.data.get("output", "")
            
            return branch.id, output, events
        
        # 并行执行所有分支
        tasks = [run_branch(branch) for branch in self.branches]
        results = await asyncio.gather(*tasks)
        
        # 按完成顺序 yield 事件
        branch_outputs = {}
        for branch_id, output, events in results:
            yield StepEvent(
                type=StepEventType.BRANCH_STARTED,
                branch_id=branch_id,
            )
            
            for event in events:
                yield event
            
            branch_outputs[branch_id] = output
            
            yield StepEvent(
                type=StepEventType.BRANCH_COMPLETED,
                branch_id=branch_id,
                data={"output": output},
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
            data={
                "output": merged,
                "branch_outputs": branch_outputs,
            },
        )
```

### 5.5 Conditional Workflow

```python
# agio/workflow/conditional.py

@dataclass
class Route:
    """条件路由"""
    condition: str      # 条件表达式
    stage: Stage        # 满足条件时执行的 Stage


@dataclass
class ConditionalWorkflow(BaseWorkflow):
    """
    条件分支 Workflow
    
    根据条件选择执行哪个分支
    """
    
    routes: list[Route]
    default: Stage | None = None  # 无匹配时的默认分支
    
    async def run(self, input: str) -> AsyncIterator[StepEvent]:
        run_id = str(uuid4())
        outputs = {"query": input}
        
        yield StepEvent(type=StepEventType.RUN_STARTED, run_id=run_id)
        
        # 找到第一个匹配的路由
        selected_stage: Stage | None = None
        for route in self.routes:
            if evaluate_condition(route.condition, outputs):
                selected_stage = route.stage
                break
        
        if selected_stage is None:
            selected_stage = self.default
        
        final_output = ""
        
        if selected_stage:
            stage_input = selected_stage.input.build(outputs)
            runnable = self._resolve_runnable(selected_stage.runnable)
            
            async for event in runnable.run(stage_input):
                event.stage_id = selected_stage.id
                yield event
                
                if event.type == StepEventType.RUN_COMPLETED:
                    final_output = event.data.get("output", "")
        
        self._last_output = final_output
        
        yield StepEvent(
            type=StepEventType.RUN_COMPLETED,
            run_id=run_id,
            data={"output": final_output},
        )
```

### 5.6 嵌套组合

Workflow 可以任意嵌套，因为它们都实现 Runnable 协议：

```python
# 嵌套示例：Pipeline 包含 Loop，Loop 包含 Parallel

research_workflow = PipelineWorkflow(
    id="research",
    stages=[
        Stage(id="intent", runnable=intent_agent, input="{query}"),
        Stage(id="plan", runnable=planner_agent, input="{query}\n{intent}"),
        
        # 嵌套 Loop
        Stage(
            id="research_loop",
            runnable=LoopWorkflow(
                id="inner_loop",
                stages=[
                    # 嵌套 Parallel
                    Stage(
                        id="parallel_research",
                        runnable=ParallelWorkflow(
                            id="parallel",
                            branches=[
                                Stage(id="retrieval", runnable=retrieve_agent, input="{plan}"),
                                Stage(id="analysis", runnable=analyze_agent, input="{plan}"),
                            ],
                        ),
                        input="{plan}\n{loop.last.parallel_research}",
                    ),
                ],
                condition="{parallel_research} contains 'CONTINUE'",
                max_iterations=3,
            ),
            input="{plan}",
        ),
        
        Stage(id="summary", runnable=summary_agent, input="{research_loop}"),
    ],
)
```

---

## 6. 执行引擎

### 6.1 WorkflowEngine

```python
# agio/workflow/engine.py

class WorkflowEngine:
    """
    Workflow 执行引擎
    
    职责：
    1. 管理 Runnable 注册表
    2. 从 YAML 加载 Workflow 配置
    3. 提供统一的执行入口
    """
    
    def __init__(self):
        self._registry: dict[str, Runnable] = {}
    
    def register(self, runnable: Runnable):
        """注册 Runnable"""
        self._registry[runnable.id] = runnable
    
    def register_agent(self, agent: Agent):
        """注册 Agent"""
        self._registry[agent.id] = agent
    
    def get(self, id: str) -> Runnable:
        """获取已注册的 Runnable"""
        if id not in self._registry:
            raise ValueError(f"Runnable not found: {id}")
        return self._registry[id]
    
    def resolve_runnable(self, ref: Runnable | str) -> Runnable:
        """解析 Runnable 引用"""
        if isinstance(ref, str):
            return self.get(ref)
        return ref
    
    def load_workflow(self, config_path: str) -> BaseWorkflow:
        """从 YAML 文件加载 Workflow"""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return self._build_workflow(config)
    
    def _build_workflow(self, config: dict) -> BaseWorkflow:
        """根据配置构建 Workflow"""
        workflow_type = config.get("type", "pipeline")
        
        if workflow_type == "pipeline":
            return self._build_pipeline(config)
        elif workflow_type == "loop":
            return self._build_loop(config)
        elif workflow_type == "parallel":
            return self._build_parallel(config)
        elif workflow_type == "conditional":
            return self._build_conditional(config)
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
            inherit_keys=config.get("inherit_keys"),
        )
    
    def _build_parallel(self, config: dict) -> ParallelWorkflow:
        branches = [self._build_stage(b) for b in config.get("branches", [])]
        return ParallelWorkflow(
            id=config["id"],
            branches=branches,
            merge_template=config.get("merge_template"),
        )
    
    def _build_conditional(self, config: dict) -> ConditionalWorkflow:
        routes = []
        for r in config.get("routes", []):
            stage = self._build_stage(r["stage"])
            routes.append(Route(condition=r["condition"], stage=stage))
        
        default = None
        if "default" in config:
            default = self._build_stage(config["default"])
        
        return ConditionalWorkflow(id=config["id"], routes=routes, default=default)
    
    def _build_stage(self, config: dict) -> Stage:
        """构建 Stage"""
        # 如果 runnable 是嵌套 workflow 配置
        runnable = config.get("runnable")
        if isinstance(runnable, dict):
            runnable = self._build_workflow(runnable)
        
        return Stage(
            id=config["id"],
            runnable=runnable,
            input=config.get("input", "{query}"),
            condition=config.get("condition"),
        )
    
    async def run(
        self, 
        workflow_id: str, 
        query: str,
        session_id: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        """执行 Workflow"""
        workflow = self.get(workflow_id)
        
        async for event in workflow.run(query):
            yield event
```

### 6.2 与现有 Agent 系统集成

```python
# agio/workflow/integration.py

class WorkflowAdapter:
    """
    适配器：让现有 Agent 系统支持 Workflow
    """
    
    def __init__(self, engine: WorkflowEngine, config_system: ConfigSystem):
        self.engine = engine
        self.config_system = config_system
        self._register_agents()
    
    def _register_agents(self):
        """自动注册所有已配置的 Agent"""
        for agent_config in self.config_system.get_agents():
            agent = self.config_system.build_agent(agent_config)
            self.engine.register_agent(agent)
    
    async def run_workflow(
        self,
        workflow_id: str,
        query: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        """
        执行 Workflow，兼容现有的 Session 机制
        """
        # 如果提供了 session_id，可以加载历史上下文
        session_context = ""
        if session_id:
            history = await self._load_session_history(session_id)
            if history:
                session_context = self._format_history(history)
        
        # 将 session 历史作为 query 的一部分传入
        full_input = query
        if session_context:
            full_input = f"{session_context}\n\n当前请求: {query}"
        
        async for event in self.engine.run(workflow_id, full_input, session_id):
            yield event
```

---

## 7. YAML 配置规范

### 7.1 基本结构

```yaml
# workflow 基本结构
type: pipeline | loop | parallel | conditional
id: workflow_unique_id
stages: [...]  # pipeline 和 loop
branches: [...] # parallel
routes: [...]   # conditional
```

### 7.2 Stage 配置

```yaml
# Stage 配置
- id: stage_id              # 必填，输出引用名
  runnable: agent_id        # 必填，Agent ID 或嵌套 workflow
  input: "{query}"          # 必填，输入模板
  condition: "..."          # 可选，执行条件
```

### 7.3 变量引用语法

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

### 7.4 条件语法

```yaml
# 条件表达式
condition: "true"                     # 始终执行
condition: "false"                    # 不执行
condition: "{stage_id}"               # 输出非空时执行
condition: "not {stage_id}"           # 输出为空时执行
condition: "{score} > 0.8"            # 数值比较
condition: "{result} == 'success'"    # 字符串相等
condition: "{text} contains 'error'"  # 包含检查
```

### 7.5 完整配置示例

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

branches:
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

```yaml
# configs/workflows/smart_router.yaml
type: conditional
id: smart_router

routes:
  - condition: "{query} contains '代码'"
    stage:
      id: code_expert
      runnable: code_agent
      input: "{query}"
  
  - condition: "{query} contains '数据'"
    stage:
      id: data_expert
      runnable: data_agent
      input: "{query}"

default:
  id: general
  runnable: general_agent
  input: "{query}"
```

---

## 8. 完整示例：Research Workflow

### 8.1 场景回顾

```
Pipeline (research_workflow)
├─► IntentAgent
├─► PlannerAgent
├─► OuterLoop (外层循环)
│       └─► Parallel
│               ├─► InnerLoop (内层循环)
│               │       ├─► RetrieveAgent
│               │       ├─► VerifyAgent
│               │       └─► Reflection-1
│               │
│               └─► Reflection-2
├─► SummaryAgent
└─► ReportAgent
```

### 8.2 需求分析

| Agent | 需要的输入 | 配置方式 |
|-------|-----------|---------|
| IntentAgent | 原始查询 | `input: "{query}"` |
| PlannerAgent | 查询 + 意图 | `input: "{query}\n{intent}"` |
| RetrieveAgent | 计划 + 上次迭代结果 | `input: "{plan}\n{loop.last.retrieve}"` |
| VerifyAgent | 检索结果 | `input: "{retrieve}"` |
| Reflection-1 | 检索 + 验证 | `input: "{retrieve}\n{verify}"` |
| Reflection-2 | 计划 + 内层循环结果 | `input: "{plan}\n{inner_loop}"` |
| SummaryAgent | 查询 + 研究结果 | `input: "{query}\n{outer_loop}"` |
| ReportAgent | 摘要 | `input: "{summary}"` |

### 8.3 YAML 配置

```yaml
# configs/workflows/research_workflow.yaml
type: pipeline
id: research_workflow

stages:
  # Stage 1: 意图识别
  - id: intent
    runnable: intent_agent
    input: "{query}"
  
  # Stage 2: 计划制定
  - id: plan
    runnable: planner_agent
    input: |
      用户需求: {query}
      意图分析: {intent}
      
      请制定详细的研究计划。
  
  # Stage 3: 外层研究循环
  - id: outer_loop
    runnable:
      type: loop
      id: outer_research_loop
      max_iterations: 3
      condition: "{parallel_result} contains 'CONTINUE'"
      inherit_keys: ["plan"]  # 循环内可访问 plan
      
      stages:
        # 并行执行：内层循环 + 独立反思
        - id: parallel_result
          runnable:
            type: parallel
            id: research_parallel
            merge_template: |
              ## 深度研究结果
              {inner_loop}
              
              ## 元反思
              {meta_reflection}
            
            branches:
              # Branch A: 内层检索循环
              - id: inner_loop
                runnable:
                  type: loop
                  id: retrieval_loop
                  max_iterations: 5
                  condition: "{reflection} contains 'CONTINUE'"
                  inherit_keys: ["plan"]
                  
                  stages:
                    - id: retrieve
                      runnable: retrieve_agent
                      input: |
                        研究计划: {plan}
                        当前迭代: {loop.iteration}
                        上次检索: {loop.last.retrieve}
                        上次反馈: {loop.last.reflection}
                    
                    - id: verify
                      runnable: verify_agent
                      input: |
                        检索结果:
                        {retrieve}
                        
                        请验证以上信息的准确性。
                    
                    - id: reflection
                      runnable: reflection_agent
                      input: |
                        检索结果: {retrieve}
                        验证结果: {verify}
                        
                        请评估研究进度。如需继续，输出 CONTINUE；如已完成，输出 COMPLETE。
                
                input: "{plan}"
              
              # Branch B: 元反思
              - id: meta_reflection
                runnable: meta_reflection_agent
                input: |
                  研究计划: {plan}
                  当前进度: {loop.last.parallel_result}
                  
                  请从更高层次评估研究方向是否正确。
          
          input: "{plan}\n{loop.last.parallel_result}"
    
    input: "{plan}"
  
  # Stage 4: 总结
  - id: summary
    runnable: summary_agent
    input: |
      原始需求: {query}
      研究计划: {plan}
      研究结果: {outer_loop}
      
      请总结研究发现。
  
  # Stage 5: 报告生成
  - id: report
    runnable: report_agent
    input: |
      {summary}
      
      请生成正式研究报告。
```

### 8.4 Python 代码等价实现

```python
# 使用 Python 代码构建相同的 Workflow

from agio.workflow import (
    PipelineWorkflow, LoopWorkflow, ParallelWorkflow, Stage
)

research_workflow = PipelineWorkflow(
    id="research_workflow",
    stages=[
        # Stage 1: 意图识别
        Stage(
            id="intent",
            runnable="intent_agent",
            input="{query}",
        ),
        
        # Stage 2: 计划制定
        Stage(
            id="plan",
            runnable="planner_agent",
            input="用户需求: {query}\n意图分析: {intent}",
        ),
        
        # Stage 3: 外层研究循环
        Stage(
            id="outer_loop",
            runnable=LoopWorkflow(
                id="outer_research_loop",
                max_iterations=3,
                condition="{parallel_result} contains 'CONTINUE'",
                inherit_keys=["plan"],
                stages=[
                    Stage(
                        id="parallel_result",
                        runnable=ParallelWorkflow(
                            id="research_parallel",
                            merge_template="## 深度研究\n{inner_loop}\n\n## 元反思\n{meta_reflection}",
                            branches=[
                                # 内层循环
                                Stage(
                                    id="inner_loop",
                                    runnable=LoopWorkflow(
                                        id="retrieval_loop",
                                        max_iterations=5,
                                        condition="{reflection} contains 'CONTINUE'",
                                        inherit_keys=["plan"],
                                        stages=[
                                            Stage(
                                                id="retrieve",
                                                runnable="retrieve_agent",
                                                input="{plan}\n上次: {loop.last.retrieve}",
                                            ),
                                            Stage(
                                                id="verify",
                                                runnable="verify_agent",
                                                input="{retrieve}",
                                            ),
                                            Stage(
                                                id="reflection",
                                                runnable="reflection_agent",
                                                input="{retrieve}\n{verify}",
                                            ),
                                        ],
                                    ),
                                    input="{plan}",
                                ),
                                # 元反思
                                Stage(
                                    id="meta_reflection",
                                    runnable="meta_reflection_agent",
                                    input="{plan}\n{loop.last.parallel_result}",
                                ),
                            ],
                        ),
                        input="{plan}\n{loop.last.parallel_result}",
                    ),
                ],
            ),
            input="{plan}",
        ),
        
        # Stage 4: 总结
        Stage(
            id="summary",
            runnable="summary_agent",
            input="{query}\n{plan}\n{outer_loop}",
        ),
        
        # Stage 5: 报告
        Stage(
            id="report",
            runnable="report_agent",
            input="{summary}",
        ),
    ],
)
```

### 8.5 执行流程示意

```
用户输入: "研究量子计算的最新进展"
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│ OutputStore: {"query": "研究量子计算的最新进展"}                  │
└─────────────────────────────────────────────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ IntentAgent   │  input: "{query}"
        └───────┬───────┘
                │ output: "用户想了解量子计算领域的最新研究突破"
                ▼
┌─────────────────────────────────────────────────────────────────┐
│ OutputStore: {"query": "...", "intent": "用户想了解..."}         │
└─────────────────────────────────────────────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ PlannerAgent  │  input: "{query}\n{intent}"
        └───────┬───────┘
                │ output: "1. 检索学术论文 2. 验证信息 3. 整理报告"
                ▼
┌─────────────────────────────────────────────────────────────────┐
│ OutputStore: {..., "plan": "1. 检索学术论文..."}                 │
└─────────────────────────────────────────────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │  OuterLoop    │  ◀─────────────────────┐
        │  Iteration 1  │                        │
        └───────┬───────┘                        │
                │                                │
        ┌───────┴───────┐                        │
        ▼               ▼                        │
   ┌─────────┐    ┌─────────────┐               │
   │InnerLoop│    │MetaReflect  │               │
   │ 5 iters │    │             │               │
   └────┬────┘    └──────┬──────┘               │
        │                │                       │
        └───────┬────────┘                       │
                │ merge                          │
                ▼                                │
        parallel_result                          │
                │                                │
                │ condition: contains 'CONTINUE'?│
                └────────────────────────────────┘
                │ (最终 COMPLETE)
                ▼
        ┌───────────────┐
        │ SummaryAgent  │  input: "{query}\n{plan}\n{outer_loop}"
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │ ReportAgent   │  input: "{summary}"
        └───────┬───────┘
                │
                ▼
            最终报告
```

---

## 9. 与现有架构集成

### 9.1 模块结构

```
agio/
├── workflow/                    # 新增：Workflow 模块
│   ├── __init__.py
│   ├── protocol.py              # Runnable 协议定义
│   ├── mapping.py               # InputMapping
│   ├── stage.py                 # Stage 定义
│   ├── store.py                 # OutputStore
│   ├── base.py                  # BaseWorkflow
│   ├── pipeline.py              # PipelineWorkflow
│   ├── loop.py                  # LoopWorkflow
│   ├── parallel.py              # ParallelWorkflow
│   ├── conditional.py           # ConditionalWorkflow
│   ├── engine.py                # WorkflowEngine
│   └── loader.py                # YAML 配置加载
│
├── agent.py                     # 修改：实现 Runnable 协议
├── domain/
│   └── events.py                # 修改：扩展 StepEvent
│
└── config/
    └── workflows/               # 新增：Workflow 配置目录
        └── *.yaml
```

### 9.2 改动清单

| 模块 | 改动类型 | 说明 |
|------|----------|------|
| `workflow/` | 新增 | 整个 Workflow 模块 |
| `agent.py` | 修改 | 添加 `run()` 方法，实现 Runnable 协议 |
| `domain/events.py` | 修改 | 添加 Workflow 相关事件类型 |
| `config/` | 修改 | 支持加载 Workflow 配置 |
| `api/routes/` | 修改 | 添加 Workflow 执行接口 |

### 9.3 Agent 改动

```python
# agio/agent.py

class Agent:
    """
    改动点：
    1. 添加 run() 方法实现 Runnable 协议
    2. 添加 last_output 属性
    3. 现有 arun_stream() 可保留作为内部实现或废弃
    """
    
    def __init__(self, id: str, ...):
        self._id = id
        self._last_output: str | None = None
        # ... 现有初始化代码
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def last_output(self) -> str | None:
        return self._last_output
    
    async def run(self, input: str) -> AsyncIterator[StepEvent]:
        """
        Runnable 协议实现
        
        将 input 作为 user message，执行 LLM 循环，
        最后一个无 tool_calls 的 assistant message 作为 final_output
        """
        self._last_output = None
        
        # 使用现有的执行逻辑
        async for event in self._execute_internal(input):
            yield event
            
            # 追踪最终输出
            if event.type == StepEventType.STEP_COMPLETED:
                if self._is_final_answer(event.snapshot):
                    self._last_output = event.snapshot.content
        
        # 发送完成事件
        yield StepEvent(
            type=StepEventType.RUN_COMPLETED,
            data={"output": self._last_output},
        )
    
    def _is_final_answer(self, step: Step | None) -> bool:
        """判断是否为最终回答"""
        if not step:
            return False
        return (
            step.role == MessageRole.ASSISTANT 
            and not step.tool_calls
        )
```

### 9.4 API 集成

```python
# agio/api/routes/workflow.py

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/workflows", tags=["Workflow"])

@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    request: WorkflowRunRequest,
):
    """执行 Workflow"""
    
    async def event_generator():
        async for event in workflow_engine.run(
            workflow_id=workflow_id,
            query=request.query,
            session_id=request.session_id,
        ):
            yield {
                "event": event.type.value,
                "data": event.model_dump_json(),
            }
    
    return EventSourceResponse(event_generator())


@router.get("/{workflow_id}/structure")
async def get_workflow_structure(workflow_id: str):
    """获取 Workflow 结构（用于前端展示）"""
    workflow = workflow_engine.get(workflow_id)
    return describe_workflow(workflow)
```

### 9.5 前端集成

```typescript
// 前端处理 Workflow 事件流

interface WorkflowEvent {
  type: 'stage_started' | 'stage_completed' | 'step_delta' | 'run_completed' | ...;
  stage_id?: string;
  branch_id?: string;
  iteration?: number;
  data?: Record<string, any>;
}

function WorkflowViewer({ workflowId, query }: Props) {
  const [stages, setStages] = useState<StageState[]>([]);
  
  useEffect(() => {
    const eventSource = new EventSource(
      `/api/workflows/${workflowId}/run?query=${encodeURIComponent(query)}`
    );
    
    eventSource.onmessage = (e) => {
      const event: WorkflowEvent = JSON.parse(e.data);
      
      switch (event.type) {
        case 'stage_started':
          setStages(prev => [...prev, { id: event.stage_id, status: 'running' }]);
          break;
        case 'stage_completed':
          setStages(prev => prev.map(s => 
            s.id === event.stage_id ? { ...s, status: 'completed' } : s
          ));
          break;
        case 'step_delta':
          // 更新当前 stage 的输出内容
          break;
      }
    };
  }, [workflowId, query]);
  
  return (
    <div className="workflow-viewer">
      {stages.map(stage => (
        <StagePanel key={stage.id} stage={stage} />
      ))}
    </div>
  );
}
```

---

## 附录：设计决策记录

### A.1 为什么用模板字符串而不是结构化配置？

**决策**：使用 `"{query}\n{intent}"` 模板语法

**理由**：
1. 直观易懂，降低学习成本
2. 灵活组合，无需预定义所有可能的组合方式
3. 与 prompt engineering 习惯一致

**备选方案**（已否决）：
```yaml
# 结构化配置（过于复杂）
input:
  sources:
    - stage: query
    - stage: intent
  format: "{0}\n{1}"
```

### A.2 为什么不用 DAG 而用嵌套结构？

**决策**：使用嵌套的 Pipeline/Loop/Parallel 结构

**理由**：
1. 嵌套结构更直观，符合人类思维
2. 避免 DAG 带来的复杂依赖分析
3. 配置文件更易读写

**备选方案**（已否决）：
```yaml
# DAG 风格（依赖关系复杂）
nodes:
  - id: intent
    depends_on: []
  - id: plan
    depends_on: [intent]
  - id: research
    depends_on: [plan]
```

### A.3 为什么 Agent.run() 只接收 string input？

**决策**：`run(input: str)` 而不是 `run(messages: list[Message])`

**理由**：
1. 简化接口，降低 Workflow 编排复杂度
2. 输入由 InputMapping 构建，已是格式化后的字符串
3. 如需传递结构化数据，可在模板中使用 JSON

---

## 附录：变量引用速查表

| 变量 | 说明 | 使用场景 |
|------|------|----------|
| `{query}` | 原始用户输入 | 任何 Stage |
| `{stage_id}` | 某个 Stage 的输出 | 引用前序 Stage |
| `{loop.iteration}` | 当前循环迭代次数 | Loop 内的 Stage |
| `{loop.last.stage_id}` | 上次迭代某 Stage 的输出 | Loop 内需要历史 |
| `{branch_id}` | 某个分支的输出 | Parallel 合并后 |

---

> **文档维护说明**  
> 本文档描述 Multi-Agent 编排的核心设计，与 `multi-agent-refactor-design.md` 配合使用。  
> 本方案取代了原 `multi-agent-context-design.md` 中的 ContextPolicy 设计。
