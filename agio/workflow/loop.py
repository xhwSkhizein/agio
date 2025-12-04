"""
LoopWorkflow - iterative execution of stages.

Repeats execution of stages until condition is not met
or max iterations is reached.
"""

from typing import TYPE_CHECKING, AsyncIterator
from uuid import uuid4

from agio.domain.events import StepEvent, StepEventType
from agio.workflow.base import BaseWorkflow
from agio.workflow.condition import ConditionEvaluator
from agio.workflow.protocol import RunContext
from agio.workflow.stage import Stage
from agio.workflow.store import OutputStore

if TYPE_CHECKING:
    pass


class LoopWorkflow(BaseWorkflow):
    """
    Loop Workflow.

    Repeats execution of stages until condition is not met
    or max iterations is reached.

    Special variables:
    - {loop.iteration}: current iteration number (from 1)
    - {loop.last.stage_id}: output of a stage from previous iteration
    """

    def __init__(
        self,
        id: str,
        stages: list[Stage],
        condition: str = "true",
        max_iterations: int = 10,
    ):
        super().__init__(id, stages)
        self.condition = condition
        self.max_iterations = max_iterations

    async def run(
        self,
        input: str,
        *,
        context: RunContext | None = None,
    ) -> AsyncIterator[StepEvent]:
        run_id = str(uuid4())
        store = OutputStore()
        store.set("query", input)

        trace_id = context.trace_id if context else str(uuid4())

        yield StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            trace_id=trace_id,
            data={
                "workflow_id": self._id,
                "type": "loop",
                "max_iterations": self.max_iterations,
            },
        )

        final_output = ""
        iteration = 0

        try:
            while iteration < self.max_iterations:
                iteration += 1
                store.start_iteration()

                yield StepEvent(
                    type=StepEventType.ITERATION_STARTED,
                    run_id=run_id,
                    iteration=iteration,
                    trace_id=trace_id,
                    data={"max_iterations": self.max_iterations},
                )

                # Execute all stages
                for stage in self._stages:
                    outputs_dict = store.to_dict()

                    if not stage.should_execute(outputs_dict):
                        yield StepEvent(
                            type=StepEventType.STAGE_SKIPPED,
                            run_id=run_id,
                            stage_id=stage.id,
                            iteration=iteration,
                            trace_id=trace_id,
                        )
                        continue

                    yield StepEvent(
                        type=StepEventType.STAGE_STARTED,
                        run_id=run_id,
                        stage_id=stage.id,
                        iteration=iteration,
                        trace_id=trace_id,
                    )

                    stage_input = stage.build_input(outputs_dict)
                    runnable = self._resolve_runnable(stage.runnable)
                    child_context = self._create_child_context(context, stage)
                    child_context.trace_id = trace_id

                    stage_output = ""
                    async for event in runnable.run(stage_input, context=child_context):
                        event.stage_id = stage.id
                        event.iteration = iteration
                        event.trace_id = trace_id
                        yield event

                        if event.type == StepEventType.RUN_COMPLETED and event.data:
                            stage_output = event.data.get("response", "")

                    store.set(stage.id, stage_output)
                    final_output = stage_output

                    yield StepEvent(
                        type=StepEventType.STAGE_COMPLETED,
                        run_id=run_id,
                        stage_id=stage.id,
                        iteration=iteration,
                        trace_id=trace_id,
                    )

                # Check exit condition
                if not ConditionEvaluator.evaluate(self.condition, store.to_dict()):
                    break

            self._last_output = final_output

            yield StepEvent(
                type=StepEventType.RUN_COMPLETED,
                run_id=run_id,
                trace_id=trace_id,
                data={
                    "response": final_output,
                    "iterations": iteration,
                },
            )

        except Exception as e:
            yield StepEvent(
                type=StepEventType.RUN_FAILED,
                run_id=run_id,
                trace_id=trace_id,
                data={"error": str(e), "iteration": iteration},
            )
            raise
