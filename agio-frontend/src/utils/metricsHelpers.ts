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
  return {
    input_tokens: raw.input_tokens ?? raw.prompt_tokens,
    output_tokens: raw.output_tokens ?? raw.completion_tokens,
    total_tokens: raw.total_tokens ?? (
      ((raw.input_tokens ?? raw.prompt_tokens ?? 0) + 
      (raw.output_tokens ?? raw.completion_tokens ?? 0)) || undefined
    ),
    duration_ms: raw.duration_ms,
  }
}

/**
 * Merge metrics from multiple sources (for aggregation).
 */
export function mergeMetrics(base: Metrics, other: Metrics): Metrics {
  return {
    input_tokens: (base.input_tokens ?? 0) + (other.input_tokens ?? 0) || undefined,
    output_tokens: (base.output_tokens ?? 0) + (other.output_tokens ?? 0) || undefined,
    total_tokens: (base.total_tokens ?? 0) + (other.total_tokens ?? 0) || undefined,
    duration_ms: Math.max(base.duration_ms ?? 0, other.duration_ms ?? 0) || undefined,
  }
}
