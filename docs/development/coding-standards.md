# Agio Python 代码规范

> **版本**: 1.0

本文档定义了 Agio 项目的 Python 代码开发规范。

## 核心规则

1. **文档字符串**：所有模块、类、公共方法必须有英文文档字符串
2. **类型注解**：使用 `|` 语法，所有参数和返回值必须有类型注解
3. **导入组织**：标准库 → 第三方 → 本地，每组之间空一行
4. **注释**：使用英文，放在代码上方
5. **命名**：snake_case（变量/函数）、PascalCase（类）、UPPER_SNAKE_CASE（常量）

---

## 文档字符串

### 模块级

```python
"""
Module name - Brief description.

Detailed description of module functionality.
"""
```

### 类

```python
class Agent:
    """
    Agent configuration container.

    Holds configuration for Model and Tools.
    Implements Runnable protocol for multi-agent orchestration.
    """
```

### 公共方法

```python
async def execute(
    self,
    messages: list[dict],
    context: "ExecutionContext",
) -> "RunOutput":
    """
    Execute Agent, writing Step events to context.wire.

    Args:
        messages: List of LLM messages
        context: Execution context with wire and run_id (required)

    Returns:
        RunOutput: Execution result with response and metrics
    """
```

### 私有方法

```python
def _check_abort(self, abort_signal: "AbortSignal | None") -> None:
    """Check if execution should be aborted."""
```

**规则**：所有模块、类、公共方法必须有文档字符串；私有方法使用简单描述或省略。

---

## 类型注解

### 使用 Python 3.10+ 语法

```python
# ✅ Correct
def get_run(self, run_id: str) -> Run | None:
    ...

# ❌ Wrong
from typing import Optional
def get_run(self, run_id: str) -> Optional[Run]:
    ...
```

### 完整类型注解

```python
async def execute(
    self,
    messages: list[dict],
    context: "ExecutionContext",
    *,
    pending_tool_calls: list[dict] | None = None,
) -> "RunOutput":
    ...
```

### 前向引用

```python
# Use string annotation
def execute(self, context: "ExecutionContext") -> "RunOutput":
    ...
```

**规则**：使用 `|` 语法；所有函数参数和返回值必须有类型注解。

---

## 导入组织

```python
# 1. Standard library imports
import asyncio
from typing import Any

# 2. Third-party imports
from fastapi import APIRouter
from pydantic import BaseModel

# 3. Local imports
from agio.config import ConfigSystem
from agio.runtime import Runnable

# 4. TYPE_CHECKING imports (at the end)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from agio.agent import Agent
```

**规则**：每组之间空一行；每组内按字母顺序排序；使用绝对导入。

---

## 注释规范

```python
# ✅ Correct: Comment above code
# Create Session-level resources
wire = Wire()

# ❌ Wrong: Comment on the right side
wire = Wire()  # Create Session-level resources
```

**规则**：所有注释使用英文；注释放在代码上方；解释"为什么"而非"是什么"。

---

## 命名约定

- **变量和函数**：`snake_case` - `get_user_id()`, `user_name`
- **类**：`PascalCase` - `AgentExecutor`
- **常量**：`UPPER_SNAKE_CASE` - `DEFAULT_TIMEOUT`, `MAX_RETRIES`
- **私有成员**：单下划线前缀 - `self._id`, `def _private_method()`

---

## 代码格式

### 行长度

- 最大行长度：**100 字符**，超过时使用括号换行

### 空行

- 类和函数之间：**2 个空行**
- 方法之间：**1 个空行**
- 逻辑块之间：**1 个空行**

### 字符串格式化

```python
# ✅ Correct: Use f-string
message = f"Runnable not found: {runnable_id}"

# ❌ Wrong
message = "Runnable not found: {}".format(runnable_id)
```

### 代码长度限制

- 单个函数不超过 **50 行**
- 单个类不超过 **500 行**

---

## 异常处理

### API 层

```python
try:
    instance: Runnable = config_system.get_instance(runnable_id)
except Exception:
    raise HTTPException(
        status_code=404,
        detail=f"Runnable not found: {runnable_id}"
    )
```

### 内部代码

```python
try:
    result = await self._execute_tool(tool_call)
except Exception as e:
    logger.error("tool_execution_failed", tool=tool_call["name"], error=str(e))
    raise ComponentBuildError(f"Failed to execute tool: {e}") from e
```

---

## 工具配置

项目已配置 Black、isort、mypy：

```bash
black agio/
isort agio/
mypy agio/
```

配置见 `pyproject.toml`。

---

## 参考资源

- [PEP 8](https://pep8.org/) - Python 代码风格指南
- [PEP 484](https://peps.python.org/pep-0484/) - 类型提示
- [Black](https://black.readthedocs.io/) - 代码格式化工具
