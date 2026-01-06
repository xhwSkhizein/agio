import { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ToolCallProps {
  toolName: string;
  args: string;
  result?: string;
  status: 'running' | 'completed' | 'failed';
  duration?: number;
}

// Format JSON for display
function formatArgs(args: string): { formatted: string; summary: string } {
  // Handle empty or whitespace-only args
  if (!args || !args.trim()) {
    return { formatted: '{}', summary: 'no args' };
  }
  
  try {
    const parsed = JSON.parse(args);
    const formatted = JSON.stringify(parsed, null, 2);
    // Create a short summary of args
    const keys = Object.keys(parsed);
    const summary = keys.length > 0 
      ? keys.slice(0, 3).map(k => {
          const val = parsed[k];
          const valStr = typeof val === 'string' 
            ? (val.length > 20 ? val.slice(0, 20) + '...' : val)
            : JSON.stringify(val).slice(0, 20);
          return `${k}: ${valStr}`;
        }).join(', ') + (keys.length > 3 ? ', ...' : '')
      : 'no args';
    return { formatted, summary };
  } catch {
    // If not valid JSON, show raw string
    return { formatted: args, summary: args.length > 50 ? args.slice(0, 50) + '...' : args };
  }
}

// Format duration to human readable
function formatDuration(ms?: number): string {
  if (!ms) return '';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function ToolCall({ toolName, args, result, status, duration }: ToolCallProps) {
  const [isOpen, setIsOpen] = useState(false);
  
  const { formatted: formattedArgs, summary: argsSummary } = useMemo(
    () => formatArgs(args),
    [args]
  );

  const StatusIcon = () => {
    if (status === 'running') {
      return (
        <div className="relative">
          <div className="w-3.5 h-3.5 border-2 border-primary-500/20 border-t-primary-500 rounded-full animate-spin" />
          <div className="absolute inset-0 m-auto w-1 h-1 bg-primary-500 rounded-full animate-pulse" />
        </div>
      );
    }
    if (status === 'failed') {
      return (
        <div className="p-0.5 rounded-md bg-red-500/20 text-red-400 border border-red-500/30">
          <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="4">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </div>
      );
    }
    return (
      <div className="p-0.5 rounded-md bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
        <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="4">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
    );
  };

  return (
    <div className="my-1.5 group/tool">
      {/* Compact header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg transition-all duration-200 text-left border ${
          isOpen 
            ? 'bg-white/5 border-white/10 shadow-inner' 
            : 'bg-transparent border-transparent hover:bg-white/[0.03]'
        }`}
      >
        <div className={`p-0.5 rounded transition-colors ${isOpen ? 'bg-white/10 text-white' : 'text-gray-600 group-hover/tool:text-gray-500'}`}>
          <svg 
            className={`w-2.5 h-2.5 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`} 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="3"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
        
        <StatusIcon />
        
        <div className="flex flex-col">
          <span className="font-mono text-[11px] font-black text-primary-500/70 tracking-tight uppercase">{toolName || 'system_call'}</span>
          {!isOpen && argsSummary && (
            <span className="text-[9px] text-gray-600 truncate max-w-[360px] font-medium italic">
              payload: {argsSummary}
            </span>
          )}
        </div>
        
        <div className="flex-1" />
        
        {duration && (
          <div className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md bg-black/20 border border-white/5 text-[8px] text-gray-600 font-black tracking-widest font-mono">
            {formatDuration(duration)}
          </div>
        )}
      </button>

      {/* Expanded details */}
      {isOpen && (
        <div className="ml-3 mt-1.5 space-y-2.5 animate-in slide-in-from-top-2 duration-300">
          {/* Input */}
          <div className="rounded-xl border border-white/5 bg-black/20 overflow-hidden">
            <div className="px-3 py-1 bg-white/5 border-b border-white/5 flex items-center justify-between">
              <span className="text-[8px] font-black uppercase tracking-[0.2em] text-gray-600">Input Specification</span>
              <div className="w-1 h-1 rounded-full bg-primary-500/30" />
            </div>
            <pre className="p-3 text-[10px] font-mono text-gray-500 overflow-x-auto leading-relaxed custom-scrollbar max-h-[240px]">
              {formattedArgs}
            </pre>
          </div>
          
          {/* Output */}
          {result && (
            <div className="rounded-xl border border-white/5 bg-black/20 overflow-hidden">
              <div className="px-3 py-1 bg-white/5 border-b border-white/5 flex items-center justify-between">
                <span className="text-[8px] font-black uppercase tracking-[0.2em] text-gray-600">Execution Result</span>
                <div className="w-1 h-1 rounded-full bg-emerald-500/30" />
              </div>
              <div className="p-3 text-[10px] text-gray-400 overflow-x-auto prose prose-invert prose-sm max-w-none
                prose-pre:bg-black/40 prose-pre:border prose-pre:border-white/5 prose-pre:text-[10px] prose-pre:rounded-lg
                prose-code:text-primary-400/70 prose-code:bg-white/5 prose-code:px-1 prose-code:py-0.5 prose-code:rounded-md prose-code:text-[10px]
                prose-p:my-0.5 prose-headings:my-1.5 prose-ul:my-0.5 prose-li:my-0.5 leading-relaxed custom-scrollbar max-h-[400px]">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {result}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
