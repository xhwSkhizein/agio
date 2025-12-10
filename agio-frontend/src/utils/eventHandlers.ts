/**
 * Event handlers for processing SSE events into timeline events
 */

import type { MutableRefObject } from 'react'
import type { TimelineEvent, ToolCallTracker } from '../types/chat'
import type { WorkflowNode } from '../types/workflow'
import { generateId } from '../types/chat'
import {
  handleNestedRunStarted,
  handleNestedRunCompleted,
  handleNestedStepDelta,
  handleNestedStepCompleted,
} from './nestedExecutionHandlers'
import type { NestedExecutionMap } from '../types/chat'

interface SSEEventData {
  step_id?: string
  run_id?: string
  parent_run_id?: string
  nested_runnable_id?: string
  depth?: number
  workflow_type?: string
  workflow_id?: string
  total_stages?: number
  stage_id?: string
  stage_name?: string
  stage_index?: number
  branch_id?: string
  data?: {
    session_id?: string
    workflow_id?: string
    total_stages?: number
    total_branches?: number
    branch_ids?: string[]
    termination_reason?: string
    max_steps?: number
    error?: string
    metrics?: {
      input_tokens?: number
      output_tokens?: number
      total_tokens?: number
      duration_ms?: number
    }
  }
  delta?: {
    content?: string
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
      input_tokens?: number
      output_tokens?: number
      total_tokens?: number
      duration_ms?: number
    }
  }
  error?: string
}

/**
 * Process step_delta event
 */
export function handleStepDelta(
  data: SSEEventData,
  newEvents: TimelineEvent[],
  toolCallTracker: ToolCallTracker,
  streamingContentRef: { [stepId: string]: string },
  parentStepIdForBatches: Map<string, string>
): TimelineEvent[] {
  const stepId = data.step_id || 'unknown'

  // Handle text content
  if (data.delta?.content) {
    const accumulatedContent = streamingContentRef[stepId] || ''

    const existingIdx = newEvents.findIndex(e => e.type === 'assistant' && e.id === stepId)
    if (existingIdx !== -1) {
      // Update existing assistant event with accumulated content
      newEvents[existingIdx] = {
        ...newEvents[existingIdx],
        content: accumulatedContent,
      }
    } else {
      // Create new assistant event
      newEvents.push({
        id: stepId,
        type: 'assistant',
        content: accumulatedContent,
        timestamp: Date.now(),
      })
    }
  }

  // Handle tool calls in delta - use index to track, not id
  // OpenAI streaming: id only appears in first chunk, subsequent chunks only have index
  if (data.delta?.tool_calls) {
    // Track this step_id as the parent step that triggered parallel calls
    // This will be used to group parallel RunnableTool calls into batches
    parentStepIdForBatches.set(data.run_id || '', stepId)
    for (const toolCall of data.delta.tool_calls) {
      const tcIndex = toolCall.index ?? 0
      const trackerKey = `${stepId}_${tcIndex}`
      const tracker = toolCallTracker

      if (tracker[trackerKey]) {
        // Existing tool call - accumulate arguments
        const eventIdx = newEvents.findIndex(e => e.id === tracker[trackerKey].eventId)
        if (eventIdx !== -1) {
          const existing = newEvents[eventIdx]
          const deltaArgs = toolCall.function?.arguments || ''
          const deltaName = toolCall.function?.name || ''
          newEvents[eventIdx] = {
            ...existing,
            toolName: deltaName
              ? (existing.toolName ? existing.toolName + deltaName : deltaName)
              : existing.toolName,
            toolArgs: (existing.toolArgs || '') + deltaArgs,
          }
          // Update tool_call_id if we receive it
          if (toolCall.id) {
            tracker[trackerKey].toolCallId = toolCall.id
            newEvents[eventIdx].id = toolCall.id
          }
        }
      } else {
        // New tool call
        const eventId = toolCall.id || `${stepId}_tool_${tcIndex}`
        tracker[trackerKey] = {
          eventId,
          toolCallId: toolCall.id,
        }
        newEvents.push({
          id: eventId,
          type: 'tool',
          toolName: toolCall.function?.name || '',
          toolArgs: toolCall.function?.arguments || '',
          toolStatus: 'running',
          timestamp: Date.now(),
        })
      }
    }
  }

  return newEvents
}

