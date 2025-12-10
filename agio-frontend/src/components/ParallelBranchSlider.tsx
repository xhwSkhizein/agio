/**
 * ParallelBranchSlider - Horizontal slider for parallel workflow branches
 * 
 * Shows all branches stacked, with left/right navigation to switch
 * between branches. Each branch displays its events in real-time.
 */

import { useState } from 'react'
import type { ParallelBranch, TimelineEvent } from '../types/workflow'
import { ChevronLeft, ChevronRight, Check, X, Loader2, Circle } from 'lucide-react'

interface ParallelBranchSliderProps {
  branches: ParallelBranch[]
  activeIndex: number
  renderEvent: (event: TimelineEvent) => React.ReactNode
}

const BranchStatusIcon = ({ status }: { status: string }) => {
  switch (status) {
    case 'completed':
      return <Check className="w-3 h-3 text-green-400" />
    case 'failed':
      return <X className="w-3 h-3 text-red-400" />
    case 'running':
      return <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />
    default:
      return <Circle className="w-2 h-2 text-gray-500" />
  }
}

interface BranchTabProps {
  branch: ParallelBranch
  isActive: boolean
  onClick: () => void
}

function BranchTab({ branch, isActive, onClick }: BranchTabProps) {
  const statusColors = {
    pending: 'border-gray-600',
    running: 'border-blue-500',
    completed: 'border-green-500',
    failed: 'border-red-500',
  }
  
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-2 py-1 rounded-t-lg border-b-2 transition-colors ${
        isActive 
          ? `bg-surface/50 ${statusColors[branch.status]}` 
          : 'bg-transparent border-transparent hover:bg-surface/30'
      }`}
    >
      <BranchStatusIcon status={branch.status} />
      <span className={`text-[11px] font-medium ${isActive ? 'text-white' : 'text-gray-400'}`}>
        {branch.name.replace(/_/g, ' ')}
      </span>
      {branch.events.length > 0 && (
        <span className={`px-1 py-0.5 text-[9px] rounded ${
          isActive ? 'bg-surface text-gray-300' : 'bg-surface/50 text-gray-500'
        }`}>
          {branch.events.length}
        </span>
      )}
    </button>
  )
}

export function ParallelBranchSlider({ branches, activeIndex: initialActive, renderEvent }: ParallelBranchSliderProps) {
  const [activeIndex, setActiveIndex] = useState(initialActive)
  
  const canGoPrev = activeIndex > 0
  const canGoNext = activeIndex < branches.length - 1
  
  const activeBranch = branches[activeIndex]
  
  if (branches.length === 0) {
    return (
      <div className="text-center py-4 text-gray-500 text-xs">
        No branches yet...
      </div>
    )
  }
  
  return (
    <div className="space-y-0">
      {/* Branch tabs header */}
      <div className="flex items-center gap-1 border-b border-border/50">
        {/* Navigation arrows */}
        <button
          onClick={() => setActiveIndex(prev => prev - 1)}
          disabled={!canGoPrev}
          className={`p-1 rounded transition-colors ${
            canGoPrev 
              ? 'text-gray-400 hover:text-white hover:bg-surface/50' 
              : 'text-gray-700 cursor-not-allowed'
          }`}
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        
        {/* Branch tabs - scrollable */}
        <div className="flex-1 flex items-center gap-0.5 overflow-x-auto scrollbar-hide">
          {branches.map((branch, idx) => (
            <BranchTab
              key={branch.id}
              branch={branch}
              isActive={idx === activeIndex}
              onClick={() => setActiveIndex(idx)}
            />
          ))}
        </div>
        
        <button
          onClick={() => setActiveIndex(prev => prev + 1)}
          disabled={!canGoNext}
          className={`p-1 rounded transition-colors ${
            canGoNext 
              ? 'text-gray-400 hover:text-white hover:bg-surface/50' 
              : 'text-gray-700 cursor-not-allowed'
          }`}
        >
          <ChevronRight className="w-4 h-4" />
        </button>
        
        {/* Branch counter */}
        <span className="text-[10px] text-gray-500 font-mono px-1">
          {activeIndex + 1}/{branches.length}
        </span>
      </div>
      
      {/* Active branch content */}
      <div className="pt-2 min-h-[60px]">
        {activeBranch && activeBranch.events.length > 0 ? (
          <div className="space-y-1">
            {activeBranch.events.map(event => (
              <div key={event.id}>
                {renderEvent(event)}
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center py-4">
            {activeBranch?.status === 'running' ? (
              <div className="flex items-center gap-2 text-gray-500 text-xs">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Executing {activeBranch.name}...</span>
              </div>
            ) : activeBranch?.status === 'pending' ? (
              <span className="text-gray-600 text-xs">Waiting to start...</span>
            ) : (
              <span className="text-gray-600 text-xs">No events</span>
            )}
          </div>
        )}
      </div>
      
      {/* Branch status overview */}
      <div className="flex items-center gap-1 pt-2 border-t border-border/30">
        {branches.map((branch, idx) => (
          <button
            key={branch.id}
            onClick={() => setActiveIndex(idx)}
            className={`flex-1 h-1 rounded-full transition-colors ${
              branch.status === 'completed' ? 'bg-green-500/60' :
              branch.status === 'running' ? 'bg-blue-500/60 animate-pulse' :
              branch.status === 'failed' ? 'bg-red-500/60' :
              'bg-gray-700'
            } ${idx === activeIndex ? 'ring-1 ring-white/30' : ''}`}
            title={`${branch.name}: ${branch.status}`}
          />
        ))}
      </div>
    </div>
  )
}
