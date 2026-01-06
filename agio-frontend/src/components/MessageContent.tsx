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
        <div className="my-3 rounded-xl border border-white/5 bg-black/40 overflow-hidden shadow-sm">
          {lang && (
            <div className="px-3 py-1 bg-white/5 border-b border-white/5 text-[9px] text-gray-600 font-bold uppercase tracking-[0.2em] font-mono">
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
              background: 'transparent',
              fontSize: '0.75rem',
              lineHeight: '1.5',
            }}
            codeTagProps={{
              style: {
                background: 'transparent',
                padding: '0',
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
      <code className="px-1.5 py-0.5 rounded bg-white/5 text-primary-400/70 text-[0.75rem] font-mono border border-white/5">
        {children}
      </code>
    ),
    p: ({ children }: any) => <p className="mb-1.5 last:mb-0 leading-relaxed text-gray-400">{children}</p>,
    ul: ({ children }: any) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
    ol: ({ children }: any) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
    li: ({ children }: any) => <li className="text-gray-400 pl-0.5">{children}</li>,
    h1: ({ children }: any) => <h1 className="text-lg font-black mb-2 mt-5 first:mt-0 text-gray-200 tracking-tight uppercase">{children}</h1>,
    h2: ({ children }: any) => <h2 className="text-base font-bold mb-1.5 mt-4 first:mt-0 text-gray-200 tracking-tight uppercase">{children}</h2>,
    h3: ({ children }: any) => <h3 className="text-sm font-bold mb-1.5 mt-3 first:mt-0 text-gray-300 tracking-tight uppercase">{children}</h3>,
    a: ({ href, children }: any) => (
      <a href={href} className="text-primary-500/80 hover:text-primary-400 underline decoration-primary-500/20 underline-offset-4 transition-colors" target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    ),
    blockquote: ({ children }: any) => (
      <blockquote className="border-l-2 border-primary-500/20 bg-primary-500/5 rounded-r-lg px-3 py-2 my-3 text-gray-500 italic text-[13px] leading-relaxed">
        {children}
      </blockquote>
    ),
    // Table components with borders and dividers
    table: ({ children }: any) => (
      <div className="my-3 overflow-x-auto rounded-lg border border-white/5">
        <table className="min-w-full border-collapse">
          {children}
        </table>
      </div>
    ),
    thead: ({ children }: any) => (
      <thead className="bg-white/5 border-b border-white/5">
        {children}
      </thead>
    ),
    tbody: ({ children }: any) => (
      <tbody className="bg-black/10">
        {children}
      </tbody>
    ),
    tr: ({ children }: any) => (
      <tr className="border-b border-white/5 last:border-0 hover:bg-white/[0.01] transition-colors">
        {children}
      </tr>
    ),
    th: ({ children }: any) => (
      <th className="px-3 py-2 text-left font-black text-gray-600 text-[9px] uppercase tracking-widest">
        {children}
      </th>
    ),
    td: ({ children }: any) => (
      <td className="px-3 py-2 text-gray-400 text-[13px] leading-relaxed font-medium">
        {children}
      </td>
    ),
  }), []);

  return (
    <div className="max-w-none text-gray-400">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
});
