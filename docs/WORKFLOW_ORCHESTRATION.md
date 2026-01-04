# Workflow 编排

Workflow 编排系统提供 Pipeline、Loop、Parallel 三种工作流类型，支持复杂的多 Agent 协作场景。

## 架构设计

```
BaseWorkflow (抽象基类)
├── PipelineWorkflow (顺序执行)
├── LoopWorkflow (循环执行)
└── ParallelWorkflow (并行执行)

核心组件:
├── WorkflowNode (节点定义)
├── WorkflowState (状态缓存)
├── ContextResolver (模板变量解析)
└── ConditionEvaluator (条件评估)
```

## 核心组件

### BaseWorkflow

**职责**：工作流基类，实现 `Runnable` 协议

```python
class BaseWorkflow(ABC):
    def __init__(
        self,
        id: str,
        stages: list[WorkflowNode],
        session_store: SessionStore | None = None,
    ):
        ...
    
    async def run(
        self,
        input: str,
        *,
        context: ExecutionContext,
    ) -> RunOutput:
        ...
```

**关键特性**：
- 实现 `Runnable` 协议，可嵌套和作为工具使用
- 统一的子上下文创建（`_create_child_context`）
- Runnable 解析（支持字符串引用和实例）

### WorkflowNode

**职责**：工作流节点定义

```python
class WorkflowNode:
    id: str  # 节点 ID
    runnable: Runnable | str  # Agent 或 Workflow（支持嵌套）
    input_template: str  # 输入模板（支持变量引用）
    condition: str | None  # 条件表达式（可选）
```

**输入模板变量（Jinja2）**：
- `{{ input }}`: 原始工作流输入
- `{{ nodes.<id>.output }}`: 引用其他节点的输出
- `{{ loop.iteration }}`: 当前循环迭代次数（LoopWorkflow）
- `{{ loop.last.<id> }}`: 上一轮迭代的节点输出（LoopWorkflow）

### WorkflowState

**职责**：节点输出缓存和幂等性管理

```python
class WorkflowState:
    def __init__(
        self,
        session_id: str,
        workflow_id: str,
        store: SessionStore,
    ):
        ...
    
    async def load_from_history(self) -> None:
        """从历史加载节点输出（用于 Resume 场景）"""
    
    def get_output(self, node_id: str, iteration: int | None = None) -> str | None:
        """获取节点输出（O(1) 缓存查找）"""
    
    def set_output(self, node_id: str, output: str, iteration: int | None = None) -> None:
        """设置节点输出"""
```

**特点**：
- O(1) 缓存查找，避免重复数据库查询
- 支持 Resume 场景：从历史加载已执行的节点输出
- 幂等性支持：检查节点是否已执行

### ContextResolver

**职责**：模板变量解析

```python
class ContextResolver:
    async def resolve_template(
        self,
        template: str,
        additional_vars: dict[str, Any] | None = None,
    ) -> str:
        """解析模板变量"""
```

**支持的变量（Jinja2）**：
- `{{ input }}`
- `{{ nodes.<id>.output }}`
- `{{ loop.iteration }}`
- `{{ loop.last.<id> }}`

**解析流程**：
1. 先检查 `WorkflowState` 缓存
2. 缓存未命中时查询数据库
3. 支持自定义变量（`additional_vars`）

### ConditionEvaluator

**职责**：条件表达式评估

```python
class ConditionEvaluator:
    def evaluate(
        self,
        condition: str,
        context: dict[str, Any],
    ) -> bool:
        """评估条件表达式"""
```

**支持的表达式（Jinja2）**：
- 字符串包含：`"{{ 'keyword' in nodes.analyze.output }}"` 或 `"{{ nodes.node_id.output }}"`（非空即真）
- 布尔表达式：`"{{ nodes.score.output | float > 0.8 }}"`
- 数值比较：`"{{ loop.iteration < 5 }}"`

## 工作流类型

### PipelineWorkflow（顺序执行）

**特点**：
- 按顺序执行所有节点
- 每个节点可以引用前面所有节点的输出
- 支持条件执行（跳过不满足条件的节点）

**执行流程**：

```
1. 初始化 WorkflowState 和 ContextResolver
2. 遍历节点列表：
   a. 解析节点输入模板
   b. 评估节点条件（如果有）
   c. 如果条件满足：
      - 创建子上下文
      - 执行节点 Runnable
      - 缓存节点输出
   d. 如果条件不满足：跳过节点
3. 返回最后一个节点的输出
```

**示例**：

