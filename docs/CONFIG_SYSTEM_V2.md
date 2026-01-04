# 配置系统 V2 - 完整开发指南

> **版本**: 2.0  
> **最后更新**: 2025-12-25  
> **状态**: ✅ 生产就绪

本文档是 Agio 配置系统的完整技术文档，涵盖架构设计、实现细节、使用规范和最佳实践，可作为后续开发的核心参考文档。

## 目录

1. [概述](#概述)
2. [架构设计](#架构设计)
3. [核心组件详解](#核心组件详解)
4. [配置规范](#配置规范)
5. [使用方式](#使用方式)
6. [实现细节](#实现细节)
7. [扩展开发](#扩展开发)
8. [最佳实践](#最佳实践)
9. [故障排查](#故障排查)

---

## 概述

### 设计理念

Agio 配置系统采用模块化架构，遵循 **SOLID** 和 **KISS** 原则，提供配置驱动、依赖解析、热重载等核心能力。

**核心原则**：
- ✅ **单一职责**：每个模块职责清晰
- ✅ **开闭原则**：支持动态注册 Builder 和 Provider
- ✅ **Fail Fast**：循环依赖立即抛出异常
- ✅ **线程安全**：全局单例支持并发访问
- ✅ **热重载**：配置变更自动级联重建
- ✅ **可扩展**：支持自定义 Provider 和 Builder

### 设计哲学

> **简洁 > 完美一致**  
> **实用 > 理论优雅**  
> **扁平 > 深度嵌套**

不追求 K8s 式的复杂结构，而是在**保持简洁的前提下实现一致性**。

### 核心特性

1. **统一配置结构**：所有组件遵循统一的元数据结构（type, name, description, enabled, tags）
2. **统一后端抽象**：所有 Store 类型使用统一的 `backend` 嵌套对象
3. **类型安全**：Pydantic + Union 类型提供完整的类型检查
4. **依赖管理**：自动拓扑排序，循环依赖检测
5. **热重载**：配置变更自动级联重建依赖组件
6. **环境变量**：统一使用 Jinja2 语法 `{{ env.VAR | default('...') }}`

---

## 架构设计

### 系统架构

```
ConfigSystem (门面/协调者)
├── ConfigRegistry          # 配置存储和查询
├── ComponentContainer      # 组件实例管理
├── DependencyResolver      # 依赖解析和拓扑排序
├── BuilderRegistry         # 构建器管理
├── HotReloadManager        # 热重载管理
├── ConfigLoader            # 配置文件加载器
└── ModelProviderRegistry   # 模型 Provider 注册表
```

### 核心模块职责

| 模块 | 职责 | 关键方法 |
|------|------|---------|
| `ConfigSystem` | 系统门面，协调各模块 | `load_from_directory()`, `build_all()`, `save_config()`, `delete_config()` |
| `ConfigRegistry` | 配置存储和查询 | `register()`, `get()`, `list_by_type()`, `remove()` |
| `ComponentContainer` | 实例管理和元数据 | `register()`, `get()`, `get_metadata()`, `get_dependents()` |
| `DependencyResolver` | 依赖提取和拓扑排序 | `extract_dependencies()`, `topological_sort()`, `get_affected_components()` |
| `BuilderRegistry` | 构建器注册和获取 | `register()`, `get()` |
| `HotReloadManager` | 热重载和级联重建 | `handle_change()`, `register_callback()` |
| `ConfigLoader` | YAML 文件加载和解析 | `load_all_configs()`, `_resolve_env_vars()` |

### 数据流

```
配置文件 (YAML)
    ↓
ConfigLoader (加载和解析)
    ↓
ConfigRegistry (存储配置)
    ↓
DependencyResolver (提取依赖关系)
    ↓
拓扑排序 (确定构建顺序)
    ↓
BuilderRegistry (获取构建器)
    ↓
ComponentBuilder (构建实例)
    ↓
ComponentContainer (存储实例)
```

### 依赖解析流程

```
1. 提取依赖 (extract_dependencies)
   ├── Agent: model, tools, memory, knowledge, session_store
   ├── Tool: dependencies 字段
   └── Workflow: session_store, stages[].runnable (递归)

2. 构建依赖图 (DependencyNode)
   └── 节点: {name, component_type, dependencies}

3. 拓扑排序 (Kahn's algorithm)
   ├── 计算入度
   ├── 从入度为 0 的节点开始
   └── 检测循环依赖 (fail fast)

4. 按顺序构建
   └── 确保依赖先于被依赖者构建
```

---

## 核心组件详解

### ConfigSystem

**位置**: `agio/config/system.py`

**职责**: 配置系统门面，协调各模块工作

**关键实现**:

```python
class ConfigSystem:
    def __init__(self):
        self.registry = ConfigRegistry()
        self.container = ComponentContainer()
        self.dependency_resolver = DependencyResolver()
        self.builder_registry = BuilderRegistry()
        self.hot_reload = HotReloadManager(...)
    
    CONFIG_CLASSES = {
        ComponentType.MODEL: ModelConfig,
        ComponentType.TOOL: ToolConfig,
        ComponentType.AGENT: AgentConfig,
        ComponentType.WORKFLOW: WorkflowConfig,
        ComponentType.SESSION_STORE: SessionStoreConfig,
        ComponentType.TRACE_STORE: TraceStoreConfig,
        ComponentType.CITATION_STORE: CitationStoreConfig,
    }
```

**核心方法**:

1. **`load_from_directory(config_dir)`**: 从目录加载所有配置文件
   - 使用 `ConfigLoader` 递归扫描 YAML 文件
   - 解析配置并注册到 `ConfigRegistry`
   - 返回加载统计 `{"loaded": count, "failed": count}`

2. **`build_all()`**: 按依赖顺序构建所有组件
   - 获取所有配置
   - 使用 `DependencyResolver.topological_sort()` 排序
   - 按顺序调用 `_build_component()` 构建

3. **`save_config(config)`**: 保存配置（触发热重载）
   - 注册配置到 `ConfigRegistry`
   - 如果是更新，调用 `HotReloadManager.handle_change()`
   - 如果是新建，直接构建组件

4. **`delete_config(component_type, name)`**: 删除配置
   - 调用 `HotReloadManager.handle_change()` 清理依赖组件
   - 从 `ConfigRegistry` 删除配置

5. **`_resolve_dependencies(config)`**: 解析组件依赖
   - Agent: 解析 model, tools, memory, knowledge, session_store
   - Tool: 解析 `dependencies` 字段
   - Workflow: 解析 session_store 和 stages

6. **`_resolve_tool_reference(tool_ref)`**: 解析工具引用
   - 字符串: 内置工具名称或配置的工具名称
   - 字典: `agent_tool` 或 `workflow_tool` 配置
   - 支持自引用检测

**全局单例**:

```python
_config_system: ConfigSystem | None = None
_config_system_lock = threading.Lock()

def get_config_system() -> ConfigSystem:
    """获取全局 ConfigSystem 实例（线程安全）"""
    # 双重检查锁定模式
```

### ConfigRegistry

**位置**: `agio/config/registry.py`

**职责**: 配置存储和查询

**数据结构**:

```python
self._configs: dict[tuple[ComponentType, str], ComponentConfig] = {}
```

**关键方法**:

- `register(config)`: 注册配置（使用 `(ComponentType, name)` 作为键）
- `get(component_type, name)`: 获取配置
- `has(component_type, name)`: 检查配置是否存在
- `list_by_type(component_type)`: 列出指定类型的所有配置
- `list_all()`: 列出所有配置
- `remove(component_type, name)`: 删除配置
- `get_names_by_type(component_type)`: 获取指定类型的所有组件名称

**特点**:
- 使用 `(ComponentType, name)` 作为唯一键
- 存储已验证的 Pydantic 配置模型
- 支持配置的增删改查

### ComponentContainer

**位置**: `agio/config/container.py`

**职责**: 组件实例管理和元数据存储

**数据结构**:

```python
self._instances: dict[str, Any] = {}
self._metadata: dict[str, ComponentMetadata] = {}
```

**ComponentMetadata**:

```python
@dataclass
class ComponentMetadata:
    component_type: ComponentType
    config: ComponentConfig
    dependencies: list[str]
    created_at: datetime
```

**关键方法**:

- `register(name, instance, metadata)`: 注册组件实例和元数据
- `get(name)`: 获取组件实例（不存在抛出异常）
- `get_or_none(name)`: 获取组件实例（不存在返回 None）
- `has(name)`: 检查组件是否存在
- `get_metadata(name)`: 获取组件元数据
- `get_all_instances()`: 获取所有组件实例
- `get_dependents(name)`: 获取依赖指定组件的其他组件（用于热重载）

**特点**:
- 存储已构建的组件实例
- 维护组件元数据（类型、依赖、创建时间）
- 支持依赖者查询（用于热重载级联重建）

### DependencyResolver

**位置**: `agio/config/dependency.py`

**职责**: 依赖解析和拓扑排序

**核心算法**: Kahn's algorithm（拓扑排序）

**关键方法**:

1. **`extract_dependencies(config, available_names)`**: 提取配置的依赖
   - Agent: `model`, `tools[]`, `memory`, `knowledge`, `session_store`
   - Tool: `dependencies` 字段的值
   - Workflow: `session_store`, `stages[].runnable`（递归提取）

2. **`topological_sort(configs, available_names)`**: 拓扑排序
   - 构建依赖图（`DependencyNode`）
   - 计算入度
   - 从入度为 0 的节点开始排序
   - **循环依赖检测**：如果排序后节点数 < 总节点数，抛出异常

3. **`get_affected_components(target_name, all_metadata)`**: 获取受影响的组件
   - BFS 遍历依赖图
   - 返回依赖目标组件的所有组件（用于热重载）

**依赖提取规则**:

```python
# Agent 依赖
deps = {config.model}
for tool_ref in config.tools:
    parsed = parse_tool_reference(tool_ref)
    if parsed.type == "function":
        deps.add(parsed.name)
    elif parsed.type == "agent_tool":
        deps.add(parsed.agent)
    elif parsed.type == "workflow_tool":
        deps.add(parsed.workflow)
if config.memory:
    deps.add(config.memory)
# ...

# Tool 依赖
deps = set(config.effective_dependencies.values())

# Workflow 依赖（递归）
deps = {config.session_store}
for stage in config.stages:
    if isinstance(stage.runnable, str):
        deps.add(stage.runnable)
    elif isinstance(stage.runnable, dict):
        # 递归提取嵌套 workflow
        ...
```

**循环依赖检测**:

```python
if len(sorted_names) < len(nodes):
    unresolved = set(nodes.keys()) - set(sorted_names)
    raise ConfigError(
        f"Circular dependency detected among: {unresolved}"
    )
```

### BuilderRegistry & ComponentBuilder

**位置**: `agio/config/builder_registry.py`, `agio/config/builders.py`

**职责**: 构建器注册和管理

**内置构建器**:

- `ModelBuilder`: 构建 LLM 模型实例
- `ToolBuilder`: 构建工具实例（支持依赖注入）
- `AgentBuilder`: 构建 Agent 实例
- `WorkflowBuilder`: 构建 Workflow 实例
- `SessionStoreBuilder`: 构建会话存储实例
- `TraceStoreBuilder`: 构建追踪存储实例
- `CitationStoreBuilder`: 构建引用存储实例

**ComponentBuilder 基类**:

```python
class ComponentBuilder(ABC):
    @abstractmethod
    async def build(self, config: BaseModel, dependencies: dict[str, Any]) -> Any:
        """构建组件实例"""
        pass
    
    async def cleanup(self, instance: Any) -> None:
        """清理组件资源"""
        if hasattr(instance, "cleanup"):
            await instance.cleanup()
```

**ToolBuilder 实现细节**:

```python
class ToolBuilder(ComponentBuilder):
    async def build(self, config: ToolConfig, dependencies: dict[str, Any]) -> Any:
        # 1. 获取工具类
        tool_class = self._get_tool_class(config)
        
        # 2. 合并参数: config.params + resolved dependencies
        kwargs = {**config.effective_params}
        for param_name, dep_name in config.effective_dependencies.items():
            kwargs[param_name] = dependencies[param_name]
        
        # 3. 过滤有效参数（只保留工具类接受的参数）
        kwargs = self._filter_valid_params(tool_class, kwargs)
        
        # 4. 实例化
        return tool_class(**kwargs)
```

**AgentBuilder 实现细节**:

```python
class AgentBuilder(ComponentBuilder):
    async def build(self, config: AgentConfig, dependencies: dict[str, Any]) -> Any:
        kwargs = {
            "name": config.name,
            "model": dependencies["model"],
            "tools": dependencies.get("tools", []),
            "system_prompt": config.system_prompt,
            # ...
        }
        
        # 可选依赖
        if "memory" in dependencies:
            kwargs["memory"] = dependencies["memory"]
        if "session_store" in dependencies:
            kwargs["session_store"] = dependencies["session_store"]
        
        # 权限管理器自动注入
        if config.enable_permission:
            kwargs["permission_manager"] = get_permission_manager()
        
        return Agent(**kwargs)
```

**Store Builders 实现模式**:

所有 Store Builder 都遵循统一模式：

```python
async def build(self, config: StoreConfig, dependencies: dict[str, Any]) -> Any:
    backend = config.backend
    
    if backend.type == "mongodb":
        store = MongoStore(uri=backend.uri, db_name=backend.db_name)
        await store.connect()
        return store
    elif backend.type == "sqlite":
        store = SQLiteStore(db_path=backend.db_path)
        await store.connect()
        return store
    elif backend.type == "inmemory":
        return InMemoryStore()
```

### HotReloadManager

**位置**: `agio/config/hot_reload.py`

**职责**: 热重载管理和级联重建

**工作流程**:

```
1. 检测配置变更 (save_config / delete_config)
   ↓
2. 识别受影响组件 (get_affected_components)
   └── BFS 遍历依赖图，找到所有依赖者
   ↓
3. 级联销毁 (逆序)
   └── 从依赖者到被依赖者，依次销毁
   ↓
4. 级联重建 (正序)
   └── 从被依赖者到依赖者，依次重建
   ↓
5. 通知回调
   └── 触发注册的回调函数
```

**关键方法**:

- `handle_change(name, change_type, rebuild_func)`: 处理配置变更
- `register_callback(callback)`: 注册变更回调
- `_get_affected_components(name)`: 获取受影响的组件列表
- `_destroy_affected(affected)`: 销毁受影响的组件（逆序）
- `_rebuild_affected(affected, rebuild_func)`: 重建受影响的组件（正序）

**实现细节**:

```python
async def handle_change(self, name: str, change_type: str, rebuild_func: Callable | None) -> None:
    # 1. 获取受影响组件（BFS）
    affected = self._get_affected_components(name)
    
    # 2. 销毁（逆序：依赖者 -> 被依赖者）
    await self._destroy_affected(affected)
    
    # 3. 重建（正序：被依赖者 -> 依赖者）
    if rebuild_func and change_type in ("create", "update"):
        await self._rebuild_affected(affected, rebuild_func)
    
    # 4. 通知回调
    self._notify_callbacks(name, change_type)
```

### ConfigLoader

**位置**: `agio/config/loader.py`

**职责**: 从 YAML 文件加载配置

**工作流程**:

```
1. 递归扫描所有 YAML 文件 (rglob("*.yaml"))
   ↓
2. 解析 YAML 文件内容
   ↓
3. 渲染环境变量模板（Jinja2）
   ↓
4. 验证必需字段 (type, name)
   ↓
5. 识别组件类型 (ComponentType)
   ↓
6. 检查 enabled 字段
   ↓
7. 检测重复配置名称
   ↓
8. 按类型分组返回
```

**环境变量解析（Jinja2）**:

- 语法：`{{ env.VAR_NAME }}` 或 `{{ env.VAR_NAME | default("value") }}`
- 支持表达式与过滤器，使用沙箱环境与 `SilentUndefined`（缺失变量返回空字符串）
- 递归渲染所有字符串值（包含嵌套字典和列表），渲染失败保留原值并记录 warning

**关键方法**:

- `load_all_configs()`: 加载所有配置文件
- `_load_yaml_file(file_path)`: 加载单个 YAML 文件
- `_resolve_env_vars(data)`: 递归渲染 Jinja2 模板

**错误处理**:

- 缺少 `type` 或 `name` 字段：记录警告并跳过
- 未知类型：记录警告并跳过
- `enabled: false`：跳过但不报错
- 重复配置：记录警告，后加载的覆盖先加载的

---

## 配置规范

### 统一配置结构

所有组件配置遵循统一的元数据结构：

```yaml
# ============ 通用元数据（所有组件必备）============
type: <component_type>        # 组件类型：model/tool/agent/workflow/session_store/...
name: <component_name>        # 组件名称（唯一标识）
description: <description>    # 组件描述（可选，推荐）
enabled: true                 # 是否启用（默认 true）
tags: [tag1, tag2]           # 标签（可选，用于分类和查询）

# ============ 组件特定配置 ============
# 根据 type 不同，有不同的特定字段
# 但遵循统一的命名和结构约定
```

### 配置层次

```
ComponentConfig (基类)
├── type, name, description, enabled, tags  # 通用元数据
└── 组件特定字段                              # 根据类型不同
    ├── backend (对于有后端的组件)            # 统一的后端配置
    ├── provider (对于 Model)               # 统一的 provider 配置
    └── 其他特定配置
```

### Backend 统一规范

所有 Store 类型（SessionStore、TraceStore、CitationStore）使用统一的 `backend` 结构：

```yaml
backend:
  type: <backend_type>  # mongodb/sqlite/inmemory
  # 后端特定字段
  uri: "{{ env.MONGO_URI }}"     # MongoDB 连接 URI
  db_name: agio         # 数据库名称
  db_path: "agio.db"    # SQLite 数据库文件路径
  # ...
```

**支持的后端类型**：

- `mongodb`: MongoDB 数据库
- `sqlite`: SQLite 数据库（文件存储）
- `inmemory`: 内存存储（无持久化）

**Backend 配置定义** (`agio/config/backends.py`):

```python
class MongoDBBackend(BackendConfig):
    type: Literal["mongodb"] = "mongodb"
    uri: str
    db_name: str = "agio"
    collection_name: str | None = None

class SQLiteBackend(BackendConfig):
    type: Literal["sqlite"] = "sqlite"
    db_path: str

class InMemoryBackend(BackendConfig):
    type: Literal["inmemory"] = "inmemory"

StorageBackend = MongoDBBackend | SQLiteBackend | InMemoryBackend
```

### 组件配置详解

#### Model 配置

**Schema**: `agio/config/schema.py::ModelConfig`

```yaml
type: model
name: deepseek
description: "DeepSeek model for cost-effective AI tasks"
enabled: true
tags:
  - production
  - deepseek
  - cost-effective

# Provider 配置
provider: openai              # Provider 类型
model_name: deepseek-chat    # 模型名称
api_key: "{{ env.DEEPSEEK_API_KEY }}" # API 密钥
base_url: https://api.deepseek.com  # API 端点（可选）

# 模型参数
temperature: 0.7
max_tokens: 8192
timeout: 60.0                 # 请求超时（可选）
```

**字段说明**:

- `provider`: Provider 类型（openai, anthropic, deepseek 等）
- `model_name`: 模型名称
- `api_key`: API 密钥（可选，可使用环境变量）
- `base_url`: 自定义 API 端点（可选）
- `temperature`: 采样温度（0.0-2.0，默认 0.7）
- `max_tokens`: 最大生成 token 数（可选）
- `timeout`: 请求超时（秒，可选）

#### Tool 配置

**Schema**: `agio/config/schema.py::ToolConfig`

```yaml
type: tool
name: file_read
description: "Read file contents with support for text and images"
enabled: true
tags:
  - file
  - read
  - filesystem

# 工具来源（二选一）
tool_name: file_read         # 内置工具名称
# 或
module: custom.tools         # 自定义工具模块
class_name: CustomTool       # 自定义工具类名

# 工具参数
params:
  max_output_size_mb: 10.0
  max_image_size_mb: 5.0

# 依赖注入
dependencies:
  citation_source_store: citation_store_mongodb

# 权限配置
requires_consent: false
```

**字段说明**:

- `tool_name`: 内置工具名称（与 `module`/`class_name` 二选一）
- `module` + `class_name`: 自定义工具模块和类名
- `params`: 工具构造参数（dict）
- `dependencies`: 依赖映射 `{param_name: component_name}`
- `requires_consent`: 是否需要用户确认

**依赖注入机制**:

```python
# 配置中声明依赖
dependencies:
  citation_source_store: citation_store_mongodb

# Builder 解析依赖
for param_name, dep_name in config.effective_dependencies.items():
    kwargs[param_name] = dependencies[dep_name]  # 从 container 获取实例
```

#### Agent 配置

**Schema**: `agio/config/schema.py::AgentConfig`

```yaml
type: agent
name: simple_assistant
description: "Simple general-purpose assistant"
enabled: true
tags:
  - assistant
  - general

# 核心配置
model: deepseek                      # Model 引用
system_prompt: "You are a helpful assistant."

# 工具配置
tools:
  - ls                               # 简单引用
  - file_read                         # 简单引用
  - type: agent_tool                 # Agent 作为工具
    agent: researcher
    description: "Expert researcher"

# 组件引用
memory: redis_memory                 # Memory 引用（可选）
knowledge: chroma_kb                 # Knowledge 引用（可选）
session_store: mongodb_session_store # SessionStore 引用（可选）

# 执行配置
max_steps: 10
max_tokens: 4096
enable_memory_update: false

# 权限配置
enable_permission: false

# 终止总结
enable_termination_summary: false
termination_summary_prompt: null
```

**字段说明**:

- `model`: Model 配置名称（必需）
- `tools`: 工具列表（支持字符串引用或 `agent_tool`/`workflow_tool` 配置）
- `memory`: Memory 配置名称（可选）
- `knowledge`: Knowledge 配置名称（可选）
- `session_store`: SessionStore 配置名称（可选）
- `system_prompt`: 系统提示词（可选）
- `max_steps`: 最大执行步数（默认 10）
- `max_tokens`: 最大 token 数（可选）
- `enable_permission`: 是否启用权限检查
- `enable_termination_summary`: 是否在达到限制时生成总结

**工具引用格式**:

```yaml
tools:
  # 方式 1: 简单字符串引用
  - file_read
  
  # 方式 2: Agent 作为工具
  - type: agent_tool
    agent: researcher
    description: "Expert researcher"
    name: research_tool  # 可选自定义名称
  
  # 方式 3: Workflow 作为工具
  - type: workflow_tool
    workflow: research_pipeline
    description: "Research pipeline"
```

#### Workflow 配置

**Schema**: `agio/config/schema.py::WorkflowConfig`

```yaml
type: workflow
name: research_pipeline
description: "Sequential research and analysis pipeline"
workflow_type: pipeline           # pipeline/loop/parallel
enabled: true
tags:
  - pipeline
  - research
  - example

# Workflow 定义
stages:
  - id: research
    runnable: researcher          # Agent/Workflow 引用
    input: "Research: {input}"
    condition: null               # 条件表达式（可选）
  
  - id: analyze
    runnable: analyzer
    input: "Analyze: {research.output}"

# Loop 特定配置
condition: "continue"             # Loop 条件（workflow_type=loop 时）
max_iterations: 10

# Parallel 特定配置
merge_template: "{branch1} + {branch2}"  # 合并模板（workflow_type=parallel 时）

# 组件引用
session_store: mongodb_session_store
```

**字段说明**:

- `workflow_type`: 工作流类型（pipeline/loop/parallel）
- `stages`: 阶段列表
  - `id`: 阶段标识符
  - `runnable`: Agent/Workflow 引用或内联配置
  - `input`: 输入模板（支持 `{stage_id.output}` 引用）
  - `condition`: 条件表达式（可选）
- `condition`: Loop 继续条件（workflow_type=loop 时）
- `max_iterations`: Loop 最大迭代次数
- `merge_template`: Parallel 合并模板
- `session_store`: SessionStore 配置名称（可选）

**嵌套 Workflow**:

```yaml
stages:
  - id: nested_workflow
    runnable:
      type: workflow
      workflow_type: pipeline
      stages:
        - id: step1
          runnable: agent1
```

#### Store 配置

**统一 Backend 结构**:

所有 Store 类型都使用统一的 `backend` 嵌套对象。

##### SessionStore 配置

**Schema**: `agio/config/schema.py::SessionStoreConfig`

```yaml
type: session_store
name: mongodb_session_store
description: "MongoDB session store for agent runs and steps"
enabled: true
tags:
  - persistence
  - mongodb
  - production

backend:
  type: mongodb
  uri: "{{ env.AGIO_MONGO_URI | default('mongodb://localhost:27017') }}"
  db_name: "{{ env.AGIO_MONGO_DB | default('agio') }}"

enable_indexing: true
batch_size: 100
```

**字段说明**:

- `backend`: 后端配置（统一结构）
- `enable_indexing`: 是否启用数据库索引
- `batch_size`: 批量操作大小

##### TraceStore 配置

**Schema**: `agio/config/schema.py::TraceStoreConfig`

```yaml
type: trace_store
name: trace_store
description: "Trace storage for observability and debugging"
enabled: true
tags:
  - observability
  - tracing
  - mongodb

backend:
  type: mongodb
  uri: "{{ env.AGIO_MONGO_URI | default('mongodb://localhost:27017') }}"
  db_name: "{{ env.AGIO_MONGO_DB | default('agio') }}"
  collection_name: traces

buffer_size: 1000
flush_interval: 60
enable_persistence: true
```

**字段说明**:

- `backend`: 后端配置
- `buffer_size`: 内存缓冲区大小
- `flush_interval`: 刷新间隔（秒）
- `enable_persistence`: 是否启用持久化

##### CitationStore 配置

**Schema**: `agio/config/schema.py::CitationStoreConfig`

```yaml
type: citation_store
name: citation_store_mongodb
description: "MongoDB-based citation source storage"
enabled: true
tags:
  - storage
  - citation
  - mongodb

backend:
  type: mongodb
  uri: "{{ env.MONGO_URI | default('mongodb://localhost:27017') }}"
  db_name: "{{ env.MONGO_DB_NAME | default('agio') }}"
  collection_name: citation_sources

auto_cleanup: false
cleanup_after_days: 30
```

**字段说明**:

- `backend`: 后端配置
- `auto_cleanup`: 是否启用自动清理
- `cleanup_after_days`: 清理天数阈值

---

## 使用方式

### 初始化配置系统

```python
from agio.config import init_config_system, get_config_system

# 方式 1: 初始化并加载配置
config_sys = await init_config_system("./configs")

# 方式 2: 获取全局实例（已初始化）
config_sys = get_config_system()
```

### 加载配置

```python
# 从目录加载所有配置文件
stats = await config_sys.load_from_directory("./configs")
# 返回: {"loaded": 10, "failed": 0}

# 构建所有组件
await config_sys.build_all()
```

### 获取组件实例

```python
# 获取已构建的组件实例
agent = config_sys.get_instance("simple_assistant")
workflow = config_sys.get_instance("research_pipeline")
model = config_sys.get_instance("deepseek")
```

### 查询配置

```python
from agio.config import ComponentType

# 列出所有 Agent 配置
agent_configs = config_sys.list_configs(ComponentType.AGENT)

# 获取特定配置
config = config_sys.get_config(ComponentType.AGENT, "simple_assistant")
```

### 动态保存配置（热重载）

```python
from agio.config import ModelConfig

# 创建新配置
new_model = ModelConfig(
    name="gpt4",
    provider="openai",
    model_name="gpt-4",
    api_key="{{ env.OPENAI_API_KEY }}"
)

# 保存配置（自动触发热重载）
await config_sys.save_config(new_model)
# 系统会自动：
# 1. 注册配置到 Registry
# 2. 构建组件实例
# 3. 如果已存在，级联重建依赖组件
```

### 删除配置

```python
# 删除配置（自动级联清理）
await config_sys.delete_config(ComponentType.MODEL, "old_model")
# 系统会自动：
# 1. 从 Registry 删除配置
# 2. 从 Container 删除实例
# 3. 级联清理依赖该组件的组件
```

### 注册变更回调

```python
def on_config_change(name: str, change_type: str):
    print(f"Config changed: {name} ({change_type})")

config_sys.on_change(on_config_change)
```

---

## 实现细节

### 依赖解析实现

**位置**: `agio/config/dependency.py`

**算法**: Kahn's algorithm（拓扑排序）

**步骤**:

1. **构建依赖图**:
   ```python
   nodes = {}
   for config in configs:
       deps = self.extract_dependencies(config, available_names)
       nodes[config.name] = DependencyNode(
           name=config.name,
           component_type=ComponentType(config.type),
           dependencies=deps,
       )
   ```

2. **计算入度**:
   ```python
   in_degree = {name: len(node.dependencies) for name, node in nodes.items()}
   ```

3. **拓扑排序**:
   ```python
   queue = deque([name for name, degree in in_degree.items() if degree == 0])
   sorted_names = []
   
   while queue:
       name = queue.popleft()
       sorted_names.append(name)
       
       for other_name, node in nodes.items():
           if name in node.dependencies:
               in_degree[other_name] -= 1
               if in_degree[other_name] == 0:
                   queue.append(other_name)
   ```

4. **循环依赖检测**:
   ```python
   if len(sorted_names) < len(nodes):
       unresolved = set(nodes.keys()) - set(sorted_names)
       raise ConfigError(f"Circular dependency detected among: {unresolved}")
   ```

### 工具引用解析

**位置**: `agio/config/tool_reference.py`

**支持的引用格式**:

1. **字符串引用**: `"file_read"` → 内置工具或配置的工具
2. **Agent Tool**: `{"type": "agent_tool", "agent": "researcher"}`
3. **Workflow Tool**: `{"type": "workflow_tool", "workflow": "pipeline"}`

**解析流程**:

```python
def parse_tool_reference(tool_ref: str | dict) -> ParsedToolReference:
    if isinstance(tool_ref, str):
        return ParsedToolReference(type="function", name=tool_ref)
    
    tool_type = tool_ref.get("type")
    if tool_type == "agent_tool":
        return ParsedToolReference(type="agent_tool", agent=tool_ref.get("agent"))
    elif tool_type == "workflow_tool":
        return ParsedToolReference(type="workflow_tool", workflow=tool_ref.get("workflow"))
```

### 环境变量解析

**位置**: `agio/config/loader.py::_resolve_env_vars()`

**支持格式**:
- `{{ env.VAR_NAME }}`
- `{{ env.VAR_NAME | default("value") }}`

**实现**:

```python
def _resolve_env_vars(self, data: dict[str, Any]) -> dict[str, Any]:
    def resolve_value(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return renderer.render(value, env=os.environ)
            except Exception as e:
                logger.warning(
                    f"Template render failed: {e}, using original value: {value[:100]}..."
                )
                return value
        elif isinstance(value, dict):
            return {k: resolve_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [resolve_value(item) for item in value]
        else:
            return value

    return resolve_value(data)
```

### 热重载实现

**位置**: `agio/config/hot_reload.py`

**级联重建流程**:

```python
async def handle_change(self, name: str, change_type: str, rebuild_func: Callable | None) -> None:
    # 1. 获取受影响组件（BFS）
    affected = self._get_affected_components(name)
    # 返回: [target, dependent1, dependent2, ...]
    
    # 2. 销毁（逆序：依赖者 -> 被依赖者）
    for comp_name in reversed(affected):
        instance, metadata = self._container.remove(comp_name)
        if instance and metadata:
            builder = self._builder_registry.get(metadata.component_type)
            await builder.cleanup(instance)
    
    # 3. 重建（正序：被依赖者 -> 依赖者）
    if rebuild_func and change_type in ("create", "update"):
        for comp_name in affected:
            await rebuild_func(comp_name)
    
    # 4. 通知回调
    self._notify_callbacks(name, change_type)
```

**获取受影响组件** (BFS):

```python
def _get_affected_components(self, name: str) -> list[str]:
    affected = [name]  # 目标组件本身
    queue = [name]
    
    while queue:
        current = queue.pop(0)
        for comp_name, metadata in all_metadata.items():
            if current in metadata.dependencies and comp_name not in affected:
                affected.append(comp_name)
                queue.append(comp_name)
    
    return affected
```

### 工具依赖注入

**位置**: `agio/config/builders.py::ToolBuilder`

**实现流程**:

```python
async def build(self, config: ToolConfig, dependencies: dict[str, Any]) -> Any:
    # 1. 获取工具类
    tool_class = self._get_tool_class(config)
    
    # 2. 合并参数
    kwargs = {**config.effective_params}
    
    # 3. 注入依赖
    for param_name, dep_name in config.effective_dependencies.items():
        kwargs[param_name] = dependencies[param_name]  # 从 container 获取实例
    
    # 4. 过滤有效参数（只保留工具类接受的参数）
    kwargs = self._filter_valid_params(tool_class, kwargs)
    
    # 5. 实例化
    return tool_class(**kwargs)
```

**参数过滤**:

```python
def _filter_valid_params(self, tool_class: type, kwargs: dict) -> dict:
    import inspect
    sig = inspect.signature(tool_class.__init__)
    valid_params = {}
    
    has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD 
        for p in sig.parameters.values()
    )
    
    for key, value in kwargs.items():
        if key in sig.parameters or has_var_keyword:
            valid_params[key] = value
    
    return valid_params
```

---

## 扩展开发

### 注册自定义模型 Provider

```python
from agio.config import get_model_provider_registry
from agio.llm.base import Model

class CustomModel(Model):
    # 实现 Model 接口
    ...

# 注册 Provider
registry = get_model_provider_registry()
registry.register("custom_provider", CustomModel)

# 在配置中使用
# type: model
# name: my_model
# provider: custom_provider
```

### 注册自定义构建器

```python
from agio.config import BuilderRegistry, ComponentType, ComponentBuilder
from agio.config.schema import ComponentConfig

class CustomBuilder(ComponentBuilder):
    async def build(self, config: ComponentConfig, dependencies: dict) -> Any:
        # 构建逻辑
        ...

# 注册构建器
builder_registry = config_sys.builder_registry
builder_registry.register(ComponentType.CUSTOM, CustomBuilder())
```

### 添加新的 Backend 类型

**步骤 1**: 在 `agio/config/backends.py` 定义 Backend 配置类

```python
class CustomBackend(BackendConfig):
    type: Literal["custom"] = "custom"
    host: str
    port: int = 8080
    api_key: str | None = None
```

**步骤 2**: 更新 Union 类型

```python
StorageBackend = MongoDBBackend | SQLiteBackend | InMemoryBackend | CustomBackend
```

**步骤 3**: 在对应的 Builder 中添加构建逻辑

```python
class SessionStoreBuilder(ComponentBuilder):
    async def build(self, config: SessionStoreConfig, dependencies: dict[str, Any]) -> Any:
        backend = config.backend
        
        if backend.type == "custom":
            from agio.storage.session import CustomSessionStore
            store = CustomSessionStore(host=backend.host, port=backend.port)
            await store.connect()
            return store
        # ...
```

### 添加新的组件类型

**步骤 1**: 在 `agio/config/schema.py` 定义配置类

```python
class CustomComponentConfig(ComponentConfig):
    type: Literal["custom"] = "custom"
    # 组件特定字段
    custom_field: str
```

**步骤 2**: 在 `ComponentType` 枚举中添加类型

```python
class ComponentType(str, Enum):
    # ...
    CUSTOM = "custom"
```

**步骤 3**: 在 `ConfigSystem.CONFIG_CLASSES` 中注册

```python
CONFIG_CLASSES = {
    # ...
    ComponentType.CUSTOM: CustomComponentConfig,
}
```

**步骤 4**: 实现 Builder

```python
class CustomBuilder(ComponentBuilder):
    async def build(self, config: CustomComponentConfig, dependencies: dict[str, Any]) -> Any:
        # 构建逻辑
        ...
```

**步骤 5**: 注册 Builder

```python
builder_registry.register(ComponentType.CUSTOM, CustomBuilder())
```

**步骤 6**: 在 `DependencyResolver` 中添加依赖提取逻辑（如需要）

```python
def extract_dependencies(self, config: ComponentConfig, available_names: set[str] | None = None) -> set[str]:
    # ...
    elif isinstance(config, CustomComponentConfig):
        return self._extract_custom_deps(config)
```

---

## 最佳实践

### 配置组织

**目录结构**:

```
configs/
├── models/              # Model 配置
├── tools/               # Tool 配置
│   ├── file_operations/
│   ├── web_operations/
│   └── system_operations/
├── agents/              # Agent 配置
├── workflows/           # Workflow 配置
└── storages/            # Store 配置
    ├── session_stores/
    ├── trace_stores/
    └── citation_stores/
```

**命名规范**:

- 组件名称：小写下划线，描述性强（`mongodb_session_store`）
- 后端类型：小写，简洁（`mongodb`, `sqlite`, `inmemory`）
- 字段名称：小写下划线（`enable_indexing`, `batch_size`）

### 配置一致性

1. **元数据字段完整性**：所有配置必须包含 `type`, `name`, `enabled` 字段，推荐添加 `description` 和 `tags`
2. **Store 配置规范**：所有 Store 类型必须使用统一的 `backend` 结构
3. **描述清晰**：为每个配置提供有意义的 `description`
4. **标签分类**：使用 `tags` 进行分类，便于查询和管理

### 依赖管理

1. **明确声明依赖**：避免隐式依赖
   - Tool 的 `dependencies` 字段
   - Agent 的 `model`, `tools`, `session_store` 等引用
2. **避免循环依赖**：系统会自动检测并抛出异常
3. **依赖命名一致性**：使用配置名称引用，不要硬编码

### 环境变量

1. **格式**：`{{ env.VAR_NAME | default("value") }}`
2. **命名**：大写下划线，带前缀（`AGIO_MONGO_URI`）
3. **缺省处理**：优先使用环境值，缺失时走 `default`，若仍缺失返回空字符串（`SilentUndefined`）
4. **安全性**：沙箱渲染，敏感信息必须通过环境变量注入

### 热重载

1. **开发环境**：使用热重载快速迭代
2. **生产环境**：谨慎使用，注意级联重建的影响
3. **监控回调**：注册回调函数监控配置变更

### 错误处理

1. **Fail Fast**：循环依赖立即抛出异常
2. **日志记录**：关注日志中的配置加载错误
3. **验证配置**：使用 Pydantic 的 Field 约束（`ge`, `le`, `min_length` 等）

---

## 故障排查

### 常见问题

#### 1. 循环依赖错误

**错误信息**:
```
ConfigError: Circular dependency detected among: {agent_a, agent_b}
```

**解决方案**:
- 检查配置中的依赖关系
- 移除循环依赖（例如，将 Agent A 依赖 Agent B，同时 Agent B 依赖 Agent A）

#### 2. 组件未找到

**错误信息**:
```
ComponentNotFoundError: Component 'xxx' not found
```

**可能原因**:
- 配置未加载
- 组件未构建
- 名称拼写错误

**解决方案**:
- 检查配置是否正确加载
- 确认组件已构建（`build_all()`）
- 验证名称拼写

#### 3. 依赖注入失败

**错误信息**:
```
ComponentBuildError: Dependency 'xxx' (param: yyy) not found for tool 'zzz'
```

**可能原因**:
- 依赖配置不存在
- 依赖未构建
- `dependencies` 字段配置错误

**解决方案**:
- 检查依赖配置是否存在
- 确认依赖已构建
- 验证 `dependencies` 字段格式：`{param_name: component_name}`

#### 4. 配置加载失败

**错误信息**:
```
ConfigError: Missing 'type' field in config.yaml
```

**可能原因**:
- YAML 文件格式错误
- 缺少必需字段
- 环境变量未解析

**解决方案**:
- 检查 YAML 语法
- 确保包含 `type` 和 `name` 字段
- 验证环境变量是否正确设置

#### 5. 热重载失败

**错误信息**:
```
Failed to rebuild xxx: ...
```

**可能原因**:
- 依赖组件构建失败
- 资源清理失败
- 配置变更导致依赖关系变化

**解决方案**:
- 检查依赖组件状态
- 查看详细错误日志
- 手动重建组件（`rebuild(name)`）

### 调试技巧

1. **查看配置加载统计**:
   ```python
   stats = await config_sys.load_from_directory("./configs")
   print(stats)  # {"loaded": 10, "failed": 0}
   ```

2. **查看组件列表**:
   ```python
   components = config_sys.list_components()
   for comp in components:
       print(f"{comp['name']}: {comp['type']}, deps: {comp['dependencies']}")
   ```

3. **查看组件详细信息**:
   ```python
   info = config_sys.get_component_info("simple_assistant")
   print(info)
   ```

4. **查看依赖关系**:
   ```python
   config = config_sys.get_config(ComponentType.AGENT, "simple_assistant")
   deps = config_sys.dependency_resolver.extract_dependencies(config)
   print(deps)
   ```

5. **启用详细日志**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

---

## 相关代码

### 核心模块

- `agio/config/system.py`: ConfigSystem 主类
- `agio/config/registry.py`: ConfigRegistry
- `agio/config/container.py`: ComponentContainer
- `agio/config/dependency.py`: DependencyResolver
- `agio/config/builders.py`: 各种 Builder
- `agio/config/hot_reload.py`: HotReloadManager
- `agio/config/loader.py`: ConfigLoader
- `agio/config/builder_registry.py`: BuilderRegistry
- `agio/config/model_provider_registry.py`: ModelProviderRegistry

### 配置定义

- `agio/config/schema.py`: 所有配置类定义
- `agio/config/backends.py`: Backend 配置定义（Store 后端抽象）
- `agio/config/tool_reference.py`: Tool 引用解析

### 配置文件

- `configs/`: 所有配置文件目录

---

## 总结

Agio 配置系统 V2 在**保持简洁扁平化**的前提下，实现了配置系统的**完全一致性**：

1. **统一的元数据**：所有组件都有 `type`, `name`, `description`, `enabled`, `tags`
2. **统一的后端抽象**：所有 Store 使用 `backend` 嵌套对象
3. **统一的配置模式**：所有组件遵循相同的结构约定
4. **类型安全**：Pydantic + Union 类型提供完整的类型检查
5. **依赖管理**：自动拓扑排序，循环依赖检测
6. **热重载**：配置变更自动级联重建依赖组件

**核心价值**：
- 降低用户心智负担（一通百通）
- 提高系统可维护性（统一抽象）
- 保证类型安全（编译时检查）
- 易于扩展（添加新类型遵循统一模式）

---

**文档版本**: 2.0  
**最后更新**: 2025-12-25  
**维护者**: Agio 开发团队


