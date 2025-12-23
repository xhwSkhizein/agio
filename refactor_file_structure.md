# 代码组织重构方案

## 一、重构目标

### 1.1 当前代码状态

**已完成：**
- ✅ 新增 `ResumeExecutor`：统一的Session恢复执行器（`agio/runtime/resume_executor.py`）
- ✅ `control.py` 已简化：移除了 `retry_from_sequence`，功能由 `ResumeExecutor` 统一处理

**待重构：**
- ⏳ Agent相关代码仍分散在 `agio/runtime/` 和 `agio/agent.py` 中
- ⏳ 工具相关代码仍在 `agio/runtime/` 中
- ⏳ 模块边界不清晰

### 1.2 问题分析

当前代码组织存在以下问题：

1. **Agent相关代码分散**：Agent执行逻辑分散在 `agio/runtime/` 和 `agio/agent.py` 中
2. **模块边界不清晰**：`agio/runtime/` 混合了不同抽象层次的组件
3. **命名不一致**：Runner vs Executor 的使用不统一
4. **依赖关系复杂**：跨模块依赖较多，难以追踪
5. **ResumeExecutor位置**：`ResumeExecutor` 是通用功能，应该保留在 `runtime/` 中

### 1.2 重构目标

1. **集中Agent代码**：将Agent相关代码集中到 `agio/agent/` 目录
2. **明确模块边界**：`agio/runtime/` 只放通用基础设施
3. **统一命名规范**：Runner管理生命周期，Executor执行操作
4. **简化依赖关系**：减少跨模块依赖，提高内聚性

## 二、目标目录结构

### 2.1 重构后的目录结构

```
agio/
├── agent/                    # Agent专用模块（新增）
│   ├── __init__.py
│   ├── agent.py              # Agent类定义（从agio/agent.py移动）
│   ├── runner.py              # AgentRunner（从runtime/runner.py移动并重命名）
│   ├── executor.py            # AgentExecutor（从runtime/executor.py移动并重命名）
│   ├── context.py             # Agent上下文构建（从runtime/context.py移动）
│   ├── summarizer.py          # 终止摘要（从runtime/summarizer.py移动）
│   └── control.py             # 控制流（从runtime/control.py移动）
│
├── runtime/                   # 通用运行时基础设施
│   ├── __init__.py            # 更新导出
│   ├── executor.py            # RunnableExecutor（保持）
│   ├── resume_executor.py     # ResumeExecutor（保持，统一恢复执行器）
│   ├── wire.py                # 事件通道（保持）
│   └── event_factory.py       # 事件工厂（保持）
│
├── workflow/                  # Workflow模块（保持）
│   └── (保持当前结构)
│
├── tools/                     # 工具模块（新增）
│   ├── __init__.py            # 新增
│   ├── executor.py            # ToolExecutor（从runtime/tool_executor.py移动）
│   └── cache.py              # ToolResultCache（从runtime/tool_cache.py移动）
│
└── domain/                    # 领域模型（保持）
    └── (保持当前结构)
```

## 三、详细迁移计划

### 3.1 第一阶段：创建新目录结构

#### 步骤1.1：创建 `agio/agent/` 目录
- 创建 `agio/agent/__init__.py`
- 创建 `agio/agent/agent.py`（占位）
- 创建 `agio/agent/runner.py`（占位）
- 创建 `agio/agent/executor.py`（占位）
- 创建 `agio/agent/context.py`（占位）
- 创建 `agio/agent/summarizer.py`（占位）
- 创建 `agio/agent/control.py`（占位）

#### 步骤1.2：创建 `agio/tools/` 目录
- 创建 `agio/tools/__init__.py`
- 创建 `agio/tools/executor.py`（占位）
- 创建 `agio/tools/cache.py`（占位）

### 3.2 第二阶段：迁移Agent相关代码

#### 步骤2.1：迁移 `agio/agent.py` → `agio/agent/agent.py`

**操作：**
1. 复制 `agio/agent.py` 内容到 `agio/agent/agent.py`
2. 更新导入路径：
   - `from agio.runtime import StepRunner` → `from agio.agent.runner import AgentRunner`
   - `from agio.config import ExecutionConfig` → 保持不变
   - `from agio.domain import AgentSession` → 保持不变
   - `from agio.runtime import fork_session` → `from agio.agent.control import fork_session`

