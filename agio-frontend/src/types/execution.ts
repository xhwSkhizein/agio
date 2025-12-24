/**
 * Unified execution types for building hierarchical execution tree.
 * 
 * These types replace the scattered TimelineEvent, NestedExecution, WorkflowNode types
 * with a unified recursive structure.
 */

import type { Metrics } from '../utils/metricsHelpers'

/**
 * Step types in an execution
 */
export type ExecutionStep = 
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
 * Unified execution node - represents any Runnable execution (Agent or Workflow)
 */
export interface RunnableExecution {
  id: string                          // run_id
  runnableId: string                  // Agent/Workflow config ID
  runnableType: 'agent' | 'workflow'
  
  // Nesting context
  nestingType?: 'tool_call' | 'workflow_node'  // How this execution was triggered
  parentRunId?: string
  depth: number
  
  // Workflow specific
  workflowType?: 'pipeline' | 'parallel' | 'loop'
  nodeId?: string
  branchId?: string
  
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
  
  // Root executions (top-level Agent/Workflow runs)
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
