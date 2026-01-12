# API Control Panel

Agio 的控制平面 API，基于 FastAPI + SSE，提供统一的 RESTful API 和流式事件传输。

## 架构设计

```
FastAPI Application
    │
    ├─► /agio/runnables      # 统一 Runnable 执行接口
    ├─► /agio/agents         # Agent 管理
    ├─► /agio/sessions       # 会话管理
    ├─► /agio/traces         # 追踪查询
    ├─► /agio/config         # 配置管理
    └─► /agio/health         # 健康检查
```

## 核心特性

- ✅ **统一执行接口**：通过 `/runnables` 执行任何 Runnable（Agent）
- ✅ **流式事件传输**：SSE 方式返回 `StepEvent`，实时展示执行过程
- ✅ **配置驱动**：热重载 `configs/`，拓扑排序构建组件
- ✅ **会话管理**：支持会话查询、Fork、Resume
- ✅ **可观测性**：Trace 查询和瀑布图可视化

## 路由概览

### Runnables（统一执行接口）

#### POST `/agio/runnables/{runnable_id}/run`

执行任何 Runnable（Agent）。

**请求体**：
```json
{
  "query": "Research AI trends",
  "message": "Research AI trends",
  "session_id": "session_123",
  "user_id": "user_456",
  "stream": true
}
```

**字段说明**：
- `query` 或 `message`: 输入消息（二选一，`message` 用于向后兼容）
- `session_id`: 会话 ID（可选，不提供会自动生成）
- `user_id`: 用户 ID（可选）
- `stream`: 是否使用流式响应（默认 true）

**流式响应（SSE）**：
```
event: STEP_CREATED
data: {"type": "STEP_CREATED", "step": {...}}

event: STEP_CREATED
data: {"type": "STEP_CREATED", "step": {...}}

event: RUN_COMPLETED
data: {"type": "RUN_COMPLETED", "run_id": "..."}
```

