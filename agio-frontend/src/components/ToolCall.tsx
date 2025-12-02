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
        <svg className="w-3.5 h-3.5 animate-spin text-purple-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 12a9 9 0 1 1-6.219-8.56" />
        </svg>
      );
    }
    if (status === 'failed') {
      return (
        <svg className="w-3.5 h-3.5 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
      );
    }
    return (
      <svg className="w-3.5 h-3.5 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    );
  };

  return (
    <div className="my-1">
      {/* Compact header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-1.5 px-2 py-1 rounded hover:bg-white/5 transition-colors text-left group"
      >
        <svg 
          className={`w-3 h-3 text-gray-500 transition-transform ${isOpen ? 'rotate-90' : ''}`} 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2"
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
        
        <StatusIcon />
        
        <span className="font-mono text-xs text-purple-400">{toolName || 'tool'}</span>
        
        {!isOpen && argsSummary && (
          <span className="text-[11px] text-gray-500 truncate max-w-[200px]">
            ({argsSummary})
          </span>
        )}
        
        <span className="flex-1" />
        
        {duration && (
          <span className="text-[10px] text-gray-500 font-mono">
            {formatDuration(duration)}
          </span>
        )}
      </button>

      {/* Expanded details */}
      {isOpen && (
        <div className="ml-5 mt-1 space-y-2 animate-slide-up">
          {/* Input */}
          <div className="rounded border border-border/50 overflow-hidden">
            <div className="px-2 py-0.5 bg-surface/50 border-b border-border/50">
              <span className="text-[10px] uppercase tracking-wider text-gray-500">Input</span>
            </div>
            <pre className="p-2 text-[11px] font-mono text-gray-300 overflow-x-auto bg-black/20 max-h-[200px] overflow-y-auto">
              {formattedArgs}
            </pre>
          </div>
          
          {/* Output */}
          {result && (
            <div className="rounded border border-border/50 overflow-hidden">
              <div className="px-2 py-0.5 bg-surface/50 border-b border-border/50">
                <span className="text-[10px] uppercase tracking-wider text-gray-500">Output</span>
              </div>
              <div className="p-2 text-[11px] text-gray-300 overflow-x-auto bg-black/20 max-h-[300px] overflow-y-auto prose prose-invert prose-sm max-w-none
                prose-pre:bg-black/30 prose-pre:border prose-pre:border-border/30 prose-pre:text-[11px]
                prose-code:text-purple-300 prose-code:bg-black/30 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-[11px]
                prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-li:my-0.5">
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
