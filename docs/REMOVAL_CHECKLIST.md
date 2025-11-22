# 代码清理检查清单

## 使用说明

此清单用于跟踪旧代码删除的进度。每完成一项，将 `[ ]` 改为 `[x]`。

---

## Phase 1: 文件删除 (8 个文件)

### 协议层
- [ ] 删除 `agio/protocol/events.py`

### 执行层
- [ ] 删除 `agio/execution/agent_executor.py`
- [ ] 删除 `agio/execution/checkpoint.py`
- [ ] 删除 `agio/execution/resume.py`

### Runner 层
- [ ] 删除 `agio/runners/base.py`
- [ ] 删除 `agio/runners/context.py`
- [ ] 删除 `agio/runners/state_tracker.py`

### Domain 层
- [ ] 删除 `agio/domain/messages.py`

---

## Phase 2: 代码清理

### 2.1 Agent 类 (`agio/agent/base.py`)

- [ ] 删除导入: `from agio.protocol.events import AgentEvent`
- [ ] 添加导入: `from agio.protocol.step_events import StepEvent` (如果还没有)
- [ ] 删除方法: `async def arun(...)`
- [ ] 删除方法: `async def arun_stream(...)`
- [ ] 删除方法: `async def get_run_history(...)`
- [ ] 重命名: `arun_step()` → `arun()`
- [ ] 重命名: `arun_step_stream()` → `arun_stream()`
- [ ] 重命名: `get_session_steps()` → `get_steps()`

### 2.2 Repository 接口 (`agio/db/repository.py`)

- [ ] 删除方法: `async def save_event(...)`
- [ ] 删除方法: `async def get_events(...)`
- [ ] 删除方法: `async def get_event_count(...)`
- [ ] 删除方法: `async def delete_events(...)`
- [ ] 删除 InMemoryRepository 中的 `self._events` 字段
- [ ] 删除 InMemoryRepository 中所有 event 相关实现

### 2.3 MongoDB Repository (`agio/db/mongo.py`)

- [ ] 删除字段: `self.events_collection = None`
- [ ] 删除初始化: `self.events_collection = self.db["events"]`
- [ ] 删除索引创建: events collection 相关的所有索引
- [ ] 删除方法: `async def save_event(...)`
- [ ] 删除方法: `async def get_events(...)`
- [ ] 删除方法: `async def get_event_count(...)`
- [ ] 删除方法: `async def delete_events(...)`
- [ ] 删除 `delete_run()` 中删除 events 的代码

### 2.4 Fork 逻辑 (`agio/execution/fork.py`)

- [ ] 删除导入: `from .checkpoint import ExecutionCheckpoint`
- [ ] 删除导入: `from agio.protocol.events import AgentEvent`
- [ ] 删除整个 `ForkManager` 类
- [ ] 保留 `fork_session()` 函数
- [ ] 保留 `fork_from_step_id()` 函数（如果实现了）

### 2.5 Protocol 包 (`agio/protocol/__init__.py`)

- [ ] 删除导入: `from agio.protocol.events import AgentEvent, EventType`
- [ ] 删除导出: `"AgentEvent"` from `__all__`
- [ ] 删除导出: `"EventType"` from `__all__`
- [ ] 确保只导出 Step 相关的类

### 2.6 API 路由 (`agio/api/routes/chat.py`)

- [ ] 更新导入: `AgentRunner` → `StepRunner`
- [ ] 更新导入: `AgentEvent` → `StepEvent`
- [ ] 更新代码: 使用 `StepRunner` 替代 `AgentRunner`
- [ ] 更新事件处理: 使用 `StepEvent` 替代 `AgentEvent`

---

## Phase 3: 导入更新

### 3.1 搜索并替换

运行以下命令查找所有需要更新的地方:

```bash
# 查找 AgentEvent 引用
grep -r "AgentEvent" agio/ --include="*.py"

# 查找 AgentRunner 引用  
grep -r "AgentRunner" agio/ --include="*.py"

# 查找 AgentExecutor 引用
grep -r "AgentExecutor" agio/ --include="*.py"

# 查找 ContextBuilder 引用
grep -r "ContextBuilder" agio/ --include="*.py"
```

### 3.2 逐个文件检查

对于每个找到的文件:

- [ ] 文件: ________________
  - [ ] 更新导入语句
  - [ ] 更新类型注解
  - [ ] 更新函数调用
  - [ ] 测试通过

