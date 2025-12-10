"""
LoopWorkflow - iterative execution of stages.

Repeats execution of stages until condition is not met
or max iterations is reached.

Wire-based Architecture:
- Events are written to context.wire
- Returns RunOutput with response and metrics
"""

import time
from typing import TYPE_CHECKING
from uuid import uuid4

from agio.domain.events import StepEvent, StepEventType
from agio.workflow.base import BaseWorkflow
from agio.workflow.condition import ConditionEvaluator
from agio.workflow.protocol import RunContext, RunOutput, RunMetrics
from agio.workflow.stage import Stage
from agio.workflow.store import OutputStore

if TYPE_CHECKING:
    from agio.providers.llm import Model


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
        enable_termination_summary: bool = False,
        summary_model: "Model | None" = None,
        termination_summary_prompt: str | None = None,
    ):
        super().__init__(id, stages)
        self.condition = condition
        self.max_iterations = max_iterations
        self.enable_termination_summary = enable_termination_summary
        self.summary_model = summary_model
        self.termination_summary_prompt = termination_summary_prompt

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

        await wire.write(StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            trace_id=trace_id,
            data={
                "workflow_id": self._id,
                "type": "loop",
                "max_iterations": self.max_iterations,
            },
        ))

        final_output = ""
        iteration = 0
        total_tokens = 0
        stages_executed = 0

        try:
            while iteration < self.max_iterations:
                iteration += 1
                store.start_iteration()

                await wire.write(StepEvent(
                    type=StepEventType.ITERATION_STARTED,
                    run_id=run_id,
                    iteration=iteration,
                    trace_id=trace_id,
                    data={"max_iterations": self.max_iterations},
                ))

                # Execute all stages
                for stage in self._stages:
                    outputs_dict = store.to_dict()

                    if not stage.should_execute(outputs_dict):
                        await wire.write(StepEvent(
                            type=StepEventType.STAGE_SKIPPED,
                            run_id=run_id,
                            stage_id=stage.id,
                            iteration=iteration,
                            trace_id=trace_id,
                        ))
                        continue

                    await wire.write(StepEvent(
                        type=StepEventType.STAGE_STARTED,
                        run_id=run_id,
                        stage_id=stage.id,
                        iteration=iteration,
                        trace_id=trace_id,
                    ))

                    stage_input = stage.build_input(outputs_dict)
                    runnable = self._resolve_runnable(stage.runnable)
                    child_context = self._create_child_context(context, stage)
                    child_context.trace_id = trace_id

                    # Execute - events written to wire, get RunOutput
                    result = await runnable.run(stage_input, context=child_context)
                    stage_output = result.response or ""
                    total_tokens += result.metrics.total_tokens

                    store.set(stage.id, stage_output)
                    final_output = stage_output
                    stages_executed += 1

                    await wire.write(StepEvent(
                        type=StepEventType.STAGE_COMPLETED,
                        run_id=run_id,
                        stage_id=stage.id,
                        iteration=iteration,
                        trace_id=trace_id,
                    ))

                # Check exit condition
                if not ConditionEvaluator.evaluate(self.condition, store.to_dict()):
                    break

            duration = time.time() - start_time
            termination_reason = "max_iterations" if iteration >= self.max_iterations else None

            # Generate termination summary if configured
            if termination_reason and self.enable_termination_summary:
                final_output = await self._generate_termination_summary(
                    store, termination_reason, iteration
                )

            await wire.write(StepEvent(
                type=StepEventType.RUN_COMPLETED,
                run_id=run_id,
                trace_id=trace_id,
                data={
                    "response": final_output,
                    "iterations": iteration,
                    "termination_reason": termination_reason,
                },
            ))

            return RunOutput(
                response=final_output,
                run_id=run_id,
                workflow_id=self._id,
                metrics=RunMetrics(
                    duration=duration,
                    total_tokens=total_tokens,
                    iterations=iteration,
                    stages_executed=stages_executed,
                ),
                termination_reason=termination_reason,
            )

        except Exception as e:
            await wire.write(StepEvent(
                type=StepEventType.RUN_FAILED,
                run_id=run_id,
                trace_id=trace_id,
                data={"error": str(e), "iteration": iteration},
            ))
            raise

    async def _generate_termination_summary(
        self,
        store: OutputStore,
        termination_reason: str,
        iteration: int,
    ) -> str:
        """
        Generate summary when workflow is terminated.
        
        Args:
            store: Output store with all stage outputs
            termination_reason: Reason for termination
            iteration: Current iteration number
            
        Returns:
            Summary text
        """
        # If no summary model configured, generate simple text summary
        if not self.summary_model:
            return self._generate_simple_summary(store, termination_reason, iteration)
        
        # Build messages from store outputs
        messages = self._build_messages_from_store(store)
        
        # Use the model directly to generate summary
        # Note: For workflows, we use a simpler approach without step tracking
        from agio.runtime.summarizer import DEFAULT_TERMINATION_USER_PROMPT, _format_termination_reason
        
        prompt_template = self.termination_summary_prompt or DEFAULT_TERMINATION_USER_PROMPT
        user_prompt = prompt_template.format(
            termination_reason=_format_termination_reason(termination_reason),
        )
        
        summary_messages = list(messages)
        summary_messages.append({"role": "user", "content": user_prompt})
        
        try:
            response = await self.summary_model.arun(summary_messages)
            return response.content if response.content else ""
        except Exception as e:
            # Fallback to simple summary
            return self._generate_simple_summary(store, termination_reason, iteration)
    
    def _generate_simple_summary(
        self,
        store: OutputStore,
        termination_reason: str,
        iteration: int,
    ) -> str:
        """Generate a simple text summary without LLM."""
        outputs = store.to_dict()
        query = outputs.get("query", "Unknown query")
        
        summary_parts = [
            f"Workflow terminated due to reaching {termination_reason}.",
            f"Completed {iteration} iterations.",
            f"Original query: {query}",
            "",
            "Stage outputs:",
        ]
        
        for key, value in outputs.items():
            if key not in ("query", "loop"):
                # Truncate long outputs
                output_text = str(value)[:500]
                if len(str(value)) > 500:
                    output_text += "... [truncated]"
                summary_parts.append(f"- {key}: {output_text}")
        
        return "\n".join(summary_parts)
    
    def _build_messages_from_store(self, store: OutputStore) -> list[dict]:
        """Build OpenAI format messages from store for summarizer."""
        outputs = store.to_dict()
        messages = []
        
        # Add original query as user message
        if "query" in outputs:
            messages.append({"role": "user", "content": outputs["query"]})
        
        # Add stage outputs as assistant messages
        for key, value in outputs.items():
            if key not in ("query", "loop"):
                messages.append({
                    "role": "assistant",
                    "content": f"[Stage {key}]: {value}"
                })
        
        return messages
