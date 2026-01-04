> status: Draft 

# Agent Hooks 系统设计

## 核心需求分析

| 场景 | 需要访问 | 需要修改 |
|------|---------|---------|
| 动态更新 System Prompt | 历史 steps、工具结果 | messages |
| 注入工具上下文 | tools、当前状态 | messages (临时) |
| 保存到 Memory | 完整执行历史、output | 外部存储 |
| 动态工具选择 | 当前迭代、历史 | tool_schemas |

**关键洞察**：Hook 需要区分 **持久修改**（影响后续所有调用）和 **临时注入**（仅本次 LLM 调用）

---

## 完整实现

```python
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Awaitable
from abc import ABC
import copy

if TYPE_CHECKING:
    from typing import Self


# ═══════════════════════════════════════════════════════════════════════════
# Hook Context
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class HookContext:
    """
    Rich execution context available to all hooks.
    
    - `messages`: Canonical message history. Modifications persist across iterations.
    - `store`: Shared state between hooks within the same run.
    """

    # ─── Identifiers ───
    run_id: str
    session_id: str

    # ─── Message History (mutable) ───
    messages: list[dict]

    # ─── Resources (read-only) ───
    model: "Model"
    tools: list["BaseTool"]
    config: "ExecutionConfig"

    # ─── Execution Progress ───
    iteration: int = 0
    steps: list["Step"] = field(default_factory=list)
    tracker: "MetricsTracker" = field(default_factory=lambda: MetricsTracker())

    # ─── Shared State (hooks can store custom data here) ───
    store: dict[str, Any] = field(default_factory=dict)

    # ─── Tool Control ───
    _disabled_tools: set[str] = field(default_factory=set)
    _tool_schemas: list[dict] = field(default_factory=list)

    # ─────────────────────────────────────────────────────────────────
    # System Prompt Helpers
    # ─────────────────────────────────────────────────────────────────

    def get_system_message(self) -> dict | None:
        """Get the system message if it exists."""
        return next((m for m in self.messages if m.get("role") == "system"), None)

    def set_system_prompt(self, content: str) -> None:
        """Set or replace the system prompt."""
        if msg := self.get_system_message():
            msg["content"] = content
        else:
            self.messages.insert(0, {"role": "system", "content": content})

    def append_to_system_prompt(self, content: str, separator: str = "\n\n") -> None:
        """Append content to the existing system prompt."""
        if msg := self.get_system_message():
            msg["content"] = f"{msg['content']}{separator}{content}"
        else:
            self.set_system_prompt(content)

    def prepend_to_system_prompt(self, content: str, separator: str = "\n\n") -> None:
        """Prepend content to the existing system prompt."""
        if msg := self.get_system_message():
            msg["content"] = f"{content}{separator}{msg['content']}"
        else:
            self.set_system_prompt(content)

    # ─────────────────────────────────────────────────────────────────
    # Message Helpers
    # ─────────────────────────────────────────────────────────────────

    def get_last_user_message(self) -> dict | None:
        """Get the most recent user message."""
        return next((m for m in reversed(self.messages) if m.get("role") == "user"), None)

    def get_messages_by_role(self, role: str) -> list[dict]:
        """Get all messages with a specific role."""
        return [m for m in self.messages if m.get("role") == role]

    # ─────────────────────────────────────────────────────────────────
    # Step Helpers
    # ─────────────────────────────────────────────────────────────────

    def get_last_step(self, step_type: str | None = None) -> "Step | None":
        """Get the last step, optionally filtered by type ('assistant' or 'tool')."""
        for step in reversed(self.steps):
            if step_type is None or step.type == step_type:
                return step
        return None

    def get_last_assistant_step(self) -> "Step | None":
        """Get the last assistant (LLM) step."""
        return self.get_last_step("assistant")

    def get_last_tool_step(self) -> "Step | None":
        """Get the last tool step."""
        return self.get_last_step("tool")

    def get_tool_steps(self, tool_name: str | None = None) -> list["Step"]:
        """Get all tool steps, optionally filtered by tool name."""
        return [
            s for s in self.steps
            if s.type == "tool" and (tool_name is None or s.name == tool_name)
        ]

    def get_tool_results(self, tool_name: str | None = None) -> list[str]:
        """Get content from all tool steps."""
        return [s.content for s in self.get_tool_steps(tool_name) if s.content]

    # ─────────────────────────────────────────────────────────────────
    # Tool Control
    # ─────────────────────────────────────────────────────────────────

    def disable_tool(self, name: str) -> None:
        """Disable a tool for subsequent LLM calls."""
        self._disabled_tools.add(name)

    def enable_tool(self, name: str) -> None:
        """Re-enable a previously disabled tool."""
        self._disabled_tools.discard(name)

    def disable_all_tools(self) -> None:
        """Disable all tools."""
        self._disabled_tools = {t.name for t in self.tools}

    def enable_all_tools(self) -> None:
        """Enable all tools."""
        self._disabled_tools.clear()

    def get_active_tool_schemas(self) -> list[dict] | None:
        """Get tool schemas excluding disabled tools."""
        if not self._tool_schemas:
            return None
        if not self._disabled_tools:
            return self._tool_schemas
        return [
            s for s in self._tool_schemas
            if s.get("function", {}).get("name") not in self._disabled_tools
        ]

    # ─────────────────────────────────────────────────────────────────
    # Metrics Access
    # ─────────────────────────────────────────────────────────────────

    @property
    def total_tokens(self) -> int:
        return self.tracker.total_tokens

    @property
    def tool_calls_count(self) -> int:
        return self.tracker.tool_calls_count


# ═══════════════════════════════════════════════════════════════════════════
# LLM Request (for on_llm_start)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class LLMRequest:
    """
    Represents the request about to be sent to LLM.
    
    Modify `messages` or `tools` to change what gets sent to the LLM.
    These modifications are FOR THIS CALL ONLY and won't affect ctx.messages.
    """
    messages: list[dict]
    tools: list[dict] | None

    def inject_message(self, content: str, role: str = "user", *, before_last_user: bool = True) -> None:
        """
        Inject a temporary message.
        
        Args:
            content: Message content
            role: Message role
            before_last_user: If True, insert before the last user message
        """
        msg = {"role": role, "content": content}
        
        if before_last_user:
            # Find last user message
            for i in range(len(self.messages) - 1, -1, -1):
                if self.messages[i].get("role") == "user":
                    self.messages.insert(i, msg)
                    return
        
        self.messages.append(msg)

    def inject_system_context(self, content: str) -> None:
        """Inject context by appending to system prompt (temporary, this call only)."""
        for msg in self.messages:
            if msg.get("role") == "system":
                msg["content"] = f"{msg['content']}\n\n{content}"
                return
        self.messages.insert(0, {"role": "system", "content": content})


# ═══════════════════════════════════════════════════════════════════════════
# Tool Call Context (for tool hooks)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ToolCallInfo:
    """Information about a tool call."""
    id: str
    name: str
    arguments: dict[str, Any]

    def update_argument(self, key: str, value: Any) -> None:
        """Update a tool argument."""
        self.arguments[key] = value


@dataclass
class ToolResultInfo:
    """Information about a tool execution result."""
    tool_call_id: str
    tool_name: str
    content: str
    success: bool
    duration: float | None
    error: str | None = None


# ═══════════════════════════════════════════════════════════════════════════
# Hook Base Class
# ═══════════════════════════════════════════════════════════════════════════


class AgentHook(ABC):
    """
    Base class for agent execution hooks.
    
    Override any method to hook into the execution lifecycle.
    All methods are optional - only implement what you need.
    
    Modification patterns:
    - Modify `ctx.messages` for PERSISTENT changes across iterations
    - Modify `request.messages` in on_llm_start for THIS CALL ONLY
    - Return modified objects where the signature allows
    """

    async def on_run_start(self, ctx: HookContext) -> None:
        """
        Called once at the start of execution.
        
        Use cases:
        - Initialize ctx.store with custom state
        - Set up initial system prompt based on session history
        - Load context from external memory
        """
        pass

    async def on_llm_start(self, ctx: HookContext, request: LLMRequest) -> None:
        """
        Called before each LLM call.
        
        Args:
            ctx: Full execution context. Modify ctx.messages for persistent changes.
            request: The request to be sent. Modify for this call only.
        
        Use cases:
        - Inject temporary context (modify request.messages)
        - Update system prompt based on previous results (modify ctx.messages)
        - Dynamically adjust available tools (modify request.tools)
        """
        pass

    async def on_llm_end(self, ctx: HookContext, step: "Step") -> None:
        """
        Called after each LLM call completes.
        
        Args:
            ctx: Execution context (step is already added to ctx.steps)
            step: The completed assistant step
        
        Use cases:
        - Log LLM responses
        - Analyze token usage
        - Trigger external notifications
        """
        pass

    async def on_tool_start(self, ctx: HookContext, tool_call: ToolCallInfo) -> None:
        """
        Called before each individual tool execution.
        
        Args:
            ctx: Execution context
            tool_call: Tool call info (can modify arguments in place)
        
        Use cases:
        - Validate/sanitize tool arguments
        - Log tool invocations
        - Inject additional parameters
        """
        pass

    async def on_tool_end(
        self, ctx: HookContext, tool_call: ToolCallInfo, result: ToolResultInfo
    ) -> None:
        """
        Called after each individual tool execution.
        
        Args:
            ctx: Execution context
            tool_call: The tool call that was executed
            result: The execution result
        
        Use cases:
        - Log tool results
        - Track tool success/failure rates
        - Update ctx.store with tool outputs for later use
        """
        pass

    async def on_run_end(self, ctx: HookContext, output: "RunOutput") -> "RunOutput":
        """
        Called before returning the final result.
        
        Args:
            ctx: Final execution context with all steps
            output: The output about to be returned
        
        Returns:
            Modified output (or original if no changes needed)
        
        Use cases:
        - Save execution to memory/database
        - Post-process response content
        - Add custom metadata to output
        """
        return output

    async def on_error(self, ctx: HookContext, error: Exception) -> None:
        """
        Called when an unhandled error occurs.
        
        Args:
            ctx: Execution context at time of error
            error: The exception that occurred
        
        Use cases:
        - Error logging/alerting
        - Cleanup resources
        - Save partial results
        """
        pass


# ═══════════════════════════════════════════════════════════════════════════
# Hook Manager
# ═══════════════════════════════════════════════════════════════════════════


class HookManager:
    """Manages hook execution with error isolation."""

    def __init__(self, hooks: list[AgentHook] | None = None):
        self.hooks = hooks or []

    async def on_run_start(self, ctx: HookContext) -> None:
        for hook in self.hooks:
            await self._safe_call(hook.on_run_start, ctx)

    async def on_llm_start(self, ctx: HookContext, request: LLMRequest) -> None:
        for hook in self.hooks:
            await self._safe_call(hook.on_llm_start, ctx, request)

    async def on_llm_end(self, ctx: HookContext, step: "Step") -> None:
        for hook in self.hooks:
            await self._safe_call(hook.on_llm_end, ctx, step)

    async def on_tool_start(self, ctx: HookContext, tool_call: ToolCallInfo) -> None:
        for hook in self.hooks:
            await self._safe_call(hook.on_tool_start, ctx, tool_call)

    async def on_tool_end(
        self, ctx: HookContext, tool_call: ToolCallInfo, result: ToolResultInfo
    ) -> None:
        for hook in self.hooks:
            await self._safe_call(hook.on_tool_end, ctx, tool_call, result)

    async def on_run_end(self, ctx: HookContext, output: "RunOutput") -> "RunOutput":
        current = output
        for hook in self.hooks:
            try:
                result = await hook.on_run_end(ctx, current)
                if result is not None:
                    current = result
            except Exception as e:
                logger.warning(f"Hook {hook.__class__.__name__}.on_run_end failed: {e}")
        return current

    async def on_error(self, ctx: HookContext, error: Exception) -> None:
        for hook in self.hooks:
            try:
                await hook.on_error(ctx, error)
            except Exception as e:
                logger.warning(f"Hook {hook.__class__.__name__}.on_error failed: {e}")

    async def _safe_call(self, method: Callable[..., Awaitable], *args) -> None:
        try:
            await method(*args)
        except Exception as e:
            logger.warning(f"Hook {method.__qualname__} failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# Updated AgentExecutor
# ═══════════════════════════════════════════════════════════════════════════


class AgentExecutor:
    """Executes LLM agent loop with hooks support."""

    def __init__(
        self,
        model: "Model",
        tools: list["BaseTool"],
        hooks: list[AgentHook] | None = None,
        session_store: "SessionStore | None" = None,
        sequence_manager: "SequenceManager | None" = None,
        config: "ExecutionConfig | None" = None,
        permission_manager: "PermissionManager | None" = None,
    ):
        self.model = model
        self.tools = tools
        self.session_store = session_store
        self.sequence_manager = sequence_manager
        self.config = config or ExecutionConfig()
        self.tool_executor = ToolExecutor(tools, permission_manager=permission_manager)
        self.hook_manager = HookManager(hooks)
        self._tool_schemas = [t.to_openai_schema() for t in tools] if tools else None

    async def execute(
        self,
        messages: list[dict],
        context: "ExecutionContext",
        *,
        pending_tool_calls: list[dict] | None = None,
        abort_signal: "AbortSignal | None" = None,
    ) -> "RunOutput":
        state = RunState.create(context, self.config, messages, self.session_store)
        hook_ctx = self._create_hook_context(context, messages)

        # [HOOK] Run Start
        await self.hook_manager.on_run_start(hook_ctx)

        try:
            await self._run_loop(state, hook_ctx, pending_tool_calls, abort_signal)
        except asyncio.CancelledError:
            state.termination_reason = "cancelled"
        except Exception as e:
            await self.hook_manager.on_error(hook_ctx, e)
            state.termination_reason = (
                "error_with_context" if state.tracker.assistant_steps_count > 0 else "error"
            )
        finally:
            await state.cleanup()

        output = state.build_output()

        # [HOOK] Run End
        return await self.hook_manager.on_run_end(hook_ctx, output)

    def _create_hook_context(
        self, context: "ExecutionContext", messages: list[dict]
    ) -> HookContext:
        return HookContext(
            run_id=context.run_id,
            session_id=context.session_id,
            messages=messages,
            model=self.model,
            tools=self.tools,
            config=self.config,
            _tool_schemas=self._tool_schemas or [],
        )

    async def _run_loop(
        self,
        state: RunState,
        hook_ctx: HookContext,
        pending_tool_calls: list[dict] | None,
        abort_signal: "AbortSignal | None",
    ) -> None:
        if pending_tool_calls:
            await self._execute_tools(state, hook_ctx, pending_tool_calls, abort_signal)

        while True:
            self._check_abort(abort_signal)

            if reason := state.check_limits():
                state.termination_reason = reason
                break

            state.current_step += 1
            hook_ctx.iteration = state.current_step

            step = await self._stream_assistant_step(state, hook_ctx, abort_signal)

            if not step.tool_calls:
                return

            await self._execute_tools(state, hook_ctx, step.tool_calls, abort_signal)

        await self._maybe_generate_summary(state, hook_ctx, abort_signal)

    async def _stream_assistant_step(
        self,
        state: RunState,
        hook_ctx: HookContext,
        abort_signal: "AbortSignal | None",
        *,
        messages_override: list[dict] | None = None,
        use_tools: bool = True,
        append_message: bool = True,
    ) -> "Step":
        # Prepare LLM request (copy for potential modification)
        base_messages = messages_override or state.messages
        request = LLMRequest(
            messages=copy.deepcopy(base_messages),
            tools=copy.deepcopy(hook_ctx.get_active_tool_schemas()) if use_tools else None,
        )

        # [HOOK] LLM Start
        await self.hook_manager.on_llm_start(hook_ctx, request)

        # Build and stream step
        builder = await self._create_step_builder(state, request.messages, request.tools)

        async for chunk in self.model.arun_stream(request.messages, tools=request.tools):
            self._check_abort(abort_signal)
            await builder.process_chunk(chunk)

        step = builder.finalize()

        # Record step
        await state.record_step(step, append_message=append_message)
        hook_ctx.steps.append(step)
        hook_ctx.tracker = state.tracker

        # [HOOK] LLM End
        await self.hook_manager.on_llm_end(hook_ctx, step)

        return step

    async def _execute_tools(
        self,
        state: RunState,
        hook_ctx: HookContext,
        tool_calls: list[dict],
        abort_signal: "AbortSignal | None",
    ) -> None:
        for call_dict in tool_calls:
            tool_call = ToolCallInfo(
                id=call_dict["id"],
                name=call_dict["function"]["name"],
                arguments=call_dict["function"].get("arguments", {}),
            )

            # [HOOK] Tool Start
            await self.hook_manager.on_tool_start(hook_ctx, tool_call)

            # Execute
            result = await self.tool_executor.execute_single(
                {
                    "id": tool_call.id,
                    "function": {"name": tool_call.name, "arguments": tool_call.arguments},
                },
                context=state.context,
                abort_signal=abort_signal,
            )

            result_info = ToolResultInfo(
                tool_call_id=result.tool_call_id,
                tool_name=result.tool_name,
                content=result.content,
                success=result.success,
                duration=result.duration,
                error=result.error,
            )

            # [HOOK] Tool End
            await self.hook_manager.on_tool_end(hook_ctx, tool_call, result_info)

            # Record step
            seq = await self._allocate_sequence(state.context)
            step = state.sf.tool_step(
                sequence=seq,
                tool_call_id=result.tool_call_id,
                name=result.tool_name,
                content=result.content,
                metrics=StepMetrics(
                    duration_ms=result.duration * 1000 if result.duration else None,
                    exec_start_at=datetime.fromtimestamp(result.start_time, tz=timezone.utc),
                    exec_end_at=datetime.fromtimestamp(result.end_time, tz=timezone.utc),
                ),
            )
            await state.record_step(step)
            hook_ctx.steps.append(step)

    # ... rest of the methods remain the same
```

