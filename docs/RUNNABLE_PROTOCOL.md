# Runnable 协议

Runnable 协议是 Agio 的核心抽象，统一了 Agent 和 Workflow 的执行接口，支持相互嵌套和作为工具使用。

## 协议定义

```python
@runtime_checkable
class Runnable(Protocol):
    @property
    def id(self) -> str:
        """唯一标识符"""
        ...
    
    @property
    def runnable_type(self) -> str:
        """
        返回 Runnable 类型
        
        - Agent 返回 "agent"
        - Workflow 返回 "workflow"
        """
        ...
    
    async def run(
        self,
        input: str,
        *,
        context: ExecutionContext,
    ) -> RunOutput:
        """
        执行并写入事件到 context.wire
        
        Args:
            input: 输入字符串
            context: 执行上下文（必须包含 wire）
            
        Returns:
            RunOutput 包含响应和指标
        """
        ...
```

## 核心能力

### 1. 统一 API 调用

通过 `/runnables/{id}/run` 可以执行任何 Runnable：

```python
# Agent 和 Workflow 都实现 Runnable 协议
agent = Agent(...)
workflow = PipelineWorkflow(...)

# 统一执行接口
executor = RunnableExecutor(store=session_store)

result1 = await executor.execute(agent, input="...", context=context)
result2 = await executor.execute(workflow, input="...", context=context)
```

### 2. 相互嵌套

Agent 可以作为 Workflow 的节点，Workflow 也可以嵌套 Workflow：

```python
# Agent 作为 Workflow 节点
workflow = PipelineWorkflow(
    stages=[
        WorkflowNode(id="research", runnable=research_agent),
        WorkflowNode(id="analyze", runnable=analyze_agent),
    ]
)

# Workflow 嵌套 Workflow
nested_workflow = PipelineWorkflow(
    stages=[
        WorkflowNode(id="plan", runnable=planning_agent),
        WorkflowNode(id="execute", runnable=workflow),  # 嵌套
    ]
)
```

### 3. 作为工具使用

通过 `RunnableTool` 将 Agent/Workflow 包装为 Tool：

```python
from agio.workflow import as_tool

# Agent 作为工具
research_tool = as_tool(research_agent, description="Expert researcher")

# Workflow 作为工具
pipeline_tool = as_tool(workflow, description="Complete research pipeline")

# 在另一个 Agent 中使用
orchestrator = Agent(
    model=model,
    tools=[research_tool, pipeline_tool],
)
```

## ExecutionContext

**职责**：统一的执行上下文

```python
@dataclass(frozen=True)
class ExecutionContext:
    # 执行身份
    run_id: str
    session_id: str
    
    # Session 级资源
    wire: Wire  # 事件通道（必需）
    sequence_manager: SequenceManager | None  # 序列号管理器
    
    # 用户和工作流上下文
    user_id: str | None
    workflow_id: str | None
    
    # 层级信息
    depth: int = 0  # 嵌套深度
    parent_run_id: str | None = None
    nested_runnable_id: str | None = None
    
    # Runnable 身份
    runnable_type: str = "agent"  # "agent" | "workflow"
    runnable_id: str | None = None
    nesting_type: str | None = None  # "tool_call" | "workflow_node" | None
    
    # 工作流节点信息
    node_id: str | None = None
    iteration: int | None = None  # Loop 迭代次数
    
    # 可观测性
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    
    # 元数据
    metadata: dict = field(default_factory=dict)
```

**关键特性**：
- **不可变**：使用 `@dataclass(frozen=True)` 确保线程安全
- **统一会话**：所有嵌套执行共享 `session_id`
- **统一事件流**：所有嵌套执行共享 `wire`
- **层级追踪**：通过 `depth`, `parent_run_id` 追踪嵌套关系

### 创建子上下文

```python
def child(
    self,
    run_id: str,
    nested_runnable_id: str | None = None,
    session_id: str | None = None,
    **overrides,
) -> ExecutionContext:
    """创建子上下文（用于嵌套执行）"""
```

**特点**：
- 自动递增 `depth`
- 设置 `parent_run_id` 为当前 `run_id`
- 继承 `session_id` 和 `wire`（统一会话和事件流）
- 支持字段覆盖（`**overrides`）

## RunnableExecutor

**职责**：统一的执行引擎，管理 Run 生命周期

```python
class RunnableExecutor:
    def __init__(self, store: SessionStore | None = None):
        ...
    
    async def execute(
        self,
        runnable: Runnable,
        input: str,
        context: ExecutionContext,
    ) -> RunOutput:
        ...
```

**执行流程**：

```
1. 创建 Run 记录
   └─► Run(run_id=context.run_id, status=RUNNING)
   
2. 写入 RUN_STARTED 事件
   └─► StepEvent(type=RUN_STARTED, run_id=...)
   
3. 调用 Runnable.run()
   └─► 实际执行逻辑（Agent/Workflow）
       └─► 写入 StepEvent 到 context.wire
   
4. 保存 Run 到 SessionStore
   └─► await store.save_run(run)
   
5. 写入 RUN_COMPLETED 事件
   └─► StepEvent(type=RUN_COMPLETED, run_id=...)
   
6. 返回 RunOutput
```

**特点**：
- 不修改 Runnable 内部逻辑
- 统一管理 Run 生命周期
- 支持 Run 持久化（可选）

## RunnableTool

**职责**：将 Runnable 适配为 Tool

```python
class RunnableTool(BaseTool):
    def __init__(
        self,
        runnable: Runnable,
        description: str | None = None,
        name: str | None = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
        session_store: SessionStore | None = None,
    ):
        ...
    
    async def execute(
        self,
        parameters: dict[str, Any],
        context: ExecutionContext,
        abort_signal: AbortSignal | None = None,
    ) -> ToolResult:
        ...
```

