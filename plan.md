# Agio Agent Framework Enhancement Plan

## 概述

本计划旨在为 Agio Agent 框架添加四个核心功能：

1. **配置驱动的组件实例化** - 通过 YAML 配置自动加载和注册组件
2. **执行控制与快照** - 支持暂停、恢复、从任意点创建新 Run 或修改后重跑
3. **FastAPI REST API** - 提供完整的 CRUD 接口和 Agent 交互能力
4. **React 前端观测平台** - 图形化配置、调试、监控和数据分析

## 可行性分析

### ✅ 优势与现有基础

经过对当前代码库的深入分析，以下现有架构为实现提供了良好基础：

#### 1. 事件驱动架构 (Event-Driven)
- **现状**：完整的 `AgentEvent` 系统，涵盖 15+ 事件类型
- **优势**：天然支持实时流式输出和历史回放
- **文件**：[`agio/protocol/events.py`](file:///Users/hongv/workspace/agio/agio/protocol/events.py)

#### 2. 仓储模式 (Repository Pattern)
- **现状**：`AgentRunRepository` 抽象 + `InMemoryRepository` 实现
- **优势**：已支持 Run 和 Event 的持久化、查询、分页
- **文件**：[`agio/db/repository.py`](file:///Users/hongv/workspace/agio/agio/db/repository.py)

#### 3. 清晰的领域模型
- **现状**：完整的 `AgentRun`, `AgentRunStep`, `RequestSnapshot`, `ResponseSnapshot`
- **优势**：已包含 100% 可重放所需的所有数据（request/response snapshots）
- **文件**：[`agio/domain/run.py`](file:///Users/hongv/workspace/agio/agio/domain/run.py)

#### 4. 三层架构分离
```
Agent (配置容器)
  ↓
AgentRunner (编排层)
  ↓
AgentExecutor (执行引擎)
```
- **优势**：职责清晰，易于扩展控制逻辑

#### 5. Pydantic 模型
- **现状**：所有核心组件都是 Pydantic BaseModel
- **优势**：自带序列化/反序列化、验证、JSON Schema 生成
- **应用**：可直接用于配置加载和 API 响应

### ⚠️ 挑战与需要填补的空白

#### 1. 配置系统缺失
- **现状**：仅有 `AgioSettings`（环境变量配置）
- **缺失**：组件实例化的配置 schema、配置加载器、组件注册表

#### 2. 执行状态管理有限
- **现状**：`RunStateTracker` 仅追踪指标，不支持中断/恢复
- **缺失**：
  - Checkpoint 序列化/反序列化
  - 从任意 Step 恢复执行的逻辑
  - 执行控制接口（pause/resume/cancel）

#### 3. API 层完全缺失
- **缺失**：FastAPI 应用、路由、中间件、错误处理

#### 4. 前端不存在
- **缺失**：完整的 React 项目

## 总体可行性：✅ **高度可行**

所有功能都是可行的，现有架构提供了坚实基础，主要工作是**填补空白**而非**重构核心**。

---

## 需要的架构调整

### 1. 配置系统架构

#### 新增组件

##### `/agio/registry/`
```
registry/
├── __init__.py
├── base.py              # ComponentRegistry 基类
├── loader.py            # ConfigLoader (YAML → 组件实例)
├── models.py            # 配置 Schema (AgentConfig, ModelConfig, etc.)
└── factory.py           # ComponentFactory (根据配置创建实例)
```

##### 配置文件结构
```
configs/
├── models/
│   ├── gpt4.yaml
│   └── deepseek.yaml
├── agents/
│   ├── support_agent.yaml
│   └── analyst_agent.yaml
├── tools/
│   └── web_search.yaml
├── memory/
│   └── redis_memory.yaml
└── knowledge/
    └── chromadb.yaml
```

#### 配置 Schema 示例

```yaml
# configs/agents/support_agent.yaml
type: agent
name: support_agent
model_ref: gpt4               # 引用已注册的 model
system_prompt: "You are a helpful support agent."
tools:
  - ref: web_search           # 引用已注册的 tool
  - ref: create_ticket
memory_ref: redis_memory
knowledge_ref: chromadb
max_steps: 10
```

```yaml
# configs/models/gpt4.yaml
type: model
provider: openai
name: gpt4
model: gpt-4-turbo-preview
temperature: 0.7
max_tokens: 4096
api_key: ${OPENAI_API_KEY}   # 环境变量引用
```

### 2. 执行控制架构

#### 新增/修改组件

##### `/agio/execution/checkpoint.py` (新增)
```python
class ExecutionCheckpoint(BaseModel):
    \"\"\"执行检查点 - 包含完整恢复所需的状态\"\"\"
    run_id: str
    step_num: int
    messages: list[Message]      # 当前消息上下文
    status: RunStatus
    metrics: AgentRunMetrics
    created_at: datetime
    
    # 可选：用户修改
    modified_query: str | None = None
    modified_messages: list[Message] | None = None

class CheckpointManager:
    \"\"\"检查点管理器\"\"\"
    async def create_checkpoint(self, run_id: str, step_num: int) -> ExecutionCheckpoint
    async def restore_checkpoint(self, checkpoint_id: str) -> ExecutionCheckpoint
    async def list_checkpoints(self, run_id: str) -> list[ExecutionCheckpoint]
```

##### 修改 `AgentRunner`
```python
class AgentRunner:
    # 新增方法
    async def resume_from_checkpoint(
        self, 
        checkpoint: ExecutionCheckpoint,
        modifications: dict | None = None
    ) -> AsyncIterator[AgentEvent]:
        \"\"\"从检查点恢复执行\"\"\"
        pass
    
    async def pause_run(self, run_id: str) -> None:
        \"\"\"暂停执行（设置标志位）\"\"\"
        pass
```

##### 修改 `AgentRunRepository`
```python
class AgentRunRepository(ABC):
    # 新增方法
    @abstractmethod
    async def save_checkpoint(self, checkpoint: ExecutionCheckpoint) -> None:
        pass
    
    @abstractmethod
    async def get_checkpoint(self, checkpoint_id: str) -> ExecutionCheckpoint | None:
        pass
    
    @abstractmethod
    async def get_run_at_step(self, run_id: str, step_num: int) -> tuple[AgentRun, list[Message]]:
        \"\"\"获取特定 Step 时的 Run 状态和消息上下文\"\"\"
        pass
```

### 3. FastAPI 架构

#### 新增项目结构

```
agio/
├── api/                          # 新增
│   ├── __init__.py
│   ├── app.py                    # FastAPI 应用入口
│   ├── dependencies.py           # 依赖注入
│   ├── middleware.py             # CORS, 认证等
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── agents.py             # Agent CRUD
│   │   ├── models.py             # Model CRUD
│   │   ├── tools.py              # Tool CRUD
│   │   ├── memory.py             # Memory CRUD
│   │   ├── knowledge.py          # Knowledge CRUD
│   │   ├── runs.py               # Run 查询和控制
│   │   ├── chat.py               # Chat 接口 (SSE)
│   │   └── config.py             # 配置管理
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── agent.py              # API Request/Response 模型
│   │   ├── run.py
│   │   └── chat.py
│   └── services/
│       ├── __init__.py
│       ├── agent_service.py      # 业务逻辑层
│       └── run_service.py
```

#### 核心 API 端点设计

```python
# Agent Management
POST   /api/agents                # 创建 Agent
GET    /api/agents                # 列出 Agents
GET    /api/agents/{agent_id}     # 获取 Agent 详情
PUT    /api/agents/{agent_id}     # 更新 Agent
DELETE /api/agents/{agent_id}     # 删除 Agent

# Chat Interface
POST   /api/chat                  # 发起对话 (SSE)
POST   /api/chat/stream           # 流式对话 (SSE)

# Run Management
GET    /api/runs                  # 列出 Runs
GET    /api/runs/{run_id}         # 获取 Run 详情
GET    /api/runs/{run_id}/events  # 获取事件流 (支持分页)
GET    /api/runs/{run_id}/steps   # 获取 Steps
POST   /api/runs/{run_id}/pause   # 暂停执行
POST   /api/runs/{run_id}/resume  # 恢复执行
POST   /api/runs/{run_id}/cancel  # 取消执行

# Checkpoint Management
POST   /api/runs/{run_id}/checkpoints           # 创建检查点
GET    /api/runs/{run_id}/checkpoints           # 列出检查点
POST   /api/checkpoints/{checkpoint_id}/restore # 从检查点恢复
POST   /api/checkpoints/{checkpoint_id}/fork    # 从检查点创建新 Run

# Component CRUD (相似模式)
# Models, Tools, Memory, Knowledge, etc.
```

### 4. React 前端架构

#### 技术栈
- **框架**：React 18+ with TypeScript
- **构建工具**：Vite
- **样式**：TailwindCSS + shadcn/ui
- **状态管理**：Zustand / TanStack Query
- **路由**：React Router v6
- **图表**：Recharts / Apache ECharts
- **SSE 客户端**：EventSource API

#### 项目结构

```
agio-ui/                          # 新建项目
├── src/
│   ├── components/
│   │   ├── layout/               # Header, Sidebar, Layout
│   │   ├── chat/                 # ChatWindow, MessageList, InputBox
│   │   ├── agent/                # AgentCard, AgentConfigForm
│   │   ├── run/                  # RunTimeline, StepDetail, EventViewer
│   │   ├── metrics/              # MetricsDashboard, Charts
│   │   └── ui/                   # shadcn/ui 组件
│   ├── pages/
│   │   ├── Dashboard.tsx         # 总览
│   │   ├── Agents.tsx            # Agent 管理
│   │   ├── Chat.tsx              # 对话界面
│   │   ├── Runs.tsx              # Run 列表
│   │   ├── RunDetail.tsx         # Run 详情 + 可视化
│   │   └── Config.tsx            # 配置编辑器
│   ├── hooks/
│   │   ├── useAgents.ts          # Agent CRUD hooks
│   │   ├── useRuns.ts            # Run 查询 hooks
│   │   ├── useChat.ts            # 对话 SSE hook
│   │   └── useEventStream.ts     # 通用 SSE hook
│   ├── services/
│   │   └── api.ts                # API 客户端
│   ├── types/
│   │   └── index.ts              # TypeScript 类型定义
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

#### 核心功能页面

1. **Dashboard (总览)**
   - 活跃 Agents 数量
   - 今日/本周 Runs 统计
   - Token 使用趋势图
   - 最近 Runs 列表

2. **Agent 管理**
   - Agent 列表（卡片视图）
   - 创建/编辑 Agent（表单 + YAML 预览）
   - 删除确认

3. **Chat 界面**
   - 选择 Agent
   - 聊天窗口（支持 Markdown、代码高亮）
   - 实时 Token 计数
   - Tool 调用可视化

4. **Run 详情**
   - Run 基本信息
   - Timeline 视图（展示每个 Step）
   - Event 流查看器（可过滤、搜索）
   - Metrics 图表（Token 使用、耗时分布）
   - Request/Response Snapshot 查看器
   - Checkpoint 管理（创建、恢复、Fork）

5. **配置编辑器**
   - YAML 编辑器（Monaco Editor）
   - 实时验证
   - 配置模板选择

---

## 分阶段实施计划

> **总体策略**：按模块划分，先后端后前端，每个阶段独立可测试

## 🎯 Phase 1: 配置系统基础 (Week 1-2)

### 目标
建立配置驱动的组件实例化能力。

### 任务清单

#### 1.1 定义配置 Schema
- [ ] 创建 `agio/registry/models.py`
  - `BaseComponentConfig`
  - `ModelConfig`
  - `AgentConfig`
  - `ToolConfig`
  - `MemoryConfig`
  - `KnowledgeConfig`

#### 1.2 实现配置加载器
- [ ] 创建 `agio/registry/loader.py`
  - `ConfigLoader.load_yaml()` - 读取 YAML 文件
  - `ConfigLoader.validate()` - Pydantic 验证
  - `ConfigLoader.resolve_refs()` - 解析引用（`${ENV_VAR}`, `ref: xxx`）

#### 1.3 实现组件工厂
- [ ] 创建 `agio/registry/factory.py`
  - `ComponentFactory.create_model()` - 根据 `ModelConfig` 创建 Model 实例
  - `ComponentFactory.create_agent()` - 根据 `AgentConfig` 创建 Agent 实例
  - 支持所有核心组件

#### 1.4 实现组件注册表
- [ ] 创建 `agio/registry/base.py`
  - `ComponentRegistry` - 全局注册表
  - `.register()` - 注册组件
  - `.get()` - 获取组件
  - `.list()` - 列出组件
  - 支持类型过滤

#### 1.5 集成到现有代码
- [ ] 修改 `agio/config.py` - 添加配置目录路径
- [ ] 创建默认配置目录结构 `configs/`
- [ ] 编写示例配置文件

#### 1.6 测试
- [ ] 单元测试：`tests/registry/test_loader.py`
- [ ] 单元测试：`tests/registry/test_factory.py`
- [ ] 集成测试：从配置创建完整 Agent 并运行

---

## 🎯 Phase 2: 执行控制与 Checkpoint (Week 3-4)

### 目标
实现暂停、恢复、从任意点创建新 Run 或修改后重跑的能力。

### 任务清单

#### 2.1 Checkpoint 模型
- [ ] 创建 `agio/execution/checkpoint.py`
  - `ExecutionCheckpoint` - 检查点数据模型
  - `CheckpointMetadata` - 元数据（创建时间、描述等）

#### 2.2 Checkpoint 管理器
- [ ] 在 `agio/execution/checkpoint.py` 实现
  - `CheckpointManager.create_checkpoint()`
  - `CheckpointManager.save_checkpoint()`
  - `CheckpointManager.load_checkpoint()`
  - `CheckpointManager.list_checkpoints()`

#### 2.3 扩展 Repository
- [ ] 修改 `agio/db/repository.py`
  - 添加 `save_checkpoint()` 抽象方法
  - 添加 `get_checkpoint()` 抽象方法
  - 添加 `list_checkpoints()` 抽象方法
- [ ] 修改 `InMemoryRepository` 实现上述方法
- [ ] （可选）实现 MongoDB/PostgreSQL Repository

#### 2.4 恢复逻辑
- [ ] 修改 `agio/runners/base.py`
  - 添加 `AgentRunner.resume_from_checkpoint()`
    - 加载 checkpoint
    - 重建消息上下文
    - 从指定 step 开始执行
  - 添加 `AgentRunner.create_run_from_checkpoint()`
    - 创建新 Run ID
    - 可选：应用用户修改
    - 开始执行

#### 2.5 暂停/取消
- [ ] 添加执行控制标志
  - 在 `AgentRunner` 添加 `_pause_flag`, `_cancel_flag`
  - 在执行循环中检查标志位
- [ ] 实现控制方法
  - `AgentRunner.pause_run()`
  - `AgentRunner.cancel_run()`
  - `AgentRunner.resume_run()`

#### 2.6 测试
- [ ] 单元测试：`tests/execution/test_checkpoint.py`
- [ ] 集成测试：创建 checkpoint → 修改 → 恢复执行
- [ ] 集成测试：暂停 → 恢复
- [ ] 验证：从 Step 2 恢复后的输出与原始 Run 一致性

---

## 🎯 Phase 3: FastAPI Backend (Week 5-7)

### 目标
提供完整的 RESTful API 和 SSE 接口。

### 任务清单

#### 3.1 FastAPI 应用骨架
- [ ] 创建 `agio/api/app.py`
  - 初始化 FastAPI app
  - CORS 中间件
  - 全局异常处理
- [ ] 创建 `agio/api/dependencies.py`
  - 依赖注入：`get_registry()`, `get_repository()`
- [ ] 创建 `agio/api/middleware.py`
  - 请求日志
  - 认证中间件（可选，Phase 4）

#### 3.2 API Schemas
- [ ] 创建 `agio/api/schemas/`
  - `agent.py` - `AgentCreate`, `AgentResponse`, `AgentUpdate`
  - `run.py` - `RunResponse`, `RunListResponse`
  - `chat.py` - `ChatRequest`, `ChatEvent`
  - `checkpoint.py` - `CheckpointCreate`, `CheckpointResponse`

#### 3.3 Agent Routes
- [ ] 创建 `agio/api/routes/agents.py`
  - `POST /api/agents` - 创建 Agent（从配置或 JSON）
  - `GET /api/agents` - 列出 Agents
  - `GET /api/agents/{agent_id}` - 获取 Agent
  - `PUT /api/agents/{agent_id}` - 更新 Agent
  - `DELETE /api/agents/{agent_id}` - 删除 Agent

#### 3.4 Chat Routes (SSE)
- [ ] 创建 `agio/api/routes/chat.py`
  - `POST /api/chat` - 发起对话
    - 请求：`{ "agent_id": "xxx", "query": "xxx", "user_id": "xxx" }`
    - 响应：SSE 流（`AgentEvent` 序列化为 JSON）
  - 实现 SSE 流式响应
    ```python
    from fastapi.responses import StreamingResponse
    
    async def event_generator():
        async for event in agent.arun_stream(query):
            yield f"data: {event.to_json()}\\n\\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
    ```

#### 3.5 Run Routes
- [ ] 创建 `agio/api/routes/runs.py`
  - `GET /api/runs` - 列出 Runs（分页、过滤）
  - `GET /api/runs/{run_id}` - 获取 Run 详情
  - `GET /api/runs/{run_id}/events` - 获取事件流（分页）
  - `GET /api/runs/{run_id}/steps` - 获取 Steps
  - `POST /api/runs/{run_id}/pause` - 暂停
  - `POST /api/runs/{run_id}/resume` - 恢复
  - `POST /api/runs/{run_id}/cancel` - 取消

#### 3.6 Checkpoint Routes
- [ ] 创建 `agio/api/routes/checkpoints.py`
  - `POST /api/runs/{run_id}/checkpoints` - 创建检查点
  - `GET /api/runs/{run_id}/checkpoints` - 列出检查点
  - `POST /api/checkpoints/{checkpoint_id}/restore` - 恢复执行
  - `POST /api/checkpoints/{checkpoint_id}/fork` - 创建新 Run
    - 支持修改参数：`{ "modified_query": "xxx", "modified_step": 2 }`

#### 3.7 Component CRUD Routes
- [ ] 创建 `agio/api/routes/models.py` - Model CRUD
- [ ] 创建 `agio/api/routes/tools.py` - Tool CRUD
- [ ] 创建 `agio/api/routes/memory.py` - Memory CRUD
- [ ] 创建 `agio/api/routes/knowledge.py` - Knowledge CRUD

#### 3.8 Config Routes
- [ ] 创建 `agio/api/routes/config.py`
  - `GET /api/configs` - 列出配置文件
  - `GET /api/configs/{config_type}/{name}` - 获取配置
  - `PUT /api/configs/{config_type}/{name}` - 更新配置
  - `POST /api/configs/{config_type}` - 创建配置
  - `DELETE /api/configs/{config_type}/{name}` - 删除配置

#### 3.9 WebSocket 支持（可选）
- [ ] 创建 `agio/api/routes/ws.py`
  - WebSocket endpoint for real-time bidirectional communication
  - 支持多路复用（同时监听多个 Run）

#### 3.10 测试
- [ ] 单元测试：每个 route 的测试
- [ ] 集成测试：完整的 chat 流程（SSE）
- [ ] 集成测试：Checkpoint 恢复流程
- [ ] 手动测试：使用 `curl` 或 Postman 测试所有端点

#### 3.11 文档
- [ ] 生成 OpenAPI 文档（FastAPI 自动）
- [ ] 编写 API 使用指南

---

## 🎯 Phase 4: React Frontend (Week 8-12)

### 目标
构建完整的 Web UI，提供图形化配置、调试、监控能力。

### 任务清单

#### 4.1 项目初始化
- [ ] 创建 Vite + React + TypeScript 项目
  ```bash
  npm create vite@latest agio-ui -- --template react-ts
  cd agio-ui
  npm install
  ```
- [ ] 安装依赖
  ```bash
  npm install react-router-dom zustand @tanstack/react-query
  npm install -D tailwindcss postcss autoprefixer
  npm install recharts date-fns lucide-react
  npm install @monaco-editor/react  # YAML 编辑器
  ```
- [ ] 配置 TailwindCSS
- [ ] 安装 shadcn/ui
  ```bash
  npx shadcn-ui@latest init
  ```

#### 4.2 基础设施层
- [ ] 创建 `src/services/api.ts`
  - Axios 实例
  - API 客户端封装（CRUD 方法）
  - 错误处理
- [ ] 创建 `src/types/index.ts`
  - 根据后端 Schema 定义 TypeScript 类型
  - Agent, Run, Event, Checkpoint 等
- [ ] 创建 `src/hooks/useEventStream.ts`
  - SSE 客户端 hook
  - 自动重连、错误处理
- [ ] 创建状态管理
  - `src/stores/agentStore.ts` - Agent 列表
  - `src/stores/runStore.ts` - Run 数据
  - `src/stores/chatStore.ts` - 对话状态

#### 4.3 shadcn/ui 组件安装
- [ ] 安装常用组件
  ```bash
  npx shadcn-ui@latest add button card input select table
  npx shadcn-ui@latest add dialog alert badge separator
  npx shadcn-ui@latest add dropdown-menu tabs toast
  ```

#### 4.4 Layout 组件
- [ ] `src/components/layout/Header.tsx`
  - Logo, 导航, 用户菜单
- [ ] `src/components/layout/Sidebar.tsx`
  - 主导航菜单
- [ ] `src/components/layout/Layout.tsx`
  - Header + Sidebar + Content 布局

#### 4.5 Dashboard 页面
- [ ] `src/pages/Dashboard.tsx`
  - 统计卡片（活跃 Agents、今日 Runs、Token 使用）
  - 趋势图（Recharts）
  - 最近 Runs 表格

#### 4.6 Agent 管理页面
- [ ] `src/pages/Agents.tsx`
  - Agent 列表（卡片视图）
  - 搜索、过滤
  - 创建/编辑/删除按钮
- [ ] `src/components/agent/AgentCard.tsx`
  - 显示 Agent 基本信息
  - 快速操作按钮（聊天、编辑、删除）
- [ ] `src/components/agent/AgentForm.tsx`
  - 创建/编辑 Agent 表单
  - 支持 JSON 和 YAML 两种模式
  - 实时验证

#### 4.7 Chat 页面
- [ ] `src/pages/Chat.tsx`
  - Agent 选择器
  - 聊天窗口
  - 输入框
- [ ] `src/components/chat/MessageList.tsx`
  - 消息列表（用户/助手）
  - Markdown 渲染
  - 代码高亮
- [ ] `src/components/chat/InputBox.tsx`
  - 多行输入
  - 发送按钮
  - 快捷键支持（Ctrl+Enter）
- [ ] `src/components/chat/ToolCallViewer.tsx`
  - 显示 Tool 调用（展开/收起）
  - 参数和结果高亮
- [ ] `src/hooks/useChat.ts`
  - SSE 连接管理
  - 消息状态管理
  - Token 实时统计

#### 4.8 Run 列表页面
- [ ] `src/pages/Runs.tsx`
  - Run 列表表格
  - 过滤（按 Agent、用户、状态、时间）
  - 分页
  - 点击进入详情页

#### 4.9 Run 详情页面
- [ ] `src/pages/RunDetail.tsx`
  - Run 基本信息卡片
  - Tab 切换视图
- [ ] `src/components/run/RunInfoCard.tsx`
  - 显示 Run ID、状态、耗时、Token 等
- [ ] `src/components/run/RunTimeline.tsx`
  - 垂直 Timeline 显示所有 Steps
  - 每个 Step 显示：LLM 调用 → Tool 调用
  - 点击展开详情
- [ ] `src/components/run/EventViewer.tsx`
  - 事件流查看器
  - 支持过滤（按类型）
  - 支持搜索
  - JSON 高亮显示
- [ ] `src/components/run/MetricsChart.tsx`
  - Token 使用趋势（Recharts）
  - 每步耗时分布
  - Tool 调用统计
- [ ] `src/components/run/SnapshotViewer.tsx`
  - Request/Response Snapshot 查看器
  - JSON 格式化显示
  - 复制功能

#### 4.10 Checkpoint 管理
- [ ] `src/components/run/CheckpointPanel.tsx`
  - 显示 Run 的所有 Checkpoints
  - 创建 Checkpoint 按钮
  - 恢复/Fork 按钮
- [ ] `src/components/run/ForkDialog.tsx`
  - Fork 对话框
  - 允许修改 query 或 messages
  - 预览修改
  - 确认创建新 Run

#### 4.11 配置编辑器页面
- [ ] `src/pages/Config.tsx`
  - 配置文件树（左侧）
  - Monaco Editor（右侧）
  - 保存/验证按钮
- [ ] `src/components/config/FileTree.tsx`
  - 树形显示配置文件
  - 支持创建/删除文件
- [ ] `src/components/config/YamlEditor.tsx`
  - Monaco Editor 集成
  - YAML 语法高亮
  - 实时验证

#### 4.12 Metrics Dashboard
- [ ] `src/pages/Metrics.tsx`
  - 多维度数据可视化
  - 时间范围选择器
  - 导出功能
- [ ] 使用 Recharts 实现图表
  - Token 使用趋势（折线图）
  - Agent 使用分布（饼图）
  - Tool 调用频率（柱状图）
  - 响应时间分布（直方图）

#### 4.13 错误处理与 Toast
- [ ] 全局错误边界
- [ ] Toast 通知系统（shadcn/ui toast）
- [ ] 网络错误重试逻辑

#### 4.14 响应式设计
- [ ] 移动端适配
- [ ] 平板适配
- [ ] 侧边栏折叠

#### 4.15 测试
- [ ] 单元测试：关键组件的 Vitest 测试
- [ ] E2E 测试：Playwright 测试关键流程
  - 创建 Agent → 发起对话 → 查看 Run → 创建 Checkpoint → Fork

#### 4.16 部署配置
- [ ] 创建 `Dockerfile`
- [ ] Nginx 配置
- [ ] 环境变量配置

---

## 🎯 Phase 5: 集成与优化 (Week 13-14)

### 目标
完整集成、性能优化、文档完善。

### 任务清单

#### 5.1 端到端集成测试
- [ ] 从前端创建 Agent → 发起对话 → 查看 Run → 创建 Checkpoint → Fork 新 Run
- [ ] 测试所有 CRUD 操作
- [ ] 测试暂停/恢复功能
- [ ] 测试 SSE 长连接稳定性

#### 5.2 性能优化
- [ ] 后端：
  - 添加 Redis 缓存（Agent 配置、Run 数据）
  - 数据库索引优化
  - 分页查询优化
- [ ] 前端：
  - 虚拟滚动（长列表）
  - 图片/资源懒加载
  - Code splitting

#### 5.3 安全性
- [ ] API 认证（JWT）
- [ ] API 限流（rate limiting）
- [ ] 输入验证和清洗
- [ ] CORS 配置

#### 5.4 文档
- [ ] API 文档（OpenAPI/Swagger）
- [ ] 前端开发指南
- [ ] 配置文件编写指南
- [ ] 部署指南

#### 5.5 示例与模板
- [ ] 提供多个 Agent 配置模板
- [ ] 提供典型场景的示例（客服机器人、RAG 助手等）

---

## 📋 关键设计决策

### 1. 为什么不修改现有核心架构？

**原因**：
- 现有架构（Event-Driven + Repository Pattern）已经非常适合扩展
- `AgentRun` 和 `AgentRunStep` 的设计已经包含 100% 可重放所需的数据
- 只需要**添加新层**（Config Registry, Checkpoint Manager, API Layer），而不是重构

### 2. Checkpoint 的序列化方案

**方案**：直接使用 Pydantic 的 `model_dump()` 和 `model_validate()`
- **优点**：无需自定义序列化逻辑，类型安全
- **存储格式**：JSON（存入 MongoDB 或 PostgreSQL 的 JSONB 字段）

### 3. SSE vs WebSocket

**选择**：优先使用 SSE，WebSocket 作为可选
- **原因**：
  - SSE 实现简单，浏览器原生支持
  - Chat 场景主要是单向流（服务器 → 客户端）
  - WebSocket 可以后续添加以支持更复杂交互（如协作编辑）

### 4. 前端状态管理

**选择**：Zustand + TanStack Query
- **Zustand**：轻量、简单、TypeScript 友好
- **TanStack Query**：处理服务器状态（缓存、重试、自动更新）
- **为什么不用 Redux**：过于复杂，boilerplate 太多

### 5. 配置引用解析

**策略**：两级引用
- **环境变量引用**：`${ENV_VAR}` - 在加载时解析
- **组件引用**：`ref: component_name` - 在实例化时解析
- **延迟加载**：按需加载引用的组件，避免循环依赖

---

## 🚨 风险与挑战

### 风险 1: Checkpoint 恢复的一致性
**挑战**：从 Step N 恢复后，后续执行可能因为 LLM 的随机性导致不同结果
**缓解**：
- 文档中明确说明这是预期行为
- 提供选项：固定 `temperature=0` 以获得确定性结果
- 在 Fork 时显示"可能与原始 Run 不同"的警告

### 风险 2: SSE 长连接稳定性
**挑战**：网络中断、代理超时可能导致连接断开
**缓解**：
- 前端实现自动重连逻辑
- 服务端支持 `Last-Event-ID` 恢复
- 添加心跳机制

### 风险 3: 前端状态同步
**挑战**：多个 Tab 打开时状态不一致
**缓解**：
- 使用 `localStorage` 或 `BroadcastChannel` API 同步
- TanStack Query 自动缓存失效

### 风险 4: 大规模数据查询性能
**挑战**：Run 和 Event 数据量增长可能导致查询缓慢
**缓解**：
- 添加数据库索引
- 实现分页和虚拟滚动
- 考虑归档策略（冷数据迁移到对象存储）

---

## 📦 交付物

### Phase 1
- [ ] `agio/registry/` 完整实现
- [ ] 配置文件示例
- [ ] 单元测试和集成测试

### Phase 2
- [ ] `agio/execution/checkpoint.py`
- [ ] `AgentRunner` 恢复逻辑
- [ ] 扩展的 Repository 接口
- [ ] 测试覆盖

### Phase 3
- [ ] `agio/api/` 完整实现
- [ ] OpenAPI 文档
- [ ] Postman Collection
- [ ] API 测试

### Phase 4
- [ ] `agio-ui/` 完整项目
- [ ] 所有核心页面和组件
- [ ] E2E 测试
- [ ] 部署配置

### Phase 5
- [ ] 完整文档
- [ ] 示例和模板
- [ ] 性能报告

---

## 📊 成功指标

1. **配置系统**
   - ✅ 可以通过 YAML 配置创建所有核心组件
   - ✅ 支持环境变量和引用解析
   - ✅ 配置验证通过率 100%

2. **执行控制**
   - ✅ 可以从任意 Step 创建 Checkpoint
   - ✅ 可以从 Checkpoint 恢复执行
   - ✅ 可以修改参数后 Fork 新 Run
   - ✅ 暂停/恢复功能正常

3. **API**
   - ✅ 所有 CRUD 端点正常工作
   - ✅ SSE 流稳定无中断（5 分钟测试）
   - ✅ API 响应时间 P95 < 200ms

4. **前端**
   - ✅ 所有核心页面功能完整
   - ✅ 响应式设计兼容移动端
   - ✅ 关键流程 E2E 测试通过
   - ✅ Lighthouse 性能评分 > 85

---

## 🎯 后续扩展方向

完成上述 5 个 Phase 后，可以考虑以下扩展：

### Phase 6: 高级功能
- [ ] 多用户协作（共享 Agent、注释、评论）
- [ ] Agent 模板市场
- [ ] A/B 测试（对比不同配置的效果）
- [ ] 自动化回归测试（保存测试用例，自动重跑）
- [ ] 成本分析（Token 费用统计、预算预警）

### Phase 7: 企业级功能
- [ ] RBAC 权限管理
- [ ] 审计日志
- [ ] SSO 集成
- [ ] 私有部署支持
- [ ] 多租户隔离

### Phase 8: AI 辅助开发
- [ ] Prompt 自动优化建议
- [ ] 异常检测和告警
- [ ] 性能瓶颈自动分析
- [ ] Agent 行为可解释性分析

---

## 📝 总结

本计划通过 **5 个 Phase、14 周的时间**，将 Agio 从一个纯代码框架升级为一个**配置驱动、可观测、可控制、可视化**的完整 Agent 开发平台。

关键优势：
1. **渐进式实现**：每个 Phase 独立可测试验证
2. **最小化重构**：充分利用现有架构，只添加新层
3. **工业级设计**：参考 Agno AgentOS 的最佳实践
4. **完整闭环**：从配置到执行到观测的完整链路

此方案完全可行，现有代码库提供了坚实基础，主要工作是添加新功能层而非重构核心。
