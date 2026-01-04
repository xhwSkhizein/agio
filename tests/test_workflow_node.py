"""
Tests for WorkflowNode configuration model.
"""

from unittest.mock import MagicMock

from agio.workflow.node import WorkflowNode


def test_workflow_node_creation():
    """Test creating a WorkflowNode"""
    node = WorkflowNode(
        id="node_1",
        runnable="agent_1",
        input_template="User said: {input}",
        condition=None,
    )

    assert node.id == "node_1"
    assert node.runnable == "agent_1"
    assert node.input_template == "User said: {input}"
    assert node.condition is None


def test_workflow_node_with_condition():
    """Test WorkflowNode with condition"""
    node = WorkflowNode(
        id="node_1",
        runnable="agent_1",
        input_template="{input}",
        condition="len(input) > 10",
    )

    assert node.condition == "len(input) > 10"




def test_workflow_node_with_runnable_instance():
    """Test WorkflowNode with Runnable instance"""
    mock_runnable = MagicMock()
    mock_runnable.id = "agent_1"

    node = WorkflowNode(
        id="node_1",
        runnable=mock_runnable,
        input_template="{input}",
    )

    assert node.runnable == mock_runnable
    assert node.runnable.id == "agent_1"

