# HITL (Human-in-the-Loop) 和权限系统设计方案 V2

## 概述

本文档重新设计了一套低侵入性的 HITL 和权限系统，解决了 V1 版本中的复杂性问题。

## 设计原则

1. **低侵入性**：最小化对现有架构的修改
2. **可配置性**：通过配置系统灵活控制 HITL 和权限行为
3. **简化状态管理**：不使用复杂的 SuspendedState，通过事件和交互请求实现
4. **统一事件流**：所有交互通过 Wire 事件流传递，前端统一处理

## 关键设计决策

### 1. 不使用 SuspendedState

**原因**：
- 引入过多复杂性
- 需要处理嵌套执行（Workflow/RunnableAsTool）的复杂场景
- 恢复逻辑复杂，需要重建整个执行上下文

**替代方案**：
- 暂停时发送 `INTERACTION_REQUEST` 事件，包含所有必要信息
- 恢复时通过 `interaction_id` 和 `tool_call_id` 重新执行工具调用
- 工具执行结果通过 Wire 继续后续流程

### 2. 权限系统通过配置系统构建

- `PermissionManager` 作为可配置组件
- 通过配置系统构建并注入到 `ToolExecutor`
- 支持不同的权限存储后端（MongoDB、内存等）

### 3. 恢复机制简化

- 不需要保存整个执行状态
- 只需要保存交互请求和对应的工具调用信息
- 恢复时重新执行工具调用，权限检查会通过（因为已保存权限记录）

---

## 第一部分：核心数据模型

### 1.1 InteractionRequest 和 InteractionResponse

```python
# agio/domain/interaction.py

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


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
    
    # 上下文信息（用于恢复执行）
    run_id: str
    session_id: str
    step_id: Optional[str] = None
    tool_call_id: str  # 必须：用于恢复时重新执行工具调用
    tool_name: str     # 必须：工具名称
    tool_args: dict    # 必须：工具参数（用于恢复执行）
    
    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None  # 过期时间


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

### 1.2 异常定义

```python
# agio/runtime/exceptions.py

from agio.domain.interaction import InteractionRequest


class SuspendExecution(Exception):
    """
    执行暂停异常，用于 HITL 交互
    
    当工具执行需要用户交互时，抛出此异常。
    异常中包含交互请求和工具调用信息，用于后续恢复执行。
    """
    def __init__(
        self,
        interaction_request: InteractionRequest,
    ):
        self.interaction_request = interaction_request
        super().__init__(
            f"Execution suspended for interaction: {interaction_request.id}"
        )
```

---

## 第二部分：权限系统设计

### 2.1 权限决策枚举

```python
# agio/runtime/permissions.py

from enum import Enum


class PermissionDecision(str, Enum):
    """权限决策"""
    ALLOWED = "allowed"      # 已授权，直接执行
    DENIED = "denied"        # 明确拒绝
    NEEDS_AUTH = "needs_auth"  # 需要用户授权
```

### 2.2 权限存储接口

```python
# agio/providers/storage/permissions.py

from abc import ABC, abstractmethod
from typing import Optional
from agio.runtime.permissions import PermissionDecision


class PermissionStore(ABC):
    """权限存储接口"""
    
    @abstractmethod
    async def check_permission(
        self,
        user_id: str,
        resource: str,
    ) -> PermissionDecision:
        """
        检查权限
        
        Args:
            user_id: 用户 ID
            resource: 权限资源标识符，格式: tool_name(arg_pattern)
        
        Returns:
            PermissionDecision: 权限决策
        """
        pass
    
    @abstractmethod
    async def save_permission(
        self,
        user_id: str,
        resource: str,
        allowed: bool,
    ) -> None:
        """
        保存权限记录
        
        Args:
            user_id: 用户 ID
            resource: 权限资源标识符
            allowed: 是否允许
        """
        pass
    
    @abstractmethod
    async def get_user_permissions(
        self,
        user_id: str,
    ) -> dict[str, list[str]]:
        """
        获取用户权限配置
        
        Returns:
            dict with keys: "allow", "deny"
        """
        pass
```

### 2.3 MongoDB 权限存储实现

```python
# agio/providers/storage/permissions.py

import fnmatch
import re
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from agio.runtime.permissions import PermissionDecision
from agio.providers.storage.permissions import PermissionStore
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class MongoPermissionStore(PermissionStore):
    """MongoDB 权限存储实现"""
    
    def __init__(self, mongo_uri: str, db_name: str = "agio"):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db["permissions"]
        self._initialized = False
    
    async def initialize(self):
        """初始化索引"""
        if self._initialized:
            return
        
        await self.collection.create_index("user_id", unique=True)
        await self.collection.create_index([("user_id", 1), ("resource", 1)])
        
        self._initialized = True
        logger.info("permission_store_initialized", db=self.db.name)
    
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
        await self.initialize()
        
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
    ) -> None:
        """保存权限记录"""
        await self.initialize()
        
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
    
    async def get_user_permissions(
        self,
        user_id: str,
    ) -> dict[str, list[str]]:
        """获取用户权限配置"""
        await self.initialize()
        
        doc = await self.collection.find_one({"user_id": user_id})
        if not doc:
            return {"allow": [], "deny": []}
        
        return {
            "allow": doc.get("allow", []),
            "deny": doc.get("deny", []),
        }
```

### 2.4 内存权限存储实现（用于测试）

```python
# agio/providers/storage/permissions.py

from typing import Optional
from agio.runtime.permissions import PermissionDecision
from agio.providers.storage.permissions import PermissionStore


