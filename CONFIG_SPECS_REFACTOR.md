# 配置系统 Specs 重构方案

## 1. 概述

本文档描述了将当前配置系统重构为基于统一 Specs 规范的设计方案，参考 Kubernetes 的 Spec 设计模式，为所有基于配置的组件建立统一的规范体系。

### 1.1 设计目标

1. **统一规范**：所有配置组件遵循统一的 Spec 结构
2. **类型安全**：通过类型系统保证配置的正确性
3. **易于扩展**：新增组件类型时遵循统一模式
4. **配置一致性**：YAML 配置文件格式统一
5. **抽象管理**：通过父类封装共性逻辑，减少重复代码

### 1.2 核心原则

- **Spec 分离**：配置规范（Spec）与实现（Implementation）分离
- **分层抽象**：通过基类和接口定义统一行为
- **类型驱动**：使用类型系统保证配置正确性
- **向后兼容**：重构过程中保持 API 兼容性（如需要）

## 2. 当前问题分析

### 2.1 Store 配置不统一

当前系统中存在多种 Store 类型，但配置格式不统一：

**SessionStoreConfig**:
```python
class SessionStoreConfig(ComponentConfig):
    type: Literal["session_store"] = "session_store"
    store_type: str  # "mongodb", "inmemory", "postgres"
    params: dict = Field(default_factory=dict)
    mongo_uri: str | None = None  # MongoDB 特定字段
    mongo_db_name: str | None = None
    postgres_url: str | None = None  # Postgres 特定字段
```

**TraceStoreConfig**:
```python
class TraceStoreConfig(ComponentConfig):
    type: Literal["trace_store"] = "trace_store"
    mongo_uri: str | None = None  # 直接暴露，没有 store_type
    mongo_db_name: str | None = None
    buffer_size: int = Field(default=1000)
    flush_interval: int = Field(default=60)
```

**CitationStoreConfig**:
```python
class CitationStoreConfig(ComponentConfig):
    type: Literal["citation_store"] = "citation_store"
    store_type: str  # "mongodb", "inmemory"
    mongo_uri: str | None = None
    mongo_db_name: str | None = None
    # 缺少 params 字段
```

**问题总结**：
1. 字段命名不一致（`store_type` vs 直接暴露实现细节）
2. MongoDB 配置字段重复定义
3. 缺少统一的参数传递机制（`params` 字段使用不一致）
4. 没有统一的存储后端抽象

### 2.2 其他组件配置问题

**ModelConfig**:
```python
class ModelConfig(ComponentConfig):
    type: Literal["model"] = "model"
    provider: str  # "openai", "anthropic", "deepseek"
    model_name: str
    api_key: str | None = None
    base_url: str | None = None
    # 直接暴露 provider 特定字段
```

**MemoryConfig / KnowledgeConfig**:
```python
class MemoryConfig(ComponentConfig):
    type: Literal["memory"] = "memory"
    backend: str  # "redis", "inmemory"
    params: dict = Field(default_factory=dict)  # 使用 params

class KnowledgeConfig(ComponentConfig):
    type: Literal["knowledge"] = "knowledge"
    backend: str  # "chroma", "pinecone"
    params: dict = Field(default_factory=dict)
```

**问题总结**：
1. 命名不一致（`provider` vs `backend` vs `store_type`）
2. 配置字段直接暴露实现细节
3. 缺少统一的配置结构

### 2.3 缺少抽象层

当前系统缺少：
1. 统一的 Store 基类配置
2. 统一的 Provider/Backend 配置抽象
3. 统一的参数传递机制
4. 统一的验证和转换逻辑

## 3. 统一 Spec 规范设计

### 3.1 K8s 风格的 Spec 结构

参考 Kubernetes 的设计，每个组件配置包含：

```
ComponentConfig
├── metadata: ComponentMetadata  # 元数据（名称、标签、描述等）
├── spec: ComponentSpec          # 规范（具体配置）
└── status: ComponentStatus      # 状态（运行时状态，可选）
```

### 3.2 核心抽象类设计

#### 3.2.1 ComponentMetadata

```python
class ComponentMetadata(BaseModel):
    """组件元数据"""
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    annotations: dict[str, str] = Field(default_factory=dict)
```

#### 3.2.2 BaseComponentSpec

