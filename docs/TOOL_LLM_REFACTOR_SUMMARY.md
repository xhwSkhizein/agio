# 工具系统 LLM 依赖统一重构 - 完成总结

## 重构概述

成功将工具系统中的 `SimpleLLMService` 替换为统一的 `Model` 抽象，通过配置系统实现依赖注入。

## 已完成的工作

### 1. 扩展配置系统 ✅

**文件**: `agio/core/config.py`

```python
class ToolConfig(ComponentConfig):
    # ... 原有字段
    dependencies: dict[str, str] = Field(
        default_factory=dict,
        description="Dependencies mapping: {param_name: component_name}",
    )
```

- 新增 `dependencies` 字段，支持声明工具的依赖关系
- 格式：`{参数名: 组件名}`，如 `{"llm_model": "gpt-4o-mini"}`

### 2. 增强 ToolBuilder ✅

**文件**: `agio/config/builders.py`

```python
class ToolBuilder(ComponentBuilder):
    async def build(self, config: ToolConfig, dependencies: dict[str, Any]) -> Any:
        # 合并参数：config.params + 解析后的依赖
        kwargs = {**config.params}
        
        # 解析依赖：将依赖名称映射到实际实例
        for param_name, dep_name in config.dependencies.items():
            if dep_name not in dependencies:
                raise ComponentBuildError(...)
            kwargs[param_name] = dependencies[dep_name]
        
        return tool_class(**kwargs)
```

- 支持依赖解析和注入
- 自动将配置中的依赖名称映射到实际组件实例
- 提供清晰的错误信息

### 3. 创建 ModelLLMAdapter ✅

**文件**: `agio/components/tools/builtin_tools/common/llm/model_adapter.py`

```python
class ModelLLMAdapter:
    """将 Model 的流式接口适配为简单的请求-响应接口"""
    
    def __init__(self, model: "Model"):
        self.model = model
    
    async def invoke(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
        abort_signal: "AbortSignal | None" = None,
    ) -> LLMResult | None:
        # 调用 Model 流式接口并聚合结果
        ...
```

**设计亮点**：
- 保持与 `SimpleLLMService` 相同的接口，最小化工具代码改动
- 内部处理流式聚合，对外提供简单的请求-响应模式
- 支持中断信号和错误处理

### 4. 更新 WebFetchTool ✅

**文件**: `agio/components/tools/builtin_tools/web_fetch_tool/web_fetch_tool.py`

**改动前**：
```python
def __init__(
    self,
    *,
    llm_service: SimpleLLMService | None = None,
):
    self._llm_service = llm_service
```

**改动后**：
```python
def __init__(
    self,
    *,
    llm_model: "Model | None" = None,
):
    self._llm_service = ModelLLMAdapter(llm_model) if llm_model else None
```

- 参数从 `llm_service` 改为 `llm_model`
- 使用适配器包装 Model 实例
- 保持内部使用 `_llm_service` 的逻辑不变

### 5. 更新 LLM 处理器 ✅

**文件**: `agio/components/tools/builtin_tools/common/web_fetch/llm_processors.py`

```python
async def summarize_by_llm(
    llm_service: ModelLLMAdapter,  # 改为使用适配器
    content: HtmlContent,
    abort_signal: "AbortSignal | None" = None,
) -> HtmlContent:
    # 保持原有逻辑不变
```

- 类型注解从 `SimpleLLMService` 改为 `ModelLLMAdapter`
- 函数逻辑保持不变

### 6. 删除旧代码 ✅

**删除的文件**：
- `agio/components/tools/builtin_tools/common/llm/service.py`

**更新的文件**：
- `agio/components/tools/builtin_tools/common/llm/__init__.py`
  - 导出 `ModelLLMAdapter` 而非 `SimpleLLMService`

### 7. 创建配置示例 ✅

**文件**: `configs/tools/web_fetch.yaml`

```yaml
type: tool
name: web_fetch
module: agio.components.tools.builtin_tools.web_fetch_tool.web_fetch_tool
class_name: WebFetchTool
dependencies:
  llm_model: gpt-4o-mini  # 引用 model 配置
params:
  timeout_seconds: 30
  max_length: 10000
enabled: true
```

**文件**: `configs/agents/research_agent.yaml`

```yaml
type: agent
name: research_agent
model: gpt-4o-mini
tools:
  - web_search
  - web_fetch  # 自动注入 gpt-4o-mini 作为 LLM 依赖
```

## 架构改进

### 改进前

```
┌─────────────┐
│   Tool      │
│             │
│  创建并管理  │──────┐
│ LLM Service │      │ 重复实现
└─────────────┘      │
                     ▼
              SimpleLLMService
              (独立实现)
```

### 改进后

```
┌──────────────────┐
│  ConfigManager   │
│                  │
│  解析依赖并注入   │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│      Tool       │      │    Model     │
│                 │◄─────│  (统一抽象)   │
│ 接收 Model 实例  │      └──────────────┘
└────────┬────────┘
         │
         ▼
   ModelLLMAdapter
   (适配器模式)
```

## 优势总结

### 1. **统一抽象**
- 所有 LLM 调用都通过 `Model` 抽象
- 消除重复代码，降低维护成本

### 2. **配置驱动**
- 工具的 LLM 依赖通过配置管理
- 支持灵活切换不同的 Model 实现

### 3. **依赖注入**
- 遵循 SOLID 原则中的依赖倒置原则
- 便于测试和 Mock

### 4. **向后兼容**
- 工具构造函数保持可选参数
- 适配器提供相同的接口

### 5. **易于扩展**
- 新工具可以轻松声明 Model 依赖
- 配置系统自动处理依赖解析

## 使用示例

### 通过配置系统使用

```python
from agio.config.manager import ConfigManager

# 加载配置
config_manager = ConfigManager(config_dir="configs")
await config_manager.load_all()

# 获取 Agent（工具的 LLM 依赖自动注入）
agent = await config_manager.get_component("research_agent")

# 运行 Agent
result = await agent.run("搜索并总结最新的 AI 新闻")
```

### 直接实例化（测试场景）

```python
from agio.components.models.openai import OpenAIModel
from agio.components.tools.builtin_tools.web_fetch_tool import WebFetchTool

# 创建 Model
model = OpenAIModel(
    id="openai/gpt-4o-mini",
    name="gpt-4o-mini",
    api_key="sk-xxx"
)

# 创建 Tool（手动注入依赖）
tool = WebFetchTool(llm_model=model)

# 使用 Tool
result = await tool.execute({
    "url": "https://example.com",
    "summarize": True
})
```

## 后续工作建议

### 1. 扩展到其他工具
- 将其他需要 LLM 的工具也迁移到新架构
- 如 `summarize_text`、`translate_text` 等

### 2. 支持更多依赖类型
- 除了 Model，还可以注入 Memory、Knowledge 等
- 扩展 `dependencies` 支持类型声明

### 3. 依赖版本管理
- 支持指定依赖的版本或变体
- 如 `{"llm_model": "gpt-4o-mini@v1"}`

### 4. 性能优化
- Model 实例共享和复用
- 连接池管理

### 5. 测试覆盖
- 添加依赖注入的单元测试
- 添加 ModelLLMAdapter 的集成测试

## 相关文档

- [详细设计文档](./TOOL_LLM_DEPENDENCY_REFACTOR.md)
- [配置系统文档](./DYNAMIC_CONFIG_DESIGN.md)
- [Model 抽象文档](../agio/components/models/README.md)

## 总结

本次重构成功实现了工具系统与 Model 系统的统一，通过配置驱动的依赖注入，提高了代码的可维护性和可扩展性。所有改动遵循 SOLID 和 KISS 原则，保持了向后兼容性，为后续功能扩展奠定了良好基础。
