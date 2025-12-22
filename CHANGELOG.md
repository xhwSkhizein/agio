# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### 🏗️ Configuration System Refactoring - 2025-12-22

**模块化配置系统重构 - 遵循 SOLID & KISS 原则**

#### 新增模块

新增 6 个职责清晰的模块：

- `agio/config/registry.py` - ConfigRegistry: 配置存储和查询
- `agio/config/container.py` - ComponentContainer: 组件实例管理
- `agio/config/dependency.py` - DependencyResolver: 依赖解析和拓扑排序
- `agio/config/builder_registry.py` - BuilderRegistry: 构建器注册表
- `agio/config/hot_reload.py` - HotReloadManager: 热重载管理
- `agio/config/model_provider_registry.py` - ModelProviderRegistry: Provider 注册表

#### 核心改进

| 指标 | 重构前 | 重构后 | 提升 |
|------|--------|--------|------|
| ConfigSystem 行数 | 780 | 480 | **-38%** |
| 模块职责 | 9+ 职责混杂 | 单一协调职责 | **清晰** |
| 拓扑排序 | 2 处重复 | 1 处统一 | **消除重复** |
| 循环依赖 | warning | **fail fast** | **早期发现** |
| Provider 扩展 | 硬编码分支 | 注册表模式 | **OCP** |
| ModelBuilder | 50 行 | 12 行 | **-76%** |

#### 特性

- ✅ **单一职责 (SRP)**: 每个模块职责清晰
- ✅ **开闭原则 (OCP)**: 支持动态注册 Builder 和 Provider
- ✅ **依赖倒置 (DIP)**: 使用 Protocol 定义抽象接口
- ✅ **Fail Fast**: 循环依赖立即抛出异常
- ✅ **线程安全**: 全局单例支持并发访问
- ✅ **热重载**: 配置变更自动级联重建

#### 向后兼容性

- ✅ `list_configs()` / `get_config()` 保持返回 dict 格式
- ✅ 所有现有测试通过 (215 passed)
- ✅ API 层无需改动

#### 扩展示例

```python
# 注册自定义 Provider
from agio.config import get_model_provider_registry

registry = get_model_provider_registry()
registry.register("custom_provider", CustomModelClass)
```

#### 迁移指南

无需迁移，完全向后兼容。新功能可选使用：

```python
# 访问新模块（可选）
config_sys = get_config_system()
registry = config_sys.registry  # ConfigRegistry
container = config_sys.container  # ComponentContainer

# 重置单例（测试用）
from agio.config import reset_config_system
reset_config_system()
```

详见: 
- `configs/README.md` - 配置系统使用指南
- `docs/ARCHITECTURE.md` - 架构设计文档
- `docs/refactor/config-system-refactor.md` - 重构详细方案

---

### 🔧 Domain Model Refactoring - 2025-11-23

**Domain 模型职责分离 - 遵循 SOLID 原则**

- **删除** `Step.to_message_dict()` 方法，保持 Domain 模型纯粹
- **统一** 使用 `StepAdapter.to_llm_message(step)` 进行格式转换
- **更新** 所有调用点（`step_executor.py`, `runner.py`）
- **更新** 测试用例和文档

**影响**:
- ✅ Domain 模型只包含数据和业务查询方法
- ✅ 所有格式转换逻辑集中在 `StepAdapter` 中
- ✅ 符合单一职责原则和适配器模式
- ✅ 易于扩展支持多种 LLM 格式

**迁移指南**:
```python
# 旧方式（已废弃）
message = step.to_message_dict()

# 新方式
from agio.core import StepAdapter
message = StepAdapter.to_llm_message(step)
```

详见: `docs/ARCHITECTURE.md`

---

## [0.4.0] - 2025-11-21 - Major Architecture Refactor

### 🏗️ Breaking Changes

**Architecture Redesign: Three-Layer Separation**

从复杂的双事件系统（ModelEvent + AgentEvent）演进为清晰的三层架构：

```
旧架构 (已废弃):
Agent → AgentRunner → ModelDriver → EventConverter → AgentEvent

新架构 (当前):
Agent → AgentRunner → AgentExecutor → Model
```

**移除的组件**:
- ❌ `ModelDriver` (抽象类) - 替换为 `AgentExecutor`
- ❌ `OpenAIModelDriver` - 逻辑合并到 `AgentExecutor`
- ❌ `EventConverter` - 不再需要，直接生成 `AgentEvent`
- ❌ `ModelEvent` - 统一使用 `AgentEvent`
- ❌ `ModelEventType` - 使用 `EventType`

**新增的组件**:
- ✅ `AgentExecutor` - LLM ↔ Tool 循环执行引擎
- ✅ `ToolCallAccumulator` - 流式 tool calls 累加器
- ✅ `RunStateTracker` - Run 状态追踪器
- ✅ `ExecutorConfig` - Executor 配置

### ✨ Added

#### 核心功能
- **AgentExecutor**: 新的执行引擎，负责完整的 LLM ↔ Tool 循环逻辑
- **ToolCallAccumulator**: 智能累加流式 tool calls，支持增量式工具调用
- **RunStateTracker**: 统一的 Run 状态追踪，简化 metrics 管理
- **StreamChunk**: 标准化的模型输出格式

