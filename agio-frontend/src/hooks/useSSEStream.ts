/**
 * Hook for handling SSE stream processing
 */

import { useRef, type MutableRefObject } from 'react'
import type { TimelineEvent, ToolCallTracker, NestedExecutionMap } from '../types/chat'
import type { WorkflowNode } from '../types/workflow'
import {
  handleStepDelta,
  handleStepCompleted,
  handleRunStarted,
  handleRunCompleted,
  handleWorkflowStageEvent,
  handleWorkflowBranchEvent,
} from '../utils/eventHandlers'
import {
  handleNestedRunStarted,
  handleNestedRunCompleted,
  handleNestedStepDelta,
  handleNestedStepCompleted,
} from '../utils/nestedExecutionHandlers'

interface UseSSEStreamOptions {
  onEvent: (eventsOrUpdater: TimelineEvent[] | ((prev: TimelineEvent[]) => TimelineEvent[])) => void
  onSessionId?: (sessionId: string) => void
  onRunId?: (runId: string | null) => void
  onRunCompleted?: () => void
  onWorkflowNodesUpdate?: (nodes: Map<string, WorkflowNode>) => void
  workflowNodesRef: MutableRefObject<Map<string, WorkflowNode>>
}

export function useSSEStream({
  onEvent,
  onSessionId,
  onRunId,
  onRunCompleted,
  onWorkflowNodesUpdate,
  workflowNodesRef,
}: UseSSEStreamOptions) {
  const toolCallTrackerRef = useRef<ToolCallTracker>({})
  const streamingContentRef = useRef<{ [stepId: string]: string }>({})
  const streamingReasoningContentRef = useRef<{ [stepId: string]: string }>({})
  // Track processed delta content to prevent duplicate accumulation
  // Key: `${stepId}_${deltaContent}`, Value: true
  const processedDeltaRef = useRef<Set<string>>(new Set())
  const processedReasoningDeltaRef = useRef<Set<string>>(new Set())
  const nestedTrackingRef = useRef<NestedExecutionMap>({
    executions: new Map(),
    parallelBatches: new Map(),
    nestedRunStepId: new Map(),
    parentStepIdForBatches: new Map(),
    nestedToolCallTracker: new Map(),
  })
  // Track accumulated content for nested executions (similar to streamingContentRef for main events)
  // Key: `${nestedRunId}_${stepId}`, Value: accumulated content string
  const nestedStreamingContentRef = useRef<{ [key: string]: string }>({})
  const nestedStreamingReasoningContentRef = useRef<{ [key: string]: string }>({})
  // Track processed delta content for nested executions to prevent duplicate accumulation
  // Key: `${nestedRunId}_${stepId}_${currentLength}_${deltaContent}`, Value: true
  const nestedProcessedDeltaRef = useRef<Set<string>>(new Set())
  const nestedProcessedReasoningDeltaRef = useRef<Set<string>>(new Set())

  const resetTracking = () => {
    toolCallTrackerRef.current = {}
    streamingContentRef.current = {}
    streamingReasoningContentRef.current = {}
    processedDeltaRef.current = new Set()
    processedReasoningDeltaRef.current = new Set()
    nestedProcessedDeltaRef.current = new Set()
    nestedProcessedReasoningDeltaRef.current = new Set()
    nestedStreamingContentRef.current = {}
    nestedStreamingReasoningContentRef.current = {}
    nestedTrackingRef.current = {
      executions: new Map(),
      parallelBatches: new Map(),
      nestedRunStepId: new Map(),
      parentStepIdForBatches: new Map(),
      nestedToolCallTracker: new Map(),
    }
  }

  const processSSEEvent = (eventType: string, data: any) => {
    const stepId = data.step_id || 'unknown'
    const nestedRunnableId = data.nested_runnable_id
    const nestedDepth = data.depth || 0
    const parentRunId = data.parent_run_id

    // For main step_delta events with content, we need to prevent duplicate accumulation
    // This can happen due to React StrictMode double-renders or other React batching behaviors
    // Key includes current length BEFORE accumulation to distinguish consecutive identical deltas
    // e.g., two "a" deltas would have keys: "step_run_0_a" and "step_run_1_a"
    let contentDeltaKey: string | null = null
    if (eventType === 'step_delta' && data.delta?.content && nestedDepth === 0) {
      const currentLength = streamingContentRef.current[stepId]?.length || 0
      contentDeltaKey = `${stepId}_${data.run_id || ''}_${currentLength}_${data.delta.content}`
    }

    // Similar handling for reasoning_content
    let reasoningDeltaKey: string | null = null
    if (eventType === 'step_delta' && data.delta?.reasoning_content && nestedDepth === 0) {
      const currentLength = streamingReasoningContentRef.current[stepId]?.length || 0
      reasoningDeltaKey = `${stepId}_reasoning_${data.run_id || ''}_${currentLength}_${data.delta.reasoning_content}`
    }

    // Check if this content delta has been processed before
    if (contentDeltaKey && processedDeltaRef.current.has(contentDeltaKey)) {
      // Already processed - just update the display without re-accumulating
      onEvent((prev: TimelineEvent[]) => {
        const newEvents = [...prev]
        if (eventType === 'step_delta') {
          return handleStepDelta(
            data,
            newEvents,
            toolCallTrackerRef.current,
            streamingContentRef.current,
            nestedTrackingRef.current.parentStepIdForBatches,
            streamingReasoningContentRef.current
          )
        }
        return newEvents
      })
      return
    }

    // Check if reasoning_content delta has been processed before
    if (reasoningDeltaKey && processedReasoningDeltaRef.current.has(reasoningDeltaKey)) {
      onEvent((prev: TimelineEvent[]) => {
        const newEvents = [...prev]
        if (eventType === 'step_delta') {
          return handleStepDelta(
            data,
            newEvents,
            toolCallTrackerRef.current,
            streamingContentRef.current,
            nestedTrackingRef.current.parentStepIdForBatches,
            streamingReasoningContentRef.current
          )
        }
        return newEvents
      })
      return
    }

    // Accumulate content OUTSIDE onEvent callback to ensure it only happens once per event
    // ONLY for main events (depth === 0) - nested events have their own content tracking
    if (eventType === 'step_delta' && data.delta?.content && nestedDepth === 0) {
      const contentRef = streamingContentRef.current
      if (!contentRef[stepId]) {
        contentRef[stepId] = ''
      }
      contentRef[stepId] += data.delta.content
      
      // Mark as processed AFTER accumulating - the key was computed with length BEFORE accumulation
      if (contentDeltaKey) {
        processedDeltaRef.current.add(contentDeltaKey)
      }
    }

    // Accumulate reasoning_content OUTSIDE onEvent callback
    if (eventType === 'step_delta' && data.delta?.reasoning_content && nestedDepth === 0) {
      const reasoningRef = streamingReasoningContentRef.current
      if (!reasoningRef[stepId]) {
        reasoningRef[stepId] = ''
      }
      reasoningRef[stepId] += data.delta.reasoning_content
      
      if (reasoningDeltaKey) {
        processedReasoningDeltaRef.current.add(reasoningDeltaKey)
      }
    }

    // For nested step_delta events with content, compute dedupe key and accumulate BEFORE onEvent
    // This prevents duplicate accumulation when React calls updater multiple times
    let nestedContentDeltaKey: string | null = null
    let nestedContentAlreadyProcessed = false
    let nestedReasoningDeltaKey: string | null = null
    let nestedReasoningAlreadyProcessed = false
    
    if (eventType === 'step_delta' && nestedDepth > 0 && parentRunId) {
      const nestedRunId = data.run_id || ''
      
      // Handle content delta
      if (data.delta?.content) {
        // Get current content length from accumulated ref (not from exec.steps)
        const contentKey = `${nestedRunId}_${stepId}`
        const currentLength = nestedStreamingContentRef.current[contentKey]?.length || 0
        
        // Create dedupe key using nestedRunId + stepId + currentLength + delta content
        nestedContentDeltaKey = `${nestedRunId}_${stepId}_${currentLength}_${data.delta.content}`
        
        // Check if already processed
        nestedContentAlreadyProcessed = nestedProcessedDeltaRef.current.has(nestedContentDeltaKey)
        
        // Accumulate content OUTSIDE onEvent callback (similar to main events)
        if (!nestedContentAlreadyProcessed) {
          if (!nestedStreamingContentRef.current[contentKey]) {
            nestedStreamingContentRef.current[contentKey] = ''
          }
          nestedStreamingContentRef.current[contentKey] += data.delta.content
          // Mark as processed AFTER accumulating
          nestedProcessedDeltaRef.current.add(nestedContentDeltaKey)
        }
      }
      
      // Handle reasoning_content delta
      if (data.delta?.reasoning_content) {
        const reasoningKey = `${nestedRunId}_${stepId}_reasoning`
        const currentLength = nestedStreamingReasoningContentRef.current[reasoningKey]?.length || 0
        
        nestedReasoningDeltaKey = `${nestedRunId}_${stepId}_reasoning_${currentLength}_${data.delta.reasoning_content}`
        nestedReasoningAlreadyProcessed = nestedProcessedReasoningDeltaRef.current.has(nestedReasoningDeltaKey)
        
        if (!nestedReasoningAlreadyProcessed) {
          if (!nestedStreamingReasoningContentRef.current[reasoningKey]) {
            nestedStreamingReasoningContentRef.current[reasoningKey] = ''
          }
          nestedStreamingReasoningContentRef.current[reasoningKey] += data.delta.reasoning_content
          nestedProcessedReasoningDeltaRef.current.add(nestedReasoningDeltaKey)
        }
      }
    }

    onEvent((prev) => {
      const newEvents = [...prev]

      // Handle nested events - group by parent_run_id for parallel display
      if (nestedDepth > 0 && parentRunId) {
        if (eventType === 'run_started' && nestedRunnableId) {
          return handleNestedRunStarted(data, nestedTrackingRef.current, newEvents)
        }

        if (eventType === 'run_completed') {
          return handleNestedRunCompleted(data, nestedTrackingRef.current, newEvents, 'completed')
        }

        if (eventType === 'run_failed') {
          return handleNestedRunCompleted(data, nestedTrackingRef.current, newEvents, 'failed')
        }

        if (eventType === 'step_delta') {
          // Pass accumulated content refs to handler (similar to main events)
          // Handler will use accumulated strings instead of appending deltas
          return handleNestedStepDelta(
            data,
            nestedTrackingRef.current,
            newEvents,
            nestedStreamingContentRef.current,
            nestedStreamingReasoningContentRef.current
          )
        }

        if (eventType === 'step_completed') {
          return handleNestedStepCompleted(data, nestedTrackingRef.current, newEvents)
        }

        // Skip other unhandled nested events
        return newEvents
      }

      // Handle different event types based on StepEvent format
      switch (eventType) {
        case 'step_delta': {
          return handleStepDelta(
            data,
            newEvents,
            toolCallTrackerRef.current,
            streamingContentRef.current,
            nestedTrackingRef.current.parentStepIdForBatches,
            streamingReasoningContentRef.current
          )
        }

        case 'step_completed': {
          return handleStepCompleted(
            data,
            newEvents,
            toolCallTrackerRef.current,
            nestedTrackingRef.current.parentStepIdForBatches
          )
        }

        case 'run_started': {
          const result = handleRunStarted(data, newEvents, workflowNodesRef)
          if (result.sessionId && onSessionId) {
            onSessionId(result.sessionId)
          }
          if (data.run_id && onRunId) {
            onRunId(data.run_id)
          }
          if (onWorkflowNodesUpdate) {
            onWorkflowNodesUpdate(new Map(workflowNodesRef.current))
          }
          return result.newEvents
        }

        case 'run_completed': {
          if (onRunId) {
            onRunId(null)
          }
          if (onRunCompleted) {
            onRunCompleted()
          }
          const updatedEvents = handleRunCompleted(data, newEvents, workflowNodesRef)
          if (onWorkflowNodesUpdate) {
            onWorkflowNodesUpdate(new Map(workflowNodesRef.current))
          }
          return updatedEvents
        }

        case 'run_failed': {
          if (onRunId) {
            onRunId(null)
          }
          if (onRunCompleted) {
            onRunCompleted()
          }
          const errorMsg = data.data?.error || data.error || 'Run failed'
          newEvents.push({
            id: `error_${Date.now()}`,
            type: 'error',
            content: errorMsg,
            timestamp: Date.now(),
          })
          return newEvents
        }

        case 'error': {
          newEvents.push({
            id: `error_${Date.now()}`,
            type: 'error',
            content: data.error || data.data?.error || 'An error occurred',
            timestamp: Date.now(),
          })
          return newEvents
        }

        // Workflow stage events (Pipeline)
        case 'stage_started':
        case 'stage_completed':
        case 'stage_skipped': {
          handleWorkflowStageEvent(eventType as 'stage_started' | 'stage_completed' | 'stage_skipped', data, workflowNodesRef)
          if (onWorkflowNodesUpdate) {
            onWorkflowNodesUpdate(new Map(workflowNodesRef.current))
          }
          return newEvents
        }

        // Workflow branch events (Parallel)
        case 'branch_started':
        case 'branch_completed': {
          handleWorkflowBranchEvent(eventType as 'branch_started' | 'branch_completed', data, workflowNodesRef)
          if (onWorkflowNodesUpdate) {
            onWorkflowNodesUpdate(new Map(workflowNodesRef.current))
          }
          return newEvents
        }

        // Loop iteration events
        case 'iteration_started':
        case 'iteration_completed':
          console.log(`Loop event: ${eventType}`, data.iteration)
          return newEvents

        default:
          console.log('Unhandled event:', eventType, data)
          return newEvents
      }
    })
  }

  return {
    processSSEEvent,
    resetTracking,
  }
}
