# Agio FastAPI Backend 详细设计

> **目标**：打造生产级 RESTful API - 完整的 CRUD、实时流式交互、可观测性支持

## 📋 目录

1. [设计理念](#设计理念)
2. [核心架构](#核心架构)
3. [API 端点设计](#api-端点设计)
4. [SSE 流式传输](#sse-流式传输)
5. [认证与授权](#认证与授权)
6. [错误处理](#错误处理)
7. [中间件](#中间件)
8. [数据模型](#数据模型)
9. [部署配置](#部署配置)
10. [使用指南](#使用指南)

---

## 设计理念

### 核心原则

1. **RESTful 设计** - 遵循 REST 最佳实践
2. **类型安全** - Pydantic 模型提供完整类型验证
3. **实时流式** - SSE 支持实时事件推送
4. **可扩展** - 模块化设计，易于扩展
5. **生产就绪** - 完整的错误处理、日志、监控

### 设计目标

- ✅ **完整 CRUD** - Agent、Model、Tool、Run 等资源
- ✅ **实时交互** - SSE 流式 Chat 接口
- ✅ **执行控制** - Pause、Resume、Cancel、Fork
- ✅ **配置管理** - 动态配置 CRUD
- ✅ **可观测性** - Metrics、Logs、Events
- ✅ **安全性** - 认证、授权、限流

---

## 核心架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    Middleware                         │   │
│  │  - CORS                                               │   │
│  │  - Authentication                                     │   │
│  │  - Rate Limiting                                      │   │
│  │  - Request Logging                                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                     Routes                            │   │
│  │  /api/agents      /api/chat       /api/runs          │   │
│  │  /api/config      /api/checkpoints /api/metrics      │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   Services                            │   │
│  │  - AgentService                                       │   │
│  │  - ChatService                                        │   │
│  │  - RunService                                         │   │
│  │  - ConfigService                                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  Domain Layer                         │   │
│  │  - Agent                                              │   │
│  │  - AgentRunner                                        │   │
│  │  - CheckpointManager                                  │   │
│  │  - ConfigManager                                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 目录结构

```
agio/
├── api/
│   ├── __init__.py
│   ├── app.py                 # FastAPI 应用入口
│   ├── dependencies.py        # 依赖注入
│   ├── middleware.py          # 中间件
│   ├── routes/                # 路由
│   │   ├── __init__.py
│   │   ├── agents.py          # Agent CRUD
│   │   ├── chat.py            # Chat 接口
│   │   ├── runs.py            # Run 管理
│   │   ├── checkpoints.py     # Checkpoint 管理
│   │   ├── config.py          # 配置管理
│   │   ├── metrics.py         # Metrics 查询
│   │   └── health.py          # 健康检查
│   ├── schemas/               # Pydantic 模型
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── chat.py
│   │   ├── run.py
│   │   ├── checkpoint.py
│   │   └── common.py
│   └── services/              # 业务逻辑
│       ├── __init__.py
│       ├── agent_service.py
│       ├── chat_service.py
│       ├── run_service.py
│       └── config_service.py
```

---

## API 端点设计

### 1. Agent 管理

#### 1.1 列出 Agents

```http
GET /api/agents
```

**Query Parameters:**
- `limit` (int, default=20): 返回数量
- `offset` (int, default=0): 偏移量
- `tag` (str, optional): 按标签过滤

**Response:**
```json
{
  "total": 100,
  "items": [
    {
      "id": "agent_1",
      "name": "customer_support",
      "description": "Customer support agent",
      "model": "gpt4",
      "tools": ["search", "ticket"],
      "created_at": "2024-01-01T00:00:00Z",
      "tags": ["production"]
    }
  ]
}
```

#### 1.2 获取 Agent 详情

```http
GET /api/agents/{agent_id}
```

**Response:**
```json
{
  "id": "agent_1",
  "name": "customer_support",
  "description": "Customer support agent",
  "model": "gpt4",
  "tools": ["search", "ticket"],
  "memory": "redis_memory",
  "knowledge": "product_docs",
  "system_prompt": "You are a helpful assistant",
  "config": {
    "max_steps": 10,
    "temperature": 0.7
  },
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "tags": ["production"]
}
```

#### 1.3 创建 Agent

```http
POST /api/agents
```

**Request Body:**
```json
{
  "name": "new_agent",
  "description": "A new agent",
  "model": "gpt4",
  "tools": ["search"],
  "system_prompt": "You are helpful",
  "tags": ["test"]
}
```

**Response:** `201 Created`

#### 1.4 更新 Agent

```http
PUT /api/agents/{agent_id}
```

**Request Body:** (同创建)

**Response:** `200 OK`

#### 1.5 删除 Agent

```http
DELETE /api/agents/{agent_id}
```

**Response:** `204 No Content`

---

### 2. Chat 接口

#### 2.1 发送消息（SSE 流式）

```http
POST /api/chat
Content-Type: application/json
Accept: text/event-stream
```

**Request Body:**
```json
{
  "agent_id": "customer_support",
  "message": "How do I reset my password?",
  "user_id": "user_123",
  "session_id": "session_456",
  "stream": true
}
```

**Response (SSE):**
```
event: run_started
data: {"run_id": "run_789", "timestamp": "2024-01-01T00:00:00Z"}

event: step_started
data: {"step": 1, "type": "llm_call"}

event: content_delta
data: {"content": "To reset"}

event: content_delta
data: {"content": " your password"}

event: tool_call_started
data: {"tool": "search_kb", "args": {"query": "reset password"}}

event: tool_call_completed
data: {"tool": "search_kb", "result": "..."}

event: run_completed
data: {"run_id": "run_789", "response": "To reset your password..."}
```

#### 2.2 发送消息（非流式）

```http
POST /api/chat
Content-Type: application/json
```

**Request Body:**
```json
{
  "agent_id": "customer_support",
  "message": "Hello",
  "user_id": "user_123",
  "stream": false
}
```

**Response:**
```json
{
  "run_id": "run_789",
  "response": "Hello! How can I help you?",
  "metrics": {
    "total_tokens": 150,
    "duration": 2.5
  }
}
```

---

### 3. Run 管理

#### 3.1 列出 Runs

```http
GET /api/runs
```

**Query Parameters:**
- `agent_id` (str, optional): 按 Agent 过滤
- `user_id` (str, optional): 按用户过滤
- `status` (str, optional): 按状态过滤
- `limit` (int, default=20)
- `offset` (int, default=0)

**Response:**
```json
{
  "total": 500,
  "items": [
    {
      "id": "run_789",
      "agent_id": "customer_support",
      "user_id": "user_123",
      "status": "completed",
      "input_query": "Hello",
      "response_content": "Hi!",
      "metrics": {
        "total_tokens": 150,
        "duration": 2.5
      },
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### 3.2 获取 Run 详情

```http
GET /api/runs/{run_id}
```

**Response:**
```json
{
  "id": "run_789",
  "agent_id": "customer_support",
  "user_id": "user_123",
  "session_id": "session_456",
  "status": "completed",
  "input_query": "Hello",
  "response_content": "Hi!",
  "steps": [
    {
      "step_num": 1,
      "type": "llm_call",
      "messages": [...],
      "model_response": {...},
      "metrics": {...}
    }
  ],
  "metrics": {
    "total_tokens": 150,
    "total_steps": 1,
    "duration": 2.5
  },
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### 3.3 获取 Run 事件流

```http
GET /api/runs/{run_id}/events
```

**Query Parameters:**
- `offset` (int, default=0)
- `limit` (int, default=100)

**Response:**
```json
{
  "run_id": "run_789",
  "total": 50,
  "events": [
    {
      "type": "run_started",
      "timestamp": "2024-01-01T00:00:00Z",
      "data": {...}
    },
    {
      "type": "content_delta",
      "timestamp": "2024-01-01T00:00:01Z",
      "data": {"content": "Hello"}
    }
  ]
}
```

#### 3.4 暂停 Run

```http
POST /api/runs/{run_id}/pause
```

**Response:**
```json
{
  "run_id": "run_789",
  "status": "paused",
  "message": "Run paused successfully"
}
```

#### 3.5 恢复 Run

```http
POST /api/runs/{run_id}/resume
```

**Response:**
```json
{
  "run_id": "run_789",
  "status": "running",
  "message": "Run resumed successfully"
}
```

#### 3.6 取消 Run

```http
POST /api/runs/{run_id}/cancel
```

**Response:**
```json
{
  "run_id": "run_789",
  "status": "cancelled",
  "message": "Run cancelled successfully"
}
```

---

### 4. Checkpoint 管理

#### 4.1 列出 Checkpoints

```http
GET /api/runs/{run_id}/checkpoints
```

**Response:**
```json
{
  "run_id": "run_789",
  "total": 5,
  "checkpoints": [
    {
      "id": "ckpt_1",
      "step_num": 2,
      "description": "Before tool call",
      "created_at": "2024-01-01T00:00:00Z",
      "message_count": 4,
      "total_tokens": 100
    }
  ]
}
```

#### 4.2 创建 Checkpoint

```http
POST /api/runs/{run_id}/checkpoints
```

**Request Body:**
```json
{
  "description": "Manual checkpoint",
  "tags": ["important"]
}
```

**Response:** `201 Created`

#### 4.3 获取 Checkpoint 详情

```http
GET /api/checkpoints/{checkpoint_id}
```

**Response:**
```json
{
  "id": "ckpt_1",
  "run_id": "run_789",
  "step_num": 2,
  "status": "running",
  "messages": [...],
  "metrics": {...},
  "agent_config": {...},
  "description": "Before tool call",
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### 4.4 从 Checkpoint 恢复

```http
POST /api/checkpoints/{checkpoint_id}/restore
```

**Request Body:**
```json
{
  "create_new_run": true,
  "modifications": {
    "modified_query": "New query"
  }
}
```

**Response:**
```json
{
  "new_run_id": "run_999",
  "message": "Restored successfully"
}
```

#### 4.5 Fork Checkpoint

```http
POST /api/checkpoints/{checkpoint_id}/fork
```

**Request Body:**
```json
{
  "description": "Testing different approach",
  "modifications": {
    "system_prompt": "New prompt"
  }
}
```

**Response:**
```json
{
  "new_run_id": "run_888",
  "checkpoint_id": "ckpt_2",
  "message": "Forked successfully"
}
```

---

### 5. 配置管理

#### 5.1 列出配置

```http
GET /api/config
```

**Query Parameters:**
- `type` (str, optional): 配置类型 (model, agent, tool)

**Response:**
```json
{
  "total": 20,
  "configs": [
    {
      "name": "gpt4",
      "type": "model",
      "description": "GPT-4 model",
      "enabled": true,
      "tags": ["production"]
    }
  ]
}
```

#### 5.2 获取配置详情

```http
GET /api/config/{component_name}
```

**Response:**
```json
{
  "name": "gpt4",
  "type": "model",
  "provider": "openai",
  "model": "gpt-4-turbo-preview",
  "temperature": 0.7,
  "enabled": true,
  "tags": ["production"]
}
```

#### 5.3 更新配置

```http
PUT /api/config/{component_name}
```

**Request Body:**
```json
{
  "config": {
    "type": "model",
    "name": "gpt4",
    "temperature": 0.8
  },
  "validate_only": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Configuration updated successfully"
}
```

#### 5.4 配置变更历史

```http
GET /api/config/{component_name}/history
```

**Response:**
```json
{
  "component_name": "gpt4",
  "history": [
    {
      "change_type": "updated",
      "timestamp": "2024-01-01T00:00:00Z",
      "old_config": {...},
      "new_config": {...}
    }
  ]
}
```

---

### 6. Metrics 查询

#### 6.1 获取 Agent Metrics

```http
GET /api/metrics/agents/{agent_id}
```

**Query Parameters:**
- `start_time` (datetime)
- `end_time` (datetime)
- `granularity` (str): hour, day, week

**Response:**
```json
{
  "agent_id": "customer_support",
  "period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-02T00:00:00Z"
  },
  "metrics": {
    "total_runs": 1000,
    "success_rate": 0.95,
    "avg_duration": 2.5,
    "total_tokens": 150000,
    "avg_tokens_per_run": 150
  },
  "timeseries": [
    {
      "timestamp": "2024-01-01T00:00:00Z",
      "runs": 100,
      "tokens": 15000
    }
  ]
}
```

#### 6.2 获取系统 Metrics

```http
GET /api/metrics/system
```

**Response:**
```json
{
  "total_agents": 10,
  "total_runs": 10000,
  "active_runs": 5,
  "total_tokens_today": 500000,
  "avg_response_time": 2.3
}
```

---

### 7. 健康检查

#### 7.1 健康检查

```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "components": {
    "database": "healthy",
    "cache": "healthy",
    "llm": "healthy"
  }
}
```

---

## SSE 流式传输

### 1. SSE 实现

```python
# agio/api/routes/chat.py

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import json

router = APIRouter(prefix="/api/chat", tags=["Chat"])

@router.post("")
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    Chat 接口
    
    支持流式和非流式两种模式
    """
    
    if request.stream:
        # 流式响应
        return EventSourceResponse(
            chat_service.stream_chat(
                agent_id=request.agent_id,
                message=request.message,
                user_id=request.user_id,
                session_id=request.session_id
            )
        )
    else:
        # 非流式响应
        result = await chat_service.chat(
            agent_id=request.agent_id,
            message=request.message,
            user_id=request.user_id,
            session_id=request.session_id
        )
        return result
```

### 2. Chat Service

```python
# agio/api/services/chat_service.py

from typing import AsyncIterator
import json
from agio.registry.base import get_registry
from agio.protocol.events import AgentEvent

class ChatService:
    """Chat 服务"""
    
    def __init__(self, registry):
        self.registry = registry
    
    async def stream_chat(
        self,
        agent_id: str,
        message: str,
        user_id: str | None = None,
        session_id: str | None = None
    ) -> AsyncIterator[dict]:
        """
        流式 Chat
        
        Yields:
            SSE 事件
        """
        # 获取 Agent
        agent = self.registry.get(agent_id)
        if not agent:
            yield {
                "event": "error",
                "data": json.dumps({"error": f"Agent {agent_id} not found"})
            }
            return
        
        try:
            # 执行 Agent
            async for event in agent.arun_stream(
                query=message,
                user_id=user_id,
                session_id=session_id
            ):
                # 转换为 SSE 格式
                yield {
                    "event": event.type,
                    "data": json.dumps(event.data)
                }
        
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
    
    async def chat(
        self,
        agent_id: str,
        message: str,
        user_id: str | None = None,
        session_id: str | None = None
    ) -> dict:
        """
        非流式 Chat
        
        Returns:
            完整响应
        """
        agent = self.registry.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        # 收集所有内容
        response_content = ""
        run_id = None
        metrics = {}
        
        async for event in agent.arun_stream(
            query=message,
            user_id=user_id,
            session_id=session_id
        ):
            if event.type == "run_started":
                run_id = event.data.get("run_id")
            
            elif event.type == "content_delta":
                response_content += event.data.get("content", "")
            
            elif event.type == "run_completed":
                metrics = event.data.get("metrics", {})
        
        return {
            "run_id": run_id,
            "response": response_content,
            "metrics": metrics
        }
```

### 3. SSE 客户端示例

```typescript
// 前端 SSE 客户端
const eventSource = new EventSource('/api/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    agent_id: 'customer_support',
    message: 'Hello',
    stream: true
  })
});

eventSource.addEventListener('content_delta', (event) => {
  const data = JSON.parse(event.data);
  console.log('Content:', data.content);
});

eventSource.addEventListener('run_completed', (event) => {
  const data = JSON.parse(event.data);
  console.log('Completed:', data);
  eventSource.close();
});

eventSource.addEventListener('error', (event) => {
  console.error('Error:', event);
  eventSource.close();
});
```

---

## 认证与授权

### 1. JWT 认证

```python
# agio/api/auth.py

from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# 配置
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """创建 JWT Token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """验证 JWT Token"""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
        return user_id
    
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

# 使用
@router.get("/api/agents")
async def list_agents(user_id: str = Depends(verify_token)):
    # user_id 已验证
    ...
```

### 2. API Key 认证

```python
# agio/api/auth.py

from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    """验证 API Key"""
    # 从数据库或配置中验证
    valid_keys = ["key1", "key2"]  # 实际应从数据库读取
    
    if x_api_key not in valid_keys:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )
    
    return x_api_key

# 使用
@router.get("/api/agents")
async def list_agents(api_key: str = Depends(verify_api_key)):
    ...
```

### 3. 基于角色的访问控制 (RBAC)

```python
# agio/api/rbac.py

from enum import Enum
from fastapi import Depends, HTTPException

class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

class Permission(str, Enum):
    READ_AGENT = "read:agent"
    WRITE_AGENT = "write:agent"
    DELETE_AGENT = "delete:agent"
    EXECUTE_AGENT = "execute:agent"

ROLE_PERMISSIONS = {
    Role.ADMIN: [
        Permission.READ_AGENT,
        Permission.WRITE_AGENT,
        Permission.DELETE_AGENT,
        Permission.EXECUTE_AGENT
    ],
    Role.USER: [
        Permission.READ_AGENT,
        Permission.EXECUTE_AGENT
    ],
    Role.VIEWER: [
        Permission.READ_AGENT
    ]
}

def require_permission(permission: Permission):
    """权限检查装饰器"""
    
    def permission_checker(user_id: str = Depends(verify_token)):
        # 获取用户角色（从数据库）
        user_role = get_user_role(user_id)  # 实现此函数
        
        # 检查权限
        if permission not in ROLE_PERMISSIONS.get(user_role, []):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions"
            )
        
        return user_id
    
    return permission_checker

# 使用
@router.delete("/api/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    user_id: str = Depends(require_permission(Permission.DELETE_AGENT))
):
    ...
```

---

## 错误处理

### 1. 自定义异常

```python
# agio/api/exceptions.py

class AgioAPIException(Exception):
    """API 异常基类"""
    
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class AgentNotFoundException(AgioAPIException):
    """Agent 未找到"""
    
    def __init__(self, agent_id: str):
        super().__init__(
            message=f"Agent '{agent_id}' not found",
            status_code=404
        )

class RunNotFoundException(AgioAPIException):
    """Run 未找到"""
    
    def __init__(self, run_id: str):
        super().__init__(
            message=f"Run '{run_id}' not found",
            status_code=404
        )

class InvalidConfigException(AgioAPIException):
    """配置无效"""
    
    def __init__(self, details: str):
        super().__init__(
            message=f"Invalid configuration: {details}",
            status_code=400
        )
```

### 2. 全局异常处理器

```python
# agio/api/app.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .exceptions import AgioAPIException

app = FastAPI()

@app.exception_handler(AgioAPIException)
async def agio_exception_handler(request: Request, exc: AgioAPIException):
    """处理自定义异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": exc.__class__.__name__,
                "message": exc.message,
                "path": str(request.url)
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理未捕获的异常"""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "InternalServerError",
                "message": "An unexpected error occurred",
                "path": str(request.url)
            }
        }
    )
```

### 3. 验证错误处理

```python
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误"""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "type": "ValidationError",
                "message": "Request validation failed",
                "details": exc.errors()
            }
        }
    )
```

---

## 中间件

### 1. CORS 中间件

```python
# agio/api/middleware.py

from fastapi.middleware.cors import CORSMiddleware

def add_cors_middleware(app: FastAPI):
    """添加 CORS 中间件"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

### 2. 请求日志中间件

```python
import time
import logging
from fastapi import Request

logger = logging.getLogger(__name__)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有请求"""
    start_time = time.time()
    
    # 记录请求
    logger.info(f"Request: {request.method} {request.url}")
    
    # 执行请求
    response = await call_next(request)
    
    # 记录响应
    duration = time.time() - start_time
    logger.info(
        f"Response: {response.status_code} "
        f"Duration: {duration:.3f}s"
    )
    
    # 添加响应头
    response.headers["X-Process-Time"] = str(duration)
    
    return response
```

### 3. 限流中间件

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

def add_rate_limiting(app: FastAPI):
    """添加限流"""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 使用
@router.post("/api/chat")
@limiter.limit("10/minute")
async def chat(request: Request, chat_request: ChatRequest):
    ...
```

---

## 数据模型

### 1. 请求模型

```python
# agio/api/schemas/chat.py

from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """Chat 请求"""
    
    agent_id: str = Field(description="Agent ID")
    message: str = Field(description="用户消息")
    user_id: str | None = Field(default=None, description="用户 ID")
    session_id: str | None = Field(default=None, description="会话 ID")
    stream: bool = Field(default=True, description="是否流式响应")
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "customer_support",
                "message": "How do I reset my password?",
                "user_id": "user_123",
                "stream": True
            }
        }

class ChatResponse(BaseModel):
    """Chat 响应（非流式）"""
    
    run_id: str
    response: str
    metrics: dict
```

### 2. 响应模型

```python
# agio/api/schemas/common.py

from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    
    total: int
    items: list[T]
    limit: int
    offset: int
    
    @property
    def has_more(self) -> bool:
        return self.offset + self.limit < self.total

class ErrorResponse(BaseModel):
    """错误响应"""
    
    error: dict
```

---

## 部署配置

### 1. 应用入口

```python
# agio/api/app.py

from fastapi import FastAPI
from .routes import agents, chat, runs, checkpoints, config, metrics, health
from .middleware import add_cors_middleware, add_rate_limiting
from .dependencies import get_registry, get_repository

def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    
    app = FastAPI(
        title="Agio API",
        description="Agent Framework API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # 添加中间件
    add_cors_middleware(app)
    add_rate_limiting(app)
    
    # 注册路由
    app.include_router(agents.router)
    app.include_router(chat.router)
    app.include_router(runs.router)
    app.include_router(checkpoints.router)
    app.include_router(config.router)
    app.include_router(metrics.router)
    app.include_router(health.router)
    
    # 启动事件
    @app.on_event("startup")
    async def startup_event():
        # 初始化组件
        registry = get_registry()
        # 加载配置
        from agio.registry import load_from_config
        load_from_config("./configs")
    
    return app

app = create_app()
```

### 2. 运行配置

```python
# main.py

import uvicorn
from agio.api.app import app

if __name__ == "__main__":
    uvicorn.run(
        "agio.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式
        workers=4     # 生产模式
    )
```

### 3. Docker 部署

```dockerfile
# Dockerfile

FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8000

# 运行
CMD ["uvicorn", "agio.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml

version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MONGODB_URI=mongodb://mongo:27017
    depends_on:
      - mongo
  
  mongo:
    image: mongo:latest
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

volumes:
  mongo_data:
```

---

## 使用指南

### 快速开始

#### 1. 安装依赖

```bash
pip install fastapi uvicorn sse-starlette python-jose[cryptography] passlib[bcrypt] slowapi
```

#### 2. 启动服务

```bash
# 开发模式
uvicorn agio.api.app:app --reload

# 生产模式
uvicorn agio.api.app:app --host 0.0.0.0 --port 8000 --workers 4
```

#### 3. 访问文档

```
http://localhost:8000/docs
```

### 常见场景

#### 场景 1: 创建并使用 Agent

```python
import httpx

# 1. 创建 Agent
response = httpx.post(
    "http://localhost:8000/api/agents",
    json={
        "name": "my_agent",
        "model": "gpt4",
        "system_prompt": "You are helpful"
    }
)

# 2. Chat
response = httpx.post(
    "http://localhost:8000/api/chat",
    json={
        "agent_id": "my_agent",
        "message": "Hello",
        "stream": False
    }
)

print(response.json())
```

#### 场景 2: 流式 Chat

```python
import httpx

with httpx.stream(
    "POST",
    "http://localhost:8000/api/chat",
    json={
        "agent_id": "my_agent",
        "message": "Tell me a story",
        "stream": True
    },
    headers={"Accept": "text/event-stream"}
) as response:
    for line in response.iter_lines():
        if line.startswith("data:"):
            data = line[5:].strip()
            print(data)
```

#### 场景 3: 管理 Runs

```python
# 列出 Runs
runs = httpx.get("http://localhost:8000/api/runs").json()

# 获取详情
run = httpx.get(f"http://localhost:8000/api/runs/{run_id}").json()

# 暂停
httpx.post(f"http://localhost:8000/api/runs/{run_id}/pause")

# 恢复
httpx.post(f"http://localhost:8000/api/runs/{run_id}/resume")
```

---

## 总结

这个 FastAPI Backend 设计具备以下特点：

1. **✅ RESTful 设计** - 完整的 CRUD 操作
2. **✅ 实时流式** - SSE 支持实时交互
3. **✅ 类型安全** - Pydantic 完整验证
4. **✅ 安全性** - JWT/API Key 认证 + RBAC
5. **✅ 可扩展** - 模块化设计
6. **✅ 生产就绪** - 错误处理、日志、限流

通过这个 Backend，开发者可以：
- 🚀 快速构建 Agent 应用
- 📡 实时流式交互
- 🔧 完整的执行控制
- 📊 详细的可观测性
- 🔒 企业级安全

