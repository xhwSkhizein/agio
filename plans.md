# Refactor Execution Plan

## Phase 1: ModelDriver & Tool Loop (Core Logic Shift) ✅
- [x] **Define Interfaces**: Create `ModelDriver` (or `ModelLoop`) protocol in `agio/core/loop.py` (new file).
  - [x] Define `ModelEvent` (dataclass/pydantic) with types: `text_delta`, `tool_call`, `tool_result`, `usage`, `status_update`.
  - [x] Define `LoopState` to track steps, tokens, and pending calls.
  - [x] Define `AgentEvent` for unified event streaming.
- [x] **Abstract Tool Execution**: Create `ToolExecutor` in `agio/execution/tool_executor.py`.
  - [x] Implement `execute(call)` method handling tool lookup, argument parsing, and error catching.
  - [x] Port `AgentRunner._execute_tool` logic to `ToolExecutor`, improving error formatting.
- [x] **Implement ModelDriver**: Create `OpenAIModelDriver` in `agio/drivers/openai_driver.py`.
  - [x] Implement the loop: call LLM -> parse stream -> yield events -> execute tools -> yield events -> loop.
  - [x] Move tool call accumulation logic (currently in `AgentRunner`) into the driver/model layer.
  - [x] Add error handling and logging.
- [x] **Refactor AgentRunner (Preliminary)**:
  - [x] Instantiate `OpenAIModelDriver` inside `AgentRunner`.
  - [x] Replace the main `while step_num < max_steps` loop in `AgentRunner` with `async for event in driver.run(...)`.
  - [x] **DELETE**: Remove `tool_calls_accumulator`, `_execute_tool` (legacy), and manual tool call handling code from `AgentRunner`.
  - [x] Event-driven step management.
- [x] **Testing**:
  - [x] Basic integration test with demo.py (success).

## Phase 2: Runner Simplification & Hook Split ✅
- [x] **Refine AgentRunner**:
  - [x] Strip `AgentRunner` down to: `init` -> `build_context` -> `driver.run()` -> `hooks` -> `cleanup`.
  - [x] Move `_build_context` logic into dedicated `ContextBuilder` class.
  - [x] **DELETE**: Remove `_build_context` method (55 lines) from `AgentRunner`.
  - [x] AgentRunner reduced from 232 lines to 183 lines.
- [x] **Config Management**:
  - [x] Create `AgentRunConfig` for unified configuration.
  - [x] Move `max_steps`, `max_history_messages`, `max_rag_docs`, `max_memories` to config.
  - [x] Add timeout and concurrency configuration options.
  - [x] **DELETE**: Hardcoded constants in `AgentRunner` and `ContextBuilder`.
- [x] **Async Task Optimization**:
  - [x] Add `memory_update_async` config option.
  - [x] Support both sync and async memory updates.
- [x] **Testing**:
  - [x] All 11 tests pass.
  - [x] Integration tests (demo.py) pass.

## Phase 3: Streaming Event Protocol ✅
- [x] **Standardize Events**:
  - [x] Create `AgentEvent` schema in `agio/protocol/events.py`.
  - [x] Create event converter to map `ModelEvent` to `AgentEvent`.
  - [x] Define 15+ event types for comprehensive coverage.
- [x] **Update Output**:
  - [x] Add `AgentRunner.run_stream()` to yield `AgentEvent` objects.
  - [x] Keep `AgentRunner.run()` for backward compatibility (yields strings).
  - [x] Add `Agent.arun_stream()` as new public API.
- [x] **Documentation**:
  - [x] Create `docs/streaming_protocol.md` with complete protocol specification.
  - [x] Include examples for Python and JavaScript clients.
  - [x] Document SSE format and FastAPI integration.
- [x] **Testing**:
  - [x] All 11 tests pass.
  - [x] Create `demo_events.py` showcasing event stream.
  - [x] Verify backward compatibility with `demo.py`.

## Phase 4: Persistence & History ✅
- [x] **Event Storage**:
  - [x] Create `AgentRunRepository` interface in `agio/db/repository.py`.
  - [x] Implement `InMemoryRepository` for testing.
  - [x] Integrate event storage directly into `AgentRunner`.
  - [x] Store events with `run_id` and sequence number.
