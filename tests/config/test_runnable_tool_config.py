"""Tests for ConfigSystem handling of agent_tool/workflow_tool configurations."""

import pytest

from agio.config.schema import AgentConfig, RunnableToolConfig
from agio.config.system import ConfigSystem
from agio.domain import StepEvent, StepEventType
from agio.workflow.runnable_tool import RunnableTool


class MockRunnable:
    """Mock Runnable for testing."""

    def __init__(self, id: str = "mock_agent"):
        self._id = id
        self._last_output: str | None = None

    @property
    def id(self) -> str:
        return self._id

    @property
    def last_output(self) -> str | None:
        return self._last_output

    async def run(self, input: str, *, context=None):
        self._last_output = f"Response to: {input}"
        yield StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id="test_run",
        )
        yield StepEvent(
            type=StepEventType.RUN_COMPLETED,
            run_id="test_run",
            data={"response": self._last_output},
        )


class TestRunnableToolConfig:
    """Tests for RunnableToolConfig schema."""

    def test_agent_tool_config(self):
        """Test agent_tool config parsing."""
        config = RunnableToolConfig(
            type="agent_tool",
            agent="research_agent",
            description="Research expert",
        )

        assert config.type == "agent_tool"
        assert config.agent == "research_agent"
        assert config.description == "Research expert"

    def test_workflow_tool_config(self):
        """Test workflow_tool config parsing."""
        config = RunnableToolConfig(
            type="workflow_tool",
            workflow="analysis_pipeline",
            description="Analysis pipeline",
        )

        assert config.type == "workflow_tool"
        assert config.workflow == "analysis_pipeline"
        assert config.description == "Analysis pipeline"

    def test_optional_name(self):
        """Test optional custom name."""
        config = RunnableToolConfig(
            type="agent_tool",
            agent="research_agent",
            name="my_research_tool",
        )

        assert config.name == "my_research_tool"


class TestAgentConfigWithToolReferences:
    """Tests for AgentConfig with various tool reference types."""

    def test_string_tool_references(self):
        """Test AgentConfig with string tool references."""
        config = AgentConfig(
            name="test_agent",
            model="gpt-4",
            tools=["web_search", "file_read"],
        )

        assert len(config.tools) == 2
        assert config.tools[0] == "web_search"
        assert config.tools[1] == "file_read"

    def test_dict_tool_references(self):
        """Test AgentConfig with dict tool references (auto-converted to RunnableToolConfig)."""
        config = AgentConfig(
            name="test_agent",
            model="gpt-4",
            tools=[
                {"type": "agent_tool", "agent": "research_agent", "description": "Research"},
                {"type": "workflow_tool", "workflow": "pipeline", "description": "Pipeline"},
            ],
        )

        assert len(config.tools) == 2
        # Pydantic auto-converts dict to RunnableToolConfig
        assert isinstance(config.tools[0], RunnableToolConfig)
        assert config.tools[0].type == "agent_tool"
        assert config.tools[0].agent == "research_agent"
        assert isinstance(config.tools[1], RunnableToolConfig)
        assert config.tools[1].type == "workflow_tool"
        assert config.tools[1].workflow == "pipeline"

    def test_mixed_tool_references(self):
        """Test AgentConfig with mixed tool references."""
        config = AgentConfig(
            name="test_agent",
            model="gpt-4",
            tools=[
                "web_search",
                {"type": "agent_tool", "agent": "research_agent"},
            ],
        )

        assert len(config.tools) == 2
        assert config.tools[0] == "web_search"
        # Dict is auto-converted to RunnableToolConfig
        assert isinstance(config.tools[1], RunnableToolConfig)


