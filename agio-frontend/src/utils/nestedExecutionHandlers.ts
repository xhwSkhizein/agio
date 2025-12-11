/**
 * Handlers for nested execution events (RunnableTool parallel calls)
 */

import type { TimelineEvent } from '../types/chat'
import type { NestedExecution, NestedStep } from '../components/ParallelNestedRunnables'
import type { NestedExecutionMap } from '../types/chat'

interface SSEEventData {
  nested_runnable_id?: string
  depth?: number
  parent_run_id?: string
  run_id?: string
  step_id?: string
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
    metrics?: {
      duration_ms?: number
    }
  }
  data?: {
    metrics?: {
      input_tokens?: number
      output_tokens?: number
      duration_ms?: number
    }
  }
}

/**
 * Handle run_started for nested execution
 */
export function handleNestedRunStarted(
  data: SSEEventData,
  tracking: NestedExecutionMap,
  newEvents: TimelineEvent[]
): TimelineEvent[] {
  const nestedRunnableId = data.nested_runnable_id
  const parentRunId = data.parent_run_id
  const nestedRunId = data.run_id

  if (!nestedRunnableId || !parentRunId || !nestedRunId) {
    return newEvents
  }

  // Get or create the executions map for this parent
  if (!tracking.executions.has(parentRunId)) {
    tracking.executions.set(parentRunId, new Map())
  }
  const executionsMap = tracking.executions.get(parentRunId)!

  // Create new nested execution entry with steps array
  const newExec: NestedExecution = {
    id: nestedRunId,
    runnableId: nestedRunnableId,
    status: 'running',
    steps: [],
    startTime: Date.now(),
  }
  executionsMap.set(nestedRunId, newExec)

  // Get parent step_id from the most recent Assistant Step with tool_calls
  // This groups all parallel calls from the same parent step into one batch
  const parentStepId = tracking.parentStepIdForBatches.get(parentRunId) || 'unknown'
  const batchKey = `${parentRunId}_${parentStepId}`

  // Get or create batch
  let batch = tracking.parallelBatches.get(batchKey)
  if (!batch) {
    const batchId = `parallel_nested_${batchKey}`
    batch = {
      batchId,
      executionIds: new Set([nestedRunId]),
      stepId: parentStepId,
    }
    tracking.parallelBatches.set(batchKey, batch)
  } else {
    batch.executionIds.add(nestedRunId)
  }

  // Create or update container event for this batch
  const containerEventId = batch.batchId
  const containerIdx = newEvents.findIndex(e => e.id === containerEventId)

  const batchExecutions = Array.from(executionsMap.values()).filter(exec =>
    batch.executionIds.has(exec.id)
  )

  if (containerIdx !== -1) {
    newEvents[containerIdx] = {
      ...newEvents[containerIdx],
      nestedExecutions: batchExecutions,
    }
  } else {
    newEvents.push({
      id: containerEventId,
      type: 'parallel_nested',
      parentRunId,
      nestedExecutions: batchExecutions,
      timestamp: Date.now(),
    })
  }

  return newEvents
}

/**
 * Handle run_completed/run_failed for nested execution
 */
export function handleNestedRunCompleted(
  data: SSEEventData,
  tracking: NestedExecutionMap,
  newEvents: TimelineEvent[],
  status: 'completed' | 'failed'
): TimelineEvent[] {
  const parentRunId = data.parent_run_id
  const nestedRunId = data.run_id

  if (!parentRunId || !nestedRunId) {
    return newEvents
  }

  const executionsMap = tracking.executions.get(parentRunId)
  if (!executionsMap || !executionsMap.has(nestedRunId)) {
    return newEvents
  }

  // Update execution status
  const exec = executionsMap.get(nestedRunId)!
  exec.status = status
  exec.endTime = Date.now()
  if (data.data?.metrics) {
    exec.metrics = data.data.metrics
  }

  // Update container event for the batch containing this execution
  const parentStepId = tracking.parentStepIdForBatches.get(parentRunId) || 'unknown'
  const batchKey = `${parentRunId}_${parentStepId}`
  const batch = tracking.parallelBatches.get(batchKey)
  if (batch) {
    const containerEventId = batch.batchId
    const containerIdx = newEvents.findIndex(e => e.id === containerEventId)
    if (containerIdx !== -1) {
      // Get executions for this batch only
      const batchExecutions = Array.from(executionsMap.values()).filter(exec =>
        batch.executionIds.has(exec.id)
      )
      newEvents[containerIdx] = {
        ...newEvents[containerIdx],
        nestedExecutions: batchExecutions,
      }
    }
  }

  return newEvents
}

/**
 * Handle step_delta for nested execution
 */
