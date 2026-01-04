"""
ParallelWorkflow - concurrent execution of nodes.

Executes multiple nodes in parallel, with idempotency support,
then merges results.

Wire-based Architecture:
- Events are written to context.wire
- Returns RunOutput with response and metrics
- Uses WorkflowState for output caching and idempotency
"""

import asyncio
import time
from typing import Any

from agio.config.template import renderer
from agio.domain.models import RunMetrics
from agio.runtime import RunnableExecutor, RunOutput
from agio.runtime.event_factory import EventFactory
from agio.runtime.protocol import ExecutionContext
from agio.storage.session.base import SessionStore
from agio.workflow.base import BaseWorkflow
from agio.workflow.node import WorkflowNode
from agio.workflow.resolver import ContextResolver
from agio.workflow.state import WorkflowState


class ParallelWorkflow(BaseWorkflow):
    """
    Workflow that executes multiple nodes in parallel.

    Used for map-reduce patterns or independent subtasks.
    Wait for all nodes to complete and aggregates results.
    """

    SEQ_INTERVAL = 100  # Reserved sequence range per branch

    def __init__(
        self,
        id: str,
        stages: list[WorkflowNode],
        merge_template: str | None = None,
        session_store: "SessionStore | None" = None,
    ):
        super().__init__(id, stages, session_store)
        self.merge_template = merge_template

    async def _execute(
        self,
        input: str,
        *,
        context: ExecutionContext,
    ) -> RunOutput:
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

        # Create ContextResolver
        resolver = ContextResolver(
            session_id=context.session_id,
            workflow_id=self._id,
            store=session_store,
            state=state,
        )
        resolver.set_input(input)

        # Get nodes
        nodes = self.nodes
        total_branches = len(nodes)

        # Get current max sequence for seq pre-allocation (avoid parallel seq conflicts)
        current_max_seq = await session_store.get_max_sequence(context.session_id)

        async def execute_branch(index: int, node: WorkflowNode) -> dict[str, Any]:
            """Execute a single branch with idempotency support."""
            branch_id = node.id
            branch_key = f"branch_{branch_id}"  # Unique branch identifier

            try:
                # Idempotency check: if branch already executed, return cached result
                if state.has_output(branch_id):
                    cached_output = state.get_output(branch_id)
                    await wire.write(
                        ef.branch_completed(
                            branch_id=branch_id,
                            data={"output_length": len(cached_output or ""), "cached": True},
                            branch_index=index,
                            total_branches=total_branches,
                            workflow_type="parallel",
                            workflow_id=self.id,
                        )
                    )
                    return {
                        "branch_id": branch_id,
                        "output": cached_output or "",
                        "metrics": None,  # Metrics not available for cached results
                    }

                await wire.write(
                    ef.branch_started(
                        branch_id=branch_id,
                        branch_index=index,
                        total_branches=total_branches,
                        workflow_type="parallel",
                        workflow_id=self.id,
                    )
                )

                # Resolve input template
                node_input = await resolver.resolve_template(node.input_template)

                runnable = self._resolve_runnable(node.runnable)

                # Create child context with branch_key and seq_start in metadata
                child_context = self._create_child_context(context, node)
                # Pre-allocate seq range for this branch to avoid conflicts
                seq_start = current_max_seq + 1 + index * self.SEQ_INTERVAL
                child_context = child_context.with_metadata(
                    branch_key=branch_key,
                    seq_start=seq_start,
                )

                # Execute via RunnableExecutor - handles Run lifecycle
                executor = RunnableExecutor(store=session_store)
                result = await executor.execute(runnable, node_input, child_context)
                output = result.response or ""

                # Update state cache
                state.set_output(branch_id, output)

                await wire.write(
                    ef.branch_completed(
                        branch_id=branch_id,
                        data={"output_length": len(output)},
                        branch_index=index,
                        total_branches=total_branches,
                        workflow_type="parallel",
                        workflow_id=self.id,
                    )
                )

                return {
                    "branch_id": branch_id,
                    "output": output,
                    "metrics": result.metrics,
                }
            except Exception as e:
                raise e

        try:
            # Run all branches concurrently with idempotency
            tasks = [execute_branch(i, node) for i, node in enumerate(nodes)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Aggregate results (handle exceptions)
            branches: list[dict[str, Any]] = []
            total_tokens = 0
            input_tokens = 0
            output_tokens = 0
            for res in results:
                if isinstance(res, Exception):
                    # Handle exception - could log or include error message
                    continue
                branches.append(
                    {
                        "id": res["branch_id"],
                        "output": res["output"],
                        "metrics": res.get("metrics"),
                    }
                )
                if res.get("metrics"):
                    metrics = res["metrics"]
                    total_tokens += metrics.total_tokens
                    input_tokens += metrics.input_tokens
                    output_tokens += metrics.output_tokens

            # Default merged output (fallback if no template provided)
            merged_output = "\n\n".join(f"{b['id']}: {b['output']}" for b in branches)

            # Build context for merge template
            merge_context = {
                "input": input,
                "branches": branches,
                "nodes": await resolver._build_nodes_dict(),
                "tokens": {
                    "total": total_tokens,
                    "input": input_tokens,
                    "output": output_tokens,
                },
                "results": merged_output,
            }

            final_response = merged_output
            if self.merge_template:
                final_response = renderer.render(self.merge_template, **merge_context)

            duration = time.time() - start_time

            return RunOutput(
                response=final_response,
                run_id=run_id,
                workflow_id=self._id,
                metrics=RunMetrics(
                    duration=duration,
                    total_tokens=total_tokens,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    nodes_executed=total_branches,
                ),
            )

        except Exception as e:
            raise
