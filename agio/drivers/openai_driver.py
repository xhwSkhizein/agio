from typing import List, AsyncIterator
from collections import defaultdict

from agio.core.loop import ModelDriver, LoopConfig
from agio.core.events import ModelEvent, ModelEventType
from agio.models.base import Model
from agio.tools.base import Tool
from agio.domain.messages import Message, AssistantMessage, ToolMessage
from agio.execution.tool_executor import ToolExecutor
from agio.utils.logger import log_debug, log_error

class OpenAIModelDriver(ModelDriver):
    def __init__(self, model: Model):
        self.model = model

    async def run(
        self, 
        messages: List[Message], 
        tools: List[Tool], 
        config: LoopConfig
    ) -> AsyncIterator[ModelEvent]:
        executor = ToolExecutor(tools)
        current_step = 0
        
        while current_step < config.max_steps:
            current_step += 1
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
                        yield ModelEvent(
                            type=ModelEventType.USAGE,
                            usage=delta.usage,
                            step=current_step
                        )

            except Exception as e:
                log_error(f"ModelDriver: Error in step {current_step}: {e}")
                yield ModelEvent(
                    type=ModelEventType.ERROR,
                    content=str(e),
                    step=current_step,
                    metadata={"error_type": type(e).__name__}
                )
                break
            
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
        
        if current_step >= config.max_steps:
            log_debug(f"ModelDriver: Reached max steps ({config.max_steps})")
