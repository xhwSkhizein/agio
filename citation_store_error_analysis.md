# Citation Store 错误链路分析报告

## 错误信息
```
Error: Citation store not available, cannot use index
```

## 错误发生位置

**文件**: `agio/providers/tools/builtin/web_fetch_tool/web_fetch_tool.py`  
**行号**: 165-170

```165:170:agio/providers/tools/builtin/web_fetch_tool/web_fetch_tool.py
if index is not None:
    if not self._citation_source_store:
        return self._create_error_result(
            parameters,
            "Citation store not available, cannot use index",
            start_time,
        )
```

## 问题根本原因

当 `web_fetch` 工具使用 `index` 参数时，需要通过 `citation_source_store` 查找对应的 URL。但工具实例的 `_citation_source_store` 属性为 `None`，导致无法使用 `index` 功能。

## 完整调用链路分析

### 1. 工具初始化链路

#### 1.1 WebFetchTool 构造函数
**文件**: `agio/providers/tools/builtin/web_fetch_tool/web_fetch_tool.py:61-82`

```61:82:agio/providers/tools/builtin/web_fetch_tool/web_fetch_tool.py
def __init__(
    self,
    *,
    settings: AppSettings | None = None,
    citation_source_store: "CitationSourceRepository | None" = None,
    llm_model: "Model | None" = None,
) -> None:
    super().__init__()
    self._settings = settings or SettingsRegistry.get()
    self._citation_source_store = citation_source_store
    # 使用适配器包装 Model
    self._llm_service = ModelLLMAdapter(llm_model) if llm_model else None
    self.category = ToolCategory.WEB
    self.risk_level = RiskLevel.MEDIUM

    # Core configuration
    self.timeout_seconds = self._settings.tool.web_fetch_tool_timeout_seconds
    self.max_length = self._settings.tool.web_fetch_max_content_length

    # HTTP 客户端和爬虫
    self._curl_cffi_client = SimpleAsyncClient()
    self._playwright_crawl = PlaywrightCrawler(settings=self._settings)
```

**关键点**:
- `citation_source_store` 是可选参数，默认为 `None`
- 如果调用时未传入，`self._citation_source_store` 就是 `None`

#### 1.2 工具创建入口 - ConfigSystem
**文件**: `agio/config/system.py:551-584`

```551:584:agio/config/system.py
async def _get_or_create_tool(self, tool_name: str) -> Any:
    """
    Get tool instance by name.
    
    Priority:
    1. Already built tool in ConfigSystem
    2. Tool config exists -> build it
    3. Built-in tool from registry -> create with default params
    """
    # 1. Check if already built
    if tool_name in self._instances:
        return self._instances[tool_name]

    # 2. Check if config exists -> build it
    tool_config = self.get_config(ComponentType.TOOL, tool_name)
    if tool_config:
        return await self._build_component(ComponentType.TOOL, tool_name)

    # 3. Try to create from registry (built-in tools)
    from agio.providers.tools import get_tool_registry
    registry = get_tool_registry()

    if registry.is_registered(tool_name):
        tool = registry.create(tool_name)
        # Cache the instance
        self._instances[tool_name] = tool
        logger.info(f"Created built-in tool: {tool_name}")
        return tool

    raise ComponentNotFoundError(
        f"Tool '{tool_name}' not found. "
        f"Available: configs={[n for (t, n) in self._configs.keys() if t == ComponentType.TOOL]}, "
        f"builtin={registry.list_builtin()}"
    )
```

**关键点**:
- 如果工具有配置文件，会通过 `_build_component` 构建（会解析依赖）
- 如果没有配置文件，直接从 registry 创建，**不会传入任何参数**

#### 1.3 工具构建器 - ToolBuilder
**文件**: `agio/config/builders.py:102-138`

```102:138:agio/config/builders.py
class ToolBuilder(ComponentBuilder):
    """Builder for tool components."""

    async def build(self, config: ToolConfig, dependencies: dict[str, Any]) -> Any:
        """
        Build tool instance with dependency injection.
        
        Supports two modes:
        1. Built-in tools: Use `tool_name` to reference registered tools
        2. Custom tools: Use `module` and `class_name` for dynamic import
        """
        try:
            # Get tool class
            tool_class = self._get_tool_class(config)

            # Merge parameters: config.params + resolved dependencies
            kwargs = {**config.effective_params}
            
            # Resolve dependencies: map param names to resolved instances
            # dependencies dict is keyed by param_name, not dep_name
            for param_name, dep_name in config.effective_dependencies.items():
                if param_name not in dependencies:
                    raise ComponentBuildError(
                        f"Dependency '{dep_name}' (param: {param_name}) not found for tool '{config.name}'"
                    )
                kwargs[param_name] = dependencies[param_name]

            # Filter kwargs to only include valid parameters
            kwargs = self._filter_valid_params(tool_class, kwargs)

            # Instantiate with merged params
            return tool_class(**kwargs)

        except ComponentBuildError:
            raise
        except Exception as e:
            raise ComponentBuildError(f"Failed to build tool {config.name}: {e}")
```

**关键点**:
- `ToolBuilder` 会根据 `config.effective_dependencies` 注入依赖
- 依赖解析在 `ConfigSystem._resolve_dependencies` 中进行

#### 1.4 依赖解析 - ConfigSystem._resolve_dependencies
**文件**: `agio/config/system.py:450-453`

```450:453:agio/config/system.py
elif isinstance(config, ToolConfig):
    # Tool dependencies (e.g., llm_model)
    for param_name, dep_name in config.effective_dependencies.items():
        dependencies[param_name] = self.get(dep_name)
```

**关键点**:
- 只解析配置文件中声明的依赖
- 如果配置文件中没有声明 `citation_source_store` 依赖，就不会注入

### 2. 配置文件分析

#### 2.1 web_fetch.yaml
**文件**: `configs/tools/web_fetch.yaml`

```yaml
type: tool
name: web_fetch
description: "Fetch and process web content with optional LLM processing"
tool_name: web_fetch
dependencies:
  llm_model: deepseek  # Reference to model config for content summarization
params:
  # timeout_seconds: 30
  # max_content_length: 4096
enabled: true
tags:
  - web
  - content
  - llm-enhanced
```

**问题**: 
- 只配置了 `llm_model` 依赖
- **没有配置 `citation_source_store` 依赖**

#### 2.2 web_search.yaml
**文件**: `configs/tools/web_search.yaml`

```yaml
type: tool
name: web_search
description: "Search the web for information using Serper API"
tool_name: web_search
params:
  # Requires SERPER_API_KEY environment variable
  # max_results: 10
enabled: true
tags:
  - search
  - web
  - research
```

**问题**:
- **没有配置任何依赖**
- `WebSearchTool` 也需要 `citation_source_store` 来存储搜索结果

### 3. Citation Store 实现分析

#### 3.1 协议定义
**文件**: `agio/providers/tools/builtin/common/citation/protocols.py:14-126`

定义了 `CitationSourceRepository` 协议，包含以下方法：
- `store_citation_sources()` - 存储信息源
- `get_citation_source()` - 通过 citation_id 获取
- `get_simplified_sources()` - 获取简化版信息源
- `get_session_citations()` - 获取 session 的所有 citations
- `update_citation_source()` - 更新信息源
- `get_source_by_index()` - **通过索引获取信息源（关键方法）**
- `cleanup_session()` - 清理 session

#### 3.2 内存实现
**文件**: `agio/providers/tools/builtin/common/citation/memory_store.py`

`InMemoryCitationStore` 实现了协议，但：
- 只在内存中存储，不持久化
- 没有在 ConfigSystem 中注册为组件类型
- 无法通过配置文件创建

#### 3.3 缺失的组件
- **没有 MongoDB 持久化实现**
- **没有在 ConfigSystem 中注册为组件类型**
- **没有对应的 Builder**

### 4. 工具使用场景分析

#### 4.1 WebSearchTool 的使用
**文件**: `agio/providers/tools/builtin/web_search_tool/web_search_tool.py:304-353`

```304:353:agio/providers/tools/builtin/web_search_tool/web_search_tool.py
if self._citation_source_store:
    try:
        # 获取当前 session 的最大 index
        existing_sources = (
            await self._citation_source_store.get_session_citations(session_id)
        )
        start_index = (
            max(
                (s.index for s in existing_sources if s.index is not None),
                default=-1,
            )
            + 1
            if existing_sources
            else 0
        )

        # 转换为 CitationSourceRaw 模型
        citation_sources = self._convert_to_citation_sources(
            raw_results, query, session_id, start_index
        )

        # 存储并获取 citation_ids
        citation_ids = await self._citation_source_store.store_citation_sources(
            sources=citation_sources,
        )

        # 获取简化结果
        simplified_results = (
            await self._citation_source_store.get_simplified_sources(
                citation_ids=citation_ids,
            )
        )

        logger.info(
            "citation_sources_stored_and_simplified",
            query=query,
            result_count=len(simplified_results),
            citation_ids=citation_ids,
        )
```

**关键点**:
- `WebSearchTool` 会将搜索结果存储到 `citation_source_store`
- 每个结果都有一个 `index`（0, 1, 2...）
- 如果没有 `citation_source_store`，搜索结果不会存储，但不会报错（降级处理）

