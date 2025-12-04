"""
PipelineWorkflow - sequential execution of stages.

Executes stages in order, with each stage able to reference
outputs from all previous stages.
"""

from typing import TYPE_CHECKING, AsyncIterator
from uuid import uuid4

from agio.domain.events import StepEvent, StepEventType
from agio.workflow.base import BaseWorkflow
from agio.workflow.protocol import RunContext
from agio.workflow.stage import Stage
from agio.workflow.store import OutputStore

if TYPE_CHECKING:
    pass


class PipelineWorkflow(BaseWorkflow):
    """
    Sequential Pipeline Workflow.

    Executes all stages in order:
    1. Check each stage's condition
    2. If condition met, execute; otherwise skip
    3. Each stage can reference outputs from all previous stages
    """

    def __init__(self, id: str, stages: list[Stage]):
        super().__init__(id, stages)

    async def run(
        self,
        input: str,
        *,
        context: RunContext | None = None,
    ) -> AsyncIterator[StepEvent]:
        run_id = str(uuid4())
        store = OutputStore()
        store.set("query", input)

        # Initialize trace
        trace_id = context.trace_id if context else str(uuid4())

        yield StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            trace_id=trace_id,
            data={"workflow_id": self._id, "type": "pipeline"},
        )

        final_output = ""

        try:
            for stage in self._stages:
                outputs_dict = store.to_dict()

                # Check condition
                if not stage.should_execute(outputs_dict):
                    yield StepEvent(
                        type=StepEventType.STAGE_SKIPPED,
                        run_id=run_id,
                        stage_id=stage.id,
                        trace_id=trace_id,
                        data={"condition": stage.condition},
                    )
                    continue

                yield StepEvent(
                    type=StepEventType.STAGE_STARTED,
                    run_id=run_id,
                    stage_id=stage.id,
                    trace_id=trace_id,
                )

                # Build input
                stage_input = stage.build_input(outputs_dict)

                # Get Runnable instance
                runnable = self._resolve_runnable(stage.runnable)

                # Create child context (independent session)
                child_context = self._create_child_context(context, stage)
                child_context.trace_id = trace_id

                # Execute
                stage_output = ""
                async for event in runnable.run(stage_input, context=child_context):
                    # Add stage context
                    event.stage_id = stage.id
                    event.trace_id = trace_id
                    yield event

                    # Extract output
                    if event.type == StepEventType.RUN_COMPLETED and event.data:
                        stage_output = event.data.get("response", "")

                # Store output
                store.set(stage.id, stage_output)
                final_output = stage_output

                yield StepEvent(
                    type=StepEventType.STAGE_COMPLETED,
                    run_id=run_id,
                    stage_id=stage.id,
                    trace_id=trace_id,
                    data={"output_length": len(stage_output)},
                )

            self._last_output = final_output

            yield StepEvent(
                type=StepEventType.RUN_COMPLETED,
                run_id=run_id,
                trace_id=trace_id,
                data={"response": final_output},
            )

        except Exception as e:
            yield StepEvent(
                type=StepEventType.RUN_FAILED,
                run_id=run_id,
                trace_id=trace_id,
                data={"error": str(e)},
            )
            raise
