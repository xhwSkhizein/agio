# Trace 增量保存机制

## 概述

为了提高系统的健壮性，Trace 采用了**增量保存**策略，而不是等到执行完成才一次性保存。这样即使 Agent 执行过程中失败或被中断，已经完成的部分也能被记录下来。

## 设计原则

### 旧设计的问题
- ❌ 只在 `TraceCollector.stop()` 时保存一次
- ❌ 如果执行失败或异常退出，整个 Trace 数据丢失
- ❌ 调试困难，无法看到失败前的执行状态

### 新设计的优势
- ✅ 在关键检查点增量保存
- ✅ 即使执行失败，已完成部分仍然保留
- ✅ 更好的可观测性和调试能力
- ✅ 使用异步后台任务，不阻塞主流程
- ✅ 保存失败不会中断执行

## 保存检查点

Trace 会在以下关键事件时自动保存：

1. **`RUN_STARTED`** - Agent 开始执行
   - 保存初始状态
   - 记录 agent_id、session_id、input_query 等元数据

2. **`STEP_COMPLETED`** - 每个 Step 完成
   - 保存 LLM 调用结果
   - 保存工具调用结果
   - 累积 Span 信息

3. **`RUN_COMPLETED`** - 正常完成
   - 保存最终状态
   - 记录完整的执行路径

4. **`RUN_FAILED`** - 执行失败
   - 保存失败状态
   - 记录错误信息

## 实现细节

### 代码位置
- `/agio/observability/collector.py` - `TraceCollector.collect()` 方法

### 关键代码
```python
async def collect(self, event: StepEvent) -> None:
    # ... 处理事件 ...
    
    # 增量保存检查点
    should_save = event.type in {
        StepEventType.RUN_STARTED,
        StepEventType.STEP_COMPLETED,
        StepEventType.RUN_COMPLETED,
        StepEventType.RUN_FAILED,
    }
    
    if should_save and self.store:
        # 后台异步保存，不阻塞主流程
        asyncio.create_task(self._save_trace_safe())
```

### 保存策略
- 使用 MongoDB 的 `upsert=True`，同一 trace_id 会被更新而不是重复插入
- 异步后台任务避免阻塞事件流处理
- 保存失败只记录日志，不中断执行

## 性能考虑

### 写入频率
- 典型场景：3-10 次保存 / 每次对话
  - 1x RUN_STARTED
  - 1-5x STEP_COMPLETED (取决于 LLM 调用和工具调用次数)
  - 1x RUN_COMPLETED/RUN_FAILED
  - 1x stop() 最终保存

### 性能优化
1. **异步写入**：使用 `asyncio.create_task()` 不阻塞主流程
2. **Upsert 操作**：MongoDB 批量更新同一文档
3. **内存缓存**：TraceStore 维护内存 ring buffer，读取优先从缓存
4. **错误隔离**：保存失败不影响执行继续

### 监控指标
可以通过日志监控：
- `trace_incremental_save_failed` - 增量保存失败（警告级别）
- `trace_save_failed` - 最终保存失败（错误级别）

## 使用示例

### 正常情况
```python
collector = TraceCollector(store=trace_store)
collector.start(trace_id="xxx", agent_id="yyy")

# 每个关键事件都会触发保存
await collector.collect(run_started_event)   # 保存 #1
await collector.collect(step_completed_1)     # 保存 #2
await collector.collect(step_completed_2)     # 保存 #3
await collector.collect(run_completed_event)  # 保存 #4

await collector.stop()  # 保存 #5 (最终确认)
```

### 失败场景
```python
collector = TraceCollector(store=trace_store)
collector.start(trace_id="xxx", agent_id="yyy")

await collector.collect(run_started_event)   # ✅ 已保存
await collector.collect(step_completed_1)     # ✅ 已保存
# 此时发生异常，执行中断

# 查询 Trace
trace = await trace_store.get_trace("xxx")
# ✅ 仍然能看到前 2 个事件的数据
# trace.spans 包含已完成的 Span
# trace.status 可能是 UNSET 或 ERROR
```

## 测试

运行增量保存测试：
```bash
uv run pytest tests/test_incremental_trace_save.py -v
```

测试覆盖：
- ✅ 关键检查点触发保存
- ✅ 非检查点事件不触发保存  
- ✅ 保存失败不中断执行

## 最佳实践

1. **监控保存日志**：关注 `trace_incremental_save_failed` 警告
2. **数据库性能**：确保 MongoDB 索引正确创建
3. **错误处理**：依赖增量保存，但不要假设每次都成功
4. **清理策略**：定期清理旧的 Trace 数据，避免数据库膨胀

## 未来改进

可能的优化方向：
- [ ] 批量写入：累积多个保存请求后批量提交
- [ ] 可配置策略：允许自定义保存频率或检查点
- [ ] 压缩存储：对大 Trace 进行压缩
- [ ] 分层存储：热数据内存，冷数据归档