```python
class BaseComponentSpec(BaseModel):
    """组件规范基类"""
    type: str  # 组件类型标识
    
    @abstractmethod
    def validate(self) -> None:
        """验证配置有效性"""
        pass
```

#### 3.2.3 BaseComponentConfig

```python
class BaseComponentConfig(BaseModel):
    """组件配置基类（包含 metadata + spec）"""
    metadata: ComponentMetadata
    spec: BaseComponentSpec
    
    @property
    def name(self) -> str:
        """快捷访问名称"""
        return self.metadata.name
    
    @property
    def type(self) -> str:
        """快捷访问类型"""
        return self.spec.type
```

### 3.3 Store 类型统一 Spec 设计

#### 3.3.1 StorageBackendSpec

```python
class StorageBackendSpec(BaseModel):
    """存储后端规范基类"""
    backend_type: str  # "mongodb", "postgres", "inmemory", "redis", etc.
    
    @abstractmethod
    def get_connection_params(self) -> dict[str, Any]:
        """获取连接参数"""
        pass
```

#### 3.3.2 MongoDBBackendSpec

```python
class MongoDBBackendSpec(StorageBackendSpec):
    """MongoDB 后端规范"""
    backend_type: Literal["mongodb"] = "mongodb"
    uri: str = Field(..., description="MongoDB connection URI")
    db_name: str = Field(default="agio", description="Database name")
    collection_name: str | None = Field(default=None, description="Collection name (optional)")
    
    def get_connection_params(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "db_name": self.db_name,
        }
```

#### 3.3.3 PostgresBackendSpec

```python
class PostgresBackendSpec(StorageBackendSpec):
    """PostgreSQL 后端规范"""
    backend_type: Literal["postgres"] = "postgres"
    url: str = Field(..., description="PostgreSQL connection URL")
    pool_size: int = Field(default=10, description="Connection pool size")
    
    def get_connection_params(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "pool_size": self.pool_size,
        }
```

#### 3.3.4 InMemoryBackendSpec

```python
class InMemoryBackendSpec(StorageBackendSpec):
    """内存后端规范"""
    backend_type: Literal["inmemory"] = "inmemory"
    
    def get_connection_params(self) -> dict[str, Any]:
        return {}
```

#### 3.3.5 BaseStoreSpec

```python
class BaseStoreSpec(BaseComponentSpec):
    """Store 规范基类"""
    backend: StorageBackendSpec  # 使用 Union 类型支持多种后端
    
    def validate(self) -> None:
        """验证后端配置"""
        if not self.backend:
            raise ValueError("backend is required")
```

#### 3.3.6 SessionStoreSpec

```python
class SessionStoreSpec(BaseStoreSpec):
    """Session Store 规范"""
    type: Literal["session_store"] = "session_store"
    backend: StorageBackendSpec  # MongoDBBackendSpec | PostgresBackendSpec | InMemoryBackendSpec
    
    # Session Store 特定配置
    enable_indexing: bool = Field(default=True, description="Enable database indexing")
    batch_size: int = Field(default=100, description="Batch operation size")
```

#### 3.3.7 TraceStoreSpec

```python
class TraceStoreSpec(BaseStoreSpec):
    """Trace Store 规范"""
    type: Literal["trace_store"] = "trace_store"
    backend: StorageBackendSpec
    
    # Trace Store 特定配置
    buffer_size: int = Field(default=1000, description="In-memory buffer size")
    flush_interval: int = Field(default=60, description="Flush interval in seconds")
    enable_persistence: bool = Field(default=True, description="Enable MongoDB persistence")
```

#### 3.3.8 CitationStoreSpec

```python
class CitationStoreSpec(BaseStoreSpec):
    """Citation Store 规范"""
    type: Literal["citation_store"] = "citation_store"
    backend: StorageBackendSpec
    
    # Citation Store 特定配置
    auto_cleanup: bool = Field(default=False, description="Auto cleanup old citations")
    cleanup_after_days: int = Field(default=30, description="Cleanup citations older than N days")
```

### 3.4 其他组件类型统一 Spec 设计

#### 3.4.1 ModelProviderSpec

