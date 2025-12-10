/**
 * Workflow Tree Builder
 * 
 * Transforms flat SSE events into hierarchical workflow structure
 * for proper visualization of Pipeline and Parallel workflows.
 */

import type { 
  TimelineEvent, 
  WorkflowNode, 
  HierarchicalTimeline 
} from '../types/workflow'

/**
 * Build hierarchical timeline from flat events
 */
export function buildHierarchicalTimeline(events: TimelineEvent[]): HierarchicalTimeline {
  const rootEvents: TimelineEvent[] = []
  const workflowNodes = new Map<string, WorkflowNode>()
  const parentMap = new Map<string, string>()
  
  // First pass: identify workflow nodes from run_started events
  for (const event of events) {
    if (event.type === 'workflow' && event.workflowType) {
      // Create workflow node
      const node: WorkflowNode = {
        id: event.runId!,
        type: event.workflowType,
        workflowId: event.workflowId!,
        status: 'running',
        parentRunId: event.parentRunId,
        depth: event.nestedDepth || 0,
        totalStages: event.totalStages,
        completedStages: 0,
        startTime: event.timestamp,
      }
      
      if (event.workflowType === 'pipeline') {
        node.stages = []
        node.currentStageIndex = -1
      } else if (event.workflowType === 'parallel') {
        node.branches = []
        node.activeBranchIndex = 0
        // Initialize branches from branchIds
        if (event.branchIds) {
          node.branches = event.branchIds.map((id, idx) => ({
            id,
            name: id,
            index: idx,
            status: 'pending' as const,
            events: [],
          }))
        }
      }
      
      workflowNodes.set(event.runId!, node)
      
      if (event.parentRunId) {
        parentMap.set(event.runId!, event.parentRunId)
      }
    }
  }
  
  // Second pass: assign events to workflow stages/branches
  for (const event of events) {
    const parentRunId = event.parentRunId
    
    // Skip workflow container events themselves
    if (event.type === 'workflow') {
      // Add to root if no parent
      if (!parentRunId) {
        rootEvents.push(event)
      }
      continue
    }
    
    // Check if event belongs to a workflow
    if (parentRunId && workflowNodes.has(parentRunId)) {
      const workflow = workflowNodes.get(parentRunId)!
      
      if (workflow.type === 'pipeline' && event.stageId) {
        // Find or create stage
        let stage = workflow.stages?.find(s => s.id === event.stageId)
        if (!stage) {
          stage = {
            id: event.stageId,
            name: event.stageName || event.stageId,
            index: event.stageIndex ?? (workflow.stages?.length || 0),
            status: 'running',
            events: [],
            runId: event.runId,
          }
          workflow.stages?.push(stage)
        }
        stage.events.push(event)
        
        // Update stage status
        if (event.status === 'completed') {
          stage.status = 'completed'
          workflow.completedStages = (workflow.completedStages || 0) + 1
        } else if (event.status === 'failed') {
          stage.status = 'failed'
        } else if (event.status === 'skipped') {
          stage.status = 'skipped'
        }
        
        workflow.currentStageIndex = Math.max(
          workflow.currentStageIndex ?? -1, 
          stage.index
        )
      } else if (workflow.type === 'parallel' && event.branchId) {
        // Find branch
        const branch = workflow.branches?.find(b => b.id === event.branchId)
        if (branch) {
          branch.events.push(event)
          
          // Update branch status
          if (event.status === 'completed') {
            branch.status = 'completed'
            workflow.completedStages = (workflow.completedStages || 0) + 1
          } else if (event.status === 'failed') {
            branch.status = 'failed'
          } else if (event.status === 'running') {
            branch.status = 'running'
          }
        }
      }
    } else if (!parentRunId) {
      // Root-level event
      rootEvents.push(event)
    }
  }
  
  // Update workflow statuses
  for (const [, workflow] of workflowNodes) {
    const total = workflow.totalStages || 0
    const completed = workflow.completedStages || 0
    
    if (workflow.status !== 'failed') {
      if (completed >= total && total > 0) {
        workflow.status = 'completed'
      }
    }
  }
  
  return { rootEvents, workflowNodes, parentMap }
}

/**
 * Get workflow node for a run_id, including nested workflows
 */
export function getWorkflowNode(
  timeline: HierarchicalTimeline, 
  workflowRunId: string
): WorkflowNode | undefined {
  return timeline.workflowNodes.get(workflowRunId)
}

/**
 * Get all child workflow nodes of a parent
 */
export function getChildWorkflows(
  timeline: HierarchicalTimeline,
  parentRunId: string
): WorkflowNode[] {
  const children: WorkflowNode[] = []
  for (const [, node] of timeline.workflowNodes) {
    if (node.parentRunId === parentRunId) {
      children.push(node)
    }
  }
  return children
}

/**
 * Check if an SSE event indicates workflow start
 */
export function isWorkflowStartEvent(data: any): boolean {
  return data.workflow_type && 
         data.type === 'run_started' && 
         ['pipeline', 'parallel', 'loop'].includes(data.workflow_type)
}

/**
 * Transform raw SSE event data to TimelineEvent with workflow fields
 */
export function transformToTimelineEvent(
  eventType: string, 
  data: any
): Partial<TimelineEvent> {
  const base: Partial<TimelineEvent> = {
    timestamp: Date.now(),
    workflowType: data.workflow_type,
    workflowId: data.workflow_id,
    parentRunId: data.parent_run_id,
    runId: data.run_id,
    stageId: data.stage_id,
    stageName: data.stage_name,
    stageIndex: data.stage_index,
    totalStages: data.total_stages,
    branchId: data.branch_id,
    branchIds: data.data?.branch_ids,
    nestedDepth: data.depth || 0,
  }
  
  // Set status based on event type
  if (eventType === 'stage_started' || eventType === 'branch_started') {
    base.status = 'running'
  } else if (eventType === 'stage_completed' || eventType === 'branch_completed') {
    base.status = 'completed'
  } else if (eventType === 'stage_skipped') {
    base.status = 'skipped'
  } else if (eventType === 'run_failed') {
    base.status = 'failed'
  }
  
  return base
}
