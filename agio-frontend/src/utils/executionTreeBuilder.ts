/**
 * ExecutionTreeBuilder - Unified event processor for building execution tree
 * 
 * This replaces the scattered logic in eventHandlers.ts and nestedExecutionHandlers.ts
 * with a unified approach that builds a recursive execution tree.
 */

import type { 
  RunnableExecution, 
  ExecutionStep, 
  ExecutionTree,
} from '../types/execution'
import { createEmptyTree } from '../types/execution'
import { getEventMetrics } from './metricsHelpers'

interface SSEEventData {
  type?: string
  run_id?: string
  step_id?: string
  parent_run_id?: string
  depth?: number
  
  // Runnable identity (new fields from Phase 1)
  runnable_type?: string
  runnable_id?: string
  nesting_type?: string
  nested_runnable_id?: string
  
  // Execution context
  branch_id?: string
  
  // Content
  delta?: {
    content?: string
    reasoning_content?: string
    tool_calls?: Array<{
      id?: string
      index?: number
      function?: {
        name?: string
        arguments?: string
      }
    }>
  }
  snapshot?: {
    role?: string
    content?: string
    reasoning_content?: string
    tool_calls?: Array<{
      id?: string
      index?: number
      function?: {
        name?: string
        arguments?: string
      }
    }>
    tool_call_id?: string
    name?: string
    is_error?: boolean
    metrics?: Record<string, number>
  }
  data?: {
    query?: string
    session_id?: string
    response?: string
    metrics?: Record<string, number>
    error?: string
  }
  error?: string
}

/**
 * Mutable builder state for accumulating content during streaming
 */
interface BuilderState {
  // Content accumulation: key = `${runId}_${stepId}`, value = accumulated content
  contentAccum: Map<string, string>
  reasoningAccum: Map<string, string>
  
  // Tool call tracking: key = `${runId}_${stepId}_${index}`, value = tool_call_id
  toolCallTracker: Map<string, { toolCallId: string; finalized?: boolean }>
  
  // Processed delta keys for deduplication
  processedDeltas: Set<string>
}

function createBuilderState(): BuilderState {
  return {
    contentAccum: new Map(),
    reasoningAccum: new Map(),
    toolCallTracker: new Map(),
    processedDeltas: new Set(),
  }
}

/**
 * ExecutionTreeBuilder - Processes SSE events into a unified execution tree
 */
export class ExecutionTreeBuilder {
  private tree: ExecutionTree
  private state: BuilderState
  private sessionId: string | null = null
  
  constructor() {
    this.tree = createEmptyTree()
    this.state = createBuilderState()
  }
  
  /**
   * Reset the builder state (for new conversation)
   */
  reset(): void {
    this.tree = createEmptyTree()
    this.state = createBuilderState()
    this.sessionId = null
  }

  /**
   * Get current execution tree
   */
  getTree(): ExecutionTree {
    return this.tree
  }

  /**
   * Import an existing execution tree (used for hydrating history).
   */
  importTree(tree: ExecutionTree, sessionId?: string | null): void {
    this.tree = tree
    this.state = createBuilderState()
    this.sessionId = sessionId ?? this.sessionId
  }

  /**
   * Get session ID
   */
  getSessionId(): string | null {
    return this.sessionId
  }
  
