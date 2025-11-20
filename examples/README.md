# Agio 示例代码

这里包含了 Agio 的各种使用示例，从基础到高级。

---

## 📁 目录结构

```
examples/
├── basic/              # 基础示例
│   ├── demo.py         # 最简单的 Agent
│   ├── demo_events.py  # 事件流处理
│   ├── demo_history.py # 历史回放
│   ├── demo_metrics.py # Metrics 收集
│   └── demo_prod.py    # 生产级示例
│
├── advanced/           # 高级示例 (计划中)
│   ├── custom_model.py
│   ├── custom_tool.py
│   └── multi_agent.py
│
└── web/               # Web 集成示例 (计划中)
    ├── fastapi_sse/
    ├── gradio_ui/
    └── streamlit_app/
```

---

## 🚀 基础示例

### 1. demo.py - 最简单的 Agent

```bash
cd examples/basic
python demo.py
```

**展示功能**:
- ✅ 创建 Agent
- ✅ 添加工具 (get_weather, calculate)
- ✅ 流式文本输出
- ✅ 工具调用

**适合**: 初学者了解 Agio 的基本用法

---

### 2. demo_events.py - 事件流处理

```bash
python demo_events.py
```

**展示功能**:
- ✅ 使用 `arun_stream()` API
- ✅ 处理不同类型的事件
- ✅ 实时显示工具调用
- ✅ 显示 token 使用情况

**适合**: 了解事件驱动架构

---

### 3. demo_history.py - 历史回放

```bash
python demo_history.py
```

**展示功能**:
- ✅ 配置 Repository
- ✅ 自动保存事件
- ✅ 回放历史对话
- ✅ 列出所有 Runs

**适合**: 了解持久化和回放机制

---

### 4. demo_metrics.py - Metrics 收集

```bash
python demo_metrics.py
```

**展示功能**:
- ✅ 实时 Metrics 显示
- ✅ Token 使用统计
- ✅ 工具调用统计
- ✅ 性能指标

**适合**: 了解可观测性功能

---

### 5. demo_prod.py - 生产级示例

```bash
python demo_prod.py
```

**展示功能**:
- ✅ 完整的错误处理
- ✅ 配置管理
- ✅ Hooks 使用
- ✅ 生产级最佳实践

**适合**: 准备部署到生产环境

---

## ⚙️ 运行前准备

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# Deepseek (如果使用)
DEEPSEEK_API_KEY=sk-your-key-here

# MongoDB (如果使用持久化)
MONGODB_URI=mongodb://localhost:27017
```

或直接设置环境变量：

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

---

## 📚 学习路径

推荐的学习顺序：

1. **demo.py** - 理解基本概念
2. **demo_events.py** - 掌握事件系统
3. **demo_metrics.py** - 了解可观测性
4. **demo_history.py** - 学习持久化
5. **demo_prod.py** - 生产级实践

---

## 🎓 进阶学习

完成基础示例后，可以：

1. 阅读 [架构文档](../docs/architecture/overview.md)
2. 查看 [API 参考](../docs/README.md#api-参考)
3. 尝试 [自定义扩展](../docs/guides/getting_started.md)
4. 参与 [贡献](../CONTRIBUTING.md)

---

## 💡 常见问题

### Q: 示例运行失败？

A: 检查：
1. 是否正确设置了 API Key
2. 是否安装了所有依赖
3. Python 版本是否 >= 3.9

### Q: 如何修改示例？

A: 所有示例都是独立的 Python 文件，可以直接编辑和运行。

### Q: 示例使用的模型？

A: 默认使用 Deepseek，可以修改为 OpenAIModel 或其他模型。

---

## 🤝 贡献示例

欢迎贡献更多示例！

要求：
- ✅ 代码清晰，有注释
- ✅ 包含错误处理
- ✅ 添加到此 README
- ✅ 提供运行说明

---

**需要帮助？** [提交 Issue](https://github.com/yourusername/agio/issues)
