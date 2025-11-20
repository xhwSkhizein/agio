# Agio 流式事件协议

## 概述

Agio 提供统一的事件流协议，用于实时流式输出和历史回放。所有事件都遵循相同的 JSON 结构，便于前端统一处理。

## 核心设计

### 统一事件模型

```python
class AgentEvent:
    type: EventType          # 事件类型
    run_id: str             # 运行 ID
    timestamp: datetime     # 时间戳
    data: Dict[str, Any]    # 事件负载
    metadata: Dict[str, Any] # 可选元数据
```

### 事件类型

| 类型 | 说明 | 何时触发 |
|------|------|----------|
| `run_started` | Run 开始 | Agent 开始执行 |
| `run_completed` | Run 完成 | Agent 成功完成 |
| `run_failed` | Run 失败 | Agent 执行失败 |
| `run_cancelled` | Run 取消 | 用户取消执行 |
| `step_started` | Step 开始 | 新的推理步骤开始 |
| `step_completed` | Step 完成 | 推理步骤完成 |
| `text_delta` | 文本增量 | LLM 流式输出文本 |
| `text_completed` | 文本完成 | LLM 文本输出完成 |
| `tool_call_started` | 工具调用开始 | 开始执行工具 |
| `tool_call_completed` | 工具调用完成 | 工具执行完成 |
| `tool_call_failed` | 工具调用失败 | 工具执行失败 |
| `usage_update` | Token 使用更新 | LLM 返回 token 统计 |
| `metrics_snapshot` | Metrics 快照 | 定期或步骤结束时 |
| `error` | 错误 | 发生错误 |
| `warning` | 警告 | 发生警告 |
| `debug` | 调试信息 | 调试模式下 |

## 事件详细说明

### 1. run_started

**触发时机**: Agent 开始执行

**数据结构**:
```json
{
  "type": "run_started",
  "run_id": "uuid-string",
  "timestamp": "2025-11-20T18:00:00.000Z",
  "data": {
    "query": "用户查询内容"
  },
  "metadata": {}
}
```

### 2. text_delta

**触发时机**: LLM 流式输出每个文本片段

**数据结构**:
```json
{
  "type": "text_delta",
  "run_id": "uuid-string",
  "timestamp": "2025-11-20T18:00:01.123Z",
  "data": {
    "content": "Hello",
    "step": 1
  },
  "metadata": {}
}
```

**前端处理**:
```javascript
if (event.type === 'text_delta') {
  appendText(event.data.content);
}
```

### 3. tool_call_started

**触发时机**: 开始执行工具调用

**数据结构**:
```json
{
  "type": "tool_call_started",
  "run_id": "uuid-string",
  "timestamp": "2025-11-20T18:00:02.456Z",
  "data": {
    "tool_name": "get_weather",
    "tool_call_id": "call_123",
    "arguments": {
      "city": "Beijing"
    },
    "step": 1
  },
  "metadata": {}
}
```

**前端处理**:
```javascript
if (event.type === 'tool_call_started') {
  showToolCallIndicator(event.data.tool_name);
}
```

### 4. tool_call_completed

**触发时机**: 工具执行完成

**数据结构**:
```json
{
  "type": "tool_call_completed",
  "run_id": "uuid-string",
  "timestamp": "2025-11-20T18:00:03.789Z",
  "data": {
    "tool_name": "get_weather",
    "tool_call_id": "call_123",
    "result": "The weather in Beijing is sunny",
    "duration": 0.123,
    "step": 1
  },
  "metadata": {}
}
```

### 5. usage_update

**触发时机**: LLM 返回 token 使用统计

**数据结构**:
```json
{
  "type": "usage_update",
  "run_id": "uuid-string",
  "timestamp": "2025-11-20T18:00:04.000Z",
  "data": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150,
    "step": 1
  },
  "metadata": {}
}
```

### 6. run_completed

**触发时机**: Agent 成功完成执行

**数据结构**:
```json
{
  "type": "run_completed",
  "run_id": "uuid-string",
  "timestamp": "2025-11-20T18:00:05.000Z",
  "data": {
    "response": "完整的响应文本",
    "metrics": {
      "duration": 5.14,
      "steps_count": 2,
      "tool_calls_count": 2,
      "total_tokens": 360,
      "response_latency": 1071
    }
  },
  "metadata": {}
}
```

