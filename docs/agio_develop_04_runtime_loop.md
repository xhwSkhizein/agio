# Agio 开发文档 04: Agent Runtime Loop 设计

本模块详细设计 `Agent.arun()` 的内部执行流程。这是 Agio 的心脏。
基于 README 中的 13 步逻辑，我们将其重构为纯异步流式实现。

## 1. 核心流程概览 (The Loop)

```python
async def arun(self, query: str, user_id: str = None) -> AsyncIterator[str]:
    """
    Async Stream Implementation of the Agent Run Loop
    """
    # 1. 初始化 Run & Context
    run = self._create_run(query, user_id)
    session = await self._get_or_create_session(user_id)
    
    try:
        # 2. Pre-hooks
        await self._execute_pre_hooks(run)
        
        # 3. 准备 Messages & Tools
        messages = await self._prepare_messages(run, session)
        tools = self._get_tools(run)
        
        # 4. 异步启动 Memory/Knowledge 任务 (Fire and forget via Background Tasks)
        # 注意：在 Asyncio 中，我们使用 create_task 并管理引用，避免阻塞主回路
        bg_tasks = []
        if self.memory:
            bg_tasks.append(asyncio.create_task(self.memory.add_user_memory(run)))

        # 5. 推理循环 (Reasoning & Tool Execution Loop)
        # 这是一个 while 循环，直到模型决定停止或达到最大步数
        async for chunk in self._run_step_loop(run, messages, tools):
            yield chunk
            
        # 6. Post-hooks
        await self._execute_post_hooks(run)
        
        # 7. 等待后台任务完成 (可选，或让它们在后台继续运行)
        # await asyncio.gather(*bg_tasks, return_exceptions=True)
        
        # 8. 存储 Run 结果
        run.status = RunStatus.COMPLETED
        await self.storage.upsert_run(run)
        
        # 9. 生成 Session Summary (Async)
        asyncio.create_task(self._generate_session_summary(session))

    except Exception as e:
        run.status = RunStatus.FAILED
        run.error = str(e)
        yield f"[ERROR] {str(e)}"
    finally:
        # Telemetry & Cleanup
        self._log_telemetry(run)
```

## 2. 步骤详解 (Step-by-Step Implementation Detail)

### Step 1-3: 上下文组装
*   **Messages**: 自动拼接 System Prompt + History (from Memory) + RAG Context (from Knowledge) + Current User Query。
*   **Optimization**: 所有的 I/O 操作 (读库、读向量库) 并行执行 (`asyncio.gather`)。

### Step 4: 背景任务 (Background Tasks)
*   Agio 使用 `asyncio.create_task` 来处理非阻塞任务（如：生成长时记忆、文化背景分析）。
*   **关键点**: 需要维护一个 `background_tasks` 集合，防止任务被 GC 回收，并在 Agent 销毁时正确清理。

### Step 5: 执行循环 (`_run_step_loop`)
这是最复杂的每一步 (Step) 的处理：

1.  **Model Call**: 调用 `model.astream(messages, tools)`。
2.  **Stream Handling**: 实时 `yield` 文本块给用户。
3.  **Tool Call Detection**: 收集流中的 Tool Call chunks。
4.  **Tool Execution**: 
    *   一旦检测到工具调用完成，暂停 yield 文本。
    *   **并行执行** 所有工具调用 (`asyncio.gather(*tool_coroutines)`)。
    *   将工具结果追加到 `messages` 中。
    *   **递归/循环**: 再次调用 Model，传入包含工具结果的新消息列表。
5.  **Metrics Update**: 每一步结束后，更新 Token 消耗和耗时统计。

### Step 6-9: 收尾与持久化
*   **Session Summary**: 这是一个独立的 LLM 调用，用于总结当前对话，压缩历史。它不应该阻塞用户收到最终响应，所以必须是完全异步的后台任务。

## 3. 异常处理与恢复
*   **Graceful Shutdown**: 处理 `asyncio.CancelledError`，确保在用户断开连接时，Run 的状态能被正确标记为 `cancelled` 并保存。
*   **Tool Error**: 单个工具失败不应导致整个 Run 崩溃，应将错误信息作为 Tool Output 反馈给模型，让模型自我修正。

