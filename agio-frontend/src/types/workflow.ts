/**
 * Workflow hierarchy types for frontend display.
 * 
 * These types support building a hierarchical tree structure from
 * flat SSE events to enable proper workflow visualization.
 */

// Base timeline event (existing structure)
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
  metrics?: {
    input_tokens?: number
    output_tokens?: number
    total_tokens?: number
    duration_ms?: number
  }
  // Nested execution context
  nestedRunnableId?: string
  nestedDepth?: number
  nestedEvents?: TimelineEvent[]
  
  // Workflow hierarchy - new fields
  workflowType?: 'pipeline' | 'parallel' | 'loop'
  workflowId?: string
  parentRunId?: string
  runId?: string
  stageId?: string
  stageName?: string
  stageIndex?: number
  totalStages?: number
  branchId?: string
  branchIds?: string[]  // For parallel workflow
  status?: 'running' | 'completed' | 'failed' | 'skipped'
}

// Workflow stage representation
export interface WorkflowStage {
  id: string
  name: string
  index: number
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  events: TimelineEvent[]  // Events belonging to this stage
  runId?: string  // Run ID of the agent executing this stage
}

// Parallel branch representation
export interface ParallelBranch {
  id: string
  name: string
  index: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  events: TimelineEvent[]
  runId?: string
}

// Workflow node - represents a workflow execution in the timeline
export interface WorkflowNode {
  id: string  // Workflow run_id
  type: 'pipeline' | 'parallel' | 'loop'
  workflowId: string  // Workflow definition ID
  status: 'running' | 'completed' | 'failed'
  parentRunId?: string  // For nested workflows
  depth: number
  
  // For Pipeline
  stages?: WorkflowStage[]
  currentStageIndex?: number
  
  // For Parallel
  branches?: ParallelBranch[]
  activeBranchIndex?: number  // Currently viewed branch in UI
  
  // For Loop
  iterations?: WorkflowStage[][]  // Each iteration is a list of stages
  currentIteration?: number
  
  // Metadata
  totalStages?: number
  completedStages?: number
  startTime?: number
  endTime?: number
}

// Hierarchical timeline structure
export interface HierarchicalTimeline {
  // Top-level events (user messages, direct agent responses)
  rootEvents: TimelineEvent[]
  
  // Workflow nodes indexed by run_id
  workflowNodes: Map<string, WorkflowNode>
  
  // Parent-child relationships: child run_id -> parent run_id
  parentMap: Map<string, string>
}

/**
 * Event types that indicate workflow structure
 */
export const WORKFLOW_EVENT_TYPES = [
  'stage_started',
  'stage_completed', 
  'stage_skipped',
  'branch_started',
  'branch_completed',
  'iteration_started',
] as const

export type WorkflowEventType = typeof WORKFLOW_EVENT_TYPES[number]

/**
 * Check if an event is a workflow structural event
 */
export function isWorkflowEvent(eventType: string): eventType is WorkflowEventType {
  return WORKFLOW_EVENT_TYPES.includes(eventType as WorkflowEventType)
}

/**
 * Check if an event belongs to a workflow execution
 */
export function isWorkflowRelatedEvent(event: any): boolean {
  return !!(event.workflow_type || event.workflow_id || event.parent_run_id)
}