```yaml
type: workflow
name: research_pipeline
workflow_type: pipeline
stages:
  - id: research
    runnable: researcher
    input: "Research: {{ input }}"
  - id: analyze
    runnable: analyzer
    input: "Analyze: {{ nodes.research.output }}"
    condition: "{{ 'data' in nodes.research.output }}"
  - id: format
    runnable: formatter
    input: "Format: {{ nodes.analyze.output }}"
```

### LoopWorkflow（循环执行）

**特点**：
- 重复执行节点直到条件不满足
- 支持最大迭代次数限制
- 支持循环上下文变量（`{{ loop.iteration }}`, `{{ loop.last.<id> }}`)

**执行流程**：

```
1. 初始化 WorkflowState 和 ContextResolver
2. 循环（最多 max_iterations 次）：
   a. 设置循环上下文（iteration, last_outputs）
   b. 遍历节点列表：
      - 解析输入模板（支持 `loop.*` 变量）
      - 执行节点 Runnable
      - 缓存节点输出
   c. 评估循环条件
   d. 如果条件不满足：退出循环
3. 返回最后一次迭代的输出
```

**示例**：

```yaml
type: workflow
name: quality_loop
workflow_type: loop
stages:
  - id: improve
    runnable: improver
    input: |
      Improve based on feedback:
      {{ input }}
      Feedback: {{ nodes.review.output }}
  - id: review
    runnable: reviewer
    input: |
      Review iteration {{ loop.iteration }}:
      {{ nodes.improve.output }}
condition: "{{ 'NEEDS_REVISION' in nodes.review.output }}"
max_iterations: 3
```

**循环变量**：
- `{{ loop.iteration }}`: 当前迭代次数（从 1 开始）
- `{{ loop.last.<id> }}`: 上一轮迭代的节点输出

### ParallelWorkflow（并行执行）

**特点**：
- 并行执行所有节点
- 等待所有节点完成后合并结果
- 支持合并模板（`merge_template`）

**执行流程**：

```
1. 初始化 WorkflowState 和 ContextResolver
2. 并行执行所有节点：
   a. 为每个节点创建独立的执行上下文
   b. 使用 asyncio.gather() 并行执行
   c. 缓存每个节点的输出
3. 合并结果：
   a. 使用 merge_template 合并输出
   b. 如果未提供 merge_template，返回 JSON 格式
4. 返回合并后的输出
```

**示例**：

```yaml
type: workflow
name: parallel_research
workflow_type: parallel
stages:
  - id: web_research
    runnable: web_researcher
    input: "Web research: {{ input }}"
  - id: local_research
    runnable: local_researcher
    input: "Local research: {{ input }}"
merge_template: |
  Web Research:
  {{ nodes.web_research.output }}
  
  Local Research:
  {{ nodes.local_research.output }}
```

**合并模板变量（Jinja2）**：
- `{{ nodes.<id>.output }}`: 节点输出
- `{{ results }}`: 所有节点输出的 JSON 格式

## 节点执行

### 节点执行流程

```
1. 解析输入模板
   └─► ContextResolver.resolve_template()
       └─► 替换变量引用
   
2. 评估条件（如果有）
   └─► ConditionEvaluator.evaluate()
       └─► 返回 True/False
   
3. 创建子上下文
   └─► BaseWorkflow._create_child_context()
       ├─► 新的 run_id
       ├─► 继承 session_id（统一会话）
       ├─► 共享 wire（统一事件流）
       └─► 设置 workflow_id, node_id
   
4. 执行节点 Runnable
   └─► RunnableExecutor.execute()
       └─► 递归调用 Runnable.run()
   
5. 缓存节点输出
   └─► WorkflowState.set_output()
```

### 统一会话模型

所有嵌套执行共享同一个 `session_id`，确保：
- 所有 Steps 存储在同一个 Session
- 上下文查询可以跨节点
- 支持 Fork+Resume 场景

### 事件流

工作流执行过程中写入的事件：

- `NODE_STARTED`: 节点开始执行
- `NODE_COMPLETED`: 节点执行完成
- `RUN_STARTED`: 节点内的 Runnable 开始执行
- `STEP_CREATED`: Step 创建
- `RUN_COMPLETED`: 节点内的 Runnable 执行完成

## 使用示例

### 创建 Pipeline Workflow

```python
from agio.workflow import PipelineWorkflow, WorkflowNode
from agio.runtime import RunnableExecutor

# 创建节点
nodes = [
    WorkflowNode(
        id="research",
        runnable="researcher",
        input_template="Research: {{ input }}",
    ),
    WorkflowNode(
        id="analyze",
        runnable="analyzer",
        input_template="Analyze: {{ nodes.research.output }}",
    ),
]

# 创建工作流
workflow = PipelineWorkflow(
    id="research_pipeline",
    stages=nodes,
    session_store=session_store,
)

# 设置 Runnable 注册表
workflow.set_registry({
    "researcher": researcher_agent,
    "analyzer": analyzer_agent,
})

# 执行
executor = RunnableExecutor(store=session_store)
result = await executor.execute(
    runnable=workflow,
    input="Research AI trends",
    context=context,
)
```

