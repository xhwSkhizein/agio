/**
 * Metrics helper functions for unified metrics reading
 */

export interface Metrics {
  input_tokens?: number
  output_tokens?: number
  total_tokens?: number
  duration_ms?: number
  prompt_tokens?: number
  completion_tokens?: number
}

interface SSEEventData {
  snapshot?: {
    metrics?: Metrics
  }
  data?: {
    metrics?: Metrics
  }
}

/**
 * Unified metrics extraction from SSE event data.
 * 
 * Priority:
 * 1. snapshot.metrics (step-level metrics)
 * 2. data.metrics (run-level metrics)
 */
export function getEventMetrics(event: SSEEventData): Metrics | undefined {
  // Priority 1: snapshot.metrics (step-level)
  if (event.snapshot?.metrics) {
    return normalizeMetrics(event.snapshot.metrics)
  }
  
  // Priority 2: data.metrics (run-level)
  if (event.data?.metrics) {
    return normalizeMetrics(event.data.metrics)
  }
  
  return undefined
}

/**
 * Normalize metrics to a consistent format.
 * Handles both OpenAI style (prompt_tokens) and unified style (input_tokens).
 */
function normalizeMetrics(raw: Metrics): Metrics {
  const inputTokens = raw.input_tokens ?? raw.prompt_tokens
  const outputTokens = raw.output_tokens ?? raw.completion_tokens

  return {
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    total_tokens: raw.total_tokens ?? (
      inputTokens !== undefined && outputTokens !== undefined
        ? inputTokens + outputTokens
        : undefined
    ),
    duration_ms: raw.duration_ms,
  }
}

/**
 * Merge metrics from multiple sources (for aggregation).
 * Preserves zero values as valid metrics (doesn't convert to undefined).
 */
export function mergeMetrics(base: Metrics, other: Metrics): Metrics {
  const sumOrUndefined = (a: number | undefined, b: number | undefined): number | undefined => {
    if (a === undefined && b === undefined) return undefined
    return (a ?? 0) + (b ?? 0)
  }

  const maxOrUndefined = (a: number | undefined, b: number | undefined): number | undefined => {
    if (a === undefined && b === undefined) return undefined
    return Math.max(a ?? 0, b ?? 0)
  }

  return {
    input_tokens: sumOrUndefined(base.input_tokens, other.input_tokens),
    output_tokens: sumOrUndefined(base.output_tokens, other.output_tokens),
    total_tokens: sumOrUndefined(base.total_tokens, other.total_tokens),
    duration_ms: maxOrUndefined(base.duration_ms, other.duration_ms),
  }
}
