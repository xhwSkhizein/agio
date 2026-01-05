import { useState, useEffect } from 'react'
import { 
  Bot,
  ChevronDown, 
  ChevronRight, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  Clock, 
  Terminal, 
  MessageSquare,
  Search,
  Code,
  FileText,
  Boxes,
  Activity
} from 'lucide-react'
import { RunnableExecution, ExecutionStep } from '../../types/execution'
import { summarizeExecution, mergeToolCalls } from '../../utils/v2/dataSummary'
import { MessageContent } from '../MessageContent'
import { ToolCall } from '../ToolCall'

interface AgentExecutionCardV2Props {
  execution: RunnableExecution
  isRoot?: boolean
  debugMode?: boolean
  density?: 'compact' | 'detailed'
}

export function AgentExecutionCardV2({
  execution,
  isRoot = false,
  debugMode = false,
  density = 'detailed'
}: AgentExecutionCardV2Props) {
  const [isExpanded, setIsExpanded] = useState(isRoot || debugMode)
  const summary = summarizeExecution(execution)
  
  // Auto-expand when debug mode is turned on
  useEffect(() => {
    if (debugMode) {
      setIsExpanded(true)
    }
  }, [debugMode])
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle2 className="w-4 h-4 text-green-500" />
      case 'failed': return <XCircle className="w-4 h-4 text-red-500" />
      case 'running': return <Activity className="w-4 h-4 text-blue-500 animate-pulse" />
      default: return <AlertCircle className="w-4 h-4 text-yellow-500" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'border-green-500/30 bg-green-500/5'
      case 'failed': return 'border-red-500/30 bg-red-500/5'
      case 'running': return 'border-blue-500/30 bg-blue-500/5'
      default: return 'border-yellow-500/30 bg-yellow-500/5'
    }
  }

  const getToolIcon = (name: string) => {
    const n = name.toLowerCase()
    if (n.includes('read') || n.includes('list') || n.includes('ls')) return <Search className="w-3 h-3" />
    if (n.includes('write') || n.includes('edit') || n.includes('apply')) return <Code className="w-3 h-3" />
    if (n.includes('search') || n.includes('grep')) return <FileText className="w-3 h-3" />
    return <Terminal className="w-3 h-3" />
  }

  return (
    <div className={`rounded-xl border transition-all duration-200 overflow-hidden ${getStatusColor(execution.status)} mb-4 shadow-sm`}>
      {/* L1: Task Summary Layer */}
      <div 
        className="p-4 cursor-pointer hover:bg-white/5 flex items-start gap-3"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="mt-0.5">
          {getStatusIcon(execution.status)}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-semibold text-white truncate">
              {summary.agentName}
            </h3>
            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-white/10 text-gray-400 uppercase tracking-tight">
              AGENT
            </span>
          </div>
          
          {summary.intent && (
            <p className="text-xs text-gray-300 line-clamp-2 mb-2 italic">
              " {summary.intent} "
            </p>
          )}
          
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] text-gray-500">
            <div className="flex items-center gap-1">
              <Boxes className="w-3 h-3" />
              <span>{summary.stepCount} steps · {summary.childCount} children</span>
            </div>
            
            {summary.toolSummaries.length > 0 && (
              <div className="flex items-center gap-2">
                {summary.toolSummaries.map(ts => (
                  <div key={ts.toolName} className="flex items-center gap-1 bg-white/5 px-1.5 py-0.5 rounded border border-white/10">
                    {getToolIcon(ts.toolName)}
                    <span>{ts.toolName} {ts.count > 1 ? `×${ts.count}` : ''}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        
        <div className="mt-1">
          {isExpanded ? <ChevronDown className="w-4 h-4 text-gray-500" /> : <ChevronRight className="w-4 h-4 text-gray-500" />}
        </div>
      </div>

      {/* L2 & L3 Content */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-white/10 pt-4 bg-black/20">
          
          {/* Execution Trace (L2/L3) */}
          <div className="space-y-4">
            {(debugMode ? execution.steps : mergeToolCalls(execution.steps)).map((item, idx) => {
              if ('type' in item && item.type === 'merged_tool_calls') {
                return (
                  <div key={`merged-${idx}`} className="flex items-start gap-3 group">
                    <div className="mt-1 flex flex-col items-center">
                      <div className="w-1.5 h-1.5 rounded-full bg-purple-500/50" />
                      <div className="w-px flex-1 bg-white/10 my-1" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 text-xs text-purple-400 font-medium">
                        {getToolIcon(item.toolName)}
                        <span>{item.toolName} (used {item.count} times)</span>
                      </div>
                      {debugMode && (
                        <div className="mt-2 space-y-2">
                           {item.steps.filter(s => s.type === 'tool_call').map((s: any, sidx) => (
                             <ToolCall 
                               key={sidx}
                               toolName={s.toolName}
                               args={s.toolArgs}
                               status="completed"
                             />
                           ))}
                        </div>
                      )}
                    </div>
                  </div>
                )
              }
              
              const step = item as ExecutionStep
              
              if (step.type === 'assistant_content') {
                return (
                  <div key={step.stepId} className="space-y-3">
                    {/* Debug Layer (L3) - Reasoning */}
                    {debugMode && step.reasoning_content && (
                      <div className="rounded-lg bg-blue-500/5 border border-blue-500/20 p-3">
                        <div className="flex items-center gap-2 text-[10px] text-blue-400 font-bold uppercase tracking-wider mb-2">
                          <MessageSquare className="w-3 h-3" />
                          RAW REASONING
                        </div>
                        <div className="text-xs text-blue-200/70 leading-relaxed font-mono whitespace-pre-wrap">
                          <MessageContent content={step.reasoning_content} />
                        </div>
                      </div>
                    )}
                    
                    {/* Output (L1/L2) */}
                    {step.content && (
                      <div className="text-sm text-gray-200 leading-relaxed bg-white/5 p-3 rounded-lg border border-white/5">
                        <MessageContent content={step.content} />
                      </div>
                    )}

                    {/* Metrics (L3) */}
                    {debugMode && step.metrics && (
                      <div className="flex items-center gap-4 text-[10px] text-gray-500 font-mono px-1">
                        <div className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          <span>{(step.metrics.duration_ms || 0) / 1000}s</span>
                        </div>
                        {step.metrics.input_tokens && <span>IN: {step.metrics.input_tokens}</span>}
                        {step.metrics.output_tokens && <span>OUT: {step.metrics.output_tokens}</span>}
                      </div>
                    )}
                  </div>
                )
              }
              
              if (step.type === 'tool_call') {
                // If it wasn't merged, it's a standalone tool call
                const result = execution.steps.find(s => s.type === 'tool_result' && s.toolCallId === step.toolCallId) as any
                const childExec = execution.children.find(c => c.id === step.childRunId)
                
                return (
                  <div key={step.stepId} className="space-y-2">
                    <div className="flex items-start gap-3">
                       <div className="mt-1 flex flex-col items-center">
                          <div className="w-1.5 h-1.5 rounded-full bg-amber-500/50" />
                          <div className="w-px flex-1 bg-white/10 my-1" />
                        </div>
                        <div className="flex-1">
                           <div className="flex items-center gap-2 text-xs text-amber-400 font-medium">
                              {getToolIcon(step.toolName)}
                              <span>{step.toolName}</span>
                           </div>
                           
                           {/* L2 Result Summary */}
                           {result?.result && !debugMode && (
                             <div className="mt-1 text-[11px] text-gray-400 truncate max-w-md">
                               Result: {result.result.slice(0, 100)}...
                             </div>
                           )}

                           {/* L3 Full Tool Info */}
                           {debugMode && (
                             <div className="mt-2">
                               <ToolCall 
                                  toolName={step.toolName}
                                  args={step.toolArgs}
                                  result={result?.result}
                                  status={result?.status || 'completed'}
                               />
                             </div>
                           )}
                           
                           {/* Nested Executions */}
                           {childExec && (
                             <div className="mt-3 ml-2 border-l-2 border-white/10 pl-4">
                               <div className="flex items-center gap-2 text-[10px] text-gray-500 uppercase tracking-widest mb-2 font-semibold">
                                 <Bot className="w-3 h-3" />
                                 <span>Sub-Agent Trajectory</span>
                               </div>
                               <AgentExecutionCardV2 
                                 execution={childExec}
                                 debugMode={debugMode}
                                 density={density}
                               />
                             </div>
                           )}
                        </div>
                    </div>
                  </div>
                )
              }
              
              return null
            })}
          </div>

          {/* Recursive Standalone Children */}
          {execution.children.filter(c => c.nestingType !== 'tool_call').map(child => (
            <div key={child.id} className="ml-4 border-l-2 border-white/10 pl-4">
              <AgentExecutionCardV2 
                execution={child}
                debugMode={debugMode}
                density={density}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
