# Web 展示逻辑重构方案

## 一、背景

随着后端统一了 `RunnableExecutor` 和 `StepRunner` 的职责分离，前端展示逻辑也需要相应调整，以更好地支持：

1. **统一的 Runnable 展示**：Agent 和 Workflow 使用一致的展示逻辑
2. **嵌套执行展示**：RunnableTool 调用其他 Agent/Workflow 时，展示其内部执行过程
3. **并发执行展示**：Parallel Workflow 分支和并发 RunnableTool 调用的统一处理
4. **任意深度嵌套**：支持多层嵌套的递归展示

## 二、现状分析

### 2.1 后端事件模型

当前 `StepEvent` 包含以下关键字段：

```python
class StepEvent(BaseModel):
    type: StepEventType           # step_delta, step_completed, run_started, etc.
    run_id: str                   # 当前 Run ID
    step_id: str | None           # Step ID
    
    # 嵌套上下文
    parent_run_id: str | None     # 父级 Run ID
    depth: int = 0                # 嵌套深度
    nested_runnable_id: str | None  # 被嵌套调用的 Runnable ID
    
    # Workflow 上下文
    workflow_type: str | None     # "pipeline" | "parallel" | "loop"
    workflow_id: str | None       # Workflow ID
    node_id: str | None           # 节点 ID
    branch_id: str | None         # 分支 ID
```

**问题**：
- 缺少 `runnable_type` 字段，无法直接区分 Agent 和 Workflow
- `depth` 语义不清，Workflow 子节点和 RunnableTool 嵌套都会增加 depth
- 无法区分「Workflow 内部节点执行」和「RunnableTool 嵌套调用」

### 2.2 前端组件结构

```
ChatTimeline
├── TimelineItem (user/assistant/tool/error)
├── WorkflowContainer (workflow 类型)
│   ├── PipelineStages (pipeline)
│   └── ParallelBranchSlider (parallel)
└── ParallelNestedRunnables (parallel_nested - RunnableTool 并发调用)
```

**问题**：
1. **两套并行展示逻辑**：`ParallelBranchSlider` 和 `ParallelNestedRunnables` 逻辑重复
2. **事件处理分散**：`eventHandlers.ts` 和 `nestedExecutionHandlers.ts` 两套几乎相同的逻辑
3. **嵌套追踪复杂**：`NestedExecutionMap` 使用多个 Map 追踪嵌套关系

### 2.3 当前嵌套场景

| 场景 | depth | parent_run_id | nested_runnable_id | 如何识别 |
|------|-------|---------------|-------------------|----------|
| 顶层 Agent | 0 | null | null | depth === 0 |
| Agent 调用 RunnableTool | 1+ | 有 | 有 | nested_runnable_id 存在 |
| Pipeline 子节点 Agent | 1+ | 有 | null | workflow_type 存在 |
| Parallel 分支 Agent | 1+ | 有 | null | branch_id 存在 |
| 嵌套 Workflow | 1+ | 有 | null | workflow_type 存在 |

**核心问题**：无法通过单一字段区分「RunnableTool 嵌套」和「Workflow 子节点」。

## 三、设计目标

### 3.1 统一的执行树模型

前端构建一个统一的递归执行树：

```typescript
interface RunnableExecution {
  id: string                      // run_id
  runnableId: string              // Agent/Workflow ID
  runnableType: 'agent' | 'workflow'
  
  // 嵌套上下文
  nestingType?: 'tool_call' | 'workflow_node'
  parentRunId?: string
  depth: number
  
  // Workflow 特有
  workflowType?: 'pipeline' | 'parallel' | 'loop'
  nodeId?: string
  branchId?: string
  
  // 执行状态
  status: 'running' | 'completed' | 'failed'
  
  // 内容
  steps: ExecutionStep[]          // 当前执行的步骤
  children: RunnableExecution[]   // 子执行（递归）
  
  // 指标
  metrics?: RunMetrics
}

type ExecutionStep = 
  | { type: 'assistant_content'; stepId: string; content: string; reasoning_content?: string }
  | { type: 'tool_call'; toolCallId: string; toolName: string; toolArgs: string }
  | { type: 'tool_result'; toolCallId: string; result: string; status: string; duration?: number }
```

### 3.2 RunnableTool 嵌套展示

当 Agent 调用 RunnableTool 时，结构如下：

```
RunnableExecution (顶层 Agent, depth=0)
├── steps: [
│     { type: 'assistant_content', content: '让我调用代码助手...' },
│     { type: 'tool_call', toolName: 'code_assistant', toolArgs: {...} }
│   ]
└── children: [
      RunnableExecution (code_assistant Agent, depth=1)
      ├── runnableType: 'agent'
      ├── nestingType: 'tool_call'  ← 标识由 tool_call 触发
      ├── steps: [
      │     { type: 'assistant_content', content: '分析代码...' },
      │     { type: 'tool_call', toolName: 'file_read', ... },
      │     { type: 'tool_result', result: '文件内容...' }
      │   ]
      └── children: []  // 可以继续嵌套
    ]
```

