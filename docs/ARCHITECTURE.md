# Agio 架构设计

Agio 是一个专注**可组合、多代理编排**的现代 Agent 框架，提供一致的事件流、工具系统、可观测性与配置驱动能力。

## 核心设计理念

### 1. Wire-based 事件流架构

所有执行都通过统一的 `Wire` 通道进行事件流式传输：

```
API Entry Point
    │
    ├─► Wire (事件通道)
    │
    ├─► Agent.run()
    │   └─► 写入 StepEvent 到 Wire
    │
    └─► API Layer 消费 Wire.read()
        └─► SSE 流式响应
```

**优势**：
- 统一的执行接口：Agent 实现 `Runnable` 协议
- 实时事件流：支持 SSE 流式传输，前端可实时展示执行过程
- 嵌套执行支持：所有嵌套执行共享同一个 Wire，事件统一管理

### 2. Runnable 协议统一抽象

`Runnable` 协议是核心抽象，Agent 实现此协议：

```python
from agio.runtime.protocol import RunnableType

class Runnable(Protocol):
    @property
    def id(self) -> str: ...
    
    @property
    def runnable_type(self) -> RunnableType: ...
    
    async def run(
        self,
        input: str,
        *,
        context: ExecutionContext,
    ) -> RunOutput: ...
```

**能力**：
- 统一 API 调用：通过 `/runnables/{id}/run` 执行任何 Runnable
- 相互嵌套：Agent 可以嵌套调用其他 Agent
- 作为工具使用：通过 `RunnableAsTool` 将 Agent 包装为 Tool

### 3. 配置驱动架构

所有组件通过 YAML 配置文件定义，系统自动加载、验证、构建：

```
configs/
├── models/          # LLM 模型配置
├── tools/           # 工具配置
├── agents/          # Agent 配置
└── storages/        # 存储配置
```

**特性**：
- 热重载：配置变更自动级联重建依赖组件
- 依赖解析：自动拓扑排序，循环依赖立即报错
- 类型安全：Pydantic 模型验证

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      API Control Panel                      │
│  (FastAPI + SSE) - 统一 REST API 和流式事件接口                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    ConfigSystem                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Registry   │  │   Container  │  │  Dependency  │       │
│  │  (配置存储)   │  │  (实例管理)    │  │  (依赖解析)   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │   Builder    │  │  HotReload   │                         │
│  │  (构建器)     │  │  (热重载)     │                         │
│  └──────────────┘  └──────────────┘                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│    Agent     │ │    Tools     │ │   Storage    │
│   System     │ │   System     │ │   System     │
└──────────────┘ └──────────────┘ └──────────────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
                       ▼
        ┌──────────────────────────┐
        │   Runnable Protocol      │
        │  (统一执行接口)            │
        └──────────────────────────┘
                       │
        ┌──────────────┼────────────────┐
        ▼              ▼                ▼
