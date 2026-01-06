import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, Filter, RefreshCw, Clock, Zap, AlertCircle, CheckCircle, Loader2, X, MessageSquare, Terminal, ChevronRight, BarChart3 } from 'lucide-react';

interface TraceSummary {
  trace_id: string;
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
    setFilters({ agent_id: '', status: '' });
  };

  const hasActiveFilters = Object.values(filters).some((v) => v !== '');

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      ok: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
      error: 'bg-red-500/10 text-red-400 border border-red-500/20',
      running: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
    };
    return colors[status] || 'bg-white/5 text-gray-400 border border-white/10';
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
    if (ms === null) return '-';
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatTime = (timeStr: string) => {
    const date = new Date(timeStr);
    return date.toLocaleString();
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-4">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-200 tracking-tight mb-1 flex items-center gap-2.5">
            <Activity className="w-6 h-6 text-primary-500/80" />
            Traces
          </h1>
          <p className="text-gray-500 text-[13px] font-medium">Monitor execution trajectories, performance metrics, and LLM interactions.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-black tracking-widest transition-all ${
              showFilters || hasActiveFilters
                ? 'bg-primary-500/10 text-primary-400/80 border border-primary-500/20'
                : 'bg-white/5 text-gray-500 hover:text-gray-300 border border-white/5'
            }`}
          >
            <Filter className="w-3.5 h-3.5" />
            FILTERS
            {hasActiveFilters && (
              <span className="bg-primary-500/60 text-white text-[9px] px-1.5 py-0.5 rounded-full font-black">
                {Object.values(filters).filter((v) => v !== '').length}
              </span>
            )}
          </button>
          
          <button
            onClick={() => setShowLLMCallsOnly(!showLLMCallsOnly)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-black tracking-widest transition-all ${
              showLLMCallsOnly
                ? 'bg-emerald-500/10 text-emerald-400/80 border border-emerald-500/20'
                : 'bg-white/5 text-gray-500 hover:text-gray-300 border border-white/5'
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            LLM ONLY
          </button>

          <button
            onClick={() => fetchTraces()}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 border border-white/5 rounded-lg text-[11px] font-black tracking-widest text-gray-500 hover:text-gray-300 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-primary-500/80' : ''}`} />
            REFRESH
          </button>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="bg-white/5 border border-white/5 rounded-2xl p-5 mb-6 animate-in slide-in-from-top-4 duration-300 shadow-xl">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[10px] font-black text-gray-600 uppercase tracking-[0.25em]">FILTER TRAJECTORIES</h3>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="flex items-center gap-1.5 text-[10px] font-black text-primary-500/80 hover:text-primary-400 transition-colors uppercase tracking-widest"
              >
                <X className="w-3 h-3" />
                CLEAR ALL
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="block text-[9px] font-black text-gray-700 uppercase tracking-tighter ml-1">Agent ID</label>
              <div className="relative">
                <BarChart3 className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-700" />
                <input
                  type="text"
                  placeholder="Filter by agent ID..."
                  value={filters.agent_id}
                  onChange={(e) => setFilters({ ...filters, agent_id: e.target.value })}
                  className="w-full pl-9 pr-3 py-2 bg-black/40 border border-white/5 rounded-xl text-[13px] text-gray-300 placeholder-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500/30 transition-all"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="block text-[9px] font-black text-gray-700 uppercase tracking-tighter ml-1">Status</label>
              <div className="relative">
                <Activity className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-700" />
                <select
                  value={filters.status}
                  onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                  className="w-full pl-9 pr-3 py-2 bg-black/40 border border-white/5 rounded-xl text-[13px] text-gray-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500/30 transition-all appearance-none"
                >
                  <option value="">All Statuses</option>
                  <option value="ok">Success (OK)</option>
                  <option value="error">Failed (Error)</option>
                  <option value="running">In Progress</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Traces List */}
      {loading && traces.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 bg-white/5 border border-white/10 border-dashed rounded-3xl">
          <Loader2 className="w-10 h-10 text-primary-500 animate-spin mb-4" />
          <p className="text-gray-500 font-medium tracking-tight">Accessing trace logs...</p>
        </div>
      ) : traces.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 bg-white/5 border border-white/10 border-dashed rounded-3xl text-center px-6">
          <div className="p-6 rounded-full bg-white/5 mb-6">
            <Activity className="w-12 h-12 text-gray-700" />
          </div>
          <h3 className="text-xl font-bold text-gray-300 mb-2">No Traces Detected</h3>
          <p className="text-gray-500 max-w-md mx-auto mb-8">No execution data matches your current filter criteria.</p>
          
          {!hasActiveFilters && (
            <div className="max-w-lg bg-black/40 border border-white/5 rounded-2xl p-6 text-left">
              <div className="flex items-center gap-2 mb-3">
                <Terminal className="w-4 h-4 text-primary-400" />
                <p className="text-xs font-black text-gray-500 uppercase tracking-widest">Setup Instructions</p>
              </div>
              <p className="text-sm text-gray-400 mb-4 leading-relaxed">
                Tracing must be explicitly enabled in your configuration to monitor agent behavior.
              </p>
              <div className="bg-background/50 rounded-xl p-4 font-mono text-[11px] text-primary-300/80 leading-relaxed border border-white/5 overflow-x-auto">
                # configs/observability/trace_store.yaml<br/>
                type: trace_store<br/>
                name: trace_store<br/>
                enabled: true<br/>
                mongo_uri: mongodb://localhost:27017
              </div>
            </div>
          )}
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="px-6 py-2.5 bg-primary-600 text-white text-sm font-black rounded-xl hover:bg-primary-500 transition-all shadow-lg shadow-primary-500/20 active:scale-95"
            >
              CLEAR FILTERS
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {traces
            .filter((trace) => !showLLMCallsOnly || trace.total_llm_calls > 0)
            .map((trace) => (
            <div
              key={trace.trace_id}
              onClick={() => navigate(`/traces/${trace.trace_id}`)}
              className="group relative bg-white/5 border border-white/5 rounded-2xl p-4 hover:border-primary-500/30 hover:bg-white/[0.08] transition-all duration-200 cursor-pointer overflow-hidden shadow-sm"
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
                {/* Left: Identity & Preview */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="px-2 py-0.5 rounded-lg bg-black/40 border border-white/5 font-mono text-[9px] text-gray-600 font-bold tracking-tighter">
                      ID: {trace.trace_id.slice(0, 8)}
                    </div>
                    <div className={`flex items-center gap-1.5 px-2 py-0.5 text-[9px] font-black uppercase tracking-tighter rounded-md ${getStatusColor(trace.status)}`}>
                      {getStatusIcon(trace.status)}
                      {trace.status}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 text-gray-200">
                      <div className="w-7 h-7 rounded-lg bg-primary-500/10 flex items-center justify-center border border-primary-500/20">
                        <Activity className="w-3.5 h-3.5 text-primary-500/80" />
                      </div>
                      <span className="text-sm font-bold tracking-tight uppercase tracking-widest">{trace.agent_id || 'Unknown Agent'}</span>
                    </div>
                    {trace.session_id && (
                      <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/5 text-[9px] text-gray-600 font-mono border border-white/5 font-bold uppercase tracking-tighter">
                        SESSION: {trace.session_id.slice(0, 8)}
                      </div>
                    )}
                  </div>
                  
                  {(trace.input_preview || trace.output_preview) && (
                    <div className="mt-2.5 text-[11px] text-gray-500 line-clamp-1 italic bg-black/20 rounded-lg px-2.5 py-1.5 border border-white/5 border-dashed max-w-2xl leading-relaxed">
                      <span className="text-gray-700 font-black uppercase tracking-widest text-[8px] mr-2">Preview:</span>
                      {trace.input_preview || trace.output_preview}
                    </div>
                  )}
                </div>

                {/* Right: Detailed Metrics */}
                <div className="flex flex-wrap items-center gap-y-3 gap-x-6 shrink-0">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[8px] font-black text-gray-700 uppercase tracking-widest">Duration</span>
                    <div className="flex items-center gap-1.5 text-gray-400">
                      <Clock className="w-3 h-3 text-gray-600" />
                      <span className="text-[13px] font-bold font-mono uppercase tracking-tighter">{formatDuration(trace.duration_ms)}</span>
                    </div>
                  </div>
                  
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[8px] font-black text-gray-700 uppercase tracking-widest">Token Load</span>
                    <div className="flex items-center gap-1.5 text-gray-400">
                      <Zap className="w-3 h-3 text-yellow-500/60" />
                      <span className="text-[13px] font-bold font-mono uppercase tracking-tighter">{trace.total_tokens.toLocaleString()}</span>
                    </div>
                  </div>
                  
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[8px] font-black text-gray-700 uppercase tracking-widest">Call Count (L/T)</span>
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1">
                        <MessageSquare className="w-3 h-3 text-emerald-500/60" />
                        <span className="text-[13px] font-bold text-gray-400 font-mono uppercase tracking-tighter">{trace.total_llm_calls}</span>
                      </div>
                      <span className="text-gray-800 font-black">/</span>
                      <div className="flex items-center gap-1">
                        <Terminal className="w-3 h-3 text-primary-400/60" />
                        <span className="text-[13px] font-bold text-gray-400 font-mono uppercase tracking-tighter">{trace.total_tool_calls}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex flex-col items-end gap-0.5">
                    <span className="text-[8px] font-black text-gray-700 uppercase tracking-widest">Timestamp</span>
                    <div className="text-[11px] text-gray-600 font-bold uppercase tracking-tighter">
                      {formatTime(trace.start_time)}
                    </div>
                  </div>

                  <ChevronRight className="w-4 h-4 text-gray-800 group-hover:text-primary-500/60 group-hover:translate-x-1 transition-all" />
                </div>
              </div>
              
              {/* Background Glow Effect */}
              <div className="absolute -left-20 top-0 w-40 h-full bg-primary-500/5 blur-[50px] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
