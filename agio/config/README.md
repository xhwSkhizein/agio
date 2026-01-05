# Config 模块架构说明

本文档梳理了 `agio/config/` 目录下各文件的功能和职责。

## 核心架构

配置系统采用分层架构，遵循 SOLID 原则：

```
ConfigSystem (门面)
    ├── ConfigRegistry (配置存储)
    ├── ComponentContainer (实例管理)
    ├── DependencyResolver (依赖解析)
    ├── BuilderRegistry (构建器管理)
    └── HotReloadManager (热重载)
```

## 文件职责说明

### 1. `__init__.py` - 模块导出
**职责**: 提供统一的对外接口，导出所有公共 API

**主要导出**:
- Settings: `AgioSettings`, `settings`
- Schema: 所有配置模型类 (`ModelConfig`, `ToolConfig`, `AgentConfig` 等)
- Exceptions: 配置异常类
- Core modules: 核心模块类
- System: `ConfigSystem`, `get_config_system()`, `init_config_system()`

---

### 2. `settings.py` - 全局设置
**职责**: 从环境变量加载全局配置

**功能**:
- 使用 `pydantic-settings` 从环境变量加载配置
- 环境变量前缀: `AGIO_`
- 支持 `.env` 文件
- 包含核心设置、存储设置、模型 Provider 设置、可观测性设置

**关键类**:
- `AgioSettings`: 全局设置模型
- `settings`: 全局单例实例

---

### 3. `exceptions.py` - 异常定义
**职责**: 定义配置系统的异常类型

**异常类**:
- `ConfigError`: 配置错误基类
- `ConfigNotFoundError`: 配置未找到
- `ComponentNotFoundError`: 组件未找到
- `ComponentBuildError`: 组件构建失败

---

### 4. `schema.py` - 配置模式定义
**职责**: 定义所有组件的配置模型（Pydantic）

**主要模型**:
- `ExecutionConfig`: 运行时执行配置
- `ComponentType`: 组件类型枚举
- `ComponentConfig`: 组件配置基类
- `ModelConfig`: 模型配置
- `ToolConfig`: 工具配置
- `SessionStoreConfig`: 会话存储配置
- `TraceStoreConfig`: 追踪存储配置
- `CitationStoreConfig`: 引用存储配置
- `AgentConfig`: Agent 配置
- `StageConfig`: 工作流阶段配置

**特点**:
- 使用 Pydantic 进行验证
- 支持前向引用解析
- 统一的配置结构

---

### 5. `loader.py` - 配置加载器
**职责**: 从 YAML 文件加载配置（冷启动）

**功能**:
- 递归扫描配置目录中的所有 YAML 文件
- 解析 YAML 内容
- 基于 `type` 字段识别组件类型
- 检测重复配置名称
- 解析环境变量 (`${VAR_NAME}` 或 `${VAR_NAME:default}`)
- 过滤已禁用的配置 (`enabled: false`)

**关键类**:
- `ConfigLoader`: 配置加载器

**方法**:
- `load_all_configs()`: 加载所有配置文件，返回按类型分组的字典

---

### 6. `registry.py` - 配置注册表
**职责**: 存储和查询已验证的配置模型

**功能**:
- 存储 Pydantic 配置模型
- 提供配置查询接口（按类型、按名称）
- 支持配置的增删改查
- 检测重复配置

**关键类**:
- `ConfigRegistry`: 配置注册表

**数据结构**:
- `_configs: dict[(ComponentType, str), ComponentConfig]`

---

### 7. `builder_registry.py` - 构建器注册表
**职责**: 管理组件构建器

**功能**:
- 注册和查询构建器
- 支持动态注册（扩展性）
- 默认注册所有类型的构建器

**关键类**:
- `ComponentBuilder`: 构建器协议（Protocol）
- `BuilderRegistry`: 构建器注册表

**默认构建器**:
- `ModelBuilder`, `ToolBuilder`
- `SessionStoreBuilder`, `TraceStoreBuilder`, `CitationStoreBuilder`
- `AgentBuilder`