┌──────────────┐ ┌────────────────┐ ┌──────────────┐
│  Execution   │ │  Observability │ │   Storage    │
│   Runtime    │ │   (Traces)     │ │  (MongoDB)   │
└──────────────┘ └────────────────┘ └──────────────┘
```

## 核心模块

### 1. 配置系统 (ConfigSystem)

**职责**：
- 从 YAML 文件加载配置
- 解析依赖关系并拓扑排序
- 构建组件实例
- 支持热重载

**关键组件**：
- `ConfigRegistry`: 配置存储和查询
- `ComponentContainer`: 组件实例管理
- `DependencyResolver`: 依赖解析和拓扑排序
- `BuilderRegistry`: 构建器注册表
- `HotReloadManager`: 热重载管理

详见：[配置系统文档](./CONFIG_SYSTEM_V2.md)

### 2. Agent 系统

**职责**：
- LLM 调用循环
- 工具批量执行
- 上下文构建和记忆管理
- 终止摘要生成

**关键组件**：
- `Agent`: Agent 配置容器
- `AgentExecutor`: LLM 执行循环
- `ToolExecutor`: 工具执行器
- `build_context_from_steps`: 上下文构建

详见：[Agent 系统文档](./AGENT_SYSTEM.md)

### 3. Runnable 协议

**职责**：
- 统一 Agent 的执行接口
- 支持相互嵌套
- 支持作为工具使用

**关键组件**：
- `Runnable`: 协议定义
- `RunnableExecutor`: 统一执行引擎
- `RunnableAsTool`: Agent 作为工具
- `ExecutionContext`: 执行上下文

### 5. 可观测性

**职责**：
- 分布式追踪（Trace/Span）
- 事件流收集
- OTLP 导出

**关键组件**：
- `TraceCollector`: 事件流收集器
- `TraceStore`: 追踪数据存储
- `OTLPExporter`: OTLP 导出器

详见：[可观测性文档](./OBSERVABILITY.md)

### 6. Agent Skills System

**职责**：
- 技能发现和元数据管理
- 技能内容加载和资源解析
- 技能激活工具实现
- 渐进式披露机制

**关键组件**：
- `SkillRegistry`: 技能发现和元数据缓存
- `SkillLoader`: 技能内容加载和路径解析
- `SkillTool`: 技能激活工具
- `SkillManager`: 统一管理入口

**渐进式披露**：
1. **启动阶段**：仅加载技能元数据（name + description）
2. **激活阶段**：LLM 调用 Skill 工具后加载完整 SKILL.md
3. **执行阶段**：按需加载 scripts/、references/、assets/

详见：[Agent Skills 集成方案](../refactor_support_agent_skills.md)

### 7. API Control Panel

**职责**：
- RESTful API 接口
- SSE 流式事件传输
- 配置管理
- 会话管理

**关键路由**：
- `/runnables`: 统一 Runnable 执行接口
- `/agents`: Agent 管理
- `/sessions`: 会话管理
- `/traces`: 追踪查询
- `/config`: 配置管理

详见：[API Control Panel 文档](./API_CONTROL_PANEL.md)

## 执行流程

### Agent 执行流程

```
1. API Entry Point
   └─► 创建 Wire + ExecutionContext
   
2. RunnableExecutor.execute()
   └─► 创建 Run 记录
   └─► 调用 Agent.run()
   
3. Agent.run()
   └─► AgentExecutor.execute()
       ├─► 构建上下文（从历史 Steps）
       ├─► LLM 调用循环
       │   ├─► 调用 LLM
       │   ├─► 解析 Tool Calls
       │   └─► 批量执行工具
       └─► 写入 StepEvent 到 Wire
   
4. API Layer
   └─► 消费 Wire.read()
       └─► SSE 流式响应
```

## 数据流

### StepEvent 事件流

所有执行都通过 `StepEvent` 事件流进行通信：

```python
class StepEvent:
    type: StepEventType  # RUN_STARTED, STEP_CREATED, RUN_COMPLETED, etc.
    run_id: str
    step: Step | None
    data: dict | None
    # ... trace_id, span_id for observability
```

**事件类型**：
- `RUN_STARTED`: Run 开始
- `STEP_DELTA`: Step 增量更新
- `STEP_COMPLETED`: Step 完成
- `RUN_COMPLETED`: Run 完成
- `RUN_FAILED`: Run 失败
- `ERROR`: 错误事件
- `TOOL_AUTH_REQUIRED`: 工具授权请求
- `TOOL_AUTH_DENIED`: 工具授权拒绝

### 存储层

- **SessionStore**: 存储 Session、Run、Step
- **TraceStore**: 存储 Trace、Span（用于可观测性）
- **CitationStore**: 存储引用源（用于 web_search/web_fetch）

## 扩展性

### 添加新工具

1. 实现 `BaseTool` 接口
2. 在 `providers/tools/builtin/` 下创建工具模块
3. 在 `configs/tools/` 下创建配置文件

### 添加新模型 Provider

1. 实现 `Model` 接口
2. 在 `providers/llm/` 下创建 Provider 模块
3. 注册到 `ModelProviderRegistry`

### 添加新存储类型

1. 实现 `SessionStore` / `TraceStore` / `CitationStore` 接口
2. 在 `providers/storage/` 下创建存储模块
3. 在 `configs/storages/` 下创建配置文件

## 相关文档

- [配置系统](./CONFIG_SYSTEM_V2.md)
- [Agent 系统](./AGENT_SYSTEM.md)
- [可观测性](./OBSERVABILITY.md)
- [API Control Panel](./API_CONTROL_PANEL.md)
- [工具配置](./TOOL_CONFIGURATION.md)
