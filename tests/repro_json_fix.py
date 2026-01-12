
import json
from unittest.mock import MagicMock
from agio.llm.anthropic import AnthropicModel
from agio.tools.executor import ToolExecutor
from agio.runtime.context import ExecutionContext
from agio.runtime.control import AbortSignal

def test_anthropic_conversion_fallback():
    model = AnthropicModel(
        id="anthropic/claude-3-haiku",
        name="claude-3-haiku",
        model_name="claude-3-haiku-20240307"
    )
    
    # Mock invalid JSON arguments
    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_123",
                    "function": {
                        "name": "test_tool",
                        "arguments": '{"unclosed": "json'
                    }
                }
            ]
        }
    ]
    
    system, converted = model._convert_messages(messages)
    
    # Check if fallback logic worked
    tool_use = converted[0]["content"][0]
    assert tool_use["type"] == "tool_use"
    assert isinstance(tool_use["input"], dict)
    assert tool_use["input"]["__raw_arguments__"] == '{"unclosed": "json'
    print("Anthropic conversion fallback test passed!")

async def test_executor_parsing_fallback():
    executor = ToolExecutor(tools=[])
    
    # Mock a tool call with malformed JSON but valid Python dict string
    tool_call = {
        "id": "call_456",
        "function": {
            "name": "test_tool",
            "arguments": "{'key': 'value'}" # Single quotes, invalid JSON
        }
    }
    
    # Mock tool lookup
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    executor.tools_map = {"test_tool": mock_tool}
    
    context = ExecutionContext(session_id="s1", run_id="r1", wire=MagicMock())
    
    # This should now succeed using ast.literal_eval
    result = await executor.execute(tool_call, context)
    
    # Verify ast.literal_eval fallback
    mock_tool.execute.assert_called_once()
    args = mock_tool.execute.call_args[0][0]
    assert args["key"] == "value"
    print("Executor parsing fallback test passed!")

if __name__ == "__main__":
    import asyncio
    test_anthropic_conversion_fallback()
    asyncio.run(test_executor_parsing_fallback())
