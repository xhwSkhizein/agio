# 重构方案补充和完善建议

## 一、发现的问题

### 1.1 遗漏的类和函数

#### 问题1：`TerminationSummaryResult` 类
- **位置**：`agio/runtime/runner.py:52`
- **问题**：重构方案没有提到这个 `NamedTuple` 类
- **影响**：迁移 `runner.py` 时需要一起迁移这个类
- **建议**：在步骤2.2中明确说明需要迁移 `TerminationSummaryResult`

#### 问题2：`ToolCallAccumulator` 类
- **位置**：`agio/runtime/executor.py:41`
- **问题**：重构方案没有提到这个辅助类
- **影响**：迁移 `executor.py` 时需要一起迁移这个类
- **建议**：在步骤2.3中明确说明需要迁移 `ToolCallAccumulator`

#### 问题3：`runner.py` 中的 `_generate_termination_summary` 方法
- **位置**：`agio/runtime/runner.py:338`
- **问题**：这个方法内部直接使用了 `summarizer` 模块的功能，但重构方案没有说明如何处理
- **影响**：迁移后需要确保导入路径正确
- **建议**：在步骤2.2中明确说明需要更新方法内部的导入

### 1.2 导入依赖遗漏

#### 问题4：`runner.py` 中的 observability 依赖
- **位置**：`agio/runtime/runner.py:33`
- **导入**：`from agio.observability.tracker import set_tracking_context, clear_tracking_context`
- **问题**：重构方案没有提到这个依赖
- **影响**：迁移后需要保持这个导入不变
- **建议**：在步骤2.2中明确说明需要保留 observability 相关导入

#### 问题5：`runner.py` 中的 StepAdapter 依赖
- **位置**：`agio/runtime/runner.py:32`
- **导入**：`from agio.domain.adapters import StepAdapter`
- **问题**：重构方案没有提到这个依赖
- **影响**：迁移后需要保持这个导入不变
- **建议**：在步骤2.2中明确说明需要保留 domain 相关导入

#### 问题6：`executor.py` 中的 StepAdapter 依赖
- **位置**：`agio/runtime/executor.py:27`
- **导入**：`from agio.domain.adapters import StepAdapter`
- **问题**：重构方案没有提到这个依赖
- **影响**：迁移后需要保持这个导入不变
- **建议**：在步骤2.3中明确说明需要保留 domain 相关导入

### 1.3 API路由导入更新遗漏

#### 问题7：`sessions.py` 中的 `fork_session` 导入
- **位置**：`agio/api/routes/sessions.py:19`
- **当前导入**：`from agio.runtime import Wire, fork_session`
- **应该改为**：`from agio.runtime import Wire` 和 `from agio.agent import fork_session`
- **问题**：重构方案在步骤5.2中提到了，但需要更明确
- **建议**：在步骤5.2中明确列出需要更新的具体行号

### 1.4 函数签名和返回值细节

#### 问题8：`fork_session` 的返回值
- **位置**：`agio/runtime/control.py:83`
- **返回值**：`tuple[str, int, Optional[str]]`
- **问题**：重构方案没有提到返回值的具体结构
- **影响**：调用方需要知道返回值结构
- **建议**：在步骤2.6中明确说明 `fork_session` 的返回值结构

### 1.5 `__init__.py` 导出遗漏

#### 问题9：`runtime/__init__.py` 中的其他导出
- **位置**：`agio/runtime/__init__.py`
- **当前导出**：包括 `build_context_from_steps`, `build_termination_messages`, `DEFAULT_TERMINATION_USER_PROMPT` 等
- **问题**：重构方案在步骤4.3中只提到了核心导出，但没有说明这些辅助函数的导出
- **影响**：迁移后这些函数应该从 `agio.agent` 导出，而不是 `agio.runtime`
- **建议**：在步骤4.3中明确说明需要移除这些导出，因为它们会迁移到 `agio.agent`

#### 问题10：`runtime/__init__.py` 中的 `build_context_from_sequence_range` 和 `validate_context`
- **位置**：`agio/runtime/context.py:70, 112`
- **问题**：重构方案提到了这些函数，但没有说明它们是否也需要导出
- **影响**：如果有外部代码使用这些函数，需要明确导出路径
- **建议**：在步骤4.1中明确说明这些函数的导出

## 二、需要补充的细节

### 2.1 迁移 `runner.py` 时的完整导入列表

