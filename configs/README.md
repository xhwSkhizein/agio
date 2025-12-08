# Agio 配置文件

本目录存放通过 `ConfigSystem` 动态装配的 YAML 配置，支持环境变量占位（`${ENV_VAR}`）。

## 目录结构

```
configs/
├── agents/          # Agent 配置
├── models/          # LLM 模型配置
├── tools/           # 工具配置（含 builtin 参数化）
├── memory/          # Memory 配置
├── knowledge/       # Knowledge 配置
├── storages/        # SessionStore 配置（AgentRun/Step 持久化）
├── observability/   # TraceStore 配置（可观测性数据）
├── workflows/       # Workflow 编排配置
└── hooks/           # 观测/回调配置
```

## 环境变量

常用变量（在 `.env`）：

```bash
AGIO_OPENAI_API_KEY=sk-...
AGIO_ANTHROPIC_API_KEY=sk-...
AGIO_DEEPSEEK_API_KEY=sk-...
AGIO_MONGO_URI=mongodb://localhost:27017  # 持久化可选
AGIO_CONFIG_DIR=./configs                 # API 服务启动时加载
```

## 加载与构建

```python
from agio.config import init_config_system

# 读取目录 -> 解析 -> 拓扑排序 -> 构建实例
config_sys = await init_config_system("./configs")

# 直接获取已构建组件
agent = config_sys.get("code_assistant")
store = config_sys.get("mongodb_session_store")  # 若存在
```

服务启动时 `agio.api.app` 会自动读取 `AGIO_CONFIG_DIR` 并调用 `load_from_directory` + `build_all`。

## 配置示例

### Agent
```yaml
# configs/agents/code_assistant.yaml
type: agent
name: code_assistant
model: gpt4_model
tools:
  - file_read
  - grep
  - bash
system_prompt: |
  You are a helpful coding assistant.
tags: [demo]
```

### Model
```yaml
# configs/models/gpt4.yaml
type: model
name: gpt4_model
provider: openai
model_name: gpt-4o
api_key: ${AGIO_OPENAI_API_KEY}
temperature: 0.3
```

### Tool（内置或自定义）
```yaml
# configs/tools/web_search.yaml
type: tool
name: web_search
module: agio.providers.tools.builtin.web_search_tool
class_name: WebSearchTool
params:
  max_results: 5
```

### Runnable Tool（Agent/Workflow 包装）
```yaml
# 作为工具调用其他 Agent
type: tool
name: helper_agent_tool
module: agio.workflow.runnable_tool
class_name: RunnableTool
params:
  type: agent_tool
  agent: helper_agent   # 需已存在 agent 配置
  name: helper_agent_tool
  description: "Delegate to helper_agent"
```

## 使用提示

- 支持的类型：model/tool/memory/knowledge/session_store/trace_store/agent/workflow
- 构建顺序由 `ConfigLoader` 拓扑排序；循环依赖会抛错（需拆分配置）
- 更新或新增配置可调用 `ConfigSystem.save_config` 触发热重载
- 缺省工具会尝试从内置 registry 创建；未找到则抛出 `ComponentNotFoundError`

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
| `tools` | list | 工具名称列表 |
| `memory` | string | 引用的 Memory 名称 |
| `knowledge` | string | 引用的 Knowledge 名称 |
| `session_store` | string | 引用的 SessionStore 名称（用于 AgentRun/Step 持久化） |
| `trace_store` | string | 引用的 TraceStore 名称（用于可观测性数据） |
| `system_prompt` | string | 系统提示词 |
| `max_steps` | int | 最大执行步数 |

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
