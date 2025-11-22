# Agio - Agent Framework

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61dafb.svg)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5+-blue.svg)](https://www.typescriptlang.org/)
[![uv](https://img.shields.io/badge/uv-managed-blue.svg)](https://github.com/astral-sh/uv)

**Agio** 是一个现代化的 Agent 框架，提供完整的配置管理、执行控制、API 接口和可观测平台。

## ✨ 核心特性

### 🎯 配置系统
- **YAML 配置驱动** - 声明式定义 Agent、Model、Tool
- **动态热重载** - 无需重启即可更新配置
- **环境变量支持** - `${ENV_VAR}` 语法
- **配置继承** - `extends` 复用配置

### 💾 执行控制
- **Checkpoint 快照** - 保存完整执行状态
- **Resume/Fork** - 从任意点恢复或分支
- **Pause/Resume/Cancel** - 灵活控制执行
- **时光旅行调试** - 回到任意执行步骤

### 🚀 FastAPI Backend
- **RESTful API** - 完整的 CRUD 操作
- **SSE 流式传输** - 实时 Chat 交互
- **自动文档** - Swagger UI + ReDoc
- **执行控制 API** - Pause/Resume/Cancel 端点

### 🎨 React Frontend
- **现代化 UI** - TailwindCSS + 深色模式
- **实时 Chat** - SSE 流式消息
- **Agent 管理** - 可视化配置界面
- **仪表盘** - 系统概览和指标

## 🚀 快速开始

### 前置要求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (Python 包管理器)
- Node.js 18+

### 安装 uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 一键启动

```bash
# 启动服务（后端 + 前端）
./start.sh
```

启动脚本会自动:
1. 安装 uv (如果未安装)
2. 使用 uv 同步 Python 依赖
3. 安装前端依赖
4. 启动后端和前端服务

访问:
- **前端**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/api/health

### 手动启动

#### 后端 (使用 uv)

```bash
# 同步依赖
uv sync

# 启动服务
uv run uvicorn agio.api.app:app --reload

# 或使用 Python 脚本
uv run python main.py
```

#### 前端

```bash
cd agio-frontend
npm install
npm run dev
```

### 停止服务

```bash
./stop.sh
```

## 📁 项目结构

```
agio/
├── agio/
│   ├── agent/              # Agent 核心
│   ├── models/             # LLM 模型
│   ├── tools/              # 工具集成
│   ├── memory/             # 记忆系统
│   ├── knowledge/          # 知识库
│   ├── registry/           # 配置系统 ⭐
│   │   ├── models.py       # Pydantic 配置模型
│   │   ├── base.py         # 组件注册表
│   │   ├── loader.py       # YAML 加载器
│   │   ├── factory.py      # 组件工厂
│   │   └── README.md
│   ├── execution/          # 执行控制 ⭐
│   │   ├── checkpoint.py   # Checkpoint 模型
│   │   ├── control.py      # 执行控制器
│   │   ├── resume.py       # 恢复执行
│   │   ├── fork.py         # Fork 管理
│   │   └── README.md
│   └── api/                # FastAPI Backend ⭐
│       ├── app.py          # FastAPI 应用
│       ├── routes/         # API 路由
│       └── README.md
├── agio-frontend/          # React Frontend ⭐
│   ├── src/
│   │   ├── components/     # 组件
│   │   ├── pages/          # 页面
│   │   └── services/       # API 服务
│   └── README.md
├── configs/                # 配置文件
│   ├── models/             # Model 配置
│   ├── agents/             # Agent 配置
│   └── tools/              # Tool 配置
├── tests/                  # 测试
├── pyproject.toml          # uv 项目配置
├── start.sh                # 一键启动脚本
└── README.md
```

## 📝 配置示例

### Model 配置

```yaml
# configs/models/gpt4.yaml
type: model
name: gpt4
provider: openai
model: gpt-4-turbo-preview
api_key: ${OPENAI_API_KEY}
temperature: 0.7
```

### Agent 配置

```yaml
# configs/agents/assistant.yaml
type: agent
name: assistant
model: gpt4
system_prompt: "You are a helpful assistant."
tools:
  - search_tool
  - calculator
```

## 🔧 使用示例

### Python API

```python
from agio.registry import load_from_config, get_registry

# 加载配置
load_from_config("./configs")

# 获取 Agent
registry = get_registry()
agent = registry.get("assistant")

# 运行
async for chunk in agent.arun("Hello!"):
    print(chunk, end="", flush=True)
```

### REST API

```bash
# 列出 Agents
curl http://localhost:8000/api/agents

# Chat (流式)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "assistant", "message": "Hello", "stream": true}'

# 暂停执行
curl -X POST http://localhost:8000/api/runs/{run_id}/pause
```

## 📊 测试

```bash
# 运行所有测试
uv run pytest

# 配置系统测试
uv run pytest tests/test_registry.py -v

# 执行控制测试
uv run pytest tests/test_execution.py -v

# API 测试
uv run pytest tests/test_api.py -v
```

**测试结果**: 24+ tests passing ✅

## 🛠️ 开发

### 安装开发依赖

```bash
uv sync --all-extras
```

### 代码格式化

```bash
uv run black agio/
uv run isort agio/
```

### 类型检查

```bash
uv run mypy agio/
```

## 📚 文档

- [配置系统文档](agio/registry/README.md)
- [执行控制文档](agio/execution/README.md)
- [API 文档](agio/api/README.md)
- [前端文档](agio-frontend/README.md)
- [项目总结](PROJECT_SUMMARY.md)

详细设计文档:
- [配置系统设计](agio/registry/DESIGN.md)
- [执行控制设计](agio/execution/DESIGN.md)
- [API 设计](agio/api/DESIGN.md)
- [前端设计](agio-frontend/DESIGN.md)

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 🙏 致谢

- [uv](https://github.com/astral-sh/uv) - 极速 Python 包管理器
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化 Python Web 框架
- [React](https://reactjs.org/) - UI 库
- [TailwindCSS](https://tailwindcss.com/) - CSS 框架
- [Pydantic](https://pydantic.dev/) - 数据验证

---

**Built with ❤️ by the Agio Team**
