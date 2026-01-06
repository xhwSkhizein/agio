# Project Context

## Purpose
Agio is a modern AI Agent framework focused on **composable, multi-agent orchestration**. It provides a consistent event streaming architecture, tool system, observability, and configuration-driven capabilities to build and manage complex agentic workflows.

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, uvicorn
- **Frontend**: TypeScript, React, Vite, Tailwind CSS, TanStack Query, Zustand
- **LLM Integration**: OpenAI, Anthropic
- **Data & Middleware**: Redis, MongoDB (Motor), SQLite (aiosqlite)
- **Observability**: Distributed tracing (Traces/Spans), OTLP, structlog
- **Tools & Utilities**: Playwright (Browser), BeautifulSoup4/Trafilatura (Web scraping), ripgrep (rg)

## Project Conventions

### Code Style
- **Principles**: Follow **SOLID** and **KISS** principles strictly.
- **Language**: English for code, documentation, and comments. Chinese for communication.
- **Naming**: `snake_case` for variables/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- **Type Hints**: Mandatory for all parameters and return values (using Python 3.10+ `|` syntax).
- **Docstrings**: Required for all modules, classes, and public methods.
- **Imports**: Organized as Standard Library → Third-party → Local (using absolute imports). No local imports allowed.
- **Formatting**: Max line length 100 characters. Single function < 50 lines, single class < 500 lines.

### Architecture Patterns
- **Wire-based Event Stream**: All executions use a unified `Wire` channel for real-time `StepEvent` streaming (SSE).
- **Runnable Protocol**: Core abstraction for execution; Agents implement `Runnable` for nesting and `RunnableAsTool` wrapping.
- **Configuration-Driven**: YAML-defined components with automatic dependency resolution, topological sorting, and hot reloading.
- **Multi-Agent Orchestration**: Support for nested Agent calls and Agent-as-a-Tool patterns.

### Testing Strategy
- **Framework**: `pytest` with `pytest-asyncio` for asynchronous testing.
- **Linting & Type Checking**: `black`, `isort`, and `mypy` for code quality.
- **Requirement**: New features should include corresponding unit or integration tests.

### Git Workflow
- **CI/CD**: GitHub Actions for automated testing and validation.
- **Commits**: Descriptive commit messages reflecting the changes made.

## Domain Context
- **Agentic Orchestration**: Understanding of multi-agent collaboration, tool use, and long-running execution loops.
- **Observability**: Distributed tracing concepts (Traces, Spans) for debugging agent execution flows.
- **Skill System**: Progressive disclosure of agent capabilities via `SkillRegistry` and `SkillLoader`.

## Important Constraints
- **Backward Compatibility**: Do not maintain backward compatibility unless explicitly requested; remove legacy code and comments promptly.
- **Circular Dependencies**: Resolve via refactoring, not via lazy imports or string annotations.
- **System Dependencies**: Requires `ripgrep (rg)` for the grep tool capability.

## External Dependencies
- **LLM Providers**: OpenAI API, Anthropic API.
- **Databases**: Redis for real-time state, MongoDB for persistent sessions and traces.
- **Browser Automation**: Playwright for web-based tools.