展示时：
1. 父级 Agent 的 `tool_call` 显示为可展开区域
2. 展开后显示对应 child 的完整执行过程
3. 支持任意深度递归

### 3.3 Workflow 子节点展示

```
RunnableExecution (Pipeline Workflow, depth=0)
├── runnableType: 'workflow'
├── workflowType: 'pipeline'
├── steps: []  // Workflow 本身无 steps
└── children: [
      RunnableExecution (Stage 1 Agent, depth=1)
      ├── nestingType: 'workflow_node'  ← 标识为 Workflow 内部节点
      ├── nodeId: 'stage_1'
      └── steps: [...]
      
      RunnableExecution (Stage 2 Agent, depth=1)
      ├── nestingType: 'workflow_node'
      ├── nodeId: 'stage_2'
      └── steps: [...]
    ]
```

### 3.4 并发执行展示

无论是 Parallel Workflow 还是并发 RunnableTool 调用，都统一为：

```
RunnableExecution (父级)
└── children: [
      RunnableExecution (branch_1),  // 并发
      RunnableExecution (branch_2),  // 并发
      RunnableExecution (branch_3),  // 并发
    ]
```

前端检测到多个 children 具有相同的 `parentRunId` 且同时 running，即判定为并发执行，使用 Tab/Slider 展示。

## 四、执行计划

### Phase 1: 后端事件模型增强（低风险）✅ 已完成

**目标**：在 `StepEvent` 中增加明确的 Runnable 类型标识

#### 1.1 扩展 StepEvent

```python
class StepEvent(BaseModel):
    # 现有字段保持不变...
    
    # 新增字段
    runnable_type: str | None = None   # "agent" | "workflow"
    runnable_id: str | None = None     # Agent/Workflow 的配置 ID
    nesting_type: str | None = None    # "tool_call" | "workflow_node" | None
```

#### 1.2 更新 EventFactory

```python
class EventFactory:
    def __init__(self, ctx: "ExecutionContext"):
        self._ctx = ctx
    
    def run_started(self, query: str) -> StepEvent:
        return StepEvent(
            # 现有字段...
            runnable_type=self._ctx.runnable_type,  # 新增
            runnable_id=self._ctx.runnable_id,      # 新增
            nesting_type=self._ctx.nesting_type,    # 新增
        )
```

#### 1.3 更新 ExecutionContext

```python
@dataclass
class ExecutionContext:
    # 现有字段...
    
    # 新增字段
    runnable_type: str = "agent"       # "agent" | "workflow"
    runnable_id: str | None = None     # Runnable 配置 ID
    nesting_type: str | None = None    # "tool_call" | "workflow_node"
```

#### 1.4 改动点

| 文件 | 改动 |
|------|------|
| `agio/domain/events.py` | 添加 3 个可选字段 |
| `agio/domain/context.py` | 添加 3 个字段到 ExecutionContext |
| `agio/runtime/event_factory.py` | 在事件创建时填充新字段 |
| `agio/runtime/runnable_executor.py` | 创建 context 时设置 runnable_type/id |
| `agio/workflow/base.py` | _create_child_context 设置 nesting_type='workflow_node' |
| `agio/tools/runnable_tool.py` | 创建 context 时设置 nesting_type='tool_call' |

**验证**：现有前端代码不依赖新字段，增量添加不会破坏兼容性。

---

### Phase 2: metrics 展示标准化（低风险）✅ 已完成

**目标**：统一 metrics 字段位置和格式

#### 2.1 标准化 metrics 位置

| 事件类型 | metrics 位置 | 说明 |
|----------|--------------|------|
| `step_completed` | `snapshot.metrics` | Step 级 metrics |
| `run_completed` | `data.metrics` | Run 级聚合 metrics |

#### 2.2 前端统一读取

```typescript
function getEventMetrics(event: SSEEvent): Metrics | undefined {
  // 优先从 snapshot 读取（step 级）
  if (event.snapshot?.metrics) {
    return event.snapshot.metrics
  }
  // 其次从 data 读取（run 级）
  if (event.data?.metrics) {
    return event.data.metrics
  }
  return undefined
}
```

---

### Phase 3: 前端事件处理统一（中风险）✅ 已完成

**目标**：合并 `eventHandlers.ts` 和 `nestedExecutionHandlers.ts`

#### 3.1 新建统一处理器

```typescript
// utils/executionTreeBuilder.ts

interface ExecutionTreeBuilder {
  // 状态
  executions: Map<string, RunnableExecution>  // run_id -> execution
  rootRunId: string | null
  
  // 方法
  processEvent(event: SSEEvent): void
  getTree(): RunnableExecution | null
}
```

#### 3.2 事件处理逻辑

