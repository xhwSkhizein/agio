# API Control Panel

Agio 的控制平面 API，基于 FastAPI + SSE，提供统一的 RESTful API 和流式事件传输。

## 架构设计

```
FastAPI Application
    │
    ├─► /agio/runnables      # 统一 Runnable 执行接口
    ├─► /agio/agents         # Agent 管理
    ├─► /agio/workflows      # Workflow 管理
    ├─► /agio/sessions       # 会话管理
    ├─► /agio/traces         # 追踪查询
    ├─► /agio/config         # 配置管理
    └─► /agio/health         # 健康检查
```

## 核心特性

- ✅ **统一执行接口**：通过 `/runnables` 执行任何 Runnable（Agent/Workflow）
- ✅ **流式事件传输**：SSE 方式返回 `StepEvent`，实时展示执行过程
- ✅ **配置驱动**：热重载 `configs/`，拓扑排序构建组件
- ✅ **会话管理**：支持会话查询、Fork、Resume
- ✅ **可观测性**：Trace 查询和瀑布图可视化

## 路由概览

### Runnables（统一执行接口）

#### POST `/agio/runnables/{runnable_id}/run`

执行任何 Runnable（Agent 或 Workflow）。

**请求体**：
```json
{
  "query": "Research AI trends",
  "session_id": "session_123",
  "user_id": "user_456",
  "stream": true
}
```

**流式响应（SSE）**：
```
event: STEP_CREATED
data: {"type": "STEP_CREATED", "step": {...}}

event: STEP_CREATED
data: {"type": "STEP_CREATED", "step": {...}}

event: RUN_COMPLETED
data: {"type": "RUN_COMPLETED", "run_id": "..."}
```

**非流式响应**：
```json
{
  "run_id": "run_123",
  "response": "Research results...",
  "metrics": {
    "total_tokens": 1500,
    "steps_count": 5,
    "tool_calls_count": 2
  }
}
```

**执行流程**：
1. 创建 `Wire` 和 `ExecutionContext`
2. 初始化 `TraceCollector`
3. 后台任务执行 `RunnableExecutor.execute()`
4. 消费 `Wire.read()` 并通过 `TraceCollector` 包装
5. SSE 流式返回事件

#### GET `/agio/runnables`

列出所有 Runnable（Agent 和 Workflow）。

**响应**：
```json
{
  "items": [
    {
      "id": "research_agent",
      "type": "agent",
      "description": "Research assistant"
    },
    {
      "id": "research_pipeline",
      "type": "workflow",
      "workflow_type": "pipeline"
    }
  ]
}
```

#### GET `/agio/runnables/{runnable_id}`

获取 Runnable 详细信息。

**响应**：
```json
{
  "id": "research_agent",
  "type": "agent",
  "model": "deepseek",
  "tools": ["web_search", "web_fetch"],
  "system_prompt": "You are a research assistant."
}
```

### Agents（Agent 管理）

#### GET `/agio/agents`

列出所有 Agent 配置。

**响应**：
```json
{
  "items": [
    {
      "name": "research_agent",
      "model": "deepseek",
      "tools": ["web_search"],
      "system_prompt": "..."
    }
  ]
}
```

#### GET `/agio/agents/{name}`

获取 Agent 详细信息。

#### GET `/agio/agents/{name}/status`

获取 Agent 状态（是否已构建、依赖是否满足等）。

### Workflows（Workflow 管理）

#### GET `/agio/workflows`

列出所有 Workflow 配置。

#### GET `/agio/workflows/{workflow_id}`

获取 Workflow 详细信息。

#### GET `/agio/workflows/{workflow_id}/structure`

获取 Workflow 结构（节点列表、依赖关系）。

**响应**：
```json
{
  "workflow_id": "research_pipeline",
  "workflow_type": "pipeline",
  "stages": [
    {
      "id": "research",
      "runnable": "researcher",
      "input_template": "Research: {input}",
      "condition": null
    },
    {
      "id": "analyze",
      "runnable": "analyzer",
      "input_template": "Analyze: {research.output}",
      "condition": "{research.output} contains 'data'"
    }
  ]
}
```

#### GET `/agio/workflows/{workflow_id}/dependencies`

获取 Workflow 依赖关系。

**响应**：
```json
{
  "research": [],
  "analyze": ["research"]
}
```