```python
class ModelProviderSpec(BaseModel):
    """模型 Provider 规范基类"""
    provider_type: str  # "openai", "anthropic", "deepseek", etc.
    
    @abstractmethod
    def get_api_params(self) -> dict[str, Any]:
        """获取 API 调用参数"""
        pass
```

#### 3.4.2 ModelSpec

```python
class ModelSpec(BaseComponentSpec):
    """Model 规范"""
    type: Literal["model"] = "model"
    provider: ModelProviderSpec  # OpenAIProviderSpec | AnthropicProviderSpec | ...
    model_name: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = None
    timeout: float | None = None
    
    def validate(self) -> None:
        if not self.provider:
            raise ValueError("provider is required")
```

#### 3.4.3 ToolSpec

```python
class ToolSpec(BaseComponentSpec):
    """Tool 规范"""
    type: Literal["tool"] = "tool"
    
    # 工具来源
    tool_name: str | None = None  # Built-in tool name
    module: str | None = None  # Custom tool module
    class_name: str | None = None  # Custom tool class
    
    # 工具配置
    params: dict[str, Any] = Field(default_factory=dict)
    dependencies: dict[str, str] = Field(default_factory=dict)  # {param_name: component_name}
    requires_consent: bool = Field(default=False)
```

#### 3.4.4 AgentSpec

```python
class AgentSpec(BaseComponentSpec):
    """Agent 规范"""
    type: Literal["agent"] = "agent"
    model: str  # Reference to model name
    tools: list[str | dict] = Field(default_factory=list)  # Tool references
    memory: str | None = None
    knowledge: str | None = None
    session_store: str | None = None
    system_prompt: str | None = None
    max_steps: int = Field(default=10, ge=1)
    enable_permission: bool = Field(default=False)
```

### 3.5 统一配置类设计

#### 3.5.1 StoreConfig 统一结构

```python
# 使用 Union 类型支持多种 Store
StoreConfig = SessionStoreConfig | TraceStoreConfig | CitationStoreConfig

class SessionStoreConfig(BaseComponentConfig):
    metadata: ComponentMetadata
    spec: SessionStoreSpec

class TraceStoreConfig(BaseComponentConfig):
    metadata: ComponentMetadata
    spec: TraceStoreSpec

class CitationStoreConfig(BaseComponentConfig):
    metadata: ComponentMetadata
    spec: CitationStoreSpec
```

#### 3.5.2 YAML 配置格式统一

**统一格式**：
```yaml
metadata:
  name: mongodb_session_store
  description: "MongoDB session store"
  tags:
    - persistence
    - mongodb
  enabled: true

spec:
  type: session_store
  backend:
    backend_type: mongodb
    uri: ${AGIO_MONGO_URI:mongodb://localhost:27017}
    db_name: ${AGIO_MONGO_DB:agio}
  enable_indexing: true
  batch_size: 100
```

**向后兼容格式（可选）**：
```yaml
# 支持扁平化格式，自动转换为嵌套格式
type: session_store
name: mongodb_session_store
backend_type: mongodb
mongo_uri: ${AGIO_MONGO_URI:mongodb://localhost:27017}
mongo_db_name: ${AGIO_MONGO_DB:agio}
enabled: true
```

## 4. 重构实施计划

### 4.1 阶段一：基础抽象层（Phase 1）

**目标**：建立核心抽象类和接口

1. 创建 `ComponentMetadata` 类
2. 创建 `BaseComponentSpec` 和 `BaseComponentConfig`
3. 创建 `StorageBackendSpec` 及其实现类
4. 创建 `BaseStoreSpec` 基类

**影响范围**：
- `agio/config/schema.py` - 新增抽象类
- 不影响现有代码（新增文件）

### 4.2 阶段二：Store 类型重构（Phase 2）

**目标**：统一所有 Store 类型的配置结构

1. 重构 `SessionStoreConfig` 使用新 Spec
2. 重构 `TraceStoreConfig` 使用新 Spec
3. 重构 `CitationStoreConfig` 使用新 Spec
4. 更新对应的 Builder 类

**影响范围**：
- `agio/config/schema.py` - 重构 Store 配置类
- `agio/config/builders.py` - 更新 Builder
- `configs/storages/**/*.yaml` - 更新配置文件格式

### 4.3 阶段三：其他组件类型重构（Phase 3）

**目标**：统一 Model、Tool、Agent 等组件配置