- [x] **Replay API**:
  - [x] Implement `get_events(run_id)` to fetch historical events.
  - [x] Implement `list_runs()` to list historical runs.
  - [x] Add `Agent.get_run_history()` for event replay.
  - [x] Add `Agent.list_runs()` for run listing.
- [x] **Testing**:
  - [x] All 11 tests pass.
  - [x] Create `demo_history.py` showcasing history and replay.
  - [x] Verify event storage and replay functionality.

## Phase 5: Observability & Reliability (Complete ✅)
- [x] **Event System Enhancement**:
  - [x] Add `METRICS_SNAPSHOT` to `ModelEventType`.
  - [x] Update `EventConverter` to handle metrics snapshots.
  - [x] Integrate metrics snapshot handling in `AgentRunner`.
- [x] **Metrics Collection**:
  - [x] Implement metrics collection in `ModelDriver`.
  - [x] Emit `metrics_snapshot` events at step ends.
  - [x] Track tokens, steps, tool calls, and duration.
- [x] **Error Handling**:
  - [x] Implement error classification (fatal vs non-fatal).
  - [x] Add graceful error recovery for non-fatal errors.
  - [x] Include `is_fatal` flag in error events.
- [x] **Cancellation Support**:
  - [x] Implement asyncio cancellation handling.
  - [x] Graceful cleanup on cancellation.
  - [x] Emit cancellation events.
- [x] **Testing**:
  - [x] All 11 tests pass.
  - [x] Create `demo_metrics.py` showcasing metrics and observability.
- [ ] **CI/CD** (Future):
  - [ ] Set up `pytest` workflows.
  - [ ] Set up `lint` workflows.

## Phase 6: Ecosystem & Open Source Excellence

### 目标
打造一个万星级别的开源项目，提供完整的生态系统、优秀的文档和社区支持。

---

### 6.1 文档体系 (Documentation Excellence)

#### 核心文档
- [ ] **README.md 重写**:
  - [ ] 吸引人的项目介绍和 Logo
  - [ ] 清晰的特性列表（与竞品对比）
  - [ ] 快速开始（5 分钟上手）
  - [ ] 核心概念图解
  - [ ] 安装指南（pip, poetry, conda）
  - [ ] 基础示例（3-5 个）
  - [ ] 架构图和数据流图
  - [ ] 贡献指南链接
  - [ ] 社区和支持信息
  - [ ] License 和引用信息

#### API 文档
- [ ] **自动生成 API 文档**:
  - [ ] 使用 Sphinx 或 MkDocs
  - [ ] 所有公共 API 的完整文档
  - [ ] 类型注解和参数说明
  - [ ] 使用示例
  - [ ] 部署到 GitHub Pages 或 ReadTheDocs

#### 教程和指南
- [ ] **Getting Started Guide**:
  - [ ] 安装和配置
  - [ ] 第一个 Agent
  - [ ] 添加工具
  - [ ] 使用记忆系统
  - [ ] 事件流处理
  
- [ ] **Advanced Guides**:
  - [ ] 自定义 ModelDriver
  - [ ] 实现自定义 Repository
  - [ ] 构建复杂工作流
  - [ ] 性能优化技巧
  - [ ] 生产部署最佳实践
  
- [ ] **Cookbook**:
  - [ ] RAG Agent 实现
  - [ ] Multi-Agent 协作
  - [ ] 流式 UI 集成
  - [ ] 错误处理和重试
  - [ ] 监控和日志

#### 架构文档
- [ ] **Architecture Decision Records (ADR)**:
  - [ ] 事件驱动架构选择
  - [ ] Repository 模式设计
  - [ ] ModelDriver 抽象层
  - [ ] 错误处理策略
  
- [ ] **Design Documents**:
  - [ ] 系统架构图
  - [ ] 数据流图
  - [ ] 组件交互图
  - [ ] 扩展点说明

---

### 6.2 示例和模板 (Examples & Templates)

#### 基础示例
- [ ] `examples/01_basic_agent.py` - 最简单的 Agent
- [ ] `examples/02_agent_with_tools.py` - 带工具的 Agent
- [ ] `examples/03_streaming_events.py` - 事件流处理
- [ ] `examples/04_memory_agent.py` - 带记忆的 Agent
- [ ] `examples/05_rag_agent.py` - RAG Agent