---

### 8. `builders.py` - 组件构建器实现
**职责**: 实现各种组件的构建逻辑

**功能**:
- 根据配置和依赖构建组件实例
- 处理依赖注入
- 支持资源清理

**构建器实现**:
- `ModelBuilder`: 使用 `ModelProviderRegistry` 创建模型
- `ToolBuilder`: 
  - 支持内置工具（通过 `tool_name`）
  - 支持自定义工具（通过 `module` + `class_name`）
  - 处理工具配置对象（如 `FileReadConfig`）
  - 依赖注入
- `SessionStoreBuilder`: 构建会话存储（MongoDB/SQLite/InMemory）
- `TraceStoreBuilder`: 构建追踪存储
- `CitationStoreBuilder`: 构建引用存储
- `AgentBuilder`: 构建 Agent 实例

---

### 9. `container.py` - 组件容器
**职责**: 管理组件实例的生命周期

**功能**:
- 缓存已构建的组件实例
- 存储组件元数据（类型、配置、依赖）
- 提供实例查询接口
- 管理组件依赖关系

**关键类**:
- `ComponentMetadata`: 组件元数据（类型、配置、依赖、创建时间）
- `ComponentContainer`: 组件容器

**数据结构**:
- `_instances: dict[str, Any]`: 组件实例
- `_metadata: dict[str, ComponentMetadata]`: 组件元数据

---

### 10. `dependency.py` - 依赖解析器
**职责**: 处理组件依赖关系和拓扑排序

**功能**:
- 提取配置的依赖关系（Agent/Tool）
- 拓扑排序（Kahn's algorithm）
- 循环依赖检测（fail fast）
- 获取受影响的组件列表（BFS）

**关键类**:
- `DependencyNode`: 依赖节点
- `DependencyResolver`: 依赖解析器

**方法**:
- `extract_dependencies()`: 提取依赖
- `topological_sort()`: 拓扑排序
- `get_affected_components()`: 获取受影响的组件

---

### 11. `backends.py` - 后端配置定义
**职责**: 定义统一的后端配置抽象

**功能**:
- 提供统一的后端配置模式
- 支持多种后端类型

**后端类型**:
- **Storage Backends**: `MongoDBBackend`, `SQLiteBackend`, `InMemoryBackend`
- **Cache Backends**: `RedisBackend`, `InMemoryBackend`
- **Vector Backends**: `ChromaBackend`, `PineconeBackend`

**Union Types**:
- `StorageBackend`: 存储后端（用于 Session/Trace/Citation stores）

---

### 12. `system.py` - 配置系统门面
**职责**: 协调各模块工作，提供统一的外部接口

**功能**:
- 协调 `ConfigRegistry`, `ComponentContainer`, `DependencyResolver`, `BuilderRegistry`, `HotReloadManager`
- 提供配置加载、构建、查询的统一接口
- 处理组件构建流程
- 解析工具引用（字符串、Agent Tool）

**关键类**:
- `ConfigSystem`: 配置系统门面

**主要方法**:
- `load_from_directory()`: 从目录加载配置
- `build_all()`: 按依赖顺序构建所有组件
- `get()`: 获取组件实例
- `save_config()`: 保存配置（触发热重载）
- `delete_config()`: 删除配置

**全局函数**:
- `get_config_system()`: 获取全局单例
- `init_config_system()`: 初始化全局系统
- `reset_config_system()`: 重置系统（用于测试）

---

### 13. `model_provider_registry.py` - 模型 Provider 注册表
**职责**: 管理 LLM 模型 Provider 的注册和创建

**功能**:
- 注册和查询 Provider 工厂函数
- 支持动态扩展
- 默认注册 OpenAI、Anthropic、Deepseek

**关键类**:
- `ModelProvider`: Provider 协议
- `ModelProviderRegistry`: Provider 注册表