**修改点：**
```python
# 原代码 (agio/agent.py:97)
from agio.runtime import StepRunner

# 修改后 (agio/agent/agent.py)
from agio.agent.runner import AgentRunner

# 原代码 (agio/agent.py:111)
runner = StepRunner(
    agent=self,
    config=config,
    session_store=self.session_store,
)

# 修改后
runner = AgentRunner(
    agent=self,
    config=config,
    session_store=self.session_store,
)
```

#### 步骤2.2：迁移 `agio/runtime/runner.py` → `agio/agent/runner.py`

**操作：**
1. 复制 `agio/runtime/runner.py` 内容到 `agio/agent/runner.py`
2. 重命名类：`StepRunner` → `AgentRunner`
3. 更新导入路径：
   - `from agio.runtime.executor import StepExecutor` → `from agio.agent.executor import AgentExecutor`
   - `from agio.runtime.context import build_context_from_steps` → `from agio.agent.context import build_context_from_steps`
   - `from agio.runtime.event_factory import EventFactory` → `from agio.runtime.event_factory import EventFactory`（保持不变）
   - `from agio.runtime.control import AbortSignal` → `from agio.agent.control import AbortSignal`
   - `from agio.runtime.summarizer import ...` → `from agio.agent.summarizer import ...`

**修改点：**
```python
# 原代码 (runtime/runner.py:60)
class StepRunner:

# 修改后 (agent/runner.py)
class AgentRunner:

# 原代码 (runtime/runner.py:182)
executor = StepExecutor(
    model=self.agent.model,
    tools=self.agent.tools or [],
    config=self.config,
)

# 修改后
executor = AgentExecutor(
    model=self.agent.model,
    tools=self.agent.tools or [],
    config=self.config,
)
```

#### 步骤2.3：迁移 `agio/runtime/executor.py` → `agio/agent/executor.py`

**操作：**
1. 复制 `agio/runtime/executor.py` 内容到 `agio/agent/executor.py`
2. 重命名类：`StepExecutor` → `AgentExecutor`
3. 更新导入路径：
   - `from agio.runtime.tool_executor import ToolExecutor` → `from agio.tools.executor import ToolExecutor`
   - `from agio.runtime.event_factory import EventFactory` → 保持不变

**修改点：**
```python
# 原代码 (runtime/executor.py:87)
class StepExecutor:

# 修改后 (agent/executor.py)
class AgentExecutor:

# 原代码 (runtime/executor.py:113)
self.tool_executor = ToolExecutor(tools)

# 修改后（导入路径已更新）
self.tool_executor = ToolExecutor(tools)
```

#### 步骤2.4：迁移 `agio/runtime/context.py` → `agio/agent/context.py`

**操作：**
1. 复制 `agio/runtime/context.py` 内容到 `agio/agent/context.py`
2. 更新导入路径：
   - `from agio.domain import StepAdapter` → 保持不变
   - `from agio.providers.storage import SessionStore` → 保持不变

**修改点：**
- 主要是更新导入路径，函数逻辑保持不变

#### 步骤2.5：迁移 `agio/runtime/summarizer.py` → `agio/agent/summarizer.py`

**操作：**
1. 复制 `agio/runtime/summarizer.py` 内容到 `agio/agent/summarizer.py`
2. 更新导入路径（如果有）

**修改点：**
- 主要是更新导入路径，函数逻辑保持不变

#### 步骤2.6：迁移 `agio/runtime/control.py` → `agio/agent/control.py`

**操作：**
1. 复制 `agio/runtime/control.py` 内容到 `agio/agent/control.py`
2. **注意**：`retry_from_sequence` 功能已被 `ResumeExecutor` 替代，`control.py` 中只保留 `AbortSignal` 和 `fork_session`
3. 更新导入路径（如果有）

**修改点：**
```python
# 原代码 (runtime/control.py)
# 包含：AbortSignal, retry_from_sequence, fork_session

# 修改后 (agent/control.py)
# 只包含：AbortSignal, fork_session
# retry_from_sequence 功能已由 ResumeExecutor 统一处理
```

