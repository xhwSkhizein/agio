import { useMemo } from 'react';

export interface WaterfallSpan {
  span_id: string;
  parent_span_id: string | null;
  kind: string;
  name: string;
  depth: number;
  start_offset_ms: number;
  duration_ms: number;
  status: string;
  error_message: string | null;

  // Display info
  label: string;
  sublabel: string | null;
  tokens: number | null;
  metrics?: Record<string, any>;
  llm_details?: Record<string, any>; // Complete LLM call details (for LLM_CALL spans)
}

interface WaterfallProps {
  spans: WaterfallSpan[];
  totalDuration: number;
  onSpanClick?: (span: WaterfallSpan) => void;
}

const LABEL_MIN_WIDTH = 200;
const LABEL_MAX_WIDTH = 400;
const MIN_BAR_WIDTH = 4;
const TIMELINE_MIN_WIDTH = 600;

const KIND_COLORS: Record<string, string> = {
  agent: 'bg-green-500',
  llm_call: 'bg-amber-500',
  tool_call: 'bg-orange-500',
};

const KIND_ICONS: Record<string, string> = {
  agent: '🤖',
  llm_call: '💬',
  tool_call: '🔧',
};

export function Waterfall({ spans, totalDuration, onSpanClick }: WaterfallProps) {
  // Build tree structure and flatten in display order
  const sortedSpans = useMemo(() => {
    // Build parent-child map
    const childrenMap = new Map<string | null, WaterfallSpan[]>();
    spans.forEach(span => {
      const parentId = span.parent_span_id;
      if (!childrenMap.has(parentId)) {
        childrenMap.set(parentId, []);
      }
      childrenMap.get(parentId)!.push(span);
    });
    
    // Sort children by start time
    childrenMap.forEach(children => {
      children.sort((a, b) => a.start_offset_ms - b.start_offset_ms);
    });
    
    // Flatten tree in DFS order
    const result: WaterfallSpan[] = [];
    const visit = (spanId: string | null) => {
      const children = childrenMap.get(spanId) || [];
      children.forEach(child => {
        result.push(child);
        visit(child.span_id);
      });
    };
    visit(null); // Start from root spans
    
    return result;
  }, [spans]);

  const formatDuration = (ms: number) => {
    if (ms < 1) return '<1ms';
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const timeMarkers = [0, 0.25, 0.5, 0.75, 1];

  const formatTokens = (count: number | null | undefined): string => {
    if (count === null || count === undefined) return '';
    if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
    return count.toString();
  };

  const getPrimaryInfo = (span: WaterfallSpan): { text: string; type: 'tokens' | 'duration' | null } => {
    // For LLM calls, prioritize tokens
    if (span.kind === 'llm_call') {
      const tokensTotal = span.tokens ?? span.metrics?.["tokens.total"] ?? span.metrics?.["total_tokens"];
      if (tokensTotal !== null && tokensTotal !== undefined && tokensTotal > 0) {
        const formatted = formatTokens(tokensTotal);
        return { text: `${formatted} tokens`, type: 'tokens' };
      }
      // Fallback to duration if no tokens
      if (span.duration_ms > 0) {
        return { text: formatDuration(span.duration_ms), type: 'duration' };
      }
    }
    
    // For tool calls, prioritize execution time
    if (span.kind === 'tool_call') {
      const toolExec = span.metrics?.["tool.exec_time_ms"];
      if (toolExec !== null && toolExec !== undefined && toolExec > 0) {
        return { text: formatDuration(toolExec), type: 'duration' };
      }
      // Fallback to duration_ms
      if (span.duration_ms > 0) {
        return { text: formatDuration(span.duration_ms), type: 'duration' };
      }
    }
    
    // For other types, use duration if available
    if (span.duration_ms > 0) {
      return { text: formatDuration(span.duration_ms), type: 'duration' };
    }
    
    return { text: '', type: null };
  };

  const getSecondaryInfo = (span: WaterfallSpan): string[] => {
    const info: string[] = [];
    
    if (span.kind === 'llm_call') {
      const firstToken = span.metrics?.["first_token_ms"];
      if (firstToken !== null && firstToken !== undefined) {
        info.push(`TTFT: ${formatDuration(firstToken)}`);
      }
    }
    
    if (span.kind === 'tool_call') {
      const toolExec = span.metrics?.["tool.exec_time_ms"];
      if (toolExec !== null && toolExec !== undefined && span.duration_ms !== toolExec) {
        info.push(`Total: ${formatDuration(span.duration_ms)}`);
      }
    }
    
    return info;
  };

  return (
    <div className="w-full">
      {/* Timeline header */}
      <div className="flex border-b border-border mb-2 pb-2 overflow-x-auto">
        <div 
          style={{ minWidth: LABEL_MIN_WIDTH, maxWidth: LABEL_MAX_WIDTH }} 
          className="shrink-0 px-2 py-1 text-sm font-medium text-white"
        >
          Span
        </div>
        <div className="flex-1 relative h-6 shrink-0" style={{ minWidth: TIMELINE_MIN_WIDTH }}>
          {timeMarkers.map((pct) => (
            <div
              key={pct}
              className="absolute top-0 h-full border-l border-border"
              style={{ left: `${pct * 100}%` }}
            >
              <span className="text-xs text-gray-500 ml-1">
                {formatDuration(totalDuration * pct)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Spans */}
      <div className="relative overflow-x-auto">
        {sortedSpans.map((span) => {
          const leftPct = (span.start_offset_ms / totalDuration) * 100;
          const widthPct = Math.max(
            (span.duration_ms / totalDuration) * 100,
            (MIN_BAR_WIDTH / 800) * 100
          );

          const isError = span.status === 'error';

          const primaryInfo = getPrimaryInfo(span);
          const secondaryInfo = getSecondaryInfo(span);

          return (
            <div
              key={span.span_id}
              className={`flex items-center min-h-[3rem] py-1 hover:bg-surfaceHighlight cursor-pointer transition-colors ${
                isError ? 'bg-red-900/20' : ''
              }`}
              onClick={() => onSpanClick?.(span)}
            >
              {/* Label */}
              <div
                style={{
                  minWidth: LABEL_MIN_WIDTH,
                  maxWidth: LABEL_MAX_WIDTH,
                  paddingLeft: span.depth * 16 + 8,
                }}
                className="shrink-0 px-2 flex flex-col gap-0.5"
              >
                {/* Main label row */}
                <div className="flex items-center gap-2">
                  <span className="text-base shrink-0">
                    {KIND_ICONS[span.kind] || '●'}
                  </span>
                  <span 
                    className="font-medium text-white truncate text-sm" 
                    title={span.label}
                  >
                    {span.label}
                  </span>
                </div>
                
                {/* Secondary info row */}
                {(primaryInfo.text || secondaryInfo.length > 0) && (
                  <div className="flex items-center gap-2 ml-6 text-xs">
                    {primaryInfo.text && (
                      <span className={`font-medium ${
                        primaryInfo.type === 'tokens' ? 'text-yellow-400' : 'text-blue-400'
                      }`}>
                        {primaryInfo.text}
                      </span>
                    )}
                    {secondaryInfo.length > 0 && (
                      <>
                        {primaryInfo.text && <span className="text-gray-600 mx-1">•</span>}
                        <span className="text-gray-500">
                          {secondaryInfo.join(' • ')}
                        </span>
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Timeline bar */}
              <div className="flex-1 relative h-full shrink-0" style={{ minWidth: TIMELINE_MIN_WIDTH }}>
                <div
                  className={`absolute top-1/2 -translate-y-1/2 h-5 rounded shadow-sm ${
                    KIND_COLORS[span.kind] || 'bg-gray-400'
                  } ${isError ? '!bg-red-500' : ''}`}
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    minWidth: MIN_BAR_WIDTH,
                  }}
                >
                  {/* Duration label on bar */}
                  {widthPct > 8 && (
                    <span className="absolute inset-0 flex items-center justify-center text-xs text-white font-medium">
                      {formatDuration(span.duration_ms)}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="mt-6 flex flex-wrap gap-4 text-sm text-gray-400">
        {Object.entries(KIND_ICONS).map(([kind, icon]) => (
          <div key={kind} className="flex items-center gap-2">
            <span>{icon}</span>
            <span className="capitalize">{kind.replace('_', ' ')}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
