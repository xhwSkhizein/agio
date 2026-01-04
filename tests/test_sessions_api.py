"""
Tests for session API endpoints.

Focuses on StepResponse serialization to ensure tool calls are correctly
represented with all required fields.
"""

import pytest

from agio.api.routes.sessions import StepResponse
from agio.domain import MessageRole
from agio.domain.models import Step


class TestStepResponse:
    """Test StepResponse model serialization."""

    def test_user_step_response(self):
        """User step should have content only."""
        step = Step(
            id="step-1",
            session_id="session-1",
            run_id="run-1",
            sequence=1,
            role=MessageRole.USER,
            content="Hello, world!",
        )
        
        response = StepResponse(
            id=step.id,
            session_id=step.session_id,
            sequence=step.sequence,
            role=step.role.value,
            content=step.content,
            tool_calls=step.tool_calls,
            name=step.name,
            tool_call_id=step.tool_call_id,
            created_at=step.created_at.isoformat(),
        )
        
        assert response.role == "user"
        assert response.content == "Hello, world!"
        assert response.tool_calls is None
        assert response.name is None
        assert response.tool_call_id is None

    def test_assistant_step_with_tool_calls(self):
        """Assistant step with tool_calls should include function name and arguments."""
        tool_calls = [
            {
                "id": "call-123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"city": "Tokyo"}'
                }
            }
        ]
        
        step = Step(
            id="step-2",
            session_id="session-1",
            run_id="run-1",
            sequence=2,
            role=MessageRole.ASSISTANT,
            content=None,
            tool_calls=tool_calls,
        )
        
        response = StepResponse(
            id=step.id,
            session_id=step.session_id,
            sequence=step.sequence,
            role=step.role.value,
            content=step.content,
            tool_calls=step.tool_calls,
            name=step.name,
            tool_call_id=step.tool_call_id,
            created_at=step.created_at.isoformat(),
        )
        
        assert response.role == "assistant"
        assert response.content is None
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["id"] == "call-123"
        assert response.tool_calls[0]["function"]["name"] == "get_weather"
        assert response.tool_calls[0]["function"]["arguments"] == '{"city": "Tokyo"}'
        # Assistant step should not have name or tool_call_id
        assert response.name is None
        assert response.tool_call_id is None

    def test_tool_step_response(self):
        """Tool step should have name, tool_call_id, and content (result)."""
        step = Step(
            id="step-3",
            session_id="session-1",
            run_id="run-1",
            sequence=3,
            role=MessageRole.TOOL,
            name="get_weather",
            tool_call_id="call-123",
            content='{"temperature": 22, "condition": "sunny"}',
        )
        
        response = StepResponse(
            id=step.id,
            session_id=step.session_id,
            sequence=step.sequence,
            role=step.role.value,
            content=step.content,
            tool_calls=step.tool_calls,
            name=step.name,
            tool_call_id=step.tool_call_id,
            created_at=step.created_at.isoformat(),
        )
        
        assert response.role == "tool"
        assert response.name == "get_weather"
        assert response.tool_call_id == "call-123"
        assert response.content == '{"temperature": 22, "condition": "sunny"}'
        # Tool step should not have tool_calls
        assert response.tool_calls is None

    def test_assistant_step_with_content_and_tool_calls(self):
        """Assistant step can have both content and tool_calls."""
        tool_calls = [
            {
                "id": "call-456",
                "type": "function",
                "function": {
                    "name": "search_web",
                    "arguments": '{"query": "Python tutorials"}'
                }
            }
        ]
        
        step = Step(
            id="step-4",
            session_id="session-1",
            run_id="run-1",
            sequence=4,
            role=MessageRole.ASSISTANT,
            content="Let me search for that.",
            tool_calls=tool_calls,
        )
        
        response = StepResponse(
            id=step.id,
            session_id=step.session_id,
            sequence=step.sequence,
            role=step.role.value,
            content=step.content,
            tool_calls=step.tool_calls,
            name=step.name,
            tool_call_id=step.tool_call_id,
            created_at=step.created_at.isoformat(),
        )
        
        assert response.role == "assistant"
        assert response.content == "Let me search for that."
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "search_web"


class TestStepResponseSerialization:
    """Test that StepResponse serializes correctly for frontend consumption."""

    def test_serialization_includes_all_tool_fields(self):
        """Ensure serialized response includes all fields needed by frontend."""
        response = StepResponse(
            id="step-tool",
            session_id="session-1",
            sequence=3,
            role="tool",
            content='{"result": "success"}',
            tool_calls=None,
            name="my_tool",
            tool_call_id="call-789",
            created_at="2024-01-01T00:00:00",
        )
        
        # Simulate JSON serialization
        data = response.model_dump(exclude_none=True)
        
        # Frontend expects these fields for tool display
        assert "name" in data
        assert "tool_call_id" in data
        assert data["name"] == "my_tool"
        assert data["tool_call_id"] == "call-789"

    def test_serialization_includes_tool_calls_structure(self):
        """Ensure tool_calls structure is preserved for frontend parsing."""
        tool_calls = [
            {
                "id": "call-abc",
                "type": "function",
                "function": {
                    "name": "calculate",
                    "arguments": '{"a": 1, "b": 2}'
                }
            },
            {
                "id": "call-def",
                "type": "function",
                "function": {
                    "name": "format_result",
                    "arguments": '{"format": "json"}'
                }
            }
        ]
        
        response = StepResponse(
            id="step-assistant",
            session_id="session-1",
            sequence=2,
            role="assistant",
            content=None,
            tool_calls=tool_calls,
            name=None,
            tool_call_id=None,
            created_at="2024-01-01T00:00:00",
        )

        data = response.model_dump(exclude_none=True)
        
        # Frontend parses tool_calls[].id and tool_calls[].function.name/arguments
        assert data["tool_calls"] is not None
        assert len(data["tool_calls"]) == 2
        
        tc1 = data["tool_calls"][0]
        assert tc1["id"] == "call-abc"
        assert tc1["function"]["name"] == "calculate"
        assert tc1["function"]["arguments"] == '{"a": 1, "b": 2}'
        
        tc2 = data["tool_calls"][1]
        assert tc2["id"] == "call-def"
        assert tc2["function"]["name"] == "format_result"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
