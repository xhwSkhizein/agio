# API 模块重构执行规范

## 1. 核心定位

- **用途**：Control Plane API，提供系统管理和调试能力
- **可选性**：默认开启，可通过 `AGIO_API_ENABLED=false` 禁用
- **路径前缀**：所有路由以 `/agio` 开头
- **部署模式**：
  - 独立启动 FastAPI 服务
  - 整合到现有 FastAPI 应用

---

## 2. 目录结构

```
agio/api/
├── __init__.py          # 公共 API: create_router(), start_server()
├── app.py               # FastAPI 应用和 lifespan
├── router.py            # 主路由器，汇总所有子路由
├── deps.py              # 依赖注入
├── schemas/
│   ├── __init__.py
│   ├── common.py        # 通用响应模型
│   ├── config.py        # 配置相关
│   ├── agent.py         # Agent 相关
│   ├── chat.py          # 聊天相关
│   ├── session.py       # Session 相关
│   └── data.py          # Memory/Knowledge 相关
└── routes/
    ├── __init__.py
    ├── health.py        # /agio/health
    ├── config.py        # /agio/config/**
    ├── agents.py        # /agio/agents/**
    ├── chat.py          # /agio/chat/**
    ├── sessions.py      # /agio/sessions/**
    ├── memory.py        # /agio/memory/**
    ├── knowledge.py     # /agio/knowledge/**
    └── metrics.py       # /agio/metrics/**
```

---

## 3. 公共 API 设计

```python
# agio/api/__init__.py

from fastapi import APIRouter, FastAPI

def create_router(prefix: str = "/agio") -> APIRouter:
    """
    创建 Agio API 路由器，供外部 FastAPI 应用整合。
    
    Example:
        app = FastAPI()
        app.include_router(create_router())
    """
    ...

def create_app() -> FastAPI:
    """创建独立的 FastAPI 应用（包含 lifespan）"""
    ...

def start_server(host: str = "0.0.0.0", port: int = 8000, **kwargs):
    """启动独立的 API 服务"""
    ...
```

### 使用示例

```python
# 方式 1: 独立启动
from agio.api import start_server
start_server(host="0.0.0.0", port=8000)

# 方式 2: 整合到现有 FastAPI
from fastapi import FastAPI
from agio.api import create_router

app = FastAPI()
app.include_router(create_router())  # 默认 /agio 前缀

# 方式 3: 自定义前缀
app.include_router(create_router(prefix="/admin/agio"))

# 方式 4: 禁用 API（通过环境变量）
# AGIO_API_ENABLED=false
```

---

## 4. 路由设计

### 4.1 健康检查 `/agio/health`

| 方法 | 路径 | 描述 |
|-----|------|------|
| GET | `/agio/health` | 系统健康状态 |
| GET | `/agio/health/ready` | 就绪检查 |

### 4.2 配置管理 `/agio/config`

| 方法 | 路径 | 描述 |
|-----|------|------|
| GET | `/agio/config` | 列出所有配置（按类型分组） |
| GET | `/agio/config/{type}` | 列出某类型的所有配置 |
| GET | `/agio/config/{type}/{name}` | 获取单个配置详情 |
| PUT | `/agio/config/{type}/{name}` | 创建或更新配置 |
| DELETE | `/agio/config/{type}/{name}` | 删除配置 |
| GET | `/agio/config/components` | 列出已构建的组件实例 |
| POST | `/agio/config/components/{name}/rebuild` | 重建指定组件 |
| POST | `/agio/config/reload` | 从磁盘重新加载配置 |

**type 枚举**: `model`, `tool`, `memory`, `knowledge`, `storage`, `repository`, `agent`

### 4.3 Agent 管理 `/agio/agents`

| 方法 | 路径 | 描述 |
|-----|------|------|
| GET | `/agio/agents` | 列出所有 Agent |
| GET | `/agio/agents/{name}` | 获取 Agent 详情 |
| GET | `/agio/agents/{name}/status` | 获取 Agent 运行状态（实例信息） |

### 4.4 聊天测试 `/agio/chat`

| 方法 | 路径 | 描述 |
|-----|------|------|
| POST | `/agio/chat/{agent}` | 与 Agent 聊天（支持流式） |
| GET | `/agio/chat/{agent}/sessions` | 列出该 Agent 的会话 |
| POST | `/agio/chat/{agent}/sessions` | 创建新会话 |

**请求体**:
```json
{
  "message": "用户消息",
  "session_id": "可选，复用已有会话",
  "user_id": "可选",
  "stream": true
}
```

**流式响应**: SSE 格式，事件类型对应 `StepEventType`

### 4.5 会话管理 `/agio/sessions`

| 方法 | 路径 | 描述 |
|-----|------|------|
| GET | `/agio/sessions` | 列出所有会话 |
| GET | `/agio/sessions/{id}` | 获取会话详情 |
| DELETE | `/agio/sessions/{id}` | 删除会话 |
| GET | `/agio/sessions/{id}/runs` | 获取会话的运行历史 |
| GET | `/agio/sessions/{id}/steps` | 获取会话的所有步骤 |

### 4.6 Memory 数据 `/agio/memory`

| 方法 | 路径 | 描述 |
|-----|------|------|
| GET | `/agio/memory` | 列出所有 Memory 组件 |
| GET | `/agio/memory/{name}` | 获取 Memory 组件信息 |
| POST | `/agio/memory/{name}/search` | 搜索记忆 |
| GET | `/agio/memory/{name}/history/{session_id}` | 获取会话历史 |

### 4.7 Knowledge 数据 `/agio/knowledge`

| 方法 | 路径 | 描述 |
|-----|------|------|
| GET | `/agio/knowledge` | 列出所有 Knowledge 组件 |
| GET | `/agio/knowledge/{name}` | 获取 Knowledge 组件信息 |
| POST | `/agio/knowledge/{name}/search` | 搜索知识库 |

### 4.8 指标监控 `/agio/metrics`

| 方法 | 路径 | 描述 |
|-----|------|------|
| GET | `/agio/metrics` | 系统指标概览 |
| GET | `/agio/metrics/agents/{name}` | Agent 指标详情 |

---

## 5. 依赖注入设计

```python
# agio/api/deps.py

from fastapi import Depends
from agio.config import ConfigSystem, get_config_system
from agio.storage.repository import AgentRunRepository

def get_config_sys() -> ConfigSystem:
    """获取全局 ConfigSystem"""
    return get_config_system()

def get_repository() -> AgentRunRepository:
    """获取全局 Repository"""
    from agio.api.state import get_api_state
    return get_api_state().repository

def get_agent(name: str, config_sys: ConfigSystem = Depends(get_config_sys)):
    """获取 Agent 实例"""
    return config_sys.get(name)

def get_memory(name: str, config_sys: ConfigSystem = Depends(get_config_sys)):
    """获取 Memory 实例"""
    return config_sys.get(name)

def get_knowledge(name: str, config_sys: ConfigSystem = Depends(get_config_sys)):
    """获取 Knowledge 实例"""
    return config_sys.get(name)
```

---

## 6. 实现任务分解

### Phase 1: 基础架构 (必需)

- [ ] **Task 1.1**: 重构 `__init__.py`，导出 `create_router()`, `create_app()`, `start_server()`
- [ ] **Task 1.2**: 创建 `router.py` 汇总所有子路由
- [ ] **Task 1.3**: 重构 `deps.py`，统一依赖注入
- [ ] **Task 1.4**: 统一所有路由前缀为 `/agio`

### Phase 2: 核心路由 (必需)

- [ ] **Task 2.1**: 重构 `routes/health.py`
- [ ] **Task 2.2**: 重构 `routes/config.py` - 完整 CRUD
- [ ] **Task 2.3**: 重构 `routes/agents.py`
- [ ] **Task 2.4**: 重构 `routes/chat.py` - 支持流式

### Phase 3: 数据路由 (必需)

- [ ] **Task 3.1**: 实现 `routes/sessions.py`
- [ ] **Task 3.2**: 实现 `routes/memory.py`
- [ ] **Task 3.3**: 实现 `routes/knowledge.py`
- [ ] **Task 3.4**: 重构 `routes/metrics.py`

### Phase 4: Schema 整理

- [ ] **Task 4.1**: 创建 `schemas/common.py`
- [ ] **Task 4.2**: 创建 `schemas/config.py`
- [ ] **Task 4.3**: 创建 `schemas/session.py`
- [ ] **Task 4.4**: 创建 `schemas/data.py`

### Phase 5: 清理

- [ ] **Task 5.1**: 删除遗留文件 (`routes/runs.py`, `routes/steps.py`, `routes/config_management.py`)
- [ ] **Task 5.2**: 删除 `services/` 空目录
- [ ] **Task 5.3**: 更新 `README.md`

---

## 7. 组件接口补充建议

为支持完整的 API，建议对以下组件接口进行补充：

### Memory 接口补充

```python
# agio/components/memory/base.py

class SemanticMemoryManager(ABC):
    # 现有方法
    async def remember(self, user_id: str, memory: AgentMemoriedContent): ...
    async def recall(self, user_id: str, query: str, ...) -> list[AgentMemoriedContent]: ...
    
    # 建议补充
    async def list_memories(self, user_id: str, limit: int = 100) -> list[AgentMemoriedContent]:
        """列出用户的所有记忆"""
        ...
    
    async def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """删除指定记忆"""
        ...
```

### Knowledge 接口补充

```python
# agio/components/knowledge/base.py

class Knowledge(ABC):
    # 现有方法
    async def search(self, query: str, limit: int = 5) -> list[str]: ...
    
    # 建议补充
    def get_info(self) -> dict:
        """获取知识库元信息（文档数量、索引状态等）"""
        return {"name": self.name, "type": type(self).__name__}
```

---

## 8. 多智能体支持预留

当前 API 设计已为多智能体协作预留扩展点：

```
# 未来扩展
POST /agio/chat/{agent}           # agent 可以是单一 Agent 或 AgentTeam
GET  /agio/agents/{name}/type     # 返回 "single" 或 "team"
GET  /agio/agents/{name}/members  # 如果是 team，返回成员列表
```

Agent 聊天接口通过 `agent.arun_stream()` 调用，未来 `AgentTeam` 只需实现相同接口即可无缝接入。

---

## 9. 错误响应格式

统一使用以下错误响应格式：

```json
{
  "detail": "错误描述",
  "code": "ERROR_CODE",
  "context": {}
}
```

HTTP 状态码：
- `400` - 请求参数错误
- `404` - 资源不存在
- `422` - 验证错误
- `500` - 内部错误

---

## 10. 验收标准

1. **功能验收**
   - [ ] 所有路由可正常访问
   - [ ] CRUD 配置可正常工作
   - [ ] 聊天测试支持流式响应
   - [ ] Session/Memory/Knowledge 数据可查询

2. **集成验收**
   - [ ] `create_router()` 可被外部 FastAPI 应用整合
   - [ ] `start_server()` 可独立启动服务
   - [ ] `AGIO_API_ENABLED=false` 可禁用 API

3. **文档验收**
   - [ ] `/agio/docs` Swagger 文档完整
   - [ ] 所有端点有清晰的描述和示例
