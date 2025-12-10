/**
 * ParallelNestedRunnables - Display parallel RunnableTool executions
 * 
 * When an Agent calls multiple RunnableTools in parallel, their events
 * arrive interleaved. This component groups them by nested_runnable_id
 * and displays them in a tabbed interface similar to ParallelBranchSlider.
 */

import { useState, useMemo } from 'react'
import { ChevronLeft, ChevronRight, Check, X, Loader2, Circle, Cog } from 'lucide-react'
import { ToolCall } from './ToolCall'
import { MessageContent } from './MessageContent'

// Step types in nested execution - maintains correct order
export type NestedStep = 
  | { type: 'assistant_content'; stepId: string; content: string; reasoning_content?: string }
  | { type: 'tool_call'; toolCallId: string; toolName: string; toolArgs: string; stepId: string }
  | { type: 'tool_result'; toolCallId: string; result: string; status: 'completed' | 'failed'; duration?: number }

// Nested execution state for a single RunnableTool
export interface NestedExecution {
  id: string              // run_id of the nested execution
  runnableId: string      // nested_runnable_id (e.g. "code_assistant")
  status: 'running' | 'completed' | 'failed'
  // Steps array maintains correct execution order
  steps: NestedStep[]
  startTime: number
  endTime?: number
  metrics?: {
    input_tokens?: number
    output_tokens?: number
    duration_ms?: number
  }
}

// Legacy interface for backward compatibility (deprecated)
export interface NestedToolCall {
  id: string
  toolName: string
  toolArgs: string
  toolResult?: string
  toolStatus: 'running' | 'completed' | 'failed'
  toolDuration?: number
}

interface ParallelNestedRunnablesProps {
  executions: NestedExecution[]
  onExecutionSelect?: (executionId: string) => void
}

const ExecutionStatusIcon = ({ status }: { status: string }) => {
  switch (status) {
    case 'completed':
      return <Check className="w-3 h-3 text-green-400" />
    case 'failed':
      return <X className="w-3 h-3 text-red-400" />
    case 'running':
      return <Loader2 className="w-3 h-3 text-amber-400 animate-spin" />
    default:
      return <Circle className="w-2 h-2 text-gray-500" />
  }
}

interface ExecutionTabProps {
  execution: NestedExecution
  isActive: boolean
  onClick: () => void
}

