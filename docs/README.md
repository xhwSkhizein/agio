# Agio 文档索引

本目录包含 Agio 项目的核心技术文档。

## 📚 文档列表

### 系统架构

#### [ARCHITECTURE.md](./ARCHITECTURE.md)
系统整体架构文档，介绍各组件关系、设计原则和技术栈。

**内容**：
- 系统架构概览
- 核心组件设计
- 技术栈选择
- 设计原则

**适合人群**：新开发者、架构师

---

### 配置系统

#### [DYNAMIC_CONFIG_ARCHITECTURE.md](./DYNAMIC_CONFIG_ARCHITECTURE.md)
配置系统详细架构文档，深入介绍配置管理的实现细节。

**内容**：
- 配置管理器（ConfigManager）
- 依赖图（DependencyGraph）
- 配置存储（Repository）
- 事件系统（EventBus）
- 配置构建器（Builders）

**适合人群**：配置系统开发者、系统维护者

#### [DYNAMIC_CONFIG_DESIGN.md](./DYNAMIC_CONFIG_DESIGN.md)
配置系统设计理念和核心概念。

**内容**：
- 设计目标
- 核心概念
- 使用场景
- 最佳实践

**适合人群**：系统设计者、架构师

#### [CONFIG_COLD_START_SUMMARY.md](./CONFIG_COLD_START_SUMMARY.md)
配置系统冷启动功能实现总结。

**内容**：
- ConfigLoader 实现
- 冷启动流程
- 配置文件结构
- 加载顺序
- 使用示例

**适合人群**：功能使用者、开发者

---

### 工具系统

#### [TOOL_LLM_REFACTOR_SUMMARY.md](./TOOL_LLM_REFACTOR_SUMMARY.md)
工具 LLM 依赖统一重构总结。

**内容**：
- ModelLLMAdapter 适配器
- 依赖注入机制
- 工具配置示例
- 迁移指南

**适合人群**：工具开发者、系统维护者

#### [TOOLS_CLEANUP_SUMMARY.md](./TOOLS_CLEANUP_SUMMARY.md)
工具目录清理总结，记录过时代码的删除和架构改进。

**内容**：
- 删除的过时文件
- 保留的核心文件
- 架构改进
- 迁移指南

**适合人群**：工具系统维护者、开发者

---

## 🗂️ 文档分类

### 按主题分类

| 主题 | 文档 |
|------|------|
| **系统架构** | ARCHITECTURE.md |
| **配置系统** | DYNAMIC_CONFIG_ARCHITECTURE.md<br>DYNAMIC_CONFIG_DESIGN.md<br>CONFIG_COLD_START_SUMMARY.md |
| **工具系统** | TOOL_LLM_REFACTOR_SUMMARY.md<br>TOOLS_CLEANUP_SUMMARY.md |

### 按用途分类

| 用途 | 文档 |
|------|------|
| **入门了解** | ARCHITECTURE.md<br>DYNAMIC_CONFIG_DESIGN.md |
| **深入学习** | DYNAMIC_CONFIG_ARCHITECTURE.md |
| **功能使用** | CONFIG_COLD_START_SUMMARY.md<br>TOOL_LLM_REFACTOR_SUMMARY.md |
| **维护参考** | TOOLS_CLEANUP_SUMMARY.md |

---

## 📖 阅读建议

### 新开发者

1. 先阅读 **ARCHITECTURE.md** 了解系统整体架构
2. 阅读 **DYNAMIC_CONFIG_DESIGN.md** 理解配置系统设计理念
3. 根据需要深入阅读具体模块文档

### 配置系统开发

1. **DYNAMIC_CONFIG_DESIGN.md** - 理解设计理念
2. **DYNAMIC_CONFIG_ARCHITECTURE.md** - 掌握实现细节
3. **CONFIG_COLD_START_SUMMARY.md** - 了解冷启动功能

### 工具系统开发

1. **TOOL_LLM_REFACTOR_SUMMARY.md** - 了解 LLM 依赖注入
2. **TOOLS_CLEANUP_SUMMARY.md** - 了解工具系统架构
3. **CONFIG_COLD_START_SUMMARY.md** - 了解工具配置加载

---

## 🔄 文档维护

### 文档更新原则

1. **及时更新**：代码重大变更时同步更新文档
2. **保持简洁**：避免冗余和重复内容
3. **清晰准确**：确保示例代码可运行
4. **版本控制**：重大更新记录变更历史

### 文档清理历史

- **2024-11**: 删除 23 个过时/重复文档，保留 6 个核心文档
  - 删除配置系统临时文档（5个）
  - 删除工具系统早期/临时文档（15个）
  - 删除 Web 工具重复文档（3个）

---

## 📝 贡献指南

### 添加新文档

1. 确保文档有明确的目的和受众
2. 避免与现有文档重复
3. 遵循 Markdown 格式规范
4. 更新本 README 索引

### 更新现有文档

1. 保持文档结构一致
2. 更新示例代码确保可运行
3. 标注更新日期和变更内容

### 删除过时文档

1. 确认文档已过时或被替代
2. 检查是否有外部引用
3. 更新本 README 索引
4. 记录删除原因

---

## 🔗 相关资源

- [项目 README](../README.md)
- [配置文件示例](../configs/)
- [代码示例](../examples/)
- [测试用例](../tests/)

---

## 📞 联系方式

如有文档问题或建议，请：
- 提交 Issue
- 发起 Pull Request
- 联系项目维护者

---

**最后更新**: 2024-11
**文档数量**: 6 个核心文档
