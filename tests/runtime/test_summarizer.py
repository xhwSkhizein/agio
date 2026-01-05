"""
Tests for termination summary functions.
"""

import pytest

from agio.agent.summarizer import (
    build_termination_messages,
    DEFAULT_TERMINATION_USER_PROMPT,
    _format_termination_reason,
)


class TestBuildTerminationMessages:
    """Tests for build_termination_messages function."""

    @pytest.fixture
    def sample_messages(self):
        """Sample conversation messages."""
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Please analyze this data"},
            {
                "role": "assistant",
                "content": "I'll analyze the data.",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "read_file", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "read_file",
                "content": "File content here",
            },
            {"role": "assistant", "content": "Based on the analysis..."},
        ]

    def test_build_messages_without_pending_tool_calls(self, sample_messages):
        """Test building messages when stopped at a safe position."""
        result = build_termination_messages(
            messages=sample_messages,
            termination_reason="max_steps",
        )

        # Original messages preserved
        assert len(result) == len(sample_messages) + 1
        # System message preserved (for LLM cache)
        assert result[0]["role"] == "system"
        # User summary request appended
        assert result[-1]["role"] == "user"
        assert "interrupted" in result[-1]["content"].lower()

    def test_build_messages_with_pending_tool_calls(self):
        """Test building messages when stopped with pending tool calls."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Analyze the file"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "read_file", "arguments": "{}"},
                    },
                    {
                        "id": "call_2",
                        "function": {"name": "write_file", "arguments": "{}"},
                    },
                ],
            },
        ]
        pending_tool_calls = [
            {"id": "call_1", "function": {"name": "read_file", "arguments": "{}"}},
            {"id": "call_2", "function": {"name": "write_file", "arguments": "{}"}},
        ]

        result = build_termination_messages(
            messages=messages,
            termination_reason="max_steps",
            pending_tool_calls=pending_tool_calls,
        )

        # Original messages + 2 placeholder tool results + 1 user request
        assert len(result) == len(messages) + 3

        # Placeholder tool results added
        assert result[3]["role"] == "tool"
        assert result[3]["tool_call_id"] == "call_1"
        assert "interrupted" in result[3]["content"].lower()

        assert result[4]["role"] == "tool"
        assert result[4]["tool_call_id"] == "call_2"

        # User summary request at the end
        assert result[-1]["role"] == "user"

    def test_build_messages_preserves_original(self, sample_messages):
        """Test that original messages list is not modified."""
        original_len = len(sample_messages)

        build_termination_messages(
            messages=sample_messages,
            termination_reason="max_steps",
        )

        assert len(sample_messages) == original_len

    def test_build_messages_with_custom_prompt(self, sample_messages):
        """Test custom user prompt."""
        custom_prompt = "Custom summary request: {termination_reason}"

        result = build_termination_messages(
            messages=sample_messages,
            termination_reason="timeout",
            custom_prompt=custom_prompt,
        )

        assert "Custom summary request:" in result[-1]["content"]


class TestFormatTerminationReason:
    """Tests for _format_termination_reason function."""

    def test_known_reasons(self):
        """Test formatting of known termination reasons."""
        assert "maximum number of execution steps" in _format_termination_reason(
            "max_steps"
        )
        assert "maximum number of iterations" in _format_termination_reason(
            "max_iterations"
        )
        assert "timeout" in _format_termination_reason("timeout")
        assert "cancellation" in _format_termination_reason("cancelled")

    def test_unknown_reason(self):
        """Test formatting of unknown termination reason."""
        assert _format_termination_reason("custom_reason") == "custom_reason"


class TestDefaultPrompt:
    """Tests for default prompt template."""

    def test_default_prompt_contains_placeholders(self):
        """Test default prompt has required placeholders (Jinja2 syntax)."""
        assert "{{ termination_reason }}" in DEFAULT_TERMINATION_USER_PROMPT

    def test_default_prompt_requirements(self):
        """Test default prompt includes key requirements."""
        prompt_lower = DEFAULT_TERMINATION_USER_PROMPT.lower()
        assert "incomplete" in prompt_lower or "interrupted" in prompt_lower
        assert "fabricate" in prompt_lower or "assume" in prompt_lower


class TestExecutionConfigTerminationSummary:
    """Tests for ExecutionConfig termination summary settings."""

    def test_default_values(self):
        """Test default termination summary configuration."""
        from agio.config import ExecutionConfig

        config = ExecutionConfig()

        assert config.enable_termination_summary is False
        assert config.termination_summary_prompt is None

    def test_enable_termination_summary(self):
        """Test enabling termination summary."""
        from agio.config import ExecutionConfig

        config = ExecutionConfig(enable_termination_summary=True)

        assert config.enable_termination_summary is True

    def test_custom_prompt(self):
        """Test custom termination summary prompt."""
        from agio.config import ExecutionConfig

        custom_prompt = "My custom prompt"
        config = ExecutionConfig(
            enable_termination_summary=True,
            termination_summary_prompt=custom_prompt,
        )

        assert config.termination_summary_prompt == custom_prompt
