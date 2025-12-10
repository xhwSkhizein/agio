/**
 * Hook for handling SSE stream processing
 */

import { useRef, type MutableRefObject } from 'react'
import { parseSSEBuffer } from '../utils/sseParser'
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
  onEvent: (events: TimelineEvent[]) => void
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
  const nestedTrackingRef = useRef<NestedExecutionMap>({
    executions: new Map(),
    parallelBatches: new Map(),
    nestedRunStepId: new Map(),
    parentStepIdForBatches: new Map(),
    nestedToolCallTracker: new Map(),
  })

  const resetTracking = () => {
    toolCallTrackerRef.current = {}
    streamingContentRef.current = {}
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

    // Accumulate content OUTSIDE setEvents to avoid double-execution in StrictMode
    if (eventType === 'step_delta' && data.delta?.content) {
      const contentRef = streamingContentRef.current
      if (!contentRef[stepId]) {
        contentRef[stepId] = ''
      }
      contentRef[stepId] += data.delta.content
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
          return handleNestedStepDelta(data, nestedTrackingRef.current, newEvents)
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
            nestedTrackingRef.current.parentStepIdForBatches
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
