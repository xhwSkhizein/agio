# 动态配置系统 - 架构详解

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client / Frontend                        │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/REST
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Layer                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  POST /api/config/{type}/{name}  - 创建/更新配置        │   │
│  │  GET  /api/config/{type}/{name}  - 获取配置             │   │
│  │  DELETE /api/config/{type}/{name} - 删除配置            │   │
│  │  GET  /api/config                 - 列出配置             │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ConfigManager (核心)                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  • save_config()    - 保存配置                          │   │
│  │  • get_config()     - 获取配置                          │   │
│  │  • delete_config()  - 删除配置                          │   │
│  │  • list_configs()   - 列出配置                          │   │
│  │  • _validate_config()        - 配置验证                 │   │
│  │  • _validate_dependencies()  - 依赖验证                 │   │
│  │  • _find_dependents()        - 查找被依赖               │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────┬───────────────────────────┬────────────────────┘
                 │                           │
                 ▼                           ▼
┌────────────────────────────┐  ┌──────────────────────────────┐
│   ConfigRepository         │  │      EventBus                │
│  ┌─────────────────────┐   │  │  ┌───────────────────────┐  │
│  │ • save_config()     │   │  │  │ • publish()           │  │
│  │ • get_config()      │   │  │  │ • subscribe()         │  │
│  │ • delete_config()   │   │  │  │ • unsubscribe()       │  │
│  │ • list_configs()    │   │  │  └───────────────────────┘  │
│  │ • get_history()     │   │  │                              │
│  └─────────────────────┘   │  │  Subscribers:                │
│           │                 │  │  - ComponentRegistry         │
│           ▼                 │  │  - MetricsCollector          │
│  ┌─────────────────────┐   │  │  - AuditLogger               │
│  │    MongoDB          │   │  └──────────────────────────────┘
│  │  - configs          │   │
│  │  - config_history   │   │
│  └─────────────────────┘   │
└────────────────────────────┘
                 │
                 │ ConfigChangeEvent
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ComponentRegistry (注册中心)                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  • get()                    - 获取组件实例              │   │
│  │  • register()               - 注册组件                  │   │
│  │  • unregister()             - 注销组件                  │   │
│  │  • _handle_config_change()  - 处理配置变更             │   │
│  │  • _rebuild_component()     - 重建组件                  │   │
│  │  • _wait_for_tasks()        - 等待任务完成             │   │
│  │  • track_task_start/end()   - 追踪任务                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  内部状态:                                                        │
│  • _instances: {name: instance}        - 组件实例缓存           │
│  • _component_states: {name: state}    - 组件状态               │
│  • _active_tasks: {name: count}        - 运行中任务计数         │
│  • _dependency_graph: DependencyGraph  - 依赖图                 │
└────────────┬──────────────────────────┬─────────────────────────┘
             │                          │
             ▼                          ▼
┌────────────────────────┐  ┌──────────────────────────────────┐
│  DependencyGraph       │  │    ComponentFactory              │
│  ┌──────────────────┐  │  │  ┌────────────────────────────┐  │
│  │ • add_node()     │  │  │  │ • create()                 │  │
│  │ • remove_node()  │  │  │  │ • _resolve_dependencies()  │  │
│  │ • get_affected() │  │  │  └────────────────────────────┘  │
│  │ • _has_cycle()   │  │  │                                  │
│  │ • _topo_sort()   │  │  │  Builders:                       │
│  └──────────────────┘  │  │  • ModelBuilder                  │
│                        │  │  • ToolBuilder                   │
│  数据结构:              │  │  • MemoryBuilder                 │
│  • _dependencies       │  │  • KnowledgeBuilder              │
│  • _dependents         │  │  • HookBuilder                   │
│  • _component_types    │  │  • AgentBuilder                  │
└────────────────────────┘  └──────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Component Instances                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Agent   │  │  Model   │  │   Tool   │  │  Memory  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │Knowledge │  │   Hook   │  │ Storage  │  │Repository│        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心组件职责

### 1. ConfigManager
**职责**: 配置管理的门面，协调所有配置操作

**关键方法**:
- `save_config()` - 验证、保存、发布事件
- `_validate_config()` - Pydantic 验证
- `_validate_dependencies()` - 检查依赖存在性
- `_find_dependents()` - 查找被依赖关系

**关键特性**:
- 分布式锁防止并发冲突
- 乐观锁防止版本冲突
- 自动回滚失败更新

### 2. ComponentRegistry
**职责**: 组件实例的注册中心，管理生命周期

**关键方法**:
- `get()` - 获取组件实例（带状态检查）
- `register()` - 注册新组件
- `unregister()` - 注销组件（带清理）
- `_handle_config_change()` - 处理配置变更事件
- `_rebuild_component()` - 重建组件

**关键特性**:
- 任务追踪（_active_tasks）
- 优雅等待（_wait_for_tasks）
- 状态管理（ACTIVE/PENDING_REBUILD/DEPRECATED/DISABLED）

### 3. DependencyGraph
**职责**: 管理组件依赖关系图

**关键方法**:
- `add_node()` - 添加节点（带循环检测）
- `get_affected_components()` - 计算影响范围（BFS）
- `_has_cycle()` - 循环依赖检测（DFS）
- `_topological_sort()` - 拓扑排序

**关键特性**:
- 双向依赖图（_dependencies + _dependents）
- 循环依赖检测
- 拓扑排序保证重建顺序

### 4. ComponentFactory
**职责**: 根据配置构建组件实例

**关键方法**:
- `create()` - 创建组件实例
- `_resolve_dependencies()` - 解析依赖

**关键特性**:
- 依赖注入
- 多种 Builder 支持不同组件类型

### 5. ConfigRepository
**职责**: 配置持久化到 MongoDB

**关键方法**:
- `save_config()` - 保存配置 + 历史
- `get_config()` - 获取配置
- `list_configs()` - 查询配置
- `get_history()` - 获取历史版本

**关键特性**:
- 版本管理
- 历史记录
- 查询过滤

### 6. EventBus
**职责**: 事件发布/订阅

**关键方法**:
- `publish()` - 发布事件
- `subscribe()` - 订阅事件
- `unsubscribe()` - 取消订阅

**关键特性**:
- 异步事件处理
- 多订阅者支持
- 解耦组件通信

---

## 数据流详解

### 配置更新流程

```
1. Client 发送 POST /api/config/agent/customer_support
   ↓
2. FastAPI 路由到 ConfigService
   ↓
3. ConfigService 调用 ConfigManager.save_config()
   ↓
4. ConfigManager 验证配置
   - Pydantic 模型验证
   - 依赖存在性检查
   ↓
5. ConfigManager 保存到 ConfigRepository
   - 保存到 MongoDB.configs
   - 保存历史到 MongoDB.config_history
   ↓
6. ConfigManager 发布 ConfigChangeEvent
   - EventBus.publish("config.changed", event)
   ↓
7. ComponentRegistry 接收事件
   - EventBus 调用 _handle_config_change()
   ↓
8. ComponentRegistry 分析影响
   - DependencyGraph.get_affected_components()
   - 返回: [customer_support, dependent_agent_1, ...]
   ↓
9. ComponentRegistry 标记状态
   - _component_states[name] = PENDING_REBUILD
   ↓
10. ComponentRegistry 等待任务
    - _wait_for_tasks_completion(affected, timeout=30)
    - 监控 _active_tasks 计数
    ↓
11. ComponentRegistry 重建组件
    - 按拓扑顺序遍历 affected
    - 对每个组件: unregister() → register()
    ↓
12. ComponentFactory 构建新实例
    - _resolve_dependencies() 获取依赖
    - Builder.build() 创建实例
    ↓
13. ComponentRegistry 更新状态
    - _component_states[name] = ACTIVE
    - _instances[name] = new_instance
    ↓
14. 新配置生效
    - 新请求使用新组件实例
```

### 组件获取流程

```
1. Agent.arun() 调用
   ↓
2. ComponentRegistry.get("customer_support")
   ↓
3. 检查组件状态
   - ACTIVE → 返回实例
   - PENDING_REBUILD → 抛出 ComponentNotReadyError
   - DISABLED → 抛出 ComponentDisabledError
   - DEPRECATED → 记录警告，返回实例
   ↓
4. 追踪任务开始
   - track_task_start("customer_support")
   - _active_tasks["customer_support"] += 1
   ↓
5. 执行 Agent 逻辑
   ↓
6. 追踪任务结束
   - track_task_end("customer_support")
   - _active_tasks["customer_support"] -= 1
```

---

## 依赖关系示例

### 示例配置

```yaml
# Model
gpt4:
  type: model
  provider: openai
  model_name: gpt-4

# Tools
search_tool:
  type: tool
  module: agio.tools.search
  
ticket_tool:
  type: tool
  module: agio.tools.ticket

# Memory
redis_memory:
  type: memory
  backend: redis

# Knowledge
product_docs:
  type: knowledge
  backend: chroma

# Storage (新增)
redis_storage:
  type: storage
  storage_type: redis
  redis_url: ${AGIO_REDIS_URL}

# Repository (新增)
mongodb_repo:
  type: repository
  repository_type: mongodb
  mongo_uri: ${AGIO_MONGO_URI}
  mongo_db_name: agio

# Agent
customer_support:
  type: agent
  model: gpt4
  tools: [search_tool, ticket_tool]
  memory: redis_memory
  knowledge: product_docs
  storage: redis_storage      # 新增
  repository: mongodb_repo    # 新增
```

### 依赖图

```
customer_support (Agent)
    ├── gpt4 (Model)
    ├── search_tool (Tool)
    ├── ticket_tool (Tool)
    ├── redis_memory (Memory)
    ├── product_docs (Knowledge)
    ├── redis_storage (Storage)      # 新增
    └── mongodb_repo (Repository)    # 新增
```

### 影响分析

**场景**: 更新 `gpt4` 配置

**分析过程**:
1. DependencyGraph.get_affected_components("gpt4")
2. BFS 遍历反向依赖:
   - gpt4 → customer_support
   - customer_support → (无更多依赖)
3. 返回: ["gpt4", "customer_support"]
4. 拓扑排序: ["gpt4", "customer_support"]
5. 重建顺序: 先 gpt4，后 customer_support

---

## 状态机

### 组件状态转换

```
         [配置创建]
              ↓
          ACTIVE ←──────────────┐
              ↓                  │
    [配置更新事件]              │
              ↓                  │
      PENDING_REBUILD           │
              ↓                  │
       [等待任务完成]            │
              ↓                  │
        [重建组件]               │
              ↓                  │
          ACTIVE ────────────────┘
              ↓
       [配置禁用]
              ↓
          DISABLED
              ↓
       [配置删除]
              ↓
          [组件注销]
```

### 任务追踪

```
Task Start
    ↓
_active_tasks[name] += 1
    ↓
[执行任务]
    ↓
Task End
    ↓
_active_tasks[name] -= 1
    ↓
[检查是否为 0]
    ↓
[允许重建]
```

---

## 并发控制

### 配置更新锁

```python
# ConfigManager
_update_locks: dict[str, asyncio.Lock]

async def save_config(self, config_type, name, ...):
    lock_key = f"{config_type}:{name}"
    async with self._update_locks[lock_key]:
        # 执行更新逻辑
        ...
```

### 组件重建锁

```python
# ComponentRegistry
_rebuild_locks: dict[str, asyncio.Lock]

async def _rebuild_component(self, name):
    async with self._rebuild_locks[name]:
        # 执行重建逻辑
        ...
```

### 乐观锁

```python
# ConfigRepository
async def save_config(self, ..., expected_version):
    current = await self.get_config(...)
    if current.version != expected_version:
        raise ConfigVersionConflictError(...)
```

---

## 错误处理

### 异常层次

```
ConfigError (基类)
├── ConfigValidationError      # 配置验证失败
├── ConfigNotFoundError        # 配置不存在
├── ConfigVersionConflictError # 版本冲突
├── ConfigInUseError           # 配置被使用
├── DependencyNotFoundError    # 依赖不存在
├── CircularDependencyError    # 循环依赖
└── ConfigSaveError            # 保存失败

ComponentError (基类)
├── ComponentNotFoundError     # 组件不存在
├── ComponentNotReadyError     # 组件未就绪
├── ComponentDisabledError     # 组件已禁用
├── ComponentBusyError         # 组件繁忙
└── ComponentBuildError        # 构建失败
```

### 回滚机制

```python
async def save_config(self, ...):
    old_config = await self.repository.get_config(...)
    
    try:
        # 更新配置
        await self.repository.save_config(...)
        
        # 触发重建
        await self.event_bus.publish(...)
    
    except Exception as e:
        # 回滚配置
        if old_config:
            await self.repository.save_config(..., old_config)
        raise
```

---

## 性能考虑

### 缓存策略

1. **配置缓存** - 内存缓存热点配置
2. **依赖图缓存** - 预计算依赖关系
3. **验证结果缓存** - 避免重复验证

### 批量操作

1. **批量加载** - 启动时并行加载所有配置
2. **批量更新** - 支持一次更新多个配置
3. **批量重建** - 合并重建请求

### 异步处理

1. **异步事件** - 事件处理不阻塞 API
2. **后台重建** - 重建任务放入队列
3. **异步清理** - 资源清理异步执行

---

## 监控和可观测性

### 关键指标

1. **配置指标**
   - 配置更新 QPS
   - 配置更新延迟（P50/P95/P99）
   - 配置更新失败率

2. **组件指标**
   - 组件重建次数
   - 组件重建延迟
   - 运行中任务数

3. **依赖指标**
   - 依赖图节点数
   - 依赖图边数
   - 影响分析延迟

### 日志记录

```python
logger.info(f"Config change detected: {event.change_type} {event.config_type}:{event.name}")
logger.info(f"Affected components: {affected}")
logger.info(f"Rebuilding component '{name}'...")
logger.info(f"Component '{name}' rebuilt successfully")
logger.error(f"Failed to rebuild component '{name}': {e}")
```

---

## 总结

这个架构设计的核心思想是:

1. **分层解耦** - API、配置管理、注册中心、工厂、组件实例
2. **事件驱动** - 配置变更通过事件总线通知
3. **依赖管理** - 自动分析影响，按序重建
4. **优雅重载** - 等待任务完成，不中断服务
5. **类型安全** - Pydantic 验证，编译时检查
6. **可观测性** - 完整的日志、指标、追踪

通过这个架构，我们可以实现:
- ✅ 配置动态更新，无需重启
- ✅ 自动处理依赖关系
- ✅ 防止循环依赖
- ✅ 优雅等待运行中任务
- ✅ 配置版本管理
- ✅ 完整的错误处理和回滚