1. 创建 `ModelProviderSpec` 及其实现
2. 重构 `ModelConfig` 使用新 Spec
3. 重构 `ToolConfig` 使用新 Spec
4. 重构 `AgentConfig` 使用新 Spec
5. 重构 `WorkflowConfig` 使用新 Spec

**影响范围**：
- `agio/config/schema.py` - 重构所有配置类
- `agio/config/builders.py` - 更新所有 Builder
- `configs/**/*.yaml` - 更新所有配置文件

### 4.4 阶段四：配置加载器适配（Phase 4）

**目标**：支持新旧格式兼容

1. 更新 `ConfigLoader` 支持嵌套格式
2. 添加扁平格式到嵌套格式的转换器
3. 更新配置验证逻辑

**影响范围**：
- `agio/config/loader.py` - 添加格式转换
- `agio/config/system.py` - 更新解析逻辑

### 4.5 阶段五：文档和测试（Phase 5）

**目标**：完善文档和测试

1. 更新配置文档
2. 添加配置格式示例
3. 更新单元测试
4. 添加迁移指南

**影响范围**：
- `docs/CONFIG_SYSTEM.md` - 更新文档
- `configs/README.md` - 更新示例
- `tests/config/` - 更新测试

## 5. 详细实现设计

### 5.1 代码结构组织

```
agio/config/
├── schema.py              # 现有配置类（逐步迁移）
├── specs/                 # 新增：Spec 定义目录
│   ├── __init__.py
│   ├── base.py           # BaseComponentSpec, BaseComponentConfig
│   ├── metadata.py       # ComponentMetadata
│   ├── store.py          # Store 相关 Specs
│   │   ├── StorageBackendSpec
│   │   ├── MongoDBBackendSpec
│   │   ├── PostgresBackendSpec
│   │   ├── InMemoryBackendSpec
│   │   ├── BaseStoreSpec
│   │   ├── SessionStoreSpec
│   │   ├── TraceStoreSpec
│   │   └── CitationStoreSpec
│   ├── model.py          # Model 相关 Specs
│   │   ├── ModelProviderSpec
│   │   ├── OpenAIProviderSpec
│   │   ├── AnthropicProviderSpec
│   │   └── ModelSpec
│   ├── tool.py           # Tool Spec
│   ├── agent.py          # Agent Spec
│   └── workflow.py       # Workflow Spec
├── converters.py         # 新增：格式转换器（扁平 <-> 嵌套）
└── ...
```

### 5.2 核心类实现示例

#### 5.2.1 ComponentMetadata

```python
# agio/config/specs/metadata.py
from pydantic import BaseModel, Field

class ComponentMetadata(BaseModel):
    """组件元数据"""
    name: str = Field(..., description="Component name")
    description: str | None = Field(default=None, description="Component description")
    tags: list[str] = Field(default_factory=list, description="Component tags")
    enabled: bool = Field(default=True, description="Whether component is enabled")
    annotations: dict[str, str] = Field(
        default_factory=dict,
        description="Additional annotations (key-value pairs)"
    )
```

#### 5.2.2 BaseComponentSpec

```python
# agio/config/specs/base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel

class BaseComponentSpec(BaseModel, ABC):
    """组件规范基类"""
    type: str = Field(..., description="Component type identifier")
    
    @abstractmethod
    def validate(self) -> None:
        """验证配置有效性"""
        pass
    
    class Config:
        extra = "forbid"  # 禁止额外字段
```

#### 5.2.3 BaseComponentConfig

```python
# agio/config/specs/base.py
from pydantic import BaseModel
from agio.config.specs.metadata import ComponentMetadata
from agio.config.specs.base import BaseComponentSpec

class BaseComponentConfig(BaseModel):
    """组件配置基类（包含 metadata + spec）"""
    metadata: ComponentMetadata
    spec: BaseComponentSpec
    
    @property
    def name(self) -> str:
        """快捷访问名称"""
        return self.metadata.name
    
    @property
    def type(self) -> str:
        """快捷访问类型"""
        return self.spec.type
    
    @property
    def enabled(self) -> bool:
        """快捷访问启用状态"""
        return self.metadata.enabled
    
    def validate(self) -> None:
        """验证配置"""
        self.spec.validate()
```

#### 5.2.4 StorageBackendSpec 实现

