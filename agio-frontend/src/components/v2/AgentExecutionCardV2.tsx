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

function ReasoningBlock({ content, status }: { content: string, status: string }) {
  const [isCollapsed, setIsCollapsed] = useState(true);
  const isRunning = status === 'running';
  
  return (
    <div className="rounded-lg bg-blue-500/5 border border-blue-500/10 overflow-hidden min-w-0">
      <div 
        className="flex items-center justify-between px-2.5 py-1.5 cursor-pointer hover:bg-blue-500/10 transition-colors"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        {!isCollapsed ? (
          <>
            <div className="flex items-center gap-2 text-[9px] text-blue-400/70 font-bold uppercase tracking-wider min-w-0">
              <MessageSquare className="w-2.5 h-2.5 shrink-0" />
              <span className="truncate">RAW REASONING</span>
            </div>
            <div className="flex items-center gap-1 text-[9px] text-blue-400/50 font-medium shrink-0">
              <span>Collapse</span>
              <ChevronDown className="w-2.5 h-2.5" />
            </div>
          </>
        ) : (
          <div className="flex items-center gap-1 text-[9px] text-blue-400/50 font-medium min-w-0">
            <span className={`truncate ${isRunning ? "animate-pulse" : ""}`}>Thinking...</span>
            <ChevronRight className="w-2.5 h-2.5 opacity-50 shrink-0" />
          </div>
        )}
      </div>
      {!isCollapsed && (
        <div className="px-2.5 pb-2.5 text-[11px] text-blue-300/60 leading-normal font-mono whitespace-pre-wrap break-words border-t border-blue-500/5 pt-2 overflow-x-auto">
          {content}
        </div>
      )}
    </div>
  );
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
    <div className={`rounded-xl border transition-all duration-200 ${getStatusColor(execution.status)} mb-3 shadow-sm min-w-0 overflow-hidden`}>
      {/* L1: Task Summary Layer */}
      <div 
        className="p-3 cursor-pointer hover:bg-white/5 flex items-start gap-3"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="mt-0.5">
          {getStatusIcon(execution.status)}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-x-3 gap-y-1 flex-wrap">
            <div className="flex items-center gap-2">
              <h3 className="text-[13px] font-semibold text-gray-200 truncate shrink-0 max-w-[150px]">
                {summary.agentName}
              </h3>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-white/5 text-gray-500 uppercase tracking-tight shrink-0">
                AGENT
              </span>
              {!debugMode && summary.intent && (
                <span className="text-[11px] text-gray-400 truncate italic opacity-70 ml-1">
                  - {summary.intent}
                </span>
              )}
            </div>

            <div className="flex items-center gap-x-3 gap-y-1 text-[10px] text-gray-500/80">
              <div className="flex items-center gap-1 shrink-0">
                <Boxes className="w-2.5 h-2.5" />
                <span>{summary.stepCount} · {summary.childCount}</span>
              </div>
              
              {summary.toolSummaries.length > 0 && (
                <div className="flex items-center gap-1.5 overflow-hidden">
                  {summary.toolSummaries.map(ts => (
                    <div key={ts.toolName} className="flex items-center gap-1 bg-white/5 px-1.5 py-0.5 rounded border border-white/5 shrink-0">
                      {getToolIcon(ts.toolName)}
                      <span className="text-gray-500/80 truncate max-w-[80px]">{ts.toolName}{ts.count > 1 ? `×${ts.count}` : ''}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
        
        <div className="mt-0.5">
          {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-gray-600" /> : <ChevronRight className="w-3.5 h-3.5 text-gray-600" />}
        </div>
      </div>

      {/* L2 & L3 Content */}
      {isExpanded && (
        <div className="px-3 pb-3 space-y-3 border-t border-white/5 pt-3 bg-black/10">
          
          {/* Execution Trace (L2/L3) */}
          <div className="space-y-3">
            {(debugMode ? execution.steps : mergeToolCalls(execution.steps)).map((item, idx) => {
              if ('type' in item && item.type === 'merged_tool_calls') {
                return (
                  <div key={`merged-${item.toolName}-${idx}`} className="flex items-start group">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 text-xs text-purple-400 font-medium min-w-0">
                        <span className="shrink-0">{getToolIcon(item.toolName)}</span>
                        <span className="truncate">{item.toolName} (used {item.count} times)</span>
                      </div>
                      {debugMode && (
                        <div className="mt-2 space-y-2">
                           {item.steps.filter(s => s.type === 'tool_call').map((s: any, sidx) => (
                             <ToolCall 
                               key={`merged-tool-${s.toolCallId || sidx}`}
                               toolName={s.toolName}
                               args={s.toolArgs}
                               status="completed"
                               icon={getToolIcon(s.toolName)}
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
                  <div key={`assistant-${step.stepId}-${idx}`} className="space-y-3">
                    {/* Debug Layer (L3) - Reasoning */}
                    {debugMode && step.reasoning_content && (
                      <ReasoningBlock content={step.reasoning_content} status={execution.status} />
                    )}
                    
                    {/* Output (L1/L2) */}
                    {step.content && (
                      <div className="text-[13px] text-gray-300/90 leading-relaxed bg-white/5 p-2.5 rounded-lg border border-white/5">
                        <MessageContent content={step.content} />
                      </div>
                    )}
                    
                    {/* Metrics (L3) */}
                    {debugMode && step.metrics && (
                      <div className="flex flex-wrap items-center gap-3 text-[9px] text-gray-600 font-mono px-1">
                        <div className="flex items-center gap-1">
                          <Clock className="w-2.5 h-2.5" />
                          <span>{(step.metrics.duration_ms || 0) / 1000}s</span>
                        </div>
                        {step.metrics.input_tokens !== undefined && (
                          <div className="flex items-center gap-1">
                            <span>IN: {step.metrics.input_tokens}</span>
                            {(step.metrics.cache_read_tokens || step.metrics.cache_creation_tokens) && (
                              <span className="text-blue-500/60 text-[8px]">
                                (
                                {step.metrics.cache_read_tokens ? `hit:${step.metrics.cache_read_tokens}` : ''}
                                {step.metrics.cache_read_tokens && step.metrics.cache_creation_tokens ? ' ' : ''}
                                {step.metrics.cache_creation_tokens ? `write:${step.metrics.cache_creation_tokens}` : ''}
                                )
                              </span>
                            )}
                          </div>
                        )}
                        {step.metrics.output_tokens !== undefined && <span>OUT: {step.metrics.output_tokens}</span>}
                      </div>
                    )}
                  </div>
                )
              }
              
              if (step.type === 'tool_call') {
                // If it wasn't merged, it's a standalone tool call
                const result = execution.steps.find(s => s.type === 'tool_result' && s.toolCallId === step.toolCallId) as any
                const childExec = execution.children.find(c => c.id === step.childRunId)
                
                // In debug mode, if there's a child execution, we skip rendering the tool_call header
                // because AgentExecutionCardV2 already provides its own header with the agent name/status.
                if (debugMode && childExec) {
                  return (
                    <div key={`tool-child-${step.toolCallId}-${idx}`} className="space-y-2">
                       <div className="flex items-start">
                           <div className="flex-1 min-w-0">
                              <div className="mt-1 border-l-2 border-blue-500/10 pl-3">
                                <AgentExecutionCardV2 
                                  execution={childExec}
                                  debugMode={debugMode}
                                  density={density}
                                />
                              </div>
                           </div>
                       </div>
                    </div>
                  )
                }
                
                return (
                  <div key={`tool-${step.toolCallId}-${idx}`} className="space-y-2">
                    <div className="flex items-start">
                        <div className="flex-1 min-w-0">
                           {/* L2 Result Summary */}
                           {result?.result && !debugMode && (
                             <div className="mt-0.5 text-[10px] text-gray-500 truncate">
                               Result: {result.result}
                             </div>
                           )}

                           {/* L3 Full Tool Info */}
                           {debugMode && (
                             <div className="mt-0">
                               <ToolCall 
                                  toolName={step.toolName}
                                  args={step.toolArgs}
                                  result={result?.result}
                                  status={result?.status || 'completed'}
                                  icon={getToolIcon(step.toolName)}
                               />
                             </div>
                           )}
                           
                           {/* Nested Executions */}
                           {childExec && (
                             <div className="mt-2.5 ml-1.5 border-l-2 border-white/5 pl-3 min-w-0">
                               {!debugMode && (
                                 <div className="flex items-center gap-2 text-[9px] text-gray-600 uppercase tracking-widest mb-1.5 font-semibold">
                                   <Bot className="w-2.5 h-2.5" />
                                   <span>Sub-Agent Trajectory</span>
                                 </div>
                               )}
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
          {execution.children.filter(c => c.nestingType !== 'tool_call').map((child, cidx) => (
            <div key={`standalone-child-${child.id}-${cidx}`} className="ml-3 border-l-2 border-white/5 pl-3">
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
