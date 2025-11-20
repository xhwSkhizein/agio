# Refactor Execution Plan

## Phase 1: ModelDriver & Tool Loop (Core Logic Shift) ✅
- [x] **Define Interfaces**: Create `ModelDriver` (or `ModelLoop`) protocol in `agio/core/loop.py` (new file).
  - [x] Define `ModelEvent` (dataclass/pydantic) with types: `text_delta`, `tool_call`, `tool_result`, `usage`, `status_update`.
  - [x] Define `LoopState` to track steps, tokens, and pending calls.
  - [x] Define `AgentEvent` for unified event streaming.
- [x] **Abstract Tool Execution**: Create `ToolExecutor` in `agio/execution/tool_executor.py`.
  - [x] Implement `execute(call)` method handling tool lookup, argument parsing, and error catching.
  - [x] Port `AgentRunner._execute_tool` logic to `ToolExecutor`, improving error formatting.
- [x] **Implement ModelDriver**: Create `OpenAIModelDriver` in `agio/drivers/openai_driver.py`.
  - [x] Implement the loop: call LLM -> parse stream -> yield events -> execute tools -> yield events -> loop.
  - [x] Move tool call accumulation logic (currently in `AgentRunner`) into the driver/model layer.
  - [x] Add error handling and logging.
- [x] **Refactor AgentRunner (Preliminary)**:
  - [x] Instantiate `OpenAIModelDriver` inside `AgentRunner`.
  - [x] Replace the main `while step_num < max_steps` loop in `AgentRunner` with `async for event in driver.run(...)`.
  - [x] **DELETE**: Remove `tool_calls_accumulator`, `_execute_tool` (legacy), and manual tool call handling code from `AgentRunner`.
  - [x] Event-driven step management.
- [x] **Testing**:
  - [x] Basic integration test with demo.py (success).

## Phase 2: Runner Simplification & Hook Split ✅
- [x] **Refine AgentRunner**:
  - [x] Strip `AgentRunner` down to: `init` -> `build_context` -> `driver.run()` -> `hooks` -> `cleanup`.
  - [x] Move `_build_context` logic into dedicated `ContextBuilder` class.
  - [x] **DELETE**: Remove `_build_context` method (55 lines) from `AgentRunner`.
  - [x] AgentRunner reduced from 232 lines to 183 lines.
- [x] **Config Management**:
  - [x] Create `AgentRunConfig` for unified configuration.
  - [x] Move `max_steps`, `max_history_messages`, `max_rag_docs`, `max_memories` to config.
  - [x] Add timeout and concurrency configuration options.
  - [x] **DELETE**: Hardcoded constants in `AgentRunner` and `ContextBuilder`.
- [x] **Async Task Optimization**:
  - [x] Add `memory_update_async` config option.
  - [x] Support both sync and async memory updates.
- [x] **Testing**:
  - [x] All 11 tests pass.
  - [x] Integration tests (demo.py) pass.

## Phase 3: Streaming Event Protocol ✅
- [x] **Standardize Events**:
  - [x] Create `AgentEvent` schema in `agio/protocol/events.py`.
  - [x] Create event converter to map `ModelEvent` to `AgentEvent`.
  - [x] Define 15+ event types for comprehensive coverage.
- [x] **Update Output**:
  - [x] Add `AgentRunner.run_stream()` to yield `AgentEvent` objects.
  - [x] Keep `AgentRunner.run()` for backward compatibility (yields strings).
  - [x] Add `Agent.arun_stream()` as new public API.
- [x] **Documentation**:
  - [x] Create `docs/streaming_protocol.md` with complete protocol specification.
  - [x] Include examples for Python and JavaScript clients.
  - [x] Document SSE format and FastAPI integration.
- [x] **Testing**:
  - [x] All 11 tests pass.
  - [x] Create `demo_events.py` showcasing event stream.
  - [x] Verify backward compatibility with `demo.py`.

## Phase 4: Persistence & History ✅
- [x] **Event Storage**:
  - [x] Create `AgentRunRepository` interface in `agio/db/repository.py`.
  - [x] Implement `InMemoryRepository` for testing.
  - [x] Integrate event storage directly into `AgentRunner`.
  - [x] Store events with `run_id` and sequence number.
- [x] **Replay API**:
  - [x] Implement `get_events(run_id)` to fetch historical events.
  - [x] Implement `list_runs()` to list historical runs.
  - [x] Add `Agent.get_run_history()` for event replay.
  - [x] Add `Agent.list_runs()` for run listing.
- [x] **Testing**:
  - [x] All 11 tests pass.
  - [x] Create `demo_history.py` showcasing history and replay.
  - [x] Verify event storage and replay functionality.

## Phase 5: Observability & Reliability
- [ ] **Metrics Upgrade**:
  - [ ] Integrate metrics collection into `ModelDriver` loop.
  - [ ] Emit `metrics_snapshot` events periodically or at step ends.
- [ ] **Error Handling**:
  - [ ] Ensure `ModelDriver` catches LLM/Tool errors and emits `error` events without crashing the stream (unless fatal).
  - [ ] Implement graceful cancellation support.
- [ ] **CI/CD**:
  - [ ] Set up `pytest` and `lint` workflows.

## Phase 6: Ecosystem & Release
- [ ] **Documentation**:
  - [ ] Rewrite `README.md` with new usage examples.
  - [ ] Update `docs/` to reflect the new architecture.
- [ ] **Examples**:
  - [ ] Create `examples/basic_agent.py` using the new event stream.
  - [ ] Create `examples/web_demo/` (optional) showing event rendering.
