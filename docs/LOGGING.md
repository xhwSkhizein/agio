# Agio Logging Best Practices

## 日志框架

Agio 使用 [structlog](https://www.structlog.org/) 作为统一的日志框架，提供结构化、可扩展的日志记录能力。

## 快速开始

### 基础用法

```python
from agio.utils.logging import get_logger

logger = get_logger(__name__)

# ✅ 推荐：结构化日志
logger.info("user_authenticated", user_id="user_123", session_id="sess_456")
logger.debug("processing_items", count=10, batch_size=100)
logger.error("operation_failed", error=str(e), component="database", exc_info=True)

# ❌ 不推荐：字符串格式化
logger.info(f"User user_123 authenticated")
```

### 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| **DEBUG** | 详细的调试信息（生产环境禁用） | 函数参数、内部状态 |
| **INFO** | 一般信息消息（正常操作） | 启动完成、任务处理 |
| **WARNING** | 警告信息（可恢复问题） | 弃用警告、降级使用 |
| **ERROR** | 错误信息（不中断应用） | API 调用失败、数据验证错误 |
| **CRITICAL** | 严重错误（可能导致应用中止） | 数据库连接失败、配置缺失 |

## 日志编写指南

### 1. 使用结构化键值对

**⛔ 错误示例**
```python
logger.info(f"Processing order {order_id} for user {user_id}, amount: ${amount}")
```

**✅ 正确示例**
```python
logger.info("order_processing", 
    order_id=order_id,
    user_id=user_id,
    amount=amount,
    currency="USD"
)
```

**优势**：
- 可机器解析和聚合
- 支持日志搜索和过滤
- 便于指标提取

### 2. 事件命名规范

使用 `snake_case` 命名，描述发生的事件，而非当前状态：

```python
# ✅ 推荐
logger.info("user_login_success", user_id=user_id)
logger.info("config_reload_started", config_path=path)
logger.error("database_connection_failed", host=db_host, port=db_port)

# ❌ 不推荐
logger.info("logging in")
logger.info("Config")
logger.error("error")
```

### 3. 错误日志最佳实践

**包含完整上下文**
```python
try:
    await process_payment(order_id, amount)
except Exception as e:
    logger.error(
        "payment_processing_failed",
        order_id=order_id,
        amount=amount,
        error=str(e),
        error_type=type(e).__name__,
        exc_info=True  # 自动添加堆栈跟踪
    )
    raise
```

**`exc_info=True` 的作用**：
- 自动记录完整的异常堆栈
- 在开发环境显示彩色输出
- 在生产环境输出 JSON 格式

### 4. 敏感数据保护

以下数据会被自动过滤：
- `password`
- `api_key`, `apikey`
- `secret`
- `token`, `access_token`, `refresh_token`
- `authorization`, `auth`

```python
# 自动过滤敏感字段
logger.info("api_call", 
    url="/api/users",
    api_key="sk-xxx..."  # 输出: api_key="***REDACTED***"
)
```

**手动过滤其他敏感数据**：
```python
logger.info("user_data_updated",
    user_id=user_id,
    email=mask_email(email),  # 自行实现 mask 函数
    phone=phone[-4:]  # 只记录后4位
)
```

### 5. 请求上下文跟踪

使用 `set_request_context` 自动为所有日志添加上下文：

```python
from agio.utils.logging import set_request_context, clear_request_context

# 在请求开始时
set_request_context(
    request_id="req_abc123",
    user_id="user_456",
    session_id="sess_789"
)

# 后续的所有日志会自动包含这些字段
logger.info("api_call_started")  
# 输出包含: request_id="req_abc123", user_id="user_456"

# 请求结束时清理
clear_request_context()
```

### 6. 性能监控

**记录耗时操作**
```python
import time

start_time = time.time()
result = await expensive_operation()
duration = time.time() - start_time

logger.info("operation_completed",
    operation="data_sync",
    duration_ms=int(duration * 1000),
    items_processed=len(result)
)
```

**使用上下文管理器**（可选扩展）
```python
# 可以创建一个计时装饰器
from agio.utils.logging import get_logger
import functools
import time

def log_timing(event_name: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                logger.info(f"{event_name}_completed",
                    duration_ms=int((time.time() - start) * 1000)
                )
                return result
            except Exception as e:
                logger.error(f"{event_name}_failed",
                    duration_ms=int((time.time() - start) * 1000),
                    error=str(e)
                )
                raise
        return wrapper
    return decorator

# 使用
@log_timing("user_registration")
async def register_user(email: str):
    ...
```

## 配置

### 环境变量

```bash
# 日志级别
export LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# JSON格式输出（生产环境推荐）
export LOG_JSON=true

# 日志文件路径（可选）
export LOG_FILE=/var/log/agio/app.log
```

### 代码配置

```python
from agio.utils.logging import configure_logging

# 开发环境：彩色控制台输出
configure_logging(
    log_level="DEBUG",
    json_logs=False
)

# 生产环境：JSON 格式输出到文件
configure_logging(
    log_level="INFO",
    json_logs=True,
    log_file="/var/log/agio/app.log"
)
```

## 实际示例

### Agent 执行日志

```python
from agio.utils.logging import get_logger

logger = get_logger(__name__)

class AgentRunner:
    async def run(self, query: str, session_id: str):
        logger.info("agent_run_started",
            agent_id=self.agent.id,
            session_id=session_id,
            query_length=len(query)
        )
        
        try:
            result = await self.execute(query)
            
            logger.info("agent_run_completed",
                agent_id=self.agent.id,
                session_id=session_id,
                tokens_used=result.tokens,
                duration_ms=result.duration_ms,
                tool_calls=len(result.tool_calls)
            )
            
            return result
            
        except Exception as e:
            logger.error("agent_run_failed",
                agent_id=self.agent.id,
                session_id=session_id,
                error=str(e),
                exc_info=True
            )
            raise
```

### 配置加载日志

```python
def reload_configs(self, config_dir: Path):
    logger.info("config_reload_started", 
        config_dir=str(config_dir),
        auto_reload=self.auto_reload
    )
    
    results = {}
    for file in config_dir.glob("**/*.yaml"):
        try:
            config = self.load_file(file)
            results[config.name] = True
            logger.debug("config_loaded",
                config_name=config.name,
                config_type=config.type,
                file_path=str(file)
            )
        except Exception as e:
            results[file.name] = False
            logger.error("config_load_failed",
                file_path=str(file),
                error=str(e),
                exc_info=True
            )
    
    success_count = sum(1 for v in results.values() if v)
    logger.info("config_reload_completed",
        total=len(results),
        success=success_count,
        failed=len(results) - success_count
    )
```

## 日志查询与分析

### 开发环境（控制台）

日志会以彩色、易读的格式输出：

```
2025-11-21 18:00:01 [info     ] agent_run_started         agent_id=simple_assistant session_id=sess_123
2025-11-21 18:00:02 [debug    ] tool_execution_started    tool=web_search query=weather
2025-11-21 18:00:03 [info     ] agent_run_completed       duration_ms=2000 tokens_used=150
```

### 生产环境（JSON）

JSON 格式便于日志聚合和查询：

```json
{
  "event": "agent_run_started",
  "agent_id": "simple_assistant",
  "session_id": "sess_123",
  "timestamp": "2025-11-21T18:00:01.123Z",
  "level": "info",
  "logger": "agio.runners.base"
}
```

**日志聚合工具**（推荐）：
- **ELK Stack** (Elasticsearch + Logstash + Kibana)
- **Datadog**
- **CloudWatch Logs**
- **Grafana Loki**

## 常见问题

### 1. 如何在异步函数中使用日志？

完全相同，structlog 是线程/协程安全的：

```python
async def async_function():
    logger.info("async_operation_started")
    await asyncio.sleep(1)
    logger.info("async_operation_completed")
```

### 2. 如何为不同模块设置不同日志级别？

```python
import logging

# 设置特定模块的日志级别
logging.getLogger("agio.registry").setLevel(logging.DEBUG)
logging.getLogger("agio.models").setLevel(logging.WARNING)
```

### 3. 如何禁止第三方库的日志？

```python
import logging

# 禁止 httpx 的日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
```

## 迁移指南

### 从 print 迁移

```python
# 旧代码
print(f"Processing {count} items")
print(f"✓ Completed in {duration}s")
print(f"Error: {e}")

# 新代码
logger.info("processing_items", count=count)
logger.info("processing_completed", duration=duration)
logger.error("processing_failed", error=str(e), exc_info=True)
```

### 从标准 logging 迁移

```python
# 旧代码
import logging
logger = logging.getLogger(__name__)
logger.info(f"User {user_id} logged in")

# 新代码
from agio.utils.logging import get_logger
logger = get_logger(__name__)
logger.info("user_logged_in", user_id=user_id)
```

## 总结

**日志记录的黄金法则**：
1. ✅ 使用结构化键值对，不用字符串拼接
2. ✅ 事件名称描述发生了什么
3. ✅ 错误日志包含完整上下文和堆栈
4. ✅ 保护敏感数据
5. ✅ 记录关键指标（耗时、数量、成功率）​​​​​​​​​​​​​​​​
