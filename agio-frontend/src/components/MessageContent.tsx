import { memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MessageContentProps {
  content: string;
}

// Memoized to prevent unnecessary re-renders during streaming
export const MessageContent = memo(function MessageContent({ content }: MessageContentProps) {
  // Memoize the markdown components to prevent re-creation
  const components = useMemo(() => ({
    pre: ({ children }: any) => (
      <div className="my-2 rounded-lg border border-border bg-surface overflow-hidden">
        <pre className="p-2 overflow-x-auto text-xs font-mono text-gray-200 bg-transparent m-0 border-0">
          {children}
        </pre>
      </div>
    ),
    code: ({ inline, className, children }: any) => {
      if (inline) {
        return (
          <code className="px-1 py-0.5 rounded bg-surfaceHighlight text-purple-300 text-xs font-mono">
            {children}
          </code>
        );
      }
      const lang = className?.replace('language-', '') || '';
      return (
        <>
          {lang && (
            <div className="px-2 py-0.5 bg-surfaceHighlight border-b border-border text-[10px] text-gray-400 font-mono -mt-2 -mx-2 mb-2">
              {lang}
            </div>
          )}
          <code className="text-gray-200">{children}</code>
        </>
      );
    },
    p: ({ children }: any) => <p className="mb-1.5 last:mb-0">{children}</p>,
    ul: ({ children }: any) => <ul className="list-disc list-inside mb-1.5 space-y-0.5">{children}</ul>,
    ol: ({ children }: any) => <ol className="list-decimal list-inside mb-1.5 space-y-0.5">{children}</ol>,
    li: ({ children }: any) => <li className="text-gray-300">{children}</li>,
    h1: ({ children }: any) => <h1 className="text-lg font-bold mb-1.5 mt-3 first:mt-0">{children}</h1>,
    h2: ({ children }: any) => <h2 className="text-base font-bold mb-1.5 mt-2 first:mt-0">{children}</h2>,
    h3: ({ children }: any) => <h3 className="text-sm font-bold mb-1.5 mt-1.5 first:mt-0">{children}</h3>,
    a: ({ href, children }: any) => (
      <a href={href} className="text-primary-400 hover:underline" target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    ),
    blockquote: ({ children }: any) => (
      <blockquote className="border-l-2 border-gray-600 pl-2 my-1.5 text-gray-400 italic text-xs">
        {children}
      </blockquote>
    ),
  }), []);

  return (
    <div className="prose prose-invert prose-sm max-w-none text-gray-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
});