**需要更新的导入：**
```python
# 原代码
from agio.runtime.executor import StepExecutor
from agio.runtime.context import build_context_from_steps
from agio.runtime.control import AbortSignal
from agio.runtime.summarizer import (
    DEFAULT_TERMINATION_USER_PROMPT,
    _format_termination_reason,
)

# 修改后
from agio.agent.executor import AgentExecutor
from agio.agent.context import build_context_from_steps
from agio.agent.control import AbortSignal
from agio.agent.summarizer import (
    DEFAULT_TERMINATION_USER_PROMPT,
    _format_termination_reason,
)
```

**需要保持不变的导入：**
```python
# 这些导入保持不变
from agio.domain import (
    AgentSession,
    MessageRole,
    Step,
    StepEventType,
    RunOutput,
    RunMetrics,
)
from agio.domain.adapters import StepAdapter
from agio.domain import ExecutionContext
from agio.observability.tracker import set_tracking_context, clear_tracking_context
from agio.runtime.event_factory import EventFactory
from agio.runtime.wire import Wire
```

### 2.2 迁移 `executor.py` 时的完整导入列表

**需要更新的导入：**
```python
# 原代码
from agio.runtime.tool_executor import ToolExecutor

# 修改后
from agio.tools.executor import ToolExecutor
```

**需要保持不变的导入：**
```python
# 这些导入保持不变
from agio.domain import (
    MessageRole,
    Step,
    StepDelta,
    StepEvent,
    StepMetrics,
)
from agio.domain.adapters import StepAdapter
from agio.runtime.event_factory import EventFactory
```

### 2.3 `runner.py` 中 `_generate_termination_summary` 方法的处理

**当前实现**（`runner.py:338-548`）：
- 方法内部直接创建 Steps 和发送事件
- 使用了 `summarizer` 模块的 `DEFAULT_TERMINATION_USER_PROMPT` 和 `_format_termination_reason`
- 这个方法应该保留在 `AgentRunner` 中，因为它是 Agent 执行逻辑的一部分

**迁移后**：
- 方法保留在 `agio/agent/runner.py` 中
- 导入改为：`from agio.agent.summarizer import DEFAULT_TERMINATION_USER_PROMPT, _format_termination_reason`

### 2.4 `fork_session` 函数的返回值说明

**函数签名**：
```python
async def fork_session(
    original_session_id: str,
    sequence: int,
    session_store: "SessionStore",
    modified_content: Optional[str] = None,
    modified_tool_calls: Optional[List[dict]] = None,
    exclude_last: bool = False,
) -> tuple[str, int, Optional[str]]:
```

**返回值说明**：
- `str`: 新创建的 session_id
- `int`: 最后一个 step 的 sequence 号
- `Optional[str]`: 如果是 user step fork，返回待处理的 user message；否则为 None

**调用示例**（`sessions.py:356`）：
```python
new_session_id, last_sequence, pending_user_message = await fork_session(
    original_session_id=session_id,
    sequence=request.sequence,
    session_store=session_store,
    modified_content=request.content,
    modified_tool_calls=request.tool_calls,
)
```

## 三、需要更新的文件清单（补充）

### 3.1 API路由文件

#### `agio/api/routes/sessions.py`
- **第19行**：`from agio.runtime import Wire, fork_session`
  - 改为：`from agio.runtime import Wire` 和 `from agio.agent import fork_session`
- **第404行**：`from agio.runtime import ResumeExecutor`（保持不变）

#### `agio/api/routes/runnables.py`
- **第24行**：`from agio.runtime import Wire, RunnableExecutor`（保持不变，正确）

### 3.2 Workflow文件

#### `agio/workflow/runnable_tool.py`
- **第200行**：`from agio.runtime import RunnableExecutor`（保持不变，正确）

### 3.3 测试文件（需要全面检查）

需要检查以下测试文件中的导入：

#### `tests/test_step_basics.py`
- **第242行**：`from agio.runtime import build_context_from_steps`
  - 改为：`from agio.agent import build_context_from_steps`

#### `tests/test_step_integration.py`
- **第19行**：`from agio.runtime import StepRunner, StepExecutor, Wire`
  - 改为：`from agio.agent import AgentRunner, AgentExecutor` 和 `from agio.runtime import Wire`
- **第181行**：`from agio.runtime import build_context_from_steps`
  - 改为：`from agio.agent import build_context_from_steps`
- **第232行**：`from agio.runtime import fork_session`
  - 改为：`from agio.agent import fork_session`

