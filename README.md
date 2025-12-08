# Agio - Modern Agent Framework

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

Agio 是一个专注**可组合、多代理编排**的现代 Agent 框架，提供一致的事件流、工具系统、可观测性与配置驱动能力。

## ✨ 设计要点

- **清晰分层**：`domain`（纯模型）→ `runtime`（执行引擎）→ `providers`（LLM/存储/工具）→ `config`（动态装配）
- **统一事件流**：`StepEvent` 描述 LLM 输出、工具调用、运行完成等全过程，便于回放与观测
- **可插拔工具**：内置文件/Web/系统工具，可通过注册表或 YAML 配置扩展
- **配置驱动**：`ConfigSystem` 从 `configs/` 目录加载组件，按依赖拓扑构建并支持热更新
- **可观测性内置**：集中埋点与 LLM 调用记录，前端仪表盘实时查看
- **API+前端**：FastAPI 控制平面 + React 仪表盘，开箱即用

## 🚀 安装与运行

```bash
# 安装依赖（推荐）
uv sync
```

开发环境运行 FastAPI：

```bash
python main.py  # 监听 0.0.0.0:8900，API 前缀 /agio
```

## 🔧 最小示例（代码方式）

```python
import asyncio
from agio import Agent, OpenAIModel, StepEventType
from agio.providers.tools.builtin import FileReadTool, GrepTool

async def main():
    agent = Agent(
        model=OpenAIModel(model_name="gpt-4o"),
        tools=[FileReadTool(), GrepTool()],
        system_prompt="You are a helpful assistant.",
    )

    async for event in agent.arun_stream("Read README.md and summarize"):
        if event.type == StepEventType.STEP_DELTA:
            print(event.delta.content, end="")

asyncio.run(main())
```

## 🧩 配置驱动示例

```python
import asyncio
from agio.config import init_config_system

async def main():
    config_sys = await init_config_system("./configs")
    agent = config_sys.get("code_assistant")

    async for event in agent.arun_stream("Find logging usage"):
        if event.type.name == "RUN_COMPLETED":
            print(event.data.get("response"))

asyncio.run(main())
```

`.env` 关键变量：

```bash
AGIO_OPENAI_API_KEY=sk-...
AGIO_ANTHROPIC_API_KEY=sk-...
AGIO_DEEPSEEK_API_KEY=sk-...
AGIO_MONGO_URI=mongodb://localhost:27017  # 可选，启用持久化
AGIO_CONFIG_DIR=./configs                  # API 服务启动时加载
```

## 📦 目录速览

```
agio/
├── agent.py          # Agent 容器，遵循 Runnable 协议
├── domain/           # 纯领域模型：Step/StepEvent/ToolResult 等
├── runtime/          # StepRunner/Executor/ToolExecutor 控制循环
├── providers/        # LLM、存储库、工具（含 builtin 工具）
├── config/           # ConfigSystem、Pydantic schema、构建器
├── api/              # FastAPI 控制平面（默认前缀 /agio）
├── workflow/         # 多阶段/条件/并行编排与可运行工具封装
└── observability/    # LLM 调用追踪与指标
```

更多细节参见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 🧪 测试

```bash
pytest -q
```

## 📚 相关文档

- 架构文档：`docs/ARCHITECTURE.md`
- API：运行服务后访问 `http://localhost:8900/agio/docs`
- 前端：`agio-frontend/`（Vite + React 18）

## 🤝 贡献

欢迎提交 PR / Issue，参与共建。请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 📄 许可证

MIT License
