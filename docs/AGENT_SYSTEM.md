# Agent 系统

Agent 系统是 Agio 的核心执行引擎，负责 LLM 调用循环、工具执行、上下文构建和记忆管理。

## 架构设计

```
Agent (配置容器)
    │
    └─► AgentExecutor (执行引擎)
        ├─► 上下文构建 (build_context_from_steps)
        ├─► LLM 调用循环
        │   ├─► 调用 LLM
        │   ├─► 解析 Tool Calls
        │   └─► 批量执行工具
        ├─► 事件流写入 (Wire)
        ├─► Step 持久化
        └─► 指标追踪
```

## 核心组件

### Agent

**职责**：Agent 配置容器，实现 `Runnable` 协议

```python
class Agent:
    def __init__(
        self,
        model: Model,
        tools: list[BaseTool] | None = None,
        session_store: SessionStore | None = None,
        name: str = "agio_agent",
        system_prompt: str | None = None,
        max_steps: int = 10,
        enable_termination_summary: bool = False,
    ):
        ...
    
    async def run(
        self,
        input: str,
        *,
        context: ExecutionContext,
        abort_signal: AbortSignal | None = None,
    ) -> RunOutput:
        ...
```

**关键属性**：
- `model`: LLM 模型实例
- `tools`: 工具列表（包括 Skill 工具，如果启用技能）
- `session_store`: 会话存储（用于持久化 Steps）
- `system_prompt`: 系统提示词（运行时用 Jinja2 渲染，自动注入 agent/model/tools/session/env 和可用技能列表）
- `max_steps`: 最大执行步数
- `enable_termination_summary`: 是否启用终止摘要
- `_skill_manager`: SkillManager 实例（如果启用技能）

### AgentExecutor

**职责**：完整的 LLM 执行单元

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
        ...
```

**执行流程**：

1. **LLM 调用循环**：
   - 调用 LLM，获取响应
   - 解析 Tool Calls（支持流式累积）
   - 如果有 Tool Calls，批量执行工具
   - 将工具结果添加到消息列表
   - 继续循环，直到没有 Tool Calls 或达到最大步数

2. **事件流写入**：
   - 每次 LLM 调用：写入 `STEP_CREATED` 事件（Assistant Step）
   - 每次工具执行：写入 `STEP_CREATED` 事件（Tool Step）
   - 执行完成：写入 `RUN_COMPLETED` 事件

3. **Step 持久化**：
   - 通过 `StepRepository` 保存 Steps 到 SessionStore
   - 支持会话历史查询

4. **指标追踪**：
   - Token 使用统计
   - 步数统计
   - 工具调用统计

### ToolExecutor

**职责**：工具批量执行器

```python
class ToolExecutor:
    async def execute_batch(
        self,
        tool_calls: list[dict],
        context: ExecutionContext,
        abort_signal: AbortSignal | None = None,
    ) -> list[ToolResult]:
        ...
```

**特点**：
- 支持批量执行多个工具调用
- 并发安全：每个工具调用使用独立的执行上下文
- 错误处理：单个工具失败不影响其他工具
- 结果收集：返回所有工具的执行结果

### 上下文构建

**职责**：从历史 Steps 构建 LLM 消息列表

```python
async def build_context_from_steps(
    session_id: str,
    session_store: SessionStore,
    system_prompt: str | None = None,
    run_id: str | None = None,
    node_id: str | None = None,
    runnable_id: str | None = None,
) -> list[dict]:
    ...
```

**工作流程**：

1. **查询 Steps**：
   - 从 SessionStore 查询历史 Steps
   - 支持过滤条件（run_id, node_id, runnable_id）

2. **转换为消息**：
   - 使用 `StepAdapter.steps_to_messages()` 转换
   - 格式：OpenAI 消息格式（role: user/assistant/tool）

3. **添加系统提示**：
   - 如果有 system_prompt，先使用 Jinja2 渲染（上下文：`agent/model/tools/session/env`），再插入到消息列表开头

**过滤选项**：
- `run_id`: 仅包含特定 Run 的 Steps（用于隔离 Agent 上下文）
- `node_id`: 仅包含特定节点的 Steps
- `runnable_id`: 仅包含特定 Runnable 的 Steps

## 执行流程

### 完整执行流程

```
1. API Entry Point
   └─► 创建 Wire + ExecutionContext
   
