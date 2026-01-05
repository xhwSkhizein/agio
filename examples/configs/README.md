# Agio 配置文件

本目录存放通过 `ConfigSystem` 动态装配的 YAML 配置，支持 Jinja2 环境变量占位（`{{ env.VAR_NAME | default("...") }}`）。

## 目录结构

配置系统支持**灵活的文件夹组织方式**，可以按任意目录结构组织配置文件。

### 推荐结构

```
configs/
├── agents/                    # Agent 配置
│   ├── simple_assistant.yaml
│   ├── collector.yaml
│   └── master_orchestrator.yaml
├── models/                    # LLM 模型配置
│   ├── deepseek.yaml
│   ├── deepseek-reasoner.yaml
│   ├── claude.yaml
│   ├── gpt-4o-mini.yaml
│   └── embedding.yaml
├── tools/                     # 工具配置（按功能分类）
│   ├── file_operations/       # 文件操作工具
│   │   ├── file_read.yaml
│   │   ├── file_write.yaml
│   │   └── file_edit.yaml
│   ├── web_operations/        # Web 操作工具
│   │   ├── web_search.yaml
│   │   └── web_fetch.yaml
│   ├── system_operations/     # 系统操作工具
│   │   ├── bash.yaml
│   │   ├── ls.yaml
│   │   ├── grep.yaml
│   │   └── glob.yaml
│   └── utilities/             # 工具类
│       └── get_tool_result.yaml
├── storages/                  # 存储配置（按类型分类）
│   ├── session_stores/        # 会话存储
│   │   ├── mongodb.yaml
│   │   └── inmemory.yaml
│   └── citation_stores/       # 引用存储
│       └── citation_store_mongodb.yaml
├── observability/             # 可观测性配置
    └── trace_store.yaml

```

### 灵活组织方式

配置系统会**递归扫描**所有子目录中的 YAML 文件，并基于配置文件中的 `type` 字段自动识别组件类型。这意味着你可以：

- **按功能分类**（当前采用的方式）：

  ```
  configs/
  ├── tools/
  │   ├── file_operations/    # 文件操作工具
  │   ├── web_operations/      # Web 操作工具
  │   ├── system_operations/   # 系统操作工具
  │   └── utilities/          # 工具类
  └── storages/
      ├── session_stores/     # 会话存储
      └── citation_stores/     # 引用存储
  ```

- **按环境组织**：

  ```
  configs/
  ├── production/
  │   ├── models/
  │   └── agents/
  └── development/
      ├── models/
      └── agents/
  ```

- **按团队组织**：

  ```
  configs/
  ├── team-a/
  │   └── agents/
  └── team-b/
      └── agents/
  ```

- **任意嵌套结构**：
  ```
  configs/
  ├── shared/
  │   └── storages/
  └── custom/
      └── nested/
          └── path/
              └── config.yaml
  ```

**重要**：配置文件的类型由 `type` 字段决定，而不是文件夹名称。文件夹仅用于组织，不影响类型识别。

## 环境变量

必需变量（在 `.env`）：

```bash
# 模型配置（按需启用，对应 provider）
AGIO_OPENAI_API_KEY=sk-...       # OpenAI
AGIO_ANTHROPIC_API_KEY=sk-...    # Anthropic
AGIO_DEEPSEEK_API_KEY=sk-...     # DeepSeek

# 持久化存储 (MongoDB)
AGIO_MONGO_URI=mongodb://localhost:27017
AGIO_MONGO_DB=agio

# 配置目录
AGIO_CONFIG_DIR=./configs

# 可选：Web 搜索 (Serper API)
SERPER_API_KEY=...

# 可选：可观测性 OTLP 导出
AGIO_OTLP_ENABLED=true
AGIO_OTLP_ENDPOINT=http://localhost:4317
AGIO_OTLP_PROTOCOL=grpc  # 或 http
```

## 配置系统架构

