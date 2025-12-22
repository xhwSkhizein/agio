import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Activity, Clock, MessageSquare, Wrench } from 'lucide-react';
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
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
          onClick={() => setSelectedSpan(null)}
        >
          <div
            className="bg-surface border border-border rounded-xl shadow-2xl p-6 max-w-3xl w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-bold text-white mb-1">
                  {selectedSpan.label}
                </h3>
                {selectedSpan.sublabel && (
                  <p className="text-xs text-gray-400 mb-2">{selectedSpan.sublabel}</p>
                )}
                <div className="flex flex-wrap items-center gap-3 text-xs text-gray-300">
                  <span className="px-2 py-1 rounded bg-primary-500/10 text-primary-300 border border-primary-500/30 capitalize">
                    {selectedSpan.kind.replace('_', ' ')}
                  </span>
                  <span>
                    Duration:{' '}
                    <strong className="text-white">
                      {selectedSpan.duration_ms ? `${selectedSpan.duration_ms.toFixed(0)}ms` : '-'}
                    </strong>
                  </span>
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${getStatusColor(selectedSpan.status)}`}>
                    {selectedSpan.status}
                  </span>
                  {selectedSpan.tokens ? (
                    <span>
                      Tokens:{' '}
                      <strong className="text-white">
                        {selectedSpan.tokens.toLocaleString()}
                      </strong>
                    </span>
                  ) : null}
                </div>
              </div>
              <button
                onClick={() => setSelectedSpan(null)}
                className="text-gray-400 hover:text-white text-sm"
              >
                Close
              </button>
            </div>

            {/* Metrics grid */}
            {selectedSpan.metrics && Object.keys(selectedSpan.metrics).length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-semibold text-white mb-2">Metrics</h4>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs text-gray-200 font-mono">
                  {Object.entries(selectedSpan.metrics).map(([key, value]) => (
                    <div
                      key={key}
                      className="flex flex-col bg-background border border-border rounded-lg px-3 py-2"
                    >
                      <span className="text-[11px] uppercase tracking-wide text-gray-400">
                        {key}
                      </span>
                      <span className="text-sm text-white break-words">
                        {value === null || value === undefined ? '-' : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Error section */}
            {selectedSpan.error_message && (
              <div className="mt-4">
                <span className="text-sm font-medium text-red-400">Error</span>
                <pre className="mt-1 text-sm bg-red-500/10 p-3 rounded-lg border border-red-500/50 text-red-300">
                  {selectedSpan.error_message}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
