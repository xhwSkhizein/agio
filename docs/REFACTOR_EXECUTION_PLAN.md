# Agio 架构重构执行计划

> **文档版本**: 1.0  
> **创建时间**: 2026-01-05  
> **状态**: 待执行

---

## 重构目标

基于架构评审，本次重构聚焦于两个核心问题：

1. **消除循环依赖**：通过提取 `protocols` 抽象层，彻底解决 `config ↔ tools` 循环依赖
2. **ConfigSystem 插件化**：引入插件机制，提升扩展性，符合开闭原则

---

## 核心设计原则

- **依赖倒置原则（DIP）**：高层模块和低层模块都依赖抽象
- **开闭原则（OCP）**：开放扩展，关闭修改
- **接口隔离原则（ISP）**：接口小而专注
- **单一职责原则（SRP）**：每个模块职责清晰

---

## 架构变更概览

### 新增模块结构

```
agio/
├── protocols/              # 新增：共享协议和接口层
│   ├── __init__.py
│   ├── runnable.py        # Runnable, ExecutionContext, RunOutput
│   ├── tool.py            # ToolProtocol, ToolRegistry
│   ├── model.py           # ModelProtocol
│   ├── storage.py         # SessionStore, TraceStore, CitationStore
│   └── config.py          # ComponentBuilder, ComponentContainer
├── config/
│   ├── plugin.py          # 新增：插件系统
│   ├── builtin_plugins.py # 新增：内置插件
│   ├── tool_configs.py    # 新增：工具配置类（从 tools 移出）
│   ├── system.py          # 修改：使用插件机制
│   └── builders.py        # 修改：依赖 protocols
└── tools/
    ├── base.py            # 修改：不依赖 config
    └── builtin/           # 修改：工具接受简单参数
```

### 依赖关系变更

**重构前**：
```
config ←→ tools  (循环依赖)
```

**重构后**：
```
    protocols (抽象层)
        ↑
    ┌───┴───┐
config    tools  (无循环依赖)
```

---

## 执行计划

### 阶段 1：创建 protocols 抽象层（3-4 天）

#### Day 1：创建基础结构

**任务**：
1. 创建 `agio/protocols/` 目录和 `__init__.py`
2. 从 `runtime/protocol.py` 提取核心协议到 `protocols/runnable.py`：
   - `Runnable` Protocol
   - `ExecutionContext` dataclass
   - `RunOutput` dataclass
   - `RunnableType` enum

**验证**：
- 确保 `protocols/runnable.py` 可以独立导入
- 无循环依赖

**代码示例**：
```python
# agio/protocols/runnable.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

class RunnableType(Enum):
    AGENT = "agent"
    WORKFLOW = "workflow"

class Runnable(Protocol):
    @property
    def id(self) -> str: ...
    
    @property
    def runnable_type(self) -> RunnableType: ...
    
    async def run(
        self,
        input: str,
        *,
        context: "ExecutionContext",
    ) -> "RunOutput": ...

@dataclass(frozen=True)
class ExecutionContext:
    # ... (从 runtime/protocol.py 移动)
    pass

@dataclass
class RunOutput:
    # ... (从 runtime/protocol.py 移动)
    pass
```

---

#### Day 2：提取 Tool 和 Storage 协议

**任务**：
1. 创建 `protocols/tool.py`：
   - `ToolProtocol`
   - `ToolRegistry` Protocol
   - `ToolResult` dataclass

2. 创建 `protocols/storage.py`：
   - `SessionStore` Protocol
   - `TraceStore` Protocol
   - `CitationStore` Protocol

3. 创建 `protocols/model.py`：
   - `ModelProtocol`

**验证**：
- 所有协议定义清晰
- 无外部依赖

---

#### Day 3：提取 Config 协议

**任务**：
1. 创建 `protocols/config.py`：
   - `ComponentBuilder` Protocol
   - `ComponentContainer` Protocol