  /**
   * Add a user message to the timeline
   */
  addUserMessage(content: string): void {
    const id = `user_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
    this.tree.messages.push({
      id,
      type: 'user',
      content,
      timestamp: Date.now(),
    })
  }
  
  /**
   * Process an SSE event and update the tree
   */
  processEvent(eventType: string, data: SSEEventData): void {
    switch (eventType) {
      case 'run_started':
        this.handleRunStarted(data)
        break
      case 'run_completed':
        this.handleRunCompleted(data)
        break
      case 'run_failed':
        this.handleRunFailed(data)
        break
      case 'step_delta':
        this.handleStepDelta(data)
        break
      case 'step_completed':
        this.handleStepCompleted(data)
        break
      case 'error':
        this.handleError(data)
        break
      case 'branch_started':
      case 'branch_completed':
      case 'iteration_started':
        // Structural events - currently just logged
        console.log(`Structural event: ${eventType}`, data)
        break
      default:
        console.log('Unhandled event:', eventType, data)
    }
  }
  
  private handleRunStarted(data: SSEEventData): void {
    const runId = data.run_id
    if (!runId) return

    // If already exists, don't add again to list/children
    if (this.tree.executionMap.has(runId)) {
      console.warn(`Duplicate run_started event for runId: ${runId}`)
      return
    }
    
    // Extract session ID
    if (data.data?.session_id) {
      this.sessionId = data.data.session_id
    }
    
    // Determine runnable type
    const runnableType = (data.runnable_type || 'agent') as 'agent'
    
    // Create new execution
    const exec: RunnableExecution = {
      id: runId,
      runnableId: data.runnable_id || data.nested_runnable_id || '',
      runnableType,
      nestingType: data.nesting_type as 'tool_call' | undefined,
      parentRunId: data.parent_run_id,
      depth: data.depth ?? 0,
      status: 'running',
      steps: [],
      children: [],
      startTime: Date.now(),
    }
    
    // Add to map
    this.tree.executionMap.set(runId, exec)
    
    // Establish parent-child relationship
    if (data.parent_run_id && this.tree.executionMap.has(data.parent_run_id)) {
      const parent = this.tree.executionMap.get(data.parent_run_id)!
      parent.children.push(exec)

      // If this child execution was triggered by a tool_call, link it to the tool_call step
      if (data.nesting_type === 'tool_call' && exec.runnableId) {
        // Find the matching tool_call step in parent that hasn't been linked yet
        // Match by runnableId extracted from tool name (e.g., "call_collector" -> "collector")
        const toolCallStep = parent.steps.find(
          step => step.type === 'tool_call' &&
            !step.childRunId &&
            (step.toolName.startsWith('call_')
              ? step.toolName.slice(5) === exec.runnableId
              : step.toolName === exec.runnableId)
        ) as Extract<ExecutionStep, { type: 'tool_call' }> | undefined

        if (toolCallStep) {
          toolCallStep.childRunId = runId
        }
      }
    } else {
      // Top-level execution
      this.tree.executions.push(exec)
    }
  }
  
  private handleRunCompleted(data: SSEEventData): void {
    const runId = data.run_id
    if (!runId) return
    
    const exec = this.tree.executionMap.get(runId)
    if (!exec) return
    
    exec.status = 'completed'
    exec.endTime = Date.now()
    exec.metrics = getEventMetrics(data)
  }
  
  private handleRunFailed(data: SSEEventData): void {
    const runId = data.run_id
    if (!runId) return
    
    const exec = this.tree.executionMap.get(runId)
    if (!exec) return
    
    exec.status = 'failed'
    exec.endTime = Date.now()
    
    // Add error message with unique ID
    const errorMsg = data.data?.error || data.error || 'Run failed'
    const id = `error_run_${runId}_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
    this.tree.messages.push({
      id,
      type: 'error',
      content: errorMsg,
      timestamp: Date.now(),
    })
  }
  