```python
# agio/config/specs/store.py
from abc import ABC, abstractmethod
from typing import Any, Literal
from pydantic import BaseModel, Field

class StorageBackendSpec(BaseModel, ABC):
    """存储后端规范基类"""
    backend_type: str = Field(..., description="Backend type identifier")
    
    @abstractmethod
    def get_connection_params(self) -> dict[str, Any]:
        """获取连接参数"""
        pass

class MongoDBBackendSpec(StorageBackendSpec):
    """MongoDB 后端规范"""
    backend_type: Literal["mongodb"] = "mongodb"
    uri: str = Field(..., description="MongoDB connection URI")
    db_name: str = Field(default="agio", description="Database name")
    collection_name: str | None = Field(
        default=None,
        description="Collection name (optional, backend may use default)"
    )
    
    def get_connection_params(self) -> dict[str, Any]:
        params = {
            "uri": self.uri,
            "db_name": self.db_name,
        }
        if self.collection_name:
            params["collection_name"] = self.collection_name
        return params

class PostgresBackendSpec(StorageBackendSpec):
    """PostgreSQL 后端规范"""
    backend_type: Literal["postgres"] = "postgres"
    url: str = Field(..., description="PostgreSQL connection URL")
    pool_size: int = Field(default=10, ge=1, description="Connection pool size")
    max_overflow: int = Field(default=20, ge=0, description="Max overflow connections")
    
    def get_connection_params(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
        }

class InMemoryBackendSpec(StorageBackendSpec):
    """内存后端规范"""
    backend_type: Literal["inmemory"] = "inmemory"
    
    def get_connection_params(self) -> dict[str, Any]:
        return {}

# Union 类型用于类型提示
StorageBackendSpecUnion = MongoDBBackendSpec | PostgresBackendSpec | InMemoryBackendSpec
```

#### 5.2.5 Store Specs 实现

```python
# agio/config/specs/store.py (续)
from typing import Union
from agio.config.specs.base import BaseComponentSpec
from agio.config.specs.store import StorageBackendSpecUnion

class BaseStoreSpec(BaseComponentSpec):
    """Store 规范基类"""
    backend: StorageBackendSpecUnion = Field(..., description="Storage backend specification")
    
    def validate(self) -> None:
        """验证后端配置"""
        if not self.backend:
            raise ValueError("backend is required")
        # 可以添加更多验证逻辑

class SessionStoreSpec(BaseStoreSpec):
    """Session Store 规范"""
    type: Literal["session_store"] = "session_store"
    backend: StorageBackendSpecUnion
    
    # Session Store 特定配置
    enable_indexing: bool = Field(
        default=True,
        description="Enable database indexing for better query performance"
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        description="Batch operation size for bulk operations"
    )
    enable_sequence_atomic: bool = Field(
        default=True,
        description="Enable atomic sequence allocation"
    )

class TraceStoreSpec(BaseStoreSpec):
    """Trace Store 规范"""
    type: Literal["trace_store"] = "trace_store"
    backend: StorageBackendSpecUnion
    
    # Trace Store 特定配置
    buffer_size: int = Field(
        default=1000,
        ge=1,
        description="In-memory ring buffer size for recent traces"
    )
    flush_interval: int = Field(
        default=60,
        ge=1,
        description="Flush interval in seconds (for async persistence)"
    )
    enable_persistence: bool = Field(
        default=True,
        description="Enable persistent storage (if backend supports)"
    )
    collection_name: str = Field(
        default="traces",
        description="Collection/table name for traces"
    )

class CitationStoreSpec(BaseStoreSpec):
    """Citation Store 规范"""
    type: Literal["citation_store"] = "citation_store"
    backend: StorageBackendSpecUnion
    
    # Citation Store 特定配置
    auto_cleanup: bool = Field(
        default=False,
        description="Enable automatic cleanup of old citations"
    )
    cleanup_after_days: int = Field(
        default=30,
        ge=1,
        description="Cleanup citations older than N days"
    )
    collection_name: str = Field(
        default="citation_sources",
        description="Collection/table name for citations"
    )
```

#### 5.2.6 Store Config 实现