2. Agent.run()
   ├─► 创建 User Step
   │   └─► 保存到 SessionStore
   ├─► 构建上下文
   │   └─► build_context_from_steps()
   │       └─► 查询历史 Steps
   │       └─► 转换为消息列表
   └─► AgentExecutor.execute()
       ├─► LLM 调用循环
       │   ├─► 调用 LLM
       │   ├─► 解析 Tool Calls
       │   ├─► 批量执行工具
       │   └─► 写入事件到 Wire
       ├─► Step 持久化
       └─► 返回 RunOutput
```

### LLM 调用循环

```
while step_count < max_steps:
    1. 调用 LLM
       └─► 流式接收响应
       └─► 累积 Tool Calls
    
    2. 创建 Assistant Step
       └─► 写入 STEP_CREATED 事件
       └─► 保存到 SessionStore
    
    3. 检查是否有 Tool Calls
       ├─► 有 Tool Calls
       │   ├─► 批量执行工具
       │   ├─► 创建 Tool Steps
       │   └─► 将结果添加到消息列表
       └─► 无 Tool Calls
           └─► 退出循环
    
    4. 检查终止条件
       ├─► max_steps 达到
       ├─► abort_signal 触发
       └─► LLM 返回 finish_reason="stop"
```

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
        "name": "file_read",
        "arguments": "{\"path\": \"/path/to/file\"}"
      }
    }
  ]
}
```

### 批量执行流程

```python
# 1. 解析 Tool Calls
tool_calls = response.tool_calls

# 2. 批量执行
results = await tool_executor.execute_batch(
    tool_calls=tool_calls,
    context=context,
)

# 3. 创建 Tool Steps
for result in results:
    tool_step = sf.tool_step(
        sequence=seq,
        tool_call_id=result.tool_call_id,
        content=result.output,
        tool_name=result.tool_name,
    )
    await session_store.save_step(tool_step)
    
# 4. 添加到消息列表（供下次 LLM 调用）
for result in results:
    messages.append({
        "role": "tool",
        "tool_call_id": result.tool_call_id,
        "name": result.tool_name,
        "content": result.output,
    })
```

## 终止摘要

当 Agent 执行被中断（如达到 max_steps）时，可以生成终止摘要：

```python
if enable_termination_summary:
    termination_messages = build_termination_messages(
        messages=messages,
        pending_tool_calls=pending_tool_calls,
        termination_reason="max_steps",
        custom_prompt=renderer.render(
            termination_summary_prompt,
            agent=agent_context,
            session=context,
            env=os.environ,
        )
        if termination_summary_prompt
        else None,
    )
    
    # 调用 LLM 生成摘要
    summary_response = await model.arun_stream(
        messages=termination_messages,
        tools=None,
    )
```

**终止消息构建**：

1. 保留现有消息历史
2. 为未执行的 Tool Calls 添加占位消息
3. 添加用户提示，请求生成摘要

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
        elif step.role == MessageRole.TOOL:
            # 工具执行统计
            ...
    
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

**追踪指标**：
- `total_tokens`: 总 Token 数
- `input_tokens`: 输入 Token 数
- `output_tokens`: 输出 Token 数
- `steps_count`: 总步数
- `tool_calls_count`: 工具调用次数

## 使用示例

### 创建 Agent

```python
from agio import Agent
from agio.llm import Model
from agio.tools import BaseTool

# 创建 Agent
agent = Agent(
    model=model,
    tools=[file_read_tool, web_search_tool],
    session_store=session_store,
    name="research_agent",
    system_prompt="You are a research assistant.",
    max_steps=20,
)
```

### 执行 Agent

```python
from agio.runtime import Wire, RunnableExecutor
from agio.runtime.protocol import ExecutionContext

# 创建执行上下文
wire = Wire()
context = ExecutionContext(
    run_id=str(uuid4()),
    session_id=session_id,
    wire=wire,
)

# 执行 Agent
executor = RunnableExecutor(store=session_store)
result = await executor.execute(
    runnable=agent,
    input="Research the latest AI trends",
    context=context,
)

print(result.response)
print(result.metrics)
```

### 流式事件监听

```python
# 消费事件流
async for event in wire.read():
    if event.type == StepEventType.STEP_CREATED:
        step = event.step
        if step.role == MessageRole.ASSISTANT:
            print(f"Assistant: {step.content}")
        elif step.role == MessageRole.TOOL:
            print(f"Tool {step.tool_name}: {step.content}")
```

## 配置示例

### YAML 配置

```yaml
type: agent
name: research_agent
description: "Research assistant with web search"
model: deepseek
system_prompt: |
  You are {{ agent.name }}, a research assistant.
  Use tools: {% for t in tools %}{{ t.name }} {% endfor %}
tools:
  - web_search
  - web_fetch
session_store: mongodb_session_store
max_steps: 15
enabled: true
```

### 使用 Agent 作为工具

```yaml
type: agent
name: master_orchestrator
model: deepseek-reasoner
tools:
  - agent_tool:
      agent: research_agent
      description: "Expert researcher for web information"
```

## 最佳实践

1. **系统提示词**：明确 Agent 的角色和能力
2. **工具选择**：只包含必要的工具，避免工具过多导致混乱
3. **步数限制**：合理设置 `max_steps`，避免无限循环
4. **上下文过滤**：使用 `run_id` 过滤，隔离不同 Run 的上下文
5. **错误处理**：工具执行失败时，Agent 可以继续执行
6. **终止摘要**：对于长时间运行的 Agent，启用终止摘要

## Agent Skills 集成

Agio 支持 [Agent Skills](https://agentskills.io/specification) 规范，通过渐进式披露机制优化上下文使用。

### 技能发现

技能存储在 `skills/` 目录（或通过 `AGIO_SKILLS_DIR` 环境变量配置）。每个技能是一个包含 `SKILL.md` 文件的目录：

```
skills/
└── skill-name/
    ├── SKILL.md          # 必需：技能定义文件
    ├── scripts/          # 可选：可执行脚本
    ├── references/       # 可选：参考文档
    └── assets/           # 可选：静态资源
```

### 技能激活

1. **启动阶段**：系统启动时发现所有技能，仅加载元数据（name + description）到系统提示词
2. **激活阶段**：LLM 通过 Skill 工具激活技能，加载完整 SKILL.md 内容到上下文
3. **执行阶段**：按需加载 scripts/、references/、assets/ 资源

### 配置

在 Agent 配置中启用技能：

```yaml
type: agent
name: my_agent
model: claude
enable_skills: true  # 默认启用
skill_dirs:          # 可选：覆盖全局配置
  - skills
  - ~/.agio/skills
```

### 使用示例

当用户任务匹配技能描述时，LLM 会自动调用 Skill 工具激活技能：

```
User: "提取 PDF 文本"
→ LLM 调用 Skill(skill_name="pdf-processing")
→ 技能内容注入上下文
→ LLM 按照技能指令执行任务
```

详见：[Agent Skills 集成方案](../refactor_support_agent_skills.md)

## 相关代码

- `agio/agent/agent.py`: Agent 类
- `agio/agent/executor.py`: AgentExecutor
- `agio/agent/context.py`: 上下文构建
- `agio/agent/summarizer.py`: 终止摘要
- `agio/tools/executor.py`: ToolExecutor
- `agio/skills/`: Agent Skills 系统

