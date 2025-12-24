import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Activity, Clock, MessageSquare, Wrench, ChevronDown, ChevronRight } from 'lucide-react';
import { Waterfall } from '../components/Waterfall';

interface TraceDetail {
  trace_id: string;
  workflow_id: string | null;
  agent_id: string | null;
  session_id: string | null;
  user_id: string | null;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  status: string;
  total_tokens: number;
  total_llm_calls: number;
  total_tool_calls: number;
  max_depth: number;
  input_query: string | null;
  final_output: string | null;
}

interface WaterfallData {
  trace_id: string;
  total_duration_ms: number;
  spans: any[];
  metrics: Record<string, any>;
}

export default function TraceDetail() {
  const { traceId } = useParams<{ traceId: string }>();
  const navigate = useNavigate();
  const [trace, setTrace] = useState<TraceDetail | null>(null);
  const [waterfall, setWaterfall] = useState<WaterfallData | null>(null);
  const [selectedSpan, setSelectedSpan] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (traceId) {
      fetchTrace(traceId);
    }
  }, [traceId]);

  const fetchTrace = async (id: string) => {
    setLoading(true);
    try {
      const [traceRes, waterfallRes] = await Promise.all([
        fetch(`/agio/traces/${id}`),
        fetch(`/agio/traces/${id}/waterfall`),
      ]);
      
      if (!traceRes.ok || !waterfallRes.ok) {
        throw new Error('Failed to fetch trace data');
      }
      
      setTrace(await traceRes.json());
      setWaterfall(await waterfallRes.json());
    } catch (error) {
      console.error('Failed to fetch trace:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !trace || !waterfall) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-gray-600 dark:text-gray-400">Loading trace...</p>
        </div>
      </div>
    );
  }

  const formatDuration = (ms: number) => {
    if (ms < 1) return '<1ms';
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      ok: 'bg-green-500/20 text-green-400 border border-green-500/50',
      error: 'bg-red-500/20 text-red-400 border border-red-500/50',
      running: 'bg-blue-500/20 text-blue-400 border border-blue-500/50',
    };
    return colors[status] || 'bg-gray-500/20 text-gray-400 border border-gray-500/50';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => navigate('/traces')}
          className="flex items-center gap-2 text-gray-400 hover:text-white mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Traces
        </button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">
              {trace.workflow_id || trace.agent_id || 'Trace'}
            </h1>
            <p className="text-sm text-gray-400 font-mono mt-1">
              {trace.trace_id}
            </p>
          </div>
          <span className={`px-3 py-1 inline-flex text-sm font-semibold rounded-full ${getStatusColor(trace.status)}`}>
            {trace.status}
          </span>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-surface border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-primary-400" />
            <span className="text-xs font-medium text-gray-400">Duration</span>
          </div>
          <p className="text-2xl font-bold text-white">
            {trace.duration_ms ? `${(trace.duration_ms / 1000).toFixed(2)}s` : '-'}
          </p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-yellow-500" />
            <span className="text-xs font-medium text-gray-400">Total Tokens</span>
          </div>
          <p className="text-2xl font-bold text-white">
            {trace.total_tokens.toLocaleString()}
          </p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <MessageSquare className="w-4 h-4 text-green-500" />
            <span className="text-xs font-medium text-gray-400">LLM Calls</span>
          </div>
          <p className="text-2xl font-bold text-white">
            {trace.total_llm_calls}
          </p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Wrench className="w-4 h-4 text-cyan-500" />
            <span className="text-xs font-medium text-gray-400">Tool Calls</span>
          </div>
          <p className="text-2xl font-bold text-white">
            {trace.total_tool_calls}
          </p>
        </div>
      </div>

      {/* Input/Output */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-surface border border-border rounded-xl p-4">
          <h3 className="text-sm font-medium text-white mb-3">Input</h3>
          <pre className="text-sm whitespace-pre-wrap bg-background p-4 rounded-lg border border-border max-h-48 overflow-y-auto text-gray-300">
            {trace.input_query || '-'}
          </pre>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <h3 className="text-sm font-medium text-white mb-3">Output</h3>
          <pre className="text-sm whitespace-pre-wrap bg-background p-4 rounded-lg border border-border max-h-48 overflow-y-auto text-gray-300">
            {trace.final_output || '-'}
          </pre>
        </div>
      </div>

      {/* Waterfall Chart */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <h2 className="text-lg font-bold text-white mb-6">
          Execution Timeline
        </h2>
        <Waterfall
          spans={waterfall.spans}
          totalDuration={waterfall.total_duration_ms}
          onSpanClick={setSelectedSpan}
        />
      </div>

      {/* Span Detail Modal */}
      {selectedSpan && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedSpan(null)}
        >
          <div
            className="bg-surface border border-border rounded-xl shadow-2xl flex flex-col max-w-5xl w-full max-h-[90vh] mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header - Fixed */}
            <div className="flex items-start justify-between gap-4 p-6 border-b border-border shrink-0">
              <div className="flex-1 min-w-0">
                <h3 className="text-xl font-bold text-white mb-1 truncate">
                  {selectedSpan.label}
                </h3>
                <div className="flex flex-wrap items-center gap-3 text-xs mt-2">
                  <span className="px-2 py-1 rounded bg-primary-500/10 text-primary-300 border border-primary-500/30 capitalize">
                    {selectedSpan.kind.replace('_', ' ')}
                  </span>
                  {selectedSpan.duration_ms > 0 && (
                    <span className="text-gray-300">
                      Duration:{' '}
                      <strong className="text-blue-400">
                        {formatDuration(selectedSpan.duration_ms)}
                      </strong>
                    </span>
                  )}
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${getStatusColor(selectedSpan.status)}`}>
                    {selectedSpan.status}
                  </span>
                  {selectedSpan.tokens && selectedSpan.tokens > 0 && (
                    <span className="text-gray-300">
                      Tokens:{' '}
                      <strong className="text-yellow-400">
                        {selectedSpan.tokens.toLocaleString()}
                      </strong>
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => setSelectedSpan(null)}
                className="text-gray-400 hover:text-white text-lg font-bold shrink-0 w-8 h-8 flex items-center justify-center rounded hover:bg-surfaceHighlight transition-colors"
                aria-label="Close"
              >
                ×
              </button>
            </div>

            {/* Content - Scrollable */}
            <div className="flex-1 overflow-y-auto p-6">

              {/* Metrics grid */}
              {selectedSpan.metrics && Object.keys(selectedSpan.metrics).length > 0 && (
                <div className="mb-6">
                  <h4 className="text-sm font-semibold text-white mb-3">Metrics</h4>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
                    {Object.entries(selectedSpan.metrics).map(([key, value]) => {
                      // Color code based on metric type
                      let valueColor = 'text-white';
                      if (key.includes('token')) {
                        valueColor = 'text-yellow-400';
                      } else if (key.includes('duration') || key.includes('latency') || key.includes('time')) {
                        valueColor = 'text-blue-400';
                      }
                      
                      return (
                        <div
                          key={key}
                          className="flex flex-col bg-background border border-border rounded-lg px-3 py-2"
                        >
                          <span className="text-[11px] uppercase tracking-wide text-gray-400 mb-1">
                            {key.replace(/\./g, ' ')}
                          </span>
                          <span className={`text-sm font-medium break-words ${valueColor}`}>
                            {value === null || value === undefined ? '-' : String(value)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Error section */}
              {selectedSpan.error_message && (
                <div className="mb-6">
                  <span className="text-sm font-medium text-red-400">Error</span>
                  <pre className="mt-2 text-sm bg-red-500/10 p-3 rounded-lg border border-red-500/50 text-red-300 overflow-x-auto">
                    {selectedSpan.error_message}
                  </pre>
                </div>
              )}

              {/* LLM Call Details (for LLM_CALL spans) */}
              {selectedSpan.kind === 'llm_call' && selectedSpan.llm_details && (
                <LLMCallDetailsPanel llmDetails={selectedSpan.llm_details} />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function LLMCallDetailsPanel({ llmDetails }: { llmDetails: Record<string, any> }) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['response']));
  const [expandedMessages, setExpandedMessages] = useState<Set<number>>(new Set());
  const [expandedContent, setExpandedContent] = useState<Set<string>>(new Set());

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  const toggleMessage = (index: number) => {
    setExpandedMessages((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const toggleContent = (contentId: string) => {
    setExpandedContent((prev) => {
      const next = new Set(prev);
      if (next.has(contentId)) {
        next.delete(contentId);
      } else {
        next.add(contentId);
      }
      return next;
    });
  };

  return (
    <div className="border-t border-border pt-4">
      <h4 className="text-sm font-semibold text-white mb-4">LLM Call Details</h4>

      <div className="divide-y divide-border/50 max-h-none">
        {/* Request Messages */}
        {llmDetails.messages && llmDetails.messages.length > 0 && (
          <DetailSection
            title={`Request Messages (${llmDetails.messages.length})`}
            isExpanded={expandedSections.has('request')}
            onToggle={() => toggleSection('request')}
          >
            <div className="space-y-3">
              {llmDetails.messages.map((msg: any, idx: number) => {
                const isMessageExpanded = expandedMessages.has(idx);
                const msgContent = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content, null, 2);
                const hasLongContent = (msgContent?.length || 0) > 300 || (msg.tool_calls?.length || 0) > 0;

                return (
                  <div key={idx} className="bg-background rounded-lg p-3 border border-border/50">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs font-medium px-2 py-0.5 rounded ${msg.role === 'user'
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
                    {msgContent && (
                      <div className={!isMessageExpanded ? 'max-h-32 overflow-hidden' : 'max-h-[400px] overflow-y-auto'}>
                        <pre className="text-sm text-gray-300 whitespace-pre-wrap break-words">
                          {msgContent}
                        </pre>
                      </div>
                    )}
                    {msg.role === 'assistant' && msg.tool_calls && msg.tool_calls.length > 0 && (
                      <div className={`mt-2 space-y-2 ${!isMessageExpanded ? 'max-h-32 overflow-hidden' : 'max-h-[400px] overflow-y-auto'}`}>
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
                            <pre className="text-xs text-gray-400 whitespace-pre-wrap break-words">
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
                    {!isMessageExpanded && hasLongContent && (
                      <button
                        onClick={() => toggleMessage(idx)}
                        className="mt-2 text-xs text-gray-500 hover:text-primary-400 transition-colors"
                      >
                        Click to expand...
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </DetailSection>
        )}

        {/* Tools */}
        {llmDetails.tools && llmDetails.tools.length > 0 && (
          <DetailSection
            title={`Tools (${llmDetails.tools.length})`}
            isExpanded={expandedSections.has('tools')}
            onToggle={() => toggleSection('tools')}
          >
            {expandedSections.has('tools') && (() => {
              const toolsContent = JSON.stringify(llmDetails.tools, null, 2);
              const isContentExpanded = expandedContent.has('tools');
              const hasLongContent = toolsContent.length > 300;

              return (
                <div>
                  <div className={!isContentExpanded ? 'max-h-32 overflow-hidden' : 'max-h-[400px] overflow-y-auto'}>
                    <pre className="text-sm text-gray-300 bg-background rounded-lg p-3 border border-border/50 break-words whitespace-pre-wrap">
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
              );
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
            const isContentExpanded = expandedContent.has('response');

            if (llmDetails.error) {
              const hasLongContent = llmDetails.error.length > 300;
              return (
                <div>
                  <div className={!isContentExpanded ? 'max-h-32 overflow-hidden' : 'max-h-[400px] overflow-y-auto'}>
                    <div className="bg-red-900/20 border border-red-900/50 rounded-lg p-4">
                      <p className="text-sm text-red-400 font-mono break-words">{llmDetails.error}</p>
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
              );
            } else if (llmDetails.response_content) {
              const hasLongContent = llmDetails.response_content.length > 300;
              return (
                <div>
                  <div className={!isContentExpanded ? 'max-h-32 overflow-hidden' : 'max-h-[400px] overflow-y-auto'}>
                    <pre className="text-sm text-gray-300 whitespace-pre-wrap break-words bg-background rounded-lg p-4 border border-border/50">
                      {llmDetails.response_content}
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
              );
            } else {
              return (
                <p className="text-sm text-gray-500 py-4">No response content</p>
              );
            }
          })()}
        </DetailSection>

        {/* Tool Calls */}
        {llmDetails.response_tool_calls && llmDetails.response_tool_calls.length > 0 && (
          <DetailSection
            title={`Tool Calls (${llmDetails.response_tool_calls.length})`}
            isExpanded={expandedSections.has('tool_calls')}
            onToggle={() => toggleSection('tool_calls')}
          >
            {expandedSections.has('tool_calls') && (() => {
              const toolCallsContent = JSON.stringify(llmDetails.response_tool_calls, null, 2);
              const isContentExpanded = expandedContent.has('tool_calls');
              const hasLongContent = toolCallsContent.length > 300;

              return (
                <div>
                  <div className={!isContentExpanded ? 'max-h-32 overflow-hidden' : 'max-h-[400px] overflow-y-auto'}>
                    <pre className="text-sm text-gray-300 bg-background rounded-lg p-3 border border-border/50 break-words whitespace-pre-wrap">
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
              );
            })()}
          </DetailSection>
        )}

        {/* Request Parameters */}
        {llmDetails.request && (
          <DetailSection
            title="Request Parameters"
            isExpanded={expandedSections.has('params')}
            onToggle={() => toggleSection('params')}
          >
            <div>
              <pre className="text-sm text-gray-300 bg-background rounded-lg p-3 border border-border/50 break-words whitespace-pre-wrap">
                {JSON.stringify(llmDetails.request, null, 2)}
              </pre>
            </div>
          </DetailSection>
        )}
      </div>
    </div>
  );
}

function DetailSection({
  title,
  isExpanded,
  onToggle,
  children,
}: {
  title: string;
  isExpanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div>
      <button
        onClick={onToggle}
        className="w-full px-4 py-2.5 flex items-center justify-between text-sm font-medium text-gray-400 hover:text-white transition-colors hover:bg-surfaceHighlight/50 rounded"
      >
        <span className="truncate">{title}</span>
        {isExpanded ? <ChevronDown className="w-4 h-4 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 flex-shrink-0" />}
      </button>
      {isExpanded && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}