### Sessions（会话管理）

#### GET `/agio/sessions/summary`

获取会话摘要列表（分页）。

**查询参数**：
- `limit`: 每页数量（默认 20）
- `offset`: 偏移量（默认 0）
- `user_id`: 过滤用户 ID
- `agent_id`: 过滤 Agent ID
- `workflow_id`: 过滤 Workflow ID

**响应**：
```json
{
  "total": 100,
  "items": [
    {
      "session_id": "session_123",
      "agent_id": "research_agent",
      "run_count": 5,
      "step_count": 25,
      "last_message": "Research AI trends",
      "last_activity": "2024-01-01T12:00:00Z",
      "status": "completed"
    }
  ],
  "limit": 20,
  "offset": 0
}
```

#### GET `/agio/sessions/{session_id}`

获取会话详细信息。

**响应**：
```json
{
  "session_id": "session_123",
  "runs": [
    {
      "id": "run_123",
      "agent_id": "research_agent",
      "status": "completed",
      "input_query": "Research AI trends",
      "response_content": "Research results...",
      "created_at": "2024-01-01T12:00:00Z"
    }
  ],
  "step_count": 25
}
```

#### GET `/agio/sessions/{session_id}/steps`

获取会话的所有 Steps。

**查询参数**：
- `limit`: 数量限制
- `offset`: 偏移量
- `run_id`: 过滤 Run ID
- `workflow_id`: 过滤 Workflow ID
- `node_id`: 过滤节点 ID

**响应**：
```json
{
  "items": [
    {
      "id": "step_123",
      "session_id": "session_123",
      "sequence": 1,
      "role": "user",
      "content": "Research AI trends",
      "run_id": "run_123",
      "created_at": "2024-01-01T12:00:00Z"
    },
    {
      "id": "step_124",
      "session_id": "session_123",
      "sequence": 2,
      "role": "assistant",
      "content": "I'll research AI trends...",
      "tool_calls": [...],
      "run_id": "run_123",
      "created_at": "2024-01-01T12:00:01Z"
    }
  ]
}
```

#### POST `/agio/sessions/{session_id}/fork`

Fork 会话（创建新会话，复制历史 Steps）。

**请求体**：
```json
{
  "new_session_id": "session_456"
}
```

**响应**：
```json
{
  "new_session_id": "session_456",
  "copied_steps": 25
}
```

#### POST `/agio/sessions/{session_id}/resume`

Resume 会话（从指定 Step 继续执行）。

**请求体**：
```json
{
  "from_step_id": "step_123",
  "runnable_id": "research_agent",
  "input": "Continue from here"
}
```

### Traces（追踪查询）

#### GET `/agio/traces`

查询 Traces。

**查询参数**：
- `workflow_id`: Workflow ID
- `agent_id`: Agent ID
- `session_id`: Session ID
- `status`: 状态（running, ok, error）
- `start_time`: 开始时间
- `end_time`: 结束时间
- `min_duration_ms`: 最小持续时间
- `limit`: 数量限制

**响应**：
```json
{
  "items": [
    {
      "trace_id": "trace_123",
      "agent_id": "research_agent",
      "start_time": "2024-01-01T12:00:00Z",
      "duration_ms": 1500.5,
      "status": "ok",
      "total_tokens": 1500,
      "total_llm_calls": 3,
      "total_tool_calls": 2
    }
  ]
}
```

#### GET `/agio/traces/{trace_id}`

获取 Trace 详细信息。

#### GET `/agio/traces/{trace_id}/waterfall`

获取瀑布图数据。

**响应**：
```json
{
  "spans": [
    {
      "span_id": "span_123",
      "name": "research_agent",
      "kind": "AGENT",
      "start_time": "2024-01-01T12:00:00Z",
      "duration_ms": 1500.5,
      "parent_span_id": null,
      "depth": 0,
      "spans": [
        {
          "span_id": "span_124",
          "name": "deepseek",
          "kind": "LLM_CALL",
          "duration_ms": 800.2,
          "parent_span_id": "span_123",
          "depth": 1
        }
      ]
    }
  ]
}
```

#### GET `/agio/traces/stream`

实时订阅 Traces（SSE）。

### Config（配置管理）

#### GET `/agio/config`

列出所有配置。

#### GET `/agio/config/{type}/{name}`