export function handleNestedStepDelta(
  data: SSEEventData,
  tracking: NestedExecutionMap,
  newEvents: TimelineEvent[],
  nestedStreamingContentRef?: { [key: string]: string },
  nestedStreamingReasoningContentRef?: { [key: string]: string }
): TimelineEvent[] {
  const parentRunId = data.parent_run_id
  const nestedRunId = data.run_id
  const stepId = data.step_id || 'unknown'

  if (!parentRunId || !nestedRunId) {
    return newEvents
  }

  const executionsMap = tracking.executions.get(parentRunId)
  if (!executionsMap || !executionsMap.has(nestedRunId)) {
    return newEvents
  }

  const exec = executionsMap.get(nestedRunId)!

  // Track step_id for this nested execution
  tracking.nestedRunStepId.set(nestedRunId, stepId)

  // Get batch using parentRunId + parentStepId (not nested stepId)
  const parentStepId = tracking.parentStepIdForBatches.get(parentRunId) || 'unknown'
  const batchKey = `${parentRunId}_${parentStepId}`
  let batch = tracking.parallelBatches.get(batchKey)

  if (!batch) {
    // Create new batch for this step
    const batchId = `parallel_nested_${batchKey}`
    batch = {
      batchId,
      executionIds: new Set([nestedRunId]),
      stepId,
    }
    tracking.parallelBatches.set(batchKey, batch)
  } else {
    // Add to existing batch
    batch.executionIds.add(nestedRunId)
  }

  // Handle assistant content - use accumulated content from ref (similar to main events)
  // This ensures consistency and prevents duplicate accumulation
  const contentKey = `${nestedRunId}_${stepId}`
  const reasoningKey = `${nestedRunId}_${stepId}_reasoning`
  
  if (nestedStreamingContentRef && nestedStreamingContentRef[contentKey] !== undefined) {
    const accumulatedContent = nestedStreamingContentRef[contentKey]
    const existingStep = exec.steps.find(
      s => s.type === 'assistant_content' && s.stepId === stepId
    ) as Extract<NestedStep, { type: 'assistant_content' }> | undefined

    if (existingStep) {
      // Replace with accumulated content (don't append)
      existingStep.content = accumulatedContent
    } else {
      // Create new assistant content step with accumulated content
      exec.steps.push({
        type: 'assistant_content',
        stepId,
        content: accumulatedContent,
      })
    }
  }

  // Handle reasoning_content - use accumulated content from ref
  if (nestedStreamingReasoningContentRef && nestedStreamingReasoningContentRef[reasoningKey] !== undefined) {
    const accumulatedReasoning = nestedStreamingReasoningContentRef[reasoningKey]
    const existingStep = exec.steps.find(
      s => s.type === 'assistant_content' && s.stepId === stepId
    ) as Extract<NestedStep, { type: 'assistant_content' }> | undefined

    if (existingStep) {
      // Replace with accumulated reasoning content
      existingStep.reasoning_content = accumulatedReasoning
    } else {
      // Create new assistant content step with reasoning_content
      // If content also exists, use it; otherwise use empty string
      const contentKey = `${nestedRunId}_${stepId}`
      const existingContent = nestedStreamingContentRef?.[contentKey] || ''
      exec.steps.push({
        type: 'assistant_content',
        stepId,
        content: existingContent,
        reasoning_content: accumulatedReasoning,
      })
    }
  }

  // Handle tool calls - properly parse JSON arguments
  if (data.delta?.tool_calls) {
    for (const tc of data.delta.tool_calls) {
      const tcIndex = tc.index ?? 0
      const trackerKey = `${nestedRunId}_${stepId}_${tcIndex}`
      const tracker = tracking.nestedToolCallTracker

      // Check if we already have a tracker entry for this tool_call
      let toolCallId: string
      let existingStep: Extract<NestedStep, { type: 'tool_call' }> | undefined

      if (tracker.has(trackerKey)) {
        // Use the tracked tool_call_id to find existing step
        toolCallId = tracker.get(trackerKey)!.toolCallId
        existingStep = exec.steps.find(
          s => s.type === 'tool_call' && s.toolCallId === toolCallId
        ) as Extract<NestedStep, { type: 'tool_call' }> | undefined

        // Update tracker if we receive the real ID
        if (tc.id && tc.id !== toolCallId) {
          tracker.set(trackerKey, { toolCallId: tc.id, stepIndex: tracker.get(trackerKey)!.stepIndex })
          toolCallId = tc.id
          // Also update the step's toolCallId
          if (existingStep) {
            existingStep.toolCallId = tc.id
          }
        }
      } else {
        // First time seeing this tool_call
        toolCallId = tc.id || `${stepId}_tc_${tcIndex}`
        // Try to find by temporary ID first
        existingStep = exec.steps.find(
          s => s.type === 'tool_call' && s.toolCallId === toolCallId
        ) as Extract<NestedStep, { type: 'tool_call' }> | undefined

        // Create tracker entry (stepIndex will be set after push)
        tracker.set(trackerKey, { toolCallId, stepIndex: -1 })
      }

      if (existingStep) {
        // Accumulate tool name and arguments (arguments are JSON strings)
        if (tc.function?.name) {
          existingStep.toolName = tc.function.name  // Name is complete, not incremental
        }
        if (tc.function?.arguments) {
          // Check if this tool_call has been finalized (from step_completed)
          const trackerEntry = tracker.get(trackerKey)
          if (trackerEntry?.finalized) {
            // Already finalized, skip accumulation to avoid duplication
            // This can happen if step_delta arrives after step_completed
          } else {
            // Arguments are streamed JSON strings - append directly
            // ToolCall component will parse and format for display
            existingStep.toolArgs = (existingStep.toolArgs || '') + tc.function.arguments
          }
        }
        // Update toolCallId if we receive the real ID
        if (tc.id && tc.id !== existingStep.toolCallId) {
          existingStep.toolCallId = tc.id
          const trackerEntry = tracker.get(trackerKey)!
          tracker.set(trackerKey, { toolCallId: tc.id, stepIndex: trackerEntry.stepIndex, finalized: trackerEntry.finalized })
        }
      } else {
        // Create new tool call step
        const newStep: Extract<NestedStep, { type: 'tool_call' }> = {
          type: 'tool_call',
          toolCallId,
          toolName: tc.function?.name || 'Unknown',
          toolArgs: tc.function?.arguments || '{}',
          stepId,
        }
        exec.steps.push(newStep)
        // Update tracker with correct step index
        const trackerEntry = tracker.get(trackerKey)!
        tracker.set(trackerKey, { toolCallId, stepIndex: exec.steps.length - 1, finalized: trackerEntry.finalized })
      }
    }
  }

  // Update container event for the batch containing this execution
  if (batch) {
    const containerEventId = batch.batchId
    const containerIdx = newEvents.findIndex(e => e.id === containerEventId)

    // Get executions for this batch only
    const batchExecutions = Array.from(executionsMap.values()).filter(exec =>
      batch.executionIds.has(exec.id)
    )

    if (containerIdx !== -1) {
      // Update existing container
      newEvents[containerIdx] = {
        ...newEvents[containerIdx],
        nestedExecutions: batchExecutions,
      }
    } else {
      // Create new container event for this batch
      newEvents.push({
        id: containerEventId,
        type: 'parallel_nested',
        parentRunId,
        nestedExecutions: batchExecutions,
        timestamp: Date.now(),
      })
    }
  }

  return newEvents
}