---

## Phase 4: 测试更新

### 4.1 删除旧测试

- [ ] 搜索测试文件中的 `AgentEvent`
- [ ] 搜索测试文件中的 `AgentRunner`
- [ ] 删除或更新相关测试

### 4.2 运行测试

- [ ] 运行: `pytest tests/test_step_basics.py -v`
- [ ] 运行: `pytest tests/test_step_integration.py -v`
- [ ] 运行: `pytest tests/ -v` (所有测试)
- [ ] 修复所有失败的测试

---

## Phase 5: 文档更新

### 5.1 归档旧文档

- [ ] 创建目录: `docs/archive/`
- [ ] 移动: `refactor_core.md` → `docs/archive/`
- [ ] 移动: `core_concepts_explained.md` → `docs/archive/`

### 5.2 更新设计文档

- [ ] 更新: `agio/execution/DESIGN.md`
- [ ] 更新: `agio/api/DESIGN.md`
- [ ] 更新: README.md (如果有提到旧系统)

---

## Phase 6: 数据库清理

### 6.1 MongoDB

- [ ] 备份数据库: `mongodump --db agio --out backup/`
- [ ] (可选) 运行迁移脚本: 将 events 转为 steps
- [ ] 删除 collection: `db.events.drop()`
- [ ] 验证: 确认 `steps` collection 正常工作

---

## Phase 7: 最终验证

### 7.1 代码检查

- [ ] 运行: `grep -r "AgentEvent" agio/` → 应该为空
- [ ] 运行: `grep -r "AgentRunner" agio/` → 应该为空  
- [ ] 运行: `grep -r "agent_executor" agio/` → 应该为空
- [ ] 运行: `grep -r "from agio.protocol.events" agio/` → 应该为空

### 7.2 功能测试

- [ ] 运行 demo: `python examples/step_based_demo.py`
- [ ] 测试基本对话
- [ ] 测试 retry 功能
- [ ] 测试 fork 功能
- [ ] 测试 API 端点

### 7.3 性能测试

- [ ] 测试上下文构建速度 (应该 < 10ms for 100 steps)
- [ ] 测试 Step 保存速度
- [ ] 测试查询性能

---

## Phase 8: 提交

### 8.1 Git 操作

- [ ] 查看更改: `git status`
- [ ] 查看差异: `git diff`
- [ ] 添加文件: `git add .`
- [ ] 提交: `git commit -m "Remove old Run/Step/Event system, use Step-based only"`
- [ ] (可选) 创建 PR

### 8.2 发布说明

- [ ] 编写 CHANGELOG.md
- [ ] 标注破坏性更改
- [ ] 提供迁移指南

---

## 完成标准

所有以下条件都满足时，清理工作完成:

- [x] 所有旧文件已删除 (8 个)
- [ ] 所有旧代码已清理 (6 个文件)
- [ ] 所有导入已更新
- [ ] 所有测试通过
- [ ] Demo 正常运行
- [ ] 没有旧系统引用
- [ ] 文档已更新
- [ ] 数据库已清理

---

## 回滚计划

如果需要回滚:

```bash
# 方案 1: 恢复到备份分支
git checkout backup-old-system

# 方案 2: 恢复特定文件
git checkout HEAD~1 -- agio/protocol/events.py
git checkout HEAD~1 -- agio/runners/base.py

# 方案 3: 完全回滚
git reset --hard HEAD~1
```

---

## 注意事项

⚠️ **重要提醒**:

1. **备份**: 删除前务必创建 git 分支备份
2. **测试**: 每个阶段完成后都要运行测试
3. **渐进**: 不要一次性删除所有文件，逐步进行
4. **验证**: 删除每个文件后验证系统仍可运行
5. **文档**: 记录所有更改，便于回滚

---

## 预计时间

- Phase 1: 文件删除 - 30 分钟
- Phase 2: 代码清理 - 1 小时
- Phase 3: 导入更新 - 1 小时
- Phase 4: 测试更新 - 1 小时
- Phase 5: 文档更新 - 30 分钟
- Phase 6: 数据库清理 - 30 分钟
- Phase 7: 最终验证 - 1 小时
- Phase 8: 提交 - 30 分钟

**总计**: 约 6 小时

---

## 进度跟踪

- 开始时间: ___________
- 预计完成: ___________
- 实际完成: ___________
- 遇到的问题: ___________
- 解决方案: ___________