```python
# agio/config/specs/store.py (续)
from agio.config.specs.base import BaseComponentConfig
from agio.config.specs.metadata import ComponentMetadata

class SessionStoreConfig(BaseComponentConfig):
    """Session Store 配置"""
    metadata: ComponentMetadata
    spec: SessionStoreSpec

class TraceStoreConfig(BaseComponentConfig):
    """Trace Store 配置"""
    metadata: ComponentMetadata
    spec: TraceStoreSpec

class CitationStoreConfig(BaseComponentConfig):
    """Citation Store 配置"""
    metadata: ComponentMetadata
    spec: CitationStoreSpec

# Union 类型
StoreConfig = SessionStoreConfig | TraceStoreConfig | CitationStoreConfig
```

### 5.3 格式转换器实现

#### 5.3.1 扁平格式到嵌套格式转换

```python
# agio/config/converters.py
from typing import Any
from agio.config.specs.metadata import ComponentMetadata
from agio.config.specs.store import (
    SessionStoreConfig,
    SessionStoreSpec,
    TraceStoreConfig,
    TraceStoreSpec,
    CitationStoreConfig,
    CitationStoreSpec,
    MongoDBBackendSpec,
    PostgresBackendSpec,
    InMemoryBackendSpec,
)

def flatten_to_nested(config_dict: dict[str, Any]) -> dict[str, Any]:
    """
    将扁平格式配置转换为嵌套格式
    
    扁平格式：
    ```yaml
    type: session_store
    name: mongodb_session_store
    backend_type: mongodb
    mongo_uri: ...
    mongo_db_name: ...
    enabled: true
    ```
    
    嵌套格式：
    ```yaml
    metadata:
      name: mongodb_session_store
      enabled: true
    spec:
      type: session_store
      backend:
        backend_type: mongodb
        uri: ...
        db_name: ...
    ```
    """
    # 提取 metadata 字段
    metadata_fields = {"name", "description", "tags", "enabled", "annotations"}
    metadata = {k: v for k, v in config_dict.items() if k in metadata_fields}
    
    # 提取 spec 字段
    spec_fields = {k: v for k, v in config_dict.items() if k not in metadata_fields}
    
    # 根据类型转换 backend 配置
    component_type = spec_fields.get("type")
    if component_type in ("session_store", "trace_store", "citation_store"):
        backend_type = spec_fields.pop("backend_type") or spec_fields.pop("store_type")
        
        # 构建 backend spec
        backend_spec = {}
        if backend_type == "mongodb":
            backend_spec = {
                "backend_type": "mongodb",
                "uri": spec_fields.pop("mongo_uri") or spec_fields.pop("uri"),
                "db_name": spec_fields.pop("mongo_db_name") or spec_fields.pop("db_name", "agio"),
            }
            if "collection_name" in spec_fields:
                backend_spec["collection_name"] = spec_fields.pop("collection_name")
        elif backend_type == "postgres":
            backend_spec = {
                "backend_type": "postgres",
                "url": spec_fields.pop("postgres_url") or spec_fields.pop("url"),
                "pool_size": spec_fields.pop("pool_size", 10),
            }
        elif backend_type == "inmemory":
            backend_spec = {"backend_type": "inmemory"}
        
        spec_fields["backend"] = backend_spec
    
    return {
        "metadata": metadata,
        "spec": spec_fields,
    }
```

### 5.4 Builder 适配

#### 5.4.1 SessionStoreBuilder 更新

```python
# agio/config/builders.py
class SessionStoreBuilder(ComponentBuilder):
    """Builder for session store components."""
    
    async def build(
        self, config: SessionStoreConfig, dependencies: dict[str, Any]
    ) -> Any:
        """Build session store instance."""
        backend = config.spec.backend
        
        if backend.backend_type == "mongodb":
            from agio.providers.storage import MongoSessionStore
            
            params = backend.get_connection_params()
            store = MongoSessionStore(**params)
            
            # Initialize connection
            if hasattr(store, "_ensure_connection"):
                await store._ensure_connection()
            
            return store
        
        elif backend.backend_type == "inmemory":
            from agio.providers.storage import InMemorySessionStore
            return InMemorySessionStore()
        
        elif backend.backend_type == "postgres":
            # TODO: Implement PostgresSessionStore
            raise ComponentBuildError(f"Postgres backend not yet implemented")
        
        else:
            raise ComponentBuildError(
                f"Unknown session store backend: {backend.backend_type}"
            )
```