function ExecutionTab({ execution, isActive, onClick }: ExecutionTabProps) {
  const statusColors = {
    running: 'border-amber-500',
    completed: 'border-green-500',
    failed: 'border-red-500',
  }
  
  const eventCount = execution.steps.length
  
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-2 py-1 rounded-t-lg border-b-2 transition-colors ${
        isActive 
          ? `bg-amber-500/10 ${statusColors[execution.status]}` 
          : 'bg-transparent border-transparent hover:bg-surface/30'
      }`}
    >
      <ExecutionStatusIcon status={execution.status} />
      <span className={`text-[11px] font-medium ${isActive ? 'text-amber-300' : 'text-gray-400'}`}>
        {execution.runnableId.replace(/_/g, ' ')}
      </span>
      {eventCount > 0 && (
        <span className={`px-1 py-0.5 text-[9px] rounded ${
          isActive ? 'bg-amber-500/20 text-amber-300' : 'bg-surface/50 text-gray-500'
        }`}>
          {eventCount}
        </span>
      )}
    </button>
  )
}

export function ParallelNestedRunnables({ executions, onExecutionSelect }: ParallelNestedRunnablesProps) {
  const [activeIndex, setActiveIndex] = useState(0)
  
  const canGoPrev = activeIndex > 0
  const canGoNext = activeIndex < executions.length - 1
  
  const activeExecution = executions[activeIndex]
  
  // Calculate overall status
  const overallStatus = useMemo(() => {
    if (executions.some(e => e.status === 'failed')) return 'failed'
    if (executions.some(e => e.status === 'running')) return 'running'
    if (executions.every(e => e.status === 'completed')) return 'completed'
    return 'running'
  }, [executions])
  
  const completedCount = executions.filter(e => e.status === 'completed').length
  
  if (executions.length === 0) {
    return null
  }
  
  // Single execution - simplified display
  if (executions.length === 1) {
    const exec = executions[0]
    return (
      <div className="my-2 rounded-lg border border-amber-500/30 bg-amber-500/5 overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 bg-amber-500/10 border-b border-amber-500/20">
          <Cog className="w-3.5 h-3.5 text-amber-400" />
          <span className="text-xs font-medium text-amber-300">
            {exec.runnableId.replace(/_/g, ' ')}
          </span>
          <div className="flex-1" />
          <ExecutionStatusIcon status={exec.status} />
        </div>
        <div className="p-2 space-y-1">
          {exec.steps.length === 0 && exec.status === 'running' ? (
            <div className="flex items-center gap-2 text-gray-500 text-xs py-2">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Executing...</span>
            </div>
          ) : (
            exec.steps.map((step, idx) => {
              if (step.type === 'assistant_content') {
                return (
                  <div key={`${step.stepId}_content`} className="text-xs text-gray-300 leading-relaxed">
                    <MessageContent content={step.content} />
                  </div>
                )
              } else if (step.type === 'tool_call') {
                // Find corresponding tool_result if exists
                const toolResult = exec.steps.find(
                  s => s.type === 'tool_result' && s.toolCallId === step.toolCallId
                ) as Extract<NestedStep, { type: 'tool_result' }> | undefined
                
                return (
                  <ToolCall
                    key={`${step.toolCallId}_call`}
                    toolName={step.toolName}
                    args={step.toolArgs}
                    result={toolResult?.result}
                    status={toolResult ? toolResult.status : 'running'}
                    duration={toolResult?.duration}
                  />
                )
              }
              // tool_result steps are rendered together with tool_call, skip here
              return null
            })
          )}
        </div>
      </div>
    )
  }
  
  // Multiple parallel executions - tabbed display
  return (
    <div className="my-2 rounded-lg border border-amber-500/30 bg-amber-500/5 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-amber-500/10 border-b border-amber-500/20">
        <Cog className="w-3.5 h-3.5 text-amber-400" />
        <span className="text-xs font-medium text-amber-300">
          Parallel Executions
        </span>
        <span className="text-[10px] text-gray-500">
          {completedCount}/{executions.length}
        </span>
        <div className="flex-1" />
        <span className={`px-1.5 py-0.5 text-[10px] rounded border ${
          overallStatus === 'completed' ? 'bg-green-500/20 text-green-400 border-green-500/30' :
          overallStatus === 'failed' ? 'bg-red-500/20 text-red-400 border-red-500/30' :
          'bg-amber-500/20 text-amber-400 border-amber-500/30'
        }`}>
          {overallStatus}
        </span>
      </div>
      
      {/* Execution tabs */}
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
          {executions.map((exec, idx) => (
            <ExecutionTab
              key={exec.id}
              execution={exec}
              isActive={idx === activeIndex}
              onClick={() => {
                setActiveIndex(idx)
                onExecutionSelect?.(exec.id)
              }}
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
          {activeIndex + 1}/{executions.length}
        </span>
      </div>
      
      {/* Active execution content */}
      <div className="p-2 min-h-[60px]">
        {activeExecution && (
          <div className="space-y-1">
            {activeExecution.steps.length === 0 && activeExecution.status === 'running' ? (
              <div className="flex items-center gap-2 text-gray-500 text-xs py-2">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Executing {activeExecution.runnableId}...</span>
              </div>
            ) : (
              activeExecution.steps.map((step, idx) => {
                if (step.type === 'assistant_content') {
                  return (
                    <div key={`${step.stepId}_content`} className="space-y-2">
                      {/* Reasoning content (thinking mode) */}
                      {step.reasoning_content && (
                        <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-2">
                          <details className="group">
                            <summary className="cursor-pointer text-[10px] text-blue-400 font-medium flex items-center gap-1.5 hover:text-blue-300">
                              <span className="transition-transform group-open:rotate-90">▶</span>
                              <span>思考过程 (Thinking)</span>
                            </summary>
                            <div className="mt-2 text-[10px] text-blue-300/80 leading-relaxed">
                              <MessageContent content={step.reasoning_content} />
                            </div>
                          </details>
                        </div>
                      )}
                      {/* Main content */}
                      <div className="text-xs text-gray-300 leading-relaxed">
                        <MessageContent content={step.content} />
                      </div>
                    </div>
                  )
                } else if (step.type === 'tool_call') {
                  // Find corresponding tool_result if exists
                  const toolResult = activeExecution.steps.find(
                    s => s.type === 'tool_result' && s.toolCallId === step.toolCallId
                  ) as Extract<NestedStep, { type: 'tool_result' }> | undefined
                  
                  return (
                    <ToolCall
                      key={`${step.toolCallId}_call`}
                      toolName={step.toolName}
                      args={step.toolArgs}
                      result={toolResult?.result}
                      status={toolResult ? toolResult.status : 'running'}
                      duration={toolResult?.duration}
                    />
                  )
                }
                // tool_result steps are rendered together with tool_call, skip here
                return null
              })
            )}
          </div>
        )}
      </div>
      
      {/* Status overview bar */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-t border-border/30 bg-surface/10">
        {executions.map((exec, idx) => (
          <button
            key={exec.id}
            onClick={() => setActiveIndex(idx)}
            className={`flex-1 h-1 rounded-full transition-colors ${
              exec.status === 'completed' ? 'bg-green-500/60' :
              exec.status === 'running' ? 'bg-amber-500/60 animate-pulse' :
              exec.status === 'failed' ? 'bg-red-500/60' :
              'bg-gray-700'
            } ${idx === activeIndex ? 'ring-1 ring-white/30' : ''}`}
            title={`${exec.runnableId}: ${exec.status}`}
          />
        ))}
      </div>
    </div>
  )
}
