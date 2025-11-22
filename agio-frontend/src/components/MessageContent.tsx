import React from 'react';

interface MessageContentProps {
  content: string;
}

export function MessageContent({ content }: MessageContentProps) {
  // Simple parser to split code blocks
  const parts = content.split(/(```[\s\S]*?```)/g);

  return (
    <div className="prose max-w-none text-gray-300">
      {parts.map((part, index) => {
        if (part.startsWith('```')) {
          // Code block
          const match = part.match(/```(\w*)\n([\s\S]*?)```/);
          const lang = match ? match[1] : '';
          const code = match ? match[2] : part.slice(3, -3);
          
          return (
            <div key={index} className="my-4 rounded-lg border border-border bg-surface overflow-hidden">
              {lang && (
                <div className="px-4 py-1 bg-surfaceHighlight border-b border-border text-xs text-gray-400 font-mono">
                  {lang}
                </div>
              )}
              <pre className="p-4 overflow-x-auto text-sm font-mono text-gray-200 bg-transparent m-0 border-0">
                <code>{code}</code>
              </pre>
            </div>
          );
        }
        
        // Regular text
        if (!part.trim()) return null;
        
        return (
          <div key={index} className="whitespace-pre-wrap mb-2">
            {part}
          </div>
        );
      })}
    </div>
  );
}
