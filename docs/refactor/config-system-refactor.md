# 配置系统重构方案

> **重构目标**: 解决配置系统中的职责混乱、代码重复、扩展性差等问题，构建清晰简洁优雅的架构

## 一、现状分析

### 1.1 核心问题

| 问题 | 严重程度 | 当前影响 |
|------|---------|---------|
| ConfigSystem 职责过重（780行） | 🔴 高 | 难以维护、测试困难 |
| 拓扑排序逻辑重复 | 🟡 中 | 代码冗余、一致性风险 |
| 全局单例无法重置 | 🟡 中 | 测试困难、多配置场景不支持 |
| Builder 硬编码 Provider | 🟡 中 | 每次添加新 Provider 需修改代码 |
| 循环依赖只 warning | 🔴 高 | 运行时可能崩溃 |
| 依赖解析逻辑分散 | 🟡 中 | 维护成本高、逻辑不一致 |
| Schema 与配置不匹配 | 🟡 中 | 字段被静默忽略 |

### 1.2 当前架构

```
ConfigSystem (780 lines)
├── 配置存储 (_configs: dict)
├── 实例管理 (_instances: dict)
├── 元数据管理 (_metadata: dict)
├── 构建器管理 (_builders: dict)
├── 依赖解析 (_resolve_dependencies)
├── 拓扑排序 (_get_topological_build_order)
├── 热重载 (_handle_config_change)
├── Tool 引用解析 (_resolve_tool_reference)
└── RunnableTool 创建 (_create_runnable_tool)
```

**问题**: 单一类承担了 9+ 职责，违反 SRP（单一职责原则）

---

## 二、重构方案

### 2.1 架构设计

#### 核心原则
- **职责分离**: 每个模块只做一件事
- **依赖倒置**: 依赖抽象而非具体实现
- **开闭原则**: 对扩展开放，对修改关闭
- **组合优于继承**: 使用组合构建系统

#### 新架构

```
┌─────────────────────────────────────────────────────┐
│                   ConfigSystem                      │
│  (门面/协调者 - 精简到 < 300 lines)                   │
└─────────────────────────────────────────────────────┘
           │
           ├──> ConfigRegistry (配置存储)
           │      - 存储/查询配置
           │      - 配置验证（Pydantic）
           │
           ├──> ComponentContainer (实例管理)
           │      - 实例缓存
           │      - 生命周期管理
           │
           ├──> DependencyResolver (依赖解析)
           │      - 统一的依赖提取
           │      - 拓扑排序
           │      - 循环依赖检测（fail fast）
           │
           ├──> BuilderRegistry (构建器管理)
           │      - 注册/查询 Builder
           │      - 支持动态注册
           │
           └──> HotReloadManager (热重载)
                - 变更检测
                - 级联重建
```

### 2.2 模块拆分

#### 2.2.1 ConfigRegistry - 配置存储

**职责**: 配置的存储、查询、验证

```python
# agio/config/registry.py

class ConfigRegistry:
    """配置注册表 - 负责配置的存储和查询"""
    
    def __init__(self):
        # 使用 Pydantic 模型存储，确保类型安全
        self._configs: dict[tuple[ComponentType, str], ComponentConfig] = {}
    
    def register(self, config: ComponentConfig) -> None:
        """注册配置（自动验证）"""
        key = (ComponentType(config.type), config.name)
        self._configs[key] = config
    
    def get(self, component_type: ComponentType, name: str) -> ComponentConfig | None:
        """获取配置"""
        return self._configs.get((component_type, name))
    
    def list_all(self) -> list[ComponentConfig]:
        """列出所有配置"""
        return list(self._configs.values())
    
    def remove(self, component_type: ComponentType, name: str) -> None:
        """删除配置"""
        key = (component_type, name)
        if key in self._configs:
            del self._configs[key]
```

**改进点**:
- ✅ 存储 Pydantic 模型而非 dict（类型安全）
- ✅ 单一职责
- ✅ 易于测试

---

