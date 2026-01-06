/**
 * RunnableExecutionView - Unified component for displaying any Runnable execution
 * 
 * This component recursively renders Agent executions with their
 * steps and children, supporting arbitrary nesting depth.
 */

import { useState, useMemo } from 'react'
import type { RunnableExecution, ExecutionStep } from '../types/execution'
import { MessageContent } from './MessageContent'
import { ToolCall } from './ToolCall'
import { 
  Bot, 
  Cog,
  ChevronLeft,
  ChevronRight,
  Check,
  X,
  Loader2,
  Circle,
  ChevronDown,
  ChevronRight as ChevronRightIcon,
  Clock
} from 'lucide-react'

interface RunnableExecutionViewProps {
  execution: RunnableExecution
  isRoot?: boolean
  depth?: number
}

// ============================================================================
// ExecutionHeader - Shows Runnable name, type, and status
// ============================================================================

interface ExecutionHeaderProps {
  execution: RunnableExecution
  isExpanded: boolean
  onToggle: () => void
}

function ExecutionHeader({ execution, isExpanded, onToggle }: ExecutionHeaderProps) {
  const getIcon = () => {
    // Agent triggered by tool_call
    if (execution.nestingType === 'tool_call') {
      return <Cog className="w-3 h-3" />
    }
    return <Bot className="w-3 h-3" />
  }

  const getColorClass = () => {
    if (execution.nestingType === 'tool_call') {
      return 'bg-amber-500/5 text-amber-400/80 border-white/5'
    }
    return 'bg-white/5 text-blue-400/80 border-white/5'
  }

  const statusBadge = {
    running: 'bg-blue-500/10 text-blue-400/80 border-blue-500/20',
    completed: 'bg-emerald-500/10 text-emerald-400/80 border-emerald-500/20',
    failed: 'bg-red-500/10 text-red-400/80 border-red-500/20',
  }

  const displayName = execution.runnableId.replace(/_/g, ' ') || 'Unknown'
  const typeLabel = execution.nestingType === 'tool_call' ? 'RUNNABLE' : 'AGENT'

  return (
    <button
      onClick={onToggle}
      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-t-xl border-b transition-all ${getColorClass()} hover:bg-white/10`}
    >
      <div className="p-1 rounded-lg bg-black/20 border border-white/5 shadow-inner">
        {getIcon()}
      </div>
      
      <div className="flex flex-col items-start">
        <span className="text-[8px] font-black opacity-40 uppercase tracking-[0.2em] leading-none mb-0.5">
          {typeLabel}
        </span>
        <span className="text-[13px] font-bold tracking-tight leading-none text-gray-200">
          {displayName}
        </span>
      </div>
      
      <div className="flex-1" />
      
      <div className="flex items-center gap-2.5 mr-1.5">
        {execution.steps.length > 0 && (
          <span className="text-[8px] font-black text-gray-700 uppercase tracking-widest">
            {execution.steps.length} STAGES
          </span>
        )}
        
        {execution.children.length > 0 && (
          <span className="text-[8px] font-black text-gray-700 uppercase tracking-widest">
            {execution.children.length} SUB-UNITS
          </span>
        )}
      </div>
      
      <span className={`px-1.5 py-0.5 text-[8px] font-black rounded-lg border uppercase tracking-widest ${statusBadge[execution.status]}`}>
        {execution.status}
      </span>
      
      <div className={`p-1 rounded transition-colors ${isExpanded ? 'bg-white/10 text-white' : 'text-gray-700 hover:text-gray-500'}`}>
        {isExpanded ? (
          <ChevronDown className="w-3 h-3" />
        ) : (
          <ChevronRightIcon className="w-3 h-3" />
        )}
      </div>
    </button>
  )
}

// ============================================================================
// ExecutionSteps - Renders the steps in an execution
// ============================================================================

interface ExecutionStepsProps {
  execution: RunnableExecution
}

function ExecutionSteps({ execution }: ExecutionStepsProps) {
  const steps = execution.steps
  // Use a Map to track active index for each parallel tool call group
  const [activeParallelIndices, setActiveParallelIndices] = useState<Map<number, number>>(new Map())

  const getActiveIndex = (groupIdx: number): number => {
    return activeParallelIndices.get(groupIdx) ?? 0
  }

  const setActiveIndex = (groupIdx: number, index: number): void => {
    setActiveParallelIndices(prev => {
      const newMap = new Map(prev)
      newMap.set(groupIdx, index)
      return newMap
    })
  }

  if (steps.length === 0 && execution.status === 'running') {
    return (
      <div className="flex items-center gap-2 text-gray-500 text-xs py-2">
        <Loader2 className="w-3 h-3 animate-spin" />
        <span>Executing...</span>
      </div>
    )
  }

  // Group tool_calls with their results
  const getToolResult = (toolCallId: string) => {
    return steps.find(
      s => s.type === 'tool_result' && s.toolCallId === toolCallId
    ) as Extract<ExecutionStep, { type: 'tool_result' }> | undefined
  }

  // Find child execution for a tool_call (RunnableTool)
  // Only use precise childRunId matching to avoid showing wrong child execution
  const getChildForToolCall = (step: Extract<ExecutionStep, { type: 'tool_call' }>) => {
    if (step.childRunId) {
      return execution.children.find(child => child.id === step.childRunId)
    }
    return undefined
  }

  // Group consecutive tool_calls together (they are concurrent)
  const groupedSteps: Array<ExecutionStep | ExecutionStep[]> = []
  let currentToolCallGroup: Extract<ExecutionStep, { type: 'tool_call' }>[] = []
  
  for (const step of steps) {
    if (step.type === 'tool_call') {
      currentToolCallGroup.push(step)
    } else {
      // Flush current tool_call group if exists
      if (currentToolCallGroup.length > 0) {
        groupedSteps.push(currentToolCallGroup.length === 1 ? currentToolCallGroup[0] : currentToolCallGroup)
        currentToolCallGroup = []
      }
      groupedSteps.push(step)
    }
  }
  // Flush remaining tool_call group
  if (currentToolCallGroup.length > 0) {
    groupedSteps.push(currentToolCallGroup.length === 1 ? currentToolCallGroup[0] : currentToolCallGroup)
  }

  return (
    <div className="space-y-2">
      {groupedSteps.map((stepOrGroup, idx) => {
        // Handle grouped tool_calls (concurrent execution)
        if (Array.isArray(stepOrGroup)) {
          const toolCallSteps = stepOrGroup as Extract<ExecutionStep, { type: 'tool_call' }>[]
          const activeIndex = getActiveIndex(idx)
          const activeToolCall = toolCallSteps[activeIndex] || toolCallSteps[0]
          const toolResult = getToolResult(activeToolCall.toolCallId)
          const childExec = getChildForToolCall(activeToolCall)
          const canGoPrev = activeIndex > 0
          const canGoNext = activeIndex < toolCallSteps.length - 1

          return (
            <div key={`parallel_tools_${idx}`} className="rounded-xl border border-white/5 bg-black/40 overflow-hidden shadow-xl my-3">
              {/* Parallel tool calls header */}
              <div className="flex items-center gap-1.5 px-2.5 pt-1.5 border-b border-white/5 bg-white/5">
                <button
                  onClick={() => setActiveIndex(idx, Math.max(0, activeIndex - 1))}
                  disabled={!canGoPrev}
                  className={`p-1 rounded-lg transition-all ${
                    canGoPrev
                      ? 'text-gray-500 hover:text-white hover:bg-white/10'
                      : 'text-gray-800 cursor-not-allowed'
                  }`}
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>

                <div className="flex-1 flex items-center gap-1 overflow-x-auto custom-scrollbar-hide">
                  {toolCallSteps.map((tc, tcIdx) => {
                    const tcResult = getToolResult(tc.toolCallId)
                    const isActive = tcIdx === activeIndex
                    const statusColors = {
                      running: 'border-blue-500',
                      completed: 'border-emerald-500',
                      failed: 'border-red-500',
                    }
                    const status = tcResult?.status || 'running'

                    return (
                      <button
                        key={tc.toolCallId}
                        onClick={() => setActiveIndex(idx, tcIdx)}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-t-lg border-b-2 transition-all group/tab ${
                          isActive
                            ? `bg-white/5 ${statusColors[status]}`
                            : 'bg-transparent border-transparent hover:bg-white/[0.03]'
                        }`}
                      >
                        <ChildStatusIcon status={status} />
                        <span className={`text-[10px] font-black uppercase tracking-tight transition-colors ${
                          isActive ? 'text-primary-400/80' : 'text-gray-700 group-hover/tab:text-gray-500'
                        }`}>
                          {tc.toolName}
                        </span>
                      </button>
                    )
                  })}
                </div>

                <button
                  onClick={() => setActiveIndex(idx, Math.min(toolCallSteps.length - 1, activeIndex + 1))}
                  disabled={!canGoNext}
                  className={`p-1 rounded-lg transition-all ${
                    canGoNext
                      ? 'text-gray-500 hover:text-white hover:bg-white/10'
                      : 'text-gray-800 cursor-not-allowed'
                  }`}
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>

                <div className="px-2 py-0.5 rounded bg-black/40 border border-white/5 text-[9px] text-gray-700 font-bold font-mono">
                  {activeIndex + 1}/{toolCallSteps.length}
                </div>
              </div>

              {/* Active tool call content */}
              <div className="p-3 bg-black/20">
                <ToolCall
                  toolName={activeToolCall.toolName}
                  args={activeToolCall.toolArgs}
                  result={toolResult?.result}
                  status={toolResult?.status || 'running'}
                  duration={toolResult?.duration}
                />
                {childExec && (
                  <div className="ml-4 mt-3 border-l-2 border-white/5 pl-4">
                    <div className="flex items-center gap-1.5 text-[9px] font-black text-gray-800 uppercase tracking-[0.3em] mb-3">
                      <Bot className="w-2.5 h-2.5" />
                      SUB-ORCHESTRATION LAYER
                    </div>
                    <RunnableExecutionView 
                      execution={childExec} 
                      depth={(execution.depth || 0) + 1}
                    />
                  </div>
                )}
              </div>

              {/* Status overview bar */}
              <div className="flex items-center gap-1 px-3 py-1.5 border-t border-white/5 bg-black/40">
                {toolCallSteps.map((tc, tcIdx) => {
                  const tcResult = getToolResult(tc.toolCallId)
                  const status = tcResult?.status || 'running'
                  return (
                    <button
                      key={tc.toolCallId}
                      onClick={() => setActiveIndex(idx, tcIdx)}
                      className={`flex-1 h-1 rounded-full transition-all duration-300 ${
                        status === 'completed' ? 'bg-emerald-500/30 hover:bg-emerald-500/50' :
                        status === 'running' ? 'bg-blue-500/30 animate-pulse' :
                        status === 'failed' ? 'bg-red-500/30 hover:bg-red-500/50' :
                        'bg-gray-800'
                        } ${tcIdx === activeIndex ? 'ring-1 ring-white/5 scale-y-125' : ''}`}
                      title={`${tc.toolName}: ${status}`}
                    />
                  )
                })}
              </div>
            </div>
          )
        }

        // Single step (not grouped)
        const step = stepOrGroup as ExecutionStep
        if (step.type === 'user') {
          return (
            <div key={`${step.stepId}_user_${idx}`} className="mb-2">
              <div className="text-xs text-white font-medium leading-relaxed">
                <MessageContent content={step.content} />
              </div>
            </div>
          )
        }
        
        if (step.type === 'assistant_content') {
          return (
            <div key={`${step.stepId}_content_${idx}`} className="space-y-3 my-1.5">
              {/* Reasoning content (thinking mode) */}
              {step.reasoning_content && (
                <div className="rounded-xl border border-blue-500/10 bg-blue-500/5 overflow-hidden">
                  <details className="group">
                    <summary className="cursor-pointer px-3 py-1.5 text-[9px] text-blue-400/70 font-black uppercase tracking-widest flex items-center gap-2 hover:bg-blue-500/10 transition-colors list-none">
                      <div className="w-3.5 h-3.5 rounded bg-blue-500/10 flex items-center justify-center transition-transform group-open:rotate-90">
                        <ChevronRightIcon className="w-2.5 h-2.5" />
                      </div>
                      <span>Neural Processing Core</span>
                      <div className="flex-1 h-px bg-blue-500/5" />
                    </summary>
                    <div className="px-4 pb-3 pt-1.5 text-[11px] text-blue-300/50 leading-relaxed font-bold italic border-t border-blue-500/5 uppercase tracking-tighter">
                      <MessageContent content={step.reasoning_content} />
                    </div>
                  </details>
                </div>
              )}
              {/* Main content */}
              {step.content && (
                <div className="text-[13px] text-gray-400 leading-relaxed font-medium px-0.5">
                  <MessageContent content={step.content} />
                </div>
              )}
              {/* Metrics */}
              {step.metrics && (
                <div className="flex flex-wrap items-center gap-3 px-2 py-1 rounded-lg bg-white/[0.02] border border-white/5 w-fit">
                  {step.metrics.input_tokens !== undefined && (
                    <div className="flex items-center gap-1">
                      <span className="text-[8px] font-black text-gray-800 uppercase tracking-tighter">In:</span>
                      <span className="text-[9px] font-mono font-bold text-gray-700">{step.metrics.input_tokens}</span>
                      {(step.metrics.cache_read_tokens || step.metrics.cache_creation_tokens) && (
                        <span className="text-blue-500/60 text-[7px] font-mono font-bold">
                          ({step.metrics.cache_read_tokens ? `hit:${step.metrics.cache_read_tokens}` : ''}
                          {step.metrics.cache_read_tokens && step.metrics.cache_creation_tokens ? ' ' : ''}
                          {step.metrics.cache_creation_tokens ? `write:${step.metrics.cache_creation_tokens}` : ''})
                        </span>
                      )}
                    </div>
                  )}
                  {step.metrics.output_tokens !== undefined && (
                    <div className="flex items-center gap-1">
                      <span className="text-[8px] font-black text-gray-800 uppercase tracking-tighter">Out:</span>
                      <span className="text-[9px] font-mono font-bold text-gray-700">{step.metrics.output_tokens}</span>
                    </div>
                  )}
                  {step.metrics.duration_ms && (
                    <div className="flex items-center gap-1 border-l border-white/5 pl-3">
                      <Clock className="w-2.5 h-2.5 text-gray-800" />
                      <span className="text-[9px] font-mono font-bold text-gray-700">{(step.metrics.duration_ms / 1000).toFixed(2)}s</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        }
        
        if (step.type === 'tool_call') {
          // Single tool_call (not concurrent)
          const toolResult = getToolResult(step.toolCallId)
          const childExec = getChildForToolCall(step)
          
          return (
            <div key={`${step.toolCallId}_call_${idx}`}>
              <ToolCall
                toolName={step.toolName}
                args={step.toolArgs}
                result={toolResult?.result}
                status={toolResult?.status || 'running'}
                duration={toolResult?.duration}
              />
              {/* If this tool_call triggered a child execution, show it inline */}
              {childExec && (
                <div className="ml-4 mt-2">
                  <RunnableExecutionView 
                    execution={childExec} 
                    depth={(execution.depth || 0) + 1}
                  />
                </div>
              )}
            </div>
          )
        }
        
        // tool_result is rendered with tool_call, skip standalone
        return null
      })}
    </div>
  )
}