**安全特性**：

1. **深度限制**：
   ```python
   if current_depth > self.max_depth:
       return error_result("Maximum nesting depth exceeded")
   ```

2. **循环引用检测**：
   ```python
   call_stack = context.metadata.get("_call_stack", [])
   if self.runnable.id in call_stack:
       return error_result("Circular reference detected")
   ```

**执行流程**：

```
1. 安全检查
   ├─► 检查深度限制
   └─► 检查循环引用
   
2. 构建输入
   └─► 从 parameters["task"] 提取任务
   
3. 创建子上下文
   └─► context.child(run_id=new_run_id, ...)
       └─► 更新 call_stack
   
4. 执行 Runnable
   └─► RunnableExecutor.execute(runnable, input, child_context)
   
5. 返回 ToolResult
   └─► 包含输出和指标
```

### as_tool 工厂函数

```python
def as_tool(
    runnable: Runnable,
    description: str | None = None,
    name: str | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
    session_store: SessionStore | None = None,
) -> RunnableTool:
    """将 Runnable 转换为 Tool 的便捷函数"""
```

## 使用示例

### Agent 作为 Workflow 节点

```python
# 创建 Agent
research_agent = Agent(
    model=model,
    tools=[web_search_tool],
    name="researcher",
)

# 创建 Workflow，使用 Agent 作为节点
workflow = PipelineWorkflow(
    id="research_pipeline",
    stages=[
        WorkflowNode(
            id="research",
            runnable=research_agent,  # Agent 作为节点
            input_template="Research: {input}",
        ),
    ],
)

# 执行 Workflow
executor = RunnableExecutor(store=session_store)
result = await executor.execute(workflow, input="...", context=context)
```

### Workflow 嵌套 Workflow

```python
# 创建子工作流
sub_workflow = PipelineWorkflow(
    id="sub_pipeline",
    stages=[...],
)

# 创建主工作流，嵌套子工作流
main_workflow = PipelineWorkflow(
    id="main_pipeline",
    stages=[
        WorkflowNode(
            id="subtask",
            runnable=sub_workflow,  # Workflow 嵌套
            input_template="{input}",
        ),
    ],
)
```

### Agent 作为工具

```python
from agio.workflow import as_tool

# 创建研究 Agent
research_agent = Agent(
    model=model,
    tools=[web_search_tool],
    name="researcher",
)

# 包装为工具
research_tool = as_tool(
    research_agent,
    description="Expert researcher for web information",
    name="call_researcher",
)

# 在编排 Agent 中使用
orchestrator = Agent(
    model=model,
    tools=[research_tool],  # Agent 作为工具
    name="orchestrator",
)

# 执行时，LLM 可以调用 research_tool
result = await executor.execute(orchestrator, input="...", context=context)
```

### Workflow 作为工具

```python
# 创建工作流
workflow = PipelineWorkflow(
    id="research_pipeline",
    stages=[...],
)

# 包装为工具
pipeline_tool = as_tool(
    workflow,
    description="Complete research pipeline",
    name="call_pipeline",
)

# 在 Agent 中使用
agent = Agent(
    model=model,
    tools=[pipeline_tool],
)
```

## 配置示例

### Agent 作为工具（配置）

```yaml
type: agent
name: master_orchestrator
model: deepseek-reasoner
tools:
  - agent_tool:
      agent: researcher
      description: "Expert researcher"
  - workflow_tool:
      workflow: research_pipeline
      description: "Complete research pipeline"
```

### Workflow 嵌套（配置）

```yaml
type: workflow
name: complex_workflow
workflow_type: pipeline
stages:
  - id: plan
    runnable: planner
    input: "{input}"
  - id: execute
    # 嵌套的并行工作流
    runnable:
      id: nested_parallel
      workflow_type: parallel
      stages:
        - id: branch_a
          runnable: agent_a
          input: "{plan.output}"
        - id: branch_b
          runnable: agent_b
          input: "{plan.output}"
```

## 事件流

所有 Runnable 执行都通过统一的 `Wire` 事件流：

```
RunnableExecutor.execute()
    │
    ├─► RUN_STARTED 事件
    │
    ├─► Runnable.run()
    │   ├─► Agent: STEP_CREATED 事件（Assistant/Tool Steps）
    │   └─► Workflow: NODE_STARTED/NODE_COMPLETED 事件
    │
    └─► RUN_COMPLETED 事件
```

**事件类型**：
- `RUN_STARTED`: Run 开始
- `STEP_CREATED`: Step 创建（Agent）
- `NODE_STARTED`: 节点开始（Workflow）
- `NODE_COMPLETED`: 节点完成（Workflow）
- `RUN_COMPLETED`: Run 完成

## 最佳实践

1. **统一接口**：使用 `RunnableExecutor` 执行所有 Runnable
2. **上下文传递**：正确创建子上下文，保持层级关系
3. **深度控制**：合理设置 `max_depth`，避免无限嵌套
4. **循环检测**：使用 `call_stack` 追踪调用链，避免循环引用
5. **事件流**：所有嵌套执行共享同一个 `wire`，统一事件管理
6. **会话统一**：所有嵌套执行共享 `session_id`，便于上下文查询

## 相关代码

- `agio/runtime/protocol.py`: Runnable 协议定义
- `agio/runtime/runnable_executor.py`: RunnableExecutor
- `agio/workflow/runnable_tool.py`: RunnableTool
- `agio/agent/agent.py`: Agent 实现
- `agio/workflow/base.py`: BaseWorkflow 实现

