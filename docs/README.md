# Agio 文档

欢迎来到 Agio 框架的文档中心。

## 📁 文档结构

```
docs/
├── guides/              # 用户指南
│   ├── quick-start.md       - 5分钟快速上手
│   ├── tool-configuration.md - 工具配置和使用
│   └── api-guide.md         - API 使用指南
│
├── architecture/        # 架构文档
│   ├── overview.md          - 架构总览
│   ├── agent-system.md      - Agent 系统详解
│   └── observability.md     - 可观测性系统
│
├── development/         # 开发指南
│   ├── dev-and-deploy.md    - 开发和部署
│   ├── coding-standards.md  - 编码规范
│   ├── tool-permissions.md  - 工具权限系统
│   └── otlp-setup.md        - OTLP 导出配置
│
└── technical-notes/     # 技术笔记
    ├── fix_summary_2026_01_11.md - 修复总结
    ├── trace_incremental_save.md - Trace 增量保存
    ├── wire_closure_nested_agents.md - Wire 闭包与嵌套
    └── agent-hooks-design.md - Hooks 系统设计（未实现）
```

## 🚀 快速开始

想要快速上手？从这里开始：

1. **[快速开始](./guides/quick-start.md)** - 5 分钟快速上手指南
2. **[架构总览](./architecture/overview.md)** - 了解 Agio 的设计理念
3. **[Agent 系统](./architecture/agent-system.md)** - 深入了解 Agent 执行引擎

## 📖 按主题浏览

### 用户指南

适合使用 Agio 的开发者：

- **[快速开始](./guides/quick-start.md)** - 从最简单的 Hello World 开始
- **[工具配置](./guides/tool-configuration.md)** - 如何配置和使用工具
- **[API 使用指南](./guides/api-guide.md)** - RESTful API 和 SSE 接口

### 架构文档

深入理解 Agio 的设计：

- **[架构总览](./architecture/overview.md)** - 核心设计理念和系统架构
- **[Agent 系统](./architecture/agent-system.md)** - Agent 执行引擎详解
- **[可观测性](./architecture/observability.md)** - 追踪和监控系统

### 开发指南

为 Agio 贡献代码或扩展功能：

- **[开发和部署](./development/dev-and-deploy.md)** - 开发环境搭建和部署
- **[编码规范](./development/coding-standards.md)** - 代码风格和最佳实践
- **[工具权限系统](./development/tool-permissions.md)** - HITL 权限控制
- **[OTLP 导出配置](./development/otlp-setup.md)** - OpenTelemetry 集成

### 技术笔记

设计文档和技术总结：

- **[Wire 闭包与嵌套](./technical-notes/wire_closure_nested_agents.md)** - Wire 在嵌套 Agent 中的工作原理
- **[Trace 增量保存](./technical-notes/trace_incremental_save.md)** - Trace 数据的增量保存机制
- **[Agent Hooks 设计](./technical-notes/agent-hooks-design.md)** - Hooks 系统设计（未实现）

## 🔍 常见主题

### 如何创建一个 Agent？
→ [快速开始 - 第一个 Agent](./guides/quick-start.md#第一个-agent)

### 如何使用工具？
→ [快速开始 - 使用工具](./guides/quick-start.md#使用工具)  
→ [工具配置指南](./guides/tool-configuration.md)

### 如何实现多 Agent 协作？
→ [快速开始 - 多 Agent 协作](./guides/quick-start.md#多-agent-协作)  
→ [Agent 系统 - Agent 嵌套](./architecture/agent-system.md#agent-嵌套)

### 如何集成 API？
→ [API 使用指南](./guides/api-guide.md)

### 如何追踪和监控？
→ [可观测性](./architecture/observability.md)

## 📝 贡献文档

发现文档问题或想要改进文档？欢迎贡献！

1. 文档使用 Markdown 格式
2. 所有代码示例都应该可以直接运行
3. 保持中英文文档同步
4. 遵循现有的文档结构和风格

## 🌐 语言

- [English](../README.md)
- [中文](../README_zh.md)

---

**提示**：如果你是第一次使用 Agio，强烈建议从 **[快速开始](./guides/quick-start.md)** 开始！