// ============================================================================
// ExecutionChildren - Renders child executions (concurrent or sequential)
// ============================================================================

interface ExecutionChildrenProps {
  children: RunnableExecution[]
  parentDepth: number
}

const ChildStatusIcon = ({ status }: { status: string }) => {
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

interface ChildTabProps {
  child: RunnableExecution
  isActive: boolean
  onClick: () => void
}

function ChildTab({ child, isActive, onClick }: ChildTabProps) {
  const statusColors = {
    running: 'border-blue-500',
    completed: 'border-green-500',
    failed: 'border-red-500',
  }

  const displayName = child.runnableId.replace(/_/g, ' ')

  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-2 py-1 rounded-t-lg border-b-2 transition-colors ${
        isActive
          ? `bg-surface/50 ${statusColors[child.status]}`
          : 'bg-transparent border-transparent hover:bg-surface/30'
      }`}
    >
      <ChildStatusIcon status={child.status} />
      <span className={`text-[11px] font-medium ${isActive ? 'text-white' : 'text-gray-400'}`}>
        {displayName}
      </span>
      {child.steps.length > 0 && (
        <span className={`px-1 py-0.5 text-[9px] rounded ${
          isActive ? 'bg-surface text-gray-300' : 'bg-surface/50 text-gray-500'
        }`}>
          {child.steps.length}
        </span>
      )}
    </button>
  )
}

function ExecutionChildren({ children, parentDepth }: ExecutionChildrenProps) {
  const [activeIndex, setActiveIndex] = useState(0)

  if (children.length === 0) {
    return null
  }

  // Filter out children that are already rendered inline with tool_calls
  const standaloneChildren = children.filter(
    child => child.nestingType !== 'tool_call'
  )

  if (standaloneChildren.length === 0) {
    return null
  }

  // Determine if children should be displayed in parallel (tabs) or sequential (vertical)
  // Multiple children running concurrently (e.g., concurrent tool calls)
  const runningCount = standaloneChildren.filter(c => c.status === 'running').length
  const isParallelExecution = runningCount > 1

  // Single child - render directly
  if (standaloneChildren.length === 1) {
    return (
      <div className="mt-4">
        <RunnableExecutionView 
          execution={standaloneChildren[0]} 
          depth={parentDepth + 1}
        />
      </div>
    )
  }

  // Sequential execution (Pipeline, Loop, etc.) - render children vertically
  if (!isParallelExecution) {
    return (
      <div className="mt-4 space-y-4">
        {standaloneChildren.map((child) => (
          <RunnableExecutionView 
            key={child.id}
            execution={child} 
            depth={parentDepth + 1}
          />
        ))}
      </div>
    )
  }

  // Parallel execution - tabbed interface
  const canGoPrev = activeIndex > 0
  const canGoNext = activeIndex < standaloneChildren.length - 1
  const activeChild = standaloneChildren[activeIndex]

  return (
    <div className="mt-6 rounded-2xl border border-white/10 overflow-hidden shadow-2xl bg-black/20">
      {/* Tabs header */}
      <div className="flex items-center gap-2 px-3 pt-2 border-b border-white/5 bg-white/5">
        <button
          onClick={() => setActiveIndex(prev => prev - 1)}
          disabled={!canGoPrev}
          className={`p-1.5 rounded-xl transition-all ${
            canGoPrev
              ? 'text-gray-400 hover:text-white hover:bg-white/10'
              : 'text-gray-800 cursor-not-allowed'
          }`}
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        <div className="flex-1 flex items-center gap-1 overflow-x-auto custom-scrollbar-hide">
          {standaloneChildren.map((child, idx) => (
            <ChildTab
              key={child.id}
              child={child}
              isActive={idx === activeIndex}
              onClick={() => setActiveIndex(idx)}
            />
          ))}
        </div>

        <button
          onClick={() => setActiveIndex(prev => prev + 1)}
          disabled={!canGoNext}
          className={`p-1.5 rounded-xl transition-all ${
            canGoNext
              ? 'text-gray-400 hover:text-white hover:bg-white/10'
              : 'text-gray-800 cursor-not-allowed'
          }`}
        >
          <ChevronRight className="w-4 h-4" />
        </button>

        <div className="px-3 py-1 rounded-lg bg-black/40 border border-white/5 text-[10px] text-gray-600 font-black font-mono">
          {activeIndex + 1}/{standaloneChildren.length}
        </div>
      </div>

      {/* Active child content */}
      <div className="p-4">
        {activeChild && (
          <RunnableExecutionView 
            execution={activeChild} 
            depth={parentDepth + 1}
          />
        )}
      </div>

      {/* Status overview bar */}
      <div className="flex items-center gap-1.5 px-4 py-2 border-t border-white/5 bg-black/40">
        {standaloneChildren.map((child, idx) => (
          <button
            key={child.id}
            onClick={() => setActiveIndex(idx)}
            className={`flex-1 h-1.5 rounded-full transition-all duration-300 ${
              child.status === 'completed' ? 'bg-emerald-500/40 hover:bg-emerald-500/60' :
              child.status === 'running' ? 'bg-blue-500/40 animate-pulse' :
              child.status === 'failed' ? 'bg-red-500/40 hover:bg-red-500/60' :
              'bg-gray-800'
            } ${idx === activeIndex ? 'ring-2 ring-white/10 scale-y-125' : ''}`}
            title={`${child.runnableId}: ${child.status}`}
          />
        ))}
      </div>
    </div>
  )
}

// ============================================================================
// RunnableExecutionView - Main component
// ============================================================================

export function RunnableExecutionView({ 
  execution, 
  isRoot = false,
  depth = 0,
}: RunnableExecutionViewProps) {
  const [isExpanded, setIsExpanded] = useState(true)

  // Determine border color based on type
  const borderColor = useMemo(() => {
    if (execution.nestingType === 'tool_call') {
      return 'border-white/10 shadow-lg'
    }
    return 'border-primary-500/20 shadow-xl shadow-primary-500/5'
  }, [execution.nestingType])

  // For root-level agents without nested structure, render steps directly without container
  if (isRoot && execution.runnableType === 'agent' && execution.children.length === 0) {
    return (
      <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
        <ExecutionSteps execution={execution} />
      </div>
    )
  }

  return (
    <div className={`rounded-2xl border ${borderColor} bg-white/5 overflow-hidden transition-all duration-300 group/exec animate-in fade-in slide-in-from-bottom-2 duration-500`}>
      <ExecutionHeader 
        execution={execution} 
        isExpanded={isExpanded}
        onToggle={() => setIsExpanded(!isExpanded)}
      />
      
      {isExpanded && (
        <div className="p-3 space-y-3 bg-black/10 backdrop-blur-sm">
          <ExecutionSteps execution={execution} />
          <ExecutionChildren 
            children={execution.children} 
            parentDepth={depth}
          />
        </div>
      )}
    </div>
  )
}
