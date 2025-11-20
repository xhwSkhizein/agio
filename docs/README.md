# Agio 文档中心

欢迎来到 Agio 文档中心！这里是你学习和使用 Agio 的完整指南。

---

## 🚀 快速开始

**新手？从这里开始：**

- 📘 [快速开始指南](guides/getting_started.md) - 5分钟创建第一个 Agent
- 🎯 [核心概念](concepts/core_concepts.md) - 理解 Agio 的设计理念
- 📚 [示例代码](../examples/basic/) - 实战示例集合

---

## 🏗️ 架构文档

**深入理解 Agio 的设计：**

- 🔷 [架构概览](architecture/overview.md) - 三层架构设计详解
- 🔄 [事件系统](streaming_protocol.md) - AgentEvent 协议和事件流
- ⚙️ [执行流程](architecture/execution_flow.md) - 从查询到响应的完整流程
- 📊 [数据模型](architecture/data_models.md) - Run, Step, Message 等领域模型

---

## 📖 API 参考

**完整的 API 文档：**

### 核心 API
- [Agent](api/agent.md) - Agent 配置和执行
- [AgentRunner](api/runner.md) - 编排器 API
- [AgentExecutor](api/executor.md) - 执行引擎 API

### 模型
- [Model 基类](api/model.md) - 模型抽象接口
- [OpenAIModel](api/openai_model.md) - OpenAI 实现
- [DeepseekModel](api/deepseek_model.md) - Deepseek 实现

### 工具
- [Tool 系统](api/tools.md) - 工具定义和执行
- [FunctionTool](api/function_tool.md) - 函数装饰器方式
- [MCP 支持](api/mcp.md) - Model Context Protocol

### 存储和记忆
- [Repository](api/repository.md) - 事件存储接口
- [Memory](api/memory.md) - 对话记忆
- [Knowledge](api/knowledge.md) - RAG 知识库

### 事件和协议
- [AgentEvent](api/events.md) - 事件协议详解
- [Hooks](api/hooks.md) - 生命周期钩子

---

## 🎓 使用指南

**实用的操作指南：**

### 基础教程
- [创建第一个 Agent](guides/getting_started.md#第一个-agent30秒)
- [添加工具](guides/getting_started.md#添加工具)
- [使用事件流](guides/getting_started.md#使用事件流-api)
- [添加记忆](guides/getting_started.md#添加记忆)
- [RAG 知识库](guides/getting_started.md#添加知识库rag)

### 进阶主题
- [自定义 Model](guides/custom_model.md) - 集成自己的 LLM
- [自定义 Tool](guides/custom_tools.md) - 创建强大的工具
- [自定义 Repository](guides/custom_repository.md) - 实现持久化后端
- [自定义 Hook](guides/custom_hooks.md) - 扩展生命周期

### 实战案例
- [构建聊天机器人](guides/chatbot.md)
- [RAG 问答系统](guides/rag_qa.md)
- [代码助手](guides/code_assistant.md)
- [数据分析 Agent](guides/data_analyst.md)

### 部署和生产
- [生产部署](guides/deployment.md) - Docker, K8s, 云服务
- [性能优化](guides/performance.md) - 提升速度和降低成本
- [监控和日志](guides/monitoring.md) - Prometheus, OpenTelemetry
- [错误处理](guides/error_handling.md) - 最佳实践

---

## 🔧 开发者资源

**参与 Agio 开发：**

- 🤝 [贡献指南](../CONTRIBUTING.md) - 如何参与开发
- 📋 [行为准则](../CODE_OF_CONDUCT.md) - 社区规范
- 📝 [变更日志](../CHANGELOG.md) - 版本历史
- 🐛 [Issue 跟踪](https://github.com/yourusername/agio/issues) - 报告问题

---

## 🌟 示例集合

**完整的示例代码：**

### 基础示例
- [examples/basic/demo.py](../examples/basic/demo.py) - 最简单的 Agent
- [examples/basic/demo_events.py](../examples/basic/demo_events.py) - 事件流处理
- [examples/basic/demo_history.py](../examples/basic/demo_history.py) - 历史回放
- [examples/basic/demo_metrics.py](../examples/basic/demo_metrics.py) - Metrics 收集

### Web 集成
- FastAPI + SSE - 实时流式响应
- Gradio UI - 快速构建聊天界面
- Streamlit App - 数据应用集成

### 高级示例
- Multi-Agent 协作
- 自定义 Driver
- 自定义 Repository
- 性能优化

---

## 📊 对比和选型

**Agio vs 其他框架：**

| 特性 | Agio | LangChain | AutoGPT | Semantic Kernel |
|------|------|-----------|---------|-----------------|
| 异步原生 | ✅ | ⚠️ | ❌ | ✅ |
| 事件驱动 | ✅ (15种) | ❌ | ❌ | ⚠️ |
| 类型安全 | ✅ | ⚠️ | ❌ | ✅ |
| 历史回放 | ✅ | ❌ | ❌ | ❌ |
| 学习曲线 | 低 | 中 | 高 | 中 |
| 性能 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |

**选择 Agio 的理由：**
- ✅ 需要生产级的可观测性
- ✅ 重视代码质量和类型安全
- ✅ 需要完整的历史回放
- ✅ 追求高性能异步架构
- ✅ 需要清晰的架构设计

---

## 🗺️ 路线图

### v0.4.0 (当前) ✅
- ✅ 三层架构重构
- ✅ 统一事件系统
- ✅ 历史回放
- ✅ Metrics 收集

### v0.5.0 (计划中)
- [ ] 更多 LLM 支持 (Claude, Gemini)
- [ ] PostgreSQL/MongoDB Repository
- [ ] 性能优化和基准测试
- [ ] 完整的文档网站

### v1.0.0 (目标)
- [ ] Multi-Agent 协作
- [ ] 分布式执行
- [ ] 官方工具库
- [ ] 生产级最佳实践

---

## 💬 社区和支持

**获取帮助：**

- 💬 [Discord 社区](https://discord.gg/agio) - 实时讨论
- 🐛 [GitHub Issues](https://github.com/yourusername/agio/issues) - 报告bug
- 💡 [GitHub Discussions](https://github.com/yourusername/agio/discussions) - 提问和讨论
- 📧 [邮件列表](mailto:agio@example.com) - 重要更新

**关注我们：**
- 🐦 [Twitter](https://twitter.com/AgioFramework)
- 📝 [博客](https://blog.agio.dev)
- 📺 [YouTube](https://youtube.com/@agio)

---

## 📄 许可证

Agio 采用 [MIT License](../LICENSE) 开源。

---

## 🙏 致谢

感谢所有 [贡献者](../CONTRIBUTORS.md) 的付出！

特别感谢：
- OpenAI 提供优秀的 GPT 模型
- Python 社区的支持
- 所有用户的反馈和建议

---

**文档版本**: v0.4.0  
**最后更新**: 2025-11-21

需要改进这些文档？[提交 PR](https://github.com/yourusername/agio/pulls) 或 [提出建议](https://github.com/yourusername/agio/issues/new)！