## 6. 迁移指南

### 6.1 配置文件迁移

#### 6.1.1 SessionStore 迁移示例

**旧格式** (`configs/storages/session_stores/mongodb.yaml`):
```yaml
type: session_store
name: mongodb_session_store
description: "MongoDB session store for agent runs and steps"
store_type: mongodb
mongo_uri: "${AGIO_MONGO_URI:mongodb://localhost:27017}"
mongo_db_name: "${AGIO_MONGO_DB:agio}"
enabled: true
tags:
  - persistence
  - mongodb
  - production
```

**新格式**:
```yaml
metadata:
  name: mongodb_session_store
  description: "MongoDB session store for agent runs and steps"
  enabled: true
  tags:
    - persistence
    - mongodb
    - production

spec:
  type: session_store
  backend:
    backend_type: mongodb
    uri: "${AGIO_MONGO_URI:mongodb://localhost:27017}"
    db_name: "${AGIO_MONGO_DB:agio}"
  enable_indexing: true
  batch_size: 100
```

#### 6.1.2 TraceStore 迁移示例

**旧格式** (`configs/observability/trace_store.yaml`):
```yaml
type: trace_store
name: trace_store
enabled: true
mongo_uri: ${AGIO_MONGO_URI:mongodb://localhost:27017}
mongo_db_name: ${AGIO_MONGO_DB:agio}
buffer_size: 1000
flush_interval: 60
```

**新格式**:
```yaml
metadata:
  name: trace_store
  enabled: true

spec:
  type: trace_store
  backend:
    backend_type: mongodb
    uri: ${AGIO_MONGO_URI:mongodb://localhost:27017}
    db_name: ${AGIO_MONGO_DB:agio}
  buffer_size: 1000
  flush_interval: 60
  enable_persistence: true
  collection_name: traces
```

### 6.2 代码迁移

#### 6.2.1 配置访问方式变更

**旧方式**:
```python
config = config_sys.get_config(ComponentType.SESSION_STORE, "mongodb_session_store")
uri = config.mongo_uri
db_name = config.mongo_db_name
```

**新方式**:
```python
config = config_sys.get_config(ComponentType.SESSION_STORE, "mongodb_session_store")
# 方式1：通过 spec 访问
uri = config.spec.backend.uri
db_name = config.spec.backend.db_name

# 方式2：通过快捷方法
params = config.spec.backend.get_connection_params()
uri = params["uri"]
db_name = params["db_name"]

# 方式3：通过 metadata 访问
name = config.name  # 或 config.metadata.name
enabled = config.enabled  # 或 config.metadata.enabled
```

### 6.3 向后兼容策略

在过渡期间，系统可以同时支持新旧两种格式：

1. **配置加载时自动检测格式**
2. **扁平格式自动转换为嵌套格式**
3. **逐步迁移配置文件**
4. **提供迁移工具脚本**

## 7. 优势总结

### 7.1 统一性

- ✅ 所有 Store 类型使用统一的 `backend` 结构
- ✅ 所有组件使用统一的 `metadata` + `spec` 结构
- ✅ YAML 配置文件格式统一

### 7.2 可扩展性

- ✅ 新增 Store 类型只需实现 `BaseStoreSpec`
- ✅ 新增存储后端只需实现 `StorageBackendSpec`
- ✅ 通过 Union 类型支持多种后端

### 7.3 类型安全

- ✅ 使用 Pydantic 进行配置验证
- ✅ 类型提示支持 IDE 自动补全
- ✅ 编译时类型检查

### 7.4 可维护性

- ✅ 配置结构清晰，职责分离
- ✅ 减少重复代码
- ✅ 易于理解和修改

## 8. 风险评估与缓解

### 8.1 风险点

1. **破坏性变更**：现有配置文件需要迁移
2. **代码变更范围大**：涉及多个模块
3. **测试覆盖**：需要更新大量测试用例

### 8.2 缓解措施

1. **分阶段实施**：逐步迁移，不一次性改动
2. **向后兼容**：支持新旧格式共存
3. **自动化迁移**：提供迁移工具和脚本
4. **充分测试**：每个阶段完成后进行全面测试
5. **文档完善**：提供详细的迁移指南和示例