**默认 Provider**:
- `openai`: `OpenAIModel`
- `anthropic`: `AnthropicModel`
- `deepseek`: `DeepseekModel`

**全局函数**:
- `get_model_provider_registry()`: 获取全局单例

---

### 14. `tool_reference.py` - 工具引用解析
**职责**: 统一处理工具引用的解析

**功能**:
- 解析工具引用（字符串、Agent Tool）
- 标准化工具引用结构

**关键类**:
- `ParsedToolReference`: 解析后的工具引用

**工具引用类型**:
- `regular_tool`: 内置或自定义工具（字符串）
- `agent_tool`: Agent 作为工具

**函数**:
- `parse_tool_reference()`: 解析单个工具引用
- `parse_tool_references()`: 解析工具引用列表

---

### 15. `hot_reload.py` - 热重载管理器
**职责**: 处理配置变更和组件热重载

**功能**:
- 配置变更检测
- 级联重建受影响的组件
- 通知变更回调
- 资源清理

**关键类**:
- `HotReloadManager`: 热重载管理器

**变更类型**:
- `create`: 创建新组件
- `update`: 更新组件
- `delete`: 删除组件

**流程**:
1. 检测变更
2. 获取受影响的组件（BFS 遍历依赖图）
3. 销毁受影响的组件（逆序）
4. 重建受影响的组件（正序）
5. 通知回调

---

## 工作流程

### 1. 初始化流程
```
init_config_system(config_dir)
    ├── ConfigLoader.load_all_configs()  # 加载 YAML 文件
    ├── ConfigRegistry.register()         # 注册配置
    └── ConfigSystem.build_all()          # 构建所有组件
        ├── DependencyResolver.topological_sort()  # 拓扑排序
        └── BuilderRegistry.get().build()          # 构建组件
```

### 2. 组件构建流程
```
ConfigSystem._build_component(config)
    ├── DependencyResolver.extract_dependencies()  # 提取依赖
    ├── ComponentContainer.get()                  # 获取依赖实例
    ├── BuilderRegistry.get()                     # 获取构建器
    └── Builder.build()                           # 构建实例
        └── ComponentContainer.register()         # 注册实例
```

### 3. 热重载流程
```
ConfigSystem.save_config(config)
    └── HotReloadManager.handle_change()
        ├── DependencyResolver.get_affected_components()  # 获取受影响组件
        ├── HotReloadManager._destroy_affected()          # 销毁组件
        └── HotReloadManager._rebuild_affected()          # 重建组件
```

---

## 设计原则

1. **单一职责原则 (SRP)**: 每个模块只负责一个明确的功能
2. **开闭原则 (OCP)**: 通过注册表模式支持扩展，无需修改核心代码
3. **依赖倒置原则 (DIP)**: 使用 Protocol 定义接口，具体实现可替换
4. **KISS 原则**: 保持简单，避免过度设计

---

## 依赖关系图

```
ConfigSystem
    ├── ConfigRegistry ──┐
    ├── ComponentContainer ──┐
    ├── DependencyResolver ──┐
    ├── BuilderRegistry ──┐
    │   └── builders.py (构建器实现)
    └── HotReloadManager
        ├── ComponentContainer
        ├── DependencyResolver
        └── BuilderRegistry

ConfigLoader
    └── schema.py (配置模型)

ModelProviderRegistry
    └── llm/ (模型实现)

ToolBuilder
    └── tools/ (工具实现)
```

---

## 扩展点

1. **添加新的组件类型**:
   - 在 `schema.py` 中添加新的配置模型
   - 在 `ComponentType` 枚举中添加新类型
   - 在 `builders.py` 中实现构建器
   - 在 `BuilderRegistry` 中注册构建器

2. **添加新的模型 Provider**:
   - 实现模型类（遵循 `ModelProvider` 协议）
   - 在 `ModelProviderRegistry` 中注册

3. **添加新的后端类型**:
   - 在 `backends.py` 中定义后端配置类
   - 在相应的 Builder 中实现构建逻辑

