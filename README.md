# Agio - an Agent Framework

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

Agio is a modern Agent framework focused on **composable, multi-agent orchestration**, providing consistent event streaming, tool system, observability, and configuration-driven capabilities.

## 📦 Installation

### System Requirements

Agio requires the following system dependencies:

- **ripgrep (rg)**: Required for the `grep` tool. Install via:
  - **Linux (Ubuntu/Debian)**: `sudo apt-get install ripgrep`
  - **macOS**: `brew install ripgrep`
  - **Windows**: `choco install ripgrep` or `scoop install ripgrep`

### Install from PyPI (Recommended)

```bash
pip install agio
```

### Install from Source

```bash
git clone https://github.com/your-org/agio.git
cd agio
pip install -e .
```

### Install Development Dependencies

```bash
pip install agio[dev]
```

## 📚 Documentation

For complete architecture and usage documentation, please refer to:

- [Architecture Design](./docs/ARCHITECTURE.md) - Overall architecture overview and design philosophy
- [Configuration System](./docs/CONFIG_SYSTEM_V2.md) - Configuration-driven architecture and usage guide
- [Tool Configuration](./docs/TOOL_CONFIGURATION.md) - Tool configuration methods and environment variable support
- [Agent System](./docs/AGENT_SYSTEM.md) - Agent execution engine and LLM call loop
- [Observability](./docs/OBSERVABILITY.md) - Distributed tracing and Trace querying
- [API Control Panel](./docs/API_CONTROL_PANEL.md) - RESTful API and streaming event interfaces
- [API Integration Guide](./agio/api/README.md) - How to integrate Agio API and frontend into existing FastAPI applications

## 🚀 Quick Start

### Start API Server

After installation, you can use the command-line tool to start the Agio API server:

```bash
# Use default configuration (0.0.0.0:8900)
agio-server

# Custom host and port
agio-server --host 127.0.0.1 --port 8000

# Development mode (auto-reload)
agio-server --reload

# Production mode (multi-process)
agio-server --workers 4
```

### Basic Usage

```python
from agio import Agent, ExecutionConfig, get_config_system

# Initialize configuration system
config_system = get_config_system()

# Create Agent
agent = Agent.from_config("your-agent-config.yaml")

# Run Agent
result = await agent.run("Hello, Agio!")
```

### Integrate into Existing FastAPI Application

#### Method 1: API Only (Recommended for Microservice Architecture)

```python
from fastapi import FastAPI
from agio.api import create_router

app = FastAPI(title="My Application")

# Integrate Agio API (mounted at /agio path)
app.include_router(create_router(prefix="/agio"))

# Your other routes
@app.get("/")
async def root():
    return {"message": "Hello World"}
```

#### Method 2: API + Frontend Control Panel (Recommended for Full Integration)

```python
from fastapi import FastAPI
from agio.api import create_app_with_frontend

# Create complete application with API and frontend
# API at /agio, frontend at root path /
app = create_app_with_frontend(
    api_prefix="/agio",
    frontend_path="/",
    enable_frontend=True,
)

# Your other routes (be careful not to conflict with frontend paths)
@app.get("/api/custom")
async def custom_endpoint():
    return {"message": "Custom endpoint"}
```

#### Method 3: Custom Path Mounting

```python
from fastapi import FastAPI
from agio.api import create_router, mount_frontend

app = FastAPI(title="My Application")

# Mount API to custom path
app.include_router(create_router(prefix="/admin/agio"))

# Mount frontend to custom path
mount_frontend(app, path="/admin/agio/panel", api_prefix="/admin/agio")

# Your other routes
@app.get("/")
async def root():
    return {"message": "Hello World"}
```

#### Method 4: Use Agio Library Only (No API Server)

```python
from agio import Agent, get_config_system

# Use Agio core functionality directly without starting API server
config_system = get_config_system()
await config_system.load_from_directory("./configs")

agent = await config_system.get_agent("my-agent")
result = await agent.run("Hello!")
```

### Configuration-Driven

Agio uses YAML configuration files to define Agents and tools. Example configuration files are located in the `configs/` directory.

See [configs/README.md](./configs/README.md) for details.


## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🌐 Language

- [English](README.md) (Current)
- [中文](README_zh.md)