/**
 * Process step_completed event
 */
export function handleStepCompleted(
  data: SSEEventData,
  newEvents: TimelineEvent[],
  toolCallTracker: ToolCallTracker,
  parentStepIdForBatches: Map<string, string>
): TimelineEvent[] {
  const snapshot = data.snapshot
  const stepId = data.step_id || 'unknown'

  if (!snapshot) {
    return newEvents
  }

  // Handle assistant step completion - update metrics and finalize tool calls
  if (snapshot.role === 'assistant') {
    const assistantIdx = newEvents.findIndex(e => e.id === stepId)
    if (assistantIdx !== -1 && snapshot.metrics) {
      newEvents[assistantIdx] = {
        ...newEvents[assistantIdx],
        metrics: {
          input_tokens: snapshot.metrics.input_tokens,
          output_tokens: snapshot.metrics.output_tokens,
          total_tokens: snapshot.metrics.total_tokens,
          duration_ms: snapshot.metrics.duration_ms,
        }
      }
    }

    // Track this step_id as the parent step that triggered parallel calls
    if (snapshot.tool_calls && Array.isArray(snapshot.tool_calls) && snapshot.tool_calls.length > 0) {
      parentStepIdForBatches.set(data.run_id || '', stepId)
    }

    // Finalize tool calls from snapshot (in case delta was incomplete)
    if (snapshot.tool_calls && Array.isArray(snapshot.tool_calls)) {
      for (const tc of snapshot.tool_calls) {
        if (!tc.id) continue

        // Find existing tool event or create new one
        let toolIdx = newEvents.findIndex(e => e.id === tc.id)

        // Also check tracker
        if (toolIdx === -1) {
          const tracker = toolCallTracker
          for (const key of Object.keys(tracker)) {
            if (tracker[key].toolCallId === tc.id) {
              toolIdx = newEvents.findIndex(e => e.id === tracker[key].eventId)
              break
            }
          }
        }

        if (toolIdx !== -1) {
          // Update existing
          newEvents[toolIdx] = {
            ...newEvents[toolIdx],
            id: tc.id,
            toolName: tc.function?.name || newEvents[toolIdx].toolName,
            toolArgs: tc.function?.arguments || newEvents[toolIdx].toolArgs,
          }
        } else {
          // Create new tool event from snapshot
          newEvents.push({
            id: tc.id,
            type: 'tool',
            toolName: tc.function?.name || 'Unknown Tool',
            toolArgs: tc.function?.arguments || '{}',
            toolStatus: 'running',
            timestamp: Date.now(),
          })
        }
      }
    }
  }

  // Handle tool results
  if (snapshot.role === 'tool' && snapshot.tool_call_id) {
    // Find by tool_call_id in tracker or direct match
    let toolIndex = newEvents.findIndex(e => e.id === snapshot.tool_call_id)

    // Also check tracker for matching tool_call_id
    if (toolIndex === -1) {
      const tracker = toolCallTracker
      for (const key of Object.keys(tracker)) {
        if (tracker[key].toolCallId === snapshot.tool_call_id) {
          toolIndex = newEvents.findIndex(e => e.id === tracker[key].eventId)
          break
        }
      }
    }

    if (toolIndex !== -1) {
      newEvents[toolIndex] = {
        ...newEvents[toolIndex],
        id: snapshot.tool_call_id,  // Update to real ID
        toolResult: snapshot.content,
        toolStatus: snapshot.is_error ? 'failed' : 'completed',
        toolDuration: snapshot.metrics?.duration_ms,
      }
    } else {
      // Tool result without matching tool call - create one
      newEvents.push({
        id: snapshot.tool_call_id,
        type: 'tool',
        toolName: snapshot.name || 'Unknown Tool',
        toolArgs: '{}',
        toolResult: snapshot.content,
        toolStatus: snapshot.is_error ? 'failed' : 'completed',
        toolDuration: snapshot.metrics?.duration_ms,
        timestamp: Date.now(),
      })
    }
  }

  return newEvents
}

