from typing import List, AsyncIterator
from collections import defaultdict
import asyncio
import time

from agio.core.loop import ModelDriver, LoopConfig
from agio.core.events import ModelEvent, ModelEventType
from agio.models.base import Model
from agio.tools.base import Tool
from agio.domain.messages import Message, AssistantMessage, ToolMessage
from agio.execution.tool_executor import ToolExecutor
from agio.utils.logger import log_debug, log_error, log_info

class OpenAIModelDriver(ModelDriver):
    def __init__(self, model: Model):
        self.model = model
    
    def _is_fatal_error(self, error: Exception) -> bool:
        """
        判断错误是否为致命错误。
        致命错误会中断执行，非致命错误会继续。
        """
        error_type = type(error).__name__
        
        # 致命错误类型
        fatal_errors = {
            "AuthenticationError",
            "PermissionError",
            "RateLimitError",
            "InvalidRequestError",
            "KeyboardInterrupt",
            "SystemExit",
        }
        
        # 非致命错误（可重试）
        non_fatal_errors = {
            "TimeoutError",
            "ConnectionError",
            "APIError",
        }
        
        if error_type in fatal_errors:
            return True
        elif error_type in non_fatal_errors:
            return False
        else:
            # 默认为致命错误（保守策略）
            return True

    async def run(
        self, 
        messages: List[Message], 
        tools: List[Tool], 
        config: LoopConfig
    ) -> AsyncIterator[ModelEvent]:
        executor = ToolExecutor(tools)
        current_step = 0
        
        # Metrics 累积
        total_tokens = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        step_start_time = time.time()
        
        try:
            while current_step < config.max_steps:
                current_step += 1
                step_start_time = time.time()
                log_debug(f"ModelDriver: Starting step {current_step}")
            
                full_content = ""
                tool_calls_accumulator = defaultdict(
                    lambda: {
                        "id": None,
                        "function": {"name": "", "arguments": ""},
                        "type": "function",
                    }
                )
                
                try:
                    async for delta in self.model.astream(
                        messages, 
                        tools=tools, 
                        **config.model_dump(exclude={'max_steps', 'stop_sequences', 'extra_params'})
                    ):
                        if delta.content:
                            full_content += delta.content
                            yield ModelEvent(
                                type=ModelEventType.TEXT_DELTA,
                                content=delta.content,
                                step=current_step
                            )

                        if delta.tool_calls:
                            for tc in delta.tool_calls:
                                index = tc.get("index", 0)
                                acc = tool_calls_accumulator[index]

                                if tc.get("id"):
                                    acc["id"] = tc["id"]
                                if tc.get("function"):
                                    fn = tc["function"]
                                    if fn.get("name"):
                                        acc["function"]["name"] += fn["name"]
                                    if fn.get("arguments"):
                                        acc["function"]["arguments"] += fn["arguments"]
                        
                        if delta.usage:
                            # 累积 token 统计
                            total_prompt_tokens += delta.usage.get("prompt_tokens", 0)
                            total_completion_tokens += delta.usage.get("completion_tokens", 0)
                            total_tokens += delta.usage.get("total_tokens", 0)
                            
                            yield ModelEvent(
                                type=ModelEventType.USAGE,
                                usage=delta.usage,
                                step=current_step
                            )

                except Exception as e:
                    error_type = type(e).__name__
                    error_msg = str(e)
                    is_fatal = self._is_fatal_error(e)
                    
                    log_error(f"ModelDriver: {error_type} in step {current_step}: {error_msg}")
                    
                    yield ModelEvent(
                        type=ModelEventType.ERROR,
                        content=error_msg,
                        step=current_step,
                        metadata={
                            "error_type": error_type,
                            "is_fatal": is_fatal,
                            "step": current_step
                        }
                    )
                    
                    if is_fatal:
                        log_error(f"ModelDriver: Fatal error, stopping execution")
                        break
                    else:
                        log_info(f"ModelDriver: Non-fatal error, continuing...")
                        continue
            
                final_tool_calls = []
                for idx in sorted(tool_calls_accumulator.keys()):
                    entry = tool_calls_accumulator[idx]
                    if entry["id"]:
                        final_tool_calls.append({
                            "id": entry["id"],
                            "type": entry["type"],
                            "function": {
                                "name": entry["function"]["name"],
                                "arguments": entry["function"]["arguments"],
                            },
                        })
                
                assistant_msg = AssistantMessage(
                    content=full_content if full_content else None,
                    tool_calls=final_tool_calls if final_tool_calls else None,
                )
                messages.append(assistant_msg)

                if not final_tool_calls:
                    log_debug(f"ModelDriver: No tool calls, finishing at step {current_step}")
                    # 发送最终 metrics 快照
                    step_duration = time.time() - step_start_time
                    yield ModelEvent(
                        type=ModelEventType.METRICS_SNAPSHOT,
                        step=current_step,
                        metadata={
                            "total_tokens": total_tokens,
                            "total_prompt_tokens": total_prompt_tokens,
                            "total_completion_tokens": total_completion_tokens,
                            "current_step": current_step,
                            "tool_calls_count": 0,
                            "step_duration": round(step_duration, 3),
                            "timestamp": time.time()
                        }
                    )
                    break
                
                yield ModelEvent(
                    type=ModelEventType.TOOL_CALL_STARTED,
                    tool_calls=final_tool_calls,
                    step=current_step
                )

                tool_results = await executor.execute_batch(final_tool_calls)
                
                for tr in tool_results:
                    yield ModelEvent(
                        type=ModelEventType.TOOL_CALL_FINISHED,
                        tool_result=tr.model_dump(),
                        step=current_step
                    )
                    messages.append(
                        ToolMessage(tool_call_id=tr.tool_call_id, content=tr.content)
                    )
                
                # 发送 step 结束时的 metrics 快照
                step_duration = time.time() - step_start_time
                yield ModelEvent(
                    type=ModelEventType.METRICS_SNAPSHOT,
                    step=current_step,
                    metadata={
                        "total_tokens": total_tokens,
                        "total_prompt_tokens": total_prompt_tokens,
                        "total_completion_tokens": total_completion_tokens,
                        "current_step": current_step,
                        "tool_calls_count": len(final_tool_calls),
                        "step_duration": round(step_duration, 3),
                        "timestamp": time.time()
                    }
                )
        
            if current_step >= config.max_steps:
                log_debug(f"ModelDriver: Reached max steps ({config.max_steps})")
        
        except asyncio.CancelledError:
            log_info(f"ModelDriver: Execution cancelled at step {current_step}")
            yield ModelEvent(
                type=ModelEventType.ERROR,
                content="Execution cancelled by user",
                step=current_step,
                metadata={
                    "error_type": "CancelledError",
                    "is_fatal": True,
                    "step": current_step
                }
            )
            raise
