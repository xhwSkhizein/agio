# HITL (Human-in-the-Loop) 和权限系统设计方案

## 概述

本文档设计了一套低侵入性的 HITL 和权限系统，使 Agent 能够在执行过程中与用户交互，并在工具执行前进行权限检查。

## 设计原则

1. **低侵入性**：最小化对现有架构的修改
2. **可配置性**：通过配置系统灵活控制 HITL 和权限行为
3. **持久化**：HITL 状态可持久化，支持恢复和重试
4. **可扩展性**：支持多种交互模式和权限规则

---

## 1. HITL 与用户交互的数据模型

### 1.1 核心数据模型

#### InteractionRequest（交互请求）

```python
# agio/domain/interaction.py

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class InteractionType(str, Enum):
    """交互类型"""
    INPUT = "input"           # 文本输入（问答模式）
    SELECT = "select"         # 单选/多选
    CONFIRM = "confirm"       # 确认/授权
    COMBINED = "combined"     # 组合模式（多个交互组合）

class SelectOption(BaseModel):
    """选择项"""
    value: str
    label: str
    description: Optional[str] = None

class InteractionRequest(BaseModel):
    """用户交互请求"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: InteractionType
    title: str
    description: Optional[str] = None
    
    # 对于 INPUT 类型
    placeholder: Optional[str] = None
    required: bool = True
    multiline: bool = False
    
    # 对于 SELECT 类型
    options: Optional[list[SelectOption]] = None
    multiple: bool = False  # 是否多选
    
    # 对于 CONFIRM 类型
    confirm_text: Optional[str] = None  # 确认按钮文本
    cancel_text: Optional[str] = None   # 取消按钮文本
    
    # 对于 COMBINED 类型
    interactions: Optional[list["InteractionRequest"]] = None
    
    # 上下文信息
    run_id: str
    step_id: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    
    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None  # 过期时间
```

#### InteractionResponse（交互响应）

```python
class InteractionResponse(BaseModel):
    """用户交互响应"""
    request_id: str
    type: InteractionType
    
    # 对于 INPUT 类型
    text: Optional[str] = None
    
    # 对于 SELECT 类型
    selected_values: Optional[list[str]] = None
    
    # 对于 CONFIRM 类型
    confirmed: Optional[bool] = None
    
    # 对于 COMBINED 类型
    responses: Optional[list["InteractionResponse"]] = None
    
    # 元数据
    responded_at: datetime = Field(default_factory=datetime.now)
    user_id: Optional[str] = None
```

### 1.2 前端组件设计

#### React 组件结构

```typescript
// agio-frontend/src/components/interaction/

// InteractionRequest.tsx - 主组件
interface InteractionRequestProps {
  request: InteractionRequest;
  onResponse: (response: InteractionResponse) => void;
}

// InputInteraction.tsx - 文本输入组件
interface InputInteractionProps {
  request: InteractionRequest;
  onResponse: (text: string) => void;
}

// SelectInteraction.tsx - 选择组件
interface SelectInteractionProps {
  request: InteractionRequest;
  onResponse: (values: string[]) => void;
}

// ConfirmInteraction.tsx - 确认组件
interface ConfirmInteractionProps {
  request: InteractionRequest;
  onResponse: (confirmed: boolean) => void;
}

// CombinedInteraction.tsx - 组合组件
interface CombinedInteractionProps {
  request: InteractionRequest;
  onResponse: (responses: InteractionResponse[]) => void;
}
```

#### 组件渲染逻辑

```typescript
function InteractionRequest({ request, onResponse }: InteractionRequestProps) {
  switch (request.type) {
    case 'input':
      return <InputInteraction request={request} onResponse={onResponse} />;
    case 'select':
      return <SelectInteraction request={request} onResponse={onResponse} />;
    case 'confirm':
      return <ConfirmInteraction request={request} onResponse={onResponse} />;
    case 'combined':
      return <CombinedInteraction request={request} onResponse={onResponse} />;
    default:
      return <div>Unknown interaction type</div>;
  }
}
```

### 1.3 前端集成到 Chat 界面

在 Chat 组件中，当收到 `INTERACTION_REQUEST` 事件时，显示交互组件：

```typescript
// agio-frontend/src/pages/Chat.tsx

// 在 useSSEStream hook 中处理
onEvent: (event: StepEvent) => {
  if (event.type === 'interaction_request') {
    // 显示交互组件
    setPendingInteraction(event.data.interaction_request);
  }
}

// 渲染交互组件
{pendingInteraction && (
  <InteractionRequest
    request={pendingInteraction}
    onResponse={async (response) => {
      await submitInteractionResponse(response);
      setPendingInteraction(null);
    }}
  />
)}
```

---

## 2. HITL 和权限系统接入架构

### 2.1 执行暂停机制

#### SuspendExecution 异常

```python
# agio/runtime/exceptions.py

class SuspendExecution(Exception):
    """执行暂停异常，用于 HITL 交互"""
    def __init__(self, interaction_request: InteractionRequest):
        self.interaction_request = interaction_request
        super().__init__(f"Execution suspended for interaction: {interaction_request.id}")
```

### 2.2 权限系统

#### PermissionManager（权限管理器）