#### 2.2.2 ComponentContainer - 实例管理

**职责**: 组件实例的缓存和生命周期管理

```python
# agio/config/container.py

class ComponentContainer:
    """组件容器 - 负责实例的存储和生命周期"""
    
    def __init__(self):
        self._instances: dict[str, Any] = {}
        self._metadata: dict[str, ComponentMetadata] = {}
    
    def register(self, name: str, instance: Any, metadata: ComponentMetadata) -> None:
        """注册组件实例"""
        self._instances[name] = instance
        self._metadata[name] = metadata
    
    def get(self, name: str) -> Any:
        """获取组件实例"""
        if name not in self._instances:
            raise ComponentNotFoundError(f"Component '{name}' not found")
        return self._instances[name]
    
    def get_or_none(self, name: str) -> Any | None:
        """获取组件（不存在返回 None）"""
        return self._instances.get(name)
    
    def has(self, name: str) -> bool:
        """检查组件是否存在"""
        return name in self._instances
    
    async def remove(self, name: str, builder_registry: "BuilderRegistry") -> None:
        """移除组件并清理资源"""
        if name not in self._instances:
            return
        
        instance = self._instances.pop(name)
        metadata = self._metadata.pop(name, None)
        
        # 清理资源
        if metadata:
            builder = builder_registry.get(metadata.component_type)
            if builder:
                await builder.cleanup(instance)
    
    def get_metadata(self, name: str) -> ComponentMetadata | None:
        """获取组件元数据"""
        return self._metadata.get(name)
```

**改进点**:
- ✅ 独立的生命周期管理
- ✅ 清晰的接口
- ✅ 元数据与实例分离存储

---

#### 2.2.3 DependencyResolver - 依赖解析

**职责**: 统一的依赖提取、拓扑排序、循环依赖检测

```python
# agio/config/dependency.py

from collections import deque
from dataclasses import dataclass

@dataclass
class DependencyNode:
    """依赖节点"""
    name: str
    component_type: ComponentType
    dependencies: set[str]

class DependencyResolver:
    """依赖解析器 - 统一处理依赖关系"""
    
    def extract_dependencies(self, config: ComponentConfig) -> set[str]:
        """提取配置的依赖（统一入口）"""
        deps = set()
        
        if isinstance(config, AgentConfig):
            deps.update(self._extract_agent_deps(config))
        elif isinstance(config, ToolConfig):
            deps.update(self._extract_tool_deps(config))
        elif isinstance(config, WorkflowConfig):
            deps.update(self._extract_workflow_deps(config))
        
        return deps
    
    def _extract_agent_deps(self, config: AgentConfig) -> set[str]:
        """提取 Agent 依赖"""
        deps = {config.model}
        
        # Tools
        for tool_ref in config.tools:
            from agio.config.tool_reference import parse_tool_reference
            parsed = parse_tool_reference(tool_ref)
            
            if parsed.type == "function" and parsed.name:
                deps.add(parsed.name)
            elif parsed.type == "agent_tool" and parsed.agent:
                deps.add(parsed.agent)
            elif parsed.type == "workflow_tool" and parsed.workflow:
                deps.add(parsed.workflow)
        
        # Optional deps
        if config.memory:
            deps.add(config.memory)
        if config.knowledge:
            deps.add(config.knowledge)
        if config.session_store:
            deps.add(config.session_store)
        
        return deps
    
    def _extract_tool_deps(self, config: ToolConfig) -> set[str]:
        """提取 Tool 依赖"""
        return set(config.effective_dependencies.values())
    
    def _extract_workflow_deps(self, config: WorkflowConfig) -> set[str]:
        """提取 Workflow 依赖（递归处理嵌套）"""
        deps = set()
        
        if config.session_store:
            deps.add(config.session_store)
        
        # 递归提取 stages 中的依赖
        def extract_from_stages(stages: list) -> None:
            for stage in stages:
                runnable = stage.get("runnable") if isinstance(stage, dict) else stage.runnable
                if isinstance(runnable, str):
                    deps.add(runnable)
                elif isinstance(runnable, dict):
                    nested_stages = runnable.get("stages", [])
                    extract_from_stages(nested_stages)
        
        if hasattr(config, 'stages'):
            extract_from_stages([s.model_dump() if hasattr(s, 'model_dump') else s for s in config.stages])
        
        return deps
    
    def topological_sort(
        self, 
        configs: list[ComponentConfig],
        available_names: set[str] | None = None
    ) -> list[ComponentConfig]:
        """
        拓扑排序（Kahn's algorithm）
        
        Args:
            configs: 待排序的配置列表
            available_names: 可用的组件名称集合（用于过滤 built-in 依赖）
        
        Returns:
            排序后的配置列表
            
        Raises:
            ConfigError: 检测到循环依赖
        """
        # 构建依赖图
        nodes = {}
        for config in configs:
            deps = self.extract_dependencies(config)
            
            # 过滤掉不在配置中的依赖（built-in tools 等）
            if available_names:
                deps = deps & available_names
            
            nodes[config.name] = DependencyNode(
                name=config.name,
                component_type=ComponentType(config.type),
                dependencies=deps
            )
        
        # Kahn's algorithm
        in_degree = {name: len(node.dependencies) for name, node in nodes.items()}
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        sorted_names = []
        
        while queue:
            name = queue.popleft()
            sorted_names.append(name)
            
            # 减少依赖此节点的其他节点的入度
            for other_name, node in nodes.items():
                if name in node.dependencies:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        queue.append(other_name)
        
        # 检测循环依赖（fail fast）
        if len(sorted_names) < len(nodes):
            unresolved = set(nodes.keys()) - set(sorted_names)
            raise ConfigError(
                f"Circular dependency detected: {unresolved}. "
                f"Please check the dependency chain in your configuration."
            )
        
        # 按排序后的顺序返回配置
        name_to_config = {config.name: config for config in configs}
        return [name_to_config[name] for name in sorted_names]
```

