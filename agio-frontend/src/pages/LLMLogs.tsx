import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { llmLogsService, LLMCallLog, LLMStats } from '../services/api'
import {
  Activity,
  Clock,
  Zap,
  AlertCircle,
  CheckCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
  Filter,
  RefreshCw,
  Radio,
  X,
  StopCircle,
} from 'lucide-react'

export default function LLMLogs() {
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamLogs, setStreamLogs] = useState<LLMCallLog[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)

  // Filters
  const [filters, setFilters] = useState({
    agent_name: '',
    session_id: '',
    run_id: '',
    status: '',
  })
  const [showFilters, setShowFilters] = useState(false)

  // Fetch logs
  const { data: logsData, refetch: refetchLogs, isLoading } = useQuery({
    queryKey: ['llm-logs', filters],
    queryFn: () => llmLogsService.listLogs({
      ...filters,
      agent_name: filters.agent_name || undefined,
      session_id: filters.session_id || undefined,
      run_id: filters.run_id || undefined,
      status: filters.status || undefined,
      limit: 100,
    }),
    refetchInterval: isStreaming ? false : 5000,
  })

  // Fetch stats
  const { data: stats } = useQuery({
    queryKey: ['llm-stats'],
    queryFn: () => llmLogsService.getStats(),
    refetchInterval: 10000,
  })

  // Combine stream logs with fetched logs
  const allLogs = isStreaming
    ? [...streamLogs, ...(logsData?.items || [])].filter(
        (log, index, self) => self.findIndex((l) => l.id === log.id) === index
      )
    : logsData?.items || []

  // Start/stop streaming
  const toggleStreaming = useCallback(() => {
    if (isStreaming) {
      eventSourceRef.current?.close()
      eventSourceRef.current = null
      setIsStreaming(false)
    } else {
      const url = llmLogsService.getStreamUrl({
        agent_name: filters.agent_name || undefined,
        session_id: filters.session_id || undefined,
        run_id: filters.run_id || undefined,
      })
      const es = new EventSource(url)

      es.addEventListener('llm_call', (event) => {
        const log = JSON.parse(event.data) as LLMCallLog
        setStreamLogs((prev) => {
          const existing = prev.findIndex((l) => l.id === log.id)
          if (existing >= 0) {
            const updated = [...prev]
            updated[existing] = log
            return updated
          }
          return [log, ...prev].slice(0, 100)
        })
      })

      es.onerror = () => {
        es.close()
        setIsStreaming(false)
      }

      eventSourceRef.current = es
      setIsStreaming(true)
      setStreamLogs([])
    }
  }, [isStreaming, filters])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close()
    }
  }, [])

  const clearFilters = () => {
    setFilters({ agent_name: '', session_id: '', run_id: '', status: '' })
  }

  const hasActiveFilters = Object.values(filters).some((v) => v !== '')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-white">LLM Logs</h1>
          <p className="mt-1 text-sm text-gray-400">Monitor all LLM API calls in real-time</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              showFilters || hasActiveFilters
                ? 'bg-primary-500/20 text-primary-400 border border-primary-500/50'
                : 'bg-surfaceHighlight text-gray-300 hover:text-white'
            }`}
          >
            <Filter className="w-4 h-4" />
            Filters
            {hasActiveFilters && (
              <span className="bg-primary-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                {Object.values(filters).filter((v) => v !== '').length}
              </span>
            )}
          </button>
          <button
            onClick={() => refetchLogs()}
            className="flex items-center gap-2 px-3 py-2 bg-surfaceHighlight rounded-lg text-sm font-medium text-gray-300 hover:text-white transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={toggleStreaming}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              isStreaming
                ? 'bg-red-500/20 text-red-400 border border-red-500/50'
                : 'bg-green-500/20 text-green-400 border border-green-500/50'
            }`}
          >
            <Radio className={`w-4 h-4 ${isStreaming ? 'animate-pulse' : ''}`} />
            {isStreaming ? 'Stop Stream' : 'Live Stream'}
          </button>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="bg-surface border border-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-white">Filters</h3>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="text-xs text-gray-400 hover:text-white flex items-center gap-1"
              >
                <X className="w-3 h-3" />
                Clear all
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <input
              type="text"
              placeholder="Agent Name"
              value={filters.agent_name}
              onChange={(e) => setFilters({ ...filters, agent_name: e.target.value })}
              className="bg-surfaceHighlight border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary-500"
            />
            <input
              type="text"
              placeholder="Session ID"
              value={filters.session_id}
              onChange={(e) => setFilters({ ...filters, session_id: e.target.value })}
              className="bg-surfaceHighlight border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary-500"
            />
            <input
              type="text"
              placeholder="Run ID"
              value={filters.run_id}
              onChange={(e) => setFilters({ ...filters, run_id: e.target.value })}
              className="bg-surfaceHighlight border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary-500"
            />
            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              className="bg-surfaceHighlight border border-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-primary-500"
            >
              <option value="">All Status</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="error">Error</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      {stats && <StatsCards stats={stats} />}

      {/* Logs List - Full Width */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-medium text-white">
            Recent Calls
            {isStreaming && (
              <span className="ml-2 text-xs text-green-400 animate-pulse">● Live</span>
            )}
          </h2>
          <span className="text-xs text-gray-500">{allLogs.length} logs</span>
        </div>
        <div className="max-h-[calc(100vh-320px)] overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
            </div>
          ) : allLogs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-500">
              <Activity className="w-8 h-8 mb-2" />
              <p className="text-sm">No LLM calls recorded yet</p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {allLogs.map((log) => (
                <LogItemWithDetail
                  key={log.id}
                  log={log}
                  isExpanded={expandedLogId === log.id}
                  onToggle={() => setExpandedLogId(expandedLogId === log.id ? null : log.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StatsCards({ stats }: { stats: LLMStats }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard
        title="Total Calls"
        value={stats.total_calls}
        icon={<Activity className="w-4 h-4" />}
        color="blue"
      />
      <StatCard
        title="Success Rate"
        value={`${(stats.success_rate * 100).toFixed(1)}%`}
        icon={<CheckCircle className="w-4 h-4" />}
        color="green"
      />
      <StatCard
        title="Avg Duration"
        value={`${(stats.avg_duration_ms / 1000).toFixed(2)}s`}
        icon={<Clock className="w-4 h-4" />}
        color="yellow"
      />
      <StatCard
        title="Total Tokens"
        value={stats.total_tokens.toLocaleString()}
        icon={<Zap className="w-4 h-4" />}
        color="purple"
      />
    </div>
  )
}

function StatCard({
  title,
  value,
  icon,
  color,
}: {
  title: string
  value: string | number
  icon: React.ReactNode
  color: 'blue' | 'green' | 'yellow' | 'purple'
}) {
  const colorClasses = {
    blue: 'bg-blue-900/20 text-blue-400 border-blue-900/50',
    green: 'bg-green-900/20 text-green-400 border-green-900/50',
    yellow: 'bg-yellow-900/20 text-yellow-400 border-yellow-900/50',
    purple: 'bg-purple-900/20 text-purple-400 border-purple-900/50',
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">{title}</p>
          <p className="mt-1 text-xl font-bold text-white">{value}</p>
        </div>
        <div className={`${colorClasses[color]} border rounded-lg p-2`}>{icon}</div>
      </div>
    </div>
  )
}

function LogItemWithDetail({
  log,
  isExpanded,
  onToggle,
}: {
  log: LLMCallLog
  isExpanded: boolean
  onToggle: () => void
}) {
  const statusIcon = {
    running: <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />,
    completed: <CheckCircle className="w-4 h-4 text-green-400" />,
    error: <AlertCircle className="w-4 h-4 text-red-400" />,
    cancelled: <StopCircle className="w-4 h-4 text-yellow-400" />,
  }

  const timestamp = new Date(log.timestamp).toLocaleTimeString()
  const date = new Date(log.timestamp).toLocaleDateString()

  return (
    <div className={isExpanded ? 'bg-surfaceHighlight/30' : ''}>
      {/* Header Row - Clickable */}
      <div
        onClick={onToggle}
        className={`px-4 py-3 cursor-pointer transition-colors hover:bg-surfaceHighlight ${
          isExpanded ? 'border-l-2 border-primary-500' : ''
        }`}
      >
        <div className="flex items-center gap-4">
          {/* Expand Icon */}
          <div className="text-gray-500">
            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </div>

          {/* Status */}
          {statusIcon[log.status]}

          {/* Model & Provider */}
          <div className="flex items-center gap-2 min-w-[200px]">
            <span className="text-sm font-medium text-white">{log.model_id}</span>
            <span className="text-xs px-1.5 py-0.5 bg-surfaceHighlight rounded text-gray-400">
              {log.provider}
            </span>
          </div>

          {/* Agent */}
          <div className="flex-1 min-w-0">
            {log.agent_name && (
              <span className="text-sm text-gray-400 truncate">{log.agent_name}</span>
            )}
          </div>

          {/* Metrics */}
          <div className="flex items-center gap-4 text-xs text-gray-500">
            {log.duration_ms && (
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {(log.duration_ms / 1000).toFixed(2)}s
              </span>
            )}
            {log.total_tokens && (
              <span className="flex items-center gap-1">
                <Zap className="w-3 h-3" />
                {log.total_tokens}
              </span>
            )}
            <span>{date} {timestamp}</span>
          </div>
        </div>
      </div>

      {/* Expanded Detail */}
      {isExpanded && <LogDetailPanel log={log} />}
    </div>
  )
}

function LogDetailPanel({ log }: { log: LLMCallLog }) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['response'])
  )
  const [expandedMessages, setExpandedMessages] = useState<Set<number>>(
    new Set()
  )
  const [expandedContent, setExpandedContent] = useState<Set<string>>(
    new Set()
  )

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev)
      if (next.has(section)) {
        next.delete(section)
      } else {
        next.add(section)
      }
      return next
    })
  }

  const toggleMessage = (index: number) => {
    setExpandedMessages((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  const toggleContent = (contentId: string) => {
    setExpandedContent((prev) => {
      const next = new Set(prev)
      if (next.has(contentId)) {
        next.delete(contentId)
      } else {
        next.add(contentId)
      }
      return next
    })
  }

  return (
    <div className="border-t border-border bg-surface/50 max-w-full overflow-hidden">
      {/* Quick Info Bar */}
      <div className="px-4 py-3 border-b border-border/50 flex flex-wrap gap-x-6 gap-y-2 text-xs max-w-full">
        <InfoItem label="ID" value={log.id} mono />
        <InfoItem label="Status" value={<StatusBadge status={log.status} />} />
        {log.session_id && <InfoItem label="Session" value={log.session_id} mono />}
        {log.run_id && <InfoItem label="Run" value={log.run_id} mono />}
        {log.first_token_ms && <InfoItem label="TTFT" value={`${(log.first_token_ms / 1000).toFixed(3)}s`} />}
        {log.input_tokens && <InfoItem label="In" value={`${log.input_tokens} tokens`} />}
        {log.output_tokens && <InfoItem label="Out" value={`${log.output_tokens} tokens`} />}
        {log.finish_reason && <InfoItem label="Finish" value={log.finish_reason} />}
      </div>

      {/* Collapsible Sections */}
      <div className="divide-y divide-border/50 max-w-full overflow-hidden">
        {/* Request Messages */}
        <DetailSection
          title={`Request Messages (${log.messages.length})`}
          isExpanded={expandedSections.has('request')}
          onToggle={() => toggleSection('request')}
        >
          <div className="space-y-3 max-w-full">
            {log.messages.map((msg, idx) => {
              const isMessageExpanded = expandedMessages.has(idx)
              const msgContent = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content, null, 2)
              const reasoningContent = msg.reasoning_content || (typeof msg.reasoning_content === 'string' ? msg.reasoning_content : null)
              const hasLongContent = (msgContent?.length || 0) > 300 || (reasoningContent?.length || 0) > 0 || (msg.tool_calls?.length || 0) > 0
              
              return (
                <div key={idx} className="bg-background rounded-lg p-3 border border-border/50 max-w-full overflow-hidden">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-medium px-2 py-0.5 rounded ${
                          msg.role === 'user'
                            ? 'bg-blue-900/30 text-blue-400'
                            : msg.role === 'assistant'
                            ? 'bg-green-900/30 text-green-400'
                            : msg.role === 'system'
                            ? 'bg-purple-900/30 text-purple-400'
                            : msg.role === 'tool'
                            ? 'bg-orange-900/30 text-orange-400'
                            : 'bg-gray-900/30 text-gray-400'
                        }`}
                      >
                        {msg.role}
                      </span>
                      {msg.tool_call_id && (
                        <span className="text-xs font-mono text-gray-500">
                          {msg.tool_call_id}
                        </span>
                      )}
                    </div>
                    {hasLongContent && (
                      <button
                        onClick={() => toggleMessage(idx)}
                        className="text-xs text-gray-400 hover:text-white transition-colors"
                      >
                        {isMessageExpanded ? 'Collapse' : 'Expand'}
                      </button>
                    )}
                  </div>
                  {/* Reasoning content */}
                  {reasoningContent && (
                    <div className={`mb-2 p-2 bg-purple-900/10 border border-purple-500/20 rounded text-xs text-purple-300 ${
                      !isMessageExpanded ? 'max-h-24 overflow-hidden' : ''
                    }`}>
                      <div className="font-medium mb-1">Reasoning:</div>
                      <pre className="whitespace-pre-wrap break-words max-w-full overflow-x-auto">{reasoningContent}</pre>
                    </div>
                  )}
                  {/* Message content */}
                  {msgContent && (
                    <div className={!isMessageExpanded ? 'max-h-32 overflow-hidden' : 'max-w-full'}>
                      <pre className="text-sm text-gray-300 whitespace-pre-wrap break-words max-w-full overflow-x-auto">
                        {msgContent}
                      </pre>
                    </div>
                  )}
                  {/* Tool calls for assistant messages */}
                  {msg.role === 'assistant' && msg.tool_calls && msg.tool_calls.length > 0 && (
                    <div className={`mt-2 space-y-2 ${!isMessageExpanded ? 'max-h-32 overflow-hidden' : ''}`}>
                      <div className="text-xs font-medium text-gray-400">Tool Calls ({msg.tool_calls.length}):</div>
                      {msg.tool_calls.map((tc: any, tcIdx: number) => (
                        <div key={tcIdx} className="bg-surfaceHighlight rounded p-2 border border-border/30">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-medium text-orange-400">
                              {tc.function?.name || tc.name || 'unknown'}
                            </span>
                            {tc.id && (
                              <span className="text-xs font-mono text-gray-500">{tc.id}</span>
                            )}
                          </div>
                          <pre className="text-xs text-gray-400 whitespace-pre-wrap break-words max-w-full overflow-x-auto">
                            {tc.function?.arguments 
                              ? (typeof tc.function.arguments === 'string' 
                                  ? tc.function.arguments 
                                  : JSON.stringify(tc.function.arguments, null, 2))
                              : JSON.stringify(tc, null, 2)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  )}
                  {/* Show expand hint when collapsed */}
                  {!isMessageExpanded && hasLongContent && (
                    <button
                      onClick={() => toggleMessage(idx)}
                      className="mt-2 text-xs text-gray-500 hover:text-primary-400 transition-colors"
                    >
                      Click to expand...
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </DetailSection>

        {/* Tools */}
        {log.tools && log.tools.length > 0 && (
          <DetailSection
            title={`Tools (${log.tools.length})`}
            isExpanded={expandedSections.has('tools')}
            onToggle={() => toggleSection('tools')}
          >
            {expandedSections.has('tools') && (() => {
              const toolsContent = JSON.stringify(log.tools, null, 2)
              const isContentExpanded = expandedContent.has('tools')
              const hasLongContent = toolsContent.length > 300
              
              return (
                <div className="max-w-full">
                  <div className={!isContentExpanded ? 'max-h-32 overflow-hidden' : 'max-h-[75vh] overflow-y-auto max-w-full'}>
                    <pre className="text-sm text-gray-300 bg-background rounded-lg p-3 border border-border/50 max-w-full overflow-x-auto break-words whitespace-pre-wrap">
                      {toolsContent}
                    </pre>
                  </div>
                  {hasLongContent && (
                    <button
                      onClick={() => toggleContent('tools')}
                      className="mt-2 text-xs text-gray-500 hover:text-primary-400 transition-colors"
                    >
                      {isContentExpanded ? 'Click to collapse...' : 'Click to expand...'}
                    </button>
                  )}
                </div>
              )
            })()}
          </DetailSection>
        )}

        {/* Response */}
        <DetailSection
          title="Response"
          isExpanded={expandedSections.has('response')}
          onToggle={() => toggleSection('response')}
        >
          {expandedSections.has('response') && (() => {
            const isContentExpanded = expandedContent.has('response')
            
            if (log.error) {
              const hasLongContent = log.error.length > 300
              return (
                <div className="max-w-full">
                  <div className={!isContentExpanded ? 'max-h-32 overflow-hidden' : 'max-h-[75vh] overflow-y-auto max-w-full'}>
                    <div className="bg-red-900/20 border border-red-900/50 rounded-lg p-4 max-w-full">
                      <p className="text-sm text-red-400 font-mono break-words max-w-full overflow-x-auto">{log.error}</p>
                    </div>
                  </div>
                  {hasLongContent && (
                    <button
                      onClick={() => toggleContent('response')}
                      className="mt-2 text-xs text-gray-500 hover:text-primary-400 transition-colors"
                    >
                      {isContentExpanded ? 'Click to collapse...' : 'Click to expand...'}
                    </button>
                  )}
                </div>
              )
            } else if (log.response_content) {
              const hasLongContent = log.response_content.length > 300
              return (
                <div className="max-w-full">
                  <div className={!isContentExpanded ? 'max-h-32 overflow-hidden' : 'max-h-[75vh] overflow-y-auto max-w-full'}>
                    <pre className="text-sm text-gray-300 whitespace-pre-wrap break-words bg-background rounded-lg p-4 border border-border/50 max-w-full overflow-x-auto">
                      {log.response_content}
                    </pre>
                  </div>
                  {hasLongContent && (
                    <button
                      onClick={() => toggleContent('response')}
                      className="mt-2 text-xs text-gray-500 hover:text-primary-400 transition-colors"
                    >
                      {isContentExpanded ? 'Click to collapse...' : 'Click to expand...'}
                    </button>
                  )}
                </div>
              )
            } else if (log.status === 'running') {
              return (
                <div className="flex items-center gap-2 text-gray-400 py-4">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Waiting for response...</span>
                </div>
              )
            } else if (log.status === 'cancelled') {
              return (
                <div className="flex items-center gap-2 text-yellow-400 py-4">
                  <StopCircle className="w-4 h-4" />
                  <span className="text-sm">Request cancelled</span>
                </div>
              )
            } else {
              return (
                <p className="text-sm text-gray-500 py-4">No response content</p>
              )
            }
          })()}
        </DetailSection>

        {/* Tool Calls */}
        {log.response_tool_calls && log.response_tool_calls.length > 0 && (
          <DetailSection
            title={`Tool Calls (${log.response_tool_calls.length})`}
            isExpanded={expandedSections.has('tool_calls')}
            onToggle={() => toggleSection('tool_calls')}
          >
            {expandedSections.has('tool_calls') && (() => {
              const toolCallsContent = JSON.stringify(log.response_tool_calls, null, 2)
              const isContentExpanded = expandedContent.has('tool_calls')
              const hasLongContent = toolCallsContent.length > 300
              
              return (
                <div className="max-w-full">
                  <div className={!isContentExpanded ? 'max-h-32 overflow-hidden' : 'max-h-[75vh] overflow-y-auto max-w-full'}>
                    <pre className="text-sm text-gray-300 bg-background rounded-lg p-3 border border-border/50 max-w-full overflow-x-auto break-words whitespace-pre-wrap">
                      {toolCallsContent}
                    </pre>
                  </div>
                  {hasLongContent && (
                    <button
                      onClick={() => toggleContent('tool_calls')}
                      className="mt-2 text-xs text-gray-500 hover:text-primary-400 transition-colors"
                    >
                      {isContentExpanded ? 'Click to collapse...' : 'Click to expand...'}
                    </button>
                  )}
                </div>
              )
            })()}
          </DetailSection>
        )}

        {/* Request Parameters */}
        <DetailSection
          title="Request Parameters"
          isExpanded={expandedSections.has('params')}
          onToggle={() => toggleSection('params')}
        >
          <div className="max-w-full">
            <pre className="text-sm text-gray-300 bg-background rounded-lg p-3 border border-border/50 max-w-full overflow-x-auto break-words whitespace-pre-wrap">
              {JSON.stringify(log.request, null, 2)}
            </pre>
          </div>
        </DetailSection>
      </div>
    </div>
  )
}

function InfoItem({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-gray-500">{label}:</span>
      <span className={`text-gray-300 ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  )
}

function DetailSection({
  title,
  isExpanded,
  onToggle,
  children,
}: {
  title: string
  isExpanded: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <div className="max-w-full overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-2.5 flex items-center justify-between text-sm font-medium text-gray-400 hover:text-white transition-colors"
      >
        <span className="truncate">{title}</span>
        {isExpanded ? <ChevronDown className="w-4 h-4 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 flex-shrink-0" />}
      </button>
      {isExpanded && <div className="px-4 pb-4 max-w-full overflow-hidden">{children}</div>}
    </div>
  )
}

function StatusBadge({ status }: { status: 'running' | 'completed' | 'error' | 'cancelled' }) {
  const styles = {
    running: 'bg-blue-900/30 text-blue-400 border-blue-900/50',
    completed: 'bg-green-900/30 text-green-400 border-green-900/50',
    error: 'bg-red-900/30 text-red-400 border-red-900/50',
    cancelled: 'bg-yellow-900/30 text-yellow-400 border-yellow-900/50',
  }

  return (
    <span className={`text-xs px-2 py-0.5 rounded border ${styles[status]}`}>
      {status}
    </span>
  )
}