```python
# agio/runtime/permissions.py

from enum import Enum
from typing import Optional
from agio.providers.tools import BaseTool
from agio.domain import ExecutionContext
from agio.domain.interaction import InteractionRequest, InteractionType

class PermissionDecision(str, Enum):
    """权限决策"""
    ALLOWED = "allowed"      # 已授权，直接执行
    DENIED = "denied"        # 明确拒绝
    NEEDS_AUTH = "needs_auth"  # 需要用户授权

class PermissionManager:
    """权限管理器"""
    
    def __init__(self, store: Optional["PermissionStore"] = None):
        self.store = store or get_permission_store()
    
    async def check_permission(
        self,
        tool: BaseTool,
        args: dict,
        context: ExecutionContext,
    ) -> PermissionDecision:
        """
        检查工具执行权限
        
        Returns:
            PermissionDecision: 权限决策
        """
        # 1. 生成权限资源标识符
        resource = self._generate_resource(tool, args)
        
        # 2. 查询历史授权记录
        if context.user_id:
            decision = await self.store.check_permission(
                user_id=context.user_id,
                resource=resource,
            )
            if decision != PermissionDecision.NEEDS_AUTH:
                return decision
        
        # 3. 检查工具配置的默认权限策略
        default_policy = getattr(tool, 'default_permission_policy', None)
        if default_policy == 'allow':
            return PermissionDecision.ALLOWED
        elif default_policy == 'deny':
            return PermissionDecision.DENIED
        
        # 4. 需要用户授权
        return PermissionDecision.NEEDS_AUTH
    
    def _generate_resource(self, tool: BaseTool, args: dict) -> str:
        """
        生成权限资源标识符
        
        格式: tool_name(arg_pattern)
        例如: bash(npm run lint), file_read(~/.zshrc)
        """
        tool_name = tool.get_name()
        arg_pattern = tool.get_permission_resource(args) if hasattr(tool, 'get_permission_resource') else str(args)
        return f"{tool_name}({arg_pattern})"
    
    async def create_auth_request(
        self,
        tool: BaseTool,
        args: dict,
        context: ExecutionContext,
    ) -> InteractionRequest:
        """创建授权请求"""
        resource = self._generate_resource(tool, args)
        desc = f"Execute {tool.get_name()}"
        if resource:
            desc += f" on {resource}"
        
        return InteractionRequest(
            type=InteractionType.CONFIRM,
            title="Authorization Required",
            description=f"Do you want to allow: {desc}?",
            tool_call_id=context.metadata.get("tool_call_id"),
            run_id=context.run_id,
            tool_name=tool.get_name(),
            metadata={
                "resource": resource,
                "tool_args": args,
            },
        )
```

#### PermissionStore（权限存储）

```python
# agio/providers/storage/permissions.py

from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from agio.runtime.permissions import PermissionDecision

class PermissionStore:
    """权限存储（MongoDB）"""
    
    def __init__(self, mongo_uri: str, db_name: str = "agio"):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db["permissions"]
    
    async def initialize(self):
        """初始化索引"""
        await self.collection.create_index("user_id")
        await self.collection.create_index([("user_id", 1), ("resource", 1)], unique=True)
    
    async def check_permission(
        self,
        user_id: str,
        resource: str,
    ) -> PermissionDecision:
        """
        检查权限
        
        支持通配符匹配：
        - bash(npm run test:*) 匹配 bash(npm run test:unit)
        - file_read(./secrets/**) 匹配 file_read(./secrets/api.key)
        """
        # 查询用户权限记录
        doc = await self.collection.find_one({"user_id": user_id})
        if not doc:
            return PermissionDecision.NEEDS_AUTH
        
        allow_patterns = doc.get("allow", [])
        deny_patterns = doc.get("deny", [])
        
        # 先检查 deny（优先级更高）
        for pattern in deny_patterns:
            if self._match_pattern(resource, pattern):
                return PermissionDecision.DENIED
        
        # 再检查 allow
        for pattern in allow_patterns:
            if self._match_pattern(resource, pattern):
                return PermissionDecision.ALLOWED
        
        return PermissionDecision.NEEDS_AUTH
    
    def _match_pattern(self, resource: str, pattern: str) -> bool:
        """
        模式匹配
        
        支持：
        - 精确匹配: bash(npm run lint)
        - 通配符: bash(npm run test:*)
        - 路径通配符: file_read(./secrets/**)
        """
        import fnmatch
        import re
        
        # 提取工具名和参数部分
        tool_match = re.match(r'^(\w+)\((.*)\)$', resource)
        pattern_match = re.match(r'^(\w+)\((.*)\)$', pattern)
        
        if not tool_match or not pattern_match:
            return resource == pattern
        
        tool_name, tool_args = tool_match.groups()
        pattern_tool, pattern_args = pattern_match.groups()
        
        # 工具名必须匹配
        if tool_name != pattern_tool:
            return False
        
        # 参数匹配（支持通配符）
        return fnmatch.fnmatch(tool_args, pattern_args)
    
    async def save_permission(
        self,
        user_id: str,
        resource: str,
        allowed: bool,
    ):
        """保存权限记录"""
        await self.collection.update_one(
            {"user_id": user_id},
            {
                "$addToSet": {
                    "allow" if allowed else "deny": resource,
                },
                "$pull": {
                    "deny" if allowed else "allow": resource,
                },
            },
            upsert=True,
        )
```