**改进点**:
- ✅ 统一的依赖提取逻辑（消除重复）
- ✅ 循环依赖 fail fast（而非 warning）
- ✅ 清晰的接口和错误处理

---

#### 2.2.4 BuilderRegistry - 构建器注册表

**职责**: 管理组件构建器，支持动态注册

```python
# agio/config/builder_registry.py

from typing import Protocol

class ComponentBuilder(Protocol):
    """构建器协议"""
    async def build(self, config: ComponentConfig, dependencies: dict[str, Any]) -> Any:
        ...
    
    async def cleanup(self, instance: Any) -> None:
        ...

class BuilderRegistry:
    """构建器注册表 - 支持动态注册"""
    
    def __init__(self):
        self._builders: dict[ComponentType, ComponentBuilder] = {}
        self._register_defaults()
    
    def _register_defaults(self) -> None:
        """注册默认构建器"""
        from agio.config.builders import (
            ModelBuilder, ToolBuilder, MemoryBuilder,
            KnowledgeBuilder, SessionStoreBuilder,
            TraceStoreBuilder, AgentBuilder, WorkflowBuilder
        )
        
        self.register(ComponentType.MODEL, ModelBuilder())
        self.register(ComponentType.TOOL, ToolBuilder())
        self.register(ComponentType.MEMORY, MemoryBuilder())
        self.register(ComponentType.KNOWLEDGE, KnowledgeBuilder())
        self.register(ComponentType.SESSION_STORE, SessionStoreBuilder())
        self.register(ComponentType.TRACE_STORE, TraceStoreBuilder())
        self.register(ComponentType.AGENT, AgentBuilder())
        self.register(ComponentType.WORKFLOW, WorkflowBuilder())
    
    def register(self, component_type: ComponentType, builder: ComponentBuilder) -> None:
        """注册构建器"""
        self._builders[component_type] = builder
    
    def get(self, component_type: ComponentType) -> ComponentBuilder | None:
        """获取构建器"""
        return self._builders.get(component_type)
    
    def has(self, component_type: ComponentType) -> bool:
        """检查构建器是否存在"""
        return component_type in self._builders
```

