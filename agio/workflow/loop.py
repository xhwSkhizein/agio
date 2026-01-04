"""
LoopWorkflow - iterative execution of nodes.

Repeats execution of nodes until condition is not met
or max iterations is reached.

Wire-based Architecture:
- Events are written to context.wire
- Returns RunOutput with response and metrics
- Uses WorkflowState for output caching and idempotency
"""

import time

from agio.domain.models import RunMetrics
from agio.llm import Model
from agio.runtime import RunnableExecutor, RunOutput
from agio.runtime.event_factory import EventFactory
from agio.runtime.protocol import ExecutionContext
from agio.storage.session.base import SessionStore
from agio.workflow.base import BaseWorkflow
from agio.workflow.condition import ConditionEvaluator
from agio.workflow.node import WorkflowNode
from agio.workflow.resolver import ContextResolver
from agio.workflow.state import WorkflowState


class LoopWorkflow(BaseWorkflow):
    """
    Loop Workflow.

    Repeats execution of nodes until condition is not met
    or max iterations is reached.

    Special variables:
    - {loop.iteration}: current iteration number (from 1)
    - {loop.last.node_id}: output of a node from previous iteration
    """

    def __init__(
        self,
        id: str,
        stages: list[WorkflowNode],
        condition: str = "true",
        max_iterations: int = 10,
        enable_termination_summary: bool = False,
        summary_model: "Model | None" = None,
        termination_summary_prompt: str | None = None,
        session_store: "SessionStore | None" = None,
    ):
        super().__init__(id, stages, session_store)
        self.condition = condition
        self.max_iterations = max_iterations
        self.enable_termination_summary = enable_termination_summary
        self.summary_model = summary_model
        self.termination_summary_prompt = termination_summary_prompt

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

        # Create ContextResolver for template resolution
        resolver = ContextResolver(
            session_id=context.session_id,
            workflow_id=self._id,
            store=session_store,
            state=state,
        )
        resolver.set_input(input)

        final_output = ""
        iteration = 0
        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        nodes_executed = 0
        last_iteration_outputs: dict[str, str] = {}  # Track outputs from previous iteration

        try:
            # Get nodes
            nodes = self.nodes

            while iteration < self.max_iterations:
                iteration += 1
                current_iteration_outputs: dict[str, str] = {}

                await wire.write(
                    ef.iteration_started(
                        iteration=iteration,
                        max_iterations=self.max_iterations,
                        workflow_type="loop",
                        workflow_id=self._id,
                    )
                )

                # Update loop context in resolver
                resolver.set_loop_context(iteration, last_iteration_outputs)

                # Execute all nodes
                for node in nodes:
                    node_id = node.id

                    # Build outputs dict for condition evaluation
                    outputs_dict = {"input": input}
                    outputs_dict.update(state.to_dict())
                    # Add loop context
                    outputs_dict["loop"] = {
                        "iteration": iteration,
                        "last": last_iteration_outputs,
                    }

                    # Check condition
                    if node.condition:
                        if not ConditionEvaluator.evaluate(node.condition, outputs_dict):
                            await wire.write(
                                ef.node_skipped(
                                    node_id=node_id,
                                    iteration=iteration,
                                    workflow_type="loop",
                                    workflow_id=self._id,
                                )
                            )
                            continue

                    await wire.write(
                        ef.node_started(
                            node_id=node_id,
                            iteration=iteration,
                            workflow_type="loop",
                            workflow_id=self._id,
                        )
                    )

                    # Resolve input template
                    node_input = await resolver.resolve_template(node.input_template)

                    runnable = self._resolve_runnable(node.runnable)
                    child_context = self._create_child_context(context, node)
                    # Set iteration in metadata for Step tracking
                    child_context = child_context.with_metadata(iteration=iteration)

                    # Execute via RunnableExecutor - handles Run lifecycle
                    executor = RunnableExecutor(store=session_store)
                    result = await executor.execute(runnable, node_input, child_context)
                    node_output = result.response or ""
                    if result.metrics:
                        total_tokens += result.metrics.total_tokens
                        input_tokens += result.metrics.input_tokens
                        output_tokens += result.metrics.output_tokens

                    # Update state cache
                    state.set_output(node_id, node_output)

                    current_iteration_outputs[node_id] = node_output
                    final_output = node_output
                    nodes_executed += 1

                    await wire.write(
                        ef.node_completed(
                            node_id=node_id,
                            data={"output_length": len(node_output)},
                            iteration=iteration,
                            workflow_type="loop",
                            workflow_id=self._id,
                        )
                    )

                # Update last iteration outputs for next iteration
                last_iteration_outputs = current_iteration_outputs

                # Check exit condition
                condition_dict = {"input": input}
                condition_dict.update(state.to_dict())
                condition_dict["loop"] = {
                    "iteration": iteration,
                    "last": last_iteration_outputs,
                }
                if not ConditionEvaluator.evaluate(self.condition, condition_dict):
                    break

            duration = time.time() - start_time
            termination_reason = "max_iterations" if iteration >= self.max_iterations else None

            # Generate termination summary if configured
            if termination_reason and self.enable_termination_summary:
                final_output = await self._generate_termination_summary(
                    state, termination_reason, iteration, input
                )

            return RunOutput(
                response=final_output,
                run_id=run_id,
                workflow_id=self._id,
                metrics=RunMetrics(
                    duration=duration,
                    total_tokens=total_tokens,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    iterations=iteration,
                    nodes_executed=nodes_executed,
                ),
                termination_reason=termination_reason,
            )

        except Exception as e:
            raise

    async def _generate_termination_summary(
        self,
        state: WorkflowState | None,
        termination_reason: str,
        iteration: int,
        input: str,
    ) -> str:
        """
        Generate summary when workflow is terminated.

        Args:
            state: WorkflowState with all node outputs
            termination_reason: Reason for termination
            iteration: Current iteration number
            input: Original workflow input

        Returns:
            Summary text
        """
        # If no summary model configured, generate simple text summary
        if not self.summary_model:
            return self._generate_simple_summary(state, termination_reason, iteration, input)

        # Build messages from state outputs
        messages = self._build_messages_from_state(state, input)

        # Use the model directly to generate summary
        # Note: For workflows, we use a simpler approach without step tracking
        from agio.agent.summarizer import (
            DEFAULT_TERMINATION_USER_PROMPT,
            _format_termination_reason,
        )
        from agio.config.template import renderer

        prompt_template = self.termination_summary_prompt or DEFAULT_TERMINATION_USER_PROMPT
        user_prompt = renderer.render(
            prompt_template,
            termination_reason=_format_termination_reason(termination_reason),
        )

        summary_messages = list(messages)
        summary_messages.append({"role": "user", "content": user_prompt})

        try:
            response = await self.summary_model.arun(summary_messages)
            return response.content if response.content else ""
        except Exception:
            # Fallback to simple summary
            return self._generate_simple_summary(state, termination_reason, iteration, input)

    def _generate_simple_summary(
        self,
        state: WorkflowState | None,
        termination_reason: str,
        iteration: int,
        input: str,
    ) -> str:
        """Generate a simple text summary without LLM."""
        summary_parts = [
            f"Workflow terminated due to reaching {termination_reason}.",
            f"Completed {iteration} iterations.",
            f"Original query: {input}",
            "",
            "Node outputs:",
        ]

        if state:
            outputs = state.to_dict()
            for node_id, value in outputs.items():
                # Truncate long outputs
                output_text = str(value)[:500]
                if len(str(value)) > 500:
                    output_text += "... [truncated]"
                summary_parts.append(f"- {node_id}: {output_text}")

        return "\n".join(summary_parts)

    def _build_messages_from_state(self, state: WorkflowState | None, input: str) -> list[dict]:
        """Build OpenAI format messages from state for summarizer."""
        messages = []

        # Add original query as user message
        messages.append({"role": "user", "content": input})

        # Add node outputs as assistant messages
        if state:
            outputs = state.to_dict()
            for node_id, value in outputs.items():
                messages.append({"role": "assistant", "content": f"[Node {node_id}]: {value}"})

        return messages
