import { useMemo } from 'react';

interface WaterfallSpan {
  span_id: string;
  parent_span_id: string | null;
  kind: string;
  name: string;
  depth: number;
  start_offset_ms: number;
  duration_ms: number;
  status: string;
  error_message: string | null;
  label: string;
  sublabel: string | null;
  tokens: number | null;
}

interface WaterfallProps {
  spans: WaterfallSpan[];
  totalDuration: number;
  onSpanClick?: (span: WaterfallSpan) => void;
}

const LABEL_WIDTH = 250;
const MIN_BAR_WIDTH = 4;
const TIMELINE_MIN_WIDTH = 600;

const KIND_COLORS: Record<string, string> = {
  workflow: 'bg-purple-500',
  stage: 'bg-blue-500',
  agent: 'bg-green-500',
  llm_call: 'bg-amber-500',
  tool_call: 'bg-cyan-500',
};

const KIND_ICONS: Record<string, string> = {
  workflow: '⚙️',
  stage: '📋',
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

  return (
    <div className="w-full">
      {/* Timeline header */}
      <div className="flex border-b border-border mb-2 pb-2">
        <div style={{ width: LABEL_WIDTH }} className="shrink-0 px-2 py-1 text-sm font-medium text-white">
          Span
        </div>
        <div className="flex-1 relative h-6" style={{ minWidth: TIMELINE_MIN_WIDTH }}>
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

          return (
            <div
              key={span.span_id}
              className={`flex items-center h-10 hover:bg-surfaceHighlight cursor-pointer transition-colors ${
                isError ? 'bg-red-900/20' : ''
              }`}
              onClick={() => onSpanClick?.(span)}
            >
              {/* Label */}
              <div
                style={{
                  width: LABEL_WIDTH,
                  paddingLeft: span.depth * 16 + 8,
                }}
                className="shrink-0 truncate text-sm flex items-center gap-2"
              >
                <span className="text-base">
                  {KIND_ICONS[span.kind] || '●'}
                </span>
                <span className="font-medium text-white">
                  {span.label}
                </span>
                {span.sublabel && (
                  <span className="text-gray-400 text-xs">
                    ({span.sublabel})
                  </span>
                )}
              </div>

              {/* Timeline bar */}
              <div className="flex-1 relative h-full" style={{ minWidth: TIMELINE_MIN_WIDTH }}>
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
