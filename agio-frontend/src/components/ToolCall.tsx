import React, { useState } from 'react';

interface ToolCallProps {
  toolName: string;
  args: string;
  result?: string;
  status: 'running' | 'completed' | 'failed';
  duration?: number;
}

export function ToolCall({ toolName, args, result, status, duration }: ToolCallProps) {
  const [isOpen, setIsOpen] = useState(status === 'running');

  // Icons
  const ChevronRight = () => (
    <svg className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-90' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );

  const ToolIcon = () => (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </svg>
  );

  const StatusIcon = () => {
    if (status === 'running') {
      return (
        <svg className="w-4 h-4 animate-spin text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 12a9 9 0 1 1-6.219-8.56" />
        </svg>
      );
    }
    if (status === 'failed') {
      return (
        <svg className="w-4 h-4 text-error" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      );
    }
    return (
      <svg className="w-4 h-4 text-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    );
  };

  return (
    <div className="border border-border rounded-md bg-surface overflow-hidden my-2 text-sm">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-surfaceHighlight transition-colors text-left"
      >
        <span className="text-gray-500"><ChevronRight /></span>
        <span className="text-purple-400"><ToolIcon /></span>
        <span className="font-mono font-medium text-gray-200">{toolName}</span>
        <span className="flex-1" />
        {duration && <span className="text-xs text-gray-500">{duration.toFixed(2)}s</span>}
        <StatusIcon />
      </button>

      {isOpen && (
        <div className="border-t border-border bg-black/20 p-3 font-mono text-xs space-y-3 animate-slide-up">
          <div>
            <div className="text-gray-500 mb-1 uppercase tracking-wider text-[10px]">Input</div>
            <div className="bg-surfaceHighlight rounded p-2 overflow-x-auto text-gray-300">
              {args}
            </div>
          </div>
          {result && (
            <div>
              <div className="text-gray-500 mb-1 uppercase tracking-wider text-[10px]">Output</div>
              <div className="bg-surfaceHighlight rounded p-2 overflow-x-auto text-gray-300">
                {result}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