**重要说明：**
- `retry_from_sequence` 功能已被 `ResumeExecutor.resume_session()` 替代
- `ResumeExecutor` 是通用功能，保留在 `agio/runtime/` 中
- `control.py` 迁移后只包含 Agent 专用的控制流功能

### 3.3 第三阶段：迁移工具相关代码

#### 步骤3.1：迁移 `agio/runtime/tool_executor.py` → `agio/tools/executor.py`

**操作：**
1. 复制 `agio/runtime/tool_executor.py` 内容到 `agio/tools/executor.py`
2. 更新导入路径：
   - `from agio.runtime.tool_cache import get_tool_cache` → `from agio.tools.cache import get_tool_cache`

**修改点：**
```python
# 原代码 (runtime/tool_executor.py:11)
from agio.runtime.tool_cache import get_tool_cache

# 修改后 (tools/executor.py)
from agio.tools.cache import get_tool_cache
```

#### 步骤3.2：迁移 `agio/runtime/tool_cache.py` → `agio/tools/cache.py`

**操作：**
1. 复制 `agio/runtime/tool_cache.py` 内容到 `agio/tools/cache.py`
2. 更新导入路径（如果有）

**修改点：**
- 主要是更新导入路径，类逻辑保持不变

### 3.4 第四阶段：更新模块导出

#### 步骤4.1：更新 `agio/agent/__init__.py`

**内容：**
```python
"""
Agent module - Agent execution engine.

This module contains:
- Agent: Agent configuration and execution entry point
- AgentRunner: Step lifecycle management
- AgentExecutor: LLM call loop
- Context building, summarization, and control flow utilities
"""

from .agent import Agent
from .runner import AgentRunner
from .executor import AgentExecutor
from .context import build_context_from_steps, build_context_from_sequence_range, validate_context
from .summarizer import (
    build_termination_messages,
    DEFAULT_TERMINATION_USER_PROMPT,
    _format_termination_reason,
)
from .control import AbortSignal, fork_session  # retry_from_sequence已由ResumeExecutor替代

__all__ = [
    "Agent",
    "AgentRunner",
    "AgentExecutor",
    "build_context_from_steps",
    "build_context_from_sequence_range",
    "validate_context",
    "build_termination_messages",
    "DEFAULT_TERMINATION_USER_PROMPT",
    "_format_termination_reason",
    "AbortSignal",
    "fork_session",
]
```

#### 步骤4.2：更新 `agio/tools/__init__.py`

**内容：**
```python
"""
Tools module - Tool execution and caching.

This module contains:
- ToolExecutor: Unified tool executor
- ToolResultCache: Tool result caching
"""

from .executor import ToolExecutor
from .cache import ToolResultCache, get_tool_cache

__all__ = [
    "ToolExecutor",
    "ToolResultCache",
    "get_tool_cache",
]
```

#### 步骤4.3：更新 `agio/runtime/__init__.py`

**内容：**
```python
"""
Runtime module - Common runtime infrastructure.

This module contains:
- RunnableExecutor: Unified Run lifecycle management for all Runnable types
- ResumeExecutor: Unified Session Resume mechanism for Agent and Workflow
- Wire: Event streaming channel
- EventFactory: Context-bound event factory
"""

from .runnable_executor import RunnableExecutor
from .resume_executor import ResumeExecutor
from .wire import Wire
from .event_factory import EventFactory
from agio.domain import ExecutionContext

__all__ = [
    "RunnableExecutor",
    "ResumeExecutor",
    "Wire",
    "ExecutionContext",
    "EventFactory",
]
```

#### 步骤4.4：更新 `agio/__init__.py`

**内容：**
```python
"""
Agio - Multi-agent orchestration framework.
"""

from agio.agent import Agent

__all__ = ["Agent"]
```

### 3.5 第五阶段：更新所有导入引用

#### 步骤5.1：更新 `agio/workflow/` 中的导入

**需要更新的文件：**
- `agio/workflow/pipeline.py`
- `agio/workflow/loop.py`
- `agio/workflow/parallel.py`
- `agio/workflow/runnable_tool.py`

**修改示例（pipeline.py）：**
```python
# 原代码
from agio.runtime import RunnableExecutor

# 修改后（保持不变，因为RunnableExecutor仍在runtime中）
from agio.runtime import RunnableExecutor
```