  private handleStepDelta(data: SSEEventData): void {
    const runId = data.run_id
    const stepId = data.step_id || 'unknown'
    if (!runId) return
    
    const exec = this.tree.executionMap.get(runId)
    if (!exec) return
    
    // Handle content delta
    if (data.delta?.content) {
      const contentKey = `${runId}_${stepId}`
      const currentLen = this.state.contentAccum.get(contentKey)?.length ?? 0
      const deltaKey = `${contentKey}_${currentLen}_${data.delta.content}`
      
      if (!this.state.processedDeltas.has(deltaKey)) {
        // Accumulate content
        const current = this.state.contentAccum.get(contentKey) ?? ''
        this.state.contentAccum.set(contentKey, current + data.delta.content)
        this.state.processedDeltas.add(deltaKey)
        
        // Update or create step
        this.updateAssistantStep(exec, stepId, this.state.contentAccum.get(contentKey)!)
      }
    }
    
    // Handle reasoning content delta
    if (data.delta?.reasoning_content) {
      const reasoningKey = `${runId}_${stepId}_reasoning`
      const currentLen = this.state.reasoningAccum.get(reasoningKey)?.length ?? 0
      const deltaKey = `${reasoningKey}_${currentLen}_${data.delta.reasoning_content}`
      
      if (!this.state.processedDeltas.has(deltaKey)) {
        const current = this.state.reasoningAccum.get(reasoningKey) ?? ''
        this.state.reasoningAccum.set(reasoningKey, current + data.delta.reasoning_content)
        this.state.processedDeltas.add(deltaKey)
        
        // Update step with reasoning
        this.updateAssistantStepReasoning(exec, stepId, this.state.reasoningAccum.get(reasoningKey)!)
      }
    }
    
    // Handle tool calls delta
    if (data.delta?.tool_calls) {
      for (const tc of data.delta.tool_calls) {
        this.handleToolCallDelta(exec, stepId, tc)
      }
    }
  }
  
  private handleStepCompleted(data: SSEEventData): void {
    const runId = data.run_id
    const stepId = data.step_id || 'unknown'
    const snapshot = data.snapshot
    if (!runId || !snapshot) return
    
    const exec = this.tree.executionMap.get(runId)
    if (!exec) return
    
    // Normalize metrics using getEventMetrics (handles OpenAI-style keys)
    const normalizedMetrics = getEventMetrics(data)

    // Handle assistant step completion
    if (snapshot.role === 'assistant') {
      if (snapshot.content) {
        this.updateAssistantStep(exec, stepId, snapshot.content, normalizedMetrics)
      }
      if (snapshot.reasoning_content) {
        this.updateAssistantStepReasoning(exec, stepId, snapshot.reasoning_content)
      }
      
      // Finalize tool calls
      if (snapshot.tool_calls) {
        for (const tc of snapshot.tool_calls) {
          this.finalizeToolCall(exec, stepId, tc)
        }
      }
    }
    
    // Handle tool result
    if (snapshot.role === 'tool' && snapshot.tool_call_id) {
      const existing = exec.steps.find(
        s => s.type === 'tool_result' && s.toolCallId === snapshot.tool_call_id
      )
      
      if (!existing) {
        exec.steps.push({
          type: 'tool_result',
          stepId,
          toolCallId: snapshot.tool_call_id,
          result: snapshot.content || '',
          status: snapshot.is_error ? 'failed' : 'completed',
          duration: normalizedMetrics?.duration_ms,
        })
      }
    }
  }
  