### 2.3 ToolExecutor 集成

在 `ToolExecutor.execute` 中集成权限检查：

```python
# agio/runtime/tool_executor.py (修改)

async def execute(
    self,
    tool_call: dict[str, Any],
    context: "ExecutionContext",
    abort_signal: "AbortSignal | None" = None,
) -> ToolResult:
    # ... 前面的代码 ...
    
    # 权限检查
    from agio.runtime.permissions import get_permission_manager, PermissionDecision
    from agio.runtime.exceptions import SuspendExecution
    
    pm = get_permission_manager()
    decision = await pm.check_permission(tool, args, context)
    
    if decision == PermissionDecision.DENIED:
        return self._create_error_result(
            call_id=call_id,
            tool_name=fn_name,
            error=f"Permission denied for tool {fn_name}",
            start_time=start_time,
        )
    elif decision == PermissionDecision.NEEDS_AUTH:
        # 创建授权请求并暂停执行
        request = await pm.create_auth_request(tool, args, context)
        raise SuspendExecution(request)
    
    # 继续执行工具
    # ... 后面的代码 ...
```

### 2.4 SessionStore 扩展

需要扩展 `SessionStore` 接口以支持暂停状态存储：

```python
# agio/providers/storage/base.py (扩展)

class SuspendedState(BaseModel):
    """执行暂停状态"""
    run_id: str
    interaction_request: InteractionRequest
    tool_call: dict  # 暂停时的工具调用
    context: dict  # ExecutionContext 的序列化版本
    agent_id: str
    suspended_at: datetime = Field(default_factory=datetime.now)

class SessionStore(ABC):
    # ... 现有方法 ...
    
    @abstractmethod
    async def save_suspended_state(self, state: SuspendedState) -> None:
        """保存暂停状态"""
        ...
    
    @abstractmethod
    async def get_suspended_state(self, run_id: str) -> SuspendedState | None:
        """获取暂停状态"""
        ...
    
    @abstractmethod
    async def get_suspended_state_by_interaction(
        self, 
        interaction_id: str
    ) -> SuspendedState | None:
        """通过交互 ID 获取暂停状态"""
        ...
    
    @abstractmethod
    async def save_interaction_response(
        self, 
        response: InteractionResponse
    ) -> None:
        """保存交互响应"""
        ...
```

MongoDB 实现：

```python
# agio/providers/storage/mongo.py (扩展)

class MongoSessionStore(SessionStore):
    # ... 现有代码 ...
    
    async def _ensure_connection(self):
        # ... 现有代码 ...
        self.suspended_states_collection = self.db["suspended_states"]
        self.interaction_responses_collection = self.db["interaction_responses"]
        
        # 创建索引
        await self.suspended_states_collection.create_index("run_id", unique=True)
        await self.suspended_states_collection.create_index("interaction_request.id")
        await self.interaction_responses_collection.create_index("request_id")
    
    async def save_suspended_state(self, state: SuspendedState) -> None:
        """保存暂停状态"""
        await self._ensure_connection()
        doc = state.model_dump(mode="json")
        await self.suspended_states_collection.replace_one(
            {"run_id": state.run_id},
            doc,
            upsert=True,
        )
    
    async def get_suspended_state(self, run_id: str) -> SuspendedState | None:
        """获取暂停状态"""
        await self._ensure_connection()
        doc = await self.suspended_states_collection.find_one({"run_id": run_id})
        if doc:
            return SuspendedState(**doc)
        return None
    
    async def get_suspended_state_by_interaction(
        self, 
        interaction_id: str
    ) -> SuspendedState | None:
        """通过交互 ID 获取暂停状态"""
        await self._ensure_connection()
        doc = await self.suspended_states_collection.find_one(
            {"interaction_request.id": interaction_id}
        )
        if doc:
            return SuspendedState(**doc)
        return None
    
    async def save_interaction_response(
        self, 
        response: InteractionResponse
    ) -> None:
        """保存交互响应"""
        await self._ensure_connection()
        doc = response.model_dump(mode="json")
        await self.interaction_responses_collection.insert_one(doc)
```

### 2.5 StepRunner 处理暂停

在 `StepRunner.run` 中处理 `SuspendExecution`：

```python
# agio/runtime/runner.py (修改)

async def run(
    self,
    session: AgentSession,
    query: str,
    wire: Wire,
    abort_signal: AbortSignal | None = None,
    context: "RunContext | None" = None,
) -> "RunOutput":
    # ... 前面的代码 ...
    
    try:
        async for event in executor.execute(...):
            await wire.write(event)
            # ... 处理事件 ...
    except SuspendExecution as e:
        # 保存暂停状态
        interaction_request = e.interaction_request
        
        # 发送交互请求事件
        await wire.write(
            ef.interaction_request(interaction_request)
        )
        
        # 保存暂停状态到存储
        if self.session_store:
            from agio.providers.storage.base import SuspendedState
            
            # 需要保存当前的工具调用和上下文信息
            # 这些信息应该在 ToolExecutor 中捕获并传递
            suspended_state = SuspendedState(
                run_id=run.id,
                interaction_request=interaction_request,
                tool_call=e.tool_call,  # 从异常中获取
                context=e.context.model_dump() if e.context else {},
                agent_id=self.agent.id,
            )
            await self.session_store.save_suspended_state(suspended_state)
        
        # 更新 Run 状态为 SUSPENDED
        run.status = RunStatus.SUSPENDED
        if self.session_store:
            await self.session_store.save_run(run)
        
        # 返回暂停状态
        return RunOutput(
            run_id=run.id,
            session_id=session.session_id,
            response=None,
            status="suspended",
            interaction_request_id=interaction_request.id,
        )
```

