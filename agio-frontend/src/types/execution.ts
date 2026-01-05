/**
 * Unified execution types for building hierarchical execution tree.
 * 
 * These types support Agent nesting and composition.
 */

import type { Metrics } from '../utils/metricsHelpers'

/**
 * Backend Step structure from /sessions/{id}/steps API.
 * 
 * Different roles have different fields:
 * - user: { role: 'user', content: string }
 * - assistant: { role: 'assistant', content?: string, tool_calls?: ToolCall[] }
 * - tool: { role: 'tool', name: string, tool_call_id: string, content: string }
 */
export interface BackendStep {
  id: string
  session_id: string
  sequence: number
  role: 'user' | 'assistant' | 'tool'
  content: string | null
  reasoning_content?: string | null
  // Assistant step: list of tool calls to execute
  tool_calls?: Array<{
    id: string
    type: string
    function: {
      name: string
      arguments: string
    }
    index?: number
  }>
  // Tool step: name of the tool that was called
  name?: string
  // Tool step: ID linking to the tool_call in assistant step
  tool_call_id?: string
  created_at: string
  // Hierarchy fields for building execution tree
  run_id?: string | null
  parent_run_id?: string | null
  runnable_id?: string | null
  runnable_type?: string | null
  depth?: number
  // Metrics (for assistant and tool steps)
  metrics?: Metrics
}

/**
 * Step types in an execution
 */
export type ExecutionStep = 
  | { 
    type: 'user'
    stepId: string
    content: string
  }
  | { 
      type: 'assistant_content'
      stepId: string
      content: string
      reasoning_content?: string
      metrics?: Metrics
    }
  | { 
      type: 'tool_call'
      stepId: string
      toolCallId: string
      toolName: string
      toolArgs: string
      childRunId?: string  // run_id of child execution triggered by this tool call
    }
  | { 
      type: 'tool_result'
      stepId: string
      toolCallId: string
      result: string
      status: 'running' | 'completed' | 'failed'
      duration?: number
    }

/**
 * Unified execution node - represents any Runnable execution (Agent)
 */
export interface RunnableExecution {
  id: string                          // run_id
  runnableId: string                  // Agent config ID
  runnableType: 'agent'
  
  // Nesting context
  nestingType?: 'tool_call'  // How this execution was triggered
  parentRunId?: string
  depth: number
  
  // Execution state
  status: 'running' | 'completed' | 'failed'
  
  // Content
  steps: ExecutionStep[]              // Steps in this execution
  children: RunnableExecution[]       // Child executions (recursive)
  
  // Metrics
  metrics?: Metrics
  
  // Timing
  startTime?: number
  endTime?: number
}

/**
 * Top-level message in timeline (user input, errors)
 */
export interface TimelineMessage {
  id: string
  type: 'user' | 'error'
  content: string
  timestamp: number
}

/**
 * Root execution tree state
 */
export interface ExecutionTree {
  // Top-level messages (user inputs)
  messages: TimelineMessage[]
  
  // Root executions (top-level Agent runs)
  executions: RunnableExecution[]
  
  // Quick lookup: run_id -> execution
  executionMap: Map<string, RunnableExecution>
}

/**
 * Create empty execution tree
 */
export function createEmptyTree(): ExecutionTree {
  return {
    messages: [],
    executions: [],
    executionMap: new Map(),
  }
}