**修改示例（runnable_tool.py）：**
```python
# 原代码
from agio.runtime import RunnableExecutor

# 修改后（保持不变）
from agio.runtime import RunnableExecutor
```

#### 步骤5.2：更新 `agio/api/` 中的导入

**需要更新的文件：**
- `agio/api/routes/runnables.py`
- `agio/api/routes/sessions.py`

**修改示例（runnables.py）：**
```python
# 原代码
from agio.runtime import Wire, RunnableExecutor

# 修改后（保持不变）
from agio.runtime import Wire, RunnableExecutor
```

**修改示例（sessions.py）：**
```python
# 原代码
from agio.agent import Agent
from agio.runtime import Wire, fork_session, ResumeExecutor

# 修改后
from agio.agent import Agent, fork_session
from agio.runtime import Wire, ResumeExecutor  # ResumeExecutor保留在runtime中
```

#### 步骤5.3：更新测试文件中的导入

**需要更新的文件：**
- `tests/test_*.py`
- `tests/runtime/test_*.py`
- `tests/workflow/test_*.py`
- `tests/tools/test_*.py`

**修改示例：**
```python
# 原代码
from agio.runtime import StepRunner, StepExecutor, Wire
from agio.runtime import ToolExecutor
from agio.runtime import AbortSignal

# 修改后
from agio.agent import AgentRunner, AgentExecutor, AbortSignal
from agio.tools import ToolExecutor
from agio.runtime import Wire
```

### 3.6 第六阶段：重命名类（可选，保持向后兼容）

#### 步骤6.1：在 `agio/runtime/runner.py` 中添加别名（向后兼容）

**操作：**
在 `agio/runtime/runner.py` 中添加：
```python
# 向后兼容别名
from agio.agent.runner import AgentRunner as StepRunner

__all__ = ["StepRunner"]  # 仅导出别名
```

**注意：** 这个文件在新结构中应该被删除，但为了向后兼容，可以保留一段时间。

#### 步骤6.2：在 `agio/runtime/executor.py` 中添加别名（向后兼容）

**操作：**
在 `agio/runtime/executor.py` 中添加：
```python
# 向后兼容别名
from agio.agent.executor import AgentExecutor as StepExecutor

__all__ = ["StepExecutor"]  # 仅导出别名
```

**注意：** 这个文件在新结构中应该被删除，但为了向后兼容，可以保留一段时间。

### 3.7 第七阶段：清理旧文件

#### 步骤7.1：删除已迁移的文件

**删除列表：**
- `agio/agent.py`（已迁移到 `agio/agent/agent.py`）
- `agio/runtime/runner.py`（已迁移到 `agio/agent/runner.py`）
- `agio/runtime/executor.py`（已迁移到 `agio/agent/executor.py`）
- `agio/runtime/context.py`（已迁移到 `agio/agent/context.py`）
- `agio/runtime/summarizer.py`（已迁移到 `agio/agent/summarizer.py`）
- `agio/runtime/control.py`（已迁移到 `agio/agent/control.py`，但只保留 `AbortSignal` 和 `fork_session`）
- `agio/runtime/tool_executor.py`（已迁移到 `agio/tools/executor.py`）
- `agio/runtime/tool_cache.py`（已迁移到 `agio/tools/cache.py`）

**保留在 `agio/runtime/` 的文件：**
- `agio/runtime/runnable_executor.py`（通用Run生命周期管理）
- `agio/runtime/resume_executor.py`（通用恢复执行器）
- `agio/runtime/wire.py`（事件通道）
- `agio/runtime/event_factory.py`（事件工厂）

**注意：** 如果使用了向后兼容别名，这些文件可以保留一段时间后再删除。

## 四、导入路径变更对照表

### 4.1 Agent相关导入变更

| 原导入路径 | 新导入路径 |
|-----------|-----------|
| `from agio.agent import Agent` | `from agio.agent import Agent`（保持不变） |
| `from agio.runtime import StepRunner` | `from agio.agent import AgentRunner` |
| `from agio.runtime import StepExecutor` | `from agio.agent import AgentExecutor` |
| `from agio.runtime.context import build_context_from_steps` | `from agio.agent import build_context_from_steps` |
| `from agio.runtime.summarizer import ...` | `from agio.agent import ...` |
| `from agio.runtime.control import AbortSignal` | `from agio.agent import AbortSignal` |
| `from agio.runtime.control import fork_session` | `from agio.agent import fork_session` |
| `from agio.runtime import ResumeExecutor` | `from agio.runtime import ResumeExecutor`（保持不变） |
| `from agio.runtime.control import retry_from_sequence` | 已废弃，使用 `ResumeExecutor.resume_session()` 替代 |