注意：`SuspendExecution` 异常需要携带更多上下文信息：

```python
# agio/runtime/exceptions.py (修改)

class SuspendExecution(Exception):
    """执行暂停异常，用于 HITL 交互"""
    def __init__(
        self, 
        interaction_request: InteractionRequest,
        tool_call: dict,
        context: ExecutionContext,
    ):
        self.interaction_request = interaction_request
        self.tool_call = tool_call
        self.context = context
        super().__init__(f"Execution suspended for interaction: {interaction_request.id}")
```

### 2.6 恢复执行

提供恢复执行的方法：

```python
# agio/runtime/runner.py (新增方法)

async def resume_from_interaction(
    self,
    run_id: str,
    interaction_response: InteractionResponse,
    wire: Wire,
) -> "RunOutput":
    """
    从交互响应恢复执行
    
    流程：
    1. 加载暂停状态
    2. 处理交互响应（保存权限记录等）
    3. 恢复工具执行
    4. 继续后续执行流程
    """
    from agio.domain import RunStatus
    from agio.domain.protocol import RunOutput, RunMetrics
    from agio.domain import ExecutionContext
    from agio.domain.interaction import InteractionType
    
    # 1. 加载暂停状态
    suspended_state = await self.session_store.get_suspended_state(run_id)
    if not suspended_state:
        raise ValueError(f"No suspended state found for run {run_id}")
    
    interaction_request = suspended_state.interaction_request
    
    # 验证响应匹配请求
    if interaction_response.request_id != interaction_request.id:
        raise ValueError("Interaction response does not match request")
    
    # 2. 处理交互响应
    if interaction_request.type == InteractionType.CONFIRM:
        # 保存权限记录
        if interaction_response.confirmed:
            resource = interaction_request.metadata.get("resource")
            user_id = suspended_state.context.get("user_id")
            if resource and user_id:
                from agio.runtime.permissions import get_permission_manager
                pm = get_permission_manager()
                await pm.store.save_permission(
                    user_id=user_id,
                    resource=resource,
                    allowed=True,
                )
        
        # 如果用户拒绝，返回错误
        if not interaction_response.confirmed:
            run = await self.session_store.get_run(run_id)
            if run:
                run.status = RunStatus.FAILED
                await self.session_store.save_run(run)
            
            await wire.write(
                ef.run_failed(error="Permission denied by user")
            )
            return RunOutput(
                run_id=run_id,
                error="Permission denied by user",
            )
    
    # 3. 恢复执行上下文
    # 重建 ExecutionContext（从序列化的状态恢复）
    context_dict = suspended_state.context
    exec_ctx = ExecutionContext(
        run_id=context_dict.get("run_id", run_id),
        session_id=context_dict.get("session_id"),
        wire=wire,
        user_id=context_dict.get("user_id"),
        depth=context_dict.get("depth", 0),
        parent_run_id=context_dict.get("parent_run_id"),
        nested_runnable_id=context_dict.get("nested_runnable_id"),
    )
    
    # 4. 恢复工具执行
    tool_call = suspended_state.tool_call
    
    # 重新执行工具（这次应该通过权限检查，因为已经保存了权限记录）
    result = await self.tool_executor.execute(
        tool_call,
        context=exec_ctx,
    )
    
    # 5. 创建工具结果 Step
    from agio.domain.models import Step, MessageRole, StepMetrics
    tool_step = Step(
        id=str(uuid4()),
        session_id=exec_ctx.session_id,
        run_id=exec_ctx.run_id,
        sequence=await self._get_next_sequence(exec_ctx.session_id),
        role=MessageRole.TOOL,
        content=result.content,
        tool_call_id=result.tool_call_id,
        name=result.tool_name,
        metrics=StepMetrics(
            duration_ms=result.duration * 1000 if result.duration else None,
        ),
    )
    
    if self.session_store:
        await self.session_store.save_step(tool_step)
    
    await wire.write(ef.step_completed(tool_step.id, tool_step))
    
    # 6. 继续后续执行流程（调用 StepExecutor 继续执行）
    # 需要重新构建 messages 上下文
    messages = await build_context_from_steps(
        exec_ctx.session_id,
        self.session_store,
        system_prompt=self.agent.system_prompt,
    )
    
    # 添加工具结果到 messages
    messages.append(StepAdapter.to_llm_message(tool_step))
    
    # 继续执行
    executor = StepExecutor(
        model=self.agent.model,
        tools=self.agent.tools or [],
        config=self.config,
    )
    
    start_sequence = tool_step.sequence + 1
    
    # 继续执行循环
    async for event in executor.execute(
        messages=messages,
        ctx=exec_ctx,
        start_sequence=start_sequence,
    ):
        await wire.write(event)
        if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
            if self.session_store:
                await self.session_store.save_step(event.snapshot)
    
    # 7. 完成执行
    run = await self.session_store.get_run(run_id)
    if run:
        run.status = RunStatus.COMPLETED
        await self.session_store.save_run(run)
    
    await wire.write(
        ef.run_completed(
            response="Execution resumed and completed",
            metrics={},
        )
    )
    
    return RunOutput(
        run_id=run_id,
        session_id=exec_ctx.session_id,
        response="Execution resumed and completed",
    )
```

