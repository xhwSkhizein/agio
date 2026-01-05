# Agent 执行界面 UI 优化设计说明（Draft）

## 1. 设计目标（Design Goals）

本次 UI 重构的核心目标是：

* 将当前 **开发者调试日志视角** 转变为 **人类可理解的 Agent 行为叙事视角**
* 在不牺牲调试能力的前提下，显著提升：
  * 信息清晰度
  * 信息有效密度
  * 任务执行的可读性与可解释性
* 支持 **用户模式 / Debug 模式** 的信息分级展示

---

## 2. 当前主要问题总结

### 2.1 信息架构问题

* Thinking / Tool Call / Tool Output / Status 同权展示
* 缺乏“任务主线”，用户无法快速理解：
  * Agent 在做什么
  * 为什么这么做
  * 做到了什么程度
* 实际呈现为“日志堆叠”，而非“任务执行过程”

### 2.2 信息密度失衡

* 高重复度信息（如多次 `ls`）被逐条完整展示
* 机器级信息（token、path、pattern）占据主视图
* 高价值信息（结果、失败原因、中断点）被淹没

### 2.3 视觉层级缺失

* 颜色用于区分“类型”，而非表达“重要性 / 状态”
* 过多 Box / Panel 导致视觉噪音过高
* 用户无法快速判断“该先看哪里”

---

## 3. 核心设计原则

### 3.1 三层信息密度模型（Strongly Recommended）

#### L1：任务摘要层（默认展开）

> 面向所有用户，90% 使用场景

展示内容：

* Agent / Task 名称
* 任务目标（1 句话）
* 执行状态（Success / Partial / Failed / Interrupted）
* 子任务数量 + 完成情况
* 关键产出摘要（1–3 行）

示例：

```
Master Orchestrator
Explore available skills in working directory

✔ 17 steps completed · 6 children
📁 Found 19 items · 3 skill-related files
⚠ Mission interrupted during glob scan
```

---

#### L2：执行轨迹层（可展开）

> 面向高级用户 / 产品理解者

展示内容：

* 子任务（Subtask / Agent）列表
* 每个子任务：
  * 调用过的工具（合并同类项）
  * 成功 / 失败 / 中断
  * 执行耗时

示例：

```
Collector Agent
✔ ls × 3
✔ glob("**/skill*.py")
✖ interrupted
```

说明：

* 连续、同参数 Tool Call 自动合并
* 不直接展开 Thinking 原文

---

#### L3：机器细节层（Debug 模式）

> 仅在 Debug / Developer Mode 下显示

包含：

* 原始 Thinking 文本
* Token in / out
* 原始 Tool Call 参数
* Path / Level / Pattern 等底层信息

默认完全折叠，不参与主阅读流。

---

## 4. Thinking 内容展示策略

### 问题

* Thinking 块体积过大
* 重复、冗长、对主线理解帮助有限

### 改进方案

* 默认只展示 **“Agent 意图摘要”**
* 原始 Thinking 内容：
  * 折叠
  * 仅在 Debug 模式下可查看
  * 可通过 Drawer / Modal / Tooltip 打开

示例：

```
🤔 Reasoning
"Exploring root directory to locate skill definitions"
[View full trace]
```

---

## 5. Tool Call 展示语义重构

### 当前形式（不推荐）

```
✓ ls (path: /agio, level: 1)
```

### 建议形式（Action → Object → Result）

```
📂 Listed directory
Path: /agio
Result: 19 items
Time: 4.4s
```

规则：

* 同类、连续 Tool Call 自动合并（如 `ls × 3`）
* 参数信息默认折叠
* 执行结果优先展示

---

## 6. 视觉与布局建议

### 6.1 时间轴式布局（替代 Box 堆叠）

* 使用纵向 Execution Timeline
* 每一步作为节点
* 左侧状态条表达结果（✔ / ⚠ / ✖）

示例结构：

```
│ ✔ List directory
│ ✔ Scan for skill files
│ ✖ Interrupted during glob
```

---

### 6.2 颜色使用原则

* 颜色仅用于表达 ​**状态**​，不用于区分类型
  * Green：Success
  * Yellow：Partial / Warning
  * Red：Failed / Interrupted
  * Gray：Collapsed / Secondary
* 类型通过 icon + 文本表达

---

### 6.3 顶部任务控制区（Sticky Header）

建议顶部固定区域包含：

* 当前任务目标
* 执行状态
* 视图模式切换：
  * User / Debug
* 展示密度切换：
  * Compact / Detailed

---

## 7. 推荐组件模型：Agent Execution Card

每个 Agent / Task 作为一张 Card：

```
┌─────────────────────────────┐
│ Master Orchestrator          │
│ Explore available skills     │
│                              │
│ ✔ 17 steps · 6 children      │
│ ⚠ Interrupted                │
│                              │
│ ▶ Execution Summary          │
│ ▶ Subtasks (6)               │
│ ▶ Debug Trace                │
└─────────────────────────────┘
```

特性：

* 默认只展开 Summary
* Debug Trace 仅在 Debug Mode 可见
* 支持递归嵌套（Parent / Child Agent）

---

## 8. 实现优先级建议

1. **信息结构重构（最优先）**
2. Summary / Detail / Debug 分层
3. Tool Call 合并与摘要
4. Timeline 布局
5. 视觉细节与动画优化

---

## 9. 设计导向总结（一句话）

> **不要让用户“读日志”，而是让用户“理解 Agent 在做什么”。**