**改进点**:
- ✅ 支持动态注册（扩展性）
- ✅ 使用 Protocol 定义接口（类型安全）

---

#### 2.2.5 HotReloadManager - 热重载管理

**职责**: 配置变更检测和级联重建

```python
# agio/config/hot_reload.py

from typing import Callable

class HotReloadManager:
    """热重载管理器"""
    
    def __init__(self, container: ComponentContainer, dependency_resolver: DependencyResolver):
        self._container = container
        self._dependency_resolver = dependency_resolver
        self._callbacks: list[Callable[[str, str], None]] = []
    
    def register_callback(self, callback: Callable[[str, str], None]) -> None:
        """注册变更回调"""
        self._callbacks.append(callback)
    
    async def handle_change(
        self, 
        name: str, 
        change_type: str,
        rebuild_func: Callable[[str], Any]
    ) -> None:
        """
        处理配置变更
        
        Args:
            name: 变更的组件名称
            change_type: 变更类型（create/update/delete）
            rebuild_func: 重建函数
        """
        affected = self._get_affected_components(name)
        
        # 逆序销毁
        for comp_name in reversed(affected):
            await self._container.remove(comp_name)
        
        # 正序重建
        for comp_name in affected:
            await rebuild_func(comp_name)
        
        # 通知回调
        self._notify_callbacks(name, change_type)
    
    def _get_affected_components(self, name: str) -> list[str]:
        """获取受影响的组件（BFS 遍历依赖图）"""
        affected = [name]
        queue = [name]
        
        while queue:
            current = queue.pop(0)
            for comp_name in self._container._metadata.keys():
                metadata = self._container.get_metadata(comp_name)
                if metadata and current in metadata.dependencies:
                    if comp_name not in affected:
                        affected.append(comp_name)
                        queue.append(comp_name)
        
        return affected
    
    def _notify_callbacks(self, name: str, change_type: str) -> None:
        """通知变更回调"""
        for callback in self._callbacks:
            try:
                callback(name, change_type)
            except Exception as e:
                logger.error(f"Hot reload callback error: {e}")
```

**改进点**:
- ✅ 独立的热重载逻辑
- ✅ 清晰的变更处理流程

---

#### 2.2.6 ConfigSystem - 门面/协调者

**职责**: 协调各模块，提供统一的外部接口