**非流式响应**（`stream=false`）：
```json
{
  "run_id": "run_123",
  "session_id": "session_123",
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

列出所有 Runnable（Agent）。

**响应**：
```json
{
  "agents": [
    {
      "id": "research_agent",
      "type": "Agent",
      "description": null
    }
  ]
}
```

#### GET `/agio/runnables/{runnable_id}`

获取 Runnable 详细信息。

**响应（Agent）**：
```json
{
  "id": "research_agent",
  "type": "Agent"
}
```

**响应（Agent）**：
```json
{
  "id": "research_agent",
  "type": "Agent",
  "stages": [
    {
      "id": "research",
      "runnable": "researcher",
      "input_template": "Research: {input}",
      "condition": null
    }
  ],
  "loop_condition": null,
  "max_iterations": null,
  "merge_template": null
}
```

### Agents（Agent 管理）

#### GET `/agio/agents`

列出所有 Agent 配置（分页）。

**查询参数**：
- `limit`: 每页数量（默认 20）
- `offset`: 偏移量（默认 0）

**响应**：
```json
{
  "total": 10,
  "items": [
    {
      "name": "research_agent",
      "model": "deepseek",
      "tools": [
        {
          "type": "function",
          "name": "web_search",
          "agent": null,
          "description": "Search the web for information"
        }
      ],
      "system_prompt": "...",
      "tags": []
    }
  ],
  "limit": 20,
  "offset": 0
}
```

#### GET `/agio/agents/{name}`

获取 Agent 详细信息。

**响应**：
```json
{
  "name": "research_agent",
  "model": "deepseek",
  "tools": [
    {
      "type": "function",
      "name": "web_search",
      "agent": null,
      "description": null
    }
  ],
  "system_prompt": "You are a research assistant.",
  "tags": []
}
```

#### GET `/agio/agents/{name}/status`

获取 Agent 状态（是否已构建、依赖是否满足等）。


### Sessions（会话管理）

#### GET `/agio/sessions`

列出所有会话（Runs）（分页）。

**查询参数**：
- `user_id`: 过滤用户 ID（可选）
- `limit`: 每页数量（默认 20）
- `offset`: 偏移量（默认 0）

**响应**：
```json
{
  "total": 100,
  "items": [
    {
      "id": "run_123",
      "agent_id": "research_agent",
      "user_id": "user_456",
      "session_id": "session_123",
      "status": "completed",
      "input_query": "Research AI trends",
      "response_content": "Research results...",
      "created_at": "2024-01-01T12:00:00Z"
    }
  ],
  "limit": 20,
  "offset": 0
}
```

#### GET `/agio/sessions/summary`

获取会话摘要列表（分页）。

**查询参数**：
- `limit`: 每页数量（默认 20）
- `offset`: 偏移量（默认 0）
- `user_id`: 过滤用户 ID（可选）

**响应**：
```json
{
  "total": 100,
  "items": [
    {
      "session_id": "session_123",
      "agent_id": "research_agent",
      "user_id": "user_456",
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
      "user_id": "user_456",
      "session_id": "session_123",
      "status": "completed",
      "input_query": "Research AI trends",
      "response_content": "Research results...",
      "created_at": "2024-01-01T12:00:00Z"
    }
  ],
  "step_count": 25
}
```

#### DELETE `/agio/sessions/{session_id}`

删除会话及其所有数据（Runs 和 Steps）。

**响应**：204 No Content

#### GET `/agio/sessions/{session_id}/runs`

获取会话的所有 Runs（分页）。

**查询参数**：
- `limit`: 每页数量（默认 20）
- `offset`: 偏移量（默认 0）

**响应**：
```json
{
  "total": 5,
  "items": [
    {
      "id": "run_123",
      "agent_id": "research_agent",
      "user_id": "user_456",
      "session_id": "session_123",
      "status": "completed",
      "input_query": "Research AI trends",
      "response_content": "Research results...",
      "created_at": "2024-01-01T12:00:00Z"
    }
  ],
  "limit": 20,
  "offset": 0
}
```

#### GET `/agio/sessions/{session_id}/steps`

获取会话的所有 Steps。

**查询参数**：
- `limit`: 数量限制（默认 100）
- `offset`: 偏移量（默认 0）

**响应**：
```json
{
  "total": 25,
  "items": [
    {
      "id": "step_123",
      "session_id": "session_123",
      "sequence": 1,
      "role": "user",
      "content": "Research AI trends",
      "reasoning_content": null,
      "tool_calls": null,
      "name": null,
      "tool_call_id": null,
      "run_id": "run_123",
      "parent_run_id": null,
      "node_id": null,
      "branch_key": null,
      "runnable_id": "research_agent",
      "runnable_type": "agent",
      "depth": 0,
      "created_at": "2024-01-01T12:00:00Z"
    },
    {
      "id": "step_124",
      "session_id": "session_123",
      "sequence": 2,
      "role": "assistant",
      "content": "I'll research AI trends...",
      "reasoning_content": null,
      "tool_calls": [...],
      "run_id": "run_123",
      "created_at": "2024-01-01T12:00:01Z"
    }
  ],
  "limit": 100,
  "offset": 0
}
```

#### POST `/agio/sessions/{session_id}/fork`

Fork 会话（在指定 Step 处创建新会话，复制历史 Steps）。

**请求体**：
```json
{
  "sequence": 10,
  "content": null,
  "tool_calls": null
}
```

**字段说明**：
- `sequence`: 要 fork 的 Step 的 sequence 号（必需）
- `content`: 可选，用于修改 assistant step 的 content
- `tool_calls`: 可选，用于修改 assistant step 的 tool_calls

**响应**：
```json
{
  "new_session_id": "session_456",
  "copied_steps": 10,
  "last_sequence": 10,
  "pending_user_message": null
}
```

**说明**：
- 对于 assistant step：复制所有 steps 到指定 sequence（包含），可选择性修改 content 或 tool_calls
- 对于 user step：复制指定 sequence 之前的所有 steps，返回 user message 内容在 `pending_user_message` 字段

#### POST `/agio/sessions/{session_id}/resume`

Resume 会话（继续执行，支持 Agent）。

**请求体**：
```json
{
  "runnable_id": "research_agent"
}
```

**字段说明**：
- `runnable_id`: 可选，如果不提供会自动从 Steps 中推断

**响应**：SSE 事件流

**说明**：
- 自动从 Steps 中推断 `runnable_id`（如果未提供）
- Agent：从 pending tool_calls 继续执行

### Traces（追踪查询）

#### GET `/agio/traces`

查询 Traces。

**查询参数**：
- `agent_id`: Agent ID（可选）
- `session_id`: Session ID（可选）
- `status`: 状态（running, ok, error）（可选）
- `start_time`: 开始时间（可选）
- `end_time`: 结束时间（可选）
- `min_duration_ms`: 最小持续时间（可选）
- `max_duration_ms`: 最大持续时间（可选）
- `limit`: 数量限制（默认 50，最大 500）
- `offset`: 偏移量（默认 0）

**响应**：
```json
[
  {
    "trace_id": "trace_123",
    "agent_id": "research_agent",
    "session_id": "session_123",
    "start_time": "2024-01-01T12:00:00Z",
    "duration_ms": 1500.5,
    "status": "ok",
    "total_tokens": 1500,
    "total_llm_calls": 3,
    "total_tool_calls": 2,
    "max_depth": 2,
    "input_preview": "Research AI trends...",
    "output_preview": "Research results..."
  }
]
```

#### GET `/agio/traces/{trace_id}`

获取 Trace 详细信息。

#### GET `/agio/traces/{trace_id}/waterfall`

获取瀑布图数据。

**响应**：
```json
{
  "trace_id": "trace_123",
  "total_duration_ms": 1500.5,
  "spans": [
    {
      "span_id": "span_123",
      "parent_span_id": null,
      "kind": "AGENT",
      "name": "research_agent",
      "depth": 0,
      "start_offset_ms": 0.0,
      "duration_ms": 1500.5,
      "status": "ok",
      "error_message": null,
      "label": "research_agent",
      "sublabel": null,
      "tokens": null,
      "metrics": {},
      "llm_details": null
    },
    {
      "span_id": "span_124",
      "parent_span_id": "span_123",
      "kind": "LLM_CALL",
      "name": "deepseek",
      "depth": 1,
      "start_offset_ms": 100.0,
      "duration_ms": 800.2,
      "status": "ok",
      "error_message": null,
      "label": "deepseek",
      "sublabel": "1500 tokens",
      "tokens": 1500,
      "metrics": {"tokens": {"total": 1500}},
      "llm_details": {...}
    }
  ],
  "metrics": {
    "total_tokens": 1500,
    "total_llm_calls": 3,
    "total_tool_calls": 2,
    "max_depth": 2
  }
}
```

#### GET `/agio/traces/stream`

实时订阅 Traces（SSE）。

**响应**：SSE 事件流

#### GET `/agio/traces/spans/llm-calls`

查询所有 Traces 中的 LLM 调用。

**查询参数**：
- `agent_id`: 过滤 Agent ID（可选）
- `session_id`: 过滤 Session ID（可选）
- `run_id`: 过滤 Run ID（可选）
- `model_id`: 过滤模型 ID（可选）
- `provider`: 过滤 Provider（可选）
- `start_time`: 开始时间（可选）
- `end_time`: 结束时间（可选）
- `limit`: 数量限制（默认 50，最大 500）
- `offset`: 偏移量（默认 0）

**响应**：
```json
[
  {
    "span_id": "span_124",
    "trace_id": "trace_123",
    "agent_id": "research_agent",
    "session_id": "session_123",
    "run_id": "run_123",
    "start_time": "2024-01-01T12:00:00Z",
    "duration_ms": 800.2,
    "model_name": "deepseek-chat",
    "provider": "deepseek",
    "input_tokens": 1000,
    "output_tokens": 500,
    "total_tokens": 1500,
    "llm_details": {...}
  }
]
```

### Config（配置管理）

#### GET `/agio/config`

列出所有配置（按类型分组）。

**响应**：
```json
{
  "agent": [...],
  "tool": [...],
  "model": [...],
  "session_store": [...],
  "trace_store": [...]
}
```

#### GET `/agio/config/{config_type}`

列出指定类型的配置。

**路径参数**：
- `config_type`: 配置类型（agent, tool, model, session_store, trace_store, citation_store）

**响应**：
```json
[
  {
    "type": "agent",
    "name": "research_agent",
    "model": "deepseek",
    ...
  }
]
```

#### GET `/agio/config/{config_type}/{name}`

获取特定配置。

**路径参数**：
- `config_type`: 配置类型
- `name`: 配置名称

**响应**：
```json
{
  "type": "agent",
  "name": "research_agent",
  "model": "deepseek",
  "tools": [...],
  ...
}
```

#### PUT `/agio/config/{config_type}/{name}`

创建或更新配置（触发热重载）。

**请求体**：
```json
{
  "config": {
    "type": "agent",
    "name": "research_agent",
    "model": "deepseek",
    ...
  }
}
```

**响应**：
```json
{
  "message": "Config 'agent/research_agent' saved"
}
```

#### DELETE `/agio/config/{config_type}/{name}`

删除配置。

**响应**：
```json
{
  "message": "Config 'agent/research_agent' deleted"
}
```

#### GET `/agio/config/components`

列出所有已构建的组件实例。

**响应**：
```json
[
  {
    "name": "research_agent",
    "type": "agent",
    "dependencies": ["deepseek", "web_search"],
    "created_at": "2024-01-01T12:00:00Z"
  }
]
```

#### POST `/agio/config/components/{name}/rebuild`

重建组件及其依赖项。

**响应**：
```json
{
  "message": "Component 'research_agent' rebuilt"
}
```

#### POST `/agio/config/reload`

重新加载所有配置。

**响应**：
```json
{
  "message": "Configs reloaded",
  "details": {
    "loaded": 10,
    "failed": 0
  }
}
```

### Health（健康检查）

#### GET `/agio/health`

健康检查。

**响应**：
```json
{
  "status": "healthy",
  "version": "0.1.0",
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
- `STEP_DELTA`: Step 增量更新
- `STEP_COMPLETED`: Step 完成
- `RUN_COMPLETED`: Run 完成
- `RUN_FAILED`: Run 失败
- `ERROR`: 错误事件
- `TOOL_AUTH_REQUIRED`: 工具授权请求
- `TOOL_AUTH_DENIED`: 工具授权拒绝

### 事件格式

```
event: STEP_CREATED
data: {"type": "STEP_CREATED", "step": {...}, "trace_id": "...", "span_id": "..."}

event: RUN_COMPLETED
data: {"type": "RUN_COMPLETED", "run_id": "...", "metrics": {...}}
```

### 客户端示例

```javascript
// 使用 fetch 和 EventSource API
const response = await fetch('/agio/runnables/research_agent/run', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    query: 'Research AI trends',
    session_id: 'session_123',
    stream: true,
  }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  const lines = chunk.split('\n\n');
  
  for (const line of lines) {
    if (line.startsWith('event: ')) {
      const eventType = line.substring(7);
    } else if (line.startsWith('data: ')) {
      const data = JSON.parse(line.substring(6));
      if (data.type === 'STEP_CREATED') {
        console.log('Step created:', data.step);
      } else if (data.type === 'RUN_COMPLETED') {
        console.log('Run completed:', data.metrics);
      }
    }
  }
}
```

## 依赖注入

API 层使用 FastAPI 的依赖注入系统：

```python
from agio.api.deps import get_config_sys, get_session_store, get_trace_store

@router.get("/agents")
async def list_agents(
    config_sys: ConfigSystem = Depends(get_config_sys),
):
    ...
```

**依赖项**：
- `get_config_sys`: 获取 ConfigSystem 实例
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
- `agio/api/routes/sessions.py`: 会话管理
- `agio/api/routes/traces.py`: Trace 查询
- `agio/api/routes/config.py`: 配置管理
- `agio/api/deps.py`: 依赖注入