class TestConfigSystemToolResolution:
    """Tests for ConfigSystem's tool resolution."""

    @pytest.fixture
    def config_system(self):
        """Create a fresh ConfigSystem instance."""
        return ConfigSystem()

    @pytest.mark.asyncio
    async def test_resolve_agent_tool(self, config_system):
        """Test resolving agent_tool configuration."""
        # Register a mock agent
        from agio.config.container import ComponentMetadata
        from agio.config.schema import ComponentType, AgentConfig
        
        mock_agent = MockRunnable(id="research_agent")
        metadata = ComponentMetadata(
            component_type=ComponentType.AGENT,
            config=AgentConfig(name="research_agent", model="test"),
            dependencies=[]
        )
        config_system.container.register("research_agent", mock_agent, metadata)

        # Resolve agent_tool
        tool_ref = {
            "type": "agent_tool",
            "agent": "research_agent",
            "description": "Research expert",
        }

        tool = await config_system._resolve_tool_reference(tool_ref)

        assert isinstance(tool, RunnableTool)
        assert tool.get_name() == "call_research_agent"
        assert tool.get_description() == "Research expert"

    @pytest.mark.asyncio
    async def test_resolve_workflow_tool(self, config_system):
        """Test resolving workflow_tool configuration."""
        # Register a mock workflow
        from agio.config.container import ComponentMetadata
        from agio.config.schema import ComponentType, WorkflowConfig
        
        mock_workflow = MockRunnable(id="analysis_pipeline")
        metadata = ComponentMetadata(
            component_type=ComponentType.WORKFLOW,
            config=WorkflowConfig(name="analysis_pipeline", stages=[]),
            dependencies=[]
        )
        config_system.container.register("analysis_pipeline", mock_workflow, metadata)

        # Resolve workflow_tool
        tool_ref = {
            "type": "workflow_tool",
            "workflow": "analysis_pipeline",
            "description": "Analysis pipeline",
        }

        tool = await config_system._resolve_tool_reference(tool_ref)

        assert isinstance(tool, RunnableTool)
        assert tool.get_name() == "call_analysis_pipeline"
        assert tool.get_description() == "Analysis pipeline"

    @pytest.mark.asyncio
    async def test_resolve_string_tool_reference(self, config_system):
        """Test resolving string tool reference falls back to _get_or_create_tool."""
        # This test just verifies the code path - actual tool creation
        # depends on tool registry which we don't mock here
        
        # String reference should call _get_or_create_tool
        # which will fail if tool doesn't exist
        with pytest.raises(Exception):  # ComponentNotFoundError
            await config_system._resolve_tool_reference("nonexistent_tool")

    @pytest.mark.asyncio
    async def test_resolve_agent_tool_custom_name(self, config_system):
        """Test agent_tool with custom name."""
        from agio.config.container import ComponentMetadata
        from agio.config.schema import ComponentType, AgentConfig
        
        mock_agent = MockRunnable(id="research_agent")
        metadata = ComponentMetadata(
            component_type=ComponentType.AGENT,
            config=AgentConfig(name="research_agent", model="test"),
            dependencies=[]
        )
        config_system.container.register("research_agent", mock_agent, metadata)

        tool_ref = {
            "type": "agent_tool",
            "agent": "research_agent",
            "name": "custom_research_tool",
        }

        tool = await config_system._resolve_tool_reference(tool_ref)

        assert tool.get_name() == "custom_research_tool"

    @pytest.mark.asyncio
    async def test_resolve_agent_tool_missing_agent(self, config_system):
        """Test agent_tool with missing agent field raises error."""
        tool_ref = {
            "type": "agent_tool",
            # missing 'agent' field
        }

        with pytest.raises(Exception) as exc_info:
            await config_system._resolve_tool_reference(tool_ref)
        
        assert "missing 'agent' field" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_resolve_workflow_tool_missing_workflow(self, config_system):
        """Test workflow_tool with missing workflow field raises error."""
        tool_ref = {
            "type": "workflow_tool",
            # missing 'workflow' field
        }

        with pytest.raises(Exception) as exc_info:
            await config_system._resolve_tool_reference(tool_ref)
        
        assert "missing 'workflow' field" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_resolve_agent_tool_agent_not_found(self, config_system):
        """Test agent_tool when referenced agent doesn't exist."""
        tool_ref = {
            "type": "agent_tool",
            "agent": "nonexistent_agent",
        }

        with pytest.raises(Exception):  # ComponentNotFoundError
            await config_system._resolve_tool_reference(tool_ref)

    @pytest.mark.asyncio
    async def test_resolve_invalid_tool_reference(self, config_system):
        """Test invalid tool reference format raises error."""
        tool_ref = {
            "type": "unknown_type",
        }

        with pytest.raises(Exception) as exc_info:
            await config_system._resolve_tool_reference(tool_ref)
        
        assert "Unknown tool reference format" in str(exc_info.value)