获取特定配置。

#### PUT `/agio/config/{type}/{name}`

更新配置（触发热重载）。

#### DELETE `/agio/config/{type}/{name}`

删除配置。

#### POST `/agio/config/reload`

重新加载所有配置。

### Health（健康检查）

#### GET `/agio/health`

健康检查。

**响应**：
```json
{
  "status": "ok",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

#### GET `/agio/health/ready`

就绪检查。

**响应**：
```json
{
  "ready": true,
  "configs": 10,
  "components": 15
}
```

## 事件流（SSE）

### 事件类型

- `STEP_CREATED`: Step 创建
- `STEP_UPDATED`: Step 更新
- `RUN_STARTED`: Run 开始
- `RUN_COMPLETED`: Run 完成
- `RUN_FAILED`: Run 失败
- `NODE_STARTED`: Workflow 节点开始
- `NODE_COMPLETED`: Workflow 节点完成
- `error`: 错误事件

### 事件格式

```
event: STEP_CREATED
data: {"type": "STEP_CREATED", "step": {...}, "trace_id": "...", "span_id": "..."}

event: RUN_COMPLETED
data: {"type": "RUN_COMPLETED", "run_id": "...", "metrics": {...}}
```

### 客户端示例

```javascript
const eventSource = new EventSource('/agio/runnables/research_agent/run?stream=true', {
  method: 'POST',
  body: JSON.stringify({
    query: 'Research AI trends',
    session_id: 'session_123',
  }),
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'STEP_CREATED') {
    console.log('Step created:', data.step);
  } else if (data.type === 'RUN_COMPLETED') {
    console.log('Run completed:', data.metrics);
    eventSource.close();
  }
};
```

## 依赖注入

API 层使用 FastAPI 的依赖注入系统：

```python
from agio.api.deps import get_config_system, get_session_store, get_trace_store

@router.get("/agents")
async def list_agents(
    config_system: ConfigSystem = Depends(get_config_system),
):
    ...
```

**依赖项**：
- `get_config_system`: 获取 ConfigSystem 实例
- `get_session_store`: 获取 SessionStore 实例
- `get_trace_store`: 获取 TraceStore 实例

## 错误处理

### HTTP 状态码

- `200 OK`: 成功
- `400 Bad Request`: 请求参数错误
- `404 Not Found`: 资源不存在
- `500 Internal Server Error`: 服务器错误

### 错误响应格式

```json
{
  "detail": "Runnable not found: research_agent"
}
```

## 启动和配置

### 启动服务器

```bash
# 方式 1: 使用 main.py
python main.py

# 方式 2: 使用 uvicorn
uvicorn agio.api.app:app --host 0.0.0.0 --port 8900 --reload
```

### 环境变量

```bash
# 配置目录
AGIO_CONFIG_DIR=./configs

# API 配置
AGIO_API_ENABLED=true
AGIO_API_HOST=0.0.0.0
AGIO_API_PORT=8900

# MongoDB
AGIO_MONGO_URI=mongodb://localhost:27017
AGIO_MONGO_DB_NAME=agio

# OTLP（可选）
AGIO_OTLP_ENABLED=true
AGIO_OTLP_ENDPOINT=http://localhost:4317
AGIO_OTLP_PROTOCOL=grpc
```

### API 文档

- OpenAPI: `http://localhost:8900/agio/docs`
- ReDoc: `http://localhost:8900/agio/redoc`

## 最佳实践

1. **流式执行**：使用 `stream=true` 获取实时事件流
2. **会话管理**：合理使用 `session_id` 组织对话历史
3. **错误处理**：监听 `error` 事件，处理执行错误
4. **性能优化**：使用分页查询，避免一次性加载大量数据
5. **追踪查询**：利用 Trace API 进行性能分析和调试

## 相关代码

- `agio/api/app.py`: FastAPI 应用创建
- `agio/api/router.py`: 路由聚合
- `agio/api/routes/runnables.py`: Runnable 执行接口
- `agio/api/routes/agents.py`: Agent 管理
- `agio/api/routes/workflows.py`: Workflow 管理
- `agio/api/routes/sessions.py`: 会话管理
- `agio/api/routes/traces.py`: Trace 查询
- `agio/api/routes/config.py`: 配置管理
- `agio/api/deps.py`: 依赖注入

