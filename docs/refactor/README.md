# Agent/Workflow 统一抽象重构方案

> **设计哲学**：使用**组合模式 (Composite Pattern)**，将 Agent 和 Workflow 统一为 `Runnable` 的两种实现：
> - **Agent** = **原子节点 (Leaf)**：直接执行，调用 LLM/Tool
> - **Workflow** = **组合节点 (Composite)**：调度子 Runnable

---

## 文档导航

本文档已拆分为多个文件，便于阅读和维护：

1. **[01-问题分析.md](./01-问题分析.md)** - 现状问题总结
   - 执行层抽象不统一
   - 依赖注入方式不一致
   - 模块职责边界混乱
   - 状态管理机制分裂

2. **[02-设计目标.md](./02-设计目标.md)** - 重构目标和原则
   - 核心原则
   - 目标架构
   - 预期收益

3. **[03-设计方案.md](./03-设计方案.md)** - 统一抽象设计
   - 核心洞察与 Runnable 协议
   - RunnableExecutor 设计
   - Agent/Workflow 实现
   - 模块结构重组
   - **核心概念**：Session、Run、Step 关系
   - **Workflow Step 处理**：Pipeline/Parallel/Loop 的 seq 策略
   - **Fork/Resume 设计**：各 Workflow 类型的行为定义
   - **Metrics 分层聚合**：含 merge(mode=sequential|parallel) 方法

4. **[04-执行计划.md](./04-执行计划.md)** - 完整执行计划
   - Phase 1-13 详细步骤
   - 每个 Phase 的具体操作
   - 验证测试要求

5. **[05-风险评估.md](./05-风险评估.md)** - 风险评估与缓解
   - 风险矩阵
   - 回滚策略
   - 渐进式迁移策略

6. **[06-验收标准.md](./06-验收标准.md)** - 验收标准
   - 功能验收
   - 架构验收
   - 代码质量验收

---

## 快速开始

1. **了解问题**：阅读 [01-问题分析.md](./01-问题分析.md)
2. **理解目标**：阅读 [02-设计目标.md](./02-设计目标.md)
3. **学习方案**：阅读 [03-设计方案.md](./03-设计方案.md)
4. **执行重构**：按照 [04-执行计划.md](./04-执行计划.md) 逐步实施

---

## 核心原则

> **RunnableExecutor 只负责 Run 生命周期管理，不侵入 `Runnable.run()` 签名**

### 核心变更

| 组件 | 重构前 | 重构后 |
|------|--------|--------|
| **执行层** | StepRunner（含 Run 管理） | RunnableExecutor（Run 管理） + StepRunner（Step 管理） |
| **状态管理** | Agent: Steps / Workflow: WorkflowState | **保持不变**（各自管理） |
| **Run 模型** | AgentRun | Run（统一，增加 runnable_type） |
| **Runnable.run() 签名** | 现有签名 | **保持不变** |
| **依赖注入** | Agent 构造函数 / Workflow metadata | **统一为构造函数注入** |

### 方案 D 的优势

1. **最小化改动**：不修改 `Runnable.run()` 签名，Agent 内部逻辑基本不变
2. **职责清晰**：RunnableExecutor 只管 Run，StepRunner 只管 Steps，WorkflowState 只管节点缓存
3. **无限嵌套**：通过 RunnableExecutor 递归调用，天然支持深层嵌套
4. **统一追踪**：所有执行都产生 Run 记录，通过 parent_run_id 形成执行树

---

## 执行计划概览

| Phase | 内容 | 风险 |
|-------|------|------|
| **1** | Metrics 统一 & 协议迁移 | 低 |
| **2** | 文件迁移（WorkflowState → workflow/） | 低 |
| **3** | 依赖注入统一（Workflow 构造函数注入） | 中 |
| **4** | StepRunner 重构（移除 Run 管理 + 事件发射） | 中 |
| **5** | 创建 RunnableExecutor | 中 |
| **6** | 集成 RunnableExecutor（API + Workflow 内部） | 中 |
| **7** | Run 模型改造（AgentRun → Run） | 中 |
| **8** | WorkflowState 查询优化（run_id → workflow_id） | 低 |
| **9** | 集成测试与验证 | 低 |
| **10** | Step 模型扩展（iteration 字段） | 低 |
| **11** | ParallelWorkflow seq 分配优化 | 中 |
| **12** | LoopWorkflow iteration 支持 | 中 |
| **13** | Fork/Resume 场景验证 | 低 |

重构分 13 个 Phase 渐进执行，每个 Phase 独立可验证。
