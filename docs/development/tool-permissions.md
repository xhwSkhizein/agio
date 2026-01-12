# 工具执行权限设计（实现方案）

## 目标
- 在工具调用前统一进行权限判定，未授权时向用户请求授权。
- 授权结果可复用，支持 allow/deny pattern，避免重复确认。
- **已授权数据有缓存，避免每次都查 DB**。
- **授权失败时返回明确的 ToolResult（关键：确保 LLM 能处理）**。
- 不影响现有分层（Agent → runtime → providers → config），最小侵入。
- 保持可观测与可恢复：授权阻塞可被前端感知，授权后可继续执行。
- 支持超时和取消，防止资源泄漏。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     ToolExecutor                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  PermissionManager.check_and_wait_consent()         │  │
│  │  → 返回 ConsentResult (allowed/denied)              │  │
│  │  → 如果 denied，返回授权被拒的 ToolResult            │  │
│  │  → 如果 allowed，继续执行工具                        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────────────────┐
        │      PermissionManager (统一权限模块)             │
        │  ┌───────────────────────────────────────────┐  │
        │  │ 1. 检查缓存（内存 LRU Cache）              │  │
        │  │ 2. 查询 ConsentStore（带缓存）             │  │
        │  │ 3. 调用 PermissionService 判定             │  │
        │  │ 4. 如需授权 → 发送事件 + 等待               │  │
        │  │ 5. 返回 ConsentResult (allowed/denied)     │  │
        │  └───────────────────────────────────────────┘  │
        └─────────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────┐
        │         Wire (事件流)                │
        │  TOOL_AUTH_REQUIRED → 前端展示       │
        └─────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────┐
        │      API: /tool-consent             │
        │  用户决策 → ConsentStore 写入         │
        │  → ConsentWaiter.resolve() 唤醒      │
        │  → 清除相关缓存                      │
        └─────────────────────────────────────┘
```

## 核心组件

### 1. PermissionManager（统一权限管理器）

**职责**：统一的权限检查入口，整合所有权限相关功能，提供缓存，返回明确的授权结果。

**实现位置**：`agio/tools/permission.py`（统一权限模块）

**接口**：
```python
class ConsentResult(BaseModel):
    """授权检查结果"""
    allowed: bool  # True=允许执行, False=拒绝执行
    reason: str  # 原因说明
    from_cache: bool = False  # 是否来自缓存

