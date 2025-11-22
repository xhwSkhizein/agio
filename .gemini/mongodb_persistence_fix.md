# MongoDB Persistence Issue - Root Cause Analysis & Fix

## 问题描述
Agent 成功回复用户消息，但 MongoDB 中 `runs` 和 `events` 集合都是空的。

## 根本原因

### 数据流分析
```
User Message
    ↓
Agent.arun_stream()
    ↓
AgentRunner(agent, hooks, repository=agent.repository)  ← agent.repository = None!
    ↓
runner._emit_and_store(event)
    ↓
if self.repository:  ← False, 因为 repository 是 None
    await self.repository.save_event(...)  ← 永远不执行
```

### 代码定位

**1. Agent 初始化** (`agio/agent/base.py:67`)
```python
runner = AgentRunner(agent=self, hooks=self.hooks, repository=self.repository)
# self.repository 来自 Agent.__init__ 的参数
```

**2. Agent 创建** (`agio/registry/factory.py:114-121`)
```python
return Agent(
    model=model,
    tools=tools,
    memory=memory,
    knowledge=knowledge,
    name=config.name,
    system_prompt=system_prompt,
    # ❌ 缺少 repository 参数！
)
```

**3. AgentRunner 存储逻辑** (`agio/runners/base.py:83-88`)
```python
async def _emit_and_store(self, event: AgentEvent) -> AgentEvent:
    """存储并返回事件"""
    if self.repository:  # ← repository 是 None，条件不满足
        await self.repository.save_event(event, self._event_sequence)
        self._event_sequence += 1
    return event
```

## 修复方案

### ✅ 在 ComponentFactory 中注入 Repository

**修改文件**: `agio/registry/factory.py`

```python
def create_agent(self, config: AgentConfig) -> Any:
    from agio.agent.base import Agent
    from agio.db.mongo import MongoDBRepository
    import os
    
    # ... 其他解析逻辑 ...
    
    # ✅ 创建 repository
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    repository = MongoDBRepository(uri=mongo_uri, db_name="agio")
    
    return Agent(
        model=model,
        tools=tools,
        memory=memory,
        knowledge=knowledge,
        repository=repository,  # ✅ 注入 repository
        name=config.name,
        system_prompt=system_prompt,
    )
```

## 修复后的数据流

```
User Message
    ↓
Agent.arun_stream()
    ↓
AgentRunner(agent, hooks, repository=agent.repository)  ← repository = MongoDBRepository ✅
    ↓
runner._emit_and_store(event)
    ↓
if self.repository:  ← True ✅
    await self.repository.save_event(...)  ← 执行保存 ✅
```

## 验证方法

### 1. 重启服务
```bash
# 停止当前服务
kill <PID>

# 重新启动
./start.sh
```

### 2. 发送测试消息
访问 http://localhost:3000/chat/simple_assistant，发送 "Hello"

### 3. 检查 MongoDB
```bash
mongosh

use agio

# 查看 runs
db.runs.find().count()  # 应该 > 0
db.runs.findOne()       # 查看完整 run 数据

# 查看 events  
db.events.find().count()  # 应该 > 0
db.events.find().limit(5) # 查看前 5 个事件
```

### 4. 通过 API 验证
```bash
# 列出 runs
curl http://localhost:8900/api/runs | jq

# 查看特定 run
curl http://localhost:8900/api/runs/<run_id> | jq
```

## 其他发现

### Repository 使用情况

当前系统中有 3 处使用 repository：

1. **AgentRunner** (`agio/runners/base.py:83-88`)
   - 保存 events
   - 保存 runs

2. **EventStorageHook** (`agio/agent/hooks/event_storage.py`)
   - 已废弃，注释说明被 AgentRunner 替代

3. **CheckpointManager** (`agio/execution/checkpoint_manager.py`)
   - 保存 checkpoints（未测试）

### 设计改进建议

**当前**: 每个 Agent 创建自己的 Repository 实例
```python
# 问题：每个 agent 都创建新连接
agent1.repository = MongoDBRepository()  # Connection 1
agent2.repository = MongoDBRepository()  # Connection 2
```

**建议**: 使用单例或依赖注入
```python
# 方案 1: 全局单例
repository = get_global_repository()

# 方案 2: DI 容器
factory = ComponentFactory(registry, repository)
```

这样可以：
- 共享 MongoDB 连接
- 更好的连接池管理
- 便于测试（可注入 mock）

## 总结

✅ **问题**: ComponentFactory 创建 Agent 时未注入 repository
✅ **原因**: AgentRunner 检查 `if self.repository` 失败
✅ **修复**: 在 factory 中创建并注入 MongoDBRepository
✅ **影响**: 现在所有 Agent 执行都会保存到 MongoDB