#### 高级示例
- [ ] `examples/advanced/custom_driver.py` - 自定义 Driver
- [ ] `examples/advanced/custom_repository.py` - 自定义存储
- [ ] `examples/advanced/multi_agent.py` - 多 Agent 协作
- [ ] `examples/advanced/error_handling.py` - 错误处理
- [ ] `examples/advanced/performance_tuning.py` - 性能优化

#### Web 集成示例
- [ ] `examples/web/fastapi_integration/` - FastAPI 集成
  - [ ] SSE 流式响应
  - [ ] WebSocket 支持
  - [ ] 历史回放 API
  - [ ] 前端示例（React）
  
- [ ] `examples/web/gradio_demo/` - Gradio UI Demo
- [ ] `examples/web/streamlit_app/` - Streamlit App

#### 实战项目模板
- [ ] `templates/chatbot/` - 聊天机器人模板
- [ ] `templates/code_assistant/` - 代码助手模板
- [ ] `templates/data_analyst/` - 数据分析助手模板

---

### 6.3 工具生态 (Tool Ecosystem)

#### 官方工具库
- [ ] **agio-tools** 包:
  - [ ] Web 搜索工具（Google, Bing, DuckDuckGo）
  - [ ] 文件操作工具（读写、搜索）
  - [ ] 数据库工具（SQL 查询）
  - [ ] API 调用工具（HTTP 请求）
  - [ ] 代码执行工具（Python, JavaScript）
  - [ ] 数学计算工具
  - [ ] 日期时间工具
  
#### 工具开发指南
- [ ] 工具开发最佳实践
- [ ] 工具测试指南
- [ ] 工具发布流程
- [ ] 工具市场（社区贡献）

---

### 6.4 存储后端 (Storage Backends)

#### 官方存储实现
- [ ] **PostgreSQL Repository**:
  - [ ] 完整的 SQL schema
  - [ ] 高性能查询优化
  - [ ] 事务支持
  
- [ ] **MongoDB Repository**:
  - [ ] 文档结构设计
  - [ ] 索引优化
  
- [ ] **Redis Repository**:
  - [ ] 缓存策略
  - [ ] TTL 配置
  
- [ ] **SQLite Repository** (增强版):
  - [ ] 全文搜索
  - [ ] 性能优化

#### 存储插件系统
- [ ] 插件接口规范
- [ ] 插件注册机制
- [ ] 插件市场

---

### 6.5 集成和兼容性 (Integrations)

#### LLM Provider 支持
- [ ] **OpenAI** (已支持)
- [ ] **Anthropic Claude**
- [ ] **Google Gemini**
- [ ] **Azure OpenAI**
- [ ] **本地模型** (Ollama, LM Studio)
- [ ] **开源模型** (Hugging Face)

#### 框架集成
- [ ] **LangChain** 兼容层
- [ ] **LlamaIndex** 集成
- [ ] **Haystack** 集成
- [ ] **Semantic Kernel** 兼容

#### 平台集成
- [ ] **Discord Bot** 模板
- [ ] **Slack Bot** 模板
- [ ] **Telegram Bot** 模板
- [ ] **微信公众号** 模板

---

### 6.6 开发者体验 (Developer Experience)

#### CLI 工具
- [ ] `agio init` - 初始化项目
- [ ] `agio create-tool` - 创建工具模板
- [ ] `agio test` - 运行测试
- [ ] `agio deploy` - 部署助手
- [ ] `agio docs` - 本地文档服务器

#### IDE 支持
- [ ] VS Code 扩展:
  - [ ] 代码片段
  - [ ] 工具开发辅助
  - [ ] 调试支持
  
- [ ] PyCharm 插件（可选）

#### 调试工具
- [ ] **Agio Debugger**:
  - [ ] 事件流可视化
  - [ ] Step-by-step 调试
  - [ ] 性能分析
  - [ ] 日志查看器

---

### 6.7 测试和质量保证 (Testing & QA)

#### 测试覆盖
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试套件
- [ ] 端到端测试
- [ ] 性能基准测试
- [ ] 压力测试

#### CI/CD
- [ ] **GitHub Actions**:
  - [ ] 自动测试（Python 3.9-3.12）
  - [ ] 代码质量检查（ruff, mypy）
  - [ ] 测试覆盖率报告
  - [ ] 自动发布到 PyPI
  - [ ] 文档自动部署
  
