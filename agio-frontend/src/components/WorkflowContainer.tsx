/**
 * WorkflowContainer - Wrapper for workflow execution display
 * 
 * Renders Pipeline or Parallel workflow with proper visual hierarchy
 */

import { useMemo } from 'react'
import type { WorkflowNode, TimelineEvent } from '../types/workflow'
import { PipelineStages } from './PipelineStages'
import { ParallelBranchSlider } from './ParallelBranchSlider'
import { GitBranch, Layers, RefreshCw } from 'lucide-react'

interface WorkflowContainerProps {
  workflow: WorkflowNode
  renderEvent: (event: TimelineEvent) => React.ReactNode
}

const WorkflowIcon = ({ type }: { type: string }) => {
  switch (type) {
    case 'pipeline':
      return <Layers className="w-3.5 h-3.5" />
    case 'parallel':
      return <GitBranch className="w-3.5 h-3.5" />
    case 'loop':
      return <RefreshCw className="w-3.5 h-3.5" />
    default:
      return null
  }
}

const StatusBadge = ({ status }: { status: string }) => {
  const styles = {
    running: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    completed: 'bg-green-500/20 text-green-400 border-green-500/30',
    failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  }
  
  return (
    <span className={`px-1.5 py-0.5 text-[10px] rounded border ${styles[status as keyof typeof styles] || styles.running}`}>
      {status}
    </span>
  )
}

export function WorkflowContainer({ workflow, renderEvent }: WorkflowContainerProps) {
  const progress = useMemo(() => {
    if (!workflow.totalStages) return 0
    return Math.round((workflow.completedStages || 0) / workflow.totalStages * 100)
  }, [workflow.totalStages, workflow.completedStages])
  
  return (
    <div className="my-2 rounded-lg border border-border/70 bg-surface/30 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-surface/50 border-b border-border/50">
        <div className={`p-1 rounded ${
          workflow.type === 'pipeline' ? 'bg-primary-500/20 text-primary-400' :
          workflow.type === 'parallel' ? 'bg-amber-500/20 text-amber-400' :
          'bg-purple-500/20 text-purple-400'
        }`}>
          <WorkflowIcon type={workflow.type} />
        </div>
        
        <span className="text-xs font-medium text-gray-300">
          {workflow.workflowId.replace(/_/g, ' ')}
        </span>
        
        <span className="text-[10px] text-gray-500 uppercase">
          {workflow.type}
        </span>
        
        <div className="flex-1" />
        
        {workflow.totalStages && (
          <span className="text-[10px] text-gray-500 font-mono">
            {workflow.completedStages || 0}/{workflow.totalStages}
          </span>
        )}
        
        <StatusBadge status={workflow.status} />
      </div>
      
      {/* Progress bar */}
      {workflow.status === 'running' && workflow.totalStages && (
        <div className="h-0.5 bg-surface">
          <div 
            className="h-full bg-primary-500/50 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
      
      {/* Content */}
      <div className="p-2">
        {workflow.type === 'pipeline' && workflow.stages && (
          <PipelineStages 
            stages={workflow.stages}
            currentIndex={workflow.currentStageIndex ?? -1}
            renderEvent={renderEvent}
          />
        )}
        
        {workflow.type === 'parallel' && workflow.branches && (
          <ParallelBranchSlider
            branches={workflow.branches}
            activeIndex={workflow.activeBranchIndex ?? 0}
            renderEvent={renderEvent}
          />
        )}
      </div>
    </div>
  )
}
