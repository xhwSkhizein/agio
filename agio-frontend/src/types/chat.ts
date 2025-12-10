/**
 * Chat page types and interfaces
 */

import type { NestedExecution, NestedStep } from '../components/ParallelNestedRunnables'
import type { WorkflowNode } from './workflow'

// Generate unique ID
let idCounter = 0
export const generateId = () => `event_${Date.now()}_${++idCounter}`

export interface TimelineEvent {
  id: string
  type: 'user' | 'assistant' | 'tool' | 'error' | 'nested' | 'workflow' | 'parallel_nested'
  content?: string
  toolName?: string
  toolArgs?: string
  toolResult?: string
  toolStatus?: 'running' | 'completed' | 'failed'
  toolDuration?: number
  timestamp: number
  // For assistant messages - token usage
  metrics?: {
    input_tokens?: number
    output_tokens?: number
    total_tokens?: number
    duration_ms?: number
  }
  // For nested executions (RunnableTool)
  nestedRunnableId?: string
  nestedDepth?: number
  nestedEvents?: TimelineEvent[]  // Collapsed nested events
  nestedExecutions?: NestedExecution[]  // For parallel_nested type
  
  // Workflow hierarchy fields
  workflowType?: 'pipeline' | 'parallel' | 'loop'
  workflowId?: string
  parentRunId?: string
  runId?: string
  stageId?: string
  stageName?: string
  stageIndex?: number
  totalStages?: number
  branchId?: string
  branchIds?: string[]
  status?: 'running' | 'completed' | 'failed' | 'skipped'
}

// Track tool calls by step_id + index (OpenAI streaming uses index, not id)
export interface ToolCallTracker {
  [key: string]: {  // key = `${step_id}_${index}`
    eventId: string  // The event ID in newEvents
    toolCallId?: string  // The actual tool_call_id from OpenAI
  }
}

// Nested execution tracking structures
export interface NestedExecutionMap {
  // Key: parent_run_id, Value: Map of run_id -> NestedExecution
  executions: Map<string, Map<string, NestedExecution>>
  // Track parallel call batches: Key: parentRunId_stepId, Value: batch info
  parallelBatches: Map<string, { batchId: string; executionIds: Set<string>; stepId: string }>
  // Track step_id for each nested execution: Key: nestedRunId, Value: stepId
  nestedRunStepId: Map<string, string>
  // Track the parent step_id that triggered parallel RunnableTool calls: Key: parentRunId, Value: parentStepId
  parentStepIdForBatches: Map<string, string>
  // Track tool_call mapping for nested executions: Key: `${nestedRunId}_${stepId}_${index}`, Value: { toolCallId, stepIndex, finalized }
  nestedToolCallTracker: Map<string, { toolCallId: string; stepIndex: number; finalized?: boolean }>
}
