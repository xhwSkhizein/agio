import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, Filter, RefreshCw, Clock, Zap, AlertCircle, CheckCircle, Loader2, X, MessageSquare } from 'lucide-react';

interface TraceSummary {
  trace_id: string;
  workflow_id: string | null;
  agent_id: string | null;
  session_id: string | null;
  start_time: string;
  duration_ms: number | null;
  status: string;
  total_tokens: number;
  total_llm_calls: number;
  total_tool_calls: number;
  max_depth: number;
  input_preview: string | null;
  output_preview: string | null;
}

export default function Traces() {
  const navigate = useNavigate();
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [filters, setFilters] = useState({
    workflow_id: '',
    agent_id: '',
    status: '',
  });
  const [showFilters, setShowFilters] = useState(false);
  const [showLLMCallsOnly, setShowLLMCallsOnly] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTraces();
  }, [filters]);

  const fetchTraces = async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.workflow_id) params.set('workflow_id', filters.workflow_id);
    if (filters.agent_id) params.set('agent_id', filters.agent_id);
    if (filters.status) params.set('status', filters.status);

    try {
      const res = await fetch(`/agio/traces?${params}`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data = await res.json();
      setTraces(data);
    } catch (error) {
      console.error('Failed to fetch traces:', error);
      setTraces([]);
    } finally {
      setLoading(false);
    }
  };

  const clearFilters = () => {
    setFilters({ workflow_id: '', agent_id: '', status: '' });
  };

  const hasActiveFilters = Object.values(filters).some((v) => v !== '');

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      ok: 'bg-green-500/20 text-green-400 border border-green-500/50',
      error: 'bg-red-500/20 text-red-400 border border-red-500/50',
      running: 'bg-blue-500/20 text-blue-400 border border-blue-500/50',
    };
    return colors[status] || 'bg-gray-500/20 text-gray-400 border border-gray-500/50';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ok':
        return <CheckCircle className="w-3.5 h-3.5" />;
      case 'error':
        return <AlertCircle className="w-3.5 h-3.5" />;
      case 'running':
        return <Loader2 className="w-3.5 h-3.5 animate-spin" />;
      default:
        return null;
    }
  };

  const formatDuration = (ms: number | null) => {
    if (!ms) return '-';
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatTime = (timeStr: string) => {
    const date = new Date(timeStr);
    return date.toLocaleString();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-white">Traces</h1>
          <p className="mt-1 text-sm text-gray-400">Monitor execution traces and performance metrics</p>
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
            onClick={() => fetchTraces()}
            className="flex items-center gap-2 px-3 py-2 bg-surfaceHighlight rounded-lg text-sm font-medium text-gray-300 hover:text-white transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={() => setShowLLMCallsOnly(!showLLMCallsOnly)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${showLLMCallsOnly
                ? 'bg-primary-500/20 text-primary-400 border border-primary-500/50'
                : 'bg-surfaceHighlight text-gray-300 hover:text-white'
              }`}
          >
            <MessageSquare className="w-4 h-4" />
            LLM Calls Only
          </button>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="bg-surface border border-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-white">Filter Traces</h3>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
              >
                <X className="w-3 h-3" />
                Clear all
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Workflow ID</label>
              <input
                type="text"
                placeholder="Filter by workflow..."
                value={filters.workflow_id}
                onChange={(e) => setFilters({ ...filters, workflow_id: e.target.value })}
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Agent ID</label>
              <input
                type="text"
                placeholder="Filter by agent..."
                value={filters.agent_id}
                onChange={(e) => setFilters({ ...filters, agent_id: e.target.value })}
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Status</label>
              <select
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500"
              >
                <option value="">All Status</option>
                <option value="ok">OK</option>
                <option value="error">Error</option>
                <option value="running">Running</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Traces List */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 bg-surface border border-border rounded-xl">
          <Loader2 className="w-8 h-8 text-primary-400 animate-spin mb-3" />
          <p className="text-sm text-gray-400">Loading traces...</p>
        </div>
      ) : traces.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 bg-surface border border-border rounded-xl">
          <Activity className="w-12 h-12 text-gray-600 mb-3" />
          <p className="text-gray-400 mb-2">No traces found</p>
          {!hasActiveFilters && (
            <div className="mt-4 max-w-md text-center space-y-3">
              <p className="text-sm text-gray-500">
                Trace collection is not enabled. To enable it, add the trace store configuration:
              </p>
              <div className="bg-background border border-border rounded-lg p-3 text-left">
                <code className="text-xs text-gray-300 font-mono">
                  # configs/observability/trace_store.yaml<br/>
                  type: trace_store<br/>
                  name: trace_store<br/>
                  enabled: true<br/>
                  mongo_uri: mongodb://localhost:27017<br/>
                  mongo_db_name: agio
                </code>
              </div>
              <p className="text-xs text-gray-500">
                Restart the application after adding the configuration.
              </p>
            </div>
          )}
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="mt-3 text-sm text-primary-400 hover:text-primary-300 transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-2">
              {traces
                .filter((trace) => !showLLMCallsOnly || trace.total_llm_calls > 0)
                .map((trace) => (
            <div
              key={trace.trace_id}
              onClick={() => navigate(`/traces/${trace.trace_id}`)}
              className="bg-surface border border-border rounded-xl p-4 hover:border-primary-500/50 hover:bg-surfaceHighlight transition-all cursor-pointer group"
            >
              <div className="flex items-start justify-between gap-4">
                {/* Left: Main Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="font-mono text-sm text-gray-400">
                      {trace.trace_id.slice(0, 8)}
                    </span>
                    <span className={`flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-lg ${getStatusColor(trace.status)}`}>
                      {getStatusIcon(trace.status)}
                      {trace.status}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-4 text-sm">
                    <div className="flex items-center gap-1.5 text-white">
                      <Activity className="w-4 h-4 text-primary-400" />
                      <span className="font-medium">{trace.workflow_id || trace.agent_id || 'Unknown'}</span>
                    </div>
                    {trace.session_id && (
                      <span className="text-gray-500 font-mono text-xs">
                        Session: {trace.session_id.slice(0, 8)}
                      </span>
                    )}
                  </div>
                  
                  {(trace.input_preview || trace.output_preview) && (
                    <div className="mt-2 text-xs text-gray-500 line-clamp-1">
                      {trace.input_preview || trace.output_preview}
                    </div>
                  )}
                </div>

                {/* Right: Metrics */}
                <div className="flex items-center gap-6 text-sm">
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-gray-500" />
                    <span className="text-white font-medium">{formatDuration(trace.duration_ms)}</span>
                  </div>
                  
                  <div className="flex items-center gap-1.5">
                    <Zap className="w-4 h-4 text-yellow-500" />
                    <span className="text-white font-medium">{trace.total_tokens.toLocaleString()}</span>
                    <span className="text-gray-500">tokens</span>
                  </div>
                  
                  <div className="flex items-center gap-3 text-gray-400">
                    <div className="flex items-center gap-1">
                      <span className="text-white font-medium">{trace.total_llm_calls}</span>
                      <span className="text-xs">LLM</span>
                    </div>
                    <span className="text-gray-600">/</span>
                    <div className="flex items-center gap-1">
                      <span className="text-white font-medium">{trace.total_tool_calls}</span>
                      <span className="text-xs">Tools</span>
                    </div>
                  </div>
                  
                  <div className="text-xs text-gray-500">
                    {formatTime(trace.start_time)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
