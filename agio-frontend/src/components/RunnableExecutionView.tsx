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
      return <Cog className="w-3.5 h-3.5" />
    }
    return <Bot className="w-3.5 h-3.5" />
  }

  const getColorClass = () => {
    if (execution.nestingType === 'tool_call') {
      return 'bg-amber-500/10 text-amber-400 border-amber-500/30'
    }
    return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
  }

  const statusBadge = {
    running: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    completed: 'bg-green-500/20 text-green-400 border-green-500/30',
    failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  }

  const displayName = execution.runnableId.replace(/_/g, ' ') || 'Unknown'
  const typeLabel = execution.nestingType === 'tool_call' ? 'RUNNABLE' : 'AGENT'

  return (
    <button
      onClick={onToggle}
      className={`w-full flex items-center gap-2 px-3 py-2 rounded-t-lg border-b transition-colors ${getColorClass()} hover:opacity-90`}
    >
      <div className="p-1 rounded">
        {getIcon()}
      </div>
      
      <span className="text-xs font-medium">
        {displayName}
      </span>
      
      <span className="text-[10px] opacity-70 uppercase">
        {typeLabel}
      </span>
      
      <div className="flex-1" />
      
      {/* Step count */}
      {execution.steps.length > 0 && (
        <span className="text-[10px] opacity-70 font-mono">
          {execution.steps.length} steps
        </span>
      )}
      
      {/* Children count */}
      {execution.children.length > 0 && (
        <span className="text-[10px] opacity-70 font-mono">
          {execution.children.length} children
        </span>
      )}
      
      <span className={`px-1.5 py-0.5 text-[10px] rounded border ${statusBadge[execution.status]}`}>
        {execution.status}
      </span>
      
      {isExpanded ? (
        <ChevronDown className="w-3.5 h-3.5 opacity-60" />
      ) : (
        <ChevronRightIcon className="w-3.5 h-3.5 opacity-60" />
      )}
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
            <div key={`parallel_tools_${idx}`} className="rounded-lg border border-amber-500/30 bg-amber-500/5 overflow-hidden">
              {/* Parallel tool calls header */}
              <div className="flex items-center gap-1 px-2 pt-1 border-b border-border/50 bg-surface/20">
                <button
                  onClick={() => setActiveIndex(idx, Math.max(0, activeIndex - 1))}
                  disabled={!canGoPrev}
                  className={`p-1 rounded transition-colors ${
                    canGoPrev
                      ? 'text-gray-400 hover:text-white hover:bg-surface/50'
                      : 'text-gray-700 cursor-not-allowed'
                  }`}
                >
                  <ChevronLeft className="w-3 h-3" />
                </button>

                <div className="flex-1 flex items-center gap-0.5 overflow-x-auto scrollbar-hide">
                  {toolCallSteps.map((tc, tcIdx) => {
                    const tcResult = getToolResult(tc.toolCallId)
                    const isActive = tcIdx === activeIndex
                    const statusColors = {
                      running: 'border-blue-500',
                      completed: 'border-green-500',
                      failed: 'border-red-500',
                    }
                    const status = tcResult?.status || 'running'

                    return (
                      <button
                        key={tc.toolCallId}
                        onClick={() => setActiveIndex(idx, tcIdx)}
                        className={`flex items-center gap-1.5 px-2 py-1 rounded-t-lg border-b-2 transition-colors ${
                          isActive
                            ? `bg-surface/50 ${statusColors[status]}`
                            : 'bg-transparent border-transparent hover:bg-surface/30'
                        }`}
                      >
                        <ChildStatusIcon status={status} />
                        <span className={`text-[11px] font-mono font-medium ${
                          isActive ? 'text-purple-300' : 'text-gray-400'
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
                  className={`p-1 rounded transition-colors ${
                    canGoNext
                      ? 'text-gray-400 hover:text-white hover:bg-surface/50'
                      : 'text-gray-700 cursor-not-allowed'
                  }`}
                >
                  <ChevronRight className="w-3 h-3" />
                </button>

                <span className="text-[10px] text-gray-500 font-mono px-1">
                  {activeIndex + 1}/{toolCallSteps.length}
                </span>
              </div>

              {/* Active tool call content */}
              <div className="p-2">
                <ToolCall
                  toolName={activeToolCall.toolName}
                  args={activeToolCall.toolArgs}
                  result={toolResult?.result}
                  status={toolResult?.status || 'running'}
                  duration={toolResult?.duration}
                />
                {childExec && (
                  <div className="ml-4 mt-2">
                    <RunnableExecutionView 
                      execution={childExec} 
                      depth={(execution.depth || 0) + 1}
                    />
                  </div>
                )}
              </div>

              {/* Status overview bar */}
              <div className="flex items-center gap-1 px-2 py-1.5 border-t border-border/30 bg-surface/10">
                {toolCallSteps.map((tc, tcIdx) => {
                  const tcResult = getToolResult(tc.toolCallId)
                  const status = tcResult?.status || 'running'
                  return (
                    <button
                      key={tc.toolCallId}
                      onClick={() => setActiveIndex(idx, tcIdx)}
                      className={`flex-1 h-1 rounded-full transition-colors ${
                        status === 'completed' ? 'bg-green-500/60' :
                        status === 'running' ? 'bg-blue-500/60 animate-pulse' :
                        status === 'failed' ? 'bg-red-500/60' :
                        'bg-gray-700'
                        } ${tcIdx === activeIndex ? 'ring-1 ring-white/30' : ''}`}
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
            <div key={`${step.stepId}_content_${idx}`} className="space-y-2">
              {/* Reasoning content (thinking mode) */}
              {step.reasoning_content && (
                <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-2">
                  <details className="group">
                    <summary className="cursor-pointer text-[10px] text-blue-400 font-medium flex items-center gap-1.5 hover:text-blue-300">
                      <span className="transition-transform group-open:rotate-90">▶</span>
                      <span>Thinking</span>
                    </summary>
                    <div className="mt-2 text-[10px] text-blue-300/80 leading-relaxed">
                      <MessageContent content={step.reasoning_content} />
                    </div>
                  </details>
                </div>
              )}
              {/* Main content */}
              {step.content && (
                <div className="text-xs text-gray-300 leading-relaxed">
                  <MessageContent content={step.content} />
                </div>
              )}
              {/* Metrics */}
              {step.metrics && (
                <div className="flex items-center gap-2 text-[9px] text-gray-500 font-mono">
                  {step.metrics.input_tokens && (
                    <span title="Input tokens">in: {step.metrics.input_tokens}</span>
                  )}
                  {step.metrics.output_tokens && (
                    <span title="Output tokens">out: {step.metrics.output_tokens}</span>
                  )}
                  {step.metrics.duration_ms && (
                    <span title="Response time">{(step.metrics.duration_ms / 1000).toFixed(2)}s</span>
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
      <div className="mt-2">
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
      <div className="mt-2 space-y-2">
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
    <div className="mt-2 rounded-lg border border-border/50 overflow-hidden">
      {/* Tabs header */}
      <div className="flex items-center gap-1 px-2 pt-1 border-b border-border/50 bg-surface/20">
        <button
          onClick={() => setActiveIndex(prev => prev - 1)}
          disabled={!canGoPrev}
          className={`p-1 rounded transition-colors ${
            canGoPrev
              ? 'text-gray-400 hover:text-white hover:bg-surface/50'
              : 'text-gray-700 cursor-not-allowed'
          }`}
        >
          <ChevronLeft className="w-3 h-3" />
        </button>

        <div className="flex-1 flex items-center gap-0.5 overflow-x-auto scrollbar-hide">
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
          className={`p-1 rounded transition-colors ${
            canGoNext
              ? 'text-gray-400 hover:text-white hover:bg-surface/50'
              : 'text-gray-700 cursor-not-allowed'
          }`}
        >
          <ChevronRight className="w-3 h-3" />
        </button>

        <span className="text-[10px] text-gray-500 font-mono px-1">
          {activeIndex + 1}/{standaloneChildren.length}
        </span>
      </div>

      {/* Active child content */}
      <div className="p-2">
        {activeChild && (
          <RunnableExecutionView 
            execution={activeChild} 
            depth={parentDepth + 1}
          />
        )}
      </div>

      {/* Status overview bar */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-t border-border/30 bg-surface/10">
        {standaloneChildren.map((child, idx) => (
          <button
            key={child.id}
            onClick={() => setActiveIndex(idx)}
            className={`flex-1 h-1 rounded-full transition-colors ${
              child.status === 'completed' ? 'bg-green-500/60' :
              child.status === 'running' ? 'bg-blue-500/60 animate-pulse' :
              child.status === 'failed' ? 'bg-red-500/60' :
              'bg-gray-700'
            } ${idx === activeIndex ? 'ring-1 ring-white/30' : ''}`}
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
      return 'border-amber-500/30'
    }
    return 'border-blue-500/30'
  }, [execution.nestingType])

  // For root-level agents without nested structure, render steps directly without container
  if (isRoot && execution.runnableType === 'agent' && execution.children.length === 0) {
    return <ExecutionSteps execution={execution} />
  }

  return (
    <div className={`rounded-lg border ${borderColor} bg-surface/10 overflow-hidden`}>
      <ExecutionHeader 
        execution={execution} 
        isExpanded={isExpanded}
        onToggle={() => setIsExpanded(!isExpanded)}
      />
      
      {isExpanded && (
        <div className="p-2 space-y-2">
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
