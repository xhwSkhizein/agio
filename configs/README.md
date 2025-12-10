# Agio 配置文件

本目录存放通过 `ConfigSystem` 动态装配的 YAML 配置，支持环境变量占位（`${ENV_VAR}`）。

## 目录结构

```
configs/
├── agents/          # Agent 配置
│   ├── 基础 Agent (simple_assistant, deepseek_assistant)
│   ├── 专业 Agent (tech_researcher, code_analyzer, doc_writer, ...)
│   └── 编排 Agent (master_orchestrator, orchestra_example)
├── models/          # LLM 模型配置 (当前仅启用 deepseek)
├── tools/           # 工具配置（9 个内置工具）
├── memory/          # Memory 配置
├── knowledge/       # Knowledge 配置
├── storages/        # SessionStore 配置（MongoDB 持久化）
├── observability/   # TraceStore 配置（可观测性数据）
├── workflows/       # Workflow 编排配置
│   ├── parallel_research.yaml     # 并行研究工作流
│   ├── quality_loop.yaml          # 质量迭代工作流
│   ├── conditional_pipeline.yaml  # 条件路由工作流
│   ├── doc_generation_system.yaml # 完整文档生成系统
│   └── research_pipeline.yaml     # 简单研究流水线
└── hooks/           # 观测/回调配置
```

## 环境变量

必需变量（在 `.env`）：

```bash
# 模型配置 (当前仅使用 DeepSeek)
DEEPSEEK_API_KEY=sk-...

# 持久化存储 (MongoDB)
AGIO_MONGO_URI=mongodb://localhost:27017
AGIO_MONGO_DB=agio

# 配置目录
AGIO_CONFIG_DIR=./configs

# 可选：Web 搜索 (Serper API)
SERPER_API_KEY=...
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
