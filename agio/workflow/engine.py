"""
WorkflowEngine - Workflow execution engine.

Provides:
- Runnable registry management (Agent + Workflow)
- YAML configuration loading
- Unified execution entry point

Wire-based Architecture:
- run() requires context.wire
- run() returns RunOutput
"""

from pathlib import Path
from typing import Any

import yaml

from agio.workflow.base import BaseWorkflow
from agio.workflow.loop import LoopWorkflow
from agio.workflow.parallel import ParallelWorkflow
from agio.workflow.pipeline import PipelineWorkflow
from agio.workflow.protocol import Runnable, RunOutput
from agio.domain import ExecutionContext
from agio.workflow.node import WorkflowNode


class WorkflowEngine:
    """
    Workflow execution engine.

    Responsibilities:
    1. Manage Runnable registry (Agent + Workflow)
    2. Load Workflow configurations from YAML
    3. Provide unified execution entry point
    """

    def __init__(self):
        self._registry: dict[str, Runnable] = {}

    def register(self, runnable: Runnable):
        """Register a Runnable (Agent or Workflow)."""
        self._registry[runnable.id] = runnable

    def unregister(self, id: str):
        """Unregister a Runnable."""
        if id in self._registry:
            del self._registry[id]

    def get(self, id: str) -> Runnable:
        """
        Get a registered Runnable.

        Raises:
            ValueError: If Runnable not found
        """
        if id not in self._registry:
            raise ValueError(f"Runnable not found: {id}")
        return self._registry[id]

    def has(self, id: str) -> bool:
        """Check if a Runnable is registered."""
        return id in self._registry

    def list_ids(self) -> list[str]:
        """List all registered Runnable IDs."""
        return list(self._registry.keys())

    def load_workflow(self, config_path: str | Path) -> BaseWorkflow:
        """
        Load a Workflow from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Constructed workflow instance
        """
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return self.load_workflow_from_dict(config)

    def load_workflow_from_dict(self, config: dict[str, Any]) -> BaseWorkflow:
        """
        Build a Workflow from dictionary configuration.

        Args:
            config: Workflow configuration dict

        Returns:
            Constructed workflow instance
        """
        return self._build_workflow(config)

    def _build_workflow(self, config: dict[str, Any]) -> BaseWorkflow:
        """Build a Workflow based on configuration."""
        workflow_type = config.get("type", "pipeline")

        if workflow_type == "pipeline":
            return self._build_pipeline(config)
        elif workflow_type == "loop":
            return self._build_loop(config)
        elif workflow_type == "parallel":
            return self._build_parallel(config)
        else:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

    def _build_pipeline(self, config: dict[str, Any]) -> PipelineWorkflow:
        """Build a PipelineWorkflow."""
        nodes = [self._build_node(n) for n in config.get("nodes", [])]
        workflow = PipelineWorkflow(id=config["id"], stages=nodes)
        workflow.set_registry(self._registry)
        return workflow

    def _build_loop(self, config: dict[str, Any]) -> LoopWorkflow:
        """Build a LoopWorkflow."""
        nodes = [self._build_node(n) for n in config.get("nodes", [])]
        workflow = LoopWorkflow(
            id=config["id"],
            stages=nodes,
            condition=config.get("condition", "true"),
            max_iterations=config.get("max_iterations", 10),
        )
        workflow.set_registry(self._registry)
        return workflow

    def _build_parallel(self, config: dict[str, Any]) -> ParallelWorkflow:
        """Build a ParallelWorkflow."""
        nodes = [self._build_node(n) for n in config.get("nodes", [])]
        workflow = ParallelWorkflow(
            id=config["id"],
            stages=nodes,
            merge_template=config.get("merge_template"),
        )
        workflow.set_registry(self._registry)
        return workflow

    def _build_node(self, config: dict[str, Any]) -> WorkflowNode:
        """Build a WorkflowNode from configuration."""
        runnable_config = config.get("runnable")

        # If runnable is a nested workflow config (dict)
        if isinstance(runnable_config, dict):
            nested_workflow = self._build_workflow(runnable_config)
            self.register(nested_workflow)  # Register nested workflow
            runnable_ref = nested_workflow.id
        else:
            runnable_ref = runnable_config

        return WorkflowNode(
            id=config["id"],
            runnable=runnable_ref,
            input_template=config.get("input", "{query}"),
            condition=config.get("condition"),
        )

    async def run(
        self,
        runnable_id: str,
        input: str,
        context: ExecutionContext,
    ) -> RunOutput:
        """
        Execute a Runnable (Agent or Workflow).

        Unified entry point - does not distinguish between types.

        Args:
            runnable_id: ID of the Runnable to execute
            input: Input string
            context: Execution context with wire (required)

        Returns:
            RunOutput with response and metrics
        """
        runnable = self.get(runnable_id)
        return await runnable.run(input, context=context)

    def describe(self, runnable_id: str) -> dict[str, Any]:
        """
        Get description of a Runnable.

        Args:
            runnable_id: ID of the Runnable

        Returns:
            Description dict with type, id, and structure info
        """
        runnable = self.get(runnable_id)

        info = {
            "id": runnable.id,
            "type": type(runnable).__name__,
        }

        # Add workflow-specific info
        if isinstance(runnable, BaseWorkflow):
            info["nodes"] = [
                {
                    "id": node.id,
                    "runnable": (
                        node.runnable if isinstance(node.runnable, str) else node.runnable.id
                    ),
                    "input_template": node.input_template,
                    "condition": node.condition,
                }
                for node in runnable.nodes
            ]

            if isinstance(runnable, LoopWorkflow):
                info["condition"] = runnable.condition
                info["max_iterations"] = runnable.max_iterations
            elif isinstance(runnable, ParallelWorkflow):
                info["merge_template"] = runnable.merge_template

        return info