Agio 采用模块化的配置系统架构，遵循 SOLID 原则：

```
ConfigSystem (门面/协调者)
├── ConfigRegistry          # 配置存储和查询
├── ComponentContainer      # 组件实例管理
├── DependencyResolver      # 依赖解析和拓扑排序
├── BuilderRegistry         # 构建器管理
├── HotReloadManager        # 热重载管理
└── ModelProviderRegistry   # 模型 Provider 注册表
```

**核心特性**:

- ✅ 单一职责：每个模块职责清晰
- ✅ 开闭原则：支持动态注册 Builder 和 Provider
- ✅ Fail Fast：循环依赖立即抛出异常
- ✅ 线程安全：全局单例支持并发访问
- ✅ 热重载：配置变更自动级联重建
- ✅ 可扩展：支持自定义 Provider 和 Builder

## 加载与构建

配置系统会递归扫描指定目录下的所有 YAML 文件，基于每个文件的 `type` 字段识别组件类型。

```python
from agio.config import init_config_system

# 读取目录 -> 递归扫描 -> 解析 -> 验证 -> 拓扑排序 -> 构建实例
config_sys = await init_config_system("./configs")

# 直接获取已构建组件
agent = config_sys.get("code_assistant")
store = config_sys.get("mongodb_session_store")

# 列出配置
from agio.config import ComponentType
configs = config_sys.list_configs(ComponentType.AGENT)

# 动态保存配置（触发热重载）
from agio.config import ModelConfig
new_model = ModelConfig(
    name="new_model",
    provider="openai",
    model_name="gpt-4"
)
await config_sys.save_config(new_model)
```

服务启动时 `agio.api.app` 会自动读取 `AGIO_CONFIG_DIR` 并调用 `load_from_directory` + `build_all`。

### 配置加载机制

1. **递归扫描**：`ConfigLoader` 使用 `rglob("*.yaml")` 递归扫描所有子目录
2. **类型识别**：从配置文件的 `type` 字段识别组件类型（`model`, `tool`, `agent` 等）
3. **重复检测**：如果发现相同 `(type, name)` 的配置，会记录警告，后加载的覆盖先加载的
4. **错误处理**：
   - 缺少 `type` 或 `name` 字段：记录警告并跳过
   - 未知类型：记录警告并跳过
   - `enabled: false`：跳过但不报错

### 扩展模型 Provider

支持动态注册自定义 Provider：

```python
from agio.config import get_model_provider_registry

registry = get_model_provider_registry()

# 注册自定义 Provider
registry.register("custom_provider", CustomModelClass)

# Provider 会在构建时自动使用
```

## 内置工具列表

| 名称              | 描述                            |
| ----------------- | ------------------------------- |
| `file_read`       | 读取文件内容（支持文本和图片）  |
| `file_edit`       | 编辑文件（结构化补丁）          |
| `file_write`      | 写入文件                        |
| `grep`            | 使用 ripgrep 搜索文件内容       |
| `glob`            | 按模式查找文件                  |
| `ls`              | 列出目录内容                    |
| `bash`            | 执行 shell 命令                 |
| `web_search`      | Web 搜索（需要 SERPER_API_KEY） |
| `web_fetch`       | 获取网页内容并可选 LLM 处理     |
| `get_tool_result` | 查询最近的工具执行结果          |

## 配置示例

### Agent (带工具)

```yaml
type: agent
name: code_assistant
model: deepseek # 引用 models/deepseek.yaml
tools:
  - file_read # 引用内置工具
  - grep
  - bash
session_store: mongodb_session_store

system_prompt: |
  You are a helpful coding assistant.
```

### Agent (带 Agent 作为工具)

```yaml
type: agent
name: orchestrator
model: deepseek
tools:
  - web_search # 普通工具

  # Agent 作为工具
  - type: agent_tool
    agent: tech_researcher
    description: "Delegate research tasks"
```

## 使用提示

