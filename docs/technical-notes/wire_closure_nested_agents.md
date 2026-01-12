# Wire 关闭机制与嵌套 Agent 调用的兼容性分析

## 背景

在修复 SSE 流无法关闭的问题时，我们修改了 `agent.run_stream()` 方法，在 `_run_task()` 完成后立即关闭 Wire。这引发了一个重要的问题：

**在嵌套 Agent 调用（AgentAsTool）中，子 Agent 会使用父 Agent 的 Wire，这样的修改会不会导致子 Agent 提前关闭父 Agent 的 Wire？**

## 架构设计分析

### 两种调用方式

Agio 的 Agent 提供了两种执行方法：

#### 1. `run_stream()` - 顶层流式调用
```python
async def run_stream(
    self,
    user_input: str,
    *,
    session_id: str | None = None,
    ...
) -> AsyncIterator[StepEvent]:
    """创建 Wire 并流式返回事件"""
    wire = Wire()  # ✅ 创建自己的 Wire
    context = self._build_execution_context(run_id, session_id, wire, ...)
    
    async def _run_and_close():
        try:
            await self.run(context=context, ...)
        finally:
            await wire.close()  # ✅ 关闭自己创建的 Wire
    
    task = asyncio.create_task(_run_and_close())
    async for event in wire.read():
        yield event
```

**使用场景**：API 端点、顶层执行
**Wire 归属**：自己创建，自己关闭

#### 2. `run()` - 嵌套调用
```python
async def run(
    self,
    user_input: str,
    *,
    context: ExecutionContext,  # ← 接收父级的 context（包含 Wire）
    ...
) -> RunOutput:
    """接收 context，不创建也不关闭 Wire"""
    # 使用传入的 context.wire 写事件
    # 返回 RunOutput
    # ✅ 不关闭 Wire
```

**使用场景**：AgentTool 嵌套调用
**Wire 归属**：父级传入，不归自己所有

### AgentTool 的实现

```python
# agio/runtime/agent_tool.py
class AgentTool(BaseTool):
    async def execute(
        self,
        parameters: dict,
        context: ExecutionContext,  # ← 父级的 context
        ...
    ) -> ToolResult:
        # 创建子 context，继承父级的 Wire
        child_context = context.child(
            run_id=new_run_id,
            nested_runnable_id=self.agent.id,
            ...
        )
        
        # 调用 agent.run()，传入 child_context
        result = await self.agent.run(
            input_text,
            context=child_context  # ← 使用父级的 Wire
        )
        
        return ToolResult(...)
        # ✅ 不关闭 Wire，Wire 属于父级
```

## 调用流程图

```
┌─────────────────────────────────────────────────────────┐
│ 顶层调用: agent.run_stream("question")                 │
│                                                         │
│  1. wire = Wire() ← 创建 Wire                          │
│  2. context = ExecutionContext(wire=wire)              │
│  3. 启动 _run_and_close():                             │
│      ├─ 调用 agent.run(context=context)                │
│      │   ├─ 执行，写事件到 wire                        │
│      │   └─ 如果调用了 AgentTool:                      │
│      │       └─ AgentTool.execute(context=context)     │
│      │           ├─ child_ctx = context.child(...)     │
│      │           │   └─ child_ctx.wire = context.wire  │
│      │           ├─ nested_agent.run(context=child_ctx)│
│      │           │   ├─ 写事件到 child_ctx.wire        │
│      │           │   │   = context.wire (父级的)      │
│      │           │   └─ 返回 RunOutput ✓               │
│      │           │      (不关闭 Wire)                  │
│      │           └─ 返回 ToolResult ✓                  │
│      └─ finally: wire.close() ✅                       │
│         (只有顶层关闭 Wire)                            │
│                                                         │
│  4. async for event in wire.read():                    │
│      yield event                                       │
│                                                         │
│  5. 流正常结束 ✅                                      │
└─────────────────────────────────────────────────────────┘
```

## 关键设计原则

### 1. Wire 所有权明确
- **创建者负责关闭**：只有 `run_stream()` 创建 Wire，只有它关闭 Wire
- **接收者只使用**：`run(context=...)` 接收 Wire，只使用不关闭

### 2. Context 传递层次清晰
```python
context.child(...)  # 创建子 context
├─ 继承 wire: 子 context 使用父级的 Wire
├─ 新 run_id: 每个执行有独立的 run_id
└─ 增加 depth: 嵌套深度 +1
```

### 3. 方法职责分离
| 方法 | 创建 Wire | 接收 Wire | 关闭 Wire | 使用场景 |
|------|-----------|-----------|-----------|----------|
| `run_stream()` | ✅ | ❌ | ✅ | API 端点 |
| `run()` | ❌ | ✅ | ❌ | 嵌套调用 |

## 测试验证

### 测试覆盖

创建了 `tests/test_nested_agent_stream.py`，验证：

1. ✅ **单层嵌套**：嵌套 Agent 不会关闭父级 Wire
2. ✅ **多个嵌套**：多个嵌套 Agent 顺序调用都正常
3. ✅ **深层嵌套**：3 层嵌套调用正常工作

### 测试结果

```bash
$ uv run pytest tests/test_nested_agent_stream.py -v

✅ test_nested_agent_does_not_close_parent_wire PASSED
✅ test_multiple_nested_calls_in_sequence PASSED  
✅ test_deeply_nested_agents PASSED

3 passed
```

### 关键观察

从测试输出可以看到：
- 所有层级的 Agent 事件都正常流出（多个不同的 run_id）
- 嵌套 Agent 的 `RUN_COMPLETED` 事件正常发送
- 父级 Agent 最后发送 `RUN_COMPLETED` 
- Wire 在所有嵌套执行完成后才关闭
- 流正常结束，没有死锁或提前关闭

## 结论

**修改安全** ✅

Wire 关闭机制与嵌套 Agent 调用**完全兼容**，原因：

1. **设计分离**：`run_stream()` 和 `run()` 职责明确
   - `run_stream()`：创建并关闭 Wire
   - `run()`：使用传入的 Wire，不关闭

2. **调用路径清晰**：
   - 顶层调用 → `run_stream()` → 创建 Wire → 关闭 Wire ✅
   - 嵌套调用 → `run(context=parent_context)` → 使用父级 Wire → 不关闭 ❌

3. **所有权明确**：Wire 由创建者负责关闭，接收者只使用

4. **测试验证**：所有嵌套场景测试通过

## 推荐实践

### 使用建议

1. **API 端点**：使用 `run_stream()`
   ```python
   async for event in agent.run_stream(query):
       yield format_sse(event)
   ```

2. **嵌套调用**：使用 `run(context=...)`
   ```python
   result = await agent.run(query, context=parent_context)
   ```

3. **不要混用**：不要在嵌套调用中使用 `run_stream()`
   ```python
   # ❌ 错误：嵌套中不要创建新 Wire
   async for event in nested_agent.run_stream(query):
       pass  # 会创建独立的 Wire，事件不会传递给父级
   
   # ✅ 正确：使用 run() 共享父级 Wire
   result = await nested_agent.run(query, context=child_context)
   ```

## 相关文件

- `/agio/agent/agent.py` - Agent 实现
- `/agio/runtime/agent_tool.py` - AgentTool 实现
- `/agio/runtime/wire.py` - Wire 实现
- `/tests/test_nested_agent_stream.py` - 嵌套调用测试
- `/tests/test_stream_closure.py` - 流关闭测试
