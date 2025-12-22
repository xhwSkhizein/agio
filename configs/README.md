# Agio 配置文件

本目录存放通过 `ConfigSystem` 动态装配的 YAML 配置，支持环境变量占位（`${ENV_VAR}`）。

## 目录结构

```
configs/
├── agents/          # Agent 配置
├── models/          # LLM 模型配置
├── tools/           # 工具配置（内置 + 自定义）
├── storages/        # SessionStore 配置（内存/MongoDB）
├── observability/   # TraceStore 配置（可观测性数据）
└── workflows/       # Workflow 编排配置（示例）
```

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

```python
from agio.config import init_config_system

# 读取目录 -> 解析 -> 验证 -> 拓扑排序 -> 构建实例
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

| 名称 | 描述 |
|------|------|
| `file_read` | 读取文件内容（支持文本和图片） |
| `file_edit` | 编辑文件（结构化补丁） |
| `file_write` | 写入文件 |
| `grep` | 使用 ripgrep 搜索文件内容 |
| `glob` | 按模式查找文件 |
| `ls` | 列出目录内容 |
| `bash` | 执行 shell 命令 |
| `web_search` | Web 搜索（需要 SERPER_API_KEY） |
| `web_fetch` | 获取网页内容并可选 LLM 处理 |
| `get_tool_result` | 查询最近的工具执行结果 |

## 配置示例

### Agent (带工具)
```yaml
type: agent
name: code_assistant
model: deepseek  # 引用 models/deepseek.yaml
tools:
  - file_read    # 引用内置工具
  - grep
  - bash
session_store: mongodb_session_store

system_prompt: |
  You are a helpful coding assistant.
```

### Agent (带 Agent/Workflow 作为工具)
```yaml
type: agent
name: orchestrator
model: deepseek
tools:
  - web_search  # 普通工具
  
  # Agent 作为工具
  - type: agent_tool
    agent: tech_researcher
    description: "Delegate research tasks"
  
  # Workflow 作为工具
  - type: workflow_tool
    workflow: parallel_research
    description: "Run parallel research"
```

### Workflow (Pipeline)
```yaml
type: workflow
name: research_pipeline
workflow_type: pipeline
stages:
  - id: research
    runnable: researcher
    input: "Research: {query}"
  - id: analyze
    runnable: analyst
    input: "Analyze: {research}"
    condition: "{research} contains 'data'"  # 条件执行
```

### Workflow (Parallel)
```yaml
type: workflow
name: parallel_research
workflow_type: parallel
stages:
  - id: web_research
    runnable: tech_researcher
    input: "Web research: {query}"
  - id: code_research
    runnable: code_analyzer
    input: "Code analysis: {query}"
merge_template: |
  Web: {web_research}
  Code: {code_research}
```

### Workflow (Loop)
```yaml
type: workflow
name: quality_loop
workflow_type: loop
stages:
  - id: review
    runnable: quality_reviewer
    input: "Review: {query}"
  - id: improve
    runnable: doc_writer
    input: "Improve based on: {review}"
    condition: "{review} contains 'NEEDS_REVISION'"
condition: "{review} contains 'NEEDS_REVISION'"
max_iterations: 3
```

### 嵌套 Workflow (复杂场景)
```yaml
type: workflow
name: complex_workflow
workflow_type: pipeline
stages:
  - id: plan
    runnable: task_planner
    input: "{query}"
  
  - id: research
    runnable:
      # 内联嵌套的并行工作流
      id: nested_parallel
      workflow_type: parallel
      stages:
        - id: branch_a
          runnable: agent_a
          input: "{query}"
        - id: branch_b
          runnable: agent_b
          input: "{query}"
      merge_template: "A: {branch_a}\nB: {branch_b}"
    input: "{plan}"
```

## 使用提示

- 支持的类型：model/tool/memory/knowledge/session_store/trace_store/agent/workflow
- 构建顺序由 `DependencyResolver` 统一拓扑排序；**循环依赖会立即抛出异常（fail fast）**
- 更新或新增配置可调用 `ConfigSystem.save_config` 触发热重载，会自动级联重建依赖者
- 缺省工具会尝试从内置 registry 创建；未找到则抛出 `ComponentNotFoundError`
- 所有配置通过 Pydantic 模型验证，确保类型安全

### 通用字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 组件类型: agent, model, tool, memory, knowledge, session_store, trace_store |
| `name` | string | 组件唯一名称 |
| `enabled` | bool | 是否启用 (默认 true) |

### Agent 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `model` | string | 引用的 Model 名称 |
| `tools` | list | 工具引用列表（支持字符串、agent_tool、workflow_tool） |
| `memory` | string | 引用的 Memory 名称（可选） |
| `knowledge` | string | 引用的 Knowledge 名称（可选） |
| `session_store` | string | 引用的 SessionStore 名称（用于 AgentRun/Step 持久化，可选） |
| `system_prompt` | string | 系统提示词（可选） |
| `max_steps` | int | 最大执行步数（默认 10） |
| `max_tokens` | int | 最大 token 数（可选） |
| `hooks` | list | 钩子配置列表（可选） |
| `description` | string | 组件描述（可选） |
| `tags` | list | 标签列表（可选） |
| `enable_memory_update` | bool | 是否启用记忆更新（默认 false） |
| `user_id` | string | 用户 ID（可选） |
| `enable_termination_summary` | bool | 是否生成终止总结（默认 false） |
| `termination_summary_prompt` | string | 终止总结提示词（可选） |

### Model 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `provider` | string | 提供商: openai, anthropic, deepseek |
| `model_name` | string | 模型名称 |
| `api_key` | string | API Key |
| `base_url` | string | API Base URL |
| `temperature` | float | 温度参数 |
| `max_tokens` | int | 最大 token 数 |

### Tool 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `tool_name` | string | 内置工具名称 |
| `module` | string | 自定义工具模块路径 |
| `class_name` | string | 自定义工具类名 |
| `params` | dict | 工具参数 |
| `dependencies` | dict | 依赖映射 {param: component_name} |

## 最佳实践

1. **敏感信息使用环境变量** - API Key 等不要硬编码
2. **禁用未使用的组件** - 设置 `enabled: false`
3. **合理组织配置** - 按类型放入对应目录
4. **添加注释说明** - 便于团队协作
