# 配置系统

Agio 的配置系统采用模块化架构，遵循 SOLID 原则，提供配置驱动、依赖解析、热重载等核心能力。

## 架构设计

```
ConfigSystem (门面/协调者)
├── ConfigRegistry          # 配置存储和查询
├── ComponentContainer      # 组件实例管理
├── DependencyResolver      # 依赖解析和拓扑排序
├── BuilderRegistry         # 构建器管理
├── HotReloadManager        # 热重载管理
└── ModelProviderRegistry   # 模型 Provider 注册表
```

### 核心特性

- ✅ **单一职责**：每个模块职责清晰
- ✅ **开闭原则**：支持动态注册 Builder 和 Provider
- ✅ **Fail Fast**：循环依赖立即抛出异常
- ✅ **线程安全**：全局单例支持并发访问
- ✅ **热重载**：配置变更自动级联重建
- ✅ **可扩展**：支持自定义 Provider 和 Builder

## 核心组件

### ConfigRegistry

**职责**：配置存储和查询

```python
class ConfigRegistry:
    def register(self, config: ComponentConfig) -> None:
        """注册配置（自动验证）"""
        
    def get(self, component_type: ComponentType, name: str) -> ComponentConfig | None:
        """获取配置"""
        
    def list_by_type(self, component_type: ComponentType) -> list[ComponentConfig]:
        """列出指定类型的所有配置"""
```

**特点**：
- 使用 `(ComponentType, name)` 作为唯一键
- 存储已验证的 Pydantic 配置模型
- 支持配置的增删改查

### ComponentContainer

**职责**：组件实例管理

```python
class ComponentContainer:
    def register(self, name: str, instance: Any, metadata: ComponentMetadata) -> None:
        """注册组件实例"""
        
    def get(self, name: str) -> Any:
        """获取组件实例"""
        
    def has(self, name: str) -> bool:
        """检查组件是否存在"""
```

**特点**：
- 存储已构建的组件实例
- 维护组件元数据（类型、依赖等）
- 支持实例查询和生命周期管理

### DependencyResolver

**职责**：依赖解析和拓扑排序

```python
class DependencyResolver:
    def extract_dependencies(
        self, config: ComponentConfig, available_names: set[str] | None = None
    ) -> set[str]:
        """提取配置的依赖"""
        
    def resolve_build_order(
        self, configs: list[ComponentConfig]
    ) -> list[ComponentConfig]:
        """拓扑排序，返回构建顺序"""
```

**特点**：
- 自动提取配置的依赖关系
- 拓扑排序确保依赖先于被依赖者构建
- **循环依赖检测**：发现循环依赖立即抛出异常（fail fast）

**依赖提取规则**：

1. **Agent 依赖**：
   - `model`: LLM 模型
   - `tools`: 工具列表（支持 function/agent_tool/workflow_tool）
   - `memory`: 记忆组件
   - `knowledge`: 知识库组件
   - `session_store`: 会话存储

2. **Tool 依赖**：
   - `dependencies`: 工具依赖的其他组件（如 `llm_model`, `citation_source_store`）

3. **Workflow 依赖**：
   - `session_store`: 会话存储
   - `stages[].runnable`: 节点引用的 Agent/Workflow（递归提取）

### BuilderRegistry

**职责**：构建器管理

```python
class BuilderRegistry:
    def register(self, component_type: ComponentType, builder: ComponentBuilder) -> None:
        """注册构建器"""
        
    def get_builder(self, component_type: ComponentType) -> ComponentBuilder:
        """获取构建器"""
```

**内置构建器**：
- `ModelBuilder`: 构建 LLM 模型实例
- `ToolBuilder`: 构建工具实例
- `AgentBuilder`: 构建 Agent 实例
- `WorkflowBuilder`: 构建 Workflow 实例
- `SessionStoreBuilder`: 构建会话存储实例
- `TraceStoreBuilder`: 构建追踪存储实例
- `CitationStoreBuilder`: 构建引用存储实例

### HotReloadManager

**职责**：热重载管理

```python
class HotReloadManager:
    async def handle_change(
        self, component_name: str, change_type: str, build_fn: Callable
    ) -> None:
        """处理配置变更"""
```

**工作流程**：
1. 检测配置变更（通过 `save_config` / `delete_config`）
2. 识别受影响组件（依赖该组件的所有组件）
3. 级联重建：按依赖顺序重建受影响组件
4. 通知回调：触发注册的回调函数

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
    api_key="${OPENAI_API_KEY}"
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

## 配置加载机制

### 1. 递归扫描

`ConfigLoader` 使用 `rglob("*.yaml")` 递归扫描所有子目录：