- [ ] **Pre-commit Hooks**:
  - [ ] 代码格式化
  - [ ] 类型检查
  - [ ] Lint 检查

#### 质量标准
- [ ] 代码覆盖率徽章
- [ ] 文档覆盖率徽章
- [ ] PyPI 版本徽章
- [ ] License 徽章
- [ ] 下载量统计

---

### 6.8 社区建设 (Community Building)

#### 社区平台
- [ ] **GitHub Discussions** 启用
- [ ] **Discord Server** 创建
- [ ] **中文社区** (微信群/QQ 群)
- [ ] **Twitter/X** 账号
- [ ] **博客/Newsletter**

#### 贡献指南
- [ ] `CONTRIBUTING.md`:
  - [ ] 代码规范
  - [ ] 提交规范
  - [ ] PR 流程
  - [ ] Issue 模板
  
- [ ] `CODE_OF_CONDUCT.md`
- [ ] `SECURITY.md`
- [ ] 贡献者名单

#### 社区活动
- [ ] **Good First Issue** 标签
- [ ] **Hacktoberfest** 参与
- [ ] **月度贡献者奖励**
- [ ] **社区会议** (月度)

---

### 6.9 营销和推广 (Marketing & Promotion)

#### 内容创作
- [ ] **博客文章**:
  - [ ] "Introducing Agio"
  - [ ] "Building Production-Ready AI Agents"
  - [ ] "Event-Driven Agent Architecture"
  - [ ] 技术深度文章系列
  
- [ ] **视频教程**:
  - [ ] YouTube 快速入门
  - [ ] Bilibili 中文教程
  - [ ] 实战案例分享

#### 社区推广
- [ ] **Reddit** (r/MachineLearning, r/Python)
- [ ] **Hacker News** 发布
- [ ] **Product Hunt** 发布
- [ ] **Twitter/X** 推广
- [ ] **技术会议** 分享（PyCon, AI 大会）

#### 合作伙伴
- [ ] 与其他开源项目合作
- [ ] 企业用户案例
- [ ] 学术机构合作

---

### 6.10 性能和可扩展性 (Performance & Scalability)

#### 性能优化
- [ ] 事件处理性能优化
- [ ] 内存使用优化
- [ ] 并发性能提升
- [ ] 缓存策略

#### 可扩展性
- [ ] 分布式 Agent 支持
- [ ] 负载均衡
- [ ] 水平扩展方案
- [ ] 云原生部署（K8s）

#### 监控和观测
- [ ] Prometheus metrics 导出
- [ ] OpenTelemetry 集成
- [ ] 日志聚合方案
- [ ] APM 集成

---

### 6.11 安全性 (Security)

#### 安全措施
- [ ] API Key 安全管理
- [ ] 输入验证和清理
- [ ] 输出过滤（防止注入）
- [ ] 速率限制
- [ ] 安全审计

#### 合规性
- [ ] GDPR 合规
- [ ] 数据隐私保护
- [ ] 安全最佳实践文档

---

### 6.12 发布准备 (Release Preparation)

#### 版本管理
- [ ] Semantic Versioning
- [ ] Changelog 自动生成
- [ ] Release Notes 模板
- [ ] 版本兼容性矩阵

#### 发布检查清单
- [ ] 所有测试通过
- [ ] 文档完整且最新
- [ ] 示例可运行
- [ ] 性能基准达标
- [ ] 安全审计通过
- [ ] License 检查
- [ ] PyPI 包测试

#### 首次发布 (v1.0.0)
- [ ] 发布公告
- [ ] 媒体推广
- [ ] 社区通知
- [ ] 庆祝活动 🎉

---

## 成功指标 (Success Metrics)

### 技术指标
- [ ] GitHub Stars > 10,000
- [ ] PyPI 月下载量 > 50,000
- [ ] 测试覆盖率 > 80%
- [ ] 文档覆盖率 > 90%
- [ ] Issue 响应时间 < 24h

### 社区指标
- [ ] 活跃贡献者 > 50
- [ ] Discord 成员 > 1,000
- [ ] 企业用户 > 10
- [ ] 学术论文引用 > 5

### 生态指标
- [ ] 第三方工具包 > 20
- [ ] 集成案例 > 30
- [ ] 教程和文章 > 50