class TestSelfReferenceDetection:
    """Tests for self-reference detection in ConfigSystem."""

    @pytest.fixture
    def config_system(self):
        """Create a fresh ConfigSystem instance."""
        return ConfigSystem()

    @pytest.mark.asyncio
    async def test_agent_self_reference_detected(self, config_system):
        """Test that agent self-reference is detected at config time."""
        # Register an agent
        from agio.config.container import ComponentMetadata
        from agio.config.schema import ComponentType, AgentConfig
        
        mock_agent = MockRunnable(id="my_agent")
        metadata = ComponentMetadata(
            component_type=ComponentType.AGENT,
            config=AgentConfig(name="my_agent", model="test"),
            dependencies=[]
        )
        config_system.container.register("my_agent", mock_agent, metadata)

        # Try to create agent_tool that references itself
        tool_ref = {
            "type": "agent_tool",
            "agent": "my_agent",
        }

        with pytest.raises(Exception) as exc_info:
            await config_system._resolve_tool_reference(
                tool_ref, 
                current_component="my_agent"
            )
        
        assert "Self-reference detected" in str(exc_info.value)
        assert "my_agent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_workflow_self_reference_detected(self, config_system):
        """Test that workflow self-reference is detected at config time."""
        # Register a workflow
        from agio.config.container import ComponentMetadata
        from agio.config.schema import ComponentType, WorkflowConfig
        
        mock_workflow = MockRunnable(id="my_workflow")
        metadata = ComponentMetadata(
            component_type=ComponentType.WORKFLOW,
            config=WorkflowConfig(name="my_workflow", stages=[]),
            dependencies=[]
        )
        config_system.container.register("my_workflow", mock_workflow, metadata)

        # Try to create workflow_tool that references itself
        tool_ref = {
            "type": "workflow_tool",
            "workflow": "my_workflow",
        }

        with pytest.raises(Exception) as exc_info:
            await config_system._resolve_tool_reference(
                tool_ref, 
                current_component="my_workflow"
            )
        
        assert "Self-reference detected" in str(exc_info.value)
        assert "my_workflow" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_different_agent_reference_allowed(self, config_system):
        """Test that referencing a different agent is allowed."""
        # Register two agents
        from agio.config.container import ComponentMetadata
        from agio.config.schema import ComponentType, AgentConfig
        
        mock_agent_a = MockRunnable(id="agent_a")
        mock_agent_b = MockRunnable(id="agent_b")
        
        metadata_a = ComponentMetadata(
            component_type=ComponentType.AGENT,
            config=AgentConfig(name="agent_a", model="test"),
            dependencies=[]
        )
        metadata_b = ComponentMetadata(
            component_type=ComponentType.AGENT,
            config=AgentConfig(name="agent_b", model="test"),
            dependencies=[]
        )
        
        config_system.container.register("agent_a", mock_agent_a, metadata_a)
        config_system.container.register("agent_b", mock_agent_b, metadata_b)

        # agent_a using agent_b as tool should be allowed
        tool_ref = {
            "type": "agent_tool",
            "agent": "agent_b",
        }

        tool = await config_system._resolve_tool_reference(
            tool_ref, 
            current_component="agent_a"
        )
        
        assert tool is not None
        assert tool.get_name() == "call_agent_b"
