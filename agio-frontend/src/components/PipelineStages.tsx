/**
 * PipelineStages - Display pipeline workflow stages with progress
 * 
 * Shows each stage in sequence with visual indicator of progress
 */

import { useState } from 'react'
import type { WorkflowStage, TimelineEvent } from '../types/workflow'
import { ChevronDown, ChevronRight, Check, X, SkipForward, Loader2 } from 'lucide-react'

interface PipelineStagesProps {
  stages: WorkflowStage[]
  currentIndex: number
  renderEvent: (event: TimelineEvent) => React.ReactNode
}

const StageStatusIcon = ({ status }: { status: string }) => {
  switch (status) {
    case 'completed':
      return <Check className="w-3 h-3 text-green-400" />
    case 'failed':
      return <X className="w-3 h-3 text-red-400" />
    case 'skipped':
      return <SkipForward className="w-3 h-3 text-gray-500" />
    case 'running':
      return <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />
    default:
      return <div className="w-3 h-3 rounded-full border border-gray-600" />
  }
}

interface StageItemProps {
  stage: WorkflowStage
  index: number
  isLast: boolean
  isCurrent: boolean
  renderEvent: (event: TimelineEvent) => React.ReactNode
}

function StageItem({ stage, index, isLast, isCurrent, renderEvent }: StageItemProps) {
  const [isExpanded, setIsExpanded] = useState(isCurrent || stage.status === 'running')
  
  const statusColors = {
    pending: 'border-gray-600 bg-gray-600/10',
    running: 'border-blue-500 bg-blue-500/10',
    completed: 'border-green-500 bg-green-500/10',
    failed: 'border-red-500 bg-red-500/10',
    skipped: 'border-gray-500 bg-gray-500/10',
  }
  
  return (
    <div className="relative">
      {/* Connection line to next stage */}
      {!isLast && (
        <div className={`absolute left-[11px] top-[24px] w-0.5 h-[calc(100%-12px)] ${
          stage.status === 'completed' ? 'bg-green-500/50' : 'bg-gray-700'
        }`} />
      )}
      
      {/* Stage header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors ${
          isExpanded ? 'bg-surface/50' : 'hover:bg-surface/30'
        }`}
      >
        {/* Status indicator */}
        <div className={`w-6 h-6 flex items-center justify-center rounded-full border ${statusColors[stage.status]}`}>
          <StageStatusIcon status={stage.status} />
        </div>
        
        {/* Stage info */}
        <div className="flex-1 text-left">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-gray-300">
              {stage.name.replace(/_/g, ' ')}
            </span>
            <span className="text-[10px] text-gray-500">
              Stage {index + 1}
            </span>
          </div>
        </div>
        
        {/* Event count badge */}
        {stage.events.length > 0 && (
          <span className="px-1.5 py-0.5 text-[10px] bg-surface rounded text-gray-400">
            {stage.events.length}
          </span>
        )}
        
        {/* Expand/collapse icon */}
        {stage.events.length > 0 && (
          isExpanded 
            ? <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
            : <ChevronRight className="w-3.5 h-3.5 text-gray-500" />
        )}
      </button>
      
      {/* Stage content */}
      {isExpanded && stage.events.length > 0 && (
        <div className="ml-8 mt-1 mb-2 pl-3 border-l border-border/50">
          {stage.events.map(event => (
            <div key={event.id} className="py-0.5">
              {renderEvent(event)}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function PipelineStages({ stages, currentIndex, renderEvent }: PipelineStagesProps) {
  if (stages.length === 0) {
    return (
      <div className="text-center py-4 text-gray-500 text-xs">
        No stages yet...
      </div>
    )
  }
  
  return (
    <div className="space-y-1">
      {stages.map((stage, index) => (
        <StageItem
          key={stage.id}
          stage={stage}
          index={index}
          isLast={index === stages.length - 1}
          isCurrent={index === currentIndex}
          renderEvent={renderEvent}
        />
      ))}
    </div>
  )
}