- 支持的类型：model/tool/session_store/trace_store/agent
- 构建顺序由 `DependencyResolver` 统一拓扑排序；**循环依赖会立即抛出异常（fail fast）**
- 更新或新增配置可调用 `ConfigSystem.save_config` 触发热重载，会自动级联重建依赖者
- 缺省工具会尝试从内置 registry 创建；未找到则抛出 `ComponentNotFoundError`
- 所有配置通过 Pydantic 模型验证，确保类型安全

### 通用字段

| 字段      | 类型   | 说明                                                                        |
| --------- | ------ | --------------------------------------------------------------------------- |
| `type`    | string | 组件类型: agent, model, tool, session_store, trace_store |
| `name`    | string | 组件唯一名称                                                                |
| `enabled` | bool   | 是否启用 (默认 true)                                                        |

### Agent 字段

| 字段                         | 类型   | 说明                                                        |
| ---------------------------- | ------ | ----------------------------------------------------------- |
| `model`                      | string | 引用的 Model 名称                                           |
| `tools`                      | list   | 工具引用列表（支持字符串、agent_tool）                      |
| `session_store`              | string | 引用的 SessionStore 名称（用于 AgentRun/Step 持久化，可选） |
| `system_prompt`              | string | 系统提示词（可选）                                          |
| `max_steps`                  | int    | 最大执行步数（默认 10）                                     |
| `max_tokens`                 | int    | 最大 token 数（可选）                                       |
| `hooks`                      | list   | 钩子配置列表（可选）                                        |
| `description`                | string | 组件描述（可选）                                            |
| `tags`                       | list   | 标签列表（可选）                                            |
| `enable_memory_update`       | bool   | 是否启用记忆更新（默认 false）                              |
| `user_id`                    | string | 用户 ID（可选）                                             |
| `enable_termination_summary` | bool   | 是否生成终止总结（默认 false）                              |
| `termination_summary_prompt` | string | 终止总结提示词（可选）                                      |

### Model 字段

| 字段          | 类型   | 说明                                |
| ------------- | ------ | ----------------------------------- |
| `provider`    | string | 提供商: openai, anthropic, deepseek |
| `model_name`  | string | 模型名称                            |
| `api_key`     | string | API Key                             |
| `base_url`    | string | API Base URL                        |
| `temperature` | float  | 温度参数                            |
| `max_tokens`  | int    | 最大 token 数                       |

### Tool 字段

| 字段           | 类型   | 说明                             |
| -------------- | ------ | -------------------------------- |
| `tool_name`    | string | 内置工具名称                     |
| `module`       | string | 自定义工具模块路径               |
| `class_name`   | string | 自定义工具类名                   |
| `params`       | dict   | 工具参数                         |
| `dependencies` | dict   | 依赖映射 {param: component_name} |

## 目录组织原则

当前配置采用**按功能分类**的组织方式，提高可读性和可维护性：

- **tools/** - 按功能分类：

  - `file_operations/` - 文件操作相关工具
  - `web_operations/` - Web 相关工具
  - `system_operations/` - 系统操作相关工具
  - `utilities/` - 通用工具类

- **storages/** - 按存储类型分类：
  - `session_stores/` - 会话存储（Agent Run/Step 数据）
  - `citation_stores/` - 引用存储（Web 搜索结果等）

## 最佳实践

1. **敏感信息使用环境变量** - API Key 等不要硬编码
2. **禁用未使用的组件** - 设置 `enabled: false`
3. **灵活组织配置** - 可以按环境、团队、功能等维度组织，不限制目录结构
4. **确保 type 字段正确** - 配置类型由 `type` 字段决定，必须与 `ComponentType` 枚举值匹配
5. **避免重复名称** - 相同 `(type, name)` 的配置会被覆盖，建议使用唯一名称
6. **添加注释说明** - 便于团队协作
7. **按功能分类** - 工具和存储配置建议按功能分类组织，提高可读性
