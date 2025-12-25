# 配置系统统一规范重构方案

## 设计理念

### 核心原则

1. **配置一致性**：所有组件遵循统一的配置结构，一通百通
2. **易用性优先**：简洁扁平，避免过度嵌套，降低心智负担
3. **可扩展性**：统一抽象，易于添加新组件类型和后端
4. **类型安全**：利用 Pydantic 提供完整的类型检查

### 设计哲学

> **简洁 > 完美一致**  
> **实用 > 理论优雅**  
> **扁平 > 深度嵌套**

不追求 K8s 式的复杂结构，而是在**保持简洁的前提下实现一致性**。

## 一、统一配置结构

### 1.1 通用配置模式

所有组件配置遵循以下统一结构：

```yaml
# ============ 通用元数据（所有组件必备）============
type: <component_type>        # 组件类型：model/tool/agent/workflow/session_store/...
name: <component_name>        # 组件名称（唯一标识）
description: <description>    # 组件描述（可选）
enabled: true                 # 是否启用（默认 true）
tags: [tag1, tag2]           # 标签（可选，用于分类和查询）

# ============ 组件特定配置 ============
# 根据 type 不同，有不同的特定字段
# 但遵循统一的命名和结构约定
```

### 1.2 配置层次

```
ComponentConfig
├── type, name, description, enabled, tags  # 通用元数据
└── 组件特定字段                              # 根据类型不同
    ├── backend (对于有后端的组件)            # 统一的后端配置
    ├── provider (对于 Model)               # 统一的 provider 配置
    └── 其他特定配置
```

### 1.3 关键设计决策

#### 决策 1：扁平化 vs 嵌套化

**选择：扁平化为主，必要时嵌套**

```yaml
# ✅ 推荐：扁平化
type: agent
name: simple_assistant
model: deepseek
system_prompt: "You are helpful"
max_steps: 10

# ❌ 避免：过度嵌套
type: agent
metadata:
  name: simple_assistant
spec:
  model: deepseek
  execution:
    max_steps: 10
```

**例外**：对于复杂的子结构（如 `backend`），使用嵌套以保持清晰

#### 决策 2：统一的后端配置

对于所有 Store 类型，统一使用 `backend` 嵌套对象：

```yaml
backend:
  type: <backend_type>    # mongodb/postgres/inmemory/redis/...
  <backend_specific_fields>
```

**理由**：
- 语义清晰：后端配置独立，不污染顶层
- 可扩展：添加新后端类型不影响其他字段
- 类型安全：便于 Union 类型定义

## 二、组件类型配置规范

### 2.1 Model 配置

#### 配置结构

```yaml
type: model
name: deepseek
description: "DeepSeek model"
enabled: true
tags: [production, cost-effective]

# Provider 配置
provider: openai              # Provider 类型
model_name: deepseek-chat     # 模型名称
api_key: ${DEEPSEEK_API_KEY}  # API 密钥
base_url: https://api.deepseek.com  # API 端点（可选）

# 模型参数
temperature: 0.7
max_tokens: 8192
timeout: 60.0                 # 请求超时（可选）
```

#### Schema 定义

```python
class ModelConfig(BaseModel):
    """Model 组件配置"""
    # 通用元数据
    type: Literal["model"] = "model"
    name: str
    description: str | None = None
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    
    # Provider 配置
    provider: str  # "openai", "anthropic", "deepseek", etc.
    model_name: str
    api_key: str | None = None
    base_url: str | None = None
    
    # 模型参数
    temperature: float = 0.7
    max_tokens: int | None = None
    timeout: float | None = None
```

### 2.2 Tool 配置

#### 配置结构

```yaml
type: tool
name: web_search
description: "Web search tool"
enabled: true
tags: [search, web]

# 工具来源（二选一）
tool_name: web_search         # 内置工具名称
# 或
module: custom.tools          # 自定义工具模块
class_name: CustomTool        # 自定义工具类名

# 工具参数
params:
  max_results: 10
  timeout: 30

# 依赖注入
dependencies:
  citation_source_store: citation_store_mongodb

# 权限配置
requires_consent: false
```

#### Schema 定义