### 4.2 工具相关导入变更

| 原导入路径 | 新导入路径 |
|-----------|-----------|
| `from agio.runtime import ToolExecutor` | `from agio.tools import ToolExecutor` |
| `from agio.runtime.tool_cache import get_tool_cache` | `from agio.tools import get_tool_cache` |

### 4.3 Runtime相关导入变更

| 原导入路径 | 新导入路径 |
|-----------|-----------|
| `from agio.runtime import RunnableExecutor` | `from agio.runtime import RunnableExecutor`（保持不变） |
| `from agio.runtime import ResumeExecutor` | `from agio.runtime import ResumeExecutor`（保持不变） |
| `from agio.runtime import Wire` | `from agio.runtime import Wire`（保持不变） |
| `from agio.runtime import ExecutionContext` | `from agio.domain import ExecutionContext`（保持不变） |

## 五、命名变更对照表

### 5.1 类名变更

| 原类名 | 新类名 | 位置 |
|--------|--------|------|
| `StepRunner` | `AgentRunner` | `agio/agent/runner.py` |
| `StepExecutor` | `AgentExecutor` | `agio/agent/executor.py` |
| `RunnableExecutor` | `RunnableExecutor` | `agio/runtime/runnable_executor.py`（保持不变） |
| `ResumeExecutor` | `ResumeExecutor` | `agio/runtime/resume_executor.py`（保持不变） |
| `ToolExecutor` | `ToolExecutor` | `agio/tools/executor.py`（保持不变） |

### 5.2 向后兼容别名

为了保持向后兼容，可以在 `agio/runtime/` 中保留别名：

```python
# agio/runtime/runner.py（向后兼容）
from agio.agent.runner import AgentRunner as StepRunner
__all__ = ["StepRunner"]

# agio/runtime/executor.py（向后兼容）
from agio.agent.executor import AgentExecutor as StepExecutor
__all__ = ["StepExecutor"]
```

## 六、测试验证清单

### 6.1 单元测试验证

- [ ] Agent相关测试通过
- [ ] Workflow相关测试通过
- [ ] Tool相关测试通过
- [ ] Runtime相关测试通过

### 6.2 集成测试验证

- [ ] API路由测试通过
- [ ] 嵌套执行测试通过
- [ ] 事件流测试通过

### 6.3 导入验证

- [ ] 所有导入路径正确
- [ ] 没有循环依赖
- [ ] 向后兼容别名工作正常（如果使用）

## 七、迁移执行顺序

### 7.1 推荐执行顺序

1. **第一阶段**：创建新目录结构（不破坏现有代码）
2. **第二阶段**：迁移Agent相关代码（保持原文件，复制到新位置）
3. **第三阶段**：迁移工具相关代码（保持原文件，复制到新位置）
4. **第四阶段**：更新模块导出（更新 `__init__.py`）
5. **第五阶段**：更新所有导入引用（逐步更新）
6. **第六阶段**：添加向后兼容别名（可选）
7. **第七阶段**：删除旧文件（在所有测试通过后）

### 7.2 风险控制

- **分阶段执行**：每个阶段完成后运行测试
- **保留原文件**：直到所有测试通过后再删除
- **向后兼容**：使用别名保持向后兼容
- **版本控制**：每个阶段提交一次，便于回滚

## 八、预期收益

### 8.1 代码组织改进

- ✅ Agent相关代码集中在一个目录
- ✅ 模块边界清晰，职责明确
- ✅ 命名统一，易于理解

### 8.2 可维护性提升

- ✅ 修改Agent执行逻辑只需关注 `agio/agent/`
- ✅ 减少跨模块依赖
- ✅ 提高代码内聚性

### 8.3 开发体验改善

- ✅ 更容易找到相关代码
- ✅ 导入路径更清晰
- ✅ 代码结构更直观

