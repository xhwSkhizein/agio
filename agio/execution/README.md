# Execution Package

`agio.execution` 包含 Agio 的执行引擎，负责管理 Agent 运行的完整生命周期。

## 📦 模块概览

### `runner.py` - StepRunner

管理 Agent Run 的完整生命周期：

```python
from agio.execution.runner import StepRunner, ExecutionConfig
from agio.core import AgentSession

# 创建 Runner
config = ExecutionConfig(
    max_steps=20,
    parallel_tool_calls=True,
    timeout_per_step=120.0
)

runner = StepRunner(
    agent=agent,
    hooks=[],
    config=config,
    repository=repository
)

# 运行
session = AgentSession(session_id="session_123")
async for event in runner.run_stream(session, "Hello!"):
    print(event)
```

**主要功能**：
- 管理 Run 生命周期（创建、启动、完成）
- 协调 StepExecutor 和 ToolExecutor
- 触发 Hook 回调
- 保存 Steps 到 Repository
- 发送事件流

### `step_executor.py` - StepExecutor

执行 LLM 调用循环：

```python
from agio.execution.step_executor import StepExecutor

executor = StepExecutor(model=model, tools=tools)

# 执行
async for event in executor.execute(
    session_id="session_123",
    run_id="run_456",
    messages=messages,
    start_sequence=1
):
    if event.type == StepEventType.STEP_DELTA:
        print(event.delta.content, end="")
```

**主要功能**：
- 调用 LLM 模型
- 处理流式响应
- 检测工具调用
- 生成 Step 对象
- 发送增量事件

### `tool_executor.py` - ToolExecutor

执行工具调用：

```python
from agio.execution.tool_executor import ToolExecutor

executor = ToolExecutor(tools=[search_tool, calculator_tool])

# 执行单个工具
result = await executor.execute(tool_call)

# 批量执行
results = await executor.execute_batch(tool_calls)
```

**主要功能**：
- 查找工具
- 解析参数
- 执行工具
- 错误处理
- 返回 ToolResult

### `context.py` - 上下文构建

从 Steps 构建 LLM 上下文：

```python
from agio.execution.context import build_context_from_steps

# 构建完整上下文
messages = await build_context_from_steps(
    session_id="session_123",
    repository=repository,
    system_prompt="You are helpful"
)

# 构建指定范围
messages = await build_context_from_sequence_range(
    session_id="session_123",
    repository=repository,
    start_seq=1,
    end_seq=10
)
```

**主要功能**：
- 从 Repository 加载 Steps
- 使用 StepAdapter 转换为消息
- 添加 system prompt
- 验证上下文格式

### `retry.py` - 重试机制

从指定序列重试执行：

```python
from agio.execution.retry import retry_from_sequence

# 删除从序列 5 开始的所有 steps
deleted = await repository.delete_steps("session_123", start_seq=5)

# 从序列 4 恢复
last_step = await repository.get_last_step("session_123")
async for event in runner.resume_from_user_step("session_123", last_step):
    print(event)
```

### `fork.py` - Fork 管理

创建执行分支：

```python
from agio.execution.fork import fork_session

# Fork 到新 session
new_session_id = await fork_session(
    original_session_id="session_123",
    fork_at_sequence=5,
    repository=repository
)

# 新 session 包含序列 1-5 的副本
```

## 🔄 执行流程

### 1. 完整运行流程

```
User Query
    ↓
StepRunner.run_stream()
    ↓
1. Create AgentRun
2. Create User Step
3. Save to Repository
    ↓
StepExecutor.execute()
    ↓
4. Build context from Steps
5. Call LLM model
6. Stream response
    ↓
7. Create Assistant Step
8. Save to Repository
    ↓
If tool_calls:
    ↓
ToolExecutor.execute_batch()
    ↓
9. Execute tools
10. Create Tool Steps
11. Save to Repository
    ↓
Loop back to step 4
    ↓
Final Response
```

### 2. 事件流

```python
async for event in runner.run_stream(session, query):
    match event.type:
        case StepEventType.RUN_STARTED:
            # Run 开始
            print(f"Run {event.run_id} started")
        
        case StepEventType.STEP_DELTA:
            # 内容增量（流式）
            print(event.delta.content, end="")
        
        case StepEventType.STEP_COMPLETED:
            # Step 完成
            step = event.snapshot
            print(f"\nStep {step.sequence} completed")
        
        case StepEventType.TOOL_CALL_STARTED:
            # 工具调用开始
            print(f"Calling tool: {event.tool_name}")
        
        case StepEventType.TOOL_CALL_COMPLETED:
            # 工具调用完成
            result = event.tool_result
            print(f"Tool result: {result.content}")
        
        case StepEventType.RUN_COMPLETED:
            # Run 完成
            print(f"Run completed: {event.metrics}")
```

