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
      <div className="my-3 rounded-lg border border-border bg-surface overflow-hidden">
        <pre className="p-3 overflow-x-auto text-sm font-mono text-gray-200 bg-transparent m-0 border-0">
          {children}
        </pre>
      </div>
    ),
    code: ({ inline, className, children }: any) => {
      if (inline) {
        return (
          <code className="px-1.5 py-0.5 rounded bg-surfaceHighlight text-purple-300 text-sm font-mono">
            {children}
          </code>
        );
      }
      const lang = className?.replace('language-', '') || '';
      return (
        <>
          {lang && (
            <div className="px-3 py-1 bg-surfaceHighlight border-b border-border text-xs text-gray-400 font-mono -mt-3 -mx-3 mb-3">
              {lang}
            </div>
          )}
          <code className="text-gray-200">{children}</code>
        </>
      );
    },
    p: ({ children }: any) => <p className="mb-2 last:mb-0">{children}</p>,
    ul: ({ children }: any) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
    ol: ({ children }: any) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
    li: ({ children }: any) => <li className="text-gray-300">{children}</li>,
    h1: ({ children }: any) => <h1 className="text-xl font-bold mb-2 mt-4 first:mt-0">{children}</h1>,
    h2: ({ children }: any) => <h2 className="text-lg font-bold mb-2 mt-3 first:mt-0">{children}</h2>,
    h3: ({ children }: any) => <h3 className="text-base font-bold mb-2 mt-2 first:mt-0">{children}</h3>,
    a: ({ href, children }: any) => (
      <a href={href} className="text-primary-400 hover:underline" target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    ),
    blockquote: ({ children }: any) => (
      <blockquote className="border-l-2 border-gray-600 pl-3 my-2 text-gray-400 italic">
        {children}
      </blockquote>
    ),
  }), []);

  return (
    <div className="prose prose-invert max-w-none text-gray-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
});
