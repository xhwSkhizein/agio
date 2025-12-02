# Phase 2: 统一执行协议 (Runnable)

## 目标

定义统一的 `Runnable` 协议，让单 Agent 和多 Agent 组合都实现相同接口，为 Phase 4 的多 Agent 协作做准备。

## 核心设计

### 1. Runnable 协议定义

新建文件 `agio/core/protocols.py`:

```python
from typing import Protocol, AsyncIterator, runtime_checkable

from agio.core import StepEvent


@runtime_checkable
class Runnable(Protocol):
    """
    统一的可执行协议。
    
    所有可执行单元（单 Agent、多 Agent 组合、Workflow）都实现此协议，
    确保它们产生相同格式的 StepEvent 流，可以与前端无缝对接。
    
    设计原则:
    1. 输入: 自然语言 query + 可选上下文
    2. 输出: AsyncIterator[StepEvent]
    3. 前端无需区分单 Agent 还是多 Agent
    """
    
    @property
    def name(self) -> str:
        """可执行单元的名称标识"""
        ...
    
    async def run(
        self,
        query: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        """
        执行并返回 StepEvent 流。
        
        Args:
            query: 用户输入
            session_id: 会话 ID（用于上下文持久化）
            user_id: 用户 ID
            
        Yields:
            StepEvent: 执行过程中的事件流
        """
        ...


class RunnableConfig(Protocol):
    """Runnable 的配置协议"""
    
    @property
    def runnable_type(self) -> str:
        """类型标识: 'agent', 'sequential', 'parallel', 'graph', etc."""
        ...
```

### 2. Agent 实现 Runnable

修改 `agio/agent/base.py`:

```python
from agio.core.protocols import Runnable


class Agent:  # 隐式实现 Runnable 协议
    """
    Agent Configuration Container.
    Implements Runnable protocol for unified execution interface.
    """
    
    @property
    def name(self) -> str:
        return self.id
    
    async def run(
        self,
        query: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        """执行 Agent，返回 StepEvent 流。"""
        # ... 现有 arun_stream 实现
```

### 3. 类型检查示例

```python
from agio.core.protocols import Runnable
from agio.agent import Agent

# 运行时类型检查
agent = Agent(model=model, tools=tools)
assert isinstance(agent, Runnable)  # True

# 类型提示
async def execute_runnable(runnable: Runnable, query: str):
    async for event in runnable.run(query):
        yield event
```

## 协议扩展点

### 3.1 元数据协议 (可选)

```python
class RunnableWithMetadata(Runnable, Protocol):
    """带元数据的 Runnable"""
    
    @property
    def description(self) -> str | None:
        """描述信息"""
        ...
    
    @property
    def input_schema(self) -> dict | None:
        """输入参数 JSON Schema"""
        ...
    
    @property
    def output_schema(self) -> dict | None:
        """输出格式 JSON Schema"""
        ...
```

### 3.2 可中断协议 (可选)

```python
from agio.execution.abort_signal import AbortSignal


class AbortableRunnable(Runnable, Protocol):
    """支持中断的 Runnable"""
    
    async def run(
        self,
        query: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        abort_signal: AbortSignal | None = None,
    ) -> AsyncIterator[StepEvent]:
        ...
```

## 文件变更

### 新增文件

```
agio/core/protocols.py
```

### 修改文件

```
agio/core/__init__.py       # 导出 Runnable
agio/agent/base.py          # 实现协议
```

## 实施步骤

1. 创建 `agio/core/protocols.py`，定义 `Runnable` 协议
2. 更新 `agio/core/__init__.py`，导出协议
3. 修改 `Agent` 类，添加 `name` 属性
4. 编写协议测试

## 验证

```python
# tests/core/test_protocols.py

import pytest
from agio.core.protocols import Runnable
from agio.agent import Agent


def test_agent_implements_runnable():
    """Agent 应该实现 Runnable 协议"""
    agent = Agent(model=mock_model, tools=[])
    assert isinstance(agent, Runnable)


def test_runnable_has_required_methods():
    """Runnable 协议应该包含必要的方法"""
    assert hasattr(Runnable, 'run')
    assert hasattr(Runnable, 'name')
```

## 与 Phase 4 的关系

Phase 4 的多 Agent 编排类都将实现 `Runnable` 协议：

```python
class Sequential(Runnable):
    """顺序执行多个 Runnable"""
    
class Parallel(Runnable):
    """并行执行多个 Runnable"""
    
class Graph(Runnable):
    """图结构执行"""
```

这确保了无论是单 Agent、顺序链、并行组还是复杂图，都能通过统一的 `run()` 方法执行，产生相同格式的 `StepEvent` 流。
