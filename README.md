# Agio

一个现代化、高性能的 Python Agent 框架，专注于简洁性、可观测性和开发者体验。

## 核心特性

- **🚀 Async Native**: 全链路异步设计，原生支持流式输出
- **🎯 Model-Driven Loop**: 将 LLM ↔ Tool 循环下沉至模型层，架构清晰
- **📊 Event-Based**: 统一的事件流同时服务实时渲染与历史回放
- **🔌 可插拔架构**: Tools、Memory、Knowledge、Hooks 通过标准接口注入
- **📈 生产级可观测性**: 内置详细的 Metrics、Tracing 和 Session Summary
- **🎨 类型安全**: Python 3.12+，内部 dataclass，对外 Pydantic，严格类型注解


## 代码风格 & 约定

- Python 3.12+, line length 100. Strict typing is non-negotiable.
- Types: annotate every function param/return and all `State` attributes; prefer `list`/`dict`/`set`. **Forbidden `Any`**.
- Unions: use `T | None` style; avoid `Optional[T]`. Keep generics explicit; 
- Imports: prefer absolute `kumr...`; export via package `__init__.py` where appropriate.
- Naming: modules `snake_case`; classes `PascalCase`; funcs/vars `snake_case`; constants `UPPER_CASE`.
- State helpers: avoid `@classmethod` for accessing contextual state; prefer `@statemethod` so methods work from class or instance while always operating on an instance.
- dataclass for internal objects; prefer `pydantic` for external objects.


## 快速开始

```bash
pip install -r requirements.txt
```

```python
import asyncio
from agio.agent import Agent
from agio.models import Deepseek
from agio.tools import FunctionTool

def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"The weather in {city} is sunny"

async def main():
    agent = Agent(
        model=Deepseek(temperature=0.0),
        tools=[FunctionTool(get_weather)],
        name="my_agent"
    )
    
    async for chunk in agent.arun("What's the weather in Beijing?"):
        print(chunk, end="", flush=True)

asyncio.run(main())
```

## 架构设计

### 核心模块

```
agio/
├── agent/          # Agent 配置容器与生命周期管理
├── runners/        # AgentRunner - 执行引擎，编排 ModelDriver 和 Hooks
├── drivers/        # ModelDriver - LLM ↔ Tool 循环的核心实现
├── core/           # 核心抽象：事件系统、循环配置
├── models/         # 模型抽象层，支持 OpenAI/Deepseek 等
├── tools/          # 工具系统，支持函数装饰器和 MCP
├── execution/      # ToolExecutor - 工具执行引擎
├── memory/         # 记忆系统：短期历史 + 长期语义记忆
├── knowledge/      # 知识库：RAG 向量检索
├── db/             # 持久化存储适配器
└── domain/         # 领域模型：Run, Step, Message, Metrics
```

### 执行流程

```python
async def arun(query: str):
    """
    新架构执行流程：
    1. 初始化 AgentRun，触发 on_run_start hooks
    2. 构建上下文：System Prompt + History + RAG + Memory
    3. 创建 ModelDriver 并配置循环参数
    4. 驱动 ModelDriver.run() 获取事件流：
       - TEXT_DELTA: 流式输出文本
       - TOOL_CALL_STARTED: 工具调用开始
       - TOOL_CALL_FINISHED: 工具执行完成
       - USAGE: Token 使用统计
       - ERROR: 错误处理
    5. 根据事件更新 AgentRun 和 AgentRunStep 状态
    6. 触发相应的 hooks (on_step_start, on_tool_start, on_tool_end, on_step_end)
    7. 完成后触发 on_run_end hooks
    8. 异步更新短期记忆（不阻塞响应）
    """
    # 核心代码示例
    run = AgentRun(...)
    messages = await self._build_context(query, session)
    config = LoopConfig(max_steps=10, temperature=0.7)
    
    async for event in self.driver.run(messages, tools, config):
        if event.type == EventType.TEXT_DELTA:
            yield event.content
        elif event.type == EventType.TOOL_CALL_STARTED:
            # 触发 hooks
            for hook in self.hooks:
                await hook.on_tool_start(run, step, event.tool_calls)
        # ... 处理其他事件
```

## 核心优势

### 1. Model-Driven Loop

将 "LLM 调用 → ToolCall → 执行工具 → 回写消息 → 再次调用" 的完整逻辑下沉至 `ModelDriver`：

- **AgentRunner** 专注于状态管理和 Hook 调度
- **ModelDriver** 负责 LLM ↔ Tool 的完整循环
- **ToolExecutor** 处理工具查找、参数解析、错误捕获

### 2. 事件驱动架构

统一的 `ModelEvent` 流：
- 实时流式输出
- 历史回放
- 细粒度 metrics
- 前端统一渲染

### 3. 可观测性

- **Per-Step Metrics**: Token 消耗、TTFT、执行时长
- **Per-Tool Metrics**: 工具调用次数、成功率、耗时
- **Trace ID**: 完整的请求追踪
- **Snapshot**: 100% 可重放的请求/响应快照

## 开发指南

详见 `docs/` 目录：
- `agio_develop_01_architecture.md` - 架构设计
- `agio_develop_02_domain_models.md` - 领域模型
- `agio_develop_03_core_interfaces.md` - 核心接口
- `agio_develop_04_runtime_loop.md` - 运行时循环

## License

MIT