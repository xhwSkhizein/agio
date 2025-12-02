# Phase 1: 清理与简化

## 目标

删除冗余代码，简化 Agent 类 API，保持向后兼容的 StepEvent 协议。

## 变更清单

### 1. Agent 类简化

**当前状态** (`agio/agent/base.py`):
```python
class Agent:
    async def arun(self, query, ...) -> AsyncIterator[str]:
        """返回文本流 - 冗余"""
        
    async def arun_stream(self, query, ...) -> AsyncIterator[StepEvent]:
        """返回事件流 - 保留"""
```

**目标状态**:
```python
class Agent:
    async def run(self, query, ...) -> AsyncIterator[StepEvent]:
        """统一的执行接口，返回事件流"""
```

### 2. 代码变更详情

#### 2.1 删除 `Agent.arun()` 方法

```python
# 删除以下方法 (agio/agent/base.py 第 39-65 行)
async def arun(
    self, query: str, user_id: str | None = None, session_id: str | None = None
) -> AsyncIterator[str]:
    """
    执行 Agent，返回文本流。
    ...
    """
    # 整个方法删除
```

#### 2.2 重命名 `arun_stream` → `run`

```python
# Before
async def arun_stream(self, query: str, ...) -> AsyncIterator[StepEvent]:

# After
async def run(self, query: str, ...) -> AsyncIterator[StepEvent]:
```

#### 2.3 更新 API 调用点

**`agio/api/routes/chat.py`**:
```python
# Before
async for event in agent.arun_stream(query=message, ...):

# After
async for event in agent.run(query=message, ...):
```

### 3. 测试验证

确保以下测试通过:
1. `tests/test_api.py` - API 端到端测试
2. 新增 `tests/agent/test_agent_run.py` - Agent.run() 单元测试

### 4. 迁移指南

如果有外部代码使用 `arun()`:
```python
# 旧代码
async for text in agent.arun(query):
    print(text, end="")

# 新代码
from agio.core import StepEventType

async for event in agent.run(query):
    if event.type == StepEventType.STEP_DELTA and event.delta:
        if event.delta.content:
            print(event.delta.content, end="")
```

## 实施步骤

```bash
# Step 1: 修改 Agent 类
# - 删除 arun 方法
# - 重命名 arun_stream -> run

# Step 2: 更新调用点
grep -r "arun_stream\|\.arun(" agio/ --include="*.py"
# 逐一更新

# Step 3: 运行测试
pytest tests/ -v

# Step 4: 更新文档
# 如有必要
```

## 预期结果

- Agent API 从 2 个执行方法简化为 1 个
- 保持 StepEvent 协议不变
- 前端代码无需修改