```python
# agio/config/system.py (重构后 < 300 lines)

class ConfigSystem:
    """
    配置系统门面 - 协调各模块
    
    职责：
    - 协调各模块工作
    - 提供统一的外部接口
    - 处理组件构建流程
    """
    
    def __init__(self):
        self.registry = ConfigRegistry()
        self.container = ComponentContainer()
        self.dependency_resolver = DependencyResolver()
        self.builder_registry = BuilderRegistry()
        self.hot_reload = HotReloadManager(self.container, self.dependency_resolver)
    
    async def load_from_directory(self, config_dir: str | Path) -> dict[str, int]:
        """从目录加载配置"""
        loader = ConfigLoader(config_dir)
        configs_by_type = await loader.load_all_configs()
        
        stats = {"loaded": 0, "failed": 0}
        
        # 扁平化配置列表
        all_configs = []
        for configs in configs_by_type.values():
            all_configs.extend(configs)
        
        # 解析为 Pydantic 模型并注册
        for config_dict in all_configs:
            try:
                config = self._parse_config(config_dict)
                self.registry.register(config)
                stats["loaded"] += 1
            except Exception as e:
                logger.error(f"Failed to parse config: {e}")
                stats["failed"] += 1
        
        return stats
    
    def _parse_config(self, config_dict: dict) -> ComponentConfig:
        """解析配置字典为 Pydantic 模型"""
        component_type = ComponentType(config_dict["type"])
        config_class = self._get_config_class(component_type)
        return config_class(**config_dict)
    
    async def build_all(self) -> dict[str, int]:
        """构建所有组件"""
        configs = self.registry.list_all()
        
        # 拓扑排序
        available_names = {c.name for c in configs}
        sorted_configs = self.dependency_resolver.topological_sort(configs, available_names)
        
        stats = {"built": 0, "failed": 0}
        
        for config in sorted_configs:
            if self.container.has(config.name):
                continue
            
            try:
                await self._build_component(config)
                stats["built"] += 1
            except Exception as e:
                logger.exception(f"Failed to build {config.type}/{config.name}: {e}")
                stats["failed"] += 1
        
        return stats
    
    async def _build_component(self, config: ComponentConfig) -> Any:
        """构建单个组件"""
        # 解析依赖
        dependencies = await self._resolve_dependencies(config)
        
        # 获取构建器
        component_type = ComponentType(config.type)
        builder = self.builder_registry.get(component_type)
        if not builder:
            raise ComponentBuildError(f"No builder for type: {component_type}")
        
        # 构建实例
        instance = await builder.build(config, dependencies)
        
        # 注册到容器
        metadata = ComponentMetadata(
            component_type=component_type,
            config=config,
            dependencies=list(dependencies.keys())
        )
        self.container.register(config.name, instance, metadata)
        
        return instance
    
    async def _resolve_dependencies(self, config: ComponentConfig) -> dict[str, Any]:
        """解析组件依赖（委托给具体方法）"""
        if isinstance(config, AgentConfig):
            return await self._resolve_agent_dependencies(config)
        elif isinstance(config, ToolConfig):
            return await self._resolve_tool_dependencies(config)
        elif isinstance(config, WorkflowConfig):
            return await self._resolve_workflow_dependencies(config)
        return {}
    
    # ... 其他方法简化（委托给各模块）
```

**改进点**:
- ✅ 精简到 < 300 行
- ✅ 清晰的职责（协调者）
- ✅ 委托给专门模块

---

### 2.3 Builder 改进

#### 问题：硬编码的 Provider 分支

**当前代码**:
```python
# builders.py - ModelBuilder
if config.provider == "openai":
    from agio.providers.llm import OpenAIModel
    return OpenAIModel(...)
elif config.provider == "anthropic":
    from agio.providers.llm import AnthropicModel
    return AnthropicModel(...)
```

**重构方案**: Provider 注册表

```python
# agio/providers/llm/registry.py

class ModelProviderRegistry:
    """模型 Provider 注册表"""
    
    def __init__(self):
        self._providers: dict[str, type] = {}
        self._register_defaults()
    
    def _register_defaults(self):
        """注册默认 Provider"""
        from agio.providers.llm import OpenAIModel, AnthropicModel, DeepseekModel
        
        self.register("openai", OpenAIModel)
        self.register("anthropic", AnthropicModel)
        self.register("deepseek", DeepseekModel)
    
    def register(self, provider: str, model_class: type) -> None:
        """注册 Provider"""
        self._providers[provider] = model_class
    
    def get(self, provider: str) -> type | None:
        """获取 Provider 类"""
        return self._providers.get(provider)

# 全局单例
_model_registry = ModelProviderRegistry()

def get_model_registry() -> ModelProviderRegistry:
    return _model_registry
```

**ModelBuilder 改进**:
```python
class ModelBuilder(ComponentBuilder):
    async def build(self, config: ModelConfig, dependencies: dict[str, Any]) -> Any:
        registry = get_model_registry()
        model_class = registry.get(config.provider)
        
        if not model_class:
            raise ComponentBuildError(f"Unknown model provider: {config.provider}")
        
        return model_class(
            id=f"{config.provider}/{config.model_name}",
            name=config.name,
            api_key=config.api_key,
            model_name=config.model_name,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
```

**改进点**:
- ✅ 符合 OCP（开闭原则）
- ✅ 添加新 Provider 无需修改 Builder
- ✅ 支持用户自定义 Provider

---

### 2.4 Schema 改进

#### 2.4.1 统一配置字段验证

