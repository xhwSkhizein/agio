## 问题分析

### 1. 当前循环依赖情况

根据 review 文档和代码分析，主要的循环依赖包括：

#### 1.1 config ↔ tools 循环依赖

**依赖链**：
```
config/system.py
  └─► import get_tool_registry from tools/__init__.py
        └─► tools/builtin/*.py
              └─► (某些工具可能需要配置)

config/builders.py
  └─► import from tools.builtin.config
  └─► import get_tool_registry from tools/__init__.py
```

**当前缓解措施**：
- 延迟导入（在函数内部 import）
- 但本质上是"打补丁"，并未解决设计问题

**根本原因**：
- `config` 需要知道如何构建 `tools`
- `tools` 的某些实现需要引用配置系统
- 职责边界不清晰

#### 1.2 agent ↔ runtime 潜在循环

**依赖链**：
```
agent/agent.py
  └─► 使用 runtime/protocol.py (ExecutionContext, RunOutput)
  └─► 使用 runtime/wire.py

runtime/runnable_executor.py
  └─► 需要知道 Runnable 的具体类型（Agent/Workflow）
```

**当前状态**：
- 通过 Protocol 抽象避免了直接循环
- 但仍然存在紧耦合

---

### 2. 循环依赖的危害

1. **模块职责不清晰**
   - 难以理解模块的真实边界
   - 违反单一职责原则

2. **测试困难**
   - 需要复杂的 mock 设置
   - 单元测试变成集成测试

3. **重构风险高**
   - 修改一个模块可能影响多个模块
   - 难以进行局部重构

4. **IDE 支持差**
   - 自动补全可能失效
   - 类型检查困难

---

## 解决方案

### 方案 1：提取共享抽象层（推荐）

#### 1.1 设计原则

**依赖倒置原则（DIP）**：
- 高层模块不依赖低层模块，两者都依赖抽象
- 抽象不依赖细节，细节依赖抽象

**接口隔离原则（ISP）**：
- 客户端不应该依赖它不需要的接口
- 接口应该小而专注

#### 1.2 创建独立的抽象层

**目录结构**：
```
agio/
├── protocols/              # 新增：共享协议和接口
│   ├── __init__.py
│   ├── runnable.py        # Runnable 协议
│   ├── tool.py            # Tool 协议
│   ├── model.py           # Model 协议
│   ├── storage.py         # Storage 协议
│   └── registry.py        # Registry 协议
├── config/
│   ├── system.py          # 依赖 protocols
│   └── builders.py        # 依赖 protocols
├── tools/
│   ├── base.py            # 依赖 protocols
│   └── builtin/
├── agent/
│   └── agent.py           # 依赖 protocols
└── runtime/
    └── protocol.py        # 移动到 protocols/
```

**依赖关系**：
```
protocols (抽象层)
    ↑
    ├─ config
    ├─ tools
    ├─ agent
    └─ runtime
```

#### 1.3 具体实现

**1. 提取 Tool 协议**

```python
# agio/protocols/tool.py
from abc import ABC, abstractmethod
from typing import Any, Protocol

class ToolProtocol(Protocol):
    """工具协议，定义工具的最小接口"""
    
    @property
    def name(self) -> str:
        """工具名称"""
        ...
    
    @property
    def description(self) -> str:
        """工具描述"""
        ...
    
    async def execute(
        self,
        parameters: dict[str, Any],
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> "ToolResult":
        """执行工具"""
        ...

class ToolRegistry(Protocol):
    """工具注册表协议"""
    
    def register(self, name: str, tool: ToolProtocol) -> None:
        """注册工具"""
        ...
    
    def get(self, name: str) -> ToolProtocol:
        """获取工具"""
        ...
    
    def is_registered(self, name: str) -> bool:
        """检查工具是否已注册"""
        ...
```

**2. 提取 Config 相关协议**

```python
# agio/protocols/config.py
from abc import ABC, abstractmethod
from typing import Any, Protocol

class ComponentBuilder(Protocol):
    """组件构建器协议"""
    
    async def build(self, config: Any, dependencies: dict[str, Any]) -> Any:
        """构建组件"""
        ...
    
    async def cleanup(self, instance: Any) -> None:
        """清理组件"""
        ...

class ComponentContainer(Protocol):
    """组件容器协议"""
    
    def register(self, name: str, instance: Any, metadata: Any) -> None:
        """注册组件"""
        ...
    
    def get(self, name: str) -> Any:
        """获取组件"""
        ...
    
    def has(self, name: str) -> bool:
        """检查组件是否存在"""
        ...
```

**3. 重构 config/system.py**

```python
# agio/config/system.py
from agio.protocols.tool import ToolRegistry  # 依赖抽象
from agio.protocols.config import ComponentBuilder

class ConfigSystem:
    def __init__(self, tool_registry: ToolRegistry):
        """依赖注入 ToolRegistry"""
        self._tool_registry = tool_registry
        # ...
    
    async def _build_tool(self, config: ToolConfig, dependencies: dict) -> Any:
        # 不直接导入 tools 模块
        # 通过 tool_registry 获取工具类
        if config.tool_name:
            tool_class = self._tool_registry.get_tool_class(config.tool_name)
        else:
            # 动态加载
            tool_class = self._load_tool_class(config.module, config.class_name)
        
        # 构建实例
        return tool_class(**params)
```

**4. 重构 tools/__init__.py**