```python
class ToolConfig(BaseModel):
    """Tool 组件配置"""
    # 通用元数据
    type: Literal["tool"] = "tool"
    name: str
    description: str | None = None
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    
    # 工具来源（二选一）
    tool_name: str | None = None        # 内置工具
    module: str | None = None           # 自定义工具模块
    class_name: str | None = None       # 自定义工具类
    
    # 工具配置
    params: dict[str, Any] = Field(default_factory=dict)
    dependencies: dict[str, str] = Field(default_factory=dict)
    requires_consent: bool = False
```

### 2.3 Agent 配置

#### 配置结构

```yaml
type: agent
name: simple_assistant
description: "General assistant"
enabled: true
tags: [assistant, general]

# 核心配置
model: deepseek                      # Model 引用
system_prompt: "You are helpful"     # 系统提示词

# 工具配置
tools:
  - ls                               # 简单引用
  - file_read                        # 简单引用
  - type: agent_tool                 # Agent 作为工具
    agent: researcher
    description: "Research expert"

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

#### Schema 定义

```python
ToolReference = str | dict  # 简单引用或 RunnableToolConfig

class AgentConfig(BaseModel):
    """Agent 组件配置"""
    # 通用元数据
    type: Literal["agent"] = "agent"
    name: str
    description: str | None = None
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    
    # 核心配置
    model: str                       # Model 引用
    system_prompt: str | None = None
    
    # 工具配置
    tools: list[ToolReference] = Field(default_factory=list)
    
    # 组件引用
    memory: str | None = None
    knowledge: str | None = None
    session_store: str | None = None
    
    # 执行配置
    max_steps: int = 10
    max_tokens: int | None = None
    enable_memory_update: bool = False
    
    # 权限配置
    enable_permission: bool = False
    
    # 终止总结
    enable_termination_summary: bool = False
    termination_summary_prompt: str | None = None
```

### 2.4 Workflow 配置

#### 配置结构

```yaml
type: workflow
name: research_pipeline
description: "Research workflow"
workflow_type: pipeline           # pipeline/loop/parallel
enabled: true
tags: [workflow, research]

# Workflow 定义
stages:
  - id: analyze
    runnable: simple_assistant    # Agent/Workflow 引用
    input: "Analyze: {input}"
    condition: null               # 条件表达式（可选）
  
  - id: research
    runnable: collector
    input: "Research: {analyze.output}"

# Loop 特定配置
condition: "continue"             # Loop 条件（workflow_type=loop 时）
max_iterations: 10

# Parallel 特定配置
merge_template: "{branch1} + {branch2}"  # 合并模板（workflow_type=parallel 时）

# 组件引用
session_store: mongodb_session_store
```

#### Schema 定义

```python
class StageConfig(BaseModel):
    """Workflow Stage 配置"""
    id: str
    runnable: str | dict          # Agent/Workflow 引用或内联定义
    input: str = "{query}"
    condition: str | None = None

class WorkflowConfig(BaseModel):
    """Workflow 组件配置"""
    # 通用元数据
    type: Literal["workflow"] = "workflow"
    name: str
    description: str | None = None
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    
    # Workflow 定义
    workflow_type: Literal["pipeline", "loop", "parallel"] = "pipeline"
    stages: list[StageConfig] = Field(default_factory=list)
    
    # Loop 特定
    condition: str | None = None
    max_iterations: int = 10
    
    # Parallel 特定
    merge_template: str | None = None
    
    # 组件引用
    session_store: str | None = None
```

### 2.5 Store 配置（重点）

#### 2.5.1 统一的 Backend 结构

所有 Store 类型都使用统一的 `backend` 嵌套对象：

```yaml
backend:
  type: <backend_type>    # mongodb/postgres/inmemory/redis
  <backend_specific_fields>
```

#### 2.5.2 SessionStore 配置

```yaml
type: session_store
name: mongodb_session_store
description: "MongoDB session store"
enabled: true
tags: [storage, mongodb, session]