## 九、ResumeExecutor 说明

### 9.1 ResumeExecutor 的作用

`ResumeExecutor` 是一个新增的统一恢复执行器，位于 `agio/runtime/resume_executor.py`。

**功能：**
- 统一的Session恢复机制，支持Agent和Workflow
- 自动从Steps推断 `runnable_id`
- 分析执行状态（已完成、待处理工具等）
- 支持幂等性恢复执行

**设计决策：**
- `ResumeExecutor` 是通用功能，**保留在 `agio/runtime/` 中**，不迁移到 `agio/agent/`
- 替代了原来分散在 `StepRunner` 中的 `retry_from_sequence` 等方法
- 通过 `RunnableExecutor` 执行恢复，确保Run生命周期管理的一致性

### 9.2 ResumeExecutor 在重构中的处理

**保持不变：**
- `agio/runtime/resume_executor.py` 位置不变
- 导入路径不变：`from agio.runtime import ResumeExecutor`
- 功能不变，继续作为通用运行时基础设施

**相关变更：**
- `control.py` 中的 `retry_from_sequence` 已被 `ResumeExecutor` 替代，迁移时不再包含此功能
- API层（`agio/api/routes/sessions.py`）已使用 `ResumeExecutor`，无需修改

## 十、详细代码修改示例

### 9.1 Agent类迁移示例

#### 原文件：`agio/agent.py`

```python
# 原代码片段
from agio.runtime import StepRunner
from agio.runtime import fork_session

class Agent:
    async def run(self, input: str, *, context: ExecutionContext) -> RunOutput:
        from agio.config import ExecutionConfig
        from agio.runtime import StepRunner
        
        runner = StepRunner(
            agent=self,
            config=config,
            session_store=self.session_store,
        )
        return await runner.run(session, input, context.wire, context=context)
    
    async def fork_session(self, session_id: str, sequence: int) -> str:
        from agio.runtime import fork_session
        return await fork_session(session_id, sequence, self.session_store)
```

#### 新文件：`agio/agent/agent.py`

```python
# 修改后的代码
from agio.agent.runner import AgentRunner
from agio.agent.control import fork_session

class Agent:
    async def run(self, input: str, *, context: ExecutionContext) -> RunOutput:
        from agio.config import ExecutionConfig
        from agio.agent.runner import AgentRunner
        
        runner = AgentRunner(
            agent=self,
            config=config,
            session_store=self.session_store,
        )
        return await runner.run(session, input, context.wire, context=context)
    
    async def fork_session(self, session_id: str, sequence: int) -> str:
        from agio.agent.control import fork_session
        return await fork_session(session_id, sequence, self.session_store)
```

### 9.2 StepRunner → AgentRunner 迁移示例

#### 原文件：`agio/runtime/runner.py`

```python
# 原代码片段
from agio.runtime.executor import StepExecutor
from agio.runtime.context import build_context_from_steps
from agio.runtime.control import AbortSignal
from agio.runtime.summarizer import build_termination_messages

class StepRunner:
    def __init__(self, agent, config, session_store):
        self.agent = agent
        self.config = config
        self.session_store = session_store
    
    async def run(self, session, query, wire, context):
        executor = StepExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=self.config,
        )
        # ...
```

#### 新文件：`agio/agent/runner.py`

```python
# 修改后的代码
from agio.agent.executor import AgentExecutor
from agio.agent.context import build_context_from_steps
from agio.agent.control import AbortSignal
from agio.agent.summarizer import build_termination_messages
from agio.runtime.event_factory import EventFactory  # 保持不变

class AgentRunner:
    def __init__(self, agent, config, session_store):
        self.agent = agent
        self.config = config
        self.session_store = session_store
    
    async def run(self, session, query, wire, context):
        executor = AgentExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=self.config,
        )
        # ...
```

### 9.3 StepExecutor → AgentExecutor 迁移示例

#### 原文件：`agio/runtime/executor.py`

```python
# 原代码片段
from agio.runtime.tool_executor import ToolExecutor
from agio.runtime.event_factory import EventFactory

class StepExecutor:
    def __init__(self, model, tools, config):
        self.model = model
        self.tools = tools
        self.tool_executor = ToolExecutor(tools)
        self.config = config
```