---

## 3. StepEvent 和 Wire 支持

### 3.1 新增事件类型

```python
# agio/domain/events.py (修改)

class StepEventType(str, Enum):
    # ... 现有事件 ...
    
    # HITL 事件
    INTERACTION_REQUEST = "interaction_request"  # 交互请求
    INTERACTION_RESPONSE = "interaction_response"  # 交互响应（用于日志）
    EXECUTION_SUSPENDED = "execution_suspended"  # 执行暂停
    EXECUTION_RESUMED = "execution_resumed"  # 执行恢复
```

### 3.2 EventFactory 扩展

```python
# agio/runtime/event_factory.py (修改)

class EventFactory:
    # ... 现有方法 ...
    
    def interaction_request(
        self,
        request: InteractionRequest,
    ) -> StepEvent:
        """创建交互请求事件"""
        return StepEvent(
            type=StepEventType.INTERACTION_REQUEST,
            run_id=self.ctx.run_id,
            data={
                "interaction_request": request.model_dump(mode="json"),
            },
            step_id=request.step_id,
        )
    
    def execution_suspended(
        self,
        interaction_request_id: str,
    ) -> StepEvent:
        """创建执行暂停事件"""
        return StepEvent(
            type=StepEventType.EXECUTION_SUSPENDED,
            run_id=self.ctx.run_id,
            data={
                "interaction_request_id": interaction_request_id,
            },
        )
```

### 3.3 Wire 支持

Wire 本身不需要修改，因为它已经支持任意 `StepEvent` 的写入和读取。

### 3.4 对现有系统的影响

1. **事件流**：新增事件类型不影响现有事件流处理
2. **前端适配**：前端需要处理新的事件类型并渲染交互组件
3. **存储**：需要存储暂停状态，支持恢复

---

## 4. 权限系统存储设计

### 4.1 MongoDB 集合结构

```javascript
// permissions 集合
{
  "_id": ObjectId("..."),
  "user_id": "user-123",
  "allow": [
    "bash(npm run lint)",
    "bash(npm run test:*)",
    "file_read(~/.zshrc)"
  ],
  "deny": [
    "bash(curl:*)",
    "file_read(./.env)",
    "file_read(./.env.*)",
    "file_read(./secrets/**)"
  ],
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}
```

### 4.2 权限匹配逻辑

支持以下模式：
- **精确匹配**：`bash(npm run lint)` 只匹配完全相同的调用
- **通配符**：`bash(npm run test:*)` 匹配 `bash(npm run test:unit)`、`bash(npm run test:integration)` 等
- **路径通配符**：`file_read(./secrets/**)` 匹配所有 `./secrets/` 下的文件

### 4.3 权限优先级

1. **DENY 优先**：如果匹配到 deny 规则，直接拒绝
2. **ALLOW 次之**：如果匹配到 allow 规则，允许执行
3. **默认需要授权**：如果没有匹配到任何规则，需要用户授权

---

## 5. 配置系统集成

### 5.1 ExecutionConfig 扩展

```python
# agio/config/schema.py (修改)

class ExecutionConfig(BaseModel):
    # ... 现有配置 ...
    
    # HITL 配置
    enable_hitl: bool = Field(default=True, description="启用 HITL")
    hitl_timeout: float = Field(default=3600.0, description="HITL 交互超时（秒）")
    
    # 权限配置
    enable_permissions: bool = Field(default=True, description="启用权限系统")
    permission_store_uri: str | None = Field(default=None, description="权限存储 URI")
```

### 5.2 Tool 配置扩展

```python
# agio/providers/tools/base.py (修改)

class BaseTool(ABC):
    # ... 现有属性 ...
    
    # 权限相关
    default_permission_policy: str | None = None  # "allow" | "deny" | None (需要授权)
    
    def get_permission_resource(self, args: dict) -> str:
        """
        生成权限资源标识符
        
        子类可以重写此方法来自定义资源标识符生成逻辑
        """
        # 默认实现：使用参数的关键部分
        # 例如：对于 file_read，返回文件路径
        return str(args)
```

### 5.3 配置示例

```yaml
# configs/agents/my_agent.yaml
type: agent
name: my_agent
model: gpt4_model
tools:
  - file_read
  - bash
system_prompt: "You are helpful."
enable_hitl: true
enable_permissions: true
```

---

## 6. API 端点设计

### 6.1 提交交互响应

