"""
ParallelWorkflow - concurrent execution of stages.

Executes multiple stages in parallel, each with isolated state,
then merges results.
"""

import asyncio
from typing import TYPE_CHECKING, AsyncIterator
from uuid import uuid4

from agio.domain.events import StepEvent, StepEventType
from agio.workflow.base import BaseWorkflow
from agio.workflow.mapping import InputMapping
from agio.workflow.protocol import RunContext
from agio.workflow.stage import Stage

if TYPE_CHECKING:
    pass


class ParallelWorkflow(BaseWorkflow):
    """
    Parallel Workflow.

    Executes multiple branches concurrently, each with isolated state,
    then merges results.

    Features:
    1. Each branch uses a snapshot of outputs, ensuring isolation
    2. Results stored by branch ID, accessible via {branch_id}
    3. Supports custom merge template
    """

    def __init__(
        self,
        id: str,
        stages: list[Stage],  # Each stage as a branch
        merge_template: str | None = None,
    ):
        super().__init__(id, stages)
        self.merge_template = merge_template

    async def run(
        self,
        input: str,
        *,
        context: RunContext | None = None,
    ) -> AsyncIterator[StepEvent]:
        run_id = str(uuid4())
        trace_id = context.trace_id if context else str(uuid4())

        # Initial output snapshot
        initial_outputs = {"query": input}

        yield StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            trace_id=trace_id,
            data={"workflow_id": self._id, "type": "parallel"},
        )

        async def run_branch(stage: Stage) -> tuple[str, str, list[StepEvent]]:
            """Execute a single branch, collect events and output."""
            # Each branch uses snapshot for isolation
            branch_input = stage.build_input(initial_outputs)
            runnable = self._resolve_runnable(stage.runnable)
            child_context = self._create_child_context(context, stage)
            child_context.trace_id = trace_id

            events: list[StepEvent] = []
            output = ""

            async for event in runnable.run(branch_input, context=child_context):
                event.branch_id = stage.id
                event.trace_id = trace_id
                events.append(event)

                if event.type == StepEventType.RUN_COMPLETED and event.data:
                    output = event.data.get("response", "")

            return stage.id, output, events

        try:
            # Execute all branches in parallel
            tasks = [run_branch(stage) for stage in self._stages]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and yield events
            branch_outputs: dict[str, str] = {}
            errors: list[tuple[str, Exception]] = []

            for result in results:
                if isinstance(result, Exception):
                    # Handle exception from a branch
                    errors.append(("unknown", result))
                    continue

                branch_id, output, events = result

                yield StepEvent(
                    type=StepEventType.BRANCH_STARTED,
                    run_id=run_id,
                    branch_id=branch_id,
                    trace_id=trace_id,
                )

                for event in events:
                    yield event

                branch_outputs[branch_id] = output

                yield StepEvent(
                    type=StepEventType.BRANCH_COMPLETED,
                    run_id=run_id,
                    branch_id=branch_id,
                    trace_id=trace_id,
                    data={"output_length": len(output)},
                )

            # Check for errors
            if errors:
                error_msg = "; ".join(f"{bid}: {str(e)}" for bid, e in errors)
                yield StepEvent(
                    type=StepEventType.RUN_FAILED,
                    run_id=run_id,
                    trace_id=trace_id,
                    data={"error": f"Branch errors: {error_msg}"},
                )
                raise RuntimeError(f"Parallel execution failed: {error_msg}")

            # Merge outputs
            if self.merge_template:
                merged = InputMapping(self.merge_template).build(branch_outputs)
            else:
                # Default merge: concatenate by branch ID
                merged = "\n\n".join(
                    f"[{branch_id}]:\n{output}"
                    for branch_id, output in branch_outputs.items()
                )

            self._last_output = merged

            yield StepEvent(
                type=StepEventType.RUN_COMPLETED,
                run_id=run_id,
                trace_id=trace_id,
                data={
                    "response": merged,
                    "branch_outputs": {k: len(v) for k, v in branch_outputs.items()},
                },
            )

        except Exception as e:
            if not isinstance(e, RuntimeError) or "Parallel execution failed" not in str(e):
                yield StepEvent(
                    type=StepEventType.RUN_FAILED,
                    run_id=run_id,
                    trace_id=trace_id,
                    data={"error": str(e)},
                )
            raise