### 7. error

**触发时机**: 发生错误

**数据结构**:
```json
{
  "type": "error",
  "run_id": "uuid-string",
  "timestamp": "2025-11-20T18:00:06.000Z",
  "data": {
    "error": "错误信息",
    "error_type": "ValueError"
  },
  "metadata": {}
}
```

## 使用示例

### Python 客户端

```python
import asyncio
from agio.agent import Agent
from agio.protocol.events import EventType

async def main():
    agent = Agent(...)
    
    async for event in agent.arun_stream("你好"):
        if event.type == EventType.TEXT_DELTA:
            print(event.data['content'], end='', flush=True)
        elif event.type == EventType.TOOL_CALL_STARTED:
            print(f"\n[调用工具: {event.data['tool_name']}]")
        elif event.type == EventType.RUN_COMPLETED:
            print(f"\n完成! 耗时: {event.data['metrics']['duration']}s")

asyncio.run(main())
```

### JavaScript/TypeScript 客户端

```typescript
interface AgentEvent {
  type: string;
  run_id: string;
  timestamp: string;
  data: Record<string, any>;
  metadata: Record<string, any>;
}

async function streamAgent(query: string) {
  const response = await fetch('/api/agent/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const event: AgentEvent = JSON.parse(line.slice(6));
        handleEvent(event);
      }
    }
  }
}

function handleEvent(event: AgentEvent) {
  switch (event.type) {
    case 'text_delta':
      appendText(event.data.content);
      break;
    case 'tool_call_started':
      showToolIndicator(event.data.tool_name);
      break;
    case 'run_completed':
      showMetrics(event.data.metrics);
      break;
  }
}
```

## Server-Sent Events (SSE) 格式

Agio 事件可以直接转换为 SSE 格式：

```python
event = AgentEvent(...)
sse_data = event.to_sse()
# 输出: "data: {\"type\": \"text_delta\", ...}\n\n"
```

### FastAPI 示例

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/agent/stream")
async def stream_agent(query: str):
    async def event_generator():
        agent = Agent(...)
        async for event in agent.arun_stream(query):
            yield event.to_sse()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

## 历史回放

事件流可以被持久化并用于历史回放：

```python
# 存储事件
async for event in agent.arun_stream(query):
    await storage.save_event(event)

# 回放事件
async for event in storage.get_events(run_id):
    # 前端使用相同的渲染逻辑
    render_event(event)
```

## 最佳实践

### 1. 前端渲染

- 使用相同的渲染逻辑处理实时和历史事件
- 根据 `timestamp` 排序事件
- 使用 `run_id` 区分不同的执行

### 2. 错误处理

- 监听 `error` 事件并显示错误信息
- 在 `run_completed` 后清理 UI 状态
- 处理网络断开和重连

### 3. 性能优化

- 批量处理 `text_delta` 事件以减少 DOM 更新
- 使用虚拟滚动处理大量事件
- 限制历史事件的加载数量

### 4. 调试

- 启用 `debug` 事件查看详细信息
- 记录所有事件到控制台
- 使用 `metadata` 字段传递额外信息

## 版本兼容性

### 向后兼容

Agio 保持向后兼容的文本流 API：

```python
# 旧 API（仍然支持）
async for text in agent.arun(query):
    print(text, end='')

# 新 API（推荐）
async for event in agent.arun_stream(query):
    if event.type == EventType.TEXT_DELTA:
        print(event.data['content'], end='')
```

### 未来扩展

事件协议设计为可扩展的：

- 新的事件类型可以随时添加
- `data` 和 `metadata` 字段支持任意 JSON 数据
- 客户端可以忽略未知的事件类型

## 总结

Agio 的流式事件协议提供了：

- ✅ 统一的事件模型
- ✅ 丰富的事件类型
- ✅ 实时和历史统一处理
- ✅ 易于集成的 API
- ✅ 向后兼容性
- ✅ 可扩展性

这使得构建现代化的 Agent 应用变得简单而强大。
