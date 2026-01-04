import { memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface MessageContentProps {
  content: string;
}

// Memoized to prevent unnecessary re-renders during streaming
export const MessageContent = memo(function MessageContent({ content }: MessageContentProps) {
  // Memoize the markdown components to prevent re-creation
  const components = useMemo(() => ({
    // Handle code blocks (inside pre tags)
    pre: ({ children }: any) => {
      // Extract code element props
      const codeElement = children?.props;
      const className = codeElement?.className || '';
      const lang = className.replace('language-', '') || '';
      const codeString = String(codeElement?.children || '').replace(/\n$/, '');

      return (
        <div className="my-2 rounded-lg border border-border bg-surface overflow-hidden">
          {lang && (
            <div className="px-3 py-1 bg-surfaceHighlight border-b border-border text-[10px] text-gray-400 font-mono">
              {lang}
            </div>
          )}
          <SyntaxHighlighter
            style={oneDark}
            language={lang || 'text'}
            PreTag="div"
            customStyle={{
              margin: 0,
              padding: '0.75rem',
              background: '#09090b',
              fontSize: '0.75rem',
              lineHeight: '1.4',
            }}
            codeTagProps={{
              style: {
                background: '#09090b', // 内层 <code> 背景
                padding: '0',          // 可选：避免双重 padding
                margin: 0,
              }
            }}
          >
            {codeString}
          </SyntaxHighlighter>
        </div>
      );
    },
    // Handle inline code
    code: ({ children }: any) => (
      <code className="px-1 py-0.5 rounded bg-surfaceHighlight text-purple-300 text-xs font-mono">
        {children}
      </code>
    ),
    p: ({ children }: any) => <p className="mb-1 last:mb-0 leading-snug">{children}</p>,
    ul: ({ children }: any) => <ul className="list-disc pl-5 mb-1 space-y-0.5">{children}</ul>,
    ol: ({ children }: any) => <ol className="list-decimal pl-5 mb-1 space-y-0.5">{children}</ol>,
    li: ({ children }: any) => <li className="text-gray-300 pl-1">{children}</li>,
    h1: ({ children }: any) => <h1 className="text-lg font-bold mb-1 mt-2 first:mt-0">{children}</h1>,
    h2: ({ children }: any) => <h2 className="text-base font-bold mb-1 mt-1.5 first:mt-0">{children}</h2>,
    h3: ({ children }: any) => <h3 className="text-sm font-bold mb-1 mt-1 first:mt-0">{children}</h3>,
    a: ({ href, children }: any) => (
      <a href={href} className="text-primary-400 hover:underline" target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    ),
    blockquote: ({ children }: any) => (
      <blockquote className="border-l-2 border-gray-600 pl-2 my-1 text-gray-400 italic text-xs">
        {children}
      </blockquote>
    ),
    // Table components with borders and dividers
    table: ({ children }: any) => (
      <div className="my-2 overflow-x-auto">
        <table className="min-w-full border-collapse border border-border">
          {children}
        </table>
      </div>
    ),
    thead: ({ children }: any) => (
      <thead className="bg-surfaceHighlight">
        {children}
      </thead>
    ),
    tbody: ({ children }: any) => (
      <tbody>
        {children}
      </tbody>
    ),
    tr: ({ children }: any) => (
      <tr className="border-b border-border">
        {children}
      </tr>
    ),
    th: ({ children }: any) => (
      <th className="border border-border px-2 py-1 text-left font-semibold text-gray-200 text-xs">
        {children}
      </th>
    ),
    td: ({ children }: any) => (
      <td className="border border-border px-2 py-1 text-gray-300 text-xs">
        {children}
      </td>
    ),
  }), []);

  return (
    <div className="max-w-none text-gray-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
});
