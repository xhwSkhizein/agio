# Agio 开发文档 01: 架构设计与路线图

## 1. 设计愿景

Agio 旨在构建一个基于 Python 3.12+ 的现代化 Agent 框架。
核心差异化特性：
1.  **Async Native**: 全链路异步设计，拒绝同步阻塞，原生支持 Streaming。
2.  **Type Strict**: 内部使用 `dataclass` 优化性能，对外接口强制使用 `Pydantic` 保证类型安全。
3.  **Observability**: 内置详细的 Metrics、Tracing 和 Session Summary，让 Agent 的行为可追溯、可量化。

## 2. 技术栈选型

*   **Language**: Python 3.12+
*   **Runtime**: Asyncio (Standard Library)
*   **Data Validation**: Pydantic V2
*   **Configuration**: Pydantic Settings + YAML
*   **HTTP Client**: httpx (Async)
*   **Database Abstraction**: 适配器模式 (初期支持 MongoDB, 后续支持 Postgres/SQLite)
*   **Vector Store**: 适配器模式 (初期支持 Chroma/Qdrant)

## 3. 项目目录结构 (Project Layout)

```text
agio/
├── __init__.py
├── config.py           # 全局配置加载 (Pydantic Settings)
├── exceptions.py       # 自定义异常体系
├── utils/              # 通用工具 (Logger, Async Helpers)
├── domain/             # [核心] 领域模型 (Run, Step, Message, Metrics) - 纯数据结构
│   ├── __init__.py
│   ├── messages.py     # UserMessage, SystemMessage, AssistantMessage
│   ├── run.py          # AgentRun, AgentRunStep
│   └── metrics.py      # AgentMetrics, ToolMetrics
├── agent/              # Agent 核心逻辑
│   ├── __init__.py
│   ├── base.py         # Agent 基类 & Runtime Loop
│   └── manager.py      # Session Manager
├── models/             # 模型抽象层
│   ├── __init__.py
│   ├── base.py         # Model 抽象基类
│   ├── deepseek.py     # Deepseek 实现
│   └── openai.py       # OpenAI 实现
├── tools/              # 工具层
│   ├── __init__.py
│   ├── base.py         # Tool 基类
│   ├── local.py        # 本地函数装饰器
│   └── mcp/            # MCP (Model Context Protocol) 支持
├── memory/             # 记忆系统
│   ├── __init__.py
│   ├── base.py         # Memory 接口
│   └── simple.py       # 基础实现
├── knowledge/          # 知识库 (RAG)
│   ├── __init__.py
│   └── vector/         # 向量存储适配
└── storage/            # 持久化存储
    ├── __init__.py
    └── mongo.py
```

## 4. 开发路线图 (Roadmap)

### Phase 1: 核心骨架 (Core Skeleton)
*   [ ] 定义所有 Pydantic 领域模型 (`domain/`)，确保 `main.py` 中的类型都有定义。
*   [ ] 定义核心抽象基类 (Interfaces): `Model`, `Tool`, `Agent`。
*   [ ] 实现基础配置管理 (`config.yaml` loading)。

### Phase 2: 模型与工具 (Models & Tools)
*   [ ] 实现 `Deepseek` 模型适配器 (支持 Async Stream)。
*   [ ] 实现 `Tool` 基类及函数调用解析逻辑。
*   [ ] 接入 MCP (Model Context Protocol) 基础客户端。

### Phase 3: Agent Runtime (The Loop)
*   [ ] 实现 `Agent.arun()` 核心循环。
*   [ ] 实现 `Pre-hooks` 和 `Post-hooks` 机制。
*   [ ] 实现 Step 记录与 Metrics 统计。

### Phase 4: 记忆与存储 (Memory & Storage)
*   [ ] 实现 `Storage` 接口及 MongoDB 适配。
*   [ ] 实现 `Memory` 接口 (Short-term history)。
*   [ ] 实现 `Knowledge` 向量检索流程。

### Phase 5: 可观测性与完善 (Observability)
*   [ ] 完善 `metrics()` 和 `summary()` 生成逻辑。
*   [ ] 单元测试覆盖。