---

## 实战用例

### 用例 1: 动态 System Prompt（基于工具结果）

```python
class DynamicSystemPromptHook(AgentHook):
    """根据搜索结果动态调整 System Prompt"""
    
    async def on_llm_start(self, ctx: HookContext, request: LLMRequest) -> None:
        # 检查是否有搜索结果
        search_results = ctx.get_tool_results("web_search")
        
        if search_results:
            # 持久化修改：更新 ctx.messages 中的 system prompt
            ctx.append_to_system_prompt(
                f"## 搜索上下文\n根据最新搜索，用户关注的话题涉及：{search_results[-1][:200]}..."
            )
```

### 用例 2: 临时上下文注入

```python
class ContextInjectionHook(AgentHook):
    """在每次 LLM 调用前注入实时上下文"""
    
    def __init__(self, context_provider: Callable[[], Awaitable[str]]):
        self.context_provider = context_provider
    
    async def on_llm_start(self, ctx: HookContext, request: LLMRequest) -> None:
        # 获取实时上下文
        realtime_context = await self.context_provider()
        
        # 临时注入（只影响本次调用，不污染 ctx.messages）
        request.inject_system_context(
            f"## 实时信息\n当前时间：{datetime.now()}\n{realtime_context}"
        )
```

### 用例 3: Memory 持久化