```typescript
processEvent(event: SSEEvent) {
  switch (event.type) {
    case 'run_started':
      this.handleRunStarted(event)
      break
    case 'run_completed':
    case 'run_failed':
      this.handleRunEnded(event)
      break
    case 'step_delta':
    case 'step_completed':
      this.handleStepEvent(event)
      break
    // ... workflow events
  }
}

handleRunStarted(event: SSEEvent) {
  const exec: RunnableExecution = {
    id: event.run_id,
    runnableId: event.runnable_id || event.nested_runnable_id || '',
    runnableType: event.runnable_type || (event.workflow_type ? 'workflow' : 'agent'),
    nestingType: event.nesting_type,
    parentRunId: event.parent_run_id,
    depth: event.depth,
    status: 'running',
    steps: [],
    children: [],
  }
  
  this.executions.set(event.run_id, exec)
  
  // 建立父子关系
  if (event.parent_run_id && this.executions.has(event.parent_run_id)) {
    const parent = this.executions.get(event.parent_run_id)!
    parent.children.push(exec)
  } else {
    this.rootRunId = event.run_id
  }
}
```

#### 3.3 移除旧代码

- 删除 `utils/nestedExecutionHandlers.ts`
- 重构 `utils/eventHandlers.ts` 使用新的 `ExecutionTreeBuilder`
- 简化 `hooks/useSSEStream.ts`

---

### Phase 4: 前端展示组件统一（高风险）

**目标**：统一 Runnable 展示组件

#### 4.1 新建统一组件

```typescript
// components/RunnableExecutionView.tsx

interface RunnableExecutionViewProps {
  execution: RunnableExecution
  isRoot?: boolean
}

function RunnableExecutionView({ execution, isRoot }: RunnableExecutionViewProps) {
  // 1. 渲染头部（根据 runnableType）
  // 2. 渲染 steps
  // 3. 递归渲染 children
  // 4. 处理并发展示（多个 running children）
}
```

#### 4.2 组件结构

```
RunnableExecutionView
├── ExecutionHeader (显示 Runnable 名称、类型、状态)
├── ExecutionSteps (渲染 steps 列表)
│   ├── AssistantContent
│   ├── ToolCallItem
│   │   └── 如果是 RunnableTool，展开显示对应 child
│   └── ToolResultItem
└── ExecutionChildren
    ├── 单个 child: 直接递归渲染
    └── 多个并发 children: Tab/Slider 展示
```

#### 4.3 合并现有组件

| 现有组件 | 处理方式 |
|----------|----------|
| `WorkflowContainer` | 合并到 `RunnableExecutionView` |
| `PipelineStages` | 作为 `ExecutionChildren` 的 pipeline 展示模式 |
| `ParallelBranchSlider` | 合并到 `ExecutionChildren` 的并发展示 |
| `ParallelNestedRunnables` | 合并到 `ExecutionChildren` |

#### 4.4 迁移策略

1. 先新建 `RunnableExecutionView`，与现有组件并存
2. 在 `ChatTimeline` 中增加 feature flag 切换
3. 验证新组件功能后，逐步删除旧组件

## 五、风险评估

### 5.1 风险矩阵

| Phase | 风险等级 | 影响范围 | 回滚难度 |
|-------|----------|----------|----------|
| Phase 1 | 低 | 后端新增字段 | 简单（删除字段） |
| Phase 2 | 低 | 前端 metrics 读取 | 简单（回退代码） |
| Phase 3 | 中 | 前端事件处理 | 中等（需要完整测试） |
| Phase 4 | 高 | 前端组件重构 | 复杂（涉及多组件） |

### 5.2 缓解措施

**Phase 1-2**：
- 增量添加，不破坏现有逻辑
- 前端可选择性使用新字段

**Phase 3**：
- 保留旧代码作为 fallback
- 新旧处理器并行运行，对比输出

**Phase 4**：
- Feature flag 控制新旧组件切换
- 分步骤迁移，每步验证后再继续

### 5.3 测试策略

| 场景 | 测试方法 |
|------|----------|
| 顶层 Agent 执行 | 手动测试 + 截图对比 |
| RunnableTool 嵌套 | 调用 code_assistant 等嵌套 Agent |
| Pipeline Workflow | 执行多阶段 pipeline |
| Parallel Workflow | 执行并发分支 |
| 嵌套 Workflow | Workflow 内部调用另一个 Workflow |
| 并发 RunnableTool | Agent 同时调用多个 RunnableTool |

## 六、实施顺序

**推荐顺序**：Phase 1 → Phase 2 → Phase 3 → Phase 4

| 阶段 | 预估工时 | 依赖 |
|------|----------|------|
| Phase 1 | 0.5 天 | 无 |
| Phase 2 | 0.5 天 | Phase 1 |
| Phase 3 | 1-2 天 | Phase 1 |
| Phase 4 | 2-3 天 | Phase 3 |

**总计**：4-6 天

## 七、验收标准

1. **功能验收**：
   - [ ] 顶层 Agent 执行正常显示
   - [ ] RunnableTool 嵌套执行可展开查看内部步骤
   - [ ] Pipeline Workflow 按阶段显示
   - [ ] Parallel Workflow/并发 RunnableTool 使用 Tab 切换
   - [ ] 任意深度嵌套正确渲染

2. **代码质量**：
   - [ ] 删除 `nestedExecutionHandlers.ts`
   - [ ] 统一使用 `RunnableExecution` 类型
   - [ ] 组件数量减少（合并 4 个为 1 个）

3. **性能指标**：
   - [ ] 大量事件时无明显卡顿
   - [ ] 内存占用无异常增长