  private handleError(data: SSEEventData): void {
    const errorMsg = data.data?.error || data.error || 'Unknown error'
    const id = `error_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
    this.tree.messages.push({
      id,
      type: 'error',
      content: errorMsg,
      timestamp: Date.now(),
    })
  }
  
  private updateAssistantStep(
    exec: RunnableExecution, 
    stepId: string, 
    content: string,
    metrics?: ReturnType<typeof getEventMetrics>
  ): void {
    const existing = exec.steps.find(
      s => s.type === 'assistant_content' && s.stepId === stepId
    ) as Extract<ExecutionStep, { type: 'assistant_content' }> | undefined
    
    if (existing) {
      existing.content = content
      if (metrics) {
        // Metrics are already normalized by getEventMetrics
        existing.metrics = {
          input_tokens: metrics.input_tokens,
          output_tokens: metrics.output_tokens,
          total_tokens: metrics.total_tokens,
          duration_ms: metrics.duration_ms,
        }
      }
    } else {
      exec.steps.push({
        type: 'assistant_content',
        stepId,
        content,
        metrics: metrics ? {
          // Metrics are already normalized by getEventMetrics
          input_tokens: metrics.input_tokens,
          output_tokens: metrics.output_tokens,
          total_tokens: metrics.total_tokens,
          duration_ms: metrics.duration_ms,
        } : undefined,
      })
    }
  }
  
  private updateAssistantStepReasoning(
    exec: RunnableExecution,
    stepId: string,
    reasoning: string
  ): void {
    const existing = exec.steps.find(
      s => s.type === 'assistant_content' && s.stepId === stepId
    ) as Extract<ExecutionStep, { type: 'assistant_content' }> | undefined
    
    if (existing) {
      existing.reasoning_content = reasoning
    } else {
      exec.steps.push({
        type: 'assistant_content',
        stepId,
        content: '',
        reasoning_content: reasoning,
      })
    }
  }
  
  private handleToolCallDelta(
    exec: RunnableExecution,
    stepId: string,
    tc: { id?: string; index?: number; function?: { name?: string; arguments?: string } }
  ): void {
    const tcIndex = tc.index ?? 0
    const trackerKey = `${exec.id}_${stepId}_${tcIndex}`
    
    let toolCallId: string
    let existing: Extract<ExecutionStep, { type: 'tool_call' }> | undefined
    
    const tracked = this.state.toolCallTracker.get(trackerKey)
    if (tracked) {
      toolCallId = tracked.toolCallId
      existing = exec.steps.find(
        s => s.type === 'tool_call' && s.toolCallId === toolCallId
      ) as Extract<ExecutionStep, { type: 'tool_call' }> | undefined
      
      // Update ID if we receive the real one
      if (tc.id && tc.id !== toolCallId) {
        this.state.toolCallTracker.set(trackerKey, { toolCallId: tc.id, finalized: tracked.finalized })
        toolCallId = tc.id
        if (existing) existing.toolCallId = tc.id
      }
    } else {
      toolCallId = tc.id || `${stepId}_tc_${tcIndex}`
      this.state.toolCallTracker.set(trackerKey, { toolCallId })
    }
    
    if (existing) {
      if (tc.function?.name) existing.toolName = tc.function.name
      if (tc.function?.arguments && !tracked?.finalized) {
        existing.toolArgs = (existing.toolArgs || '') + tc.function.arguments
      }
    } else {
      exec.steps.push({
        type: 'tool_call',
        stepId,
        toolCallId,
        toolName: tc.function?.name || 'Unknown',
        toolArgs: tc.function?.arguments || '{}',
      })
    }
  }
  
  private finalizeToolCall(
    exec: RunnableExecution,
    stepId: string,
    tc: { id?: string; index?: number; function?: { name?: string; arguments?: string } }
  ): void {
    if (!tc.id) return
    
    const existing = exec.steps.find(
      s => s.type === 'tool_call' && s.toolCallId === tc.id
    ) as Extract<ExecutionStep, { type: 'tool_call' }> | undefined
    
    if (existing) {
      if (tc.function?.name) existing.toolName = tc.function.name
      if (tc.function?.arguments) existing.toolArgs = tc.function.arguments
    } else {
      exec.steps.push({
        type: 'tool_call',
        stepId,
        toolCallId: tc.id,
        toolName: tc.function?.name || 'Unknown',
        toolArgs: tc.function?.arguments || '{}',
      })
    }
    
    // Mark as finalized
    // Use same default index as handleToolCallDelta to ensure tracker key matches
    const tcIndex = tc.index ?? 0
    const trackerKey = `${exec.id}_${stepId}_${tcIndex}`
    const tracked = this.state.toolCallTracker.get(trackerKey)
    
    // If tracker key doesn't match, try to find by toolCallId
    if (!tracked || tracked.toolCallId !== tc.id) {
      // Search for tracker entry with matching toolCallId
      for (const [key, value] of this.state.toolCallTracker.entries()) {
        if (value.toolCallId === tc.id && key.startsWith(`${exec.id}_${stepId}_`)) {
          this.state.toolCallTracker.set(key, { ...value, finalized: true })
          return
        }
      }
      // If still not found, create new tracker entry with default index
      this.state.toolCallTracker.set(trackerKey, { toolCallId: tc.id, finalized: true })
    } else {
      this.state.toolCallTracker.set(trackerKey, { ...tracked, finalized: true })
    }
  }
}

/**
 * Create a new ExecutionTreeBuilder instance
 */
export function createExecutionTreeBuilder(): ExecutionTreeBuilder {
  return new ExecutionTreeBuilder()
}