## 🎯 核心概念

### ExecutionConfig

运行时配置：

```python
from agio.core import ExecutionConfig

config = ExecutionConfig(
    # 最大步骤数
    max_steps=20,
    
    # 并行工具调用
    parallel_tool_calls=True,
    
    # 每步超时（秒）
    timeout_per_step=120.0,
    
    # 启用重试
    enable_retry=True,
    max_retries=3,
    
    # 流式输出
    stream=True
)
```

### Step Sequence

每个 Step 都有全局序列号：

```
Sequence 1: USER    - "Hello"
Sequence 2: ASSISTANT - "Hi! Let me search..."
Sequence 3: TOOL    - search results
Sequence 4: ASSISTANT - "Based on results..."
```

序列号用于：
- 排序和查询
- Resume/Fork 定位
- 上下文构建

### Context Building

从 Steps 构建 LLM 上下文：

```python
# 1. 加载 Steps
steps = await repository.get_steps("session_123")

# 2. 转换为消息
messages = StepAdapter.steps_to_messages(steps)

# 3. 添加 system prompt
if system_prompt:
    messages.insert(0, {"role": "system", "content": system_prompt})

# 4. 发送给 LLM
response = await model.arun_stream(messages, tools=tools)
```

## 🔧 高级用法

### 自定义 Hook

```python
from agio.agent.hooks import AgentHook

class MetricsHook(AgentHook):
    async def on_run_start(self, run: AgentRun):
        print(f"Run {run.id} started")
    
    async def on_step_end(self, run: AgentRun, step: Step):
        if step.metrics:
            print(f"Tokens: {step.metrics.total_tokens}")
    
    async def on_run_end(self, run: AgentRun):
        print(f"Run {run.id} completed")

# 使用
runner = StepRunner(agent=agent, hooks=[MetricsHook()])
```

### Resume from Step

```python
# 获取最后一个 Step
last_step = await repository.get_last_step("session_123")

# 从该 Step 恢复
if last_step.is_user_step():
    async for event in runner.resume_from_user_step(
        "session_123", 
        last_step
    ):
        print(event)
```

### Fork Session

```python
# Fork 到新 session（复制前 N 个 steps）
new_session_id = await fork_session(
    original_session_id="session_123",
    fork_at_sequence=5,
    repository=repository
)

# 在新 session 中继续
async for event in runner.run_stream(
    AgentSession(session_id=new_session_id),
    "Continue from fork"
):
    print(event)
```

### Retry from Sequence

```python
# 删除从序列 5 开始的所有 steps
deleted = await repository.delete_steps("session_123", start_seq=5)

# 获取最后一个 step（现在是序列 4）
last_step = await repository.get_last_step("session_123")

# 重新生成
async for event in runner.resume_from_user_step("session_123", last_step):
    print(event)
```

## 📊 性能优化

### 1. 并行工具调用

```python
config = ExecutionConfig(parallel_tool_calls=True)

# 多个工具调用会并行执行
results = await tool_executor.execute_batch(tool_calls)
```

### 2. 上下文窗口管理

```python
# 只加载最近的 N 个 steps
messages = await build_context_from_sequence_range(
    session_id="session_123",
    repository=repository,
    start_seq=max(1, current_seq - 20),
    end_seq=current_seq
)
```

### 3. 流式输出

```python
# 启用流式输出以获得更好的用户体验
config = ExecutionConfig(stream=True)

async for event in runner.run_stream(session, query):
    if event.type == StepEventType.STEP_DELTA:
        # 实时显示内容
        print(event.delta.content, end="", flush=True)
```

## 🧪 测试

运行测试：

```bash
# 所有执行相关测试
pytest tests/test_step_*.py tests/test_tool_executor.py -v

# 集成测试
pytest tests/test_step_integration.py -v
```

## 🔗 相关文档

- [Core Package](../core/README.md) - 核心数据模型
- [Storage Package](../storage/README.md) - 持久化层
- [Agent Package](../agent/README.md) - Agent 核心
- [DESIGN.md](DESIGN.md) - 详细设计文档