/**
 * Process run_started event
 */
export function handleRunStarted(
  data: SSEEventData,
  newEvents: TimelineEvent[],
  workflowNodesRef: MutableRefObject<Map<string, WorkflowNode>>
): { newEvents: TimelineEvent[]; sessionId?: string } {
  console.log('Run started:', data.run_id, 'Session:', data.data?.session_id, 'Workflow:', data.workflow_type)

  const sessionId = data.data?.session_id

  // Handle workflow run_started
  if (data.workflow_type && ['pipeline', 'parallel', 'loop'].includes(data.workflow_type)) {
    const workflowNode: WorkflowNode = {
      id: data.run_id || '',
      type: data.workflow_type as 'pipeline' | 'parallel' | 'loop',
      workflowId: data.workflow_id || data.data?.workflow_id || '',
      status: 'running',
      parentRunId: data.parent_run_id,
      depth: data.depth || 0,
      totalStages: data.total_stages || data.data?.total_stages || data.data?.total_branches,
      completedStages: 0,
      startTime: Date.now(),
      stages: data.workflow_type === 'pipeline' ? [] : undefined,
      branches: data.workflow_type === 'parallel'
        ? (data.data?.branch_ids || []).map((id: string, idx: number) => ({
            id,
            name: id,
            index: idx,
            status: 'pending' as const,
            events: [],
          }))
        : undefined,
    }

    // Update workflow nodes ref (for immediate access in subsequent events)
    workflowNodesRef.current = new Map(workflowNodesRef.current).set(data.run_id || '', workflowNode)

    // Add workflow event to timeline (only for top-level workflows)
    if (!data.parent_run_id || data.depth === 0) {
      newEvents.push({
        id: data.run_id || '',
        type: 'workflow',
        workflowType: data.workflow_type as 'pipeline' | 'parallel' | 'loop',
        workflowId: data.workflow_id || data.data?.workflow_id,
        runId: data.run_id,
        totalStages: workflowNode.totalStages,
        branchIds: data.data?.branch_ids,
        status: 'running',
        timestamp: Date.now(),
      })
    }
  }

  return { newEvents, sessionId }
}

/**
 * Process run_completed event
 */
export function handleRunCompleted(
  data: SSEEventData,
  newEvents: TimelineEvent[],
  workflowNodesRef: MutableRefObject<Map<string, WorkflowNode>>
): TimelineEvent[] {
  console.log('Run completed:', data)

  // Mark any still-running tool calls as completed
  newEvents.forEach((event, idx) => {
    if (event.type === 'tool' && event.toolStatus === 'running') {
      newEvents[idx] = { ...event, toolStatus: 'completed' }
    }
  })

  // Update workflow status if this is a workflow run
  if (data.workflow_type && workflowNodesRef.current.has(data.run_id || '')) {
    const workflow = workflowNodesRef.current.get(data.run_id || '')!
    workflow.status = 'completed'
    workflow.endTime = Date.now()
    workflowNodesRef.current = new Map(workflowNodesRef.current).set(data.run_id || '', workflow)

    // Update workflow event in timeline
    const workflowEventIdx = newEvents.findIndex(e => e.type === 'workflow' && e.runId === data.run_id)
    if (workflowEventIdx !== -1) {
      newEvents[workflowEventIdx] = {
        ...newEvents[workflowEventIdx],
        status: 'completed',
      }
    }
  }

  // Check for termination reason
  if (data.data?.termination_reason) {
    const reason = data.data.termination_reason
    if (reason === 'max_steps') {
      newEvents.push({
        id: generateId(),
        type: 'error',
        content: `Reached maximum steps limit (${data.data.max_steps || 30}). You can continue the conversation.`,
        timestamp: Date.now(),
      })
    } else if (reason === 'timeout') {
      newEvents.push({
        id: generateId(),
        type: 'error',
        content: 'Request timed out. You can continue the conversation.',
        timestamp: Date.now(),
      })
    }
  }

  return newEvents
}

