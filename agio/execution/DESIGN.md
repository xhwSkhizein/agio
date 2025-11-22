# Agio 执行控制系统详细设计

> **目标**：打造时光机般的调试体验 - 支持暂停、恢复、回溯、Fork 任意执行点

## 📋 目录

1. [设计理念](#设计理念)
2. [核心架构](#核心架构)
3. [Checkpoint 设计](#checkpoint-设计)
4. [状态序列化](#状态序列化)
5. [恢复机制](#恢复机制)
6. [Fork 机制](#fork-机制)
7. [执行控制](#执行控制)
8. [时光旅行调试](#时光旅行调试)
9. [使用指南](#使用指南)
10. [实现路线图](#实现路线图)

---

## 设计理念

### 核心原则

1. **完全可重放** - 任何 Run 都可以从任意 Step 完整重现
2. **状态隔离** - Checkpoint 包含完整的执行上下文，互不干扰
3. **轻量高效** - 最小化序列化开销，支持增量 Checkpoint
4. **用户友好** - 简单的 API，清晰的概念模型
5. **调试优先** - 为开发者调试体验而设计

### 设计目标

- ✅ **暂停/恢复** - 随时暂停执行，稍后恢复
- ✅ **时间回溯** - 从任意 Step 重新执行
- ✅ **Fork 分支** - 从某个点创建新的执行分支
- ✅ **修改重跑** - 修改输入/配置后重新执行
- ✅ **对比分析** - 对比不同执行路径的结果
- ✅ **调试友好** - 可视化执行流程，单步调试

### 使用场景

1. **调试 Agent 行为** - 从失败的 Step 重新开始
2. **A/B 测试** - Fork 同一个点，测试不同策略
3. **Prompt 优化** - 修改 Prompt 后从某个点重跑
4. **长时间任务** - 暂停后稍后继续
5. **错误恢复** - 从错误前的状态恢复

---

## 核心架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                  Execution Control Layer                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   Pause      │      │   Resume     │      │   Fork    │ │
│  │   Control    │      │   Control    │      │  Control  │ │
│  └──────┬───────┘      └──────┬───────┘      └─────┬─────┘ │
│         │                     │                     │       │
│         └─────────────────────┼─────────────────────┘       │
│                               ▼                             │
│                    ┌────────────────────┐                   │
│                    │ CheckpointManager  │                   │
│                    │  - create()        │                   │
│                    │  - restore()       │                   │
│                    │  - fork()          │                   │
│                    └─────────┬──────────┘                   │
│                              │                              │
│         ┌────────────────────┼────────────────────┐         │
│         ▼                    ▼                    ▼         │
│  ┌─────────────┐      ┌─────────────┐      ┌──────────┐   │
│  │ Checkpoint  │      │  Serializer │      │ Storage  │   │
│  │   Model     │      │  (State)    │      │  Layer   │   │
│  └─────────────┘      └─────────────┘      └──────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │   AgentRunner      │
                    │  (Resume/Fork)     │
                    └────────────────────┘
```

### 数据流

```
Run 执行
  ↓
每个 Step 完成后
  ↓
自动创建 Checkpoint (可选)
  ↓
序列化状态
  ↓
持久化到 Repository
  ↓
用户触发恢复/Fork
  ↓
加载 Checkpoint
  ↓
反序列化状态
  ↓
重建执行上下文
  ↓
继续/重新执行
```

---

## Checkpoint 设计

### 1. Checkpoint 模型

```python
# agio/execution/checkpoint.py

from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field
from typing import Any
from agio.domain.messages import Message
from agio.domain.run import RunStatus
from agio.domain.metrics import AgentRunMetrics

class ExecutionCheckpoint(BaseModel):
    """
    执行检查点 - 包含完整恢复所需的状态
    
    设计原则：
    1. 自包含 - 包含所有恢复所需的信息
    2. 不可变 - 创建后不可修改
    3. 可序列化 - 支持 JSON 序列化
    """
    
    # 基本信息
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str = Field(description="所属 Run ID")
    step_num: int = Field(description="Step 编号")
    created_at: datetime = Field(default_factory=datetime.now)
    
    # 执行状态
    status: RunStatus = Field(description="Run 状态")
    
    # 消息上下文（核心）
    messages: list[Message] = Field(
        description="当前消息历史（完整对话上下文）"
    )
    
    # Metrics 快照
    metrics: AgentRunMetrics = Field(
        default_factory=AgentRunMetrics,
        description="当前 Metrics"
    )
    
    # Agent 配置快照
    agent_config: dict[str, Any] = Field(
        description="Agent 配置快照（用于重现）"
    )
    
    # 可选：用户修改
    user_modifications: dict[str, Any] | None = Field(
        default=None,
        description="用户修改（用于 Fork）"
    )
    
    # 元数据
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="额外元数据"
    )
    
    # 标签（用于分类和搜索）
    tags: list[str] = Field(
        default_factory=list,
        description="标签"
    )
    
    # 描述
    description: str | None = Field(
        default=None,
        description="Checkpoint 描述"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "ckpt_123",
                "run_id": "run_456",
                "step_num": 2,
                "status": "running",
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi!"}
                ],
                "description": "Before tool call"
            }
        }


class CheckpointMetadata(BaseModel):
    """Checkpoint 元数据（用于列表展示）"""
    
    id: str
    run_id: str
    step_num: int
    created_at: datetime
    status: RunStatus
    description: str | None
    tags: list[str]
    
    # 统计信息
    message_count: int
    total_tokens: int
    
    # 是否有用户修改
    has_modifications: bool = False
```

### 2. Checkpoint 策略

```python
# agio/execution/checkpoint_policy.py

from enum import Enum
from typing import Callable
from .checkpoint import ExecutionCheckpoint

class CheckpointStrategy(str, Enum):
    """Checkpoint 创建策略"""
    
    MANUAL = "manual"              # 手动创建
    EVERY_STEP = "every_step"      # 每步自动创建
    ON_TOOL_CALL = "on_tool_call"  # Tool 调用前创建
    ON_ERROR = "on_error"          # 错误时创建
    CUSTOM = "custom"              # 自定义策略


class CheckpointPolicy:
    """
    Checkpoint 策略管理器
    
    决定何时自动创建 Checkpoint
    """
    
    def __init__(self, strategy: CheckpointStrategy = CheckpointStrategy.MANUAL):
        self.strategy = strategy
        self._custom_predicate: Callable | None = None
    
    def set_custom_predicate(self, predicate: Callable[[dict], bool]) -> None:
        """设置自定义判断函数"""
        self.strategy = CheckpointStrategy.CUSTOM
        self._custom_predicate = predicate
    
    def should_create_checkpoint(self, context: dict) -> bool:
        """判断是否应该创建 Checkpoint"""
        
        if self.strategy == CheckpointStrategy.MANUAL:
            return False
        
        elif self.strategy == CheckpointStrategy.EVERY_STEP:
            return True
        
        elif self.strategy == CheckpointStrategy.ON_TOOL_CALL:
            return context.get("has_tool_calls", False)
        
        elif self.strategy == CheckpointStrategy.ON_ERROR:
            return context.get("has_error", False)
        
        elif self.strategy == CheckpointStrategy.CUSTOM:
            if self._custom_predicate:
                return self._custom_predicate(context)
            return False
        
        return False
```

---

## 状态序列化

### 1. 状态序列化器

```python
# agio/execution/serializer.py

from typing import Any
import json
from datetime import datetime
from pydantic import BaseModel
from agio.domain.messages import Message

class StateSerializer:
    """
    状态序列化器
    
    职责：
    1. 将 Python 对象序列化为 JSON
    2. 处理特殊类型（datetime, Pydantic 模型等）
    3. 压缩大型数据
    """
    
    @staticmethod
    def serialize(obj: Any) -> str:
        """序列化对象为 JSON 字符串"""
        return json.dumps(
            obj,
            default=StateSerializer._json_encoder,
            ensure_ascii=False,
            indent=None  # 紧凑格式
        )
    
    @staticmethod
    def deserialize(data: str, target_type: type = dict) -> Any:
        """反序列化 JSON 字符串"""
        obj = json.loads(data)
        
        # 如果目标类型是 Pydantic 模型，使用 model_validate
        if isinstance(target_type, type) and issubclass(target_type, BaseModel):
            return target_type.model_validate(obj)
        
        return obj
    
    @staticmethod
    def _json_encoder(obj: Any) -> Any:
        """自定义 JSON 编码器"""
        
        # Pydantic 模型
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode='json')
        
        # datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        # 其他类型
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class MessageSerializer:
    """
    消息序列化器
    
    专门处理 Message 对象的序列化
    """
    
    @staticmethod
    def serialize_messages(messages: list[Message]) -> list[dict]:
        """序列化消息列表"""
        return [
            msg.model_dump(mode='json', exclude_none=True)
            for msg in messages
        ]
    
    @staticmethod
    def deserialize_messages(data: list[dict]) -> list[Message]:
        """反序列化消息列表"""
        from agio.domain.messages import (
            UserMessage,
            AssistantMessage,
            SystemMessage,
            ToolMessage
        )
        
        messages = []
        for msg_dict in data:
            role = msg_dict.get('role')
            
            if role == 'user':
                messages.append(UserMessage(**msg_dict))
            elif role == 'assistant':
                messages.append(AssistantMessage(**msg_dict))
            elif role == 'system':
                messages.append(SystemMessage(**msg_dict))
            elif role == 'tool':
                messages.append(ToolMessage(**msg_dict))
            else:
                raise ValueError(f"Unknown message role: {role}")
        
        return messages
```

### 2. 增量 Checkpoint

```python
# agio/execution/incremental.py

from typing import Any
from .checkpoint import ExecutionCheckpoint

class IncrementalCheckpoint:
    """
    增量 Checkpoint
    
    只存储与上一个 Checkpoint 的差异，节省存储空间
    """
    
    def __init__(self, base_checkpoint: ExecutionCheckpoint):
        self.base_checkpoint = base_checkpoint
        self.deltas: list[dict] = []
    
    def add_delta(self, delta: dict) -> None:
        """添加增量变更"""
        self.deltas.append(delta)
    
    def reconstruct(self) -> ExecutionCheckpoint:
        """重建完整 Checkpoint"""
        # 从基础 Checkpoint 开始
        state = self.base_checkpoint.model_dump()
        
        # 应用所有增量变更
        for delta in self.deltas:
            self._apply_delta(state, delta)
        
        return ExecutionCheckpoint(**state)
    
    @staticmethod
    def _apply_delta(state: dict, delta: dict) -> None:
        """应用增量变更"""
        for key, value in delta.items():
            if key == "messages" and isinstance(value, list):
                # 消息是追加的
                state["messages"].extend(value)
            else:
                # 其他字段是覆盖的
                state[key] = value
```

---

## 恢复机制

### 1. Checkpoint 管理器

```python
# agio/execution/checkpoint_manager.py

from typing import Optional
from datetime import datetime
from .checkpoint import ExecutionCheckpoint, CheckpointMetadata
from .checkpoint_policy import CheckpointPolicy, CheckpointStrategy
from agio.db.repository import AgentRunRepository

class CheckpointManager:
    """
    Checkpoint 管理器
    
    职责：
    1. 创建 Checkpoint
    2. 存储和加载 Checkpoint
    3. 列出和搜索 Checkpoint
    4. 管理 Checkpoint 生命周期
    """
    
    def __init__(
        self,
        repository: AgentRunRepository,
        policy: CheckpointPolicy | None = None
    ):
        self.repository = repository
        self.policy = policy or CheckpointPolicy(CheckpointStrategy.MANUAL)
    
    async def create_checkpoint(
        self,
        run_id: str,
        step_num: int,
        messages: list,
        metrics: dict,
        agent_config: dict,
        description: str | None = None,
        tags: list[str] | None = None
    ) -> ExecutionCheckpoint:
        """
        创建 Checkpoint
        
        Args:
            run_id: Run ID
            step_num: Step 编号
            messages: 消息历史
            metrics: Metrics 快照
            agent_config: Agent 配置
            description: 描述
            tags: 标签
        
        Returns:
            ExecutionCheckpoint
        """
        from agio.domain.run import RunStatus
        from agio.domain.metrics import AgentRunMetrics
        
        checkpoint = ExecutionCheckpoint(
            run_id=run_id,
            step_num=step_num,
            status=RunStatus.RUNNING,
            messages=messages,
            metrics=AgentRunMetrics(**metrics) if isinstance(metrics, dict) else metrics,
            agent_config=agent_config,
            description=description,
            tags=tags or []
        )
        
        # 持久化
        await self.repository.save_checkpoint(checkpoint)
        
        return checkpoint
    
    async def get_checkpoint(self, checkpoint_id: str) -> Optional[ExecutionCheckpoint]:
        """获取 Checkpoint"""
        return await self.repository.get_checkpoint(checkpoint_id)
    
    async def list_checkpoints(
        self,
        run_id: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
        offset: int = 0
    ) -> list[CheckpointMetadata]:
        """
        列出 Checkpoints
        
        Args:
            run_id: 过滤 Run ID
            tags: 过滤标签
            limit: 限制数量
            offset: 偏移量
        
        Returns:
            Checkpoint 元数据列表
        """
        checkpoints = await self.repository.list_checkpoints(
            run_id=run_id,
            tags=tags,
            limit=limit,
            offset=offset
        )
        
        # 转换为元数据
        metadata_list = []
        for ckpt in checkpoints:
            metadata = CheckpointMetadata(
                id=ckpt.id,
                run_id=ckpt.run_id,
                step_num=ckpt.step_num,
                created_at=ckpt.created_at,
                status=ckpt.status,
                description=ckpt.description,
                tags=ckpt.tags,
                message_count=len(ckpt.messages),
                total_tokens=ckpt.metrics.total_tokens,
                has_modifications=ckpt.user_modifications is not None
            )
            metadata_list.append(metadata)
        
        return metadata_list
    
    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """删除 Checkpoint"""
        return await self.repository.delete_checkpoint(checkpoint_id)
    
    async def should_create_auto_checkpoint(self, context: dict) -> bool:
        """判断是否应该自动创建 Checkpoint"""
        return self.policy.should_create_checkpoint(context)
```

### 2. 恢复执行

```python
# agio/runners/resume.py

from typing import AsyncIterator
from agio.execution.checkpoint import ExecutionCheckpoint
from agio.protocol.events import AgentEvent
from agio.domain.run import AgentRun, RunStatus
from agio.execution.agent_executor import AgentExecutor, ExecutorConfig

class ResumeRunner:
    """
    恢复执行器
    
    从 Checkpoint 恢复执行
    """
    
    def __init__(self, agent, hooks, repository):
        self.agent = agent
        self.hooks = hooks
        self.repository = repository
    
    async def resume_from_checkpoint(
        self,
        checkpoint: ExecutionCheckpoint,
        new_run_id: str | None = None
    ) -> AsyncIterator[AgentEvent]:
        """
        从 Checkpoint 恢复执行
        
        Args:
            checkpoint: Checkpoint 对象
            new_run_id: 新 Run ID（如果为 None，继续原 Run）
        
        Yields:
            AgentEvent
        """
        from agio.runners.state_tracker import RunStateTracker
        from agio.protocol.events import create_run_started_event
        import time
        
        # 决定 Run ID
        run_id = new_run_id or checkpoint.run_id
        is_new_run = new_run_id is not None
        
        # 创建或加载 Run
        if is_new_run:
            # 创建新 Run
            run = AgentRun(
                id=run_id,
                agent_id=self.agent.id,
                input_query=f"Resumed from checkpoint {checkpoint.id}",
                status=RunStatus.RUNNING
            )
            run.metrics.start_time = time.time()
            
            # 发送 Run 开始事件
            yield create_run_started_event(
                run_id=run_id,
                query=f"Resumed from step {checkpoint.step_num}"
            )
        else:
            # 加载原 Run
            run = await self.repository.get_run(checkpoint.run_id)
            if not run:
                raise ValueError(f"Run {checkpoint.run_id} not found")
            
            run.status = RunStatus.RUNNING
        
        # 重建消息上下文
        messages = checkpoint.messages
        
        # 应用用户修改（如果有）
        if checkpoint.user_modifications:
            messages = self._apply_modifications(
                messages,
                checkpoint.user_modifications
            )
        
        # 创建 Executor
        executor = AgentExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=ExecutorConfig(
                max_steps=10,  # 可配置
                start_step=checkpoint.step_num + 1  # 从下一步开始
            )
        )
        
        # 状态追踪器
        state = RunStateTracker(run)
        
        # 执行
        async for event in executor.execute(messages, run_id=run_id):
            state.update(event)
            yield event
        
        # 完成
        run.status = RunStatus.COMPLETED
        run.response_content = state.get_full_response()
        run.metrics.end_time = time.time()
        
        # 保存
        await self.repository.save_run(run)
    
    def _apply_modifications(
        self,
        messages: list,
        modifications: dict
    ) -> list:
        """应用用户修改"""
        
        # 修改最后一条用户消息
        if "modified_query" in modifications:
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].role == "user":
                    messages[i].content = modifications["modified_query"]
                    break
        
        # 修改特定消息
        if "modified_messages" in modifications:
            messages = modifications["modified_messages"]
        
        return messages
```

---

## Fork 机制

### 1. Fork 管理器

```python
# agio/execution/fork.py

from typing import AsyncIterator, Optional
from uuid import uuid4
from .checkpoint import ExecutionCheckpoint
from agio.protocol.events import AgentEvent

class ForkManager:
    """
    Fork 管理器
    
    从 Checkpoint 创建新的执行分支
    """
    
    def __init__(self, checkpoint_manager, resume_runner):
        self.checkpoint_manager = checkpoint_manager
        self.resume_runner = resume_runner
    
    async def fork_from_checkpoint(
        self,
        checkpoint_id: str,
        modifications: dict | None = None,
        description: str | None = None
    ) -> tuple[str, AsyncIterator[AgentEvent]]:
        """
        从 Checkpoint Fork 新分支
        
        Args:
            checkpoint_id: Checkpoint ID
            modifications: 用户修改
            description: Fork 描述
        
        Returns:
            (new_run_id, event_stream)
        """
        # 加载 Checkpoint
        checkpoint = await self.checkpoint_manager.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")
        
        # 应用修改
        if modifications:
            checkpoint.user_modifications = modifications
        
        # 生成新 Run ID
        new_run_id = str(uuid4())
        
        # 创建 Fork Checkpoint（记录分支关系）
        fork_checkpoint = await self.checkpoint_manager.create_checkpoint(
            run_id=new_run_id,
            step_num=0,
            messages=checkpoint.messages,
            metrics=checkpoint.metrics.model_dump(),
            agent_config=checkpoint.agent_config,
            description=description or f"Forked from {checkpoint.id}",
            tags=["fork", f"parent:{checkpoint.run_id}"]
        )
        
        # 恢复执行
        event_stream = self.resume_runner.resume_from_checkpoint(
            checkpoint,
            new_run_id=new_run_id
        )
        
        return new_run_id, event_stream
    
    async def compare_forks(
        self,
        run_id_1: str,
        run_id_2: str
    ) -> dict:
        """
        对比两个 Fork 的结果
        
        Args:
            run_id_1: Run ID 1
            run_id_2: Run ID 2
        
        Returns:
            对比结果
        """
        from agio.db.repository import AgentRunRepository
        
        # 加载两个 Runs
        run1 = await self.checkpoint_manager.repository.get_run(run_id_1)
        run2 = await self.checkpoint_manager.repository.get_run(run_id_2)
        
        if not run1 or not run2:
            raise ValueError("One or both runs not found")
        
        # 对比
        comparison = {
            "run_1": {
                "id": run1.id,
                "status": run1.status,
                "response": run1.response_content,
                "metrics": run1.metrics.model_dump()
            },
            "run_2": {
                "id": run2.id,
                "status": run2.status,
                "response": run2.response_content,
                "metrics": run2.metrics.model_dump()
            },
            "differences": {
                "response_diff": run1.response_content != run2.response_content,
                "token_diff": run1.metrics.total_tokens - run2.metrics.total_tokens,
                "duration_diff": run1.metrics.duration - run2.metrics.duration
            }
        }
        
        return comparison
```

---

## 执行控制

### 1. 执行控制器

```python
# agio/execution/control.py

import asyncio
from enum import Enum
from typing import Optional

class ExecutionState(str, Enum):
    """执行状态"""
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionController:
    """
    执行控制器
    
    控制 Run 的执行（暂停、恢复、取消）
    """
    
    def __init__(self):
        self._states: dict[str, ExecutionState] = {}
        self._pause_events: dict[str, asyncio.Event] = {}
    
    def start_run(self, run_id: str) -> None:
        """开始 Run"""
        self._states[run_id] = ExecutionState.RUNNING
        self._pause_events[run_id] = asyncio.Event()
        self._pause_events[run_id].set()  # 初始为运行状态
    
    def pause_run(self, run_id: str) -> bool:
        """暂停 Run"""
        if run_id not in self._states:
            return False
        
        if self._states[run_id] != ExecutionState.RUNNING:
            return False
        
        self._states[run_id] = ExecutionState.PAUSED
        self._pause_events[run_id].clear()  # 清除事件，阻塞执行
        return True
    
    def resume_run(self, run_id: str) -> bool:
        """恢复 Run"""
        if run_id not in self._states:
            return False
        
        if self._states[run_id] != ExecutionState.PAUSED:
            return False
        
        self._states[run_id] = ExecutionState.RUNNING
        self._pause_events[run_id].set()  # 设置事件，继续执行
        return True
    
    def cancel_run(self, run_id: str) -> bool:
        """取消 Run"""
        if run_id not in self._states:
            return False
        
        self._states[run_id] = ExecutionState.CANCELLED
        self._pause_events[run_id].set()  # 设置事件，让执行继续以便检查取消状态
        return True
    
    async def check_pause(self, run_id: str) -> None:
        """检查是否暂停（在执行循环中调用）"""
        if run_id in self._pause_events:
            await self._pause_events[run_id].wait()
    
    def is_cancelled(self, run_id: str) -> bool:
        """检查是否已取消"""
        return self._states.get(run_id) == ExecutionState.CANCELLED
    
    def get_state(self, run_id: str) -> Optional[ExecutionState]:
        """获取执行状态"""
        return self._states.get(run_id)
    
    def complete_run(self, run_id: str) -> None:
        """标记 Run 完成"""
        if run_id in self._states:
            self._states[run_id] = ExecutionState.COMPLETED
    
    def fail_run(self, run_id: str) -> None:
        """标记 Run 失败"""
        if run_id in self._states:
            self._states[run_id] = ExecutionState.FAILED


# 全局执行控制器
_global_controller = ExecutionController()

def get_execution_controller() -> ExecutionController:
    """获取全局执行控制器"""
    return _global_controller
```

### 2. 集成到 AgentRunner

```python
# 修改 agio/runners/base.py

class AgentRunner:
    def __init__(self, agent, hooks, config=None, repository=None):
        # ... 现有代码 ...
        self.execution_controller = get_execution_controller()
        self.checkpoint_manager = CheckpointManager(repository) if repository else None
    
    async def run_stream(
        self, 
        session: AgentSession, 
        query: str
    ) -> AsyncIterator[AgentEvent]:
        # ... 创建 Run ...
        
        # 注册到执行控制器
        self.execution_controller.start_run(run.id)
        
        try:
            # 执行循环
            async for event in executor.execute(dict_messages, run_id=run.id):
                # 检查暂停
                await self.execution_controller.check_pause(run.id)
                
                # 检查取消
                if self.execution_controller.is_cancelled(run.id):
                    run.status = RunStatus.CANCELLED
                    break
                
                # 更新状态
                state.update(event)
                
                # 自动创建 Checkpoint（如果策略允许）
                if self.checkpoint_manager:
                    context = {
                        "step_num": state.current_step,
                        "has_tool_calls": event.type == EventType.TOOL_CALL_STARTED
                    }
                    if await self.checkpoint_manager.should_create_auto_checkpoint(context):
                        await self.checkpoint_manager.create_checkpoint(
                            run_id=run.id,
                            step_num=state.current_step,
                            messages=dict_messages,
                            metrics=state.build_metrics().model_dump(),
                            agent_config=self._get_agent_config()
                        )
                
                yield await self._emit_and_store(event)
            
            # 完成
            self.execution_controller.complete_run(run.id)
            
        except Exception as e:
            self.execution_controller.fail_run(run.id)
            raise e
```

---

## 时光旅行调试

### 1. 时光旅行器

```python
# agio/execution/time_travel.py

from typing import AsyncIterator, Optional
from .checkpoint import ExecutionCheckpoint
from agio.protocol.events import AgentEvent

class TimeTraveler:
    """
    时光旅行器
    
    提供时光旅行调试能力
    """
    
    def __init__(self, checkpoint_manager, resume_runner):
        self.checkpoint_manager = checkpoint_manager
        self.resume_runner = resume_runner
    
    async def go_to_step(
        self,
        run_id: str,
        target_step: int
    ) -> tuple[ExecutionCheckpoint, AsyncIterator[AgentEvent]]:
        """
        跳转到指定 Step
        
        Args:
            run_id: Run ID
            target_step: 目标 Step
        
        Returns:
            (checkpoint, event_stream)
        """
        # 查找最接近的 Checkpoint
        checkpoints = await self.checkpoint_manager.list_checkpoints(
            run_id=run_id,
            limit=100
        )
        
        # 找到 <= target_step 的最大 Checkpoint
        closest_checkpoint = None
        for ckpt_meta in checkpoints:
            if ckpt_meta.step_num <= target_step:
                if not closest_checkpoint or ckpt_meta.step_num > closest_checkpoint.step_num:
                    closest_checkpoint = ckpt_meta
        
        if not closest_checkpoint:
            raise ValueError(f"No checkpoint found before step {target_step}")
        
        # 加载完整 Checkpoint
        checkpoint = await self.checkpoint_manager.get_checkpoint(closest_checkpoint.id)
        
        # 如果正好是目标 Step，直接返回
        if checkpoint.step_num == target_step:
            return checkpoint, None
        
        # 否则，从 Checkpoint 恢复并执行到目标 Step
        event_stream = self._execute_until_step(checkpoint, target_step)
        
        return checkpoint, event_stream
    
    async def _execute_until_step(
        self,
        checkpoint: ExecutionCheckpoint,
        target_step: int
    ) -> AsyncIterator[AgentEvent]:
        """从 Checkpoint 执行到目标 Step"""
        
        step_count = 0
        async for event in self.resume_runner.resume_from_checkpoint(checkpoint):
            yield event
            
            # 检查是否到达目标 Step
            if event.type == "step_completed":
                step_count += 1
                if checkpoint.step_num + step_count >= target_step:
                    break
    
    async def replay_run(
        self,
        run_id: str,
        from_step: int = 0,
        to_step: int | None = None
    ) -> AsyncIterator[AgentEvent]:
        """
        回放 Run
        
        Args:
            run_id: Run ID
            from_step: 起始 Step
            to_step: 结束 Step（None 表示到最后）
        
        Yields:
            AgentEvent
        """
        # 获取所有事件
        events = await self.checkpoint_manager.repository.get_events(
            run_id=run_id,
            offset=0,
            limit=10000  # 足够大
        )
        
        # 过滤 Step 范围
        for event in events:
            step = event.data.get("step", 0)
            
            if step < from_step:
                continue
            
            if to_step is not None and step > to_step:
                break
            
            yield event
```

### 2. 单步调试器

```python
# agio/execution/debugger.py

from typing import AsyncIterator, Optional
from .checkpoint import ExecutionCheckpoint
from agio.protocol.events import AgentEvent

class StepDebugger:
    """
    单步调试器
    
    支持单步执行、断点等调试功能
    """
    
    def __init__(self, checkpoint_manager, resume_runner):
        self.checkpoint_manager = checkpoint_manager
        self.resume_runner = resume_runner
        self._breakpoints: dict[str, set[int]] = {}  # run_id -> set of step numbers
    
    def set_breakpoint(self, run_id: str, step_num: int) -> None:
        """设置断点"""
        if run_id not in self._breakpoints:
            self._breakpoints[run_id] = set()
        self._breakpoints[run_id].add(step_num)
    
    def remove_breakpoint(self, run_id: str, step_num: int) -> None:
        """移除断点"""
        if run_id in self._breakpoints:
            self._breakpoints[run_id].discard(step_num)
    
    async def step_over(
        self,
        checkpoint: ExecutionCheckpoint
    ) -> tuple[ExecutionCheckpoint, AgentEvent]:
        """
        单步执行（执行一个 Step）
        
        Returns:
            (new_checkpoint, last_event)
        """
        last_event = None
        new_checkpoint = None
        
        # 执行一个 Step
        async for event in self.resume_runner.resume_from_checkpoint(checkpoint):
            last_event = event
            
            # 如果是 Step 完成事件，创建新 Checkpoint 并停止
            if event.type == "step_completed":
                new_checkpoint = await self.checkpoint_manager.create_checkpoint(
                    run_id=checkpoint.run_id,
                    step_num=checkpoint.step_num + 1,
                    messages=event.data.get("messages", []),
                    metrics=event.data.get("metrics", {}),
                    agent_config=checkpoint.agent_config,
                    description=f"Step {checkpoint.step_num + 1}"
                )
                break
        
        return new_checkpoint, last_event
    
    async def continue_until_breakpoint(
        self,
        checkpoint: ExecutionCheckpoint
    ) -> tuple[ExecutionCheckpoint, list[AgentEvent]]:
        """
        继续执行直到断点
        
        Returns:
            (checkpoint_at_breakpoint, events)
        """
        events = []
        current_checkpoint = checkpoint
        
        async for event in self.resume_runner.resume_from_checkpoint(checkpoint):
            events.append(event)
            
            # 检查是否到达断点
            if event.type == "step_completed":
                step_num = event.data.get("step", 0)
                
                if (checkpoint.run_id in self._breakpoints and
                    step_num in self._breakpoints[checkpoint.run_id]):
                    # 到达断点，创建 Checkpoint
                    current_checkpoint = await self.checkpoint_manager.create_checkpoint(
                        run_id=checkpoint.run_id,
                        step_num=step_num,
                        messages=event.data.get("messages", []),
                        metrics=event.data.get("metrics", {}),
                        agent_config=checkpoint.agent_config,
                        description=f"Breakpoint at step {step_num}"
                    )
                    break
        
        return current_checkpoint, events
```

---

## 使用指南

### 快速开始

#### 1. 创建 Checkpoint

```python
from agio import Agent
from agio.execution.checkpoint_manager import CheckpointManager
from agio.db.repository import InMemoryRepository

# 创建 Agent
agent = Agent(model=..., tools=[...])

# 创建 Repository 和 Checkpoint Manager
repository = InMemoryRepository()
checkpoint_manager = CheckpointManager(repository)

# 运行 Agent 并自动创建 Checkpoints
async for event in agent.arun_stream("Hello"):
    print(event)
    
    # 手动创建 Checkpoint
    if event.type == "tool_call_started":
        checkpoint = await checkpoint_manager.create_checkpoint(
            run_id=event.run_id,
            step_num=event.data["step"],
            messages=event.data["messages"],
            metrics=event.data["metrics"],
            agent_config={},
            description="Before tool call"
        )
        print(f"Created checkpoint: {checkpoint.id}")
```

#### 2. 从 Checkpoint 恢复

```python
from agio.runners.resume import ResumeRunner

# 创建恢复执行器
resume_runner = ResumeRunner(agent, hooks=[], repository=repository)

# 加载 Checkpoint
checkpoint = await checkpoint_manager.get_checkpoint(checkpoint_id)

# 恢复执行
async for event in resume_runner.resume_from_checkpoint(checkpoint):
    print(event)
```

#### 3. Fork 新分支

```python
from agio.execution.fork import ForkManager

# 创建 Fork Manager
fork_manager = ForkManager(checkpoint_manager, resume_runner)

# Fork 并修改
new_run_id, event_stream = await fork_manager.fork_from_checkpoint(
    checkpoint_id=checkpoint.id,
    modifications={
        "modified_query": "New query here"
    },
    description="Testing different prompt"
)

# 执行新分支
async for event in event_stream:
    print(event)
```

#### 4. 暂停和恢复

```python
from agio.execution.control import get_execution_controller

controller = get_execution_controller()

# 开始执行
async def run_agent():
    async for event in agent.arun_stream("Long task"):
        print(event)

# 在另一个协程中暂停
await asyncio.sleep(5)
controller.pause_run(run_id)

# 稍后恢复
await asyncio.sleep(10)
controller.resume_run(run_id)
```

### 常见场景

#### 场景 1: 调试失败的 Run

```python
# 1. 找到失败的 Run
run = await repository.get_run(failed_run_id)

# 2. 列出所有 Checkpoints
checkpoints = await checkpoint_manager.list_checkpoints(run_id=failed_run_id)

# 3. 从失败前的 Checkpoint 恢复
last_checkpoint = checkpoints[-1]
checkpoint = await checkpoint_manager.get_checkpoint(last_checkpoint.id)

# 4. 修改并重新执行
checkpoint.user_modifications = {
    "modified_query": "Fixed query"
}

async for event in resume_runner.resume_from_checkpoint(checkpoint):
    print(event)
```

#### 场景 2: A/B 测试不同 Prompts

```python
# 创建基准 Checkpoint
base_checkpoint = await checkpoint_manager.create_checkpoint(...)

# Fork A: 使用 Prompt A
run_a_id, stream_a = await fork_manager.fork_from_checkpoint(
    checkpoint_id=base_checkpoint.id,
    modifications={"system_prompt": "Prompt A"},
    description="Test Prompt A"
)

# Fork B: 使用 Prompt B
run_b_id, stream_b = await fork_manager.fork_from_checkpoint(
    checkpoint_id=base_checkpoint.id,
    modifications={"system_prompt": "Prompt B"},
    description="Test Prompt B"
)

# 对比结果
comparison = await fork_manager.compare_forks(run_a_id, run_b_id)
print(comparison)
```

#### 场景 3: 时光旅行调试

```python
from agio.execution.time_travel import TimeTraveler

time_traveler = TimeTraveler(checkpoint_manager, resume_runner)

# 跳转到 Step 5
checkpoint, event_stream = await time_traveler.go_to_step(
    run_id=run_id,
    target_step=5
)

# 从 Step 5 重新执行
if event_stream:
    async for event in event_stream:
        print(event)
```

#### 场景 4: 单步调试

```python
from agio.execution.debugger import StepDebugger

debugger = StepDebugger(checkpoint_manager, resume_runner)

# 设置断点
debugger.set_breakpoint(run_id, step_num=3)

# 单步执行
current_checkpoint = initial_checkpoint
while True:
    new_checkpoint, event = await debugger.step_over(current_checkpoint)
    print(f"Step {new_checkpoint.step_num}: {event}")
    
    # 检查是否继续
    user_input = input("Continue? (y/n): ")
    if user_input.lower() != 'y':
        break
    
    current_checkpoint = new_checkpoint
```

---

## 实现路线图

### Week 1: Checkpoint 基础

#### Day 1-2: 数据模型
- [ ] 实现 `ExecutionCheckpoint` 模型
- [ ] 实现 `CheckpointMetadata` 模型
- [ ] 实现 `CheckpointPolicy`
- [ ] 编写单元测试

#### Day 3-4: 序列化
- [ ] 实现 `StateSerializer`
- [ ] 实现 `MessageSerializer`
- [ ] 实现增量 Checkpoint
- [ ] 编写序列化测试

#### Day 5: Checkpoint Manager
- [ ] 实现 `CheckpointManager`
- [ ] 集成到 Repository
- [ ] 实现自动 Checkpoint 策略
- [ ] 编写集成测试

### Week 2: 恢复与 Fork

#### Day 1-2: 恢复机制
- [ ] 实现 `ResumeRunner`
- [ ] 实现状态重建逻辑
- [ ] 实现用户修改应用
- [ ] 编写恢复测试

#### Day 3-4: Fork 机制
- [ ] 实现 `ForkManager`
- [ ] 实现分支创建
- [ ] 实现 Fork 对比
- [ ] 编写 Fork 测试

#### Day 5: 执行控制
- [ ] 实现 `ExecutionController`
- [ ] 集成暂停/恢复到 AgentRunner
- [ ] 实现取消逻辑
- [ ] 编写控制测试

### Week 3: 高级功能

#### Day 1-2: 时光旅行
- [ ] 实现 `TimeTraveler`
- [ ] 实现 Step 跳转
- [ ] 实现 Run 回放
- [ ] 编写时光旅行测试

#### Day 3: 单步调试
- [ ] 实现 `StepDebugger`
- [ ] 实现断点功能
- [ ] 实现单步执行
- [ ] 编写调试器测试

#### Day 4: 集成测试
- [ ] 端到端测试：创建 → 恢复 → Fork
- [ ] 测试暂停/恢复
- [ ] 测试时光旅行
- [ ] 性能测试

#### Day 5: 文档与优化
- [ ] 编写使用文档
- [ ] 性能优化
- [ ] 代码审查
- [ ] 准备发布

---

## 总结

这个执行控制系统设计具备以下特点：

1. **✅ 完全可重放** - 任何 Run 都可以从任意点重现
2. **✅ 灵活控制** - 暂停、恢复、取消、Fork
3. **✅ 时光旅行** - 跳转到任意 Step，单步调试
4. **✅ 开发者友好** - 简单的 API，清晰的概念
5. **✅ 高效存储** - 增量 Checkpoint，最小化开销
6. **✅ 调试优先** - 为调试体验而设计

通过这个系统，开发者可以：
- 🐛 快速定位和修复 Bug
- 🔬 深入理解 Agent 行为
- 🧪 轻松进行 A/B 测试
- ⏱️ 暂停长时间任务
- 🎯 精确控制执行流程