### 创建 Loop Workflow

```python
from agio.workflow import LoopWorkflow

workflow = LoopWorkflow(
    id="quality_loop",
    stages=[
        WorkflowNode(
            id="improve",
            runnable="improver",
            input_template="Improve: {{ input }}\nFeedback: {{ nodes.review.output }}",
        ),
        WorkflowNode(
            id="review",
            runnable="reviewer",
            input_template="Review iteration {{ loop.iteration }}: {{ nodes.improve.output }}",
        ),
    ],
    condition="{{ 'NEEDS_REVISION' in nodes.review.output }}",
    max_iterations=3,
    session_store=session_store,
)
```

### 创建 Parallel Workflow

```python
from agio.workflow import ParallelWorkflow

workflow = ParallelWorkflow(
    id="parallel_research",
    stages=[
        WorkflowNode(
            id="web_research",
            runnable="web_researcher",
            input_template="Web research: {{ input }}",
        ),
        WorkflowNode(
            id="local_research",
            runnable="local_researcher",
            input_template="Local research: {{ input }}",
        ),
    ],
    merge_template="""
    Web Research:
    {{ nodes.web_research.output }}
    
    Local Research:
    {{ nodes.local_research.output }}
    """,
    session_store=session_store,
)
```

## 配置示例

### Pipeline Workflow

```yaml
type: workflow
name: research_pipeline
workflow_type: pipeline
stages:
  - id: research
    runnable: researcher
    input: "Research: {{ input }}"
  - id: analyze
    runnable: analyzer
    input: "Analyze: {{ nodes.research.output }}"
    condition: "{{ 'data' in nodes.research.output }}"
session_store: mongodb_session_store
enabled: true
```

### Loop Workflow

```yaml
type: workflow
name: quality_loop
workflow_type: loop
stages:
  - id: improve
    runnable: improver
    input: |
      Improve based on feedback:
      {{ input }}
      Feedback: {{ nodes.review.output }}
  - id: review
    runnable: reviewer
    input: |
      Review iteration {{ loop.iteration }}:
      {{ nodes.improve.output }}
condition: "{{ 'NEEDS_REVISION' in nodes.review.output }}"
max_iterations: 3
session_store: mongodb_session_store
enabled: true
```

### Parallel Workflow

```yaml
type: workflow
name: parallel_research
workflow_type: parallel
stages:
  - id: web_research
    runnable: web_researcher
    input: "Web research: {{ input }}"
  - id: local_research
    runnable: local_researcher
    input: "Local research: {{ input }}"
merge_template: |
  Web Research:
  {{ nodes.web_research.output }}
  
  Local Research:
  {{ nodes.local_research.output }}
session_store: mongodb_session_store
enabled: true
```

### 嵌套 Workflow

```yaml
type: workflow
name: complex_workflow
workflow_type: pipeline
stages:
  - id: plan
    runnable: planner
    input: "{{ input }}"
  - id: research
    # 嵌套的并行工作流
    runnable:
      id: nested_parallel
      workflow_type: parallel
      stages:
        - id: branch_a
          runnable: agent_a
          input: "{{ nodes.plan.output }}"
        - id: branch_b
          runnable: agent_b
          input: "{{ nodes.plan.output }}"
      merge_template: "A: {{ nodes.branch_a.output }}\nB: {{ nodes.branch_b.output }}"
    input: "{{ nodes.plan.output }}"
```

## 最佳实践

1. **节点命名**：使用有意义的节点 ID，便于引用
2. **输入模板**：明确引用依赖节点的输出
3. **条件执行**：合理使用条件，避免不必要的执行
4. **状态管理**：利用 `WorkflowState` 缓存，提高性能
5. **错误处理**：单个节点失败不影响其他节点（Parallel）
6. **循环控制**：合理设置 `max_iterations`，避免无限循环
7. **合并模板**：Parallel Workflow 提供清晰的合并模板

## 相关代码

- `agio/workflow/base.py`: BaseWorkflow
- `agio/workflow/pipeline.py`: PipelineWorkflow
- `agio/workflow/loop.py`: LoopWorkflow
- `agio/workflow/parallel.py`: ParallelWorkflow
- `agio/workflow/node.py`: WorkflowNode
- `agio/workflow/state.py`: WorkflowState
- `agio/workflow/resolver.py`: ContextResolver
- `agio/workflow/condition.py`: ConditionEvaluator