/**
 * Process workflow stage events
 */
export function handleWorkflowStageEvent(
  eventType: 'stage_started' | 'stage_completed' | 'stage_skipped',
  data: SSEEventData,
  workflowNodesRef: MutableRefObject<Map<string, WorkflowNode>>
): void {
  const parentRunId = data.parent_run_id || (data.workflow_type && data.run_id)
  if (!parentRunId || !workflowNodesRef.current.has(parentRunId)) {
    return
  }

  const workflow = workflowNodesRef.current.get(parentRunId)!
  if (workflow.type !== 'pipeline' || !workflow.stages) {
    return
  }

  const stageId = data.stage_id
  if (!stageId) {
    return
  }

  if (eventType === 'stage_started') {
    console.log('Stage started:', stageId, 'in workflow:', parentRunId)
    let stage = workflow.stages.find(s => s.id === stageId)
    if (!stage) {
      stage = {
        id: stageId,
        name: data.stage_name || stageId,
        index: data.stage_index ?? workflow.stages.length,
        status: 'running',
        events: [],
      }
      workflow.stages.push(stage)
    } else {
      stage.status = 'running'
    }
    workflow.currentStageIndex = stage.index
  } else if (eventType === 'stage_completed') {
    console.log('Stage completed:', stageId, 'in workflow:', parentRunId)
    const stage = workflow.stages.find(s => s.id === stageId)
    if (stage) {
      stage.status = 'completed'
      workflow.completedStages = (workflow.completedStages || 0) + 1
    }
  } else if (eventType === 'stage_skipped') {
    console.log('Stage skipped:', stageId)
    let stage = workflow.stages.find(s => s.id === stageId)
    if (!stage) {
      stage = {
        id: stageId,
        name: data.stage_name || stageId,
        index: data.stage_index ?? workflow.stages.length,
        status: 'skipped',
        events: [],
      }
      workflow.stages.push(stage)
    } else {
      stage.status = 'skipped'
    }
  }

  workflowNodesRef.current = new Map(workflowNodesRef.current).set(parentRunId, workflow)
}

/**
 * Process workflow branch events
 */
export function handleWorkflowBranchEvent(
  eventType: 'branch_started' | 'branch_completed',
  data: SSEEventData,
  workflowNodesRef: MutableRefObject<Map<string, WorkflowNode>>
): void {
  const parentRunId = data.parent_run_id || (data.workflow_type && data.run_id)
  if (!parentRunId || !workflowNodesRef.current.has(parentRunId)) {
    return
  }

  const workflow = workflowNodesRef.current.get(parentRunId)!
  if (workflow.type !== 'parallel' || !workflow.branches) {
    return
  }

  const branchId = data.branch_id
  if (!branchId) {
    return
  }

  const branch = workflow.branches.find(b => b.id === branchId)
  if (!branch) {
    return
  }

  if (eventType === 'branch_started') {
    console.log('Branch started:', branchId, 'in workflow:', parentRunId)
    branch.status = 'running'
  } else if (eventType === 'branch_completed') {
    console.log('Branch completed:', branchId, 'in workflow:', parentRunId)
    branch.status = 'completed'
    workflow.completedStages = (workflow.completedStages || 0) + 1
  }

  workflowNodesRef.current = new Map(workflowNodesRef.current).set(parentRunId, workflow)
}