class InMemoryPermissionStore(PermissionStore):
    """内存权限存储实现（用于测试）"""
    
    def __init__(self):
        self._permissions: dict[str, dict[str, list[str]]] = {}
    
    async def check_permission(
        self,
        user_id: str,
        resource: str,
    ) -> PermissionDecision:
        """检查权限"""
        user_perms = self._permissions.get(user_id)
        if not user_perms:
            return PermissionDecision.NEEDS_AUTH
        
        allow_patterns = user_perms.get("allow", [])
        deny_patterns = user_perms.get("deny", [])
        
        # 先检查 deny
        for pattern in deny_patterns:
            if self._match_pattern(resource, pattern):
                return PermissionDecision.DENIED
        
        # 再检查 allow
        for pattern in allow_patterns:
            if self._match_pattern(resource, pattern):
                return PermissionDecision.ALLOWED
        
        return PermissionDecision.NEEDS_AUTH
    
    def _match_pattern(self, resource: str, pattern: str) -> bool:
        """模式匹配（简化版，仅支持精确匹配和简单通配符）"""
        import fnmatch
        return fnmatch.fnmatch(resource, pattern)
    
    async def save_permission(
        self,
        user_id: str,
        resource: str,
        allowed: bool,
    ) -> None:
        """保存权限记录"""
        if user_id not in self._permissions:
            self._permissions[user_id] = {"allow": [], "deny": []}
        
        key = "allow" if allowed else "deny"
        other_key = "deny" if allowed else "allow"
        
        if resource not in self._permissions[user_id][key]:
            self._permissions[user_id][key].append(resource)
        
        if resource in self._permissions[user_id][other_key]:
            self._permissions[user_id][other_key].remove(resource)
    
    async def get_user_permissions(
        self,
        user_id: str,
    ) -> dict[str, list[str]]:
        """获取用户权限配置"""
        return self._permissions.get(user_id, {"allow": [], "deny": []})
```

---

## 第二部分：PermissionManager 和配置系统集成

### 2.5 PermissionManager 实现

```python
# agio/runtime/permissions.py

