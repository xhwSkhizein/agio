# Agio 核心架构重构方案 (Final v3)

基于 **"Native Message Stream" (原生消息流)** 的统一架构。

## 核心理念

1.  **原生对齐**: 数据库中的 Step 直接对应 LLM 的 `Message` 结构。使用 `user`, `assistant`, `tool` 角色，**零转换**直接构建 Context。
2.  **Step 即 Event**: 前端不再区分 "历史加载" 和 "实时流"，统一使用 Step 数据结构。实时流只是 Step 的增量更新 (Delta)。
3.  **扁平化**: 只有 `steps` 表。Run 只是一个逻辑 ID。

---

## 1. 数据模型设计

### 1.1 Step (即 Message)

完全复用 LLM 的 Message 定义，外加元数据。

```python
class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class Step(BaseModel):
    # --- 索引与关联 ---
    id: str
    session_id: str            # 归属会话
    run_id: str                # 归属轮次 (逻辑分组)
    sequence: int              # 会话内的全局序号 (1, 2, 3...)
    
    # --- 核心内容 (Standard LLM Message) ---
    role: MessageRole          # 直接使用原生角色
    
    content: str | None        # User/Assistant/Tool 的文本内容
    
    # Assistant 专属
    tool_calls: list[dict] | None  # [{"id": "call_1", "function": {...}}]
    
    # Tool 专属
    tool_call_id: str | None   # 对应哪个调用
    name: str | None           # 工具名称
    
    # --- 元数据 (Metrics & Status) ---
    metrics: StepMetrics | None
    created_at: datetime
```

### 1.2 StepMetrics (明确定义)

```python
class StepMetrics(BaseModel):
    # 耗时
    duration_ms: float | None        # 执行耗时
    
    # Token 消耗 (仅 Assistant/Model Step 有效)
    input_tokens: int|None
    output_tokens: int|None
    total_tokens: int|None
    cache_tokens: int|None
    
    # 模型信息
    model_name: str | None     # e.g. "gpt-4"
    provider: str | None       # e.g. "openai"
    
    # 扩展字段
    first_token_latency_ms: float | None # 首字延迟

    # 工具执行信息（仅 Tool Step 有效）
    tool_exec_time_ms: float | None
    tool_exec_start_at: int | None  # 开始执行时间
    tool_exec_end_at: int | None    # 结束执行时间
```

---

## 2. 场景实现

### 2.1 极简 Context 构建

因为 Step 结构就是 Message 结构，所以构建 Context 不需要任何转换逻辑。

```python
def build_context(session_id: str) -> list[dict]:
    # 1. 查询: SELECT * FROM steps WHERE session_id = ? ORDER BY sequence
    steps = repository.get_steps(session_id)
    
    # 2. 映射: 直接 dump 为 dict (过滤掉 metrics 等非 LLM 字段)
    messages = [
        {
            "role": s.role,
            "content": s.content,
            "tool_calls": s.tool_calls,
            "tool_call_id": s.tool_call_id,
            "name": s.name
        }
        for s in steps
    ]
    
    # 3. 插入 System Prompt (如果数据库里没存 System Step)
    messages.insert(0, {"role": "system", "content": agent.system_prompt})
    
    return messages
```

### 2.2 场景: 从 Sequence N 重试 (Retry)

**定义**: 撤销 N 之后的操作，从 N 重新开始生成。

```python
async def retry_from_sequence(session_id: str, sequence: int):
    # 1. 物理删除 (或软删除) 该 Session 中 sequence >= N 的所有 steps
    #    这样保证 sequence 的唯一性和连续性
    await repository.delete_steps(session_id, start_seq=sequence)
    
    # 2. 获取被保留的最后一个 Step (作为触发点)
    #    如果是 User Input，则重新触发 LLM
    #    如果是 Tool Result，则重新触发 LLM (带上 Tool Result)
    #    如果是 Assistant，则判断是否包含Tool Calls，如果包含ToolCall则执行工具调用并记录ToolResult后重新触发LLM
    last_step = await repository.get_last_step(session_id)
    
    # 3. 启动 Agent Loop
    #    Loop 会自动加载剩余的 Context 并开始生成新的 Step (Seq=N)
    await agent_loop.run(session_id)
```

### 2.3 场景: 从 Sequence N Fork (分支)

**定义**: 复制 N 之前的状态到新会话，在新会话中继续。

```python
async def fork_session(original_session_id: str, sequence: int) -> str:
    # 1. 创建新 Session ID
    new_session_id = generate_uuid()
    
    # 2. 读取原始 Steps (<= N)
    source_steps = await repository.get_steps(original_session_id, end_seq=sequence)
    
    # 3. 批量复制到新 Session
    new_steps = [
        step.copy(update={"session_id": new_session_id}) 
        for step in source_steps
    ]
    await repository.bulk_insert(new_steps)
    
    # 4. 在新 Session 启动 Agent Loop
    await agent_loop.run(new_session_id)
    
    return new_session_id
```

---

## 3. 统一的前端交互 (Unified Event/Step)

**核心观点**: 废弃独立的 `Event` 对象。前端只认识 `Step`。
实时流本质上是 `Step` 对象的**增量传输 (Delta Transfer)**。

### 3.1 协议定义

前端接收到的 SSE 消息格式统一为：

```json
{
  "type": "step_update",  // 只有这一种核心类型
  "id": "step_123",       // Step ID
  "delta": {              // 增量数据
    "content": "Hello",   // 文本追加
    "tool_calls": ...     // 工具调用追加
  },
  "snapshot": { ... }     // 可选：完整状态 (用于 step_completed)
}
```

### 3.2 前端处理逻辑

前端维护一个 `steps` 数组。无论是加载历史还是接收实时流，逻辑一致。

```javascript
// 前端伪代码
const steps = ref({}); // Map<id, Step>

function onMessage(payload) {
  const { id, delta, snapshot } = payload;
  
  if (!steps.value[id]) {
    // 新 Step: 初始化
    steps.value[id] = { content: "", ...snapshot };
  }
  
  if (delta) {
    // 实时流: 拼接内容
    if (delta.content) steps.value[id].content += delta.content;
    // ... 处理其他 delta
  }
  
  if (snapshot) {
    // 完成: 最终一致性覆盖 (确保 metrics 等元数据正确)
    steps.value[id] = snapshot;
  }
}

// 加载历史
async function loadHistory() {
  const list = await api.getSteps();
  list.forEach(step => {
    // 历史数据直接作为 snapshot 处理，逻辑复用
    onMessage({ id: step.id, snapshot: step });
  });
}
```

### 3.3 优势
1.  **代码复用**: 一套解析逻辑同时处理历史和实时。
2.  **无缝体验**: 用户刷新页面，看到的结构与实时生成时完全一致。
3.  **断点续传**: 如果网络中断，前端只需重新拉取一次 `getSteps` 即可对齐状态，无需复杂的补漏逻辑。

---

## 4. 总结

这是最终极的简化方案。

*   **存储**: `steps` 表 (Native Message 格式)。
*   **计算**: Context = `Select *`.
*   **交互**: Event = Step Delta.
*   **扩展**: Retry = Delete & Resume; Fork = Copy & Resume.

系统复杂度降低到了理论最低值。