**问题**: `hooks`, `description`, `max_tokens` 等字段在配置中使用但 Schema 未定义

**方案**: 完善 Schema 定义

```python
# agio/config/schema.py

class ComponentConfig(BaseModel):
    """基础配置（所有组件共有）"""
    
    type: str
    name: str
    enabled: bool = True
    description: str | None = None  # ✅ 添加通用字段
    tags: list[str] = Field(default_factory=list)

class AgentConfig(ComponentConfig):
    type: Literal["agent"] = "agent"
    model: str
    tools: list[ToolReference] = Field(default_factory=list)
    memory: str | None = None
    knowledge: str | None = None
    session_store: str | None = None
    
    system_prompt: str | None = None
    max_steps: int = 10
    max_tokens: int | None = None  # ✅ 添加缺失字段
    enable_memory_update: bool = False
    user_id: str | None = None
    
    # Hooks
    hooks: list[str] = Field(default_factory=list)  # ✅ 添加缺失字段
    
    # Termination summary
    enable_termination_summary: bool = False
    termination_summary_prompt: str | None = None
```

#### 2.4.2 SessionStore 配置多态

**问题**: `SessionStoreConfig` 混合了多种存储类型的字段

**方案**: 使用 Pydantic 的 discriminated union

```python
# agio/config/schema.py

class BaseSessionStoreConfig(ComponentConfig):
    """基础 SessionStore 配置"""
    type: Literal["session_store"] = "session_store"
    store_type: str

class MongoDBSessionStoreConfig(BaseSessionStoreConfig):
    """MongoDB SessionStore 配置"""
    store_type: Literal["mongodb"] = "mongodb"
    mongo_uri: str
    mongo_db_name: str

class PostgresSessionStoreConfig(BaseSessionStoreConfig):
    """Postgres SessionStore 配置"""
    store_type: Literal["postgres"] = "postgres"
    postgres_url: str

class InMemorySessionStoreConfig(BaseSessionStoreConfig):
    """InMemory SessionStore 配置"""
    store_type: Literal["inmemory"] = "inmemory"

# 使用 Union + discriminator
SessionStoreConfig = Annotated[
    MongoDBSessionStoreConfig | PostgresSessionStoreConfig | InMemorySessionStoreConfig,
    Field(discriminator="store_type")
]
```

**改进点**:
- ✅ 类型安全
- ✅ 符合 OCP
- ✅ 清晰的配置结构

---

### 2.5 全局单例改进

**问题**: 当前单例无法重置，测试困难

**方案**: 可重置的单例 + 上下文管理

```python
# agio/config/system.py

_config_system: ConfigSystem | None = None
_config_system_lock = threading.Lock()

def get_config_system() -> ConfigSystem:
    """获取全局 ConfigSystem 实例"""
    global _config_system
    
    if _config_system is None:
        with _config_system_lock:
            if _config_system is None:
                _config_system = ConfigSystem()
    
    return _config_system

def reset_config_system() -> None:
    """重置全局 ConfigSystem（用于测试）"""
    global _config_system
    with _config_system_lock:
        _config_system = None

async def init_config_system(config_dir: str | Path) -> ConfigSystem:
    """初始化全局 ConfigSystem"""
    system = get_config_system()
    await system.load_from_directory(config_dir)
    await system.build_all()
    return system

# 可选：支持多配置系统
class ConfigSystemContext:
    """配置系统上下文（支持多配置目录）"""
    
    def __init__(self, config_dir: str | Path):
        self.config_dir = config_dir
        self.system: ConfigSystem | None = None
    
    async def __aenter__(self) -> ConfigSystem:
        self.system = ConfigSystem()
        await self.system.load_from_directory(self.config_dir)
        await self.system.build_all()
        return self.system
    
    async def __aexit__(self, *args):
        # 清理资源
        pass

# 使用示例
async def test_with_custom_config():
    async with ConfigSystemContext("./test_configs") as system:
        agent = system.container.get("test_agent")
        ...
```