```
configs/
├── models/
│   ├── deepseek.yaml
│   └── claude.yaml
├── tools/
│   └── file_operations/
│       └── file_read.yaml
└── agents/
    └── simple_assistant.yaml
```

### 2. 类型识别

从配置文件的 `type` 字段识别组件类型：

```yaml
type: agent  # 识别为 AgentConfig
name: simple_assistant
model: deepseek
```

支持的组件类型：
- `model`: LLM 模型配置
- `tool`: 工具配置
- `agent`: Agent 配置
- `workflow`: Workflow 配置
- `session_store`: 会话存储配置
- `trace_store`: 追踪存储配置
- `citation_store`: 引用存储配置

### 3. 重复检测

如果发现相同 `(type, name)` 的配置：
- 记录警告日志
- 后加载的覆盖先加载的

### 4. 错误处理

- **缺少 `type` 或 `name` 字段**：记录警告并跳过
- **未知类型**：记录警告并跳过
- **`enabled: false`**：跳过但不报错
- **循环依赖**：立即抛出异常（fail fast）

## 依赖解析示例

### 简单依赖链

```yaml
# models/deepseek.yaml
type: model
name: deepseek
provider: deepseek

# agents/simple_assistant.yaml
type: agent
name: simple_assistant
model: deepseek  # 依赖 deepseek
```

**构建顺序**：
1. `deepseek` (Model)
2. `simple_assistant` (Agent)

### 复杂依赖链

```yaml
# models/claude.yaml
type: model
name: claude
provider: anthropic

# tools/web_search.yaml
type: tool
name: web_search
dependencies:
  citation_source_store: citation_store_mongodb

# storages/citation_stores/citation_store_mongodb.yaml
type: citation_store
name: citation_store_mongodb

# agents/researcher.yaml
type: agent
name: researcher
model: claude
tools:
  - web_search
```

**构建顺序**：
1. `claude` (Model)
2. `citation_store_mongodb` (CitationStore)
3. `web_search` (Tool)
4. `researcher` (Agent)

### 循环依赖检测

```yaml
# agents/agent_a.yaml
type: agent
name: agent_a
model: deepseek
tools:
  - agent_tool:
      agent: agent_b

# agents/agent_b.yaml
type: agent
name: agent_b
model: deepseek
tools:
  - agent_tool:
      agent: agent_a
```

**结果**：立即抛出 `ConfigError: Circular dependency detected`

## 扩展能力

### 注册自定义模型 Provider

```python
from agio.config import get_model_provider_registry
from agio.providers.llm.base import Model

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

## 配置示例

### Model 配置

```yaml
type: model
name: deepseek
description: "DeepSeek model"
provider: deepseek
model_name: deepseek-chat
api_key: ${DEEPSEEK_API_KEY}
temperature: 0.7
max_tokens: 4096
enabled: true
```

### Tool 配置

```yaml
type: tool
name: file_read
description: "Read file contents"
tool_name: file_read
dependencies:
  # 工具可以依赖其他组件
params:
  max_size_mb: 10
enabled: true
```

### Agent 配置

```yaml
type: agent
name: simple_assistant
description: "Simple general-purpose assistant"
model: deepseek  # 引用 model 配置
system_prompt: "You are a helpful assistant."
tools:
  - ls  # 简单引用
  - file_read
  - agent_tool:  # Agent 作为工具
      agent: researcher
      description: "Expert researcher"
session_store: mongodb_session_store
enabled: true
```

### Workflow 配置

```yaml
type: workflow
name: research_pipeline
workflow_type: pipeline
stages:
  - id: research
    runnable: researcher  # 引用 Agent
    input: "Research: {input}"
  - id: analyze
    runnable: analyzer
    input: "Analyze: {research.output}"
session_store: mongodb_session_store
enabled: true
```

## 最佳实践

1. **配置组织**：按类型分目录组织配置文件
2. **命名规范**：使用有意义的名称，避免冲突
3. **依赖管理**：明确声明所有依赖，避免隐式依赖
4. **环境变量**：敏感信息使用环境变量 `${VAR_NAME}`
5. **热重载**：开发环境使用热重载，生产环境谨慎使用
6. **错误处理**：关注日志中的配置加载错误

## 相关代码

- `agio/config/system.py`: ConfigSystem 主类
- `agio/config/registry.py`: ConfigRegistry
- `agio/config/container.py`: ComponentContainer
- `agio/config/dependency.py`: DependencyResolver
- `agio/config/builders.py`: 各种 Builder
- `agio/config/hot_reload.py`: HotReloadManager
- `agio/config/loader.py`: ConfigLoader

