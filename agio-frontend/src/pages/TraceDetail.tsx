import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Activity, Clock, MessageSquare, Wrench, ChevronDown, Zap, Terminal, Hash, X, BarChart3, AlertCircle } from 'lucide-react';
import { Waterfall } from '../components/Waterfall';

interface TraceDetailData {
  trace_id: string;
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
  const [trace, setTrace] = useState<TraceDetailData | null>(null);
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
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="relative">
          <div className="w-12 h-12 border-4 border-primary-500/20 border-t-primary-500 rounded-full animate-spin"></div>
          <Activity className="absolute inset-0 m-auto w-5 h-5 text-primary-500 animate-pulse" />
        </div>
        <p className="mt-4 text-gray-500 font-medium tracking-tight">Reconstructing execution trajectory...</p>
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
      ok: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
      error: 'bg-red-500/10 text-red-400 border border-red-500/20',
      running: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
    };
    return colors[status] || 'bg-white/5 text-gray-400 border border-white/10';
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-4 space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col gap-4">
        <button
          onClick={() => navigate('/traces')}
          className="group flex items-center gap-1.5 text-gray-600 hover:text-gray-300 transition-all w-fit"
        >
          <div className="p-1 rounded-lg bg-white/5 group-hover:bg-white/10 transition-colors">
            <ArrowLeft className="w-3.5 h-3.5" />
          </div>
          <span className="text-[11px] font-black uppercase tracking-[0.2em]">Back to Trajectories</span>
        </button>
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-500/10 flex items-center justify-center border border-primary-500/20 shadow-lg shadow-primary-500/5">
              <Activity className="w-5 h-5 text-primary-500/80" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-200 tracking-tight uppercase tracking-wider">
                {trace.agent_id?.replace(/_/g, ' ') || 'Execution Trace'}
              </h1>
              <div className="flex items-center gap-2 mt-0.5">
                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-black/40 border border-white/5 text-[9px] font-mono text-gray-600 font-bold uppercase tracking-tighter">
                  <Hash className="w-2.5 h-2.5" />
                  {trace.trace_id}
                </div>
                {trace.session_id && (
                  <div className="text-[9px] font-black text-gray-700 uppercase tracking-widest bg-white/5 px-2 py-0.5 rounded-lg border border-white/5">
                    Session: {trace.session_id.slice(0, 8)}
                  </div>
                )}
              </div>
            </div>
          </div>
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest border shadow-xl ${getStatusColor(trace.status)}`}>
            {trace.status === 'ok' ? <Activity className="w-3.5 h-3.5" /> : null}
            {trace.status}
          </div>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'DURATION', value: trace.duration_ms ? `${(trace.duration_ms / 1000).toFixed(2)}s` : '-', icon: Clock, color: 'text-blue-400/80', bg: 'bg-blue-500/5' },
          { label: 'TOTAL TOKENS', value: trace.total_tokens.toLocaleString(), icon: Zap, color: 'text-yellow-400/80', bg: 'bg-yellow-500/5' },
          { label: 'LLM CALLS', value: trace.total_llm_calls, icon: MessageSquare, color: 'text-emerald-400/80', bg: 'bg-emerald-500/5' },
          { label: 'TOOL CALLS', value: trace.total_tool_calls, icon: Wrench, color: 'text-cyan-400/80', bg: 'bg-cyan-500/5' },
        ].map((m, i) => (
          <div key={i} className="bg-white/5 border border-white/5 rounded-2xl p-4 relative overflow-hidden group hover:border-white/10 transition-all">
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-2">
                <div className={`p-1.5 rounded-lg ${m.bg} ${m.color} border border-white/5`}>
                  <m.icon className="w-3 h-3" />
                </div>
                <span className="text-[9px] font-black text-gray-600 uppercase tracking-widest">{m.label}</span>
              </div>
              <p className="text-xl font-bold text-gray-200 tracking-tight font-mono">{m.value}</p>
            </div>
            <m.icon className={`absolute -right-4 -bottom-4 w-16 h-16 opacity-[0.02] ${m.color} group-hover:scale-110 transition-transform duration-500`} />
          </div>
        ))}
      </div>

      {/* Input/Output */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white/5 border border-white/5 rounded-2xl p-5 shadow-sm overflow-hidden relative">
          <div className="flex items-center gap-2 mb-3">
            <Terminal className="w-3.5 h-3.5 text-primary-500/60" />
            <h3 className="text-[10px] font-black text-gray-600 uppercase tracking-[0.25em]">INPUT QUERY</h3>
          </div>
          <pre className="text-[13px] font-mono whitespace-pre-wrap bg-black/40 p-4 rounded-xl border border-white/5 max-h-64 overflow-y-auto text-gray-400 leading-relaxed custom-scrollbar">
            {trace.input_query || 'No input data recorded'}
          </pre>
          <div className="absolute top-0 right-0 p-3 opacity-5 italic text-[9px] text-gray-500 pointer-events-none font-black uppercase tracking-widest">Request</div>
        </div>
        <div className="bg-white/5 border border-white/5 rounded-2xl p-5 shadow-sm overflow-hidden relative">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-3.5 h-3.5 text-emerald-500/60" />
            <h3 className="text-[10px] font-black text-gray-600 uppercase tracking-[0.25em]">FINAL OUTPUT</h3>
          </div>
          <pre className="text-[13px] font-mono whitespace-pre-wrap bg-black/40 p-4 rounded-xl border border-white/5 max-h-64 overflow-y-auto text-gray-400 leading-relaxed custom-scrollbar">
            {trace.final_output || 'No output data generated'}
          </pre>
          <div className="absolute top-0 right-0 p-3 opacity-5 italic text-[9px] text-gray-500 pointer-events-none font-black uppercase tracking-widest">Response</div>
        </div>
      </div>

      {/* Waterfall Chart */}
      <div className="bg-white/5 border border-white/5 rounded-3xl p-6 shadow-2xl relative overflow-hidden">
        <div className="flex items-center justify-between mb-6">
          <div className="flex flex-col gap-0.5">
            <h2 className="text-lg font-bold text-gray-200 tracking-tight uppercase tracking-wider">Execution Timeline</h2>
            <p className="text-[9px] font-black text-gray-700 uppercase tracking-widest">Waterfall visualization of sequential and parallel spans</p>
          </div>
          <div className="flex items-center gap-3 text-[9px] font-black text-gray-700 uppercase tracking-widest">
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-500/60" />
              <span>Runnable</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/60" />
              <span>LLM Call</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-primary-500/60" />
              <span>Tool Call</span>
            </div>
          </div>
        </div>
        
        <div className="bg-black/20 rounded-2xl border border-white/5 p-3 min-h-[400px]">
          <Waterfall
            spans={waterfall.spans}
            totalDuration={waterfall.total_duration_ms}
            onSpanClick={setSelectedSpan}
          />
        </div>
        
        {/* Decorative elements */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary-500/5 blur-[80px] -mr-32 -mt-32 pointer-events-none" />
      </div>

      {/* Span Detail Modal */}
      {selectedSpan && (
        <div
          className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-50 p-6 animate-in fade-in duration-300"
          onClick={() => setSelectedSpan(null)}
        >
          <div
            className="bg-surface border border-white/10 rounded-3xl shadow-2xl flex flex-col max-w-5xl w-full max-h-[90vh] overflow-hidden animate-in zoom-in-95 duration-300"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header - Fixed */}
            <div className="flex items-start justify-between gap-6 p-8 border-b border-white/10 bg-white/5 relative overflow-hidden">
              <div className="flex-1 min-w-0 relative z-10">
                <div className="flex items-center gap-3 mb-2">
                  <span className="px-2.5 py-1 rounded-lg bg-primary-500/20 text-primary-300 border border-primary-500/30 text-[10px] font-black uppercase tracking-widest">
                    {selectedSpan.kind.replace('_', ' ')}
                  </span>
                  <div className={`px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-widest border ${getStatusColor(selectedSpan.status)}`}>
                    {selectedSpan.status}
                  </div>
                </div>
                <h3 className="text-2xl font-bold text-white tracking-tight truncate">
                  {selectedSpan.label}
                </h3>
                <div className="flex flex-wrap items-center gap-6 text-[11px] mt-4 font-bold uppercase tracking-widest text-gray-500">
                  {selectedSpan.duration_ms > 0 && (
                    <div className="flex items-center gap-2">
                      <Clock className="w-3.5 h-3.5 text-blue-400" />
                      <span className="text-gray-300">
                        DURATION: <strong className="text-blue-400">{formatDuration(selectedSpan.duration_ms)}</strong>
                      </span>
                    </div>
                  )}
                  {selectedSpan.tokens && selectedSpan.tokens > 0 && (
                    <div className="flex items-center gap-2">
                      <Zap className="w-3.5 h-3.5 text-yellow-400" />
                      <span className="text-gray-300">
                        TOKEN LOAD: <strong className="text-yellow-400">{selectedSpan.tokens.toLocaleString()}</strong>
                      </span>
                    </div>
                  )}
                </div>
              </div>
              <button
                onClick={() => setSelectedSpan(null)}
                className="text-gray-500 hover:text-white transition-all shrink-0 w-10 h-10 flex items-center justify-center rounded-xl hover:bg-white/10 relative z-10"
                aria-label="Close"
              >
                <X className="w-6 h-6" />
              </button>
              
              <Activity className="absolute -right-8 -bottom-8 w-48 h-48 opacity-[0.02] text-primary-500 pointer-events-none" />
            </div>

            {/* Content - Scrollable */}
            <div className="flex-1 overflow-y-auto p-8 space-y-8 bg-black/20 custom-scrollbar">

              {/* Metrics grid */}
              {selectedSpan.metrics && Object.entries(selectedSpan.metrics).filter(([_, v]) => v !== null).length > 0 && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-primary-400" />
                    <h4 className="text-[10px] font-black text-gray-500 uppercase tracking-[0.2em]">Performance Metrics</h4>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    {Object.entries(selectedSpan.metrics)
                      .filter(([_, value]) => value !== null && value !== undefined)
                      .map(([key, value]) => {
                      let valueColor = 'text-white';
                      if (key.includes('token')) valueColor = 'text-yellow-400';
                      else if (key.includes('duration') || key.includes('latency') || key.includes('time')) valueColor = 'text-blue-400';
                      
                      return (
                        <div
                          key={key}
                          className="flex flex-col bg-white/5 border border-white/5 rounded-xl px-4 py-3 hover:bg-white/[0.08] transition-colors"
                        >
                          <span className="text-[9px] uppercase tracking-widest text-gray-600 mb-1.5 font-black">
                            {key.replace(/\./g, ' ')}
                          </span>
                          <span className={`text-sm font-mono font-medium break-words ${valueColor}`}>
                            {String(value)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Error section */}
              {selectedSpan.error_message && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-red-400">
                    <AlertCircle className="w-4 h-4" />
                    <h4 className="text-[10px] font-black uppercase tracking-[0.2em]">Error Traceback</h4>
                  </div>
                  <pre className="text-xs font-mono bg-red-500/5 p-5 rounded-2xl border border-red-500/20 text-red-300 overflow-x-auto leading-relaxed whitespace-pre-wrap">
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
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  };

  const toggleMessage = (index: number) => {
    setExpandedMessages((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const toggleContent = (contentId: string) => {
    setExpandedContent((prev) => {
      const next = new Set(prev);
      if (next.has(contentId)) next.delete(contentId);
      else next.add(contentId);
      return next;
    });
  };

  return (
    <div className="border-t border-white/10 pt-8 space-y-6">
      <div className="flex items-center gap-2">
        <MessageSquare className="w-4 h-4 text-emerald-400" />
        <h4 className="text-[10px] font-black text-gray-500 uppercase tracking-[0.2em]">LLM Call Detailed Log</h4>
      </div>

      <div className="divide-y divide-white/5 border border-white/10 rounded-3xl bg-black/40 overflow-hidden">
        {/* Request Messages */}
        {llmDetails.messages && llmDetails.messages.length > 0 && (
          <DetailSection
            title={`Request Messages (${llmDetails.messages.length})`}
            isExpanded={expandedSections.has('request')}
            onToggle={() => toggleSection('request')}
          >
            <div className="space-y-4 pt-2">
              {llmDetails.messages.map((msg: any, idx: number) => {
                const isMessageExpanded = expandedMessages.has(idx);
                const msgContent = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content, null, 2);
                const hasLongContent = (msgContent?.length || 0) > 300 || (msg.tool_calls?.length || 0) > 0;

                return (
                  <div key={idx} className="bg-white/5 rounded-2xl p-5 border border-white/5 hover:border-white/10 transition-colors">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <span
                          className={`text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-lg ${msg.role === 'user'
                              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/20'
                              : msg.role === 'assistant'
                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/20'
                                : msg.role === 'system'
                                  ? 'bg-purple-500/20 text-purple-400 border border-purple-500/20'
                                  : msg.role === 'tool'
                                    ? 'bg-orange-500/20 text-orange-400 border border-orange-500/20'
                                    : 'bg-white/5 text-gray-400 border border-white/5'
                            }`}
                        >
                          {msg.role}
                        </span>
                        {msg.tool_call_id && (
                          <span className="text-[10px] font-mono text-gray-600 bg-black/40 px-2 py-0.5 rounded border border-white/5">
                            REF: {msg.tool_call_id}
                          </span>
                        )}
                      </div>
                      {hasLongContent && (
                        <button
                          onClick={() => toggleMessage(idx)}
                          className="text-[10px] font-black text-gray-500 hover:text-white transition-colors"
                        >
                          {isMessageExpanded ? 'COLLAPSE' : 'EXPAND'}
                        </button>
                      )}
                    </div>
                    {msgContent && (
                      <div className={`font-mono text-xs text-gray-300 leading-relaxed ${!isMessageExpanded ? 'max-h-32 overflow-hidden' : ''}`}>
                        <pre className="whitespace-pre-wrap break-words">{msgContent}</pre>
                      </div>
                    )}
                    {msg.role === 'assistant' && msg.tool_calls && msg.tool_calls.length > 0 && (
                      <div className={`mt-4 space-y-3 ${!isMessageExpanded ? 'max-h-32 overflow-hidden' : ''}`}>
                        <div className="text-[9px] font-black text-gray-600 uppercase tracking-[0.2em] mb-2">Proposed Tool Calls ({msg.tool_calls.length})</div>
                        {msg.tool_calls.map((tc: any, tcIdx: number) => (
                          <div key={tcIdx} className="bg-black/40 rounded-xl p-4 border border-white/5">
                            <div className="flex items-center gap-2 mb-2">
                              <Terminal className="w-3 h-3 text-orange-400" />
                              <span className="text-xs font-bold text-orange-400/90">
                                {tc.function?.name || tc.name || 'unknown_tool'}
                              </span>
                              {tc.id && (
                                <span className="text-[10px] font-mono text-gray-600 ml-auto">ID: {tc.id}</span>
                              )}
                            </div>
                            <pre className="text-[11px] text-gray-500 font-mono whitespace-pre-wrap break-words leading-relaxed">
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
                        className="mt-4 text-[10px] font-black text-primary-500 hover:text-primary-400 transition-colors"
                      >
                        READ COMPLETE MESSAGE...
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
            title={`Available Tools (${llmDetails.tools.length})`}
            isExpanded={expandedSections.has('tools')}
            onToggle={() => toggleSection('tools')}
          >
            <div className="pt-2">
              <div className={`bg-black/40 rounded-2xl border border-white/5 p-5 ${!expandedContent.has('tools') ? 'max-h-48 overflow-hidden' : ''}`}>
                <pre className="text-[11px] font-mono text-gray-500 leading-relaxed break-words whitespace-pre-wrap">
                  {JSON.stringify(llmDetails.tools, null, 2)}
                </pre>
              </div>
              <button
                onClick={() => toggleContent('tools')}
                className="mt-3 text-[10px] font-black text-primary-500 hover:text-primary-400 transition-colors"
              >
                {expandedContent.has('tools') ? 'SHOW LESS' : 'SHOW COMPLETE TOOLSET'}
              </button>
            </div>
          </DetailSection>
        )}

        {/* Response */}
        <DetailSection
          title="Raw Response"
          isExpanded={expandedSections.has('response')}
          onToggle={() => toggleSection('response')}
        >
          <div className="pt-2">
            {llmDetails.error ? (
              <div className="bg-red-500/5 border border-red-500/20 rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-3 text-red-400">
                  <AlertCircle className="w-4 h-4" />
                  <span className="text-[10px] font-black uppercase tracking-widest">Error Log</span>
                </div>
                <p className="text-xs text-red-300 font-mono leading-relaxed break-words">{llmDetails.error}</p>
              </div>
            ) : llmDetails.response_content ? (
              <>
                <div className={`bg-black/40 rounded-2xl border border-white/5 p-6 ${!expandedContent.has('response') ? 'max-h-64 overflow-hidden' : ''}`}>
                  <pre className="text-xs text-gray-300 font-mono leading-relaxed whitespace-pre-wrap break-words">
                    {llmDetails.response_content}
                  </pre>
                </div>
                {(llmDetails.response_content.length > 300) && (
                  <button
                    onClick={() => toggleContent('response')}
                    className="mt-3 text-[10px] font-black text-primary-500 hover:text-primary-400 transition-colors"
                  >
                    {expandedContent.has('response') ? 'REDUCE VIEW' : 'EXPAND COMPLETE RESPONSE'}
                  </button>
                )}
              </>
            ) : (
              <div className="py-8 text-center bg-white/5 rounded-2xl border border-dashed border-white/10">
                <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest">No response content available</p>
              </div>
            )}
          </div>
        </DetailSection>

        {/* Tool Calls */}
        {llmDetails.response_tool_calls && llmDetails.response_tool_calls.length > 0 && (
          <DetailSection
            title={`Extracted Tool Calls (${llmDetails.response_tool_calls.length})`}
            isExpanded={expandedSections.has('tool_calls')}
            onToggle={() => toggleSection('tool_calls')}
          >
            <div className="pt-2">
              <div className={`bg-black/40 rounded-2xl border border-white/5 p-5 ${!expandedContent.has('tool_calls') ? 'max-h-48 overflow-hidden' : ''}`}>
                <pre className="text-[11px] font-mono text-primary-400/80 leading-relaxed break-words whitespace-pre-wrap">
                  {JSON.stringify(llmDetails.response_tool_calls, null, 2)}
                </pre>
              </div>
              <button
                onClick={() => toggleContent('tool_calls')}
                className="mt-3 text-[10px] font-black text-primary-500 hover:text-primary-400 transition-colors"
              >
                {expandedContent.has('tool_calls') ? 'SHOW LESS' : 'SHOW ALL TOOL CALLS'}
              </button>
            </div>
          </DetailSection>
        )}

        {/* Request Parameters */}
        {llmDetails.request && (
          <DetailSection
            title="Engine Configuration"
            isExpanded={expandedSections.has('params')}
            onToggle={() => toggleSection('params')}
          >
            <div className="pt-2">
              <div className="bg-black/40 rounded-2xl border border-white/5 p-5">
                <pre className="text-[11px] font-mono text-gray-500 leading-relaxed break-words whitespace-pre-wrap">
                  {JSON.stringify(llmDetails.request, null, 2)}
                </pre>
              </div>
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
    <div className="transition-all">
      <button
        onClick={onToggle}
        className="w-full px-6 py-4 flex items-center justify-between text-[11px] font-black text-gray-500 hover:text-white uppercase tracking-[0.2em] transition-all hover:bg-white/5 group"
      >
        <span className="truncate">{title}</span>
        <div className={`p-1 rounded-lg group-hover:bg-white/10 transition-all ${isExpanded ? 'rotate-180 text-primary-400' : ''}`}>
          <ChevronDown className="w-4 h-4 flex-shrink-0" />
        </div>
      </button>
      {isExpanded && <div className="px-6 pb-6 animate-in slide-in-from-top-2 duration-300">{children}</div>}
    </div>
  );
}