#### 改进
- **更清晰的职责分离**: 
  - `Agent`: 纯配置容器
  - `AgentRunner`: 编排和生命周期管理
  - `AgentExecutor`: 执行逻辑
  - `Model`: 纯 LLM 接口
- **统一事件流**: 所有组件直接生成 `AgentEvent`，无需转换
- **简化的工具执行**: `ToolExecutor` 独立工具执行逻辑
- **更好的状态管理**: `RunStateTracker` 集中管理状态和 metrics

### 🔧 Changed

#### API 变更
- `Agent.arun()` - 保持不变（向后兼容）
- `Agent.arun_stream()` - 保持不变（向后兼容）
- `AgentRunner.run_stream()` - 内部实现重构，API 兼容

#### 配置变更
- `AgentRunConfig` - 保持不变
- 新增 `ExecutorConfig` - 独立的执行器配置

#### 事件系统
- 统一使用 `AgentEvent`（15种事件类型）
- 移除 `ModelEvent` 及其转换逻辑
- 事件生成点从 `EventConverter` 移到 `AgentExecutor`

### 📝 Documentation

- 清理了 9 个过时的重构文档
- 更新 README 反映新架构
- 添加详细的代码审查报告 (`CODE_REVIEW_REPORT.md`)
- 创建清理脚本 (`cleanup.sh`)

### 🗑️ Removed

**过时文档**:
- `REFACTOR_PROGRESS.md` - 旧架构重构进度
- `review_after_refactor.md` - 旧架构代码审查
- `plans.md` - 旧重构计划
- `refactor.md` - 旧重构文档
- `PROJECT_STATUS.md` - 过时的项目状态

**临时文件**:
- `test_new_arch.py` - 临时测试
- `test_full_arch.py` - 临时测试
- `test_error.txt` - 临时输出
- `test_output.txt` - 临时输出

**废弃代码** (在之前的提交中):
- `agio/core/loop.py` - ModelDriver 接口
- `agio/drivers/openai_driver.py` - OpenAI Driver 实现
- `agio/protocol/converter.py` - EventConverter

### 📊 Metrics

**代码简化**:
- 核心文件数: 50+ 个
- 核心代码行数: ~6000 行
- 事件类型: 15 种
- 测试覆盖: 基础单元测试完整

**架构改进**:
- 层级深度: 从 5 层减少到 4 层
- 事件转换: 移除转换层，直接生成
- 职责明确度: 每个组件单一职责

### 🔄 Migration Guide

#### 从旧架构迁移

如果你的代码只使用了公共 API (`Agent.arun()`, `Agent.arun_stream()`)，**无需任何修改**。

如果你自定义了内部组件：

**1. 自定义 ModelDriver → 需要重写为 Model**

```python
# 旧代码 (不再支持)
class CustomDriver(ModelDriver):
    async def run(self, messages, tools, config):
        # ...

# 新代码
class CustomModel(Model):
    async def arun_stream(self, messages, tools):
        # 返回 StreamChunk
        yield StreamChunk(content="...", tool_calls=[...], usage={...})
```

**2. 处理 ModelEvent → 使用 AgentEvent**

```python
# 旧代码 (不再支持)
from agio.core.events import ModelEvent, ModelEventType

if event.type == ModelEventType.TEXT_DELTA:
    # ...

# 新代码
from agio.protocol.events import AgentEvent, EventType

if event.type == EventType.TEXT_DELTA:
    # ...
```

**3. 自定义 EventConverter → 不再需要**

事件现在直接由 `AgentExecutor` 生成，无需转换层。

### 🚀 Performance

- **事件处理**: 减少一层转换，性能提升 ~10%
- **内存使用**: 移除重复的事件对象，内存减少 ~15%
- **代码复杂度**: 圈复杂度降低，可维护性大幅提升

---

## [0.3.0] - 2025-11-20 - Event Streaming & History

### Added
- 统一事件流协议 (`AgentEvent`)
- 事件持久化 (`SessionStore`)
- 历史回放 API (`get_run_history`, `list_runs`)
- Metrics 收集和快照
- 错误分类和恢复机制

### Changed
- 新增 `Agent.arun_stream()` API
- 增强可观测性

---

## [0.2.0] - 2025-11-19 - ModelDriver Architecture

### Added
- ModelDriver 抽象层
- ToolExecutor 独立执行器
- ContextBuilder 上下文构建器
- AgentRunConfig 统一配置

### Changed
- AgentRunner 职责精简
- 循环逻辑下沉至 Driver 层

---

## [0.1.0] - Initial Release

### Added
- 基础 Agent 实现
- OpenAI 模型支持
- 工具系统
- 记忆系统
- 知识库 (RAG)

---

## Versioning Strategy

我们遵循语义化版本号 (Semantic Versioning):

- **主版本号 (Major)**: 不兼容的 API 变更
- **次版本号 (Minor)**: 向后兼容的功能新增
- **修订号 (Patch)**: 向后兼容的问题修正

---

## Links

- [GitHub Repository](https://github.com/yourusername/agio)
- [Documentation](https://agio.dev/docs)
- [Issue Tracker](https://github.com/yourusername/agio/issues)
- [Architecture](docs/ARCHITECTURE.md)