2. 更新 `protocols/__init__.py`，导出所有协议

**验证**：
- 协议层完整
- 可以独立测试

---

#### Day 4：更新现有代码导入

**任务**：
1. 更新 `runtime/protocol.py`：
   - 从 `protocols.runnable` 重新导出，保持向后兼容
   - 添加 deprecation warning

2. 批量更新导入语句：
   ```python
   # 旧导入
   from agio.runtime.protocol import Runnable, ExecutionContext
   
   # 新导入
   from agio.protocols.runnable import Runnable, ExecutionContext
   ```

3. 运行全量测试，确保无破坏性变更

**自动化脚本**：
```bash
# 批量替换导入语句
find agio -name "*.py" -exec sed -i '' \
  's/from agio\.runtime\.protocol import/from agio.protocols.runnable import/g' {} \;
```

**验证**：
- 所有测试通过
- 无导入错误

---

### 阶段 2：ConfigSystem 插件化（4-5 天）

#### Day 1：实现插件系统基础

**任务**：
1. 创建 `config/plugin.py`：
   - `ConfigPlugin` 抽象基类
   - `PluginRegistry` 实现
   - `register_plugin()` 全局函数
   - `get_plugin_registry()` 全局函数

2. 编写单元测试：
   - 测试插件注册
   - 测试插件查询
   - 测试重复注册检测

**代码**：
```python
# agio/config/plugin.py
from abc import ABC, abstractmethod
from typing import Any, Type
from agio.config.schema import ComponentType

class ConfigPlugin(ABC):
    @property
    @abstractmethod
    def component_type(self) -> ComponentType:
        """组件类型"""
        ...
    
    @property
    @abstractmethod
    def config_class(self) -> Type:
        """配置类"""
        ...
    
    @property
    @abstractmethod
    def builder_class(self) -> Type:
        """构建器类"""
        ...
    
    def validate_config(self, config) -> None:
        """验证配置（可选重写）"""
        pass

class PluginRegistry:
    def __init__(self):
        self._plugins: dict[ComponentType, ConfigPlugin] = {}
    
    def register(self, plugin: ConfigPlugin) -> None:
        component_type = plugin.component_type
        if component_type in self._plugins:
            raise ValueError(f"Plugin for {component_type} already registered")
        self._plugins[component_type] = plugin
    
    def get(self, component_type: ComponentType) -> ConfigPlugin:
        if component_type not in self._plugins:
            raise ValueError(f"No plugin registered for {component_type}")
        return self._plugins[component_type]
    
    def has(self, component_type: ComponentType) -> bool:
        return component_type in self._plugins

_plugin_registry = PluginRegistry()

def register_plugin(plugin: ConfigPlugin) -> None:
    _plugin_registry.register(plugin)

def get_plugin_registry() -> PluginRegistry:
    return _plugin_registry
```

**验证**：
- 单元测试通过
- 插件注册和查询正常工作

---

#### Day 2：实现内置插件

**任务**：
1. 创建 `config/builtin_plugins.py`：
   - `ModelPlugin`
   - `ToolPlugin`
   - `AgentPlugin`
   - `WorkflowPlugin`
   - `StoragePlugin`
   - `register_builtin_plugins()` 函数

2. 编写测试验证插件功能

