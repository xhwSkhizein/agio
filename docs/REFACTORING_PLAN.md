# Agio 重构方案

## 1. 现状分析与评估

### 1.1 当前架构优势

项目已有的架构有几个核心优势值得保留：

1. **Step-based 架构** - `Step` 直接映射 LLM Message，零转换开销
2. **StepEvent 协议** - 清晰的流式事件协议，适合 SSE 传输
3. **分层执行** - `Agent` → `StepRunner` → `StepExecutor` 职责分明
4. **ConfigSystem 基础** - 已有组件生命周期管理和热重载雏形

### 1.2 Review 意见评估

| Review 意见 | 评估 | 处理方式 |
|------------|------|----------|
| execution 包职责过重 | **部分认同** | 当前职责划分已合理，只需小幅调整 |
| Step 模型过度泛化 | **不认同** | 统一模型恰好简化 LLM 交互，保持现状 |
| 双重 API (arun/arun_stream) | **认同** | 删除 `arun`，统一为 `arun_stream` |
| 配置系统过度抽象 | **部分认同** | 保留依赖注入能力，简化使用方式 |
| 数据流转不清晰 | **认同** | 需要明确文档和简化路径 |

### 1.3 核心需求映射

| 用户需求 | 实现要点 |
|---------|---------|
| 配置系统创建所有依赖，支持热重载 | 增加 MongoDB 配置源，完善热重载机制 |
| 保持 Stream 协议，简化 Agent 实现 | 统一执行接口，删除冗余 API |
| 多 Agent 协作像单 Agent 一样交互 | 抽象 `Runnable` 协议，统一输出流 |

---

## 2. 重构分阶段计划

### Phase 1: 清理与简化 ✂️

**目标**: 删除冗余代码，简化 Agent 类

**变更内容**:
- 删除 `Agent.arun()` 方法，只保留 `arun_stream()`
- 重命名 `arun_stream` → `run` (更简洁的 API)
- 清理相关的遗留代码和注释

**影响范围**: 小，仅 Agent 类和调用点

---

### Phase 2: 统一执行协议 🔌

**目标**: 为多 Agent 协作准备统一的执行接口

**核心设计**:
```python
from typing import Protocol, AsyncIterator
from agio.core import StepEvent

class Runnable(Protocol):
    """统一的可执行协议 - 单 Agent 和多 Agent 组合都实现此协议"""
    
    async def run(
        self,
        query: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        """执行并返回 StepEvent 流"""
        ...
```

**重构**:
- `Agent` 实现 `Runnable` 协议
- 新增 `agio/core/protocols.py` 定义协议
- 为后续多 Agent 编排做准备

---

### Phase 3: 配置系统增强 ⚙️

**目标**: 支持多配置源和完善热重载

**变更内容**:

1. **配置源抽象**
```python
class ConfigSource(Protocol):
    """配置源协议"""
    async def load_all(self) -> dict[tuple[ComponentType, str], dict]: ...
    async def watch(self, callback: Callable) -> None: ...
```

2. **实现多配置源**
- `YamlConfigSource` - 文件系统 YAML (已有)
- `MongoConfigSource` - MongoDB 配置集合 (新增)

3. **热重载完善**
- 配置变更监听
- 依赖组件自动重建
- 资源优雅清理

---

### Phase 4: 多 Agent 协作框架 🤖🤖

**目标**: 支持多种协作模式，统一输出 StepEvent 流

**协作模式**:

1. **Sequential (顺序执行)**
```python
pipeline = Sequential([agent_a, agent_b, agent_c])
async for event in pipeline.run(query):
    yield event  # 所有 agent 的事件按序输出
```

2. **Parallel (并行执行)**
```python
parallel = Parallel([research_agent, code_agent])
async for event in parallel.run(query):
    yield event  # 并行执行，事件合并输出
```

3. **Graph (图结构)**
```python
graph = Graph()
graph.add_node("research", research_agent)
graph.add_node("code", code_agent)
graph.add_edge("research", "code", condition=lambda x: "code" in x)
```

4. **控制流 (代码控制)**
```python
class CustomWorkflow(Runnable):
    async def run(self, query: str, **kwargs) -> AsyncIterator[StepEvent]:
        # 自定义 for/while/if-else 逻辑
        for i in range(3):
            async for event in self.agent.run(query):
                yield event
```

---

## 3. 关键设计决策

### 3.1 保持 StepEvent 协议不变

前端已基于 `StepEvent` 协议实现，重构期间 **不修改** 此协议：

```python
class StepEvent(BaseModel):
    type: StepEventType      # step_delta, step_completed, run_started, ...
    run_id: str
    step_id: str | None
    delta: StepDelta | None   # 增量内容
    snapshot: Step | None     # 完整快照
    data: dict | None         # 运行级别数据
```

### 3.2 多 Agent 输出合并策略

多 Agent 协作时，每个 Agent 产生的事件流需要合并：

```
Agent A Events: [run_started_a, delta_a1, delta_a2, step_completed_a, run_completed_a]
Agent B Events: [run_started_b, delta_b1, step_completed_b, run_completed_b]

合并后 (Sequential):
[run_started_workflow, 
 run_started_a, delta_a1, ..., run_completed_a,
 run_started_b, delta_b1, ..., run_completed_b,
 run_completed_workflow]
```

**关键**: 前端只需要处理 StepEvent，无需知道是单 Agent 还是多 Agent。

### 3.3 配置与实例分离

```
configs/agents/code_assistant.yaml  →  ConfigSystem  →  Agent 实例
                                           ↓
MongoDB: agents collection          →  ConfigSystem  →  Agent 实例
```

ConfigSystem 作为唯一的组件工厂，不直接暴露构建细节。

---

## 4. 实施顺序

```
Week 1: Phase 1 - 清理与简化
  ├── 删除 Agent.arun()
  ├── 重命名 arun_stream → run
  └── 更新所有调用点

Week 2: Phase 2 - 统一执行协议
  ├── 定义 Runnable 协议
  ├── Agent 实现协议
  └── 编写协议测试

Week 3-4: Phase 3 - 配置系统增强
  ├── ConfigSource 抽象
  ├── MongoConfigSource 实现
  └── 热重载完善

Week 5-6: Phase 4 - 多 Agent 框架
  ├── Sequential 实现
  ├── Parallel 实现
  ├── Graph 基础实现
  └── 控制流支持
```

---

## 5. 文件变更预览

### 新增文件
```
agio/core/protocols.py          # Runnable 协议定义
agio/config/sources/            # 配置源
  ├── base.py                   # ConfigSource 协议
  ├── yaml_source.py            # YAML 文件源
  └── mongo_source.py           # MongoDB 源
agio/orchestration/             # 多 Agent 编排
  ├── __init__.py
  ├── base.py                   # 基础编排类
  ├── sequential.py             # 顺序执行
  ├── parallel.py               # 并行执行
  └── graph.py                  # 图结构执行
```

### 修改文件
```
agio/agent/base.py              # 删除 arun, 重命名 arun_stream
agio/config/system.py           # 支持多配置源
agio/api/routes/chat.py         # 更新 API 调用
```

### 删除文件
```
无
```

---

下一步：阅读 [Phase 1 详细设计](./REFACTORING_PHASE1.md)