class PermissionManager:
    """
    统一权限管理器。
    
    职责：
    1. 权限检查（缓存 + DB）
    2. 授权等待协调
    3. 返回明确的授权结果（allowed/denied）
    """
    
    def __init__(
        self,
        consent_store: ConsentStore,
        consent_waiter: ConsentWaiter,
        permission_service: PermissionService,
        cache_ttl: int = 300,  # 缓存 TTL（秒）
        cache_size: int = 1000,  # 缓存大小
    ):
        self.consent_store = consent_store
        self.consent_waiter = consent_waiter
        self.permission_service = permission_service
        # LRU 缓存：key = (user_id, tool_name, args_hash), value = (ConsentResult, timestamp)
        self._cache: dict[str, tuple[ConsentResult, float]] = {}
        self._cache_ttl = cache_ttl
        self._cache_size = cache_size
        self._cache_lock = asyncio.Lock()
    
    async def check_and_wait_consent(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        context: ExecutionContext,
        timeout: float = 300.0,
    ) -> ConsentResult:
        """
        检查并等待授权，返回明确的授权结果。
        
        Args:
            tool_call_id: 工具调用唯一标识
            tool_name: 工具名称
            tool_args: 工具参数
            context: 执行上下文
            timeout: 超时时间（秒）
        
        Returns:
            ConsentResult: 授权结果（allowed=True/False）
            
        流程：
        1. 检查缓存（命中且未过期 → 直接返回）
        2. 检查工具配置 requires_consent（False → allowed）
        3. 查询 ConsentStore pattern 匹配（命中 → allowed/denied）
        4. 调用 PermissionService（策略判定）
        5. 如需授权 → 发送事件 + 等待用户决策
        6. 返回明确的 ConsentResult（allowed=True/False）
        7. 缓存结果
        """
        user_id = context.user_id
        if not user_id:
            # 无 user_id，视为需要授权
            return await self._request_consent(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                tool_args=tool_args,
                context=context,
                timeout=timeout,
            )
        
        # 1. 检查缓存
        cache_key = self._make_cache_key(user_id, tool_name, tool_args)
        cached_result = await self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        # 2. 检查工具配置
        tool_config = self._get_tool_config(tool_name)
        requires_consent = tool_config.get("requires_consent", False) if tool_config else False
        
        if not requires_consent:
            result = ConsentResult(allowed=True, reason="Tool does not require consent")
            await self._set_cache(cache_key, result)
            return result
        
        # 3. 查询 ConsentStore（pattern 匹配）
        store_result = await self.consent_store.check_consent(
            user_id=user_id,
            tool_name=tool_name,
            tool_args=tool_args,
        )
        
        if store_result == "allowed":
            result = ConsentResult(allowed=True, reason="Matched allow pattern")
            await self._set_cache(cache_key, result)
            return result
        
        if store_result == "denied":
            result = ConsentResult(allowed=False, reason="Matched deny pattern")
            await self._set_cache(cache_key, result)
            return result
        
        # 4. 调用 PermissionService
        permission_decision = await self.permission_service.check_permission(
            user_id=user_id,
            tool_name=tool_name,
            tool_args=tool_args,
            context=context,
        )
        
        if permission_decision.decision == "allowed":
            result = ConsentResult(allowed=True, reason=permission_decision.reason)
            await self._set_cache(cache_key, result)
            return result
        
        if permission_decision.decision == "denied":
            result = ConsentResult(allowed=False, reason=permission_decision.reason)
            await self._set_cache(cache_key, result)
            return result
        
        # 5. requires_consent：请求用户授权
        return await self._request_consent(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_args=tool_args,
            context=context,
            permission_decision=permission_decision,
            timeout=timeout,
        )
    
    async def _request_consent(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        context: ExecutionContext,
        permission_decision: PermissionDecision | None = None,
        timeout: float = 300.0,
    ) -> ConsentResult:
        """请求用户授权并等待决策"""
        # 1. 发送 TOOL_AUTH_REQUIRED 事件
        await self._send_auth_required_event(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_args=tool_args,
            context=context,
            permission_decision=permission_decision,
        )
        
        # 2. 等待用户决策
        try:
            decision = await self.consent_waiter.wait_for_consent(
                tool_call_id=tool_call_id,
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            # 超时视为拒绝
            result = ConsentResult(
                allowed=False,
                reason="User consent request timed out",
            )
            await self._send_auth_denied_event(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                context=context,
                reason="Timeout",
            )
            return result
        
        # 3. 保存授权记录（如果允许）
        if decision.decision == "allow" and decision.patterns:
            user_id = context.user_id
            if user_id:
                await self.consent_store.save_consent(
                    user_id=user_id,
                    tool_name=tool_name,
                    patterns=decision.patterns,
                    expires_at=decision.expires_at,
                )
                # 清除相关缓存
                await self._invalidate_cache(user_id, tool_name)
        
        # 4. 返回结果
        if decision.decision == "deny":
            result = ConsentResult(
                allowed=False,
                reason="User denied consent",
            )
            await self._send_auth_denied_event(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                context=context,
                reason="User denied",
            )
            return result
        
        # 5. 允许执行
        result = ConsentResult(
            allowed=True,
            reason="User granted consent",
        )
        # 缓存结果
        if context.user_id:
            cache_key = self._make_cache_key(context.user_id, tool_name, tool_args)
            await self._set_cache(cache_key, result)
        return result
    
    def _make_cache_key(
        self,
        user_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> str:
        """生成缓存 key"""
        import hashlib
        import json
        
        # 序列化参数（排除 tool_call_id）
        args_copy = {k: v for k, v in tool_args.items() if k != "tool_call_id"}
        args_str = json.dumps(args_copy, sort_keys=True)
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
        
        return f"{user_id}:{tool_name}:{args_hash}"
    
    async def _get_from_cache(self, cache_key: str) -> ConsentResult | None:
        """从缓存获取结果"""
        import time
        
        async with self._cache_lock:
            if cache_key not in self._cache:
                return None
            
            result, timestamp = self._cache[cache_key]
            
            # 检查是否过期
            if time.time() - timestamp > self._cache_ttl:
                del self._cache[cache_key]
                return None
            
            # 返回缓存结果（标记为来自缓存）
            return ConsentResult(
                allowed=result.allowed,
                reason=result.reason,
                from_cache=True,
            )
    
    async def _set_cache(self, cache_key: str, result: ConsentResult) -> None:
        """设置缓存"""
        import time
        
        async with self._cache_lock:
            # LRU 淘汰：如果缓存已满，删除最旧的
            if len(self._cache) >= self._cache_size:
                # 删除最旧的（简单策略：删除第一个）
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            
            self._cache[cache_key] = (result, time.time())
    
    async def _invalidate_cache(self, user_id: str, tool_name: str | None = None) -> None:
        """清除缓存（授权记录更新后调用）"""
        async with self._cache_lock:
            keys_to_delete = []
            prefix = f"{user_id}:{tool_name}:" if tool_name else f"{user_id}:"
            for key in self._cache.keys():
                if key.startswith(prefix):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self._cache[key]
```

### 2. PermissionService（权限策略服务）

**职责**：基于工具配置和上下文生成权限决策。

**接口**：
```python
class PermissionDecision(BaseModel):
    """权限决策结果"""
    decision: Literal["allowed", "denied", "requires_consent"]
    reason: str
    suggested_patterns: list[str] | None = None  # 建议的 pattern
    expires_at_hint: datetime | None = None  # 建议过期时间

class PermissionService:
    async def check_permission(
        self,
        user_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        context: ExecutionContext,
    ) -> PermissionDecision:
        """
        检查工具执行权限。
        
        决策逻辑：
        1. 如果工具配置 requires_consent=False → allowed
        2. 如果工具配置 requires_consent=True → requires_consent
        3. Agent 可覆盖默认策略（如只读工具集）
        
        Returns:
            PermissionDecision: 权限决策
        """
```

### 3. ConsentStore（授权记录存储）

**职责**：持久化用户授权记录（allow/deny patterns + 过期时间）。

**接口**：
```python
class ConsentStore:
    async def check_consent(
        self,
        user_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> Literal["allowed", "denied", None]:
        """
        查询授权记录。
        
        匹配策略：
        1. 先匹配 deny_patterns（命中 → denied）
        2. 再匹配 patterns（命中 → allowed）
        3. 未命中 → None（需要授权）
        
        Returns:
            "allowed" | "denied" | None
        """
    
    async def save_consent(
        self,
        user_id: str,
        tool_name: str | None,
        patterns: list[str],
        deny_patterns: list[str] = [],
        expires_at: datetime | None = None,
    ) -> None:
        """保存授权记录"""
```

**存储方案**：复用 SessionStore 的 MongoDB，新增 `consents` 集合。

### 4. ConsentWaiter（授权等待协调器）

**职责**：基于 `asyncio.Event` 的协调器，挂起等待用户授权，收到结果后唤醒继续。

**接口**：
```python
class ConsentDecision(BaseModel):
    """授权决策"""
    decision: Literal["allow", "deny"]
    patterns: list[str] = []  # 用户选择的 patterns
    expires_at: datetime | None = None

class ConsentWaiter:
    async def wait_for_consent(
        self,
        tool_call_id: str,
        timeout: float | None = None,
    ) -> ConsentDecision:
        """等待用户授权决策"""
    
    async def resolve(
        self,
        tool_call_id: str,
        decision: ConsentDecision,
    ) -> None:
        """解析授权决策并唤醒等待的任务"""
```

## ToolExecutor 集成

**关键点**：授权失败时必须返回明确的 ToolResult，不能返回 None 或挂起。

**修改点**：在 `agio/tools/executor.py` 的 `execute()` 方法中添加权限检查。

**流程**：
```python
async def execute(
    self,
    tool_call: dict[str, Any],
    context: ExecutionContext,
    abort_signal: AbortSignal | None = None,
) -> ToolResult:
    """执行工具调用（含权限检查）"""
    # ... 现有参数解析代码 ...
    
    fn_name = tool_call.get("function", {}).get("name")
    call_id = tool_call.get("id")
    start_time = time.time()
    
    # 获取工具实例
    tool = self.tools_map.get(fn_name)
    if not tool:
        return self._create_error_result(...)
    
    # 解析参数
    try:
        if isinstance(fn_args_str, str):
            args = json.loads(fn_args_str)
        else:
            args = fn_args_str or {}
    except json.JSONDecodeError as e:
        return self._create_error_result(...)
    
    args["tool_call_id"] = call_id
    
    # ===== 权限检查 =====
    permission_manager = get_permission_manager()  # 从依赖注入获取
    consent_result = await permission_manager.check_and_wait_consent(
        tool_call_id=call_id,
        tool_name=fn_name,
        tool_args=args,
        context=context,
        timeout=300.0,
    )
    
    # 关键：授权失败时返回明确的 ToolResult
    if not consent_result.allowed:
        return self._create_denied_result(
            call_id=call_id,
            tool_name=fn_name,
            reason=consent_result.reason,
            start_time=start_time,
        )
    
    # 授权通过，继续执行工具
    # ... 现有的缓存检查和工具执行代码 ...
    
    try:
        result: ToolResult = await tool.execute(
            args, context=context, abort_signal=abort_signal
        )
        # ... 缓存处理 ...
        return result
    except Exception as e:
        return self._create_error_result(...)

def _create_denied_result(
    self,
    call_id: str,
    tool_name: str,
    reason: str,
    start_time: float,
) -> ToolResult:
    """
    创建授权被拒的 ToolResult。
    
    关键：必须返回明确的 ToolResult，包含错误信息，
    让 LLM 能够理解为什么工具调用失败。
    """
    end_time = time.time()
    return ToolResult(
        tool_name=tool_name,
        tool_call_id=call_id,
        input_args={},
        content=f"Tool execution denied: {reason}. Please ask the user for permission or use a different approach.",
        output=None,
        error=f"Permission denied: {reason}",
        start_time=start_time,
        end_time=end_time,
        duration=end_time - start_time,
        is_success=False,
    )
```

**重要说明**：
- 授权失败时，返回的 ToolResult 必须包含清晰的错误信息
- `content` 字段应该包含 LLM 可理解的消息，说明为什么被拒绝
- `error` 字段用于日志和调试
- `is_success=False` 标记执行失败

## 事件定义

### 新增事件类型

在 `agio/domain/events.py` 中添加：

```python
class StepEventType(str, Enum):
    # ... 现有事件类型 ...
    
    # Tool permission events
    TOOL_AUTH_REQUIRED = "tool_auth_required"  # 需要授权
    TOOL_AUTH_DENIED = "tool_auth_denied"       # 授权被拒绝
```

### TOOL_AUTH_REQUIRED 事件

```python
# 事件数据格式
{
    "type": "tool_auth_required",
    "run_id": "...",
    "timestamp": "...",
    "data": {
        "tool_call_id": "call_abc123",
        "tool_name": "bash",
        "args_preview": "npm run lint",
        "suggested_patterns": [
            "bash(npm run lint)",
            "bash(npm run test:*)"
        ],
        "reason": "Tool requires user consent",
        "expires_at_hint": "2025-12-31T00:00:00Z"
    }
}
```

### TOOL_AUTH_DENIED 事件

```python
# 事件数据格式
{
    "type": "tool_auth_denied",
    "run_id": "...",
    "timestamp": "...",
    "data": {
        "tool_call_id": "call_abc123",
        "tool_name": "bash",
        "reason": "User denied consent"
    }
}
```

## API 端点

### POST /agio/tool-consent

**请求**：
```json
{
    "tool_call_id": "call_abc123",
    "decision": "allow",
    "patterns": ["bash(npm run lint)"],
    "expires_at": "2025-12-31T00:00:00Z",
    "user_id": "user_123"
}
```

**响应**：
```json
{
    "success": true,
    "tool_call_id": "call_abc123",
    "message": "Consent saved and execution resumed"
}
```

**实现位置**：`agio/api/routes/tool_consent.py`

**关键点**：保存授权后，清除相关缓存：
```python
@router.post("")
async def submit_tool_consent(
    request: ToolConsentRequest,
    consent_store: ConsentStore = Depends(get_consent_store),
    consent_waiter: ConsentWaiter = Depends(get_consent_waiter),
    permission_manager: PermissionManager = Depends(get_permission_manager),
):
    """提交工具授权决策"""
    # ... 验证请求 ...
    
    # 保存授权记录
    if request.decision == "allow" and request.user_id:
        await consent_store.save_consent(...)
        # 清除相关缓存
        await permission_manager._invalidate_cache(
            request.user_id, 
            tool_name=None  # 清除该用户所有工具的缓存
        )
    
    # 唤醒等待的任务
    await consent_waiter.resolve(request.tool_call_id, decision)
    
    return {"success": True, ...}
```

## 配置集成

### 工具配置扩展

在 `agio/config/schema.py` 的 `ToolConfig` 中添加：

```python
class ToolConfig(ComponentConfig):
    # ... 现有字段 ...
    
    requires_consent: bool = Field(
        default=False,
        description="Whether this tool requires user consent before execution"
    )
```

### 默认配置策略

**高风险工具默认开启**：
- `bash`: `requires_consent: true`
- `file_edit`: `requires_consent: true`
- `file_write`: `requires_consent: true`
- `file_read`: `requires_consent: true`（读取敏感路径时）

## Pattern 匹配实现

### Pattern 格式

```
{tool_name}({arg_pattern})
```

**示例**：
- `bash(npm run lint)` - 精确匹配
- `bash(npm run test:*)` - glob 模式
- `file_read(~/.zshrc)` - 精确匹配
- `file_read(./.env.*)` - glob 模式

### 匹配逻辑

```python
import fnmatch

def match_pattern(
    pattern: str,
    tool_name: str,
    tool_args: dict[str, Any],
) -> bool:
    """匹配 pattern"""
    # 解析 pattern: "{tool_name}({arg_pattern})"
    if not pattern.endswith(")"):
        return False
    
    open_paren = pattern.find("(")
    if open_paren == -1:
        return False
    
    pattern_tool_name = pattern[:open_paren]
    arg_pattern = pattern[open_paren + 1:-1]
    
    # 匹配工具名
    if not fnmatch.fnmatch(tool_name, pattern_tool_name):
        return False
    
    # 构造参数字符串用于匹配
    args_str = _serialize_args(tool_args)
    
    # 使用 glob 匹配
    return fnmatch.fnmatch(args_str, arg_pattern)
```

## 依赖注入

### 在 `agio/api/deps.py` 中添加

```python
from agio.tools.permission import PermissionManager, get_permission_manager

# 单例 PermissionManager
_permission_manager: PermissionManager | None = None

def get_permission_manager() -> PermissionManager:
    """Get global PermissionManager instance"""
    global _permission_manager
    if _permission_manager is None:
        from agio.tools.permission import PermissionManager
        from agio.tools.consent_store import get_consent_store
        from agio.tools.consent_waiter import get_consent_waiter
        from agio.tools.permission_service import get_permission_service
        
        _permission_manager = PermissionManager(
            consent_store=get_consent_store(),
            consent_waiter=get_consent_waiter(),
            permission_service=get_permission_service(),
            cache_ttl=300,
            cache_size=1000,
        )
    return _permission_manager
```

## 设计原则总结

1. **统一权限模块**：PermissionManager 整合所有权限相关功能
2. **缓存优化**：已授权数据有缓存，避免每次都查 DB
3. **明确的结果**：授权失败时返回明确的 ToolResult，确保 LLM 能处理
4. **职责单一**：PermissionService 判定，ConsentStore 持久化，ConsentWaiter 同步等待
5. **最小侵入**：仅在 ToolExecutor 中添加权限检查
6. **可观测**：事件流经 Wire，前端可感知阻塞
7. **安全默认**：deny 优先，未命中视为未授权
8. **幂等与安全**：拒绝/超时都要唤醒等待；执行前再校验授权
9. **资源管理**：支持超时/取消，防止悬挂和泄漏

## 实施步骤

### Phase 1: 核心组件（1-2 天）
1. 实现 `PermissionManager`（统一权限管理器 + 缓存）
2. 实现 `ConsentStore`（MongoDB + InMemory）
3. 实现 `ConsentWaiter`
4. 实现 `PermissionService`

### Phase 2: ToolExecutor 集成（1 天）
1. 修改 `ToolExecutor.execute()` 添加权限检查
2. 实现 `_create_denied_result()` 方法
3. 确保授权失败时返回明确的 ToolResult

### Phase 3: API 和事件（1 天）
1. 添加 `TOOL_AUTH_REQUIRED` 和 `TOOL_AUTH_DENIED` 事件类型
2. 实现 `/tool-consent` API 端点
3. 实现缓存清除逻辑

### Phase 4: 配置集成（0.5 天）
1. 扩展 `ToolConfig` schema
2. 更新工具配置文件
3. 添加默认策略

### Phase 5: 前端集成（1-2 天）
1. 处理新事件类型
2. 实现授权卡片 UI
3. 集成 API 调用

### Phase 6: 测试和文档（1-2 天）
1. 编写单元测试（重点测试缓存和授权失败场景）
2. 编写集成测试
3. 更新文档
