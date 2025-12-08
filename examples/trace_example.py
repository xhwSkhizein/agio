"""
Example: Using Trace/Span for observability with OTLP export.

This example demonstrates:
1. Wrapping event stream with TraceCollector
2. Automatic trace construction
3. Exporting to OTLP (Jaeger/Zipkin/SkyWalking)
4. Querying traces from TraceStore
"""

import asyncio
from uuid import uuid4

from agio.domain.events import StepEvent, StepEventType, StepDelta, create_step_delta_event
from agio.domain.models import Step, MessageRole, StepMetrics
from agio.observability import (
    TraceCollector,
    TraceStore,
    get_otlp_exporter,
    initialize_trace_store,
)


async def simulate_agent_execution() -> list[StepEvent]:
    """Simulate agent execution events"""
    run_id = str(uuid4())
    session_id = str(uuid4())

    events = [
        # Run started
        StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            data={
                "agent_id": "research_agent",
                "session_id": session_id,
                "query": "Research AI agents",
            },
        ),
        # LLM call completed
        StepEvent(
            type=StepEventType.STEP_COMPLETED,
            run_id=run_id,
            step_id=str(uuid4()),
            snapshot=Step(
                id=str(uuid4()),
                session_id=session_id,
                run_id=run_id,
                sequence=1,
                role=MessageRole.ASSISTANT,
                content="AI agents are software entities...",
                metrics=StepMetrics(
                    model_name="gpt-4o",
                    provider="openai",
                    input_tokens=100,
                    output_tokens=200,
                    total_tokens=300,
                    duration_ms=1500,
                    first_token_latency_ms=200,
                ),
            ),
        ),
        # Run completed
        StepEvent(
            type=StepEventType.RUN_COMPLETED,
            run_id=run_id,
            data={"response": "AI agents are software entities..."},
        ),
    ]

    return events


async def main():
    """Main example"""
    print("=== Agio Trace Example ===\n")

    # 1. Initialize TraceStore
    print("1. Initializing TraceStore...")
    store = await initialize_trace_store()
    print(f"   ✓ TraceStore initialized (MongoDB: {store.mongo_uri is not None})\n")

    # 2. Create TraceCollector
    print("2. Creating TraceCollector...")
    collector = TraceCollector(store=store)
    print("   ✓ TraceCollector created\n")

    # 3. Simulate agent execution
    print("3. Simulating agent execution...")
    events = await simulate_agent_execution()
    print(f"   ✓ Generated {len(events)} events\n")

    # 4. Wrap event stream with collector
    print("4. Collecting trace from events...")

    async def event_stream():
        for event in events:
            yield event

    trace_id = str(uuid4())
    collected_events = []

    async for event in collector.wrap_stream(
        event_stream(),
        trace_id=trace_id,
        agent_id="research_agent",
        input_query="Research AI agents",
    ):
        collected_events.append(event)
        print(f"   - Event: {event.type.value} (trace_id={event.trace_id[:8]}...)")

    print(f"   ✓ Collected {len(collected_events)} events\n")

    # 5. Query trace from store
    print("5. Querying trace from store...")
    trace = await store.get_trace(trace_id)
    if trace:
        print(f"   ✓ Trace found: {trace.trace_id}")
        print(f"     - Status: {trace.status.value}")
        print(f"     - Duration: {trace.duration_ms:.2f}ms")
        print(f"     - Spans: {len(trace.spans)}")
        print(f"     - Total tokens: {trace.total_tokens}")
        print(f"     - LLM calls: {trace.total_llm_calls}")

        for i, span in enumerate(trace.spans, 1):
            print(f"\n     Span {i}:")
            print(f"       - Kind: {span.kind.value}")
            print(f"       - Name: {span.name}")
            print(f"       - Duration: {span.duration_ms:.2f}ms" if span.duration_ms else "       - Duration: N/A")
            print(f"       - Status: {span.status.value}")
    else:
        print("   ✗ Trace not found")

    # 6. Export to OTLP (if configured)
    print("\n6. Exporting to OTLP...")
    exporter = get_otlp_exporter()
    if exporter.enabled:
        success = await exporter.export_trace(trace)
        if success:
            print(f"   ✓ Trace exported to {exporter.endpoint}")
        else:
            print("   ✗ Export failed")
    else:
        print("   ⊘ OTLP export not configured")
        print("     To enable, set environment variables:")
        print("       AGIO_OTLP_ENABLED=true")
        print("       AGIO_OTLP_ENDPOINT=http://localhost:4317")
        print("       AGIO_OTLP_PROTOCOL=grpc")

    print("\n=== Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