```python
# agio/api/routes/interactions.py (新建)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from agio.domain.interaction import InteractionResponse
from agio.config import ConfigSystem, get_config_system
from agio.providers.storage.base import SessionStore, get_session_store
from agio.runtime import Wire
from agio.domain import ExecutionContext
from uuid import uuid4

router = APIRouter(prefix="/interactions")

@router.post("/{interaction_id}/respond")
async def respond_to_interaction(
    interaction_id: str,
    response: InteractionResponse,
    config_system: ConfigSystem = Depends(get_config_system),
    session_store: SessionStore = Depends(get_session_store),
):
    """
    提交交互响应并恢复执行
    
    流程：
    1. 验证交互请求（检查是否存在且未过期）
    2. 保存响应
    3. 恢复执行（通过 SSE 流返回结果）
    """
    # 1. 加载暂停状态
    suspended_state = await session_store.get_suspended_state_by_interaction(interaction_id)
    if not suspended_state:
        raise HTTPException(404, f"Interaction {interaction_id} not found or expired")
    
    # 2. 验证响应匹配请求
    if response.request_id != interaction_id:
        raise HTTPException(400, "Response request_id does not match interaction_id")
    
    # 3. 保存响应
    await session_store.save_interaction_response(response)
    
    # 4. 恢复执行
    async def event_generator():
        wire = Wire()
        
        async def _resume():
            from agio.runtime import StepRunner
            from agio.config import ExecutionConfig
            
            # 获取 Agent
            agent = config_system.get_instance(suspended_state.agent_id)
            
            runner = StepRunner(
                agent=agent,
                config=ExecutionConfig(),
                session_store=session_store,
            )
            
            try:
                await runner.resume_from_interaction(
                    run_id=suspended_state.run_id,
                    interaction_response=response,
                    wire=wire,
                )
            finally:
                await wire.close()
        
        task = asyncio.create_task(_resume())
        
        try:
            async for event in wire.read():
                yield {
                    "event": event.type.value,
                    "data": event.model_dump_json(),
                }
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    
    return EventSourceResponse(
        event_generator(),
        headers={
            "Connection": "close",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/{interaction_id}")
async def get_interaction_request(
    interaction_id: str,
    session_store: SessionStore = Depends(get_session_store),
):
    """获取交互请求详情"""
    state = await session_store.get_suspended_state_by_interaction(interaction_id)
    if not state:
        raise HTTPException(404, f"Interaction {interaction_id} not found")
    return {
        "interaction_request": state.interaction_request.model_dump(mode="json"),
        "run_id": state.run_id,
        "suspended_at": state.suspended_at.isoformat(),
    }
```

### 6.2 查询暂停状态

```python
# agio/api/routes/runnables.py (扩展)

@router.get("/runs/{run_id}/suspended")
async def get_suspended_state(
    run_id: str,
    session_store: SessionStore = Depends(get_session_store),
):
    """查询运行暂停状态"""
    state = await session_store.get_suspended_state(run_id)
    if not state:
        raise HTTPException(404, "No suspended state found")
    return {
        "interaction_request": state.interaction_request.model_dump(mode="json"),
        "suspended_at": state.suspended_at.isoformat(),
    }
```

### 6.3 权限管理 API

```python
# agio/api/routes/permissions.py (新建)

router = APIRouter(prefix="/permissions")

@router.get("/{user_id}")
async def get_user_permissions(
    user_id: str,
    permission_store: PermissionStore = Depends(get_permission_store),
):
    """获取用户权限配置"""
    doc = await permission_store.collection.find_one({"user_id": user_id})
    if not doc:
        return {"allow": [], "deny": []}
    return {
        "allow": doc.get("allow", []),
        "deny": doc.get("deny", []),
    }

@router.post("/{user_id}/allow")
async def add_permission(
    user_id: str,
    resource: str,
    permission_store: PermissionStore = Depends(get_permission_store),
):
    """添加允许权限"""
    await permission_store.save_permission(user_id, resource, allowed=True)
    return {"status": "ok"}

@router.post("/{user_id}/deny")
async def deny_permission(
    user_id: str,
    resource: str,
    permission_store: PermissionStore = Depends(get_permission_store),
):
    """添加拒绝权限"""
    await permission_store.save_permission(user_id, resource, allowed=False)
    return {"status": "ok"}
```

---

## 7. 前端实现细节

### 7.1 交互组件实现

#### InputInteraction 组件

```typescript
// agio-frontend/src/components/interaction/InputInteraction.tsx

import React, { useState } from 'react';
import { InteractionRequest, InteractionResponse } from '@/types/interaction';

interface InputInteractionProps {
  request: InteractionRequest;
  onResponse: (response: InteractionResponse) => void;
}

export function InputInteraction({ request, onResponse }: InputInteractionProps) {
  const [value, setValue] = useState('');
  
  const handleSubmit = () => {
    if (!value.trim() && request.required) {
      return;
    }
    
    const response: InteractionResponse = {
      request_id: request.id,
      type: 'input',
      text: value,
      responded_at: new Date(),
    };
    
    onResponse(response);
  };
  
  return (
    <div className="interaction-input">
      <h3>{request.title}</h3>
      {request.description && <p>{request.description}</p>}
      {request.multiline ? (
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={request.placeholder}
          rows={5}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={request.placeholder}
          onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
        />
      )}
      <div className="actions">
        <button onClick={handleSubmit} disabled={!value.trim() && request.required}>
          Submit
        </button>
      </div>
    </div>
  );
}
```

#### SelectInteraction 组件

```typescript
// agio-frontend/src/components/interaction/SelectInteraction.tsx

export function SelectInteraction({ request, onResponse }: InputInteractionProps) {
  const [selected, setSelected] = useState<string[]>([]);
  
  const handleToggle = (value: string) => {
    if (request.multiple) {
      setSelected(prev => 
        prev.includes(value) 
          ? prev.filter(v => v !== value)
          : [...prev, value]
      );
    } else {
      setSelected([value]);
    }
  };
  
  const handleSubmit = () => {
    const response: InteractionResponse = {
      request_id: request.id,
      type: 'select',
      selected_values: selected,
      responded_at: new Date(),
    };
    
    onResponse(response);
  };
  
  return (
    <div className="interaction-select">
      <h3>{request.title}</h3>
      {request.description && <p>{request.description}</p>}
      <div className="options">
        {request.options?.map(option => (
          <label key={option.value} className="option">
            <input
              type={request.multiple ? 'checkbox' : 'radio'}
              checked={selected.includes(option.value)}
              onChange={() => handleToggle(option.value)}
            />
            <div>
              <strong>{option.label}</strong>
              {option.description && <p>{option.description}</p>}
            </div>
          </label>
        ))}
      </div>
      <div className="actions">
        <button onClick={handleSubmit} disabled={selected.length === 0}>
          Submit
        </button>
      </div>
    </div>
  );
}
```

#### ConfirmInteraction 组件

```typescript
// agio-frontend/src/components/interaction/ConfirmInteraction.tsx

export function ConfirmInteraction({ request, onResponse }: InputInteractionProps) {
  const handleConfirm = (confirmed: boolean) => {
    const response: InteractionResponse = {
      request_id: request.id,
      type: 'confirm',
      confirmed,
      responded_at: new Date(),
    };
    
    onResponse(response);
  };
  
  return (
    <div className="interaction-confirm">
      <h3>{request.title}</h3>
      {request.description && <p>{request.description}</p>}
      <div className="actions">
        <button 
          onClick={() => handleConfirm(true)}
          className="confirm"
        >
          {request.confirm_text || 'Allow'}
        </button>
        <button 
          onClick={() => handleConfirm(false)}
          className="cancel"
        >
          {request.cancel_text || 'Deny'}
        </button>
      </div>
    </div>
  );
}
```

### 7.2 Chat 界面集成

```typescript
// agio-frontend/src/pages/Chat.tsx (修改)

import { InteractionRequest } from '@/components/interaction/InteractionRequest';
import { InteractionResponse } from '@/types/interaction';

export default function Chat() {
  const [pendingInteraction, setPendingInteraction] = useState<InteractionRequest | null>(null);
  
  // 在 useSSEStream 中处理事件
  const { events, sendMessage } = useSSEStream({
    onEvent: (event: StepEvent) => {
      if (event.type === 'interaction_request') {
        const request = event.data.interaction_request as InteractionRequest;
        setPendingInteraction(request);
      }
    },
    // ... 其他回调
  });
  
  const handleInteractionResponse = async (response: InteractionResponse) => {
    try {
      // 提交响应到后端
      const res = await fetch(`/api/interactions/${response.request_id}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(response),
      });
      
      if (!res.ok) {
        throw new Error('Failed to submit interaction response');
      }
      
      // 清除待处理的交互
      setPendingInteraction(null);
      
      // 如果需要，可以重新连接 SSE 流来接收恢复后的执行结果
      // 或者后端可以通过同一个 SSE 连接继续发送事件
    } catch (error) {
      console.error('Error submitting interaction response:', error);
    }
  };
  
  return (
    <div className="chat-container">
      {/* 消息列表 */}
      <div className="messages">
        {/* ... 现有消息渲染 ... */}
      </div>
      
      {/* 交互组件覆盖层 */}
      {pendingInteraction && (
        <div className="interaction-overlay">
          <div className="interaction-modal">
            <InteractionRequest
              request={pendingInteraction}
              onResponse={handleInteractionResponse}
            />
          </div>
        </div>
      )}
      
      {/* 输入框 */}
      <MessageInput onSend={sendMessage} />
    </div>
  );
}
```

### 7.3 样式设计

```css
/* agio-frontend/src/components/interaction/interaction.css */