```python
class MemoryPersistenceHook(AgentHook):
    """将执行结果保存到 Memory"""
    
    def __init__(self, memory_store: "MemoryStore"):
        self.memory_store = memory_store
    
    async def on_run_start(self, ctx: HookContext) -> None:
        # 加载历史上下文
        history = await self.memory_store.load(ctx.session_id)
        if history:
            ctx.append_to_system_prompt(f"## 历史上下文\n{history}")
    
    async def on_run_end(self, ctx: HookContext, output: RunOutput) -> RunOutput:
        # 保存本次执行摘要
        summary = self._build_summary(ctx)
        await self.memory_store.save(
            session_id=ctx.session_id,
            run_id=ctx.run_id,
            summary=summary,
            steps=ctx.steps,
            output=output,
        )
        return output
    
    def _build_summary(self, ctx: HookContext) -> str:
        tool_names = [s.name for s in ctx.get_tool_steps()]
        return f"Used tools: {tool_names}, Tokens: {ctx.total_tokens}"
```

### 用例 4: 动态工具控制

```python
class AdaptiveToolHook(AgentHook):
    """根据执行进度动态禁用/启用工具"""
    
    async def on_llm_start(self, ctx: HookContext, request: LLMRequest) -> None:
        # 迭代次数过多时禁用昂贵工具
        if ctx.iteration > 3:
            ctx.disable_tool("expensive_api_call")
        
        # Token 接近限制时只保留必要工具
        if ctx.total_tokens > ctx.config.max_total_tokens * 0.8:
            ctx.disable_tool("web_search")
            ctx.disable_tool("code_execution")
```

### 用例 5: 工具参数增强

```python
class ToolEnhancementHook(AgentHook):
    """增强工具调用参数"""
    
    async def on_tool_start(self, ctx: HookContext, tool_call: ToolCallInfo) -> None:
        if tool_call.name == "database_query":
            # 自动注入用户权限范围
            tool_call.update_argument("allowed_tables", ["public_data", "user_reports"])
            tool_call.update_argument("user_id", ctx.store.get("current_user_id"))
```

---

## 设计总结

| 特性 | 实现方式 |
|------|---------|
| **持久修改** | 直接修改 `ctx.messages` |
| **临时注入** | 修改 `request.messages`（副本） |
| **工具控制** | `ctx.disable_tool()` / `ctx.enable_tool()` |
| **Hook 间通信** | `ctx.store` 共享字典 |
| **便捷操作** | `ctx.set_system_prompt()`, `request.inject_message()` 等 |
| **错误隔离** | `HookManager._safe_call()` 包装 |