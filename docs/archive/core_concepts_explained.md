# Agio 核心概念详解

## 概念层级关系

```
Agent Execution
    └── Run (一次完整的执行)
          ├── Steps (执行的步骤)
          │     ├── Step 1: LLM Call
          │     ├── Step 2: Tool Call  
          │     └── Step 3: LLM Call
          ├── Events (实时事件流)
          │     ├── run_started
          │     ├── text_delta (流式内容)
          │     ├── tool_call_started
          │     └── run_completed
          └── Checkpoints (可选的状态快照)
                ├── Checkpoint 1 (after Step 1)
                └── Checkpoint 2 (after Step 2)
```

---

## 1. Run (运行)

### 定义
**Run** 是 Agent 执行一次完整对话的记录。每次用户发送消息，Agent 处理并回复，就是一个 Run。

### 数据结构
```python
class AgentRun:
    id: str                    # 唯一标识符
    agent_id: str              # 哪个 Agent
    user_id: str               # 哪个用户
    session_id: str            # 哪个会话
    input_query: str           # 用户输入
    status: RunStatus          # 状态：starting/running/completed/failed
    
    steps: list[AgentRunStep]  # 执行步骤列表
    response_content: str      # 最终回复
    metrics: AgentRunMetrics   # 性能指标（tokens, 耗时等）
    
    created_at: datetime
    updated_at: datetime
```

### 生命周期
```
1. User Input → Run Created (status: starting)
2. Agent Processing → Run Running (status: running)
3. Agent Response → Run Completed (status: completed)
```

### MongoDB 存储
- **Collection**: `runs`
- **Document Example**:
```json
{
  "id": "run_abc123",
  "agent_id": "simple_assistant",
  "user_id": "user_456",
  "session_id": "sess_789",
  "input_query": "Hello",
  "status": "completed",
  "response_content": "Hello! How can I assist you today?",
  "steps": [...],
  "metrics": {
    "total_tokens": 35,
    "duration": 1.2
  },
  "created_at": "2025-11-21T10:30:00Z"
}
```

---

## 2. Step (步骤)

### 定义
**Step** 是 Run 内部的一个执行单元。复杂的对话可能需要多个步骤（多轮 LLM 调用 + Tool 调用）。

### 数据结构
```python
class AgentRunStep:
    id: str
    run_id: str
    step_num: int               # 步骤编号 (1, 2, 3...)
    
    # 请求快照 (100% 可重放)
    request_snapshot: RequestSnapshot
    # 响应快照
    response_snapshot: ResponseSnapshot
    
    # 结构化数据
    messages_context: list[Message]      # 上下文消息
    model_response: AssistantMessage     # LLM 响应
    tool_results: list[ToolResult]       # Tool 执行结果
    
    metrics: LLMCallMetrics              # 本步骤指标
```

### 典型执行流程

#### 简单对话 (1 Step)
```
User: "Hello"
  Step 1: LLM Call → "Hello! How can I help?"
Result: 1 step
```

#### 复杂对话 (多 Steps)
```
User: "What's the weather in Beijing?"
  Step 1: LLM Call → decides to use weather_tool
  Step 2: Tool Call (weather_tool) → gets weather data
  Step 3: LLM Call → formats response with data
Result: 3 steps
```

### Step 的重要性
- **完全可重放**: `request_snapshot` 包含所有参数
- **调试利器**: 可以精确定位哪一步出错
- **性能分析**: 每步的 tokens 和耗时

---

## 3. Event (事件)

### 定义
**Event** 是执行过程中发出的实时事件流，用于流式响应和监控。

### 事件类型
```python
class EventType(Enum):
    # Run 生命周期
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    
    # 流式内容
    TEXT_DELTA = "text_delta"           # 增量文本
    
    # Step 事件
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    
    # Tool 事件
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    
    # 指标更新
    USAGE_UPDATE = "usage_update"
```

### 数据结构
```python
class AgentEvent:
    type: EventType
    run_id: str
    timestamp: datetime
    data: dict                # 事件数据
    metadata: dict            # 额外元数据
```

### Event vs Step 的区别

| 维度 | Event | Step |
|------|-------|------|
| **目的** | 实时通知、流式响应 | 完整记录、可重放 |
| **粒度** | 细粒度（每个 token） | 粗粒度（整个 LLM 调用） |
| **存储** | 可选（监控用） | 必须（审计用） |
| **用途** | SSE 流、实时 UI | 调试、重放、分析 |

### MongoDB 存储
- **Collection**: `events`
- **Document Example**:
```json
{
  "id": "evt_xyz",
  "run_id": "run_abc123",
  "sequence": 1,
  "event_type": "text_delta",
  "timestamp": "2025-11-21T10:30:01.234Z",
  "data": {
    "content": "Hello",
    "step": 1
  }
}
```

### Event 流示例
```
event: run_started
data: {"query": "Hi"}

event: text_delta
data: {"content": "Hello", "step": 1}

event: text_delta
data: {"content": "!", "step": 1}

event: text_delta
data: {"content": " How", "step": 1}

event: usage_update
data: {"usage": {"total_tokens": 35}, "step": 1}

event: run_completed
data: {"response": "Hello! How can I assist?", "metrics": {...}}
```

---

## 4. Checkpoint (检查点)

### 定义
**Checkpoint** 是 Run 执行过程中某个时刻的完整状态快照，可用于恢复、Fork、或回滚。

### 数据结构
```python
class Checkpoint:
    id: str
    run_id: str
    step_num: int              # 哪个 step 之后的快照
    
    # 完整状态
    messages: list[Message]    # 当前对话历史
    metrics: AgentRunMetrics   # 当前指标
    agent_config: dict         # Agent 配置
    
    description: str           # 描述
    created_at: datetime
```

### 使用场景

#### 1. 人工干预点
```
User: "Book a flight to Paris"
  Step 1: LLM → "I'll search flights"
  → Checkpoint 1 (before expensive tool call)
  Step 2: Tool → Search flights (expensive API)
```

#### 2. Fork 实验
```
原始对话:
  User: "Explain AI"
  Step 1-3: Normal explanation
  → Checkpoint A
  
从 Checkpoint A Fork:
  Branch 1: Technical explanation
  Branch 2: Simple explanation
```

#### 3. 错误恢复
```
Run fails at Step 5
→ Restore from Checkpoint at Step 3
→ Retry with different parameters
```

---

## 完整数据流

### 执行流程
```
1. User sends message
   ↓
2. Create Run (status: starting)
   ↓
3. For each reasoning step:
   a. Create Step
   b. Emit event: step_started
   c. Call LLM
   d. Emit events: text_delta (streaming)
   e. Record Step result
   f. Emit event: step_completed
   g. [Optional] Create Checkpoint
   ↓
4. Update Run (status: completed)
   ↓
5. Emit event: run_completed
   ↓
6. Save to MongoDB:
   - runs collection ← Run
   - events collection ← Events (optional)
```

### MongoDB 数据关系
```
runs (1)  ──────┐
                ├── has many ──→ events (N)
                │                 (run_id foreign key)
                │
                ├── embeds ──→ steps (array)
                │              (stored in run document)
                │
                └── has many ──→ checkpoints (N)
                                 (run_id foreign key)
```

---

## 为什么需要这些概念？

### 1. Run
- **用户视角**: "我和 Agent 的一次对话"
- **业务需求**: 审计、计费、分析

### 2. Step  
- **开发者视角**: "Agent 内部推理过程"
- **技术需求**: 调试、优化、重放

### 3. Event
- **实时性**: "正在发生什么"
- **用户体验**: 流式响应、进度显示

### 4. Checkpoint
- **可控性**: "人工介入点"
- **实验性**: Fork 不同策略

---

## 当前代码中的实现

### 1. Run 定义
📁 `agio/domain/run.py`
```python
class AgentRun(BaseModel):
    id: str
    agent_id: str
    steps: list[AgentRunStep]  # 嵌入的 steps
    response_content: str
    metrics: AgentRunMetrics
```

### 2. Step 定义  
📁 `agio/domain/run.py`
```python
class AgentRunStep(BaseModel):
    step_num: int
    request_snapshot: RequestSnapshot   # 完整请求
    response_snapshot: ResponseSnapshot # 完整响应
    messages_context: list[Message]
    tool_results: list[ToolResult]
```

### 3. Event 定义
📁 `agio/protocol/events.py`
```python
class AgentEvent(BaseModel):
    type: EventType
    run_id: str
    timestamp: datetime
    data: dict
```

### 4. 存储接口
📁 `agio/db/repository.py`
```python
class AgentRunRepository(ABC):
    async def save_run(run: AgentRun)
    async def get_run(run_id: str)
    async def save_event(event: AgentEvent, sequence: int)
    async def get_events(run_id: str)
```

---

## 总结

| 概念 | 用途 | 粒度 | 存储 | 关系 |
|------|------|------|------|------|
| **Run** | 完整对话记录 | 粗 | 必须 | 1 个 Run 包含 N 个 Steps/Events |
| **Step** | 推理步骤记录 | 中 | 嵌入 Run | 嵌入在 Run 中 |
| **Event** | 实时事件流 | 细 | 可选 | 属于某个 Run |
| **Checkpoint** | 状态快照 | 中 | 可选 | 关联某个 Run 的某个 Step |

**核心理解**:
- Run = 用户视角的"一次对话"
- Step = Agent 内部的"推理步骤"  
- Event = 实时的"发生了什么"
- Checkpoint = 可恢复的"时光机"
