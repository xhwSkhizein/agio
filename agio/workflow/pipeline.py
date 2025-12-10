"""
PipelineWorkflow - sequential execution of stages.

Executes stages in order, with each stage able to reference
outputs from all previous stages.

Wire-based Architecture:
- Events are written to context.wire
- Returns RunOutput with response and metrics
"""

import time
from uuid import uuid4

from agio.domain.events import StepEvent, StepEventType
from agio.workflow.base import BaseWorkflow
from agio.workflow.protocol import RunContext, RunOutput, RunMetrics
from agio.workflow.stage import Stage
from agio.workflow.store import OutputStore


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

    async def _execute(
        self,
        input: str,
        *,
        context: RunContext,
    ) -> RunOutput:
        start_time = time.time()
        run_id = str(uuid4())
        store = OutputStore()
        store.set("query", input)
        wire = context.wire

        trace_id = context.trace_id or str(uuid4())
        total_stages = len(self._stages)
        
        # Common workflow context for all events
        workflow_ctx = {
            "workflow_type": "pipeline",
            "workflow_id": self._id,
            "parent_run_id": context.metadata.get("parent_run_id"),
            "total_stages": total_stages,
            "depth": context.depth,
        }

        await wire.write(StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            trace_id=trace_id,
            data={"workflow_id": self._id, "type": "pipeline", "total_stages": total_stages},
            **workflow_ctx,
        ))

        final_output = ""
        stages_executed = 0
        total_tokens = 0

        try:
            for stage_index, stage in enumerate(self._stages):
                outputs_dict = store.to_dict()
                
                # Stage-specific context
                stage_ctx = {
                    **workflow_ctx,
                    "stage_id": stage.id,
                    "stage_name": stage.id,
                    "stage_index": stage_index,
                }

                # Check condition
                if not stage.should_execute(outputs_dict):
                    await wire.write(StepEvent(
                        type=StepEventType.STAGE_SKIPPED,
                        run_id=run_id,
                        trace_id=trace_id,
                        data={"condition": stage.condition},
                        **stage_ctx,
                    ))
                    continue

                await wire.write(StepEvent(
                    type=StepEventType.STAGE_STARTED,
                    run_id=run_id,
                    trace_id=trace_id,
                    **stage_ctx,
                ))

                # Build input
                stage_input = stage.build_input(outputs_dict)

                # Get Runnable instance
                runnable = self._resolve_runnable(stage.runnable)

                # Create child context with parent_run_id for nested events
                child_context = self._create_child_context(context, stage)
                child_context.trace_id = trace_id
                child_context.metadata["parent_run_id"] = run_id
                child_context.metadata["stage_id"] = stage.id
                child_context.metadata["stage_index"] = stage_index

                # Execute - events written to wire, get RunOutput
                result = await runnable.run(stage_input, context=child_context)
                stage_output = result.response or ""
                total_tokens += result.metrics.total_tokens

                # Store output
                store.set(stage.id, stage_output)
                final_output = stage_output
                stages_executed += 1

                await wire.write(StepEvent(
                    type=StepEventType.STAGE_COMPLETED,
                    run_id=run_id,
                    trace_id=trace_id,
                    data={"output_length": len(stage_output)},
                    **stage_ctx,
                ))

            duration = time.time() - start_time

            await wire.write(StepEvent(
                type=StepEventType.RUN_COMPLETED,
                run_id=run_id,
                trace_id=trace_id,
                data={"response": final_output, "stages_executed": stages_executed},
                **workflow_ctx,
            ))

            return RunOutput(
                response=final_output,
                run_id=run_id,
                workflow_id=self._id,
                metrics=RunMetrics(
                    duration=duration,
                    total_tokens=total_tokens,
                    stages_executed=stages_executed,
                ),
            )

        except Exception as e:
            await wire.write(StepEvent(
                type=StepEventType.RUN_FAILED,
                run_id=run_id,
                trace_id=trace_id,
                data={"error": str(e)},
                **workflow_ctx,
            ))
            raise