**代码**：
```python
# agio/config/builtin_plugins.py
from agio.config.plugin import ConfigPlugin, register_plugin
from agio.config.schema import ComponentType, ModelConfig, ToolConfig, AgentConfig, WorkflowConfig
from agio.config.builders import ModelBuilder, ToolBuilder, AgentBuilder, WorkflowBuilder

class ModelPlugin(ConfigPlugin):
    @property
    def component_type(self) -> ComponentType:
        return ComponentType.MODEL
    
    @property
    def config_class(self):
        return ModelConfig
    
    @property
    def builder_class(self):
        return ModelBuilder

class ToolPlugin(ConfigPlugin):
    @property
    def component_type(self) -> ComponentType:
        return ComponentType.TOOL
    
    @property
    def config_class(self):
        return ToolConfig
    
    @property
    def builder_class(self):
        return ToolBuilder
    
    def validate_config(self, config: ToolConfig) -> None:
        if config.tool_name and (config.module or config.class_name):
            raise ValueError("Cannot specify both tool_name and module/class_name")

# ... 其他插件

def register_builtin_plugins():
    """注册所有内置插件"""
    register_plugin(ModelPlugin())
    register_plugin(ToolPlugin())
    register_plugin(AgentPlugin())
    register_plugin(WorkflowPlugin())
    # ... 其他插件
```

**验证**：
- 所有内置插件注册成功
- 插件验证逻辑正常工作

---

#### Day 3：重构 ConfigSystem

**任务**：
1. 修改 `config/system.py`：
   - 在 `__init__` 中初始化插件注册表
   - 移除硬编码的 `CONFIG_CLASSES` 字典
   - 修改 `_get_config_class()` 使用插件
   - 修改 `_build_component()` 使用插件

2. 在应用启动时调用 `register_builtin_plugins()`

**代码**：
```python
# agio/config/system.py
from agio.config.plugin import get_plugin_registry
from agio.config.schema import ComponentType

class ConfigSystem:
    def __init__(self):
        self.registry = ConfigRegistry()
        self.container = ComponentContainer()
        self.dependency_resolver = DependencyResolver()
        self.builder_registry = BuilderRegistry()
        self.hot_reload = HotReloadManager(...)
        self.plugin_registry = get_plugin_registry()
    
    def _get_config_class(self, component_type: ComponentType) -> Type:
        """动态获取配置类"""
        plugin = self.plugin_registry.get(component_type)
        return plugin.config_class
    
    async def _build_component(self, config, dependencies: dict) -> Any:
        """动态构建组件"""
        component_type = ComponentType(config.type)
        plugin = self.plugin_registry.get(component_type)
        
        # 验证配置
        plugin.validate_config(config)
        
        # 获取构建器
        builder = self.builder_registry.get(component_type)
        
        # 构建组件
        instance = await builder.build(config, dependencies)
        
        return instance
```

**验证**：
- ConfigSystem 初始化成功
- 组件构建正常工作
- 所有现有配置文件可以正常加载

---

#### Day 4-5：测试和文档

**任务**：
1. 编写集成测试：
   - 测试完整的配置加载流程
   - 测试第三方插件注册（示例）
   - 测试插件验证逻辑

2. 更新文档：
   - 插件开发指南
   - 迁移指南（如果有第三方扩展）

3. 性能基准测试：
   - 对比重构前后的配置加载性能
   - 确保无性能回退

**验证**：
- 所有测试通过
- 文档完整
- 性能符合预期

---

### 阶段 3：解决 config ↔ tools 循环依赖（5-6 天）

#### Day 1-2：移动工具配置类

**任务**：
1. 创建 `config/tool_configs.py`
2. 将所有工具配置类从 `tools/builtin/config.py` 移动到 `config/tool_configs.py`：
   - `BashConfig`
   - `FileReadConfig`
   - `FileWriteConfig`
   - `FileEditConfig`
   - `GrepConfig`
   - `LSConfig`
   - `GlobConfig`
   - `WebSearchConfig`
   - `WebFetchConfig`

3. 更新 `config/builders.py` 的导入：
   ```python
   # 旧导入
   from agio.tools.builtin.config import BashConfig, ...
   
   # 新导入
   from agio.config.tool_configs import BashConfig, ...
   ```

4. 保留 `tools/builtin/config.py` 作为兼容层（重新导出），添加 deprecation warning

**验证**：
- 配置类移动成功
- 向后兼容性保持
- 无导入错误

---

#### Day 3-4：重构工具实现