#### `tests/test_context_filtering.py`
- **第9行**：`from agio.runtime.context import build_context_from_steps`
  - 改为：`from agio.agent import build_context_from_steps`

#### `tests/test_tool_executor.py`
- **第6行**：`from agio.runtime import ToolExecutor, Wire`
  - 改为：`from agio.tools import ToolExecutor` 和 `from agio.runtime import Wire`

#### `tests/tools/test_*.py`（多个文件）
- `tests/tools/test_glob_tool.py` 第7行：`from agio.runtime import AbortSignal`
  - 改为：`from agio.agent import AbortSignal`
- `tests/tools/test_ls_tool.py` 第9行：`from agio.runtime import AbortSignal`
  - 改为：`from agio.agent import AbortSignal`
- `tests/tools/test_grep_tool.py` 第7行：`from agio.runtime import AbortSignal`
  - 改为：`from agio.agent import AbortSignal`
- `tests/tools/test_file_read_tool.py` 第7行：`from agio.runtime import AbortSignal`
  - 改为：`from agio.agent import AbortSignal`
- `tests/tools/test_file_edit_tool.py` 第7行：`from agio.runtime import AbortSignal`
  - 改为：`from agio.agent import AbortSignal`

#### `tests/runtime/test_summarizer.py`
- **第8-12行**：
  ```python
  # 原代码
  from agio.runtime.summarizer import (
      build_termination_messages,
      DEFAULT_TERMINATION_USER_PROMPT,
      _format_termination_reason,
  )
  
  # 修改后
  from agio.agent.summarizer import (
      build_termination_messages,
      DEFAULT_TERMINATION_USER_PROMPT,
      _format_termination_reason,
  )
  ```

#### 其他测试文件
- `tests/test_step_metadata.py`（需要检查）
- 其他测试文件（需要全面搜索）

## 四、向后兼容性考虑

### 4.1 向后兼容别名的完整实现

如果选择向后兼容，需要在 `agio/runtime/__init__.py` 中保留以下导出：

```python
# agio/runtime/__init__.py（向后兼容版本）
"""
Runtime module - Common runtime infrastructure.

DEPRECATED: Some exports have moved to agio.agent and agio.tools.
This module is kept for backward compatibility.
"""

from .runnable_executor import RunnableExecutor
from .resume_executor import ResumeExecutor
from .wire import Wire
from .event_factory import EventFactory
from agio.domain import ExecutionContext

# 向后兼容别名
from agio.agent.runner import AgentRunner as StepRunner
from agio.agent.executor import AgentExecutor as StepExecutor
from agio.agent.control import AbortSignal, fork_session
from agio.tools.executor import ToolExecutor
from agio.tools.cache import ToolResultCache, get_tool_cache

__all__ = [
    # 核心运行时基础设施（保持不变）
    "RunnableExecutor",
    "ResumeExecutor",
    "Wire",
    "ExecutionContext",
    "EventFactory",
    # 向后兼容别名
    "StepRunner",
    "StepExecutor",
    "AbortSignal",
    "fork_session",
    "ToolExecutor",
    "ToolResultCache",
    "get_tool_cache",
]
```

**注意**：根据用户规则，如果不要求向后兼容，应该直接删除这些导出。

### 4.2 废弃警告（可选）

如果保留向后兼容，可以添加废弃警告：

```python
import warnings

def _deprecated_import(name: str, new_location: str):
    """Helper to show deprecation warning."""
    warnings.warn(
        f"{name} has moved to {new_location}. "
        f"Please update your imports.",
        DeprecationWarning,
        stacklevel=3,
    )

# 在向后兼容别名处添加警告
def __getattr__(name: str):
    if name == "StepRunner":
        _deprecated_import("StepRunner", "agio.agent.AgentRunner")
        return AgentRunner
    elif name == "StepExecutor":
        _deprecated_import("StepExecutor", "agio.agent.AgentExecutor")
        return AgentExecutor
    # ... 其他别名
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## 五、迁移检查清单补充

### 5.1 代码迁移检查（补充）

- [ ] `TerminationSummaryResult` 类已迁移
- [ ] `ToolCallAccumulator` 类已迁移
- [ ] `_generate_termination_summary` 方法中的导入已更新
- [ ] `runner.py` 中的 observability 导入保持不变
- [ ] `executor.py` 中的 StepAdapter 导入保持不变
- [ ] `fork_session` 的返回值文档已更新

### 5.2 导入验证（补充）

- [ ] `agio/api/routes/sessions.py` 中的 `fork_session` 导入已更新
- [ ] 所有测试文件中的导入已更新
- [ ] `agio/runtime/__init__.py` 中已移除迁移的导出
- [ ] `agio/agent/__init__.py` 中已添加所有必要的导出

### 5.3 功能验证（补充）

- [ ] `fork_session` 的返回值处理正确
- [ ] `_generate_termination_summary` 方法正常工作
- [ ] observability tracking 正常工作
- [ ] 所有工具执行功能正常

## 六、建议的修改方案

### 6.1 更新步骤2.2（迁移 runner.py）

在步骤2.2中添加：

**需要迁移的类：**
- `StepRunner` → `AgentRunner`
- `TerminationSummaryResult`（保持不变，随文件迁移）

**需要更新的导入：**
```python
# 更新这些导入
from agio.runtime.executor import StepExecutor → from agio.agent.executor import AgentExecutor
from agio.runtime.context import build_context_from_steps → from agio.agent.context import build_context_from_steps
from agio.runtime.control import AbortSignal → from agio.agent.control import AbortSignal
from agio.runtime.summarizer import ... → from agio.agent.summarizer import ...

