# Agio 配置系统详细设计

> **目标**：打造开源易用的万星 Agent 配置系统 - 让开发者通过声明式配置快速构建、调试和部署 Agent

## 📋 目录

1. [设计理念](#设计理念)
2. [核心架构](#核心架构)
3. [配置 Schema 设计](#配置-schema-设计)
4. [组件注册表](#组件注册表)
5. [配置加载器](#配置加载器)
6. [组件工厂](#组件工厂)
7. [插件系统](#插件系统)
8. [验证与错误处理](#验证与错误处理)
9. [最佳实践](#最佳实践)
10. [实现路线图](#实现路线图)

---

## 设计理念

### 核心原则

1. **声明式优先** - 配置即文档，YAML 配置应该自解释
2. **类型安全** - 利用 Pydantic 提供完整的类型检查和验证
3. **渐进式增强** - 支持从简单到复杂的配置方式
4. **插件化** - 易于扩展，支持第三方组件
5. **开发者友好** - 清晰的错误信息，丰富的示例

### 设计目标

- ✅ **零代码创建 Agent** - 纯配置即可运行
- ✅ **热重载** - 修改配置后自动重新加载
- ✅ **配置复用** - 通过引用和继承减少重复
- ✅ **环境隔离** - 支持 dev/staging/prod 多环境配置
- ✅ **配置验证** - 启动前发现所有配置错误
- ✅ **IDE 支持** - 提供 JSON Schema 实现自动补全

---

## 核心架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     Configuration Layer                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │ YAML Files   │─────▶│ ConfigLoader │─────▶│ Validator │ │
│  └──────────────┘      └──────────────┘      └───────────┘ │
│         │                      │                     │       │
│         │                      ▼                     ▼       │
│         │              ┌──────────────┐      ┌───────────┐ │
│         │              │ Schema Models│      │  Errors   │ │
│         │              └──────────────┘      └───────────┘ │
│         │                      │                            │
│         ▼                      ▼                            │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │ Environment  │      │   Registry   │                    │
│  │  Variables   │      │  (In-Memory) │                    │
│  └──────────────┘      └──────────────┘                    │
│                                │                            │
│                                ▼                            │
│                        ┌──────────────┐                    │
│                        │   Factory    │                    │
│                        └──────────────┘                    │
│                                │                            │
└────────────────────────────────┼────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  Component Instances   │
                    │  (Agent, Model, etc.)  │
                    └────────────────────────┘
```

### 模块职责

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **ConfigLoader** | 读取和解析 YAML 文件 | YAML 文件路径 | 原始配置字典 |
| **Validator** | 验证配置结构和类型 | 配置字典 | Pydantic 模型 |
| **Registry** | 管理组件注册和查找 | 组件 ID | 组件实例/配置 |
| **Factory** | 根据配置创建组件实例 | 配置模型 | 组件实例 |
| **PluginManager** | 加载和管理插件 | 插件路径 | 插件实例 |

---

## 配置 Schema 设计

### 1. 基础配置模型

```python
# agio/registry/models.py

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

class ComponentType(str, Enum):
    """组件类型枚举"""
    MODEL = "model"
    AGENT = "agent"
    TOOL = "tool"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    HOOK = "hook"

class BaseComponentConfig(BaseModel):
    """所有组件配置的基类"""
    
    # 必填字段
    type: ComponentType = Field(description="组件类型")
    name: str = Field(description="组件唯一标识符")
    
    # 可选字段
    description: str | None = Field(default=None, description="组件描述")
    enabled: bool = Field(default=True, description="是否启用")
    tags: list[str] = Field(default_factory=list, description="标签")
    metadata: dict[str, Any] = Field(default_factory=dict, description="自定义元数据")
    
    # 继承支持
    extends: str | None = Field(default=None, description="继承的配置名称")
    
    class Config:
        extra = "forbid"  # 禁止额外字段
        use_enum_values = True
```

### 2. Model 配置

```python
class ModelProvider(str, Enum):
    """支持的模型提供商"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    CUSTOM = "custom"

class ModelConfig(BaseComponentConfig):
    """Model 组件配置"""
    
    type: Literal[ComponentType.MODEL] = ComponentType.MODEL
    
    # 提供商配置
    provider: ModelProvider = Field(description="模型提供商")
    model: str = Field(description="模型名称，如 gpt-4-turbo-preview")
    
    # API 配置
    api_key: str | None = Field(default=None, description="API Key，支持 ${ENV_VAR}")
    api_base: str | None = Field(default=None, description="API Base URL")
    
    # 模型参数
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    
    # 高级配置
    timeout: int = Field(default=60, description="请求超时（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")
    
    # 自定义提供商
    custom_class: str | None = Field(
        default=None, 
        description="自定义 Model 类路径，如 'mypackage.MyModel'"
    )
    custom_params: dict[str, Any] = Field(
        default_factory=dict,
        description="传递给自定义类的参数"
    )
    
    @field_validator("api_key", "api_base")
    @classmethod
    def resolve_env_vars(cls, v: str | None) -> str | None:
        """解析环境变量引用"""
        if v and v.startswith("${") and v.endswith("}"):
            import os
            env_var = v[2:-1]
            return os.getenv(env_var)
        return v
```

### 3. Agent 配置

```python
class AgentConfig(BaseComponentConfig):
    """Agent 组件配置"""
    
    type: Literal[ComponentType.AGENT] = ComponentType.AGENT
    
    # 核心组件引用
    model: str = Field(description="Model 引用，如 'gpt4' 或 'ref:gpt4'")
    tools: list[str] = Field(default_factory=list, description="Tool 引用列表")
    memory: str | None = Field(default=None, description="Memory 引用")
    knowledge: str | None = Field(default=None, description="Knowledge 引用")
    hooks: list[str] = Field(default_factory=list, description="Hook 引用列表")
    
    # Agent 配置
    system_prompt: str | None = Field(default=None, description="系统提示词")
    system_prompt_file: str | None = Field(
        default=None, 
        description="系统提示词文件路径"
    )
    
    # 执行配置
    max_steps: int = Field(default=10, ge=1, description="最大执行步数")
    enable_memory_update: bool = Field(default=True, description="是否更新记忆")
    
    # 存储配置
    storage: str | None = Field(default=None, description="Storage 引用")
    repository: str | None = Field(default=None, description="Repository 引用")
    
    @field_validator("system_prompt_file")
    @classmethod
    def load_prompt_file(cls, v: str | None) -> str | None:
        """从文件加载系统提示词"""
        if v:
            from pathlib import Path
            return Path(v).read_text(encoding="utf-8")
        return None
```

### 4. Tool 配置

```python
class ToolType(str, Enum):
    """Tool 类型"""
    FUNCTION = "function"
    CLASS = "class"
    MCP = "mcp"

class ToolConfig(BaseComponentConfig):
    """Tool 组件配置"""
    
    type: Literal[ComponentType.TOOL] = ComponentType.TOOL
    tool_type: ToolType = Field(description="Tool 实现类型")
    
    # Function Tool
    function_path: str | None = Field(
        default=None,
        description="函数路径，如 'mypackage.my_function'"
    )
    
    # Class Tool
    class_path: str | None = Field(
        default=None,
        description="类路径，如 'mypackage.MyTool'"
    )
    class_params: dict[str, Any] = Field(
        default_factory=dict,
        description="类初始化参数"
    )
    
    # MCP Tool
    mcp_server: str | None = Field(default=None, description="MCP 服务器名称")
    mcp_tool_name: str | None = Field(default=None, description="MCP Tool 名称")
    
    # Tool Schema (可选，用于覆盖自动生成的 schema)
    schema_override: dict[str, Any] | None = Field(
        default=None,
        description="覆盖自动生成的 Tool Schema"
    )
```

### 5. Memory 配置

```python
class MemoryConfig(BaseComponentConfig):
    """Memory 组件配置"""
    
    type: Literal[ComponentType.MEMORY] = ComponentType.MEMORY
    
    # 实现类
    class_path: str = Field(description="Memory 类路径")
    
    # 通用配置
    max_history_length: int = Field(default=10, description="最大历史长度")
    max_tokens: int | None = Field(default=None, description="最大 Token 数")
    
    # 向量存储配置（用于语义记忆）
    vector_store: str | None = Field(default=None, description="向量存储引用")
    embedding_model: str | None = Field(default=None, description="Embedding 模型")
    
    # 自定义参数
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="传递给 Memory 类的参数"
    )
```

### 6. Knowledge 配置

```python
class KnowledgeConfig(BaseComponentConfig):
    """Knowledge 组件配置"""
    
    type: Literal[ComponentType.KNOWLEDGE] = ComponentType.KNOWLEDGE
    
    # 实现类
    class_path: str = Field(description="Knowledge 类路径")
    
    # 向量存储配置
    vector_store: str = Field(description="向量存储引用")
    embedding_model: str = Field(description="Embedding 模型")
    
    # 检索配置
    top_k: int = Field(default=5, description="返回结果数量")
    similarity_threshold: float = Field(default=0.7, description="相似度阈值")
    
    # 数据源
    data_sources: list[str] = Field(
        default_factory=list,
        description="数据源路径列表"
    )
    
    # 自定义参数
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="传递给 Knowledge 类的参数"
    )
```

---

## 配置文件示例

### 示例 1: 简单 Agent 配置

```yaml
# configs/agents/simple_assistant.yaml
type: agent
name: simple_assistant
description: "A simple helpful assistant"

model: gpt4  # 引用已注册的 model
system_prompt: "You are a helpful assistant."

tags:
  - assistant
  - general
```

### 示例 2: 完整 Agent 配置

```yaml
# configs/agents/customer_support.yaml
type: agent
name: customer_support
description: "Customer support agent with tools and memory"

# 组件引用
model: gpt4
tools:
  - search_knowledge_base
  - create_ticket
  - send_email
memory: redis_memory
knowledge: product_docs

# 系统提示词
system_prompt_file: "./prompts/customer_support.txt"

# 执行配置
max_steps: 15
enable_memory_update: true

# 存储
repository: mongodb_repo

# 元数据
tags:
  - customer-support
  - production
metadata:
  team: "support"
  version: "2.0"
```

### 示例 3: Model 配置

```yaml
# configs/models/gpt4.yaml
type: model
name: gpt4
description: "GPT-4 Turbo Preview"

provider: openai
model: gpt-4-turbo-preview

# API 配置（使用环境变量）
api_key: ${OPENAI_API_KEY}
api_base: ${OPENAI_API_BASE}  # 可选

# 模型参数
temperature: 0.7
max_tokens: 4096
top_p: 0.9

# 高级配置
timeout: 120
max_retries: 3

tags:
  - openai
  - gpt4
```

### 示例 4: 自定义 Model

```yaml
# configs/models/custom_llm.yaml
type: model
name: custom_llm
description: "Custom LLM implementation"

provider: custom
custom_class: "mycompany.models.CustomLLM"
custom_params:
  endpoint: "https://api.mycompany.com/v1/chat"
  auth_token: ${CUSTOM_LLM_TOKEN}
  model_version: "v2.5"

temperature: 0.8
max_tokens: 2048
```

### 示例 5: Tool 配置

```yaml
# configs/tools/web_search.yaml
type: tool
name: web_search
description: "Search the web using Google"

tool_type: class
class_path: "agio.tools.WebSearchTool"
class_params:
  api_key: ${GOOGLE_API_KEY}
  search_engine_id: ${GOOGLE_SEARCH_ENGINE_ID}
  max_results: 5

tags:
  - search
  - web
```

### 示例 6: 配置继承

```yaml
# configs/models/gpt4_base.yaml
type: model
name: gpt4_base
provider: openai
model: gpt-4-turbo-preview
api_key: ${OPENAI_API_KEY}
temperature: 0.7
max_tokens: 4096
```

```yaml
# configs/models/gpt4_creative.yaml
type: model
name: gpt4_creative
extends: gpt4_base  # 继承 gpt4_base

# 只覆盖需要修改的字段
temperature: 1.2
top_p: 0.95

tags:
  - creative
```

---

## 组件注册表

### Registry 架构

```python
# agio/registry/base.py

from typing import TypeVar, Generic, Type
from collections import defaultdict
import threading

T = TypeVar('T')

class ComponentRegistry(Generic[T]):
    """
    组件注册表 - 线程安全的组件管理
    
    职责：
    1. 注册和存储组件实例/配置
    2. 按类型、名称、标签查询组件
    3. 支持热重载
    4. 依赖关系管理
    """
    
    def __init__(self):
        self._components: dict[str, T] = {}
        self._configs: dict[str, BaseComponentConfig] = {}
        self._type_index: dict[ComponentType, set[str]] = defaultdict(set)
        self._tag_index: dict[str, set[str]] = defaultdict(set)
        self._lock = threading.RLock()
    
    def register(
        self, 
        name: str, 
        component: T, 
        config: BaseComponentConfig
    ) -> None:
        """注册组件"""
        with self._lock:
            self._components[name] = component
            self._configs[name] = config
            self._type_index[config.type].add(name)
            for tag in config.tags:
                self._tag_index[tag].add(name)
    
    def get(self, name: str) -> T | None:
        """获取组件实例"""
        return self._components.get(name)
    
    def get_config(self, name: str) -> BaseComponentConfig | None:
        """获取组件配置"""
        return self._configs.get(name)
    
    def list_by_type(self, component_type: ComponentType) -> list[str]:
        """按类型列出组件"""
        return list(self._type_index.get(component_type, set()))
    
    def list_by_tag(self, tag: str) -> list[str]:
        """按标签列出组件"""
        return list(self._tag_index.get(tag, set()))
    
    def unregister(self, name: str) -> None:
        """注销组件"""
        with self._lock:
            if name in self._components:
                config = self._configs[name]
                del self._components[name]
                del self._configs[name]
                self._type_index[config.type].discard(name)
                for tag in config.tags:
                    self._tag_index[tag].discard(name)
    
    def reload(self, name: str, component: T, config: BaseComponentConfig) -> None:
        """重新加载组件"""
        self.unregister(name)
        self.register(name, component, config)
    
    def exists(self, name: str) -> bool:
        """检查组件是否存在"""
        return name in self._components
    
    def list_all(self) -> list[str]:
        """列出所有组件名称"""
        return list(self._components.keys())


# 全局注册表实例
_global_registry = ComponentRegistry()

def get_registry() -> ComponentRegistry:
    """获取全局注册表"""
    return _global_registry
```

---

## 配置加载器

### Loader 实现

```python
# agio/registry/loader.py

import os
import yaml
from pathlib import Path
from typing import Any
from .models import BaseComponentConfig, ComponentType

class ConfigLoader:
    """
    配置加载器
    
    职责：
    1. 读取 YAML 文件
    2. 解析环境变量引用
    3. 处理配置继承
    4. 验证配置结构
    """
    
    def __init__(self, config_dir: str | Path):
        self.config_dir = Path(config_dir)
        self._cache: dict[str, dict] = {}
    
    def load(self, config_path: str | Path) -> dict[str, Any]:
        """加载配置文件"""
        path = Path(config_path)
        if not path.is_absolute():
            path = self.config_dir / path
        
        # 检查缓存
        cache_key = str(path)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 读取 YAML
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 解析环境变量
        config = self._resolve_env_vars(config)
        
        # 处理继承
        if 'extends' in config:
            config = self._resolve_inheritance(config)
        
        # 缓存
        self._cache[cache_key] = config
        return config
    
    def load_directory(self, component_type: ComponentType | None = None) -> dict[str, dict]:
        """加载目录下的所有配置"""
        configs = {}
        
        # 确定搜索路径
        if component_type:
            search_dir = self.config_dir / f"{component_type.value}s"
        else:
            search_dir = self.config_dir
        
        # 遍历 YAML 文件
        for yaml_file in search_dir.rglob("*.yaml"):
            try:
                config = self.load(yaml_file)
                name = config.get('name')
                if name:
                    configs[name] = config
            except Exception as e:
                print(f"Warning: Failed to load {yaml_file}: {e}")
        
        return configs
    
    def _resolve_env_vars(self, config: Any) -> Any:
        """递归解析环境变量引用"""
        if isinstance(config, dict):
            return {k: self._resolve_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._resolve_env_vars(item) for item in config]
        elif isinstance(config, str):
            if config.startswith("${") and config.endswith("}"):
                env_var = config[2:-1]
                value = os.getenv(env_var)
                if value is None:
                    raise ValueError(f"Environment variable {env_var} not found")
                return value
        return config
    
    def _resolve_inheritance(self, config: dict) -> dict:
        """处理配置继承"""
        extends = config.pop('extends')
        
        # 加载父配置
        parent_path = self.config_dir / f"{extends}.yaml"
        if not parent_path.exists():
            # 尝试按类型查找
            component_type = config.get('type')
            if component_type:
                parent_path = self.config_dir / f"{component_type}s" / f"{extends}.yaml"
        
        if not parent_path.exists():
            raise ValueError(f"Parent config '{extends}' not found")
        
        parent_config = self.load(parent_path)
        
        # 合并配置（子配置覆盖父配置）
        merged = {**parent_config, **config}
        return merged
    
    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache.clear()
```

---

## 组件工厂

### Factory 实现

```python
# agio/registry/factory.py

from typing import Any
from importlib import import_module
from .models import (
    BaseComponentConfig, 
    ModelConfig, 
    AgentConfig, 
    ToolConfig,
    MemoryConfig,
    KnowledgeConfig
)
from agio.models.base import Model
from agio.agent.base import Agent
from agio.tools.base import Tool
from agio.memory.base import Memory
from agio.knowledge.base import Knowledge

class ComponentFactory:
    """
    组件工厂
    
    职责：
    1. 根据配置创建组件实例
    2. 解析组件引用
    3. 处理依赖注入
    """
    
    def __init__(self, registry):
        self.registry = registry
    
    def create(self, config: BaseComponentConfig) -> Any:
        """根据配置创建组件"""
        if isinstance(config, ModelConfig):
            return self.create_model(config)
        elif isinstance(config, AgentConfig):
            return self.create_agent(config)
        elif isinstance(config, ToolConfig):
            return self.create_tool(config)
        elif isinstance(config, MemoryConfig):
            return self.create_memory(config)
        elif isinstance(config, KnowledgeConfig):
            return self.create_knowledge(config)
        else:
            raise ValueError(f"Unsupported config type: {type(config)}")
    
    def create_model(self, config: ModelConfig) -> Model:
        """创建 Model 实例"""
        if config.provider == "custom":
            # 自定义 Model
            model_class = self._import_class(config.custom_class)
            return model_class(
                id=f"{config.provider}/{config.model}",
                name=config.name,
                **config.custom_params
            )
        
        # 内置 Model
        provider_map = {
            "openai": "agio.models.openai.OpenAIModel",
            "deepseek": "agio.models.deepseek.DeepSeekModel",
        }
        
        model_class_path = provider_map.get(config.provider)
        if not model_class_path:
            raise ValueError(f"Unsupported provider: {config.provider}")
        
        model_class = self._import_class(model_class_path)
        
        return model_class(
            id=f"{config.provider}/{config.model}",
            name=config.name,
            model=config.model,
            api_key=config.api_key,
            base_url=config.api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
        )
    
    def create_agent(self, config: AgentConfig) -> Agent:
        """创建 Agent 实例"""
        # 解析 Model 引用
        model = self._resolve_reference(config.model, Model)
        
        # 解析 Tools 引用
        tools = [
            self._resolve_reference(tool_ref, Tool)
            for tool_ref in config.tools
        ]
        
        # 解析 Memory 引用
        memory = None
        if config.memory:
            memory = self._resolve_reference(config.memory, Memory)
        
        # 解析 Knowledge 引用
        knowledge = None
        if config.knowledge:
            knowledge = self._resolve_reference(config.knowledge, Knowledge)
        
        # 加载系统提示词
        system_prompt = config.system_prompt
        if config.system_prompt_file:
            from pathlib import Path
            system_prompt = Path(config.system_prompt_file).read_text()
        
        return Agent(
            model=model,
            tools=tools,
            memory=memory,
            knowledge=knowledge,
            name=config.name,
            system_prompt=system_prompt,
        )
    
    def create_tool(self, config: ToolConfig) -> Tool:
        """创建 Tool 实例"""
        if config.tool_type == "function":
            # Function Tool
            func = self._import_function(config.function_path)
            from agio.tools import tool
            return tool(func)
        
        elif config.tool_type == "class":
            # Class Tool
            tool_class = self._import_class(config.class_path)
            return tool_class(**config.class_params)
        
        elif config.tool_type == "mcp":
            # MCP Tool
            from agio.tools.mcp import MCPTool
            return MCPTool.from_server(
                config.mcp_server,
                config.mcp_tool_name
            )
        
        raise ValueError(f"Unsupported tool_type: {config.tool_type}")
    
    def create_memory(self, config: MemoryConfig) -> Memory:
        """创建 Memory 实例"""
        memory_class = self._import_class(config.class_path)
        return memory_class(**config.params)
    
    def create_knowledge(self, config: KnowledgeConfig) -> Knowledge:
        """创建 Knowledge 实例"""
        knowledge_class = self._import_class(config.class_path)
        
        # 解析向量存储引用
        vector_store = self._resolve_reference(config.vector_store, Any)
        
        return knowledge_class(
            vector_store=vector_store,
            embedding_model=config.embedding_model,
            top_k=config.top_k,
            **config.params
        )
    
    def _resolve_reference(self, ref: str, expected_type: type) -> Any:
        """解析组件引用"""
        # 支持两种格式：
        # 1. 直接名称: "gpt4"
        # 2. 显式引用: "ref:gpt4"
        
        if ref.startswith("ref:"):
            ref = ref[4:]
        
        component = self.registry.get(ref)
        if component is None:
            # FIXME: 未找到组件时，应该尝试加载并注册？而不是直接报错
            raise ValueError(f"Component '{ref}' not found in registry")
        
        if not isinstance(component, expected_type):
            raise TypeError(
                f"Component '{ref}' is {type(component)}, "
                f"expected {expected_type}"
            )
        
        return component
    
    def _import_class(self, class_path: str) -> type:
        """动态导入类"""
        module_path, class_name = class_path.rsplit('.', 1)
        module = import_module(module_path)
        return getattr(module, class_name)
    
    def _import_function(self, func_path: str):
        """动态导入函数"""
        module_path, func_name = func_path.rsplit('.', 1)
        module = import_module(module_path)
        return getattr(module, func_name)
```

---

## 插件系统

### 插件接口

```python
# agio/registry/plugins.py

from abc import ABC, abstractmethod
from typing import Any

class ConfigPlugin(ABC):
    """配置插件基类"""
    
    @abstractmethod
    def get_name(self) -> str:
        """插件名称"""
        pass
    
    @abstractmethod
    def get_component_types(self) -> list[str]:
        """支持的组件类型"""
        pass
    
    @abstractmethod
    def create_component(self, config: dict[str, Any]) -> Any:
        """创建组件实例"""
        pass
    
    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> bool:
        """验证配置"""
        pass


class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self._plugins: dict[str, ConfigPlugin] = {}
    
    def register_plugin(self, plugin: ConfigPlugin) -> None:
        """注册插件"""
        name = plugin.get_name()
        self._plugins[name] = plugin
    
    def get_plugin(self, name: str) -> ConfigPlugin | None:
        """获取插件"""
        return self._plugins.get(name)
    
    def list_plugins(self) -> list[str]:
        """列出所有插件"""
        return list(self._plugins.keys())
    
    def load_from_directory(self, plugin_dir: str) -> None:
        """从目录加载插件"""
        from pathlib import Path
        import importlib.util
        
        for plugin_file in Path(plugin_dir).glob("*.py"):
            spec = importlib.util.spec_from_file_location(
                plugin_file.stem, 
                plugin_file
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找插件类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, ConfigPlugin) and 
                    attr is not ConfigPlugin):
                    plugin = attr()
                    self.register_plugin(plugin)
```

### 插件示例

```python
# plugins/langchain_plugin.py

from agio.registry.plugins import ConfigPlugin

class LangChainPlugin(ConfigPlugin):
    """LangChain 集成插件"""
    
    def get_name(self) -> str:
        return "langchain"
    
    def get_component_types(self) -> list[str]:
        return ["tool", "memory", "knowledge"]
    
    def create_component(self, config: dict) -> Any:
        component_type = config.get("type")
        
        if component_type == "tool":
            # 从 LangChain Tool 创建 Agio Tool
            from langchain.tools import load_tool
            lc_tool = load_tool(config["langchain_tool_name"])
            return self._wrap_langchain_tool(lc_tool)
        
        # ... 其他类型
    
    def validate_config(self, config: dict) -> bool:
        return "langchain_tool_name" in config
    
    def _wrap_langchain_tool(self, lc_tool):
        """将 LangChain Tool 包装为 Agio Tool"""
        # 实现包装逻辑
        pass
```

---

## 验证与错误处理

### 配置验证器

```python
# agio/registry/validator.py

from typing import Any
from pydantic import ValidationError
from .models import BaseComponentConfig, ComponentType

class ConfigValidator:
    """配置验证器"""
    
    CONFIG_MODEL_MAP = {
        ComponentType.MODEL: ModelConfig,
        ComponentType.AGENT: AgentConfig,
        ComponentType.TOOL: ToolConfig,
        ComponentType.MEMORY: MemoryConfig,
        ComponentType.KNOWLEDGE: KnowledgeConfig,
    }
    
    def validate(self, config: dict[str, Any]) -> BaseComponentConfig:
        """验证配置并返回 Pydantic 模型"""
        component_type = config.get("type")
        if not component_type:
            raise ValueError("Missing 'type' field in config")
        
        try:
            component_type = ComponentType(component_type)
        except ValueError:
            raise ValueError(f"Invalid component type: {component_type}")
        
        model_class = self.CONFIG_MODEL_MAP.get(component_type)
        if not model_class:
            raise ValueError(f"No validator for type: {component_type}")
        
        try:
            return model_class(**config)
        except ValidationError as e:
            raise ConfigValidationError(
                f"Validation failed for {config.get('name', 'unknown')}: {e}"
            )
    
    def validate_batch(
        self, 
        configs: dict[str, dict]
    ) -> dict[str, BaseComponentConfig]:
        """批量验证配置"""
        validated = {}
        errors = {}
        
        for name, config in configs.items():
            try:
                validated[name] = self.validate(config)
            except Exception as e:
                errors[name] = str(e)
        
        if errors:
            raise BatchValidationError(errors)
        
        return validated


class ConfigValidationError(Exception):
    """配置验证错误"""
    pass


class BatchValidationError(Exception):
    """批量验证错误"""
    
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__(self._format_errors())
    
    def _format_errors(self) -> str:
        lines = ["Configuration validation failed:"]
        for name, error in self.errors.items():
            lines.append(f"  - {name}: {error}")
        return "\n".join(lines)
```

### 友好的错误信息

```python
# agio/registry/errors.py

class ConfigError(Exception):
    """配置错误基类"""
    
    def __init__(self, message: str, suggestions: list[str] | None = None):
        self.suggestions = suggestions or []
        super().__init__(self._format_message(message))
    
    def _format_message(self, message: str) -> str:
        lines = [message]
        if self.suggestions:
            lines.append("\nSuggestions:")
            for suggestion in self.suggestions:
                lines.append(f"  • {suggestion}")
        return "\n".join(lines)


class ComponentNotFoundError(ConfigError):
    """组件未找到错误"""
    
    def __init__(self, component_name: str, available: list[str]):
        super().__init__(
            f"Component '{component_name}' not found",
            suggestions=[
                f"Available components: {', '.join(available[:5])}",
                "Check if the component is registered",
                "Verify the component name spelling"
            ]
        )


class CircularDependencyError(ConfigError):
    """循环依赖错误"""
    
    def __init__(self, dependency_chain: list[str]):
        chain_str = " -> ".join(dependency_chain)
        super().__init__(
            f"Circular dependency detected: {chain_str}",
            suggestions=[
                "Review component dependencies",
                "Consider breaking the circular reference"
            ]
        )
```

---

## 最佳实践

### 1. 配置文件组织

```
configs/
├── environments/
│   ├── dev.yaml          # 开发环境全局配置
│   ├── staging.yaml      # 预发布环境
│   └── prod.yaml         # 生产环境
├── models/
│   ├── _base/
│   │   └── openai_base.yaml
│   ├── gpt4.yaml
│   ├── gpt4_creative.yaml
│   └── deepseek.yaml
├── agents/
│   ├── customer_support.yaml
│   ├── data_analyst.yaml
│   └── code_assistant.yaml
├── tools/
│   ├── web_search.yaml
│   ├── database.yaml
│   └── email.yaml
├── memory/
│   └── redis_memory.yaml
├── knowledge/
│   └── product_docs.yaml
└── prompts/
    ├── customer_support.txt
    └── data_analyst.txt
```

### 2. 环境变量管理

```bash
# .env.dev
AGIO_ENV=development
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
REDIS_URL=redis://localhost:6379
MONGODB_URI=mongodb://localhost:27017
```

```bash
# .env.prod
AGIO_ENV=production
OPENAI_API_KEY=${SECRET_OPENAI_KEY}
REDIS_URL=${SECRET_REDIS_URL}
MONGODB_URI=${SECRET_MONGODB_URI}
```

### 3. 配置模板

```yaml
# templates/agent_template.yaml
type: agent
name: ${AGENT_NAME}
description: "${AGENT_DESCRIPTION}"

model: ${MODEL_REF}
tools: []
memory: null
knowledge: null

system_prompt: "You are a helpful assistant."

max_steps: 10
enable_memory_update: true

tags:
  - template
```

### 4. 配置验证 CLI

```bash
# 验证单个配置
agio config validate configs/agents/customer_support.yaml

# 验证整个目录
agio config validate configs/

# 生成 JSON Schema
agio config schema --output schemas/agent.json

# 测试配置（dry-run）
agio config test configs/agents/customer_support.yaml --query "Hello"
```

---

## 实现路线图

### Week 1: 核心基础

#### Day 1-2: Schema 设计
- [ ] 实现 `BaseComponentConfig`
- [ ] 实现 `ModelConfig`
- [ ] 实现 `AgentConfig`
- [ ] 编写单元测试

#### Day 3-4: Registry 实现
- [ ] 实现 `ComponentRegistry`
- [ ] 实现线程安全机制
- [ ] 实现索引（类型、标签）
- [ ] 编写单元测试

#### Day 5: Loader 实现
- [ ] 实现 `ConfigLoader`
- [ ] 实现环境变量解析
- [ ] 实现配置继承
- [ ] 编写单元测试

### Week 2: 高级功能

#### Day 1-2: Factory 实现
- [ ] 实现 `ComponentFactory`
- [ ] 实现 Model 创建
- [ ] 实现 Agent 创建
- [ ] 实现引用解析

#### Day 3: Tool/Memory/Knowledge 配置
- [ ] 实现 `ToolConfig`
- [ ] 实现 `MemoryConfig`
- [ ] 实现 `KnowledgeConfig`
- [ ] 更新 Factory

#### Day 4: 验证与错误处理
- [ ] 实现 `ConfigValidator`
- [ ] 实现友好错误信息
- [ ] 实现批量验证

#### Day 5: 插件系统
- [ ] 实现 `ConfigPlugin` 接口
- [ ] 实现 `PluginManager`
- [ ] 编写示例插件

### Week 3: 集成与测试

#### Day 1-2: 集成测试
- [ ] 端到端测试：从配置创建 Agent
- [ ] 测试配置继承
- [ ] 测试引用解析
- [ ] 测试错误处理

#### Day 3: CLI 工具
- [ ] 实现 `agio config` 命令
- [ ] 实现验证子命令
- [ ] 实现 schema 生成
- [ ] 实现 dry-run 测试

#### Day 4: 文档
- [ ] 编写配置指南
- [ ] 编写 API 文档
- [ ] 创建配置示例
- [ ] 创建最佳实践文档

#### Day 5: 优化与发布
- [ ] 性能优化
- [ ] 代码审查
- [ ] 准备 PR
- [ ] 发布 v0.1.0

---

## JSON Schema 生成

为了支持 IDE 自动补全，我们需要生成 JSON Schema：

```python
# agio/registry/schema.py

from pydantic.json_schema import GenerateJsonSchema
from .models import AgentConfig, ModelConfig

def generate_schemas() -> dict[str, dict]:
    """生成所有配置的 JSON Schema"""
    return {
        "agent": AgentConfig.model_json_schema(),
        "model": ModelConfig.model_json_schema(),
        # ... 其他类型
    }

def save_schemas(output_dir: str) -> None:
    """保存 JSON Schema 到文件"""
    from pathlib import Path
    import json
    
    schemas = generate_schemas()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    for name, schema in schemas.items():
        schema_file = output_path / f"{name}.schema.json"
        with open(schema_file, 'w') as f:
            json.dump(schema, f, indent=2)
```

在 VSCode 中使用：

```json
// .vscode/settings.json
{
  "yaml.schemas": {
    "./schemas/agent.schema.json": "configs/agents/*.yaml",
    "./schemas/model.schema.json": "configs/models/*.yaml"
  }
}
```

---

## 动态配置管理

> **目标**：支持运行时动态修改配置，无需重启应用，配置变更立即生效

### 核心能力

1. **🔄 热重载** - 文件变更自动检测和重新加载
2. **🌐 API 驱动更新** - 通过 REST API 动态修改配置
3. **📡 事件通知** - 配置变更时发送事件通知
4. **🔒 安全更新** - 验证配置有效性后再应用
5. **📜 变更历史** - 记录所有配置变更历史
6. **🔙 回滚支持** - 支持回滚到之前的配置版本

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                  Dynamic Configuration Layer                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │ File Watcher │      │  API Update  │      │  Manual   │ │
│  │  (watchdog)  │      │   Handler    │      │  Reload   │ │
│  └──────┬───────┘      └──────┬───────┘      └─────┬─────┘ │
│         │                     │                     │       │
│         └─────────────────────┼─────────────────────┘       │
│                               ▼                             │
│                    ┌────────────────────┐                   │
│                    │  ConfigManager     │                   │
│                    │  - validate()      │                   │
│                    │  - apply()         │                   │
│                    │  - rollback()      │                   │
│                    └─────────┬──────────┘                   │
│                              │                              │
│         ┌────────────────────┼────────────────────┐         │
│         ▼                    ▼                    ▼         │
│  ┌─────────────┐      ┌─────────────┐      ┌──────────┐   │
│  │  Validator  │      │  Registry   │      │  Events  │   │
│  │  (pre-check)│      │  (update)   │      │ (notify) │   │
│  └─────────────┘      └─────────────┘      └──────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 1. 配置管理器

```python
# agio/registry/manager.py

import asyncio
from typing import Callable, Any
from datetime import datetime
from pathlib import Path
from .base import ComponentRegistry
from .loader import ConfigLoader
from .factory import ComponentFactory
from .validator import ConfigValidator
from .models import BaseComponentConfig

class ConfigChangeEvent:
    """配置变更事件"""
    
    def __init__(
        self,
        component_name: str,
        component_type: str,
        change_type: str,  # "created", "updated", "deleted"
        old_config: BaseComponentConfig | None,
        new_config: BaseComponentConfig | None,
        timestamp: datetime = None
    ):
        self.component_name = component_name
        self.component_type = component_type
        self.change_type = change_type
        self.old_config = old_config
        self.new_config = new_config
        self.timestamp = timestamp or datetime.now()


class ConfigHistory:
    """配置变更历史"""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._history: list[ConfigChangeEvent] = []
    
    def add(self, event: ConfigChangeEvent) -> None:
        """添加历史记录"""
        self._history.append(event)
        if len(self._history) > self.max_history:
            self._history.pop(0)
    
    def get_history(
        self, 
        component_name: str | None = None,
        limit: int = 10
    ) -> list[ConfigChangeEvent]:
        """获取历史记录"""
        if component_name:
            filtered = [
                e for e in self._history 
                if e.component_name == component_name
            ]
        else:
            filtered = self._history
        
        return filtered[-limit:]


class ConfigManager:
    """
    配置管理器 - 动态配置的核心
    
    职责：
    1. 管理配置的生命周期
    2. 验证配置变更
    3. 应用配置变更
    4. 发送变更事件
    5. 支持回滚
    """
    
    def __init__(
        self,
        config_dir: str | Path,
        registry: ComponentRegistry,
        auto_reload: bool = True
    ):
        self.config_dir = Path(config_dir)
        self.registry = registry
        self.loader = ConfigLoader(config_dir)
        self.factory = ComponentFactory(registry)
        self.validator = ConfigValidator()
        self.history = ConfigHistory()
        
        # 事件监听器
        self._listeners: list[Callable[[ConfigChangeEvent], None]] = []
        
        # 文件监控
        self._watcher = None
        if auto_reload:
            self._start_file_watcher()
    
    def add_listener(self, listener: Callable[[ConfigChangeEvent], None]) -> None:
        """添加配置变更监听器"""
        self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[ConfigChangeEvent], None]) -> None:
        """移除配置变更监听器"""
        self._listeners.remove(listener)
    
    async def update_component(
        self,
        component_name: str,
        new_config: dict[str, Any],
        validate_only: bool = False
    ) -> tuple[bool, str]:
        """
        更新组件配置
        
        Args:
            component_name: 组件名称
            new_config: 新配置（字典格式）
            validate_only: 仅验证，不应用
        
        Returns:
            (success, message)
        """
        try:
            # 1. 验证新配置
            validated_config = self.validator.validate(new_config)
            
            # 2. 如果只是验证，直接返回
            if validate_only:
                return True, "Configuration is valid"
            
            # 3. 获取旧配置
            old_config = self.registry.get_config(component_name)
            
            # 4. 创建新组件实例
            new_component = self.factory.create(validated_config)
            
            # 5. 更新注册表
            if old_config:
                self.registry.reload(component_name, new_component, validated_config)
                change_type = "updated"
            else:
                self.registry.register(component_name, new_component, validated_config)
                change_type = "created"
            
            # 6. 记录历史
            event = ConfigChangeEvent(
                component_name=component_name,
                component_type=validated_config.type,
                change_type=change_type,
                old_config=old_config,
                new_config=validated_config
            )
            self.history.add(event)
            
            # 7. 通知监听器
            await self._notify_listeners(event)
            
            return True, f"Component '{component_name}' {change_type} successfully"
            
        except Exception as e:
            return False, f"Failed to update component: {str(e)}"
    
    async def delete_component(self, component_name: str) -> tuple[bool, str]:
        """删除组件"""
        try:
            old_config = self.registry.get_config(component_name)
            if not old_config:
                return False, f"Component '{component_name}' not found"
            
            # 注销组件
            self.registry.unregister(component_name)
            
            # 记录历史
            event = ConfigChangeEvent(
                component_name=component_name,
                component_type=old_config.type,
                change_type="deleted",
                old_config=old_config,
                new_config=None
            )
            self.history.add(event)
            
            # 通知监听器
            await self._notify_listeners(event)
            
            return True, f"Component '{component_name}' deleted successfully"
            
        except Exception as e:
            return False, f"Failed to delete component: {str(e)}"
    
    async def reload_from_file(self, file_path: str | Path) -> tuple[bool, str]:
        """从文件重新加载配置"""
        try:
            # 加载配置
            config_dict = self.loader.load(file_path)
            component_name = config_dict.get('name')
            
            if not component_name:
                return False, "Configuration missing 'name' field"
            
            # 更新组件
            return await self.update_component(component_name, config_dict)
            
        except Exception as e:
            return False, f"Failed to reload from file: {str(e)}"
    
    async def reload_all(self) -> dict[str, tuple[bool, str]]:
        """重新加载所有配置文件"""
        results = {}
        
        # 加载所有配置
        all_configs = self.loader.load_directory()
        
        for name, config in all_configs.items():
            success, message = await self.update_component(name, config)
            results[name] = (success, message)
        
        return results
    
    async def rollback(self, component_name: str, steps: int = 1) -> tuple[bool, str]:
        """回滚到之前的配置"""
        try:
            # 获取历史记录
            history = self.history.get_history(component_name, limit=steps + 1)
            
            if len(history) < steps + 1:
                return False, f"Not enough history to rollback {steps} steps"
            
            # 获取目标配置
            target_event = history[-(steps + 1)]
            target_config = target_event.old_config
            
            if not target_config:
                return False, "Cannot rollback to deleted state"
            
            # 应用旧配置
            config_dict = target_config.model_dump()
            return await self.update_component(component_name, config_dict)
            
        except Exception as e:
            return False, f"Failed to rollback: {str(e)}"
    
    def _start_file_watcher(self) -> None:
        """启动文件监控"""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            class ConfigFileHandler(FileSystemEventHandler):
                def __init__(self, manager: ConfigManager):
                    self.manager = manager
                
                def on_modified(self, event):
                    if event.is_directory:
                        return
                    
                    if event.src_path.endswith('.yaml'):
                        # 异步重新加载
                        asyncio.create_task(
                            self.manager.reload_from_file(event.src_path)
                        )
            
            self._watcher = Observer()
            handler = ConfigFileHandler(self)
            self._watcher.schedule(handler, str(self.config_dir), recursive=True)
            self._watcher.start()
            
        except ImportError:
            print("Warning: watchdog not installed, file watching disabled")
    
    async def _notify_listeners(self, event: ConfigChangeEvent) -> None:
        """通知所有监听器"""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event)
                else:
                    listener(event)
            except Exception as e:
                print(f"Error in listener: {e}")
    
    def stop(self) -> None:
        """停止配置管理器"""
        if self._watcher:
            self._watcher.stop()
            self._watcher.join()
```

### 2. 文件监控

```python
# agio/registry/watcher.py

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from pathlib import Path
import asyncio
from typing import Callable

class ConfigFileWatcher:
    """
    配置文件监控器
    
    使用 watchdog 监控配置文件变化
    """
    
    def __init__(
        self,
        watch_dir: str | Path,
        on_change: Callable[[Path], None],
        patterns: list[str] = None
    ):
        self.watch_dir = Path(watch_dir)
        self.on_change = on_change
        self.patterns = patterns or ["*.yaml", "*.yml"]
        self.observer = Observer()
        
    def start(self) -> None:
        """启动监控"""
        handler = ConfigChangeHandler(self.on_change, self.patterns)
        self.observer.schedule(handler, str(self.watch_dir), recursive=True)
        self.observer.start()
    
    def stop(self) -> None:
        """停止监控"""
        self.observer.stop()
        self.observer.join()


class ConfigChangeHandler(FileSystemEventHandler):
    """配置文件变更处理器"""
    
    def __init__(self, on_change: Callable, patterns: list[str]):
        self.on_change = on_change
        self.patterns = patterns
        self._debounce_tasks = {}
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """文件修改事件"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # 检查文件扩展名
        if not any(file_path.match(pattern) for pattern in self.patterns):
            return
        
        # 防抖处理（避免频繁触发）
        self._debounce_reload(file_path)
    
    def _debounce_reload(self, file_path: Path, delay: float = 0.5) -> None:
        """防抖重新加载"""
        # 取消之前的任务
        if file_path in self._debounce_tasks:
            self._debounce_tasks[file_path].cancel()
        
        # 创建新任务
        async def delayed_reload():
            await asyncio.sleep(delay)
            self.on_change(file_path)
        
        task = asyncio.create_task(delayed_reload())
        self._debounce_tasks[file_path] = task
```

### 3. API 驱动更新

配置管理器可以直接集成到 FastAPI 中：

```python
# agio/api/routes/config.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from agio.registry.manager import ConfigManager

router = APIRouter(prefix="/api/config", tags=["Configuration"])

class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    config: dict
    validate_only: bool = False

class ConfigUpdateResponse(BaseModel):
    """配置更新响应"""
    success: bool
    message: str
    component_name: str

@router.put("/{component_name}")
async def update_config(
    component_name: str,
    request: ConfigUpdateRequest,
    manager: ConfigManager = Depends(get_config_manager)
) -> ConfigUpdateResponse:
    """更新组件配置"""
    success, message = await manager.update_component(
        component_name,
        request.config,
        validate_only=request.validate_only
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return ConfigUpdateResponse(
        success=success,
        message=message,
        component_name=component_name
    )

@router.delete("/{component_name}")
async def delete_config(
    component_name: str,
    manager: ConfigManager = Depends(get_config_manager)
):
    """删除组件配置"""
    success, message = await manager.delete_component(component_name)
    
    if not success:
        raise HTTPException(status_code=404, detail=message)
    
    return {"success": success, "message": message}

@router.post("/{component_name}/rollback")
async def rollback_config(
    component_name: str,
    steps: int = 1,
    manager: ConfigManager = Depends(get_config_manager)
):
    """回滚配置"""
    success, message = await manager.rollback(component_name, steps)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": success, "message": message}

@router.get("/{component_name}/history")
async def get_config_history(
    component_name: str,
    limit: int = 10,
    manager: ConfigManager = Depends(get_config_manager)
):
    """获取配置变更历史"""
    history = manager.history.get_history(component_name, limit)
    
    return {
        "component_name": component_name,
        "history": [
            {
                "change_type": event.change_type,
                "timestamp": event.timestamp.isoformat(),
                "old_config": event.old_config.model_dump() if event.old_config else None,
                "new_config": event.new_config.model_dump() if event.new_config else None,
            }
            for event in history
        ]
    }

@router.post("/reload-all")
async def reload_all_configs(
    manager: ConfigManager = Depends(get_config_manager)
):
    """重新加载所有配置"""
    results = await manager.reload_all()
    
    return {
        "total": len(results),
        "success": sum(1 for success, _ in results.values() if success),
        "failed": sum(1 for success, _ in results.values() if not success),
        "details": results
    }
```

### 4. 事件通知系统

```python
# agio/registry/events.py

from typing import Callable, Any
from enum import Enum
import asyncio

class ConfigEventType(str, Enum):
    """配置事件类型"""
    COMPONENT_CREATED = "component.created"
    COMPONENT_UPDATED = "component.updated"
    COMPONENT_DELETED = "component.deleted"
    VALIDATION_FAILED = "validation.failed"
    RELOAD_STARTED = "reload.started"
    RELOAD_COMPLETED = "reload.completed"

class ConfigEventBus:
    """配置事件总线"""
    
    def __init__(self):
        self._subscribers: dict[ConfigEventType, list[Callable]] = {}
    
    def subscribe(
        self, 
        event_type: ConfigEventType, 
        handler: Callable[[Any], None]
    ) -> None:
        """订阅事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def unsubscribe(
        self, 
        event_type: ConfigEventType, 
        handler: Callable
    ) -> None:
        """取消订阅"""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)
    
    async def publish(
        self, 
        event_type: ConfigEventType, 
        data: Any
    ) -> None:
        """发布事件"""
        if event_type not in self._subscribers:
            return
        
        for handler in self._subscribers[event_type]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                print(f"Error in event handler: {e}")

# 全局事件总线
_event_bus = ConfigEventBus()

def get_event_bus() -> ConfigEventBus:
    """获取全局事件总线"""
    return _event_bus
```

### 5. 使用示例

#### 示例 1: 启用自动热重载

```python
from agio.registry.manager import ConfigManager
from agio.registry.base import get_registry

# 创建配置管理器（自动启用文件监控）
manager = ConfigManager(
    config_dir="./configs",
    registry=get_registry(),
    auto_reload=True  # 启用自动重载
)

# 添加变更监听器
async def on_config_change(event):
    print(f"Config changed: {event.component_name} - {event.change_type}")

manager.add_listener(on_config_change)

# 现在修改 configs/agents/my_agent.yaml 文件
# 配置会自动重新加载！
```

#### 示例 2: API 驱动更新

```python
# 通过 API 更新配置
import httpx

# 更新 Agent 配置
new_config = {
    "type": "agent",
    "name": "my_agent",
    "model": "gpt4",
    "system_prompt": "Updated prompt!",
    "max_steps": 20
}

response = httpx.put(
    "http://localhost:8000/api/config/my_agent",
    json={"config": new_config}
)

print(response.json())
# {"success": true, "message": "Component 'my_agent' updated successfully"}
```

#### 示例 3: 验证配置（不应用）

```python
# 仅验证配置，不应用
success, message = await manager.update_component(
    "my_agent",
    new_config,
    validate_only=True
)

if success:
    print("Configuration is valid!")
else:
    print(f"Validation failed: {message}")
```

#### 示例 4: 回滚配置

```python
# 回滚到上一个版本
success, message = await manager.rollback("my_agent", steps=1)

# 回滚到 3 个版本之前
success, message = await manager.rollback("my_agent", steps=3)
```

#### 示例 5: 查看变更历史

```python
# 获取变更历史
history = manager.history.get_history("my_agent", limit=10)

for event in history:
    print(f"{event.timestamp}: {event.change_type}")
    print(f"  Old: {event.old_config}")
    print(f"  New: {event.new_config}")
```

### 6. 前端集成

在 React 前端中，可以实时监听配置变更：

```typescript
// src/hooks/useConfigUpdates.ts

import { useEffect, useState } from 'react';

export function useConfigUpdates(componentName: string) {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(false);

  // 更新配置
  const updateConfig = async (newConfig: any, validateOnly = false) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/config/${componentName}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: newConfig, validate_only: validateOnly })
      });
      
      const result = await response.json();
      if (result.success) {
        setConfig(newConfig);
      }
      return result;
    } finally {
      setLoading(false);
    }
  };

  // 回滚配置
  const rollback = async (steps = 1) => {
    const response = await fetch(`/api/config/${componentName}/rollback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ steps })
    });
    return response.json();
  };

  return { config, updateConfig, rollback, loading };
}
```

### 7. 安全考虑

```python
# agio/registry/security.py

from typing import Callable
from .models import BaseComponentConfig

class ConfigSecurityPolicy:
    """配置安全策略"""
    
    def __init__(self):
        self._validators: list[Callable[[BaseComponentConfig], bool]] = []
    
    def add_validator(self, validator: Callable[[BaseComponentConfig], bool]) -> None:
        """添加安全验证器"""
        self._validators.append(validator)
    
    def validate(self, config: BaseComponentConfig) -> tuple[bool, str]:
        """验证配置安全性"""
        for validator in self._validators:
            try:
                if not validator(config):
                    return False, "Security validation failed"
            except Exception as e:
                return False, f"Security check error: {str(e)}"
        
        return True, "Security validation passed"

# 示例：禁止某些敏感配置
def no_external_api_validator(config: BaseComponentConfig) -> bool:
    """禁止外部 API 调用"""
    if hasattr(config, 'api_base'):
        if config.api_base and not config.api_base.startswith('https://api.openai.com'):
            raise ValueError("External API endpoints not allowed")
    return True

# 使用
policy = ConfigSecurityPolicy()
policy.add_validator(no_external_api_validator)
```

---

## 使用指南

> **目标**：让开发者快速上手，从零到一使用 YAML 配置构建 Agent 应用

### 快速开始

#### 1. 安装 Agio

```bash
pip install agio

# 或从源码安装
git clone https://github.com/yourusername/agio.git
cd agio
pip install -e .
```

#### 2. 创建配置目录

```bash
mkdir -p configs/{models,agents,tools,memory,knowledge}
```

#### 3. 创建第一个 Model 配置

```yaml
# configs/models/gpt4.yaml
type: model
name: gpt4
provider: openai
model: gpt-4-turbo-preview
api_key: ${OPENAI_API_KEY}
temperature: 0.7
```

#### 4. 创建第一个 Agent 配置

```yaml
# configs/agents/assistant.yaml
type: agent
name: assistant
model: gpt4
system_prompt: "You are a helpful assistant."
```

#### 5. 使用配置创建 Agent

```python
from agio.registry import load_from_config

# 方式 1: 从配置目录加载所有组件
registry = load_from_config("./configs")

# 获取 Agent
agent = registry.get("assistant")

# 运行 Agent
async for chunk in agent.arun("Hello!"):
    print(chunk, end="", flush=True)
```

### 核心使用模式

#### 模式 1: 纯配置驱动（零代码）

```python
# main.py
from agio import Agio

# 初始化 Agio（自动加载配置）
app = Agio(config_dir="./configs")

# 运行指定 Agent
await app.run("assistant", "What's the weather today?")
```

#### 模式 2: 配置 + 代码混合

```python
from agio.registry import get_registry, ComponentFactory
from agio.registry.loader import ConfigLoader

# 加载配置
loader = ConfigLoader("./configs")
registry = get_registry()
factory = ComponentFactory(registry)

# 从配置创建 Model
model_config = loader.load("models/gpt4.yaml")
model = factory.create(model_config)

# 代码创建 Agent（使用配置的 Model）
from agio import Agent

agent = Agent(
    model=model,  # 使用配置的 Model
    tools=[my_custom_tool],  # 代码定义的 Tool
    system_prompt="Custom prompt"
)
```

#### 模式 3: 动态加载和切换

```python
from agio.registry.manager import ConfigManager
from agio.registry.base import get_registry

# 创建配置管理器
manager = ConfigManager(
    config_dir="./configs",
    registry=get_registry(),
    auto_reload=True
)

# 获取 Agent（会自动热重载）
agent = get_registry().get("assistant")

# 运行时切换 Model
new_config = {
    "type": "agent",
    "name": "assistant",
    "model": "gpt4_creative",  # 切换到更有创意的模型
    "system_prompt": "You are a creative assistant."
}

await manager.update_component("assistant", new_config)

# Agent 已更新，无需重启！
```

### 常见场景

#### 场景 1: 多环境配置

```yaml
# configs/environments/dev.yaml
environment: development
models:
  default: gpt-3.5-turbo
  
# configs/environments/prod.yaml
environment: production
models:
  default: gpt-4-turbo-preview
```

```python
import os
from agio import Agio

env = os.getenv("AGIO_ENV", "dev")
app = Agio(
    config_dir="./configs",
    environment_file=f"./configs/environments/{env}.yaml"
)
```

#### 场景 2: 带工具的 Agent

```yaml
# configs/tools/calculator.yaml
type: tool
name: calculator
tool_type: function
function_path: "myapp.tools.calculator"

# configs/agents/math_tutor.yaml
type: agent
name: math_tutor
model: gpt4
tools:
  - calculator
system_prompt: "You are a math tutor. Use the calculator when needed."
```

```python
# myapp/tools.py
from agio.tools import tool

@tool
def calculator(expression: str) -> float:
    """Calculate a mathematical expression."""
    return eval(expression)

# main.py
from agio import Agio

app = Agio(config_dir="./configs")
agent = app.get_agent("math_tutor")

result = await agent.arun("What is 123 * 456?")
```

#### 场景 3: 带记忆的 Agent

```yaml
# configs/memory/redis_memory.yaml
type: memory
name: redis_memory
class_path: "agio.memory.RedisMemory"
params:
  redis_url: ${REDIS_URL}
  max_history_length: 20

# configs/agents/chatbot.yaml
type: agent
name: chatbot
model: gpt4
memory: redis_memory
system_prompt: "You are a friendly chatbot."
```

```python
from agio import Agio

app = Agio(config_dir="./configs")
agent = app.get_agent("chatbot")

# 第一次对话
await agent.arun("My name is Alice", user_id="user123")

# 第二次对话（记住上下文）
await agent.arun("What's my name?", user_id="user123")
# 输出: "Your name is Alice."
```

#### 场景 4: RAG Agent

```yaml
# configs/knowledge/docs.yaml
type: knowledge
name: product_docs
class_path: "agio.knowledge.ChromaKnowledge"
vector_store: chroma_db
embedding_model: text-embedding-3-small
data_sources:
  - "./docs/**/*.md"
top_k: 5

# configs/agents/support_agent.yaml
type: agent
name: support_agent
model: gpt4
knowledge: product_docs
system_prompt: "You are a customer support agent. Use the knowledge base to answer questions."
```

```python
from agio import Agio

app = Agio(config_dir="./configs")
agent = app.get_agent("support_agent")

# Agent 会自动检索知识库
result = await agent.arun("How do I reset my password?")
```

### 高级用法

#### 1. 自定义组件

```python
# myapp/models/custom_llm.py
from agio.models.base import Model, StreamChunk

class MyCustomLLM(Model):
    endpoint: str
    auth_token: str
    
    async def arun_stream(self, messages, tools=None):
        # 自定义实现
        async for chunk in self._call_api(messages):
            yield StreamChunk(content=chunk)
```

```yaml
# configs/models/custom.yaml
type: model
name: custom_llm
provider: custom
custom_class: "myapp.models.custom_llm.MyCustomLLM"
custom_params:
  endpoint: "https://my-api.com/v1/chat"
  auth_token: ${MY_API_TOKEN}
```

#### 2. 配置模板和继承

```yaml
# configs/models/_base/gpt_base.yaml
type: model
provider: openai
api_key: ${OPENAI_API_KEY}
timeout: 60
max_retries: 3

# configs/models/gpt4_fast.yaml
extends: _base/gpt_base
name: gpt4_fast
model: gpt-4-turbo-preview
temperature: 0.3

# configs/models/gpt4_creative.yaml
extends: _base/gpt_base
name: gpt4_creative
model: gpt-4-turbo-preview
temperature: 1.2
top_p: 0.95
```

#### 3. 批量操作

```python
from agio.registry.manager import ConfigManager

manager = ConfigManager(config_dir="./configs")

# 批量创建 Agents
agent_configs = [
    {"type": "agent", "name": f"agent_{i}", "model": "gpt4"}
    for i in range(10)
]

for config in agent_configs:
    await manager.update_component(config["name"], config)

# 批量更新（例如：更换所有 Agent 的 Model）
for agent_name in registry.list_by_type(ComponentType.AGENT):
    config = registry.get_config(agent_name)
    config_dict = config.model_dump()
    config_dict["model"] = "gpt4_creative"
    await manager.update_component(agent_name, config_dict)
```

#### 4. 配置验证和测试

```python
from agio.registry.validator import ConfigValidator
from agio.registry.loader import ConfigLoader

loader = ConfigLoader("./configs")
validator = ConfigValidator()

# 验证单个配置
config = loader.load("agents/my_agent.yaml")
try:
    validated = validator.validate(config)
    print("✅ Configuration is valid")
except Exception as e:
    print(f"❌ Validation failed: {e}")

# 批量验证
configs = loader.load_directory()
try:
    validated_configs = validator.validate_batch(configs)
    print(f"✅ All {len(validated_configs)} configurations are valid")
except Exception as e:
    print(f"❌ Validation failed: {e}")
```

### CLI 工具

```bash
# 验证配置
agio config validate ./configs/agents/my_agent.yaml

# 验证所有配置
agio config validate ./configs/

# 列出所有组件
agio config list

# 列出特定类型的组件
agio config list --type agent

# 查看组件详情
agio config show my_agent

# 测试 Agent（dry-run）
agio agent test my_agent --query "Hello, world!"

# 运行 Agent
agio agent run my_agent --query "What's the weather?"

# 生成 JSON Schema
agio config schema --output ./schemas/

# 创建新配置（从模板）
agio config create agent --name my_new_agent --template basic

# 热重载所有配置
agio config reload
```

### 最佳实践

#### 1. 配置文件组织

```
configs/
├── _base/              # 基础配置（用于继承）
│   ├── gpt_base.yaml
│   └── agent_base.yaml
├── environments/       # 环境配置
│   ├── dev.yaml
│   ├── staging.yaml
│   └── prod.yaml
├── models/            # Model 配置
│   ├── gpt4.yaml
│   └── deepseek.yaml
├── agents/            # Agent 配置
│   ├── customer_support.yaml
│   └── data_analyst.yaml
├── tools/             # Tool 配置
│   └── web_search.yaml
└── prompts/           # 提示词文件
    └── customer_support.txt
```

#### 2. 环境变量管理

```bash
# .env
AGIO_ENV=development
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
REDIS_URL=redis://localhost:6379
```

```python
from dotenv import load_dotenv
load_dotenv()

from agio import Agio
app = Agio(config_dir="./configs")
```

#### 3. 版本控制

```gitignore
# .gitignore
.env
.env.*
configs/environments/prod.yaml  # 生产配置不提交
*.local.yaml                     # 本地配置不提交
```

```yaml
# configs/models/gpt4.yaml.example
type: model
name: gpt4
provider: openai
model: gpt-4-turbo-preview
api_key: ${OPENAI_API_KEY}  # 使用环境变量
```

#### 4. 配置文档化

```yaml
# configs/agents/customer_support.yaml
type: agent
name: customer_support
description: |
  Customer support agent with access to knowledge base and ticketing system.
  
  Features:
  - Searches product documentation
  - Creates support tickets
  - Sends email notifications
  
  Usage:
    agent = registry.get("customer_support")
    await agent.arun("How do I reset my password?")

model: gpt4
tools:
  - search_knowledge_base
  - create_ticket
  - send_email
knowledge: product_docs

metadata:
  version: "2.0"
  owner: "support-team"
  last_updated: "2024-01-15"
```

### 故障排查

#### 问题 1: 配置未生效

```python
# 清除缓存并重新加载
loader = ConfigLoader("./configs")
loader.clear_cache()
config = loader.load("agents/my_agent.yaml")
```

#### 问题 2: 组件未找到

```python
from agio.registry.base import get_registry

registry = get_registry()

# 检查组件是否存在
if not registry.exists("my_agent"):
    print("Component not found!")
    print("Available agents:", registry.list_by_type(ComponentType.AGENT))
```

#### 问题 3: 配置验证失败

```python
from agio.registry.validator import ConfigValidator

validator = ConfigValidator()
try:
    validated = validator.validate(config)
except Exception as e:
    print(f"Validation error: {e}")
    # 查看详细错误信息
    import traceback
    traceback.print_exc()
```

---

## 总结

这个配置系统设计具备以下特点：

1. **✅ 类型安全** - Pydantic 提供完整验证
2. **✅ 易于使用** - 声明式 YAML 配置
3. **✅ 可扩展** - 插件系统支持第三方组件
4. **✅ 开发者友好** - 友好的错误信息、IDE 支持
5. **✅ 生产就绪** - 线程安全、热重载、环境隔离
6. **✅ 动态配置** - 支持运行时更新、API 驱动、事件通知
7. **✅ 完整文档** - 详细的使用指南和示例

通过这个配置系统，开发者可以：
- 🚀 快速上手，零代码创建 Agent
- 🔄 动态调整配置，无需重启
- 📊 通过 Web UI 可视化管理所有组件
- 🔧 灵活组合配置和代码
- 🌍 轻松管理多环境部署