**任务**：
1. 修改 `tools/base.py`：
   - 移除对配置类的依赖
   - 工具构造函数接受简单参数

2. 逐个重构内置工具（以 `BashTool` 为例）：
   ```python
   # 重构前
   class BashTool(BaseTool, ConfigurableToolMixin):
       def __init__(self, config: BashConfig | None = None, **kwargs):
           self._config = self._init_config(BashConfig, config, **kwargs)
           self.timeout_seconds = self._config.timeout_seconds
   
   # 重构后
   class BashTool(BaseTool):
       def __init__(
           self,
           timeout_seconds: int = 60,
           max_output_length: int = 10000,
           allowed_commands: list[str] | None = None,
       ):
           super().__init__(name="bash", description="Execute bash commands")
           self.timeout_seconds = timeout_seconds
           self.max_output_length = max_output_length
           self.allowed_commands = allowed_commands
   ```

3. 更新 `config/builders.py` 中的 `ToolBuilder`：
   - 从配置对象提取参数
   - 传递给工具构造函数

**代码**：
```python
# agio/config/builders.py
class ToolBuilder(ComponentBuilder):
    async def build(self, config: ToolConfig, dependencies: dict) -> Any:
        tool_class = self._get_tool_class(config)
        
        # 从配置对象提取参数
        if config.tool_name == "bash":
            from agio.config.tool_configs import BashConfig
            bash_config = BashConfig(**config.params)
            tool = tool_class(
                timeout_seconds=bash_config.timeout_seconds,
                max_output_length=bash_config.max_output_length,
                allowed_commands=bash_config.allowed_commands,
            )
        # ... 其他工具
        
        return tool
```

**验证**：
- 工具初始化正常
- 配置参数正确传递
- 所有工具测试通过

---

#### Day 5：移除延迟导入

**任务**：
1. 检查所有延迟导入（函数内部 import）
2. 将延迟导入改为顶部导入
3. 验证无循环依赖

**查找延迟导入**：
```bash
# 查找函数内部的 import 语句
grep -r "def.*:" agio/config agio/tools | grep -A 10 "import"
```

**验证**：
- 无延迟导入
- 无循环依赖错误
- 所有测试通过

---

#### Day 6：集成测试和验证

**任务**：
1. 运行完整的测试套件
2. 手动测试关键场景：
   - 加载配置文件
   - 构建 Agent
   - 执行工具调用
   - 工作流编排

3. 性能基准测试

**验证**：
- 所有测试通过（164+ passed）
- 性能无回退
- 无循环依赖

---

### 阶段 4：清理和文档（2-3 天）

#### Day 1：代码清理

**任务**：
1. 移除废弃的兼容层（如果确认无外部依赖）
2. 清理未使用的导入
3. 统一代码风格（运行 ruff）

**命令**：
```bash
# 清理未使用的导入
ruff check --select F401 --fix agio/

# 格式化代码
ruff format agio/
```

---

#### Day 2：更新文档

**任务**：
1. 更新 `docs/ARCHITECTURE.md`：
   - 添加 protocols 层说明
   - 更新依赖关系图

2. 更新 `docs/CONFIG_SYSTEM_V2.md`：
   - 添加插件系统说明
   - 添加第三方插件开发指南

3. 创建迁移指南（如果需要）

---

#### Day 3：Code Review 和发布

**任务**：
1. 提交 Pull Request
2. Code Review
3. 修复反馈问题
4. 合并到主分支
5. 更新 CHANGELOG

---

## 测试策略

### 单元测试

**protocols 层**：
```python
# tests/protocols/test_tool.py
def test_tool_protocol():
    assert hasattr(ToolProtocol, "execute")
    assert hasattr(ToolProtocol, "name")
    assert hasattr(ToolProtocol, "description")
```