#### 新文件：`agio/agent/executor.py`

```python
# 修改后的代码
from agio.tools.executor import ToolExecutor
from agio.runtime.event_factory import EventFactory  # 保持不变

class AgentExecutor:
    def __init__(self, model, tools, config):
        self.model = model
        self.tools = tools
        self.tool_executor = ToolExecutor(tools)
        self.config = config
```

### 9.4 ToolExecutor 迁移示例

#### 原文件：`agio/runtime/tool_executor.py`

```python
# 原代码片段
from agio.runtime.tool_cache import get_tool_cache

class ToolExecutor:
    def __init__(self, tools, cache=None):
        self.tools_map = {t.name: t for t in tools}
        self._cache = cache or get_tool_cache()
```

#### 新文件：`agio/tools/executor.py`

```python
# 修改后的代码
from agio.tools.cache import get_tool_cache

class ToolExecutor:
    def __init__(self, tools, cache=None):
        self.tools_map = {t.name: t for t in tools}
        self._cache = cache or get_tool_cache()
```

### 9.5 测试文件更新示例

#### 原测试文件：`tests/test_step_basics.py`

```python
# 原代码
from agio.runtime import StepRunner, StepExecutor, Wire
from agio.runtime import ToolExecutor
from agio.runtime import AbortSignal

def test_step_execution():
    runner = StepRunner(...)
    executor = StepExecutor(...)
    tool_executor = ToolExecutor(...)
    signal = AbortSignal()
```

#### 新测试文件：`tests/test_step_basics.py`

```python
# 修改后的代码
from agio.agent import AgentRunner, AgentExecutor, AbortSignal
from agio.tools import ToolExecutor
from agio.runtime import Wire

def test_step_execution():
    runner = AgentRunner(...)
    executor = AgentExecutor(...)
    tool_executor = ToolExecutor(...)
    signal = AbortSignal()
```

## 十一、常见问题与解决方案

### 10.1 循环依赖问题

**问题：** Agent模块和Tools模块可能存在循环依赖

**解决方案：**
- 使用TYPE_CHECKING延迟导入
- 通过参数传递依赖，避免直接导入

**示例：**
```python
# agio/agent/executor.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agio.tools.executor import ToolExecutor

class AgentExecutor:
    def __init__(self, model, tools, config):
        # 延迟导入避免循环依赖
        from agio.tools.executor import ToolExecutor
        self.tool_executor = ToolExecutor(tools)
```

### 10.2 向后兼容问题

**问题：** 现有代码可能直接导入 `StepRunner` 和 `StepExecutor`

**解决方案：**
- 在 `agio/runtime/` 中保留别名
- 逐步迁移，不强制一次性更新所有导入

**示例：**
```python
# agio/runtime/runner.py（向后兼容层）
"""
Deprecated: Use agio.agent.AgentRunner instead.
This file is kept for backward compatibility only.
"""
from agio.agent.runner import AgentRunner as StepRunner

__all__ = ["StepRunner"]
```

### 10.3 测试文件更新

**问题：** 测试文件数量多，更新工作量大

**解决方案：**
- 使用脚本批量更新导入路径
- 分批次更新，每次更新一个测试目录

**脚本示例：**
```python
# scripts/update_imports.py
import re
import os

def update_imports(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # 替换导入路径
    content = re.sub(
        r'from agio\.runtime import StepRunner',
        'from agio.agent import AgentRunner',
        content
    )
    content = re.sub(
        r'from agio\.runtime import StepExecutor',
        'from agio.agent import AgentExecutor',
        content
    )
    # ... 更多替换规则
    
    with open(file_path, 'w') as f:
        f.write(content)
```

## 十二、迁移检查清单

### 11.1 代码迁移检查

- [ ] 所有Agent相关文件已迁移到 `agio/agent/`
- [ ] 所有工具相关文件已迁移到 `agio/tools/`
- [ ] 所有类名已重命名（StepRunner → AgentRunner等）
- [ ] 所有导入路径已更新
- [ ] `__init__.py` 文件已更新

### 11.2 测试检查

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 导入路径测试通过
- [ ] 向后兼容测试通过（如果使用）

### 11.3 文档检查

- [ ] README已更新
- [ ] API文档已更新
- [ ] 代码注释已更新
- [ ] 迁移文档已完善