.interaction-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.interaction-modal {
  background: white;
  border-radius: 8px;
  padding: 24px;
  max-width: 500px;
  width: 90%;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.interaction-input textarea,
.interaction-input input {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.interaction-select .options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.interaction-select .option {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
}

.interaction-confirm .actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.interaction-confirm button.confirm {
  background: #4CAF50;
  color: white;
}

.interaction-confirm button.cancel {
  background: #f44336;
  color: white;
}
```

## 8. 实现步骤

### Phase 1: 核心数据模型和存储
1. ✅ 实现 `InteractionRequest` 和 `InteractionResponse` 数据模型
2. ✅ 实现 `PermissionStore` 和权限匹配逻辑
3. ✅ 扩展 `SessionStore` 支持暂停状态存储（新增方法）

### Phase 2: 权限系统集成
1. ✅ 实现 `PermissionManager`
2. ✅ 在 `ToolExecutor` 中集成权限检查
3. ✅ 实现权限存储的 MongoDB 集合和索引

### Phase 3: HITL 执行暂停和恢复
1. ✅ 实现 `SuspendExecution` 异常
2. ✅ 在 `StepRunner` 中处理暂停
3. ✅ 实现恢复执行逻辑（`resume_from_interaction` 方法）

### Phase 4: 事件和 API
1. ✅ 扩展 `StepEvent` 支持新事件类型
2. ✅ 实现交互响应 API (`/interactions/{id}/respond`)
3. ✅ 实现权限管理 API (`/permissions/{user_id}`)
4. ✅ 更新前端 SSE 流处理新事件类型

### Phase 5: 前端组件
1. ✅ 实现交互组件（Input, Select, Confirm, Combined）
2. ✅ 集成到 Chat 界面（覆盖层显示）
3. ✅ 实现交互响应提交和恢复执行

---

## 9. 工具自定义权限资源标识符

工具可以通过实现 `get_permission_resource` 方法来自定义权限资源标识符的生成逻辑：

```python
# agio/providers/tools/builtin/file_read_tool/file_read_tool.py

class FileReadTool(BaseTool):
    # ... 现有代码 ...
    
    def get_permission_resource(self, args: dict) -> str:
        """
        生成权限资源标识符
        
        对于 file_read，返回文件路径
        例如: ~/.zshrc, ./config.yaml
        """
        file_path = args.get("file_path", "")
        return file_path

# agio/providers/tools/builtin/bash_tool/bash_tool.py

class BashTool(BaseTool):
    # ... 现有代码 ...
    
    def get_permission_resource(self, args: dict) -> str:
        """
        生成权限资源标识符
        
        对于 bash，返回命令的关键部分
        例如: npm run lint, curl https://api.example.com
        """
        command = args.get("command", "")
        # 提取命令的关键部分（去除参数）
        parts = command.split()
        if len(parts) > 0:
            # 返回命令和第一个参数（如果有）
            if len(parts) > 1:
                return f"{parts[0]} {parts[1]}"
            return parts[0]
        return command
```

## 10. 使用示例

### 10.1 配置 Agent 启用权限系统

```yaml
# configs/agents/code_assistant.yaml
type: agent
name: code_assistant
model: gpt4_model
tools:
  - file_read
  - file_write
  - bash
enable_hitl: true
enable_permissions: true
```

### 10.2 Agent 执行流程示例

1. **用户请求**：用户发送 "请运行 npm run lint"
2. **Agent 决策**：Agent 决定调用 `bash` 工具执行 `npm run lint`
3. **权限检查**：
   - `PermissionManager` 检查用户是否有 `bash(npm run lint)` 的权限
   - 如果没有匹配的权限记录，返回 `NEEDS_AUTH`
4. **暂停执行**：
   - `ToolExecutor` 抛出 `SuspendExecution` 异常
   - `StepRunner` 捕获异常，保存暂停状态，发送 `INTERACTION_REQUEST` 事件
5. **用户交互**：
   - 前端收到事件，显示确认对话框
   - 用户点击 "Allow"
6. **恢复执行**：
   - 前端提交响应到 `/interactions/{id}/respond`
   - 后端保存权限记录，恢复工具执行
   - 工具执行完成后，继续 Agent 执行流程

### 10.3 权限记录示例

```json
{
  "user_id": "user-123",
  "allow": [
    "bash(npm run lint)",
    "bash(npm run test:*)",
    "file_read(~/.zshrc)",
    "file_read(./src/**)"
  ],
  "deny": [
    "bash(curl:*)",
    "bash(rm -rf *)",
    "file_read(./.env)",
    "file_read(./secrets/**)"
  ]
}
```

### 10.4 自定义交互请求示例

Agent 可以在工具执行前主动请求用户输入：

```python
# 在工具中主动请求用户输入
from agio.runtime.exceptions import SuspendExecution
from agio.domain.interaction import InteractionRequest, InteractionType

class CustomTool(BaseTool):
    async def execute(self, parameters, abort_signal=None):
        # 需要用户确认某些操作
        request = InteractionRequest(
            type=InteractionType.CONFIRM,
            title="Confirm Operation",
            description="Do you want to proceed with this operation?",
            run_id=self._get_run_id_from_context(),
        )
        raise SuspendExecution(request, parameters, self._get_context())
```

## 11. 注意事项

1. **状态持久化**：暂停状态必须持久化，支持页面刷新后恢复
2. **超时处理**：交互请求有过期时间，超时后需要处理（可以配置默认超时时间）
3. **并发安全**：多个用户同时响应同一个交互请求的处理（通过 interaction_id 唯一性保证）
4. **权限缓存**：权限查询结果可以缓存以提高性能（建议使用 Redis 缓存）
5. **向后兼容**：现有工具和 Agent 在没有配置权限的情况下应该正常工作（默认行为：需要授权）
6. **工具参数序列化**：暂停状态中的工具参数需要能够正确序列化和反序列化
7. **上下文恢复**：恢复执行时需要正确重建 ExecutionContext，包括 wire、user_id 等关键信息
8. **错误处理**：如果恢复执行时出现错误（如工具执行失败），需要正确处理并通知用户
