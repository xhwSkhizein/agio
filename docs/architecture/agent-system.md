# Agent 系统

Agent 是 Agio 的核心执行引擎，负责 LLM 调用循环、工具执行、上下文管理和事件流发射。

## 设计理念

**简化优先**：Agent 是唯一的执行单元，不需要额外的抽象层（移除了 Runnable 协议和 RunnableExecutor）。

**直接编码**：通过代码直接创建和配置 Agent，而不是复杂的配置系统。

---

## 核心组件

### Agent

**职责**：Agent 是执行容器，负责协调 LLM 调用、工具执行和事件发射。

```python
from agio import Agent, OpenAIModel

agent = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    tools=[bash_tool, file_read_tool],
    session_store=session_store,  # 可选：持久化会话
    permission_manager=permission_manager,  # 可选：工具权限控制
    skill_manager=skill_manager,  # 可选：Agent Skills 支持
    name="my_agent",
    system_prompt="You are a helpful assistant.",
    max_steps=10,
    enable_termination_summary=True,  # 达到 max_steps 时生成摘要
)
```

**关键属性**：
- `model`: LLM 模型实例（OpenAIModel, AnthropicModel, DeepseekModel）
- `tools`: 工具列表，包括内置工具和 AgentTool
- `session_store`: 会话存储，用于持久化 Steps
- `permission_manager`: 工具权限管理器（HITL - Human-in-the-Loop）
- `skill_manager`: Agent Skills 管理器（支持 agentskills.io 规范）
- `system_prompt`: 系统提示词（支持 Jinja2 模板）
- `max_steps`: 最大执行步数
- `enable_termination_summary`: 是否启用终止摘要

### AgentExecutor

**职责**：完整的 LLM 执行循环，是 Agent 的执行引擎。

```python
class AgentExecutor:
    async def execute(
        self,
        messages: list[dict],
        context: ExecutionContext,
        *,
        pending_tool_calls: list[dict] | None = None,
        abort_signal: AbortSignal | None = None,
    ) -> RunOutput:
        """执行 LLM 调用循环"""
        ...
```

**执行流程**：

```
while step_count < max_steps:
    1. 调用 LLM
       └─► model.arun_stream(messages, tools)
       └─► 流式接收响应
       └─► 累积 Tool Calls
    
    2. 创建 Assistant Step
       └─► pipeline.commit_step(step)
       └─► 写入 STEP_CREATED 事件到 Wire
       └─► 保存到 SessionStore（如果启用）
    
    3. 检查 Tool Calls
       ├─► 有 Tool Calls
       │   ├─► ToolExecutor.execute_batch(tool_calls)
       │   ├─► 创建 Tool Steps
       │   ├─► 保存到 SessionStore
       │   └─► 将结果添加到 messages
       └─► 无 Tool Calls
           └─► 退出循环（LLM 完成响应）
    
    4. 检查终止条件
       ├─► max_steps 达到
       ├─► abort_signal 触发
       └─► LLM 返回 finish_reason="stop"
```

### ToolExecutor

**职责**：工具批量执行器，支持并发执行多个工具调用。

```python
class ToolExecutor:
    async def execute_batch(
        self,
        tool_calls: list[dict],
        context: ExecutionContext,
        abort_signal: AbortSignal | None = None,
    ) -> list[ToolResult]:
        """批量执行工具调用"""
        ...
```

**特点**：
- 批量执行：一次 LLM 调用可能返回多个 tool_calls
- 并发安全：每个工具调用使用独立的上下文
- 错误隔离：单个工具失败不影响其他工具
- 权限检查：可选的 HITL 工具权限控制

---

## 执行模式

### 1. 流式执行（run_stream）

**用于顶层执行**，自动创建 Wire 和 ExecutionContext：

```python
# 创建 Agent
agent = Agent(...)

# 流式执行
async for event in agent.run_stream("Hello, world!"):
    if event.type == "STEP_CREATED" and event.step:
        # 实时处理事件
        print(f"{event.step.role}: {event.step.content}")
```

**特点**：
- 自动创建 Wire 和 ExecutionContext
- 返回 AsyncIterator[StepEvent]
- 适合顶层调用和 API 接口
- 支持可选的 TraceCollector 包装

**内部流程**：

```python
async def run_stream(
    self,
    user_input: str,
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    metadata: dict | None = None,
    trace_store: TraceStore | None = None,
) -> AsyncIterator[StepEvent]:
    # 1. 创建 Wire 和 Context
    wire = Wire()
    context = ExecutionContext(
        run_id=str(uuid4()),
        session_id=session_id or str(uuid4()),
        wire=wire,
        user_id=user_id,
        metadata=metadata or {},
    )
    
    # 2. 创建 Pipeline
    pipeline = StepPipeline(context, self.session_store)
    
    # 3. 启动后台执行任务
    async def _run_task():
        await self.run(user_input, context=context, pipeline=pipeline)
    
    task = asyncio.create_task(_run_task())
    
    # 4. 流式返回事件
    event_stream = wire.read()
    if trace_store:
        collector = TraceCollector(store=trace_store)
        event_stream = collector.wrap_stream(event_stream, ...)
    
    async for event in event_stream:
        yield event
```

### 2. 直接执行（run）

**用于嵌套执行**，需要外部提供 context 和 wire：

```python
# 嵌套执行（由 AgentTool 调用）
context = ExecutionContext(...)
result = await agent.run(
    user_input="Research AI trends",
    context=context,
)

print(result.response)
print(result.metrics)
```

**特点**：
- 需要外部提供 ExecutionContext（包含 wire）
- 返回 RunOutput（同步结果）
- 适合嵌套调用（AgentTool）
- 事件写入到共享的 Wire

---

## 上下文管理

### ExecutionContext

**职责**：携带执行上下文信息，在整个执行链中传递。

```python
@dataclass(frozen=True)
class ExecutionContext:
    run_id: str
    session_id: str
    wire: Wire
    user_id: str | None = None
    runnable_type: RunnableType = RunnableType.AGENT
    runnable_id: str | None = None
    metadata: dict = field(default_factory=dict)
    
    # 嵌套相关
    parent_run_id: str | None = None
    nested_runnable_id: str | None = None
    nesting_type: str | None = None  # "tool_call" | "parallel"
    depth: int = 0
```

**关键方法**：

```python
def child(
    self,
    run_id: str,
    *,
    nested_runnable_id: str | None = None,
    runnable_type: RunnableType | None = None,
    nesting_type: str | None = None,
    metadata: dict | None = None,
) -> "ExecutionContext":
    """创建子上下文（用于嵌套执行）"""
    return ExecutionContext(
        run_id=run_id,
        session_id=self.session_id,  # 继承 session_id
        wire=self.wire,  # 共享 wire
        user_id=self.user_id,
        parent_run_id=self.run_id,
        depth=self.depth + 1,
        nested_runnable_id=nested_runnable_id,
        runnable_type=runnable_type or self.runnable_type,
        nesting_type=nesting_type,
        metadata=metadata or {},
    )
```

### StepPipeline

**职责**：管理 Step 的创建、保存和事件发射。

```python
class StepPipeline:
    def __init__(
        self,
        context: ExecutionContext,
        session_store: SessionStore | None = None,
    ):
        self.context = context
        self.session_store = session_store
        self._sequence = 0
    
    async def allocate_sequence(self) -> int:
        """分配新的 Step sequence"""
        ...
    
    async def commit_step(self, step: Step) -> None:
        """提交 Step（保存 + 发射事件）"""
        # 1. 保存到 SessionStore
        if self.session_store:
            await self.session_store.save_step(step)
        
        # 2. 发射 STEP_CREATED 事件到 Wire
        await self.context.wire.write(StepEvent(
            type=StepEventType.STEP_CREATED,
            run_id=self.context.run_id,
            step=step,
        ))
```

### RunLifecycle

**职责**：管理 Run 的生命周期（RUN_STARTED、RUN_COMPLETED、RUN_FAILED）。

```python
class RunLifecycle:
    async def __aenter__(self):
        # 写入 RUN_STARTED 事件
        await self.context.wire.write(StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=self.context.run_id,
            data={"input": self.input},
        ))
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 写入 RUN_COMPLETED 或 RUN_FAILED 事件
        if exc_type:
            await self.context.wire.write(StepEvent(
                type=StepEventType.RUN_FAILED,
                run_id=self.context.run_id,
                data={"error": str(exc_val)},
            ))
        else:
            await self.context.wire.write(StepEvent(
                type=StepEventType.RUN_COMPLETED,
                run_id=self.context.run_id,
                data={"output": self.output},
            ))
```

---

## System Prompt 渲染

### Jinja2 模板支持

Agent 的 `system_prompt` 支持 Jinja2 模板，在运行时动态渲染：

```python
agent = Agent(
    model=model,
    system_prompt="""
You are {{ agent.name }}.

Working directory: {{ work_dir }}
Current date: {{ date }}

{% if tools %}
Available tools:
{% for tool in tools %}
- {{ tool.name }}: {{ tool.description }}
{% endfor %}
{% endif %}

{% if skills %}
Available skills:
{% for skill in skills %}
- {{ skill.name }}: {{ skill.description }}
{% endfor %}
{% endif %}
""",
)
```

**可用变量**：
- `work_dir`: 当前工作目录
- `date`: 当前日期
- `tools`: 工具列表（如果有）
- `skills`: 技能列表（如果启用 Skills）

**渲染时机**：
- 在 `Agent._build_system_prompt()` 中渲染
- 每次 `run()` 调用时都会重新渲染
- 支持动态内容（如当前时间）

---

## 工具执行

### 工具调用格式

LLM 返回的 Tool Calls 格式（OpenAI 标准）：

```json
{
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "bash",
        "arguments": "{\"command\": \"ls -la\"}"
      }
    }
  ]
}
```

### 执行流程

```python
# 1. AgentExecutor 收到 LLM 响应（包含 tool_calls）
assistant_step = Step(
    role=MessageRole.ASSISTANT,
    content="Let me check the directory.",
    tool_calls=[...],
)

# 2. ToolExecutor 批量执行
results = await tool_executor.execute_batch(
    tool_calls=assistant_step.tool_calls,
    context=context,
)

# 3. 为每个结果创建 Tool Step
for result in results:
    tool_step = StepFactory(context).tool_step(
        sequence=await pipeline.allocate_sequence(),
        tool_call_id=result.tool_call_id,
        name=result.tool_name,
        content=result.output,
    )
    await pipeline.commit_step(tool_step)

# 4. 添加到消息列表（供下次 LLM 调用）
for result in results:
    messages.append({
        "role": "tool",
        "tool_call_id": result.tool_call_id,
        "name": result.tool_name,
        "content": result.output,
    })
```

---

## Agent 嵌套

### AgentTool

**职责**：将 Agent 包装为 BaseTool，实现 Agent 嵌套和多 Agent 协作。

```python
from agio import Agent, as_tool

# 创建专家 Agent
research_agent = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    name="research_agent",
    system_prompt="You are a research expert.",
)

# 转换为工具
research_tool = as_tool(
    research_agent,
    description="Expert at research tasks",
    max_depth=5,  # 最大嵌套深度
)

# 创建编排 Agent
orchestrator = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    tools=[research_tool],
    name="orchestrator",
)

# 运行编排 Agent
async for event in orchestrator.run_stream("Research AI trends"):
    print(event)
```

**Wire 共享**：

```
Orchestrator Agent
    │
    ├─► Wire (共享)
    │
    ├─► LLM 调用
    │   └─► 返回 tool_call: call_research_agent
    │
    ├─► ToolExecutor 执行 research_tool
    │   └─► AgentTool.execute()
    │       ├─► 创建子 ExecutionContext
    │       │   └─► wire = parent_context.wire (共享)
    │       ├─► research_agent.run(context=child_ctx)
    │       │   └─► 事件写入到共享的 wire
    │       └─► 返回 ToolResult
    │
    └─► 继续 LLM 循环
```

**安全特性**：
- **深度限制**：默认最多 5 层嵌套
- **循环检测**：检测 call stack 中的循环（A → B → A）
- **错误隔离**：嵌套 Agent 错误不会中断父 Agent

---

## 终止摘要

当 Agent 达到 `max_steps` 限制时，可以生成终止摘要：

```python
agent = Agent(
    model=model,
    max_steps=10,
    enable_termination_summary=True,
    termination_summary_prompt="""
**IMPORTANT: Execution Limit Reached**

You have reached the maximum step limit. Please provide:
1. A summary of what you've accomplished
2. What remains to be done
3. Any recommendations for next steps
""",
)
```

**终止消息构建**：

```python
def build_termination_messages(
    messages: list[dict],
    pending_tool_calls: list[dict] | None,
    termination_reason: str,
    custom_prompt: str | None = None,
) -> list[dict]:
    """
    构建终止摘要的消息列表。
    
    1. 保留现有消息历史
    2. 为未执行的 Tool Calls 添加占位消息
    3. 添加用户提示，请求生成摘要
    """
    ...
```

---

## 指标追踪

### MetricsTracker

内部指标追踪器，聚合执行统计：

```python
class MetricsTracker:
    def track(self, step: Step):
        """追踪 Step 指标"""
        if step.role == MessageRole.ASSISTANT:
            self.assistant_steps_count += 1
            if step.tool_calls:
                self.tool_calls_count += len(step.tool_calls)
            if step.metrics:
                self.total_tokens += step.metrics.total_tokens or 0
        elif step.role == MessageRole.TOOL:
            self.tool_steps_count += 1
    
    def get_metrics(self) -> RunMetrics:
        """获取聚合指标"""
        return RunMetrics(
            total_tokens=self.total_tokens,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            steps_count=self.steps_count,
            tool_calls_count=self.tool_calls_count,
        )
```

---

## 使用示例

### 基础示例

```python
import asyncio
from agio import Agent, OpenAIModel

async def main():
    # 创建 Agent
    agent = Agent(
        model=OpenAIModel(model_name="gpt-4o"),
        name="assistant",
        system_prompt="You are a helpful assistant.",
        max_steps=10,
    )
    
    # 流式执行
    async for event in agent.run_stream("Hello, world!"):
        if event.type == "STEP_CREATED" and event.step:
            print(f"{event.step.role}: {event.step.content}")

asyncio.run(main())
```

### 带工具的示例

```python
from agio import Agent, OpenAIModel
from agio.tools import get_tool_registry

# 获取工具
registry = get_tool_registry()
bash_tool = registry.get("bash")
file_read_tool = registry.get("file_read")

# 创建 Agent
agent = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    tools=[bash_tool, file_read_tool],
    system_prompt="You are a helpful assistant with access to bash and file reading.",
    max_steps=20,
)

# 运行
async for event in agent.run_stream("List files in current directory"):
    ...
```

### 多 Agent 协作示例

```python
from agio import Agent, OpenAIModel, as_tool

# 专家 Agent
researcher = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    name="researcher",
    system_prompt="You are an expert researcher.",
)

coder = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    name="coder",
    system_prompt="You are an expert programmer.",
)

# 转换为工具
research_tool = as_tool(researcher, "Expert at research")
code_tool = as_tool(coder, "Expert at coding")

# 编排 Agent
orchestrator = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    tools=[research_tool, code_tool],
    name="orchestrator",
    system_prompt="You coordinate between research and coding experts.",
)

# 运行
async for event in orchestrator.run_stream("Build a web scraper"):
    ...
```

---

## 最佳实践

### 1. System Prompt 设计

- **明确角色**：清晰定义 Agent 的角色和职责
- **工具说明**：使用 Jinja2 模板自动列出可用工具
- **约束条件**：明确设置步数限制、输出格式等

### 2. 工具使用策略

- **工具选择**：只包含必要的工具，避免工具过多导致混乱
- **并发执行**：工具自然支持并发，LLM 可以一次调用多个工具
- **错误处理**：工具执行失败时，Agent 可以继续执行

### 3. 嵌套 Agent

- **职责分离**：Master 负责规划，Specialist 负责执行
- **上下文隔离**：使用独立的 Agent 避免上下文污染
- **深度限制**：合理设置 max_depth，避免无限嵌套

### 4. 性能优化

- **步数限制**：合理设置 `max_steps`，避免无限循环
- **Token 管理**：使用 `max_tokens` 限制输出长度
- **Session Store**：对于长对话使用持久化存储

### 5. 可观测性

- **TraceCollector**：使用 TraceCollector 收集执行追踪
- **事件监听**：通过 Wire 监听执行事件
- **指标监控**：关注 Token 使用、执行时间等指标

---

## Agent Skills 集成

Agio 支持 [Agent Skills](https://agentskills.io/specification) 规范。

### 技能发现

技能存储在 `skills/` 目录（或通过 `AGIO_SKILLS_DIR` 环境变量配置）：

```
skills/
└── skill-name/
    ├── SKILL.md          # 必需：技能定义
    ├── scripts/          # 可选：可执行脚本
    ├── references/       # 可选：参考文档
    └── assets/           # 可选：静态资源
```

### 渐进式披露

1. **启动阶段**：仅加载技能元数据（name + description）
2. **激活阶段**：LLM 调用 Skill 工具后加载完整 SKILL.md
3. **执行阶段**：按需加载 scripts/、references/、assets/

### 使用示例

```python
# 启用 Skills（默认启用）
agent = Agent(
    model=model,
    enable_skills=True,
    skill_dirs=["./skills", "~/.agio/skills"],
)

# 当用户任务匹配技能描述时，LLM 会自动调用 Skill 工具
# User: "提取 PDF 文本"
# → LLM 调用 Skill(skill_name="pdf-processing")
# → 技能内容注入上下文
# → LLM 按照技能指令执行任务
```

---

## 相关代码

- `agio/agent/agent.py`: Agent 类
- `agio/agent/executor.py`: AgentExecutor
- `agio/agent/helper.py`: 辅助函数
- `agio/agent/summarizer.py`: 终止摘要
- `agio/tools/executor.py`: ToolExecutor
- `agio/runtime/agent_tool.py`: AgentTool
- `agio/runtime/context.py`: ExecutionContext
- `agio/runtime/pipeline.py`: StepPipeline
- `agio/runtime/lifecycle.py`: RunLifecycle
- `agio/skills/`: Agent Skills 系统