**改进点**:
- ✅ 线程安全
- ✅ 可重置（测试友好）
- ✅ 支持多配置系统（上下文）

---

## 三、迁移计划

### 3.1 迁移步骤

#### Phase 1: 基础模块（不影响现有功能）
1. 创建新模块
   - `agio/config/registry.py` - ConfigRegistry
   - `agio/config/container.py` - ComponentContainer
   - `agio/config/dependency.py` - DependencyResolver
   - `agio/config/builder_registry.py` - BuilderRegistry
   - `agio/config/hot_reload.py` - HotReloadManager

2. 完善测试
   - 为每个新模块编写单元测试
   - 确保拓扑排序、依赖解析逻辑正确

#### Phase 2: 重构 ConfigSystem（渐进式）
1. 在 `ConfigSystem` 中引入新模块
2. 逐步迁移方法到新模块
3. 保持向后兼容（旧方法标记为 deprecated）

#### Phase 3: Builder 改进
1. 创建 Provider 注册表
2. 重构 ModelBuilder、ToolBuilder
3. 完善 Schema 定义

#### Phase 4: 清理和优化
1. 删除旧代码
2. 更新文档和示例
3. 性能优化

### 3.2 风险控制

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 破坏现有功能 | 🔴 高 | 完整的单元测试 + 集成测试 |
| 性能下降 | 🟡 中 | 性能基准测试 |
| API 不兼容 | 🟡 中 | 保持向后兼容，逐步废弃 |

### 3.3 回滚策略

- 使用 Git 分支：`refactor/config-system`
- 保留旧代码（标记为 deprecated）
- 提供配置开关切换新旧实现

---

## 四、验收标准

### 4.1 功能验收
- [ ] 所有现有测试通过
- [ ] 新模块测试覆盖率 > 90%
- [ ] 循环依赖正确抛出异常
- [ ] 热重载功能正常

### 4.2 代码质量
- [ ] ConfigSystem 精简到 < 300 行
- [ ] 没有代码重复（拓扑排序逻辑统一）
- [ ] 符合 SOLID 原则
- [ ] 类型提示完整

### 4.3 性能要求
- [ ] 构建时间 < 当前实现的 120%
- [ ] 内存占用无显著增加

### 4.4 文档更新
- [ ] 更新 `configs/README.md`
- [ ] 添加架构文档
- [ ] 更新 API 文档

---

## 五、实施时间估算

| 阶段 | 工作量 | 时间 |
|------|-------|------|
| Phase 1: 基础模块 | 中 | 2-3 天 |
| Phase 2: 重构 ConfigSystem | 高 | 3-4 天 |
| Phase 3: Builder 改进 | 中 | 1-2 天 |
| Phase 4: 清理优化 | 低 | 1 天 |
| **总计** | | **7-10 天** |

---

## 六、后续优化方向

1. **配置热更新**: 支持文件系统监听，自动重载
2. **配置版本管理**: 支持配置的版本回滚
3. **配置继承**: 支持配置模板和继承
4. **插件系统**: 支持第三方 Builder 和 Provider
5. **配置校验**: 增强的配置验证（如依赖是否存在）

---

## 七、总结

本重构方案通过以下措施解决现有问题：

| 问题 | 解决方案 |
|------|---------|
| ConfigSystem 职责过重 | 拆分为 5 个独立模块 |
| 拓扑排序逻辑重复 | 统一在 DependencyResolver |
| 循环依赖只 warning | fail fast，抛出异常 |
| Builder 硬编码 | Provider 注册表 |
| 全局单例无法重置 | 可重置单例 + 上下文管理 |
| Schema 字段缺失 | 完善定义 + discriminated union |

**核心设计原则**:
- ✅ 单一职责（SRP）
- ✅ 开闭原则（OCP）
- ✅ 依赖倒置（DIP）
- ✅ 组合优于继承
- ✅ KISS（保持简单）

重构后的架构将更加**清晰、简洁、优雅**，易于维护和扩展。
