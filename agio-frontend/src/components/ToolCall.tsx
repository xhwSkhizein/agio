import { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CheckCircle2, XCircle, ChevronDown } from 'lucide-react';

interface ToolCallProps {
  toolName: string;
  args: string;
  result?: string;
  status: 'running' | 'completed' | 'failed';
  duration?: number;
  icon?: React.ReactNode;
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
      ? keys.slice(0, 5).map(k => {
        const val = parsed[k];
        const valStr = typeof val === 'string'
          ? (val.length > 100 ? val.slice(0, 100) + '...' : val)
          : JSON.stringify(val).slice(0, 100);
        return `${k}: ${valStr}`;
      }).join(', ') + (keys.length > 5 ? ', ...' : '')
      : 'no args';
    return { formatted, summary };
  } catch {
    // If not valid JSON, show raw string
    return { formatted: args, summary: args.length > 100 ? args.slice(0, 100) + '...' : args };
  }
}

// Format duration to human readable
function formatDuration(ms?: number): string {
  if (!ms) return '';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function ToolCall({ toolName, args, result, status, duration, icon }: ToolCallProps) {
  const [isOpen, setIsOpen] = useState(false);

  const { formatted: formattedArgs, summary: argsSummary } = useMemo(
    () => formatArgs(args),
    [args]
  );

  const StatusIcon = () => {
    if (status === 'running') {
      return (
        <div className="w-4 h-4 flex items-center justify-center">
          <div className="w-3 h-3 border-2 border-primary-500/20 border-t-primary-500 rounded-full animate-spin" />
        </div>
      );
    }
    if (status === 'failed') {
      return <XCircle className="w-4 h-4 text-red-500/80" />;
    }
    return <CheckCircle2 className="w-4 h-4 text-emerald-500/80" />;
  };

  return (
    <div className="my-1 group/tool">
      {/* Compact header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full flex items-center gap-3 px-2 py-1.5 rounded-lg transition-all duration-200 text-left ${isOpen
            ? 'bg-white/5 shadow-sm'
            : 'bg-transparent hover:bg-white/[0.03]'
          }`}
      >
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <div className="shrink-0 flex items-center gap-2">
            <StatusIcon />
            {icon && <div className="text-gray-500 shrink-0">{icon}</div>}
          </div>

          <div className="flex items-center gap-3 min-w-0 flex-1">
            <span className="font-mono text-[11px] font-bold text-amber-500/90 tracking-tight uppercase shrink-0">
              {toolName || 'system_call'}
            </span>

            {!isOpen && argsSummary && (
              <span className="text-[11px] text-gray-500/60 truncate font-medium italic flex-1">
                {argsSummary}
              </span>
            )}

            {duration && (
              <span className="text-[9px] text-gray-600 font-mono opacity-50 shrink-0">
                {formatDuration(duration)}
              </span>
            )}
          </div>
        </div>

        <div className={`shrink-0 transition-transform duration-300 ${isOpen ? 'rotate-180 text-gray-400' : 'text-gray-600'}`}>
          <ChevronDown className="w-3.5 h-3.5" />
        </div>
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