from typing import Optional
from agio.providers.tools import BaseTool
from agio.domain import ExecutionContext
from agio.domain.interaction import InteractionRequest, InteractionType
from agio.runtime.permissions import PermissionDecision
from agio.providers.storage.permissions import PermissionStore
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class PermissionManager:
    """
    权限管理器
    
    负责检查工具执行权限，并在需要时创建授权请求。
    """
    
    def __init__(self, store: Optional[PermissionStore] = None):
        """
        初始化权限管理器
        
        Args:
            store: 权限存储后端（可选，如果为 None 则禁用权限检查）
        """
        self.store = store
    
    async def check_permission(
        self,
        tool: BaseTool,
        args: dict,
        context: ExecutionContext,
    ) -> PermissionDecision:
        """
        检查工具执行权限
        
        Args:
            tool: 工具实例
            args: 工具参数
            context: 执行上下文
        
        Returns:
            PermissionDecision: 权限决策
        """
        # 如果未配置权限存储，默认允许
        if not self.store:
            return PermissionDecision.ALLOWED
        
        # 如果没有 user_id，无法检查权限，需要授权
        if not context.user_id:
            logger.debug("no_user_id_for_permission_check", tool_name=tool.get_name())
            return PermissionDecision.NEEDS_AUTH
        
        # 1. 生成权限资源标识符
        resource = self._generate_resource(tool, args)
        
        # 2. 查询历史授权记录
        decision = await self.store.check_permission(
            user_id=context.user_id,
            resource=resource,
        )
        
        if decision != PermissionDecision.NEEDS_AUTH:
            logger.debug(
                "permission_check_result",
                tool_name=tool.get_name(),
                resource=resource,
                decision=decision.value,
            )
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
        
        如果工具实现了 get_permission_resource 方法，使用工具的自定义逻辑。
        否则使用参数的字符串表示。
        """
        tool_name = tool.get_name()
        
        if hasattr(tool, 'get_permission_resource'):
            arg_pattern = tool.get_permission_resource(args)
        else:
            # 默认使用参数的字符串表示
            arg_pattern = str(args)
        
        return f"{tool_name}({arg_pattern})"
    
    async def create_auth_request(
        self,
        tool: BaseTool,
        args: dict,
        tool_call_id: str,
        context: ExecutionContext,
    ) -> InteractionRequest:
        """
        创建授权请求
        
        Args:
            tool: 工具实例
            args: 工具参数
            tool_call_id: 工具调用 ID
            context: 执行上下文
        
        Returns:
            InteractionRequest: 交互请求
        """
        resource = self._generate_resource(tool, args)
        desc = f"Execute {tool.get_name()}"
        if resource:
            desc += f" on {resource}"
        
        return InteractionRequest(
            type=InteractionType.CONFIRM,
            title="Authorization Required",
            description=f"Do you want to allow: {desc}?",
            tool_call_id=tool_call_id,
            run_id=context.run_id,
            session_id=context.session_id,
            tool_name=tool.get_name(),
            tool_args=args,
            metadata={
                "resource": resource,
            },
        )
    
    async def save_permission_from_response(
        self,
        interaction_request: InteractionRequest,
        interaction_response: "InteractionResponse",
        context: ExecutionContext,
    ) -> None:
        """
        从交互响应保存权限记录
        
        Args:
            interaction_request: 交互请求
            interaction_response: 交互响应
            context: 执行上下文
        """
        if not self.store or not context.user_id:
            return
        
        if interaction_request.type != InteractionType.CONFIRM:
            return
        
        if not interaction_response.confirmed:
            return
        
        resource = interaction_request.metadata.get("resource")
        if resource:
            await self.store.save_permission(
                user_id=context.user_id,
                resource=resource,
                allowed=True,
            )
            logger.info(
                "permission_saved",
                user_id=context.user_id,
                resource=resource,
            )
```

### 2.6 配置系统扩展

#### PermissionStoreConfig

```python
# agio/config/schema.py (添加)

class PermissionStoreConfig(ComponentConfig):
    """Configuration for permission store components"""
    
    type: Literal["permission_store"] = "permission_store"
    store_type: str  # "mongodb", "inmemory"
    
    # MongoDB specific
    mongo_uri: str | None = None
    mongo_db_name: str | None = None
    
    # Params for future extensibility
    params: dict = Field(default_factory=dict)
```

#### PermissionStoreBuilder

```python
# agio/config/builders.py (添加)

class PermissionStoreBuilder(ComponentBuilder):
    """Builder for permission store components"""
    
    async def build(
        self, config: PermissionStoreConfig, dependencies: dict[str, Any]
    ) -> Any:
        """Build permission store instance"""
        try:
            if config.store_type == "mongodb":
                from agio.providers.storage.permissions import MongoPermissionStore
                
                store = MongoPermissionStore(
                    mongo_uri=config.mongo_uri or "mongodb://localhost:27017",
                    db_name=config.mongo_db_name or "agio",
                )
                
                await store.initialize()
                return store
            
            elif config.store_type == "inmemory":
                from agio.providers.storage.permissions import InMemoryPermissionStore
                
                return InMemoryPermissionStore()
            
            else:
                raise ComponentBuildError(
                    f"Unknown permission store type: {config.store_type}"
                )
        
        except Exception as e:
            raise ComponentBuildError(
                f"Failed to build permission_store {config.name}: {e}"
            )
```

#### 更新 ConfigSystem

```python
# agio/config/system.py (修改)

class ConfigSystem:
    # ... 现有代码 ...
    
    # 添加 PermissionStore 到组件类型
    TYPE_PRIORITY = {
        ComponentType.MODEL: 0,
        ComponentType.SESSION_STORE: 0,
        ComponentType.TRACE_STORE: 0,
        ComponentType.PERMISSION_STORE: 0,  # 新增
        ComponentType.MEMORY: 1,
        ComponentType.KNOWLEDGE: 1,
        ComponentType.TOOL: 2,
        ComponentType.AGENT: 3,
        ComponentType.WORKFLOW: 3,
    }
    
    CONFIG_CLASSES = {
        ComponentType.MODEL: ModelConfig,
        ComponentType.TOOL: ToolConfig,
        ComponentType.MEMORY: MemoryConfig,
        ComponentType.KNOWLEDGE: KnowledgeConfig,
        ComponentType.SESSION_STORE: SessionStoreConfig,
        ComponentType.TRACE_STORE: TraceStoreConfig,
        ComponentType.PERMISSION_STORE: PermissionStoreConfig,  # 新增
        ComponentType.AGENT: AgentConfig,
        ComponentType.WORKFLOW: WorkflowConfig,
    }
    
    def __init__(self):
        # ... 现有代码 ...
        
        # 添加 PermissionStoreBuilder
        from agio.config.builders import PermissionStoreBuilder
        self._builders[ComponentType.PERMISSION_STORE] = PermissionStoreBuilder()
```

#### AgentConfig 扩展

```python
# agio/config/schema.py (修改 AgentConfig)

class AgentConfig(ComponentConfig):
    """Configuration for agent components"""
    
    type: Literal["agent"] = "agent"
    model: str
    tools: list[ToolReference] = Field(default_factory=list)
    memory: str | None = None
    knowledge: str | None = None
    session_store: str | None = None
    trace_store: str | None = None
    permission_store: str | None = None  # 新增：权限存储引用
    
    system_prompt: str | None = None
    max_steps: int = 10
    enable_memory_update: bool = False
    user_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    
    # HITL 和权限配置
    enable_hitl: bool = Field(default=True, description="启用 HITL")
    enable_permissions: bool = Field(default=True, description="启用权限系统")
```

#### AgentBuilder 修改

```python
# agio/config/builders.py (修改 AgentBuilder)

class AgentBuilder(ComponentBuilder):
    async def build(
        self, config: AgentConfig, dependencies: dict[str, Any]
    ) -> Any:
        """Build agent instance"""
        from agio.agent import Agent
        
        # ... 现有代码 ...
        
        # 构建 PermissionManager（如果配置了权限存储）
        permission_manager = None
        if config.enable_permissions and config.permission_store:
            permission_store = dependencies.get(config.permission_store)
            if permission_store:
                from agio.runtime.permissions import PermissionManager
                permission_manager = PermissionManager(store=permission_store)
        
        # 创建 Agent（需要修改 Agent.__init__ 接受 permission_manager）
        agent = Agent(
            model=model,
            tools=tools,
            memory=memory,
            knowledge=knowledge,
            session_store=session_store,
            name=config.name,
            user_id=config.user_id,
            system_prompt=config.system_prompt,
            permission_manager=permission_manager,  # 新增
        )
        
        return agent
```

### 2.7 ToolExecutor 修改

```python
# agio/runtime/tool_executor.py (修改)

from typing import Any, Optional
from agio.domain import ToolResult
from agio.runtime.tool_cache import get_tool_cache
from agio.runtime.permissions import PermissionManager, PermissionDecision
from agio.runtime.exceptions import SuspendExecution
from agio.utils.logging import get_logger
from agio.providers.tools import BaseTool
from agio.runtime.control import AbortSignal
from agio.domain import ExecutionContext
from agio.runtime.tool_cache import ToolResultCache
    

logger = get_logger(__name__)


class ToolExecutor:
    """Unified tool executor that returns ToolResult directly."""
    
    def __init__(
        self,
        tools: list["BaseTool"],
        cache: "ToolResultCache | None" = None,
        permission_manager: Optional[PermissionManager] = None,
    ):
        """
        Initialize tool executor.
        
        Args:
            tools: List of tools (BaseTool only)
            cache: Optional cache for expensive tool results
            permission_manager: Optional permission manager for permission checks
        """
        self.tools_map = {t.name: t for t in tools}
        self._cache = cache or get_tool_cache()
        self._permission_manager = permission_manager
    
    async def execute(
        self,
        tool_call: dict[str, Any],
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """
        Execute a single tool call.
        
        Args:
            tool_call: OpenAI format tool call
            context: Execution context
            abort_signal: Abort signal
        
        Returns:
            ToolResult: Tool execution result
        
        Raises:
            SuspendExecution: If execution needs user interaction
        """
        fn_name = tool_call.get("function", {}).get("name")
        fn_args_str = tool_call.get("function", {}).get("arguments", "{}")
        call_id = tool_call.get("id")
        start_time = time.time()
        
        # ... 前面的验证和参数解析代码 ...
        
        args["tool_call_id"] = call_id
        
        # Inject context information
        args["_wire"] = context.wire
        args["_parent_run_id"] = context.run_id
        args["_trace_id"] = context.trace_id
        args["_parent_span_id"] = context.span_id
        args["_depth"] = context.depth
        args["_execution_context"] = context
        
        # Check cache for cacheable tools
        session_id = context.session_id
        if session_id and tool.cacheable:
            cached = self._cache.get(session_id, fn_name, args)
            if cached is not None:
                return ToolResult(
                    tool_name=cached.tool_name,
                    tool_call_id=call_id,
                    input_args=cached.input_args,
                    content=cached.content,
                    output=cached.output,
                    error=cached.error,
                    start_time=start_time,
                    end_time=time.time(),
                    duration=0.0,
                    is_success=cached.is_success,
                )
        
        # 权限检查
        if self._permission_manager:
            decision = await self._permission_manager.check_permission(
                tool, args, context
            )
            
            if decision == PermissionDecision.DENIED:
                return self._create_error_result(
                    call_id=call_id,
                    tool_name=fn_name,
                    error=f"Permission denied for tool {fn_name}",
                    start_time=start_time,
                )
            elif decision == PermissionDecision.NEEDS_AUTH:
                # 创建授权请求并暂停执行
                request = await self._permission_manager.create_auth_request(
                    tool=tool,
                    args=args,
                    tool_call_id=call_id,
                    context=context,
                )
                raise SuspendExecution(request)
        
        # 执行工具
        try:
            logger.debug("executing_tool", tool_name=fn_name, tool_call_id=call_id)
            result: ToolResult = await tool.execute(args, abort_signal=abort_signal)
            logger.debug(
                "tool_execution_completed",
                tool_name=fn_name,
                success=result.is_success,
                duration=result.duration,
            )
            
            # Cache successful results
            if session_id and tool.cacheable and result.is_success:
                self._cache.set(session_id, fn_name, args, result)
            
            return result
        
        except SuspendExecution:
            # 重新抛出，让上层处理
            raise
        
        except asyncio.CancelledError:
            logger.info("tool_execution_cancelled", tool_name=fn_name)
            return self._create_error_result(
                call_id=call_id,
                tool_name=fn_name,
                error="Tool execution was cancelled",
                start_time=start_time,
            )
        
        except Exception as e:
            logger.error(
                "tool_execution_exception",
                tool_name=fn_name,
                error=str(e),
                exc_info=True,
            )
            return self._create_error_result(
                call_id=call_id,
                tool_name=fn_name,
                error=f"Tool execution failed: {e}",
                start_time=start_time,
            )
    
    # ... execute_batch 和 _create_error_result 方法保持不变 ...
```

### 2.8 StepExecutor 修改

```python
# agio/runtime/executor.py (修改)

# 在文件顶部添加导入
from agio.runtime.exceptions import SuspendExecution
from agio.runtime.permissions import PermissionManager

# 修改 StepExecutor.__init__
class StepExecutor:
    def __init__(
        self,
        model: "Model",
        tools: list["BaseTool"],
        config: "ExecutionConfig | None" = None,
        permission_manager: Optional[PermissionManager] = None,
    ):
        """
        Initialize Executor.
        
        Args:
            model: LLM Model instance
            tools: Available tools list
            config: Execution config
            permission_manager: Optional permission manager
        """
        self.model = model
        self.tools = tools
        self.tool_executor = ToolExecutor(
            tools=tools,
            permission_manager=permission_manager,
        )
        
        from agio.config import ExecutionConfig
        self.config = config or ExecutionConfig()
    
    # ... execute 方法中处理 SuspendExecution ...
    async def execute(
        self,
        messages: list[dict],
        ctx: "ExecutionContext",
        *,
        start_sequence: int = 1,
        pending_tool_calls: list[dict] | None = None,
        abort_signal: "AbortSignal | None" = None,
    ) -> AsyncIterator[StepEvent]:
        """
        Execute LLM Call Loop, yield StepEvent stream.
        
        Yields:
            StepEvent: Step event stream
        
        Raises:
            SuspendExecution: If execution needs user interaction
        """
        from agio.runtime.event_factory import EventFactory
        
        ef = EventFactory(ctx)
        current_step = 0
        current_sequence = start_sequence
        
        # ... 现有代码 ...
        
        try:
            # 执行工具调用
            async for event, new_seq in self._execute_tool_calls(
                final_tool_calls,
                ctx,
                current_sequence,
                messages,
                abort_signal,
            ):
                current_sequence = new_seq
                yield event
        
        except SuspendExecution as e:
            # 发送交互请求事件
            yield ef.interaction_request(e.interaction_request)
            # 重新抛出，让 StepRunner 处理
            raise
```

### 2.9 Agent 和 StepRunner 修改

```python
# agio/agent.py (修改)

class Agent:
    def __init__(
        self,
        model: Model,
        tools: list[BaseTool] | None = None,
        memory=None,
        knowledge=None,
        session_store=None,
        name: str = "agio_agent",
        user_id: str | None = None,
        system_prompt: str | None = None,
        permission_manager=None,  # 新增
    ):
        self._id = name
        self.model = model
        self.tools = tools or []
        self.memory = memory
        self.knowledge = knowledge
        self.session_store: SessionStore = session_store
        self.user_id = user_id
        self.system_prompt = system_prompt
        self.permission_manager = permission_manager  # 新增
    
    # ... run 方法中传递 permission_manager 到 StepRunner ...
    async def run(
        self,
        input: str,
        *,
        context: "ExecutionContext",
    ) -> "RunOutput":
        from agio.config import ExecutionConfig
        from agio.runtime import StepRunner
        
        session_id = context.session_id
        current_user_id = context.user_id or self.user_id
        
        session = AgentSession(session_id=session_id, user_id=current_user_id)
        
        runner = StepRunner(
            agent=self,
            config=ExecutionConfig(),
            session_store=self.session_store,
            permission_manager=self.permission_manager,  # 新增
        )
        
        return await runner.run(session, input, context.wire, context=context)
```

```python
# agio/runtime/runner.py (修改)

class StepRunner:
    def __init__(
        self,
        agent: "Agent",
        config: "ExecutionConfig | None" = None,
        session_store: "SessionStore | None" = None,
        permission_manager=None,  # 新增
    ):
        """
        Initialize Runner.
        
        Args:
            agent: Agent instance
            config: Run configuration
            session_store: SessionStore for saving steps
            permission_manager: Optional permission manager
        """
        self.agent = agent
        self.session_store = session_store
        self.permission_manager = permission_manager  # 新增
        
        from agio.config import ExecutionConfig
        self.config = config or ExecutionConfig()
    
    async def run(
        self,
        session: AgentSession,
        query: str,
        wire: Wire,
        abort_signal: AbortSignal | None = None,
        context: "RunContext | None" = None,
    ) -> "RunOutput":
        # ... 现有代码 ...
        
        # 创建 StepExecutor 时传递 permission_manager
        executor = StepExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=self.config,
            permission_manager=self.permission_manager,  # 新增
        )
        
        try:
            async for event in executor.execute(...):
                await wire.write(event)
                # ... 处理事件 ...
        
        except SuspendExecution as e:
            # 处理暂停
            interaction_request = e.interaction_request
            
            # 发送交互请求事件（已经在 executor 中发送，这里可以再次确认）
            # 或者移除 executor 中的发送，统一在这里发送
            
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
        
        # ... 其他异常处理 ...
```

---

## 第三部分：事件系统扩展和恢复执行机制

### 3.1 StepEvent 扩展

```python
# agio/domain/events.py (修改)

class StepEventType(str, Enum):
    """Event types for Step-based streaming"""
    
    # Step-level events
    STEP_DELTA = "step_delta"
    STEP_COMPLETED = "step_completed"
    
    # Run-level events
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    
    # Workflow events
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_SKIPPED = "stage_skipped"
    ITERATION_STARTED = "iteration_started"
    BRANCH_STARTED = "branch_started"
    BRANCH_COMPLETED = "branch_completed"
    
    # HITL events (新增)
    INTERACTION_REQUEST = "interaction_request"  # 交互请求
    INTERACTION_RESPONSE = "interaction_response"  # 交互响应（用于日志）
    EXECUTION_SUSPENDED = "execution_suspended"  # 执行暂停
    EXECUTION_RESUMED = "execution_resumed"  # 执行恢复
    
    # Error events
    ERROR = "error"
```

### 3.2 EventFactory 扩展

```python
# agio/runtime/event_factory.py (修改)

from agio.domain.interaction import InteractionRequest
from agio.domain.events import StepEvent, StepEventType

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
    
    def execution_resumed(
        self,
        interaction_request_id: str,
    ) -> StepEvent:
        """创建执行恢复事件"""
        return StepEvent(
            type=StepEventType.EXECUTION_RESUMED,
            run_id=self.ctx.run_id,
            data={
                "interaction_request_id": interaction_request_id,
            },
        )
```

### 3.3 恢复执行机制

恢复执行的关键思路：
1. 不需要保存整个执行状态
2. 只需要保存交互请求（包含 tool_call_id、tool_name、tool_args）
3. 恢复时，重新执行工具调用（此时权限已通过）
4. 工具执行结果通过 Wire 发送，继续后续流程

#### 交互请求存储（简化版）

```python
# agio/providers/storage/base.py (扩展 SessionStore)

class SessionStore(ABC):
    # ... 现有方法 ...
    
    @abstractmethod
    async def save_interaction_request(
        self,
        interaction_request: "InteractionRequest",
    ) -> None:
        """保存交互请求（用于恢复执行）"""
        pass
    
    @abstractmethod
    async def get_interaction_request(
        self,
        interaction_id: str,
    ) -> "InteractionRequest | None":
        """获取交互请求"""
        pass
    
    @abstractmethod
    async def save_interaction_response(
        self,
        response: "InteractionResponse",
    ) -> None:
        """保存交互响应"""
        pass
```

#### MongoDB 实现

```python
# agio/providers/storage/mongo.py (扩展)

class MongoSessionStore(SessionStore):
    # ... 现有代码 ...
    
    async def _ensure_connection(self):
        # ... 现有代码 ...
        self.interaction_requests_collection = self.db["interaction_requests"]
        self.interaction_responses_collection = self.db["interaction_responses"]
        
        # 创建索引
        await self.interaction_requests_collection.create_index("id", unique=True)
        await self.interaction_requests_collection.create_index("run_id")
        await self.interaction_requests_collection.create_index("tool_call_id")
        await self.interaction_responses_collection.create_index("request_id")
    
    async def save_interaction_request(
        self,
        interaction_request: "InteractionRequest",
    ) -> None:
        """保存交互请求"""
        await self._ensure_connection()
        doc = interaction_request.model_dump(mode="json")
        await self.interaction_requests_collection.replace_one(
            {"id": interaction_request.id},
            doc,
            upsert=True,
        )
    
    async def get_interaction_request(
        self,
        interaction_id: str,
    ) -> "InteractionRequest | None":
        """获取交互请求"""
        await self._ensure_connection()
        doc = await self.interaction_requests_collection.find_one({"id": interaction_id})
        if doc:
            from agio.domain.interaction import InteractionRequest
            return InteractionRequest(**doc)
        return None
    
    async def save_interaction_response(
        self,
        response: "InteractionResponse",
    ) -> None:
        """保存交互响应"""
        await self._ensure_connection()
        doc = response.model_dump(mode="json")
        await self.interaction_responses_collection.insert_one(doc)
```

#### StepRunner 恢复方法

```python
# agio/runtime/runner.py (新增方法)

async def resume_from_interaction(
    self,
    interaction_id: str,
    interaction_response: "InteractionResponse",
    wire: Wire,
) -> "RunOutput":
    """
    从交互响应恢复执行
    
    流程：
    1. 加载交互请求
    2. 处理交互响应（保存权限记录等）
    3. 重新执行工具调用
    4. 继续后续执行流程
    
    Args:
        interaction_id: 交互请求 ID
        interaction_response: 交互响应
        wire: Wire 用于事件流
    
    Returns:
        RunOutput: 执行结果
    """
    from agio.domain.interaction import InteractionRequest, InteractionType
    from agio.domain.protocol import RunOutput, RunMetrics
    from agio.domain import RunStatus
    
    # 1. 加载交互请求
    if not self.session_store:
        raise ValueError("SessionStore required for resume")
    
    interaction_request = await self.session_store.get_interaction_request(interaction_id)
    if not interaction_request:
        raise ValueError(f"Interaction request {interaction_id} not found")
    
    # 验证响应匹配请求
    if interaction_response.request_id != interaction_id:
        raise ValueError("Interaction response does not match request")
    
    # 2. 处理交互响应
    if interaction_request.type == InteractionType.CONFIRM:
        # 如果用户拒绝，返回错误
        if not interaction_response.confirmed:
            run = await self.session_store.get_run(interaction_request.run_id)
            if run:
                run.status = RunStatus.FAILED
                await self.session_store.save_run(run)
            
            from agio.runtime.event_factory import EventFactory
            exec_ctx = ExecutionContext(
                run_id=interaction_request.run_id,
                session_id=interaction_request.session_id,
                wire=wire,
            )
            ef = EventFactory(exec_ctx)
            
            await wire.write(
                ef.run_failed(error="Permission denied by user")
            )
            return RunOutput(
                run_id=interaction_request.run_id,
                error="Permission denied by user",
            )
        
        # 保存权限记录
        if self.permission_manager:
            exec_ctx = ExecutionContext(
                run_id=interaction_request.run_id,
                session_id=interaction_request.session_id,
                wire=wire,
            )
            await self.permission_manager.save_permission_from_response(
                interaction_request,
                interaction_response,
                exec_ctx,
            )
    
    # 保存交互响应
    await self.session_store.save_interaction_response(interaction_response)
    
    # 3. 重新执行工具调用
    # 构建工具调用对象
    tool_call = {
        "id": interaction_request.tool_call_id,
        "type": "function",
        "function": {
            "name": interaction_request.tool_name,
            "arguments": json.dumps(interaction_request.tool_args),
        },
    }
    
    # 创建执行上下文
    exec_ctx = ExecutionContext(
        run_id=interaction_request.run_id,
        session_id=interaction_request.session_id,
        wire=wire,
    )
    
    # 创建 EventFactory
    from agio.runtime.event_factory import EventFactory
    ef = EventFactory(exec_ctx)
    
    # 发送恢复事件
    await wire.write(
        ef.execution_resumed(interaction_id)
    )
    
    # 执行工具调用（这次应该通过权限检查）
    executor = StepExecutor(
        model=self.agent.model,
        tools=self.agent.tools or [],
        config=self.config,
        permission_manager=self.permission_manager,
    )
    
    tool_result = await executor.tool_executor.execute(
        tool_call,
        context=exec_ctx,
    )
    
    # 4. 创建工具结果 Step
    from agio.domain.models import Step, MessageRole, StepMetrics
    from uuid import uuid4
    
    tool_step = Step(
        id=str(uuid4()),
        session_id=interaction_request.session_id,
        run_id=interaction_request.run_id,
        sequence=await self._get_next_sequence(interaction_request.session_id),
        role=MessageRole.TOOL,
        content=tool_result.content,
        tool_call_id=tool_result.tool_call_id,
        name=tool_result.tool_name,
        metrics=StepMetrics(
            duration_ms=tool_result.duration * 1000 if tool_result.duration else None,
        ),
    )
    
    await self.session_store.save_step(tool_step)
    await wire.write(ef.step_completed(tool_step.id, tool_step))
    
    # 5. 继续后续执行流程
    # 重新构建 messages 上下文
    from agio.runtime.context import build_context_from_steps
    from agio.domain.adapters import StepAdapter
    
    messages = await build_context_from_steps(
        interaction_request.session_id,
        self.session_store,
        system_prompt=self.agent.system_prompt,
    )
    
    # 添加工具结果到 messages
    messages.append(StepAdapter.to_llm_message(tool_step))
    
    # 继续执行
    start_sequence = tool_step.sequence + 1
    
    try:
        async for event in executor.execute(
            messages=messages,
            ctx=exec_ctx,
            start_sequence=start_sequence,
        ):
            await wire.write(event)
            if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
                await self.session_store.save_step(event.snapshot)
        
        # 6. 完成执行
        run = await self.session_store.get_run(interaction_request.run_id)
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
            run_id=interaction_request.run_id,
            session_id=interaction_request.session_id,
            response="Execution resumed and completed",
        )
    
    except SuspendExecution as e:
        # 如果再次暂停，继续处理
        await wire.write(ef.interaction_request(e.interaction_request))
        run = await self.session_store.get_run(interaction_request.run_id)
        if run:
            run.status = RunStatus.SUSPENDED
            await self.session_store.save_run(run)
        
        return RunOutput(
            run_id=interaction_request.run_id,
            session_id=interaction_request.session_id,
            status="suspended",
            interaction_request_id=e.interaction_request.id,
        )
```

### 3.4 StepRunner.run 中保存交互请求

```python
# agio/runtime/runner.py (修改 run 方法)

async def run(
    self,
    session: AgentSession,
    query: str,
    wire: Wire,
    abort_signal: AbortSignal | None = None,
    context: "RunContext | None" = None,
) -> "RunOutput":
    # ... 现有代码 ...
    
    try:
        async for event in executor.execute(...):
            await wire.write(event)
            # ... 处理事件 ...
    
    except SuspendExecution as e:
        # 处理暂停
        interaction_request = e.interaction_request
        
        # 保存交互请求（用于恢复）
        if self.session_store:
            await self.session_store.save_interaction_request(interaction_request)
        
        # 发送执行暂停事件
        await wire.write(
            ef.execution_suspended(interaction_request.id)
        )
        
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
    
    # ... 其他异常处理 ...
```

---

## 第四部分：API 端点和前端集成

### 4.1 交互响应 API

```python
# agio/api/routes/interactions.py (新建)

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agio.domain.interaction import InteractionResponse
from agio.config import ConfigSystem, get_config_system
from agio.providers.storage.base import SessionStore, get_session_store
from agio.runtime import Wire
from agio.domain import ExecutionContext
from agio.utils.logging import get_logger

logger = get_logger(__name__)

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
    # 1. 加载交互请求
    interaction_request = await session_store.get_interaction_request(interaction_id)
    if not interaction_request:
        raise HTTPException(404, f"Interaction {interaction_id} not found or expired")
    
    # 2. 验证响应匹配请求
    if response.request_id != interaction_id:
        raise HTTPException(400, "Response request_id does not match interaction_id")
    
    # 3. 获取 Agent（通过 run_id 找到对应的 Agent）
    from agio.domain import AgentRun
    run = await session_store.get_run(interaction_request.run_id)
    if not run:
        raise HTTPException(404, f"Run {interaction_request.run_id} not found")
    
    agent = config_system.get_instance(run.agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {run.agent_id} not found")
    
    # 4. 恢复执行
    async def event_generator():
        wire = Wire()
        
        async def _resume():
            from agio.config import ExecutionConfig
            from agio.runtime import StepRunner
            
            runner = StepRunner(
                agent=agent,
                config=ExecutionConfig(),
                session_store=session_store,
                permission_manager=getattr(agent, 'permission_manager', None),
            )
            
            try:
                await runner.resume_from_interaction(
                    interaction_id=interaction_id,
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
        except Exception as e:
            logger.error("resume_execution_error", error=str(e), exc_info=True)
            yield {
                "event": "error",
                "data": f'{{"error": "{str(e)}"}}',
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
    interaction_request = await session_store.get_interaction_request(interaction_id)
    if not interaction_request:
        raise HTTPException(404, f"Interaction {interaction_id} not found")
    return {
        "interaction_request": interaction_request.model_dump(mode="json"),
        "run_id": interaction_request.run_id,
    }
```

### 4.2 权限管理 API

```python
# agio/api/routes/permissions.py (新建)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agio.runtime.permissions import PermissionManager, get_permission_manager
from agio.providers.storage.permissions import PermissionStore, get_permission_store
from agio.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/permissions")


class PermissionResource(BaseModel):
    """权限资源"""
    resource: str


@router.get("/{user_id}")
async def get_user_permissions(
    user_id: str,
    permission_store: PermissionStore = Depends(get_permission_store),
):
    """获取用户权限配置"""
    permissions = await permission_store.get_user_permissions(user_id)
    return permissions


@router.post("/{user_id}/allow")
async def add_permission(
    user_id: str,
    resource_data: PermissionResource,
    permission_store: PermissionStore = Depends(get_permission_store),
):
    """添加允许权限"""
    await permission_store.save_permission(
        user_id=user_id,
        resource=resource_data.resource,
        allowed=True,
    )
    return {"status": "ok", "message": f"Permission allowed: {resource_data.resource}"}


@router.post("/{user_id}/deny")
async def deny_permission(
    user_id: str,
    resource_data: PermissionResource,
    permission_store: PermissionStore = Depends(get_permission_store),
):
    """添加拒绝权限"""
    await permission_store.save_permission(
        user_id=user_id,
        resource=resource_data.resource,
        allowed=False,
    )
    return {"status": "ok", "message": f"Permission denied: {resource_data.resource}"}
```

### 4.3 前端组件设计

#### TypeScript 类型定义

```typescript
// agio-frontend/src/types/interaction.ts

export enum InteractionType {
  INPUT = "input",
  SELECT = "select",
  CONFIRM = "confirm",
  COMBINED = "combined",
}

export interface SelectOption {
  value: string;
  label: string;
  description?: string;
}

export interface InteractionRequest {
  id: string;
  type: InteractionType;
  title: string;
  description?: string;
  placeholder?: string;
  required?: boolean;
  multiline?: boolean;
  options?: SelectOption[];
  multiple?: boolean;
  confirm_text?: string;
  cancel_text?: string;
  interactions?: InteractionRequest[];
  run_id: string;
  session_id: string;
  step_id?: string;
  tool_call_id: string;
  tool_name: string;
  tool_args: Record<string, any>;
  metadata: Record<string, any>;
  created_at: string;
  expires_at?: string;
}

export interface InteractionResponse {
  request_id: string;
  type: InteractionType;
  text?: string;
  selected_values?: string[];
  confirmed?: boolean;
  responses?: InteractionResponse[];
  responded_at: string;
  user_id?: string;
}
```

#### Chat 界面集成示例

```typescript
// agio-frontend/src/pages/Chat.tsx (修改)

import { useState } from 'react';
import { InteractionRequest, InteractionResponse } from '@/types/interaction';
import { InteractionRequestComponent } from '@/components/interaction/InteractionRequest';
import { StepEvent } from '@/types/events';

export default function Chat() {
  const [pendingInteraction, setPendingInteraction] = useState<InteractionRequest | null>(null);
  
  const { events, sendMessage } = useSSEStream({
    onEvent: (event: StepEvent) => {
      if (event.type === 'interaction_request') {
        const request = event.data.interaction_request as InteractionRequest;
        setPendingInteraction(request);
      }
    },
  });
  
  const handleInteractionResponse = async (response: InteractionResponse) => {
    try {
      const res = await fetch(`/api/interactions/${response.request_id}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(response),
      });
      
      if (!res.ok) {
        throw new Error('Failed to submit interaction response');
      }
      
      setPendingInteraction(null);
    } catch (error) {
      console.error('Error submitting interaction response:', error);
    }
  };
  
  return (
    <div className="chat-container">
      <div className="messages">
        {/* ... 现有消息渲染 ... */}
      </div>
      
      {pendingInteraction && (
        <div className="interaction-overlay">
          <div className="interaction-modal">
            <InteractionRequestComponent
              request={pendingInteraction}
              onResponse={handleInteractionResponse}
            />
          </div>
        </div>
      )}
      
      <MessageInput onSend={sendMessage} />
    </div>
  );
}
```

### 4.4 配置示例

```yaml
# configs/permission_stores/mongodb.yaml
type: permission_store
name: mongodb_permission_store
store_type: mongodb
mongo_uri: mongodb://localhost:27017
mongo_db_name: agio

# configs/agents/code_assistant.yaml
type: agent
name: code_assistant
model: gpt4_model
tools:
  - file_read
  - file_write
  - bash
permission_store: mongodb_permission_store
enable_hitl: true
enable_permissions: true
```

---

## 总结

### 关键改进点

1. **简化状态管理**：不使用 SuspendedState，只保存交互请求
2. **配置系统集成**：PermissionManager 通过配置系统构建和注入
3. **统一导入**：所有导入在文件顶部，不使用局部导入
4. **恢复机制简化**：恢复时重新执行工具调用，不需要重建整个执行上下文

### 实现步骤

1. ✅ 实现核心数据模型（InteractionRequest/Response）
2. ✅ 实现权限存储接口和 MongoDB 实现
3. ✅ 实现 PermissionManager
4. ✅ 扩展配置系统支持 PermissionStore
5. ✅ 修改 ToolExecutor 集成权限检查
6. ✅ 修改 StepRunner 处理暂停和恢复
7. ✅ 扩展事件系统支持新事件类型
8. ✅ 实现 API 端点
9. ✅ 实现前端组件

### 注意事项

1. **嵌套执行**：暂停发生在工具调用层面，恢复时只恢复工具调用，不影响嵌套的 Agent/Workflow
2. **权限缓存**：可以考虑添加权限查询结果的缓存以提高性能
3. **超时处理**：交互请求有过期时间，需要在前端和后端都处理超时情况
4. **向后兼容**：现有工具和 Agent 在没有配置权限的情况下应该正常工作（默认允许或需要授权，可配置）
