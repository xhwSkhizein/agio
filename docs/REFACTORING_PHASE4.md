# Phase 4: 多 Agent 协作框架

## 目标

实现多 Agent 协作能力，支持顺序执行、并行执行、图结构执行和代码控制流，同时保持与前端的单 Agent 交互协议完全一致。

## 核心设计原则

1. **统一输出**: 无论多少 Agent 协作，输出都是 `AsyncIterator[StepEvent]`
2. **透明组合**: 前端无需知道是单 Agent 还是多 Agent
3. **灵活编排**: 支持静态配置和代码动态控制

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     Runnable Protocol                        │
│              async def run(...) -> AsyncIterator[StepEvent]  │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ implements
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────┴────┐          ┌─────┴─────┐         ┌────┴────┐
   │  Agent  │          │ Sequential │         │ Parallel │
   └─────────┘          └───────────┘         └──────────┘
                              │
                        ┌─────┴─────┐
                        │   Graph   │
                        └───────────┘
```

## 1. Sequential (顺序执行)

### 设计

```python
# agio/orchestration/sequential.py

from typing import AsyncIterator
from agio.core import StepEvent, StepEventType
from agio.core.protocols import Runnable


class Sequential(Runnable):
    """
    顺序执行多个 Runnable。
    
    每个 Runnable 的输出作为下一个的输入上下文。
    所有事件按执行顺序输出。
    
    Example:
        >>> pipeline = Sequential([
        ...     research_agent,
        ...     analysis_agent,
        ...     report_agent,
        ... ])
        >>> async for event in pipeline.run("分析市场趋势"):
        ...     handle_event(event)
    """
    
    def __init__(
        self,
        steps: list[Runnable],
        name: str = "sequential",
        pass_context: bool = True,  # 是否传递上下文
    ):
        self._steps = steps
        self._name = name
        self._pass_context = pass_context
    
    @property
    def name(self) -> str:
        return self._name
    
    async def run(
        self,
        query: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        """
        顺序执行所有步骤。
        
        事件流结构:
        - workflow_run_started
        - step[0] events...
        - step[1] events...
        - ...
        - workflow_run_completed
        """
        from uuid import uuid4
        from agio.core.events import create_run_started_event, create_run_completed_event
        
        workflow_run_id = str(uuid4())
        
        # 发送 Workflow 开始事件
        yield create_run_started_event(
            run_id=workflow_run_id,
            query=query,
        )
        
        current_input = query
        all_outputs = []
        
        for i, step in enumerate(self._steps):
            step_outputs = []
            
            # 执行当前步骤
            async for event in step.run(
                current_input,
                session_id=session_id,
                user_id=user_id,
            ):
                # 收集输出用于下一步
                if event.type == StepEventType.STEP_DELTA and event.delta:
                    if event.delta.content:
                        step_outputs.append(event.delta.content)
                
                # 转发事件（添加 workflow 上下文）
                event_with_context = self._add_workflow_context(
                    event, workflow_run_id, step_index=i
                )
                yield event_with_context
            
            # 准备下一步的输入
            if self._pass_context and step_outputs:
                step_output = "".join(step_outputs)
                current_input = self._build_next_input(query, step_output, i)
                all_outputs.append(step_output)
        
        # 发送 Workflow 完成事件
        yield create_run_completed_event(
            run_id=workflow_run_id,
            response=all_outputs[-1] if all_outputs else "",
            metrics={"steps_count": len(self._steps)},
        )
    
    def _build_next_input(self, original_query: str, last_output: str, step_index: int) -> str:
        """构建下一步的输入"""
        return f"基于以下上一步的结果，继续处理：\n\n{last_output}\n\n原始任务：{original_query}"
    
    def _add_workflow_context(self, event: StepEvent, workflow_run_id: str, step_index: int) -> StepEvent:
        """为事件添加 workflow 上下文"""
        # 可以在 event.data 中添加 workflow 信息
        if event.data is None:
            event.data = {}
        event.data["workflow_run_id"] = workflow_run_id
        event.data["workflow_step_index"] = step_index
        return event
```

### 使用示例

```python
# 创建研究 -> 分析 -> 报告的流水线
pipeline = Sequential([
    Agent(model=gpt4, name="researcher", system_prompt="你是研究员..."),
    Agent(model=gpt4, name="analyst", system_prompt="你是分析师..."),
    Agent(model=gpt4, name="reporter", system_prompt="你是报告撰写者..."),
])

async for event in pipeline.run("分析 2024 年 AI 市场趋势"):
    if event.type == StepEventType.STEP_DELTA:
        print(event.delta.content, end="")
```

## 2. Parallel (并行执行)

### 设计

```python
# agio/orchestration/parallel.py

import asyncio
from typing import AsyncIterator
from agio.core import StepEvent, StepEventType
from agio.core.protocols import Runnable


class Parallel(Runnable):
    """
    并行执行多个 Runnable。
    
    所有 Runnable 同时执行，事件交错输出。
    适用于独立任务的并行处理。
    
    Example:
        >>> parallel = Parallel([
        ...     code_agent,
        ...     test_agent,
        ...     doc_agent,
        ... ])
        >>> async for event in parallel.run("实现用户登录功能"):
        ...     handle_event(event)
    """
    
    def __init__(
        self,
        branches: list[Runnable],
        name: str = "parallel",
        merge_strategy: str = "interleave",  # 'interleave' | 'sequential'
    ):
        self._branches = branches
        self._name = name
        self._merge_strategy = merge_strategy
    
    @property
    def name(self) -> str:
        return self._name
    
    async def run(
        self,
        query: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        """并行执行所有分支"""
        from uuid import uuid4
        from agio.core.events import create_run_started_event, create_run_completed_event
        
        workflow_run_id = str(uuid4())
        
        yield create_run_started_event(run_id=workflow_run_id, query=query)
        
        # 创建事件队列
        event_queue: asyncio.Queue[tuple[int, StepEvent | None]] = asyncio.Queue()
        
        async def run_branch(index: int, branch: Runnable):
            """运行单个分支，将事件放入队列"""
            try:
                async for event in branch.run(query, session_id=session_id, user_id=user_id):
                    event.data = event.data or {}
                    event.data["branch_index"] = index
                    event.data["branch_name"] = branch.name
                    await event_queue.put((index, event))
            finally:
                await event_queue.put((index, None))  # 标记分支完成
        
        # 启动所有分支
        tasks = [
            asyncio.create_task(run_branch(i, branch))
            for i, branch in enumerate(self._branches)
        ]
        
        # 消费事件队列
        completed_count = 0
        branch_outputs = {i: [] for i in range(len(self._branches))}
        
        while completed_count < len(self._branches):
            index, event = await event_queue.get()
            
            if event is None:
                completed_count += 1
                continue
            
            # 收集输出
            if event.type == StepEventType.STEP_DELTA and event.delta and event.delta.content:
                branch_outputs[index].append(event.delta.content)
            
            yield event
        
        # 等待所有任务完成
        await asyncio.gather(*tasks)
        
        # 合并输出
        merged_response = self._merge_outputs(branch_outputs)
        
        yield create_run_completed_event(
            run_id=workflow_run_id,
            response=merged_response,
            metrics={"branches_count": len(self._branches)},
        )
    
    def _merge_outputs(self, branch_outputs: dict[int, list[str]]) -> str:
        """合并各分支输出"""
        parts = []
        for i, outputs in sorted(branch_outputs.items()):
            branch_name = self._branches[i].name
            content = "".join(outputs)
            parts.append(f"## {branch_name}\n\n{content}")
        return "\n\n".join(parts)
```

## 3. Graph (图结构执行)

### 设计

```python
# agio/orchestration/graph.py

from typing import AsyncIterator, Callable, Any
from dataclasses import dataclass, field
from agio.core import StepEvent
from agio.core.protocols import Runnable


@dataclass
class GraphNode:
    """图节点"""
    name: str
    runnable: Runnable
    
    
@dataclass  
class GraphEdge:
    """图边"""
    source: str
    target: str
    condition: Callable[[str], bool] | None = None  # 条件函数


class Graph(Runnable):
    """
    图结构执行。
    
    支持条件分支、循环等复杂流程。
    
    Example:
        >>> graph = Graph()
        >>> graph.add_node("classify", classifier_agent)
        >>> graph.add_node("code", code_agent)
        >>> graph.add_node("chat", chat_agent)
        >>> graph.set_entry("classify")
        >>> graph.add_edge("classify", "code", condition=lambda x: "代码" in x)
        >>> graph.add_edge("classify", "chat", condition=lambda x: "代码" not in x)
    """
    
    def __init__(self, name: str = "graph"):
        self._name = name
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._entry_node: str | None = None
        self._end_nodes: set[str] = set()
    
    @property
    def name(self) -> str:
        return self._name
    
    def add_node(self, name: str, runnable: Runnable) -> "Graph":
        """添加节点"""
        self._nodes[name] = GraphNode(name=name, runnable=runnable)
        return self
    
    def set_entry(self, node_name: str) -> "Graph":
        """设置入口节点"""
        self._entry_node = node_name
        return self
    
    def set_end(self, *node_names: str) -> "Graph":
        """设置结束节点"""
        self._end_nodes.update(node_names)
        return self
    
    def add_edge(
        self,
        source: str,
        target: str,
        condition: Callable[[str], bool] | None = None,
    ) -> "Graph":
        """添加边（可带条件）"""
        self._edges.append(GraphEdge(source=source, target=target, condition=condition))
        return self
    
    async def run(
        self,
        query: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        """执行图"""
        from uuid import uuid4
        from agio.core.events import create_run_started_event, create_run_completed_event
        
        if not self._entry_node:
            raise ValueError("Entry node not set")
        
        workflow_run_id = str(uuid4())
        yield create_run_started_event(run_id=workflow_run_id, query=query)
        
        current_node = self._entry_node
        current_input = query
        last_output = ""
        visited = set()
        max_iterations = 100  # 防止无限循环
        
        for _ in range(max_iterations):
            if current_node in visited and current_node in self._end_nodes:
                break
            
            visited.add(current_node)
            node = self._nodes.get(current_node)
            
            if not node:
                raise ValueError(f"Node '{current_node}' not found")
            
            # 执行当前节点
            outputs = []
            async for event in node.runnable.run(
                current_input,
                session_id=session_id,
                user_id=user_id,
            ):
                event.data = event.data or {}
                event.data["graph_node"] = current_node
                
                if event.type == StepEventType.STEP_DELTA and event.delta and event.delta.content:
                    outputs.append(event.delta.content)
                
                yield event
            
            last_output = "".join(outputs)
            
            # 检查是否是结束节点
            if current_node in self._end_nodes:
                break
            
            # 查找下一个节点
            next_node = self._find_next_node(current_node, last_output)
            if not next_node:
                break
            
            current_node = next_node
            current_input = last_output
        
        yield create_run_completed_event(
            run_id=workflow_run_id,
            response=last_output,
            metrics={"nodes_visited": len(visited)},
        )
    
    def _find_next_node(self, current: str, output: str) -> str | None:
        """根据条件找下一个节点"""
        for edge in self._edges:
            if edge.source != current:
                continue
            
            if edge.condition is None or edge.condition(output):
                return edge.target
        
        return None
```

## 4. 代码控制流 (CustomWorkflow)

### 设计

```python
# agio/orchestration/workflow.py

from abc import ABC, abstractmethod
from typing import AsyncIterator
from agio.core import StepEvent
from agio.core.protocols import Runnable


class Workflow(Runnable, ABC):
    """
    自定义工作流基类。
    
    允许用代码实现复杂的控制流逻辑。
    
    Example:
        >>> class RetryWorkflow(Workflow):
        ...     def __init__(self, agent: Agent, max_retries: int = 3):
        ...         self.agent = agent
        ...         self.max_retries = max_retries
        ...     
        ...     async def execute(self, query: str, context: WorkflowContext):
        ...         for i in range(self.max_retries):
        ...             async for event in self.agent.run(query):
        ...                 yield event
        ...                 if self._is_success(event):
        ...                     return
    """
    
    @property
    def name(self) -> str:
        return self.__class__.__name__
    
    async def run(
        self,
        query: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        """执行工作流"""
        from uuid import uuid4
        from agio.core.events import create_run_started_event, create_run_completed_event
        
        workflow_run_id = str(uuid4())
        
        context = WorkflowContext(
            run_id=workflow_run_id,
            session_id=session_id,
            user_id=user_id,
        )
        
        yield create_run_started_event(run_id=workflow_run_id, query=query)
        
        last_output = ""
        async for event in self.execute(query, context):
            if event.type == StepEventType.STEP_DELTA and event.delta and event.delta.content:
                last_output += event.delta.content
            yield event
        
        yield create_run_completed_event(
            run_id=workflow_run_id,
            response=last_output,
            metrics=context.metrics,
        )
    
    @abstractmethod
    async def execute(
        self, 
        query: str, 
        context: "WorkflowContext"
    ) -> AsyncIterator[StepEvent]:
        """
        实现具体的工作流逻辑。
        
        子类重写此方法实现自定义控制流。
        """
        ...


@dataclass
class WorkflowContext:
    """工作流上下文"""
    run_id: str
    session_id: str | None
    user_id: str | None
    state: dict = field(default_factory=dict)  # 共享状态
    metrics: dict = field(default_factory=dict)  # 指标收集
```

### 使用示例

```python
class IterativeRefinement(Workflow):
    """迭代优化工作流"""
    
    def __init__(self, generator: Agent, critic: Agent, max_iterations: int = 3):
        self.generator = generator
        self.critic = critic
        self.max_iterations = max_iterations
    
    async def execute(self, query: str, context: WorkflowContext) -> AsyncIterator[StepEvent]:
        current_draft = ""
        
        for i in range(self.max_iterations):
            # 生成/改进
            gen_prompt = f"{query}\n\n当前草稿：{current_draft}" if current_draft else query
            
            async for event in self.generator.run(gen_prompt):
                if event.type == StepEventType.STEP_DELTA and event.delta:
                    current_draft += event.delta.content or ""
                yield event
            
            # 评审
            critique = ""
            async for event in self.critic.run(f"评审以下内容：\n{current_draft}"):
                if event.type == StepEventType.STEP_DELTA and event.delta:
                    critique += event.delta.content or ""
                yield event
            
            # 检查是否满意
            if "满意" in critique or "通过" in critique:
                break
        
        context.metrics["iterations"] = i + 1
```

## 5. YAML 配置支持

### 配置格式

```yaml
# configs/workflows/research_pipeline.yaml
type: workflow
name: research_pipeline
workflow_type: sequential
description: "研究流水线"

steps:
  - agent: researcher
  - agent: analyst  
  - agent: reporter

pass_context: true
```

```yaml
# configs/workflows/parallel_dev.yaml
type: workflow
name: parallel_dev
workflow_type: parallel

branches:
  - agent: code_agent
  - agent: test_agent
  - agent: doc_agent

merge_strategy: interleave
```

### 配置构建器

```python
# agio/config/builders.py

class WorkflowBuilder(ComponentBuilder):
    """工作流构建器"""
    
    async def build(self, config: WorkflowConfig, dependencies: dict) -> Runnable:
        workflow_type = config.workflow_type
        
        if workflow_type == "sequential":
            steps = [dependencies[s.agent] for s in config.steps]
            return Sequential(steps, name=config.name)
        
        elif workflow_type == "parallel":
            branches = [dependencies[b.agent] for b in config.branches]
            return Parallel(branches, name=config.name)
        
        elif workflow_type == "graph":
            return self._build_graph(config, dependencies)
        
        else:
            raise ComponentBuildError(f"Unknown workflow type: {workflow_type}")
```

## 文件结构

```
agio/orchestration/
├── __init__.py
├── base.py           # 基础类和工具函数
├── sequential.py     # Sequential 实现
├── parallel.py       # Parallel 实现
├── graph.py          # Graph 实现
└── workflow.py       # Workflow 基类
```

## 测试用例

```python
# tests/orchestration/test_sequential.py

@pytest.mark.asyncio
async def test_sequential_execution():
    """测试顺序执行"""
    mock_agent1 = MockAgent(output="Step 1 output")
    mock_agent2 = MockAgent(output="Step 2 output")
    
    pipeline = Sequential([mock_agent1, mock_agent2])
    
    events = []
    async for event in pipeline.run("test query"):
        events.append(event)
    
    # 验证事件顺序
    assert events[0].type == StepEventType.RUN_STARTED
    assert events[-1].type == StepEventType.RUN_COMPLETED
    
    # 验证两个 agent 都执行了
    step_completed_events = [e for e in events if e.type == StepEventType.STEP_COMPLETED]
    assert len(step_completed_events) >= 2
```

## 总结

多 Agent 协作框架的核心是 **统一的 `Runnable` 协议**：

1. 单 Agent (`Agent`) 实现 `Runnable`
2. 顺序组合 (`Sequential`) 实现 `Runnable`
3. 并行组合 (`Parallel`) 实现 `Runnable`
4. 图结构 (`Graph`) 实现 `Runnable`
5. 自定义工作流 (`Workflow`) 实现 `Runnable`

所有实现都输出 `AsyncIterator[StepEvent]`，前端代码无需修改即可支持任意复杂的多 Agent 协作。