```python
# agio/tools/__init__.py
from agio.protocols.tool import ToolProtocol, ToolRegistry

class DefaultToolRegistry:
    """工具注册表实现（不依赖 config）"""
    
    def __init__(self):
        self._tools: dict[str, type[ToolProtocol]] = {}
    
    def register(self, name: str, tool_class: type[ToolProtocol]) -> None:
        self._tools[name] = tool_class
    
    def get_tool_class(self, name: str) -> type[ToolProtocol]:
        return self._tools[name]
    
    def is_registered(self, name: str) -> bool:
        return name in self._tools

# 全局注册表
_tool_registry = DefaultToolRegistry()

def get_tool_registry() -> ToolRegistry:
    return _tool_registry
```

**5. 工具实现不再依赖 config**

```python
# agio/tools/builtin/bash_tool/bash_tool.py
from agio.protocols.tool import ToolProtocol  # 依赖抽象
from agio.tools.base import BaseTool

class BashTool(BaseTool):
    """Bash 工具实现"""
    
    def __init__(
        self,
        timeout_seconds: int = 60,
        max_output_length: int = 10000,
        # ... 其他参数
    ):
        # 不依赖 BashConfig，直接接受参数
        super().__init__(
            name="bash",
            description="Execute bash commands",
        )
        self.timeout_seconds = timeout_seconds
        self.max_output_length = max_output_length
    
    async def execute(self, parameters, context, abort_signal):
        # ... 实现
        pass
```

**6. Config 配置对象移到单独模块**

```python
# agio/config/tool_configs.py
from pydantic import BaseModel

class BashConfig(BaseModel):
    """Bash 工具配置（仅用于配置系统）"""
    timeout_seconds: int = 60
    max_output_length: int = 10000
    # ...

# 工具不再需要导入这些配置类
```


## 实施路线图

### 阶段 1：创建 protocols 抽象层

**Day 1-2**：
1. 创建 `agio/protocols/` 目录
2. 提取核心协议：
   - `runnable.py`：Runnable, ExecutionContext, RunOutput
   - `tool.py`：ToolProtocol, ToolRegistry
   - `model.py`：ModelProtocol
   - `storage.py`：SessionStore, TraceStore, CitationStore
   - `config.py`：ComponentBuilder, ComponentContainer

**Day 3-4**：
1. 更新 `runtime/protocol.py` 移动到 `protocols/runnable.py`
2. 更新所有导入语句（自动化脚本）
3. 验证无破坏性变更

**Day 5**：
1. 测试和验证
2. 文档更新

### 阶段 2：重构 config ↔ tools 循环依赖

**Week 1**：
1. 将工具配置类移到 `config/tool_configs.py`
2. 重构 `tools/base.py` 不依赖配置类
3. 工具构造函数接受简单参数，而非配置对象

**Week 2**：
1. 重构 `config/builders.py` 通过 ToolRegistry 获取工具类
2. 移除延迟导入
3. 测试和验证

### 阶段 3：验证和优化

**Day 1-3**：
1. 全量测试
2. 性能基准测试
3. 修复发现的问题

**Day 4-5**：
1. 文档更新
2. Code review
3. 发布

---

## 依赖关系图

### 优化前

```
┌─────────┐     ┌──────┐
│ config  │ ←──→│ tools│  ← 循环依赖
└─────────┘     └──────┘
     ↓              ↓
┌─────────┐     ┌──────┐
│ agent   │     │ ...  │
└─────────┘     └──────┘
```

### 优化后

```
        ┌───────────┐
        │ protocols │  ← 抽象层
        └───────────┘
             ↑
    ┌────────┼────────┐
    ↓        ↓        ↓
┌────────┐ ┌─────┐ ┌───────┐
│ config │ │tools│ │ agent │  ← 无循环依赖
└────────┘ └─────┘ └───────┘
```

---

## 测试策略

### 1. 模块隔离测试

**测试 protocols 层**：
```python
# tests/protocols/test_tool.py
def test_tool_protocol():
    """测试 Tool 协议定义"""
    # 验证协议签名
    assert hasattr(ToolProtocol, "execute")
    # ...
```

**测试 config 层（不依赖 tools）**：
```python
# tests/config/test_builders.py
def test_tool_builder_with_mock():
    """使用 mock ToolRegistry 测试 ToolBuilder"""
    mock_registry = MockToolRegistry()
    builder = ToolBuilder(tool_registry=mock_registry)
    
    config = ToolConfig(tool_name="mock_tool")
    result = await builder.build(config, {})
    
    assert result is not None
```

**测试 tools 层（不依赖 config）**：
```python
# tests/tools/test_bash_tool.py
def test_bash_tool_initialization():
    """测试 Bash 工具初始化（不依赖配置对象）"""
    tool = BashTool(
        timeout_seconds=30,
        max_output_length=5000,
    )
    
    assert tool.timeout_seconds == 30
    assert tool.max_output_length == 5000
```

### 2. 集成测试

```python
# tests/integration/test_config_tool_integration.py
async def test_config_builds_tool():
    """集成测试：ConfigSystem 构建 Tool"""
    config_sys = ConfigSystem()
    await config_sys.load_from_directory("./test_configs")
    
    tool = config_sys.get_instance("bash")
    assert isinstance(tool, ToolProtocol)
    
    result = await tool.execute({"command": "echo test"}, context, None)
    assert "test" in result.output
```