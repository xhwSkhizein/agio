# Agio 配置文件

本目录包含 Agio 组件的 YAML 配置文件。

## 目录结构

```
configs/
├── agents/          # Agent 配置
├── models/          # LLM 模型配置 (可选)
├── tools/           # 工具配置 (可选)
├── memory/          # 记忆系统配置
├── knowledge/       # 知识库配置
├── repositories/    # 存储库配置
└── hooks/           # Hook 配置
```

## 环境变量

配置文件支持 `${ENV_VAR}` 语法引用环境变量：

```bash
# .env
AGIO_OPENAI_API_KEY=sk-...
AGIO_DEEPSEEK_API_KEY=sk-...
AGIO_ANTHROPIC_API_KEY=sk-...
AGIO_MONGO_URI=mongodb://localhost:27017
```

## 使用方式

### 加载配置

```python
from agio.config import init_config_system

# 加载并构建所有组件
config_sys = await init_config_system("./configs")

# 获取组件
agent = config_sys.get("my_agent")
model = config_sys.get("gpt4_model")
```

### 配置示例

#### Agent 配置

```yaml
# configs/agents/code_assistant.yaml
type: agent
name: code_assistant
enabled: true

model: gpt4_model
tools:
  - file_read
  - file_edit
  - grep
  - bash

system_prompt: |
  You are a helpful coding assistant.

max_steps: 30
```

#### Model 配置

```yaml
# configs/models/gpt4.yaml
type: model
name: gpt4_model
enabled: true

provider: openai
model_name: gpt-4-turbo
api_key: ${AGIO_OPENAI_API_KEY}
temperature: 0.7
```

#### Tool 配置

```yaml
# configs/tools/custom_tool.yaml
type: tool
name: my_custom_tool
enabled: true

module: my_package.tools
class_name: MyCustomTool
params:
  timeout: 30
  max_retries: 3
```

## 配置字段说明

### 通用字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 组件类型: agent, model, tool, memory, knowledge, repository |
| `name` | string | 组件唯一名称 |
| `enabled` | bool | 是否启用 (默认 true) |

### Agent 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `model` | string | 引用的 Model 名称 |
| `tools` | list | 工具名称列表 |
| `memory` | string | 引用的 Memory 名称 |
| `knowledge` | string | 引用的 Knowledge 名称 |
| `repository` | string | 引用的 Repository 名称 |
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
