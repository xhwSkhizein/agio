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

**Getting Started:**
- [Quick Start](./docs/guides/quick-start.md) - 5-minute quick start guide

**Architecture:**
- [Architecture Overview](./docs/architecture/overview.md) - Design philosophy and system architecture
- [Agent System](./docs/architecture/agent-system.md) - Agent execution engine detailed
- [Observability](./docs/architecture/observability.md) - Distributed tracing and monitoring

**Guides:**
- [Tool Configuration](./docs/guides/tool-configuration.md) - Tool configuration and usage
- [API Guide](./docs/guides/api-guide.md) - RESTful API and SSE interface

**Development:**
- [Development and Deployment](./docs/development/dev-and-deploy.md) - Development and deployment guide

📖 **[Browse all documentation](./docs/README.md)**


## 🚀 Quick Start

### Basic Usage

Create and run an Agent programmatically:

```python
import asyncio
from agio import Agent, OpenAIModel

async def main():
    # Create a model
    model = OpenAIModel(
        model_name="gpt-4o",
        api_key="your-api-key"  # or use environment variable OPENAI_API_KEY
    )
    
    # Create an Agent
    agent = Agent(
        model=model,
        name="my_agent",
        system_prompt="You are a helpful assistant.",
        max_steps=10
    )
    
    # Run the Agent (streaming mode)
    async for event in agent.run_stream("Hello! What can you help me with?"):
        if event.type == "STEP_CREATED" and event.step:
            print(f"{event.step.role}: {event.step.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Start API Server

You can also use the API server (requires configuration files):

```bash
# Start server with default settings
agio-server

# Custom host and port
agio-server --host 127.0.0.1 --port 8000

# Development mode (auto-reload)
agio-server --reload

# Production mode (multi-process)
agio-server --workers 4
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
from agio import Agent, OpenAIModel, MongoSessionStore

# Create model
model = OpenAIModel(model_name="gpt-4o")

# Optional: Create session store for conversation history
session_store = MongoSessionStore(
    uri="mongodb://localhost:27017",
    db_name="agio"
)

# Create Agent
agent = Agent(
    model=model,
    session_store=session_store,
    name="my-agent",
    system_prompt="You are a helpful assistant.",
)

# Run Agent
async for event in agent.run_stream("Hello!"):
    if event.type == "STEP_CREATED" and event.step:
        print(f"{event.step.role}: {event.step.content}")
```

### Using Tools

Add tools to your Agent to extend its capabilities:

```python
from agio import Agent, OpenAIModel
from agio.tools import get_tool_registry

# Get tool registry
tool_registry = get_tool_registry()

# Create tools
bash_tool = tool_registry.get("bash")
file_read_tool = tool_registry.get("file_read")

# Create Agent with tools
agent = Agent(
    model=OpenAIModel(model_name="gpt-4o"),
    tools=[bash_tool, file_read_tool],
    system_prompt="You are a helpful assistant with access to bash and file reading tools.",
)

# Agent can now use tools
async for event in agent.run_stream("List files in current directory"):
    if event.type == "STEP_CREATED" and event.step:
        print(f"{event.step.role}: {event.step.content}")


## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🌐 Language

- [English](README.md) (Current)
- [中文](README_zh.md)
