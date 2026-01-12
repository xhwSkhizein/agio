# Agio - Agent 框架

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

Agio 是一个**简洁、强大**的 Agent 框架，专注于核心功能：Agent 执行、事件流和可观测性。

## 设计哲学

**简单优于复杂**：Agio 主动移除了过度抽象，将重点放在实际需要的功能上。

**核心特性**：
- 🤖 **Agent 优先**：Agent 是唯一的执行单元，简单直接
- 📡 **Wire 事件流**：统一的事件流架构，支持实时 SSE 推送
- 🔧 **直接编码**：通过代码直接创建和配置，无需复杂的配置系统
- 🧩 **组合能力**：通过 AgentTool 实现 Agent 嵌套和多 Agent 协作
- 📊 **可观测性**：完整的追踪和监控支持

## 📦 安装

### 系统要求

Agio 需要以下系统依赖：

- **ripgrep (rg)**：grep 工具需要。安装方式：
  - **Linux (Ubuntu/Debian)**：`sudo apt-get install ripgrep`
  - **macOS**：`brew install ripgrep`
  - **Windows**：`choco install ripgrep` 或 `scoop install ripgrep`

### 从 PyPI 安装（推荐）

```bash
pip install agio
```

### 从源码安装

```bash
git clone https://github.com/your-org/agio.git
cd agio
pip install -e .
```

### 安装开发依赖

```bash
pip install agio[dev]
```

## 📚 文档

完整的架构和使用文档请参考：

**快速开始：**
- [快速开始](./docs/guides/quick-start.md) - 5分钟快速上手指南

**架构文档：**
- [架构总览](./docs/architecture/overview.md) - 设计理念和系统架构
- [Agent 系统](./docs/architecture/agent-system.md) - Agent 执行引擎详解
- [可观测性](./docs/architecture/observability.md) - 分布式追踪和监控

**使用指南：**
- [工具配置](./docs/guides/tool-configuration.md) - 工具配置和使用
- [API 指南](./docs/guides/api-guide.md) - RESTful API 和 SSE 接口

**开发指南：**
- [开发和部署](./docs/development/dev-and-deploy.md) - 开发和部署指南

📖 **[浏览所有文档](./docs/README.md)**

## 🚀 快速开始

### 基础使用

创建并运行一个 Agent：

```python
import asyncio
from agio import Agent, OpenAIModel

async def main():
    # 创建模型
    model = OpenAIModel(
        model_name="gpt-4o",
        api_key="your-api-key"  # 或使用环境变量 OPENAI_API_KEY
    )
    
    # 创建 Agent
    agent = Agent(
        model=model,
        name="my_agent",
        system_prompt="你是一个有帮助的助手。",
        max_steps=10
    )
    
    # 运行 Agent（流式模式）
    async for event in agent.run_stream("你好！你能帮我做什么？"):
        if event.type == "STEP_CREATED" and event.step:
            print(f"{event.step.role}: {event.step.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 启动 API 服务器

你也可以使用 API 服务器（需要配置文件）：

```bash
# 使用默认设置启动服务器
agio-server

# 自定义主机和端口
agio-server --host 127.0.0.1 --port 8000

# 开发模式（自动重载）
agio-server --reload

# 生产模式（多进程）
agio-server --workers 4
```

### 集成到现有 FastAPI 应用

#### 方式 1：仅集成 API（推荐用于微服务架构）

```python
from fastapi import FastAPI
from agio.api import create_router

app = FastAPI(title="My Application")

# 集成 Agio API（挂载到 /agio 路径）
app.include_router(create_router(prefix="/agio"))

# 你的其他路由
@app.get("/")
async def root():
    return {"message": "Hello World"}
```

#### 方式 2：集成 API + 前端控制面板（推荐用于完整集成）

```python
from fastapi import FastAPI
from agio.api import create_app_with_frontend

# 创建包含 API 和前端的完整应用
# API 在 /agio，前端在根路径 /
app = create_app_with_frontend(
    api_prefix="/agio",
    frontend_path="/",
    enable_frontend=True,
)

# 你的其他路由（注意不要与前端路径冲突）
@app.get("/api/custom")
async def custom_endpoint():
    return {"message": "Custom endpoint"}
```

#### 方式 3：自定义路径挂载

```python
from fastapi import FastAPI
from agio.api import create_router, mount_frontend

app = FastAPI(title="My Application")

# 挂载 API 到自定义路径
app.include_router(create_router(prefix="/admin/agio"))

# 挂载前端到自定义路径
mount_frontend(app, path="/admin/agio/panel", api_prefix="/admin/agio")

# 你的其他路由
@app.get("/")
async def root():
    return {"message": "Hello World"}
```

#### 方式 4：仅使用 Agio 库（不启动 API 服务器）

```python
from agio import Agent, OpenAIModel, MongoSessionStore

# 创建模型
model = OpenAIModel(model_name="gpt-4o")

# 可选：创建 Session Store 用于对话历史
session_store = MongoSessionStore(
    uri="mongodb://localhost:27017",
    db_name="agio"
)

# 创建 Agent
agent = Agent(
    model=model,
    session_store=session_store,
    name="my-agent",
    system_prompt="你是一个有帮助的助手。",
)

# 运行 Agent
async for event in agent.run_stream("你好！"):
    if event.type == "STEP_CREATED" and event.step:
        print(f"{event.step.role}: {event.step.content}")
```

### 使用工具

为 Agent 添加工具以扩展其能力：

```python
from agio import Agent, OpenAIModel
from agio.tools import get_tool_registry

# 获取工具注册表
tool_registry = get_tool_registry()

# 创建工具
bash_tool = tool_registry.get("bash")
file_read_tool = tool_registry.get("file_read")

# 创建带工具的 Agent
agent = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    tools=[bash_tool, file_read_tool],
    system_prompt="你是一个有帮助的助手，可以使用 bash 和文件读取工具。",
)

# Agent 现在可以使用工具了
async for event in agent.run_stream("列出当前目录的文件"):
    if event.type == "STEP_CREATED" and event.step:
        print(f"{event.step.role}: {event.step.content}")
```

### 多 Agent 协作

使用 AgentTool 实现 Agent 嵌套：

```python
from agio import Agent, OpenAIModel, as_tool

# 创建专家 Agent
research_agent = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    name="research_agent",
    system_prompt="你是研究专家。",
)

# 转换为工具
research_tool = as_tool(
    research_agent,
    description="擅长研究任务的专家"
)

# 创建编排 Agent
orchestrator = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    tools=[research_tool],  # 使用 Agent 作为工具
    name="orchestrator",
)
```

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🌐 语言

- [English](README.md)
- [中文](README_zh.md)（当前）