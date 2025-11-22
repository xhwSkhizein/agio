# Backend Error Fixes

## 问题 1: 模型名称错误 ✅ 已修复

### 错误信息
```
Error code: 404 - {'error': {'message': 'The model `gpt4o-mini` does not exist or you do not have access to it.', 'type': 'invalid_request_error', 'param': None, 'code': 'model_not_found'}}
```

### 根本原因
模型名称拼写错误：`gpt4o-mini` 应该是 `gpt-4o-mini`

### 修复内容
更新了以下 6 个配置文件中的模型名称：

1. `configs/models/gpt-4o-mini.yaml` - 模型定义文件
   - `name: gpt4o-mini` → `name: gpt-4o-mini`
   - 标签: `gpt4o-mini` → `gpt-4o-mini`

2. `configs/agents/code_assistant.yaml`
3. `configs/agents/simple_assistant.yaml`
4. `configs/agents/customer_support.yaml`
5. `configs/agents/research_agent.yaml`
6. `test_phase1.py`

所有文件中的 `model: gpt4o-mini` 都已更新为 `model: gpt-4o-mini`

---

## 问题 2: 文件监视器重复初始化 ✅ 已修复

### 错误信息
```
ERROR:fsevents:Unhandled exception in FSEventsEmitter
RuntimeError: Cannot add watch <ObservedWatch: path='configs', is_recursive=True> - it is already scheduled
✓ Started watching configs for configuration changes
✓ Started watching configs for configuration changes
```

### 根本原因
- `DependencyContainer.initialize()` 可能被调用多次（例如在测试或热重载期间）
- 每次调用都会创建新的 `ConfigManager` 并启动文件监视器
- 导致尝试重复添加同一个监视路径

### 修复内容

#### 1. `agio/registry/watcher.py` - 添加重复启动守护
```python
def start(self) -> None:
    """Start watching for file changes."""
    # Guard: Don't start if already running
    if self._running and self.observer:
        print(f"⚠ File watcher already running for {self.watch_dir}")
        return
```

#### 2. `agio/api/dependencies.py` - 防止容器重复初始化
```python
def initialize(self, config_dir: str | Path):
    # Guard: Don't re-initialize if already done
    if self.config_manager is not None:
        return
```

---

## 验证

启动服务后应该看到：
- ✅ 只有一次 "Started watching configs for configuration changes"
- ✅ 没有 fsevents 错误
- ✅ 模型 `gpt-4o-mini` 正常工作

---

## 待办事项：Web 错误提示

用户请求添加 Web 端错误处理：
1. 添加 toast 提醒功能，在接口失败时显示错误信息
2. 在 console 中打印错误详情，方便 debug

**建议实现**:
- 使用 toast 库（如 react-hot-toast 或 sonner）
- 在 API 请求拦截器中捕获错误
- 显示用户友好的错误消息
- 在控制台记录完整的错误堆栈