**插件系统**：
```python
# tests/config/test_plugin.py
def test_plugin_registration():
    registry = PluginRegistry()
    plugin = ModelPlugin()
    registry.register(plugin)
    assert registry.has(ComponentType.MODEL)

def test_duplicate_registration():
    registry = PluginRegistry()
    plugin = ModelPlugin()
    registry.register(plugin)
    with pytest.raises(ValueError):
        registry.register(plugin)
```

**工具重构**：
```python
# tests/tools/test_bash_tool.py
def test_bash_tool_init():
    tool = BashTool(timeout_seconds=30, max_output_length=5000)
    assert tool.timeout_seconds == 30
    assert tool.max_output_length == 5000
```

### 集成测试

```python
# tests/integration/test_config_tool_integration.py
async def test_config_builds_tool():
    config_sys = ConfigSystem()
    await config_sys.load_from_directory("./test_configs")
    
    tool = config_sys.get_instance("bash")
    assert isinstance(tool, BaseTool)
    
    result = await tool.execute({"command": "echo test"}, context, None)
    assert "test" in result.output
```

### 性能基准测试

```python
# tests/benchmarks/test_config_loading.py
import time

async def test_config_loading_performance():
    start = time.time()
    config_sys = ConfigSystem()
    await config_sys.load_from_directory("./examples/configs")
    duration = time.time() - start
    
    # 应该在 1 秒内完成
    assert duration < 1.0
```

---

## 风险管理

### 风险 1：大规模代码变更

**影响**：高  
**概率**：中

**缓解措施**：
- 分阶段实施，每个阶段独立测试
- 使用自动化脚本批量更新导入
- 充分的回归测试
- 保持向后兼容期（3-6 个月）

---

### 风险 2：性能回退

**影响**：中  
**概率**：低

**缓解措施**：
- 性能基准测试
- 插件查询使用 O(1) 字典查找
- 协议层无运行时开销（编译时优化）

---

### 风险 3：第三方代码兼容性

**影响**：中  
**概率**：低（当前无已知第三方扩展）

**缓解措施**：
- 保留兼容层，添加 deprecation warning
- 提供清晰的迁移指南
- 充分的过渡期

---

## 成功标准

### 功能完整性

- ✅ 所有现有功能正常工作
- ✅ 所有测试通过（164+ passed）
- ✅ 配置文件无需修改

### 架构改进

- ✅ 完全消除 config ↔ tools 循环依赖
- ✅ ConfigSystem 支持插件扩展
- ✅ 依赖关系清晰，符合 SOLID 原则

### 性能指标

- ✅ 配置加载性能无回退（< 1s）
- ✅ 工具执行性能无回退
- ✅ 内存占用无显著增加

### 可维护性

- ✅ 代码结构清晰
- ✅ 文档完整
- ✅ 易于扩展（第三方插件）

---

## 时间估算

| 阶段 | 任务 | 预计时间 |
|------|------|----------|
| 阶段 1 | 创建 protocols 抽象层 | 3-4 天 |
| 阶段 2 | ConfigSystem 插件化 | 4-5 天 |
| 阶段 3 | 解决循环依赖 | 5-6 天 |
| 阶段 4 | 清理和文档 | 2-3 天 |
| **总计** | | **14-18 天** |

---

## 后续优化（可选）

完成本次重构后，可以考虑以下优化（不在本次计划内）：

1. **Runnable 协议增强**：
   - 添加能力声明系统
   - 添加生命周期钩子
   - 实现中间件机制

2. **WorkflowState 优化**：
   - LRU 缓存淘汰
   - 按需加载

3. **API 版本控制**：
   - 设计 V2 API 规范
   - 统一错误响应格式

---

## 总结

本次重构聚焦于两个核心问题：

1. **消除循环依赖**：通过提取 protocols 抽象层，实现清晰的依赖关系
2. **ConfigSystem 插件化**：提升扩展性，支持第三方插件

重构遵循 SOLID 原则，分阶段实施，保持向后兼容，风险可控。

预计耗时 **14-18 天**，完成后将显著提升代码质量和可维护性。
