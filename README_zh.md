# Agio - an Agent Framework

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

Agio 是一个专注**可组合、多代理编排**的现代 Agent 框架，提供一致的事件流、工具系统、可观测性与配置驱动能力。

## 📦 安装

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

- [架构设计](./docs/ARCHITECTURE.md) - 整体架构概述和设计理念
- [配置系统](./docs/CONFIG_SYSTEM_V2.md) - 配置驱动架构和使用指南
- [工具配置](./docs/TOOL_CONFIGURATION.md) - 工具配置方式和环境变量支持
- [Agent 系统](./docs/AGENT_SYSTEM.md) - Agent 执行引擎和 LLM 调用循环
- [Workflow 编排](./docs/WORKFLOW_ORCHESTRATION.md) - Pipeline/Loop/Parallel 工作流
- [Runnable 协议](./docs/RUNNABLE_PROTOCOL.md) - 统一执行接口和嵌套能力
- [可观测性](./docs/OBSERVABILITY.md) - 分布式追踪和 Trace 查询
- [API Control Panel](./docs/API_CONTROL_PANEL.md) - RESTful API 和流式事件接口
- [API 集成指南](./agio/api/README.md) - 如何在现有 FastAPI 应用中集成 Agio API 和前端

## 🚀 快速开始

### 启动 API 服务器

安装后，可以使用命令行工具启动 Agio API 服务器：

```bash
# 使用默认配置（0.0.0.0:8900）
agio-server

# 自定义主机和端口
agio-server --host 127.0.0.1 --port 8000

# 开发模式（自动重载）
agio-server --reload

# 生产模式（多进程）
agio-server --workers 4
```

### 基本使用

```python
from agio import Agent, ExecutionConfig, get_config_system

# 初始化配置系统
config_system = get_config_system()

# 创建 Agent
agent = Agent.from_config("your-agent-config.yaml")

# 运行 Agent
result = await agent.run("Hello, Agio!")
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

#### 方式 4：仅使用 Agio 库功能（不启动 API）

```python
from agio import Agent, get_config_system

# 直接使用 Agio 核心功能，不启动 API 服务器
config_system = get_config_system()
await config_system.load_from_directory("./configs")

agent = await config_system.get_agent("my-agent")
result = await agent.run("Hello!")
```

### 配置驱动

Agio 使用 YAML 配置文件来定义 Agent、工具和工作流。配置文件示例位于 `configs/` 目录。

详见 [configs/README.md](./configs/README.md)


## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🌐 语言

- [English](README.md)
- [中文](README_zh.md) (当前)