# Agio Refactor Plan

## 背景概述
- **职责耦合**：`AgentRunner` 同时负责上下文构建、模型流、工具执行、记忆写入，导致循环超过 200 行，任何一个层的调整都会牵一发动全身。
- **模型抽象不足**：`Model` 只提供一次性 `astream`，没有“LLM ↔ Tool”闭环能力，Runner 被迫处理 ToolCall 拼接与递归调用。
- **实时/历史割裂**：当前仅输出纯文本流，缺少结构化事件，前端无法统一渲染实时与历史，更无法展示细粒度 metrics。
- **可观测性薄弱**：token/耗时等指标仅在内存更新，无标准序列化/存储流程；tool 执行缺少超时、重试、隔离机制。

## 总体目标
1. **Model-led Loop**：把“LLM 调用 → ToolCall → 执行工具 → 回写消息 → 再次调用”完整逻辑下沉至模型执行层。
2. **Runner 聚焦状态**：AgentRunner 专注 AgentRun 生命周期、上下文生成、Hook 调度，不直接参与工具细节。
3. **事件化输出**：统一的 `AgentEvent` 流同时服务实时渲染与历史回放，并携带丰富 metrics。
4. **可插拔执行栈**：Tools、Memory、Knowledge、Hooks 通过标准接口注入，支持扩展与裁剪。
5. **生产级可观测性**：提供 per-step/per-tool metrics、trace id、错误诊断信息，并易于导出到前端或外部监控系统。

---

## Phase 1：ModelDriver 与工具循环
- **接口设计**
  - 定义 `ModelDriver`（或 `ModelLoop`）协议：接受 `messages`, `tools`, `loop_config`，返回 `AsyncIterator[ModelEvent]`。
  - `ModelEvent` 至少包含 `text_delta`, `tool_call`, `tool_result`, `usage`, `status_update` 等类型。
  - `LoopState` 结构体记录当前 messages、step 序号、已使用 tokens、pending tool calls。
- **工具执行抽象**
  - 新建 `ToolExecutor`：负责工具查找、参数反序列化、超时/并发控制、错误捕获。
  - ModelDriver 仅通过 `await tool_executor.run(call)` 获取结果，并自行把 `ToolObservation` 写入消息列表。
- **最小实现**
  - 基于 OpenAI 实现首个 `ModelDriver`，从现有 Runner 中搬迁 ToolCall 聚合逻辑（删除旧代码，不做兼容保留）。
  - 覆盖单元测试：无工具、单工具、多工具、工具异常、最大步数超限。
- **验收**
  - Runner 仅调用 `async for event in model_driver.run(...)`，不再直接触碰 tool schema。

## Phase 2：Runner 精简与 Hook 拆分
- **Runner 职责**
  - 仅负责：创建 `AgentRun`、构建上下文（System/History/Memory/RAG）、驱动 ModelDriver、维护 Run/Step 状态、触发 Hooks、收尾任务。
  - 将 memory 写入、knowledge 查询改为可配置的 async pipeline，使其天然支持并发。
- **Hook 体系**
  - 以事件为中心：Hook 监听 `RunStarted`, `StepFinished`, `ToolErrored`, `MetricsUpdated` 等高阶事件。
  - Storage/Logging Hook 改为依赖事件负载完成持久化，无需访问 Runner 内部结构。
- **配置清理**
  - 把 `max_steps`、timeouts、并发数、记忆参数写入 Agent/Model 配置，不再硬编码。

## Phase 3：流式事件协议与客户端契约
- **AgentEvent Schema**
  - 统一 JSON 结构：`{"type": "...", "run_id": "...", "payload": {...}}`。
  - 定义必备事件：`text_delta`, `tool_call_started`, `tool_call_finished`, `metrics_snapshot`, `run_status`, `error`.
- **实时 & 历史共用**
  - Runner stream 直接 yield `AgentEvent`；终端/Web 客户端共享渲染逻辑。
  - 历史详情通过读取事件流或 step snapshot 复现完整 UI。
- **前端契约文档**
  - 在 `docs/` 增补《Streaming Protocol》说明字段、顺序、示例，方便第三方集成。

## Phase 4：持久化与历史回放
- **事件存储**
  - StorageHook 负责把 `AgentEvent` 序列化后写入数据库（可先用 Mongo/SQLite）。
  - 为 `AgentRun` 增加 `events_pointer` 或 `steps` 外键，支持分页读取。
- **回放 API**
  - 新增 `AgentRunRepository.get_events(run_id, cursor, limit)`，供历史页面按顺序获取事件。
  - 提供 CLI/HTTP 示例：如何读取 run 并在终端回放。

## Phase 5：可观测性与可靠性
- **Metrics 扩展**
  - `AgentRunMetrics`、`AgentRunStepMetrics`、`ToolMetrics` 增加 `to_event()` 方法。
  - 记录：prompt/completion tokens、TTFT、step duration、tool duration、错误率。
- **错误恢复**
  - ModelDriver 捕获工具/LLM 错误并产出 `error` 事件，同时允许 Runner 决定是否中断或降级。
  - 支持取消（`asyncio.CancelledError`）时正确标记 run 状态。
- **测试/CI**
  - 添加单测覆盖事件顺序、工具失败、记忆回写、Hook 调用。
  - 在 CI 中引入 lint + pytest，保证重构安全。

## Phase 6：发布准备与生态
- **文档与示例**
  - 更新 README、`docs/agio_develop_*.md`，描述新架构、事件协议、扩展点。
  - 提供高质量 Demo（web + terminal）展示实时事件与历史回放。
- **Tool/MCP 生态**
  - 设计官方 Tool 套件模板、MCP 适配示例，展示如何在新架构下扩展。
- **社区化准备**
  - 补充贡献指南、Issue 模板、Benchmarks、Roadmap，使之具备“上万 star 项目”的基础体验。

---

> 以上计划默认不做向后兼容，所有遗留逻辑与注释在重构过程中应及时删除，以保持代码库简洁可维护。