# 保持这些导入不变
from agio.domain import ...  # 所有domain导入
from agio.domain.adapters import StepAdapter
from agio.observability.tracker import set_tracking_context, clear_tracking_context
from agio.runtime.event_factory import EventFactory
from agio.runtime.wire import Wire
```

**需要更新的方法：**
- `_generate_termination_summary` 方法内部的 `summarizer` 导入需要更新

### 6.2 更新步骤2.3（迁移 executor.py）

在步骤2.3中添加：

**需要迁移的类：**
- `StepExecutor` → `AgentExecutor`
- `ToolCallAccumulator`（保持不变，随文件迁移）

**需要更新的导入：**
```python
# 更新这个导入
from agio.runtime.tool_executor import ToolExecutor → from agio.tools.executor import ToolExecutor

# 保持这些导入不变
from agio.domain import ...  # 所有domain导入
from agio.domain.adapters import StepAdapter
from agio.runtime.event_factory import EventFactory
```

### 6.3 更新步骤2.6（迁移 control.py）

在步骤2.6中添加：

**函数签名和返回值：**
```python
async def fork_session(
    original_session_id: str,
    sequence: int,
    session_store: "SessionStore",
    modified_content: Optional[str] = None,
    modified_tool_calls: Optional[List[dict]] = None,
    exclude_last: bool = False,
) -> tuple[str, int, Optional[str]]:
    """
    返回值：
    - str: 新创建的 session_id
    - int: 最后一个 step 的 sequence 号
    - Optional[str]: 如果是 user step fork，返回待处理的 user message；否则为 None
    """
```

### 6.4 更新步骤4.3（更新 runtime/__init__.py）

在步骤4.3中明确说明：

**需要移除的导出：**
- `build_context_from_steps`（已迁移到 `agio.agent`）
- `build_termination_messages`（已迁移到 `agio.agent`）
- `DEFAULT_TERMINATION_USER_PROMPT`（已迁移到 `agio.agent`）
- `AbortSignal`（已迁移到 `agio.agent`）
- `fork_session`（已迁移到 `agio.agent`）
- `ToolExecutor`（已迁移到 `agio.tools`）
- `ToolResultCache`（已迁移到 `agio.tools`）
- `get_tool_cache`（已迁移到 `agio.tools`）

**保留的导出：**
- `RunnableExecutor`
- `ResumeExecutor`
- `Wire`
- `ExecutionContext`（从 `agio.domain` 重新导出）
- `EventFactory`

### 6.5 更新步骤5.2（更新 API 路由）

在步骤5.2中添加具体的行号和修改：

**`agio/api/routes/sessions.py`：**
- **第19行**：
  ```python
  # 原代码
  from agio.runtime import Wire, fork_session
  
  # 修改后
  from agio.runtime import Wire
  from agio.agent import fork_session
  ```

## 七、总结

主要需要补充的内容：

1. **遗漏的类和函数**：`TerminationSummaryResult`, `ToolCallAccumulator`
2. **导入依赖细节**：observability, StepAdapter 等依赖的处理
3. **函数签名细节**：`fork_session` 的返回值结构
4. **API路由更新**：具体的行号和修改内容
5. **导出清理**：明确哪些导出需要从 `runtime/__init__.py` 移除

建议在重构方案中补充这些细节，确保迁移过程更加清晰和完整。