# 统一的后端配置
backend:
  type: mongodb
  uri: ${MONGO_URI:mongodb://localhost:27017}
  db_name: ${MONGO_DB:agio}
  collection_name: sessions       # 可选

# SessionStore 特定配置
enable_indexing: true
batch_size: 100
```

**其他后端示例**：

```yaml
# PostgreSQL
backend:
  type: postgres
  url: ${POSTGRES_URL}
  pool_size: 10
  max_overflow: 20

# InMemory
backend:
  type: inmemory
```

#### Schema 定义

```python
# Backend Specs
class BackendConfig(BaseModel):
    """后端配置基类"""
    type: str

class MongoDBBackend(BackendConfig):
    type: Literal["mongodb"] = "mongodb"
    uri: str
    db_name: str = "agio"
    collection_name: str | None = None

class PostgresBackend(BackendConfig):
    type: Literal["postgres"] = "postgres"
    url: str
    pool_size: int = 10
    max_overflow: int = 20

class InMemoryBackend(BackendConfig):
    type: Literal["inmemory"] = "inmemory"

# Union 类型
Backend = MongoDBBackend | PostgresBackend | InMemoryBackend

# SessionStore Config
class SessionStoreConfig(BaseModel):
    """SessionStore 组件配置"""
    # 通用元数据
    type: Literal["session_store"] = "session_store"
    name: str
    description: str | None = None
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    
    # 后端配置（统一）
    backend: Backend
    
    # SessionStore 特定配置
    enable_indexing: bool = True
    batch_size: int = 100
```

#### 2.5.3 TraceStore 配置

```yaml
type: trace_store
name: trace_store
description: "Trace storage"
enabled: true
tags: [observability, tracing]

# 统一的后端配置
backend:
  type: mongodb
  uri: ${MONGO_URI}
  db_name: ${MONGO_DB}
  collection_name: traces

# TraceStore 特定配置
buffer_size: 1000
flush_interval: 60
enable_persistence: true
```

#### Schema 定义

```python
class TraceStoreConfig(BaseModel):
    """TraceStore 组件配置"""
    # 通用元数据
    type: Literal["trace_store"] = "trace_store"
    name: str
    description: str | None = None
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    
    # 后端配置（统一）
    backend: Backend
    
    # TraceStore 特定配置
    buffer_size: int = 1000
    flush_interval: int = 60
    enable_persistence: bool = True
```

#### 2.5.4 CitationStore 配置

```yaml
type: citation_store
name: citation_store_mongodb
description: "Citation storage"
enabled: true
tags: [storage, citation]

# 统一的后端配置
backend:
  type: mongodb
  uri: ${MONGO_URI}
  db_name: ${MONGO_DB}
  collection_name: citations

# CitationStore 特定配置
auto_cleanup: false
cleanup_after_days: 30
```

#### Schema 定义

```python
class CitationStoreConfig(BaseModel):
    """CitationStore 组件配置"""
    # 通用元数据
    type: Literal["citation_store"] = "citation_store"
    name: str
    description: str | None = None
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    
    # 后端配置（统一）
    backend: Backend
    
    # CitationStore 特定配置
    auto_cleanup: bool = False
    cleanup_after_days: int = 30
```

### 2.6 Memory 配置（未来）

```yaml
type: memory
name: redis_memory
description: "Redis memory"
enabled: true
tags: [memory, redis]

# 统一的后端配置
backend:
  type: redis
  host: localhost
  port: 6379
  db: 0
  password: ${REDIS_PASSWORD}

# Memory 特定配置
ttl: 3600
max_size: 1000
```

### 2.7 Knowledge 配置（未来）

```yaml
type: knowledge
name: chroma_kb
description: "Chroma knowledge base"
enabled: true
tags: [knowledge, vector]

# 统一的后端配置
backend:
  type: chroma
  host: localhost
  port: 8000
  collection_name: documents

# Knowledge 特定配置
embedding_model: text-embedding-3-small
chunk_size: 512
chunk_overlap: 50
```

## 三、统一抽象设计

### 3.1 Backend 抽象

#### 设计原则

1. **统一接口**：所有后端遵循统一的配置结构
2. **类型区分**：使用 `type` 字段区分不同后端
3. **按需字段**：只包含必要字段，避免冗余

#### 代码结构

```python
# agio/config/backends.py

from typing import Literal
from pydantic import BaseModel, Field

class BackendConfig(BaseModel):
    """后端配置基类"""
    type: str

# ========== 数据库后端 ==========

class MongoDBBackend(BackendConfig):
    """MongoDB 后端配置"""
    type: Literal["mongodb"] = "mongodb"
    uri: str = Field(..., description="MongoDB connection URI")
    db_name: str = Field(default="agio", description="Database name")
    collection_name: str | None = Field(default=None, description="Collection name (optional)")

class PostgresBackend(BackendConfig):
    """PostgreSQL 后端配置"""
    type: Literal["postgres"] = "postgres"
    url: str = Field(..., description="PostgreSQL connection URL")
    pool_size: int = Field(default=10, ge=1, description="Connection pool size")
    max_overflow: int = Field(default=20, ge=0, description="Max overflow connections")

# ========== 缓存后端 ==========

class RedisBackend(BackendConfig):
    """Redis 后端配置"""
    type: Literal["redis"] = "redis"
    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
    db: int = Field(default=0, ge=0, description="Redis database number")
    password: str | None = Field(default=None, description="Redis password")

# ========== 内存后端 ==========

class InMemoryBackend(BackendConfig):
    """InMemory 后端配置"""
    type: Literal["inmemory"] = "inmemory"

# ========== 向量数据库后端 ==========

class ChromaBackend(BackendConfig):
    """Chroma 后端配置"""
    type: Literal["chroma"] = "chroma"
    host: str = Field(default="localhost", description="Chroma host")
    port: int = Field(default=8000, description="Chroma port")
    collection_name: str = Field(..., description="Collection name")

class PineconeBackend(BackendConfig):
    """Pinecone 后端配置"""
    type: Literal["pinecone"] = "pinecone"
    api_key: str = Field(..., description="Pinecone API key")
    environment: str = Field(..., description="Pinecone environment")
    index_name: str = Field(..., description="Index name")

# ========== Union 类型 ==========

# 存储后端（用于 Store 类型）
StorageBackend = MongoDBBackend | PostgresBackend | InMemoryBackend

# 缓存后端（用于 Memory 类型）
CacheBackend = RedisBackend | InMemoryBackend

# 向量后端（用于 Knowledge 类型）
VectorBackend = ChromaBackend | PineconeBackend
```

### 3.2 组件配置基类

```python
# agio/config/base.py

from typing import Literal
from pydantic import BaseModel, Field

class ComponentConfig(BaseModel):
    """组件配置基类 - 所有组件配置的共同字段"""
    
    # 通用元数据（必备）
    type: str = Field(..., description="Component type")
    name: str = Field(..., description="Component name (unique identifier)")
    
    # 通用元数据（可选）
    description: str | None = Field(default=None, description="Component description")
    enabled: bool = Field(default=True, description="Whether the component is enabled")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    
    class Config:
        extra = "forbid"  # 禁止额外字段，提高安全性
```

### 3.3 配置访问便利性

为 Store 配置提供便捷访问方法：

```python
class SessionStoreConfig(ComponentConfig):
    type: Literal["session_store"] = "session_store"
    backend: StorageBackend
    enable_indexing: bool = True
    batch_size: int = 100
    
    # 便捷访问方法
    def get_backend_type(self) -> str:
        """获取后端类型"""
        return self.backend.type
    
    def is_mongodb(self) -> bool:
        """是否为 MongoDB 后端"""
        return self.backend.type == "mongodb"
    
    def is_postgres(self) -> bool:
        """是否为 PostgreSQL 后端"""
        return self.backend.type == "postgres"
```

## 四、Builder 适配

### 4.1 统一的 Builder 接口

```python
class ComponentBuilder(ABC):
    """组件构建器基类"""
    
    @abstractmethod
    async def build(self, config: ComponentConfig, dependencies: dict[str, Any]) -> Any:
        """构建组件实例"""
        pass
    
    async def cleanup(self, instance: Any) -> None:
        """清理组件资源"""
        if hasattr(instance, "cleanup"):
            await instance.cleanup()
```

### 4.2 SessionStoreBuilder 示例

```python
class SessionStoreBuilder(ComponentBuilder):
    """SessionStore 构建器"""
    
    async def build(
        self, config: SessionStoreConfig, dependencies: dict[str, Any]
    ) -> Any:
        backend = config.backend
        
        # 根据后端类型构建
        if backend.type == "mongodb":
            from agio.providers.storage import MongoSessionStore
            store = MongoSessionStore(
                uri=backend.uri,
                db_name=backend.db_name,
                collection_name=backend.collection_name or "sessions",
            )
            await store.connect()
            return store
        
        elif backend.type == "postgres":
            from agio.providers.storage import PostgresSessionStore
            store = PostgresSessionStore(
                url=backend.url,
                pool_size=backend.pool_size,
                max_overflow=backend.max_overflow,
            )
            await store.connect()
            return store
        
        elif backend.type == "inmemory":
            from agio.providers.storage import InMemorySessionStore
            return InMemorySessionStore()
        
        else:
            raise ComponentBuildError(f"Unknown backend type: {backend.type}")
```

## 五、配置加载和解析

### 5.1 统一的配置解析

```python
class ConfigLoader:
    """配置加载器"""
    
    CONFIG_CLASSES = {
        "model": ModelConfig,
        "tool": ToolConfig,
        "agent": AgentConfig,
        "workflow": WorkflowConfig,
        "session_store": SessionStoreConfig,
        "trace_store": TraceStoreConfig,
        "citation_store": CitationStoreConfig,
        "memory": MemoryConfig,
        "knowledge": KnowledgeConfig,
    }
    
    def parse_config(self, config_dict: dict) -> ComponentConfig:
        """解析配置字典为配置对象"""
        config_type = config_dict.get("type")
        if not config_type:
            raise ConfigError("Missing 'type' field")
        
        config_class = self.CONFIG_CLASSES.get(config_type)
        if not config_class:
            raise ConfigError(f"Unknown config type: {config_type}")
        
        return config_class(**config_dict)
```

### 5.2 环境变量支持

所有配置文件支持环境变量替换：

```yaml
# 语法：${VAR_NAME:default_value}
backend:
  type: mongodb
  uri: ${MONGO_URI:mongodb://localhost:27017}
  db_name: ${MONGO_DB:agio}
```

## 六、迁移计划

### 6.1 迁移策略

**原则**：一次性迁移，不做向后兼容

**步骤**：

1. **Phase 1: Backend 抽象**
   - 创建 `agio/config/backends.py`
   - 定义所有 Backend 配置类

2. **Phase 2: Store 配置重构**
   - 更新 `SessionStoreConfig`、`TraceStoreConfig`、`CitationStoreConfig`
   - 更新对应的 Builder
   - 迁移所有 Store 配置文件

3. **Phase 3: 其他组件统一**
   - 检查 Model、Tool、Agent、Workflow 配置
   - 确保所有组件遵循统一的元数据字段
   - 补充缺失的字段（如 `description`、`tags`）

4. **Phase 4: 测试和文档**
   - 更新单元测试
   - 更新配置文档
   - 提供配置示例

### 6.2 配置文件迁移示例

#### SessionStore 迁移

**旧格式**：
```yaml
type: session_store
name: mongodb_session_store
description: "MongoDB session store"
store_type: mongodb
mongo_uri: ${MONGO_URI:mongodb://localhost:27017}
mongo_db_name: ${MONGO_DB:agio}
enabled: true
tags: [persistence, mongodb]
```

**新格式**：
```yaml
type: session_store
name: mongodb_session_store
description: "MongoDB session store"
enabled: true
tags: [persistence, mongodb]

backend:
  type: mongodb
  uri: ${MONGO_URI:mongodb://localhost:27017}
  db_name: ${MONGO_DB:agio}

enable_indexing: true
batch_size: 100
```

#### TraceStore 迁移

**旧格式**：
```yaml
type: trace_store
name: trace_store
enabled: true
mongo_uri: ${MONGO_URI}
mongo_db_name: ${MONGO_DB}
buffer_size: 1000
flush_interval: 60
```

**新格式**：
```yaml
type: trace_store
name: trace_store
description: "Trace storage for observability"
enabled: true
tags: [observability, tracing]

backend:
  type: mongodb
  uri: ${MONGO_URI}
  db_name: ${MONGO_DB}
  collection_name: traces

buffer_size: 1000
flush_interval: 60
enable_persistence: true
```

### 6.3 迁移工具脚本

提供自动化迁移脚本：

```python
# scripts/migrate_configs.py

def migrate_store_config(old_config: dict) -> dict:
    """迁移 Store 配置到新格式"""
    new_config = {
        "type": old_config["type"],
        "name": old_config["name"],
        "description": old_config.get("description", ""),
        "enabled": old_config.get("enabled", True),
        "tags": old_config.get("tags", []),
    }
    
    # 提取后端配置
    if "store_type" in old_config or "mongo_uri" in old_config:
        backend_type = old_config.get("store_type", "mongodb")
        backend = {"type": backend_type}
        
        if backend_type == "mongodb":
            backend["uri"] = old_config.get("mongo_uri")
            backend["db_name"] = old_config.get("mongo_db_name", "agio")
        elif backend_type == "postgres":
            backend["url"] = old_config.get("postgres_url")
        
        new_config["backend"] = backend
    
    # 提取特定配置
    if old_config["type"] == "session_store":
        new_config["enable_indexing"] = True
        new_config["batch_size"] = 100
    elif old_config["type"] == "trace_store":
        new_config["buffer_size"] = old_config.get("buffer_size", 1000)
        new_config["flush_interval"] = old_config.get("flush_interval", 60)
        new_config["enable_persistence"] = True
    
    return new_config
```

## 七、一致性检查清单

### 7.1 配置文件一致性

所有配置文件必须包含：

- ✅ `type` 字段
- ✅ `name` 字段
- ✅ `enabled` 字段（默认 true）
- ✅ `tags` 字段（可为空）
- ✅ `description` 字段（推荐）

### 7.2 Backend 配置一致性

所有 Store 类型必须：

- ✅ 使用 `backend` 嵌套对象
- ✅ `backend.type` 字段指定后端类型
- ✅ 后端特定字段统一命名（`uri`, `db_name`, `url`, 等）

### 7.3 Schema 定义一致性

所有 Config 类必须：

- ✅ 继承自 `ComponentConfig`（或直接实现相同字段）
- ✅ 使用 `Literal` 类型约束 `type` 字段
- ✅ 使用 `Field` 提供描述和默认值
- ✅ 设置 `extra = "forbid"` 禁止额外字段

## 八、优势总结

### 8.1 一致性

- ✅ 所有组件遵循统一的配置结构
- ✅ Store 类型统一使用 `backend` 配置
- ✅ 元数据字段完全一致

### 8.2 易用性

- ✅ 扁平化设计，易于阅读和编写
- ✅ 清晰的字段命名，降低心智负担
- ✅ 环境变量支持，便于不同环境配置

### 8.3 可扩展性

- ✅ 添加新后端只需定义新的 Backend 类
- ✅ 添加新组件类型遵循统一模式
- ✅ Union 类型支持类型安全的多态

### 8.4 类型安全

- ✅ Pydantic 提供完整的运行时验证
- ✅ Literal 类型约束字段值
- ✅ Union 类型支持多态配置

## 九、最佳实践

### 9.1 配置组织

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

### 9.2 命名规范

- **组件名称**：小写下划线，描述性强（`mongodb_session_store`）
- **后端类型**：小写，简洁（`mongodb`, `postgres`, `inmemory`）
- **字段名称**：小写下划线（`enable_indexing`, `batch_size`）

### 9.3 环境变量

- **格式**：`${VAR_NAME:default_value}`
- **命名**：大写下划线，带前缀（`AGIO_MONGO_URI`）
- **敏感信息**：API 密钥、数据库密码等必须使用环境变量

### 9.4 配置验证

- 使用 Pydantic 的 `Field` 提供约束（`ge`, `le`, `min_length` 等）
- 使用 `validator` 或 `model_validator` 自定义验证逻辑
- 在配置加载时立即验证，Fail Fast

## 十、总结

本方案在**保持简洁扁平化**的前提下，实现了配置系统的**完全一致性**：

1. **统一的元数据**：所有组件都有 `type`, `name`, `description`, `enabled`, `tags`
2. **统一的后端抽象**：所有 Store 使用 `backend` 嵌套对象
3. **统一的配置模式**：所有组件遵循相同的结构约定
4. **类型安全**：Pydantic + Union 类型提供完整的类型检查

**核心价值**：
- 降低用户心智负担（一通百通）
- 提高系统可维护性（统一抽象）
- 保证类型安全（编译时检查）
- 易于扩展（添加新类型遵循统一模式）