### 11.4 清理检查

- [ ] 旧文件已删除（或标记为deprecated）
- [ ] 未使用的导入已清理
- [ ] 代码格式已统一
- [ ] Git提交已完成

## 十三、回滚方案

### 12.1 回滚步骤

如果迁移过程中出现问题，可以按以下步骤回滚：

1. **恢复文件：** 从Git历史恢复已删除的文件
2. **恢复导入：** 恢复所有导入路径到原始状态
3. **恢复导出：** 恢复 `__init__.py` 文件
4. **运行测试：** 确保所有测试通过

### 12.2 回滚命令

```bash
# 恢复所有文件
git checkout HEAD~1 -- agio/agent.py
git checkout HEAD~1 -- agio/runtime/runner.py
git checkout HEAD~1 -- agio/runtime/executor.py
# ... 更多文件

# 恢复目录结构
git checkout HEAD~1 -- agio/runtime/
git checkout HEAD~1 -- agio/__init__.py
```

### 12.3 部分回滚

如果只是部分迁移有问题，可以：

1. **保留新结构：** 保留 `agio/agent/` 和 `agio/tools/` 目录
2. **恢复旧文件：** 恢复 `agio/runtime/` 中的旧文件
3. **使用别名：** 通过别名保持兼容性

## 十四、后续优化建议

### 13.1 进一步优化

迁移完成后，可以考虑：

1. **统一命名规范：** 确保所有模块遵循统一的命名规范
2. **提取公共逻辑：** 将重复代码提取到公共模块
3. **优化导入：** 减少不必要的导入，提高启动速度
4. **完善文档：** 补充模块文档和使用示例

### 13.2 长期维护

1. **代码审查：** 确保新代码遵循新的组织结构
2. **文档更新：** 及时更新文档反映新的结构
3. **测试覆盖：** 确保新结构的测试覆盖率
4. **性能监控：** 监控迁移后的性能变化

---

## 十五、当前重构状态

### 15.1 已完成的工作

- ✅ **ResumeExecutor 统一恢复机制**
  - 新增 `agio/runtime/resume_executor.py`
  - 统一了Agent和Workflow的恢复逻辑
  - 替代了原来分散的 `retry_from_sequence` 方法
  - API层已集成使用

- ✅ **control.py 简化**
  - 移除了 `retry_from_sequence`（由 `ResumeExecutor` 替代）
  - 保留了 `AbortSignal` 和 `fork_session`

### 15.2 待完成的工作

- ⏳ **创建新目录结构**
  - 创建 `agio/agent/` 目录
  - 创建 `agio/tools/` 目录

- ⏳ **迁移Agent相关代码**
  - 迁移 `agio/agent.py` → `agio/agent/agent.py`
  - 迁移 `agio/runtime/runner.py` → `agio/agent/runner.py`（重命名为 `AgentRunner`）
  - 迁移 `agio/runtime/executor.py` → `agio/agent/executor.py`（重命名为 `AgentExecutor`）
  - 迁移 `agio/runtime/context.py` → `agio/agent/context.py`
  - 迁移 `agio/runtime/summarizer.py` → `agio/agent/summarizer.py`
  - 迁移 `agio/runtime/control.py` → `agio/agent/control.py`（只保留 `AbortSignal` 和 `fork_session`）

- ⏳ **迁移工具相关代码**
  - 迁移 `agio/runtime/tool_executor.py` → `agio/tools/executor.py`
  - 迁移 `agio/runtime/tool_cache.py` → `agio/tools/cache.py`

- ⏳ **更新模块导出和导入**
  - 更新所有 `__init__.py` 文件
  - 更新所有导入引用

- ⏳ **测试和验证**
  - 运行所有测试确保通过
  - 验证向后兼容性

### 15.3 重构进度

```
[████░░░░░░░░░░░░░░] 10% 完成

已完成：
- ResumeExecutor 统一恢复机制
- control.py 简化

待完成：
- 目录结构创建
- Agent代码迁移
- 工具代码迁移
- 导入路径更新
- 测试验证
```

---

**文档版本：** 1.1  
**最后更新：** 2024  
**维护者：** Agio Team  
**更新说明：** 添加了 ResumeExecutor 说明和当前重构状态

