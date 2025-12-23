"""
PipelineWorkflow - sequential execution of nodes.

Executes nodes in order, with each node able to reference
outputs from all previous nodes.

Wire-based Architecture:
- Events are written to context.wire
- Returns RunOutput with response and metrics
- Uses WorkflowState for output caching and idempotency
"""

import time
from typing import TYPE_CHECKING

from agio.domain import ExecutionContext
from agio.workflow.state import WorkflowState
from agio.workflow.resolver import ContextResolver
from agio.runtime import RunnableExecutor
from agio.workflow.base import BaseWorkflow
from agio.domain.protocol import RunOutput
from agio.domain.models import RunMetrics
from agio.workflow.node import WorkflowNode

if TYPE_CHECKING:
    from agio.providers.storage.base import SessionStore


class PipelineWorkflow(BaseWorkflow):
    """
    Sequential Pipeline Workflow.

    Executes all nodes in order:
    1. Check each node's condition
    2. If condition met, execute; otherwise skip
    3. Each node can reference outputs from all previous nodes
    """

    def __init__(
        self,
        id: str,
        stages: list[WorkflowNode],
        session_store: "SessionStore | None" = None,
    ):
        super().__init__(id, stages, session_store)

    async def _execute(
        self,
        input: str,
        *,
        context: ExecutionContext,
    ) -> RunOutput:
        from agio.runtime.event_factory import EventFactory

        start_time = time.time()
        run_id = context.run_id
        wire = context.wire
        ef = EventFactory(context)

        # Get SessionStore from constructor injection
        session_store = self._session_store
        if session_store is None:
            raise ValueError(
                "SessionStore required for workflow execution. "
                "Pass it via constructor (configure session_store in workflow config)."
            )

        # Create WorkflowState for output caching and idempotency
        state = WorkflowState(
            session_id=context.session_id,
            workflow_id=self._id,
            store=session_store,
        )

        # Load history for resume scenarios
        await state.load_from_history()

        # Create ContextResolver for template resolution
        resolver = ContextResolver(
            session_id=context.session_id,
            workflow_id=self._id,
            store=session_store,
            state=state,
        )
        resolver.set_input(input)

        # Get nodes (convert stages if needed)
        nodes = self.nodes
        total_nodes = len(nodes)

        final_output = ""
        nodes_executed = 0
        total_tokens = 0

        try:
            for node_index, node in enumerate(nodes):
                node_id = node.id

                # Idempotency check: skip if node already executed
                if state.has_output(node_id):
                    await wire.write(
                        ef.node_skipped(
                            node_id=node_id,
                            condition=None,
                            node_index=node_index,
                            total_nodes=total_nodes,
                            workflow_type="pipeline",
                            workflow_id=self._id,
                        )
                    )
                    continue

                # Check condition
                if node.condition:
                    # Build outputs dict for condition evaluation
                    outputs_dict = {"input": input}
                    outputs_dict.update(state.to_dict())
                    from agio.workflow.condition import ConditionEvaluator

                    if not ConditionEvaluator.evaluate(node.condition, outputs_dict):
                        await wire.write(
                            ef.node_skipped(
                                node_id=node_id,
                                condition=node.condition,
                                node_index=node_index,
                                total_nodes=total_nodes,
                                workflow_type="pipeline",
                                workflow_id=self._id,
                            )
                        )
                        continue

                await wire.write(
                    ef.node_started(
                        node_id=node_id,
                        node_index=node_index,
                        total_nodes=total_nodes,
                        workflow_type="pipeline",
                        workflow_id=self._id,
                    )
                )

                # Resolve input template
                node_input = await resolver.resolve_template(node.input_template)

                # Get Runnable instance
                runnable = self._resolve_runnable(node.runnable)

                # Create child context
                child_context = self._create_child_context(context, node)

                # Execute Runnable via RunnableExecutor - handles Run lifecycle
                executor = RunnableExecutor(store=session_store)
                result = await executor.execute(runnable, node_input, child_context)
                node_output = result.response or ""
                total_tokens += result.metrics.total_tokens

                # Update state cache
                state.set_output(node_id, node_output)

                final_output = node_output
                nodes_executed += 1

                await wire.write(
                    ef.node_completed(
                        node_id=node_id,
                        data={"output_length": len(node_output)},
                        node_index=node_index,
                        total_nodes=total_nodes,
                        workflow_type="pipeline",
                        workflow_id=self._id,
                    )
                )

            duration = time.time() - start_time

            return RunOutput(
                response=final_output,
                run_id=run_id,
                workflow_id=self._id,
                metrics=RunMetrics(
                    duration=duration,
                    total_tokens=total_tokens,
                    nodes_executed=nodes_executed,
                ),
            )

        except Exception as e:
            raise