/**
 * Handle step_completed for nested execution
 */
export function handleNestedStepCompleted(
  data: SSEEventData,
  tracking: NestedExecutionMap,
  newEvents: TimelineEvent[]
): TimelineEvent[] {
  const parentRunId = data.parent_run_id
  const nestedRunId = data.run_id
  const snapshot = data.snapshot
  const stepId = data.step_id || 'unknown'

  if (!parentRunId || !nestedRunId || !snapshot) {
    return newEvents
  }

  const executionsMap = tracking.executions.get(parentRunId)
  if (!executionsMap || !executionsMap.has(nestedRunId)) {
    return newEvents
  }

  const exec = executionsMap.get(nestedRunId)!

  // Track step_id for this nested execution
  tracking.nestedRunStepId.set(nestedRunId, stepId)

  // Get batch using parentRunId + parentStepId (not nested stepId)
  const parentStepId = tracking.parentStepIdForBatches.get(parentRunId) || 'unknown'
  const batchKey = `${parentRunId}_${parentStepId}`
  let batch = tracking.parallelBatches.get(batchKey)

  if (!batch) {
    // Create new batch for this step
    const batchId = `parallel_nested_${batchKey}`
    batch = {
      batchId,
      executionIds: new Set([nestedRunId]),
      stepId,
    }
    tracking.parallelBatches.set(batchKey, batch)
  } else {
    // Add to existing batch
    batch.executionIds.add(nestedRunId)
  }

  // Handle assistant step completion - finalize content
  if (snapshot.role === 'assistant') {
    // Update existing assistant content step if exists (from step_delta)
    const existingContentStep = exec.steps.find(
      s => s.type === 'assistant_content' && s.stepId === stepId
    ) as Extract<NestedStep, { type: 'assistant_content' }> | undefined

    if (existingContentStep) {
      // Update with final content from snapshot (may be more complete than delta)
      if (snapshot.content && snapshot.content !== existingContentStep.content) {
        existingContentStep.content = snapshot.content
      }
      // Update reasoning_content if present
      if (snapshot.reasoning_content !== undefined) {
        existingContentStep.reasoning_content = snapshot.reasoning_content
      }
    } else if (snapshot.content || snapshot.reasoning_content) {
      // Only create if step_delta didn't create it (shouldn't happen normally)
      exec.steps.push({
        type: 'assistant_content',
        stepId,
        content: snapshot.content || '',
        reasoning_content: snapshot.reasoning_content,
      })
    }

    // Handle tool calls from snapshot - only update existing ones, don't add new ones
    // (step_delta should have already created them)
    if (snapshot.tool_calls && Array.isArray(snapshot.tool_calls)) {
      for (const tc of snapshot.tool_calls) {
        if (!tc.id) continue

        // Try to find by tool_call_id first
        let existingStep = exec.steps.find(
          s => s.type === 'tool_call' && s.toolCallId === tc.id
        ) as Extract<NestedStep, { type: 'tool_call' }> | undefined

        // If not found, check tracker for temporary IDs
        if (!existingStep) {
          const tracker = tracking.nestedToolCallTracker
          for (const [key, value] of tracker.entries()) {
            if (value.toolCallId === tc.id && key.startsWith(`${nestedRunId}_${stepId}_`)) {
              // Found in tracker, try to find step by temporary ID
              existingStep = exec.steps.find(
                s => s.type === 'tool_call' && s.toolCallId === value.toolCallId
              ) as Extract<NestedStep, { type: 'tool_call' }> | undefined
              break
            }
          }
        }

        if (existingStep) {
          // Update existing tool call with complete info from snapshot
          // Replace (don't append) to avoid duplication
          if (tc.function?.name) {
            existingStep.toolName = tc.function.name
          }
          if (tc.function?.arguments) {
            existingStep.toolArgs = tc.function.arguments
          }
          // Ensure toolCallId is set correctly
          if (tc.id !== existingStep.toolCallId) {
            existingStep.toolCallId = tc.id
          }
          // Mark as finalized to prevent further accumulation from step_delta
          const tcIndex = tc.index ?? 0
          const trackerKey = `${nestedRunId}_${stepId}_${tcIndex}`
          const trackerEntry = tracking.nestedToolCallTracker.get(trackerKey)
          if (trackerEntry) {
            tracking.nestedToolCallTracker.set(trackerKey, { ...trackerEntry, finalized: true })
          }
        } else {
          // Only add if step_delta didn't create it (shouldn't happen normally)
          // This might happen if step_completed arrives before step_delta
          exec.steps.push({
            type: 'tool_call',
            toolCallId: tc.id,
            toolName: tc.function?.name || 'Unknown',
            toolArgs: tc.function?.arguments || '{}',
            stepId,
          })
          // Also update tracker (mark as finalized since it came from step_completed)
          const tcIndex = tc.index ?? exec.steps.length - 1
          const trackerKey = `${nestedRunId}_${stepId}_${tcIndex}`
          tracking.nestedToolCallTracker.set(trackerKey, { toolCallId: tc.id, stepIndex: exec.steps.length - 1, finalized: true })
        }
      }
    }
  }

  // Handle tool result step
  if (snapshot.role === 'tool' && snapshot.tool_call_id) {
    // Check if tool_result step already exists
    const existingResult = exec.steps.find(
      s => s.type === 'tool_result' && s.toolCallId === snapshot.tool_call_id
    )

    if (!existingResult) {
      // Add tool result step (will be rendered with corresponding tool_call)
      exec.steps.push({
        type: 'tool_result',
        toolCallId: snapshot.tool_call_id,
        result: snapshot.content || '',
        status: snapshot.is_error ? 'failed' : 'completed',
        duration: snapshot.metrics?.duration_ms,
      })
    }
  }

  // Update container event for the batch containing this execution
  if (batch) {
    const containerEventId = batch.batchId
    const containerIdx = newEvents.findIndex(e => e.id === containerEventId)

    // Get executions for this batch only
    const batchExecutions = Array.from(executionsMap.values()).filter(exec =>
      batch.executionIds.has(exec.id)
    )

    if (containerIdx !== -1) {
      // Update existing container
      newEvents[containerIdx] = {
        ...newEvents[containerIdx],
        nestedExecutions: batchExecutions,
      }
    } else {
      // Create new container event for this batch
      newEvents.push({
        id: containerEventId,
        type: 'parallel_nested',
        parentRunId,
        nestedExecutions: batchExecutions,
        timestamp: Date.now(),
      })
    }
  }

  return newEvents
}
