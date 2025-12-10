"""
ParallelWorkflow - concurrent execution of stages.

Executes multiple stages in parallel, each with isolated state,
then merges results.

Wire-based Architecture:
- Events are written to context.wire
- Returns RunOutput with response and metrics
"""

import asyncio
import time
from uuid import uuid4

from agio.domain.events import StepEvent, StepEventType
from agio.workflow.base import BaseWorkflow
from agio.workflow.mapping import InputMapping
from agio.workflow.protocol import RunContext, RunOutput, RunMetrics
from agio.workflow.stage import Stage


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

    async def _execute(
        self,
        input: str,
        *,
        context: RunContext,
    ) -> RunOutput:
        start_time = time.time()
        run_id = str(uuid4())
        trace_id = context.trace_id or str(uuid4())
        wire = context.wire
        total_branches = len(self._stages)
        branch_ids = [stage.id for stage in self._stages]

        # Initial output snapshot
        initial_outputs = {"query": input}
        
        # Common workflow context for all events
        workflow_ctx = {
            "workflow_type": "parallel",
            "workflow_id": self._id,
            "parent_run_id": context.metadata.get("parent_run_id"),
            "total_stages": total_branches,
            "depth": context.depth,
        }

        await wire.write(StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            trace_id=trace_id,
            data={
                "workflow_id": self._id, 
                "type": "parallel", 
                "total_branches": total_branches,
                "branch_ids": branch_ids,
            },
            **workflow_ctx,
        ))

        async def run_branch(stage: Stage, branch_index: int) -> tuple[str, RunOutput]:
            """Execute a single branch, return output."""
            branch_ctx = {
                **workflow_ctx,
                "branch_id": stage.id,
                "stage_id": stage.id,
                "stage_name": stage.id,
                "stage_index": branch_index,
            }
            
            # Emit BRANCH_STARTED
            await wire.write(StepEvent(
                type=StepEventType.BRANCH_STARTED,
                run_id=run_id,
                trace_id=trace_id,
                **branch_ctx,
            ))
            
            branch_input = stage.build_input(initial_outputs)
            runnable = self._resolve_runnable(stage.runnable)
            child_context = self._create_child_context(context, stage)
            child_context.trace_id = trace_id
            child_context.metadata["parent_run_id"] = run_id
            child_context.metadata["branch_id"] = stage.id
            child_context.metadata["branch_index"] = branch_index

            # Execute - events written to shared wire
            result = await runnable.run(branch_input, context=child_context)
            return stage.id, result, branch_ctx

        try:
            # Execute all branches in parallel
            tasks = [run_branch(stage, idx) for idx, stage in enumerate(self._stages)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            branch_outputs: dict[str, str] = {}
            errors: list[tuple[str, Exception]] = []
            total_tokens = 0

            for result in results:
                if isinstance(result, Exception):
                    errors.append(("unknown", result))
                    continue

                branch_id, run_output, branch_ctx = result

                await wire.write(StepEvent(
                    type=StepEventType.BRANCH_COMPLETED,
                    run_id=run_id,
                    trace_id=trace_id,
                    data={"output_length": len(run_output.response or "")},
                    **branch_ctx,
                ))

                branch_outputs[branch_id] = run_output.response or ""
                total_tokens += run_output.metrics.total_tokens

            # Check for errors
            if errors:
                error_msg = "; ".join(f"{bid}: {str(e)}" for bid, e in errors)
                await wire.write(StepEvent(
                    type=StepEventType.RUN_FAILED,
                    run_id=run_id,
                    trace_id=trace_id,
                    data={"error": f"Branch errors: {error_msg}"},
                    **workflow_ctx,
                ))
                raise RuntimeError(f"Parallel execution failed: {error_msg}")

            # Merge outputs
            if self.merge_template:
                merged = InputMapping(self.merge_template).build(branch_outputs)
            else:
                merged = "\n\n".join(
                    f"[{branch_id}]:\n{output}"
                    for branch_id, output in branch_outputs.items()
                )

            duration = time.time() - start_time

            await wire.write(StepEvent(
                type=StepEventType.RUN_COMPLETED,
                run_id=run_id,
                trace_id=trace_id,
                data={
                    "response": merged,
                    "branch_outputs": {k: len(v) for k, v in branch_outputs.items()},
                    "branches_completed": len(branch_outputs),
                },
                **workflow_ctx,
            ))

            return RunOutput(
                response=merged,
                run_id=run_id,
                workflow_id=self._id,
                metrics=RunMetrics(
                    duration=duration,
                    total_tokens=total_tokens,
                    stages_executed=len(branch_outputs),
                ),
            )

        except Exception as e:
            if not isinstance(e, RuntimeError) or "Parallel execution failed" not in str(e):
                await wire.write(StepEvent(
                    type=StepEventType.RUN_FAILED,
                    run_id=run_id,
                    trace_id=trace_id,
                    data={"error": str(e)},
                    **workflow_ctx,
                ))
            raise