#### 4.2 WebFetchTool 的使用
**文件**: `agio/providers/tools/builtin/web_fetch_tool/web_fetch_tool.py:162-182`

```162:182:agio/providers/tools/builtin/web_fetch_tool/web_fetch_tool.py
# 通过 index 获取 URL（如果有 store）
existing_source: CitationSourceRaw | None = None
if index is not None:
    if not self._citation_source_store:
        return self._create_error_result(
            parameters,
            "Citation store not available, cannot use index",
            start_time,
        )

    existing_source = await self._citation_source_store.get_source_by_index(
        session_id, index
    )
    if not existing_source:
        return self._create_error_result(
            parameters,
            f"Search result with index {index} not found",
            start_time,
        )
    url = existing_source.url
    logger.info(f"Found source by index {index}: {url}")
```

**关键点**:
- 当使用 `index` 参数时，**必须**有 `citation_source_store`
- 如果没有 store，直接返回错误（**不会降级**）

### 5. 错误触发场景

#### 场景 1: 使用 index 参数但没有配置 citation_source_store
```
1. Agent 调用 web_fetch(index=0)
2. WebFetchTool.execute() 被调用
3. 检测到 index 不为 None
4. 检测到 self._citation_source_store 为 None
5. 返回错误: "Citation store not available, cannot use index"
```

#### 场景 2: 先调用 web_search，再调用 web_fetch(index=0)
```
1. web_search 存储结果到 citation_source_store（如果有）
2. web_fetch(index=0) 尝试从 store 获取 URL
3. 如果 store 为 None，报错
```

## 问题总结

### 核心问题
1. **工具配置缺失**: `web_fetch.yaml` 和 `web_search.yaml` 都没有配置 `citation_source_store` 依赖
2. **组件系统缺失**: `CitationSourceRepository` 没有在 ConfigSystem 中注册为组件类型
3. **实现不完整**: 只有内存实现，没有持久化实现，也没有对应的 Builder

### 设计不一致
- `WebSearchTool`: 没有 store 时降级处理（不存储，但继续工作）
- `WebFetchTool`: 没有 store 时直接报错（使用 index 时）

### 依赖注入链路断裂
```
配置文件 (web_fetch.yaml)
  ↓ (缺少 citation_source_store 依赖声明)
ConfigSystem._resolve_dependencies()
  ↓ (不会解析 citation_source_store)
ToolBuilder.build()
  ↓ (不会注入 citation_source_store)
WebFetchTool.__init__()
  ↓ (citation_source_store = None)
WebFetchTool.execute(index=0)
  ↓ (检测到 None，报错)
```

## 解决方案建议

### 方案 1: 在配置文件中添加依赖（推荐）
1. 创建 `CitationStore` 组件类型和配置
2. 在 `web_fetch.yaml` 和 `web_search.yaml` 中添加依赖声明
3. 创建 `CitationStoreBuilder` 来构建实例

### 方案 2: 提供默认实现
1. 在 `ToolBuilder` 中检测工具是否需要 `citation_source_store`
2. 如果没有配置，自动创建 `InMemoryCitationStore` 实例

### 方案 3: 降级处理
1. 修改 `WebFetchTool`，当没有 store 且使用 index 时，提示用户使用 `url` 参数

## 相关文件清单

### 核心文件
- `agio/providers/tools/builtin/web_fetch_tool/web_fetch_tool.py` - WebFetchTool 实现
- `agio/providers/tools/builtin/web_search_tool/web_search_tool.py` - WebSearchTool 实现
- `agio/providers/tools/builtin/common/citation/protocols.py` - CitationSourceRepository 协议
- `agio/providers/tools/builtin/common/citation/memory_store.py` - InMemoryCitationStore 实现

### 配置系统文件
- `agio/config/system.py` - ConfigSystem 核心逻辑
- `agio/config/builders.py` - ToolBuilder 实现
- `agio/config/schema.py` - 配置模型定义

### 配置文件
- `configs/tools/web_fetch.yaml` - web_fetch 工具配置
- `configs/tools/web_search.yaml` - web_search 工具配置

## 结论

这是一个**依赖注入配置缺失**的问题。`WebFetchTool` 和 `WebSearchTool` 都需要 `citation_source_store` 来支持 `index` 功能，但：
1. 配置文件中没有声明这个依赖
2. ConfigSystem 中没有注册 CitationStore 组件类型
3. 工具创建时无法自动注入依赖

需要完善配置系统和组件注册机制，或者提供默认实现来解决这个问题。

