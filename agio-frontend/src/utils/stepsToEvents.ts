/**
 * Utility to convert backend Step data to frontend TimelineEvent format.
 * 
 * This module handles the mapping between backend conversation steps and
 * frontend timeline display events, with special handling for tool calls.
 */

/**
 * Frontend timeline event structure for display.
 */
export interface TimelineEvent {
  id: string
  type: 'user' | 'assistant' | 'tool' | 'error'
  content?: string
  toolName?: string
  toolArgs?: string
  toolResult?: string
  toolStatus?: 'running' | 'completed' | 'failed'
  toolDuration?: number
  timestamp: number
  metrics?: {
    input_tokens?: number
    output_tokens?: number
    total_tokens?: number
    duration_ms?: number
  }
}

/**
 * Backend Step structure from /sessions/{id}/steps API.
 * 
 * Different roles have different fields:
 * - user: { role: 'user', content: string }
 * - assistant: { role: 'assistant', content?: string, tool_calls?: ToolCall[] }
 * - tool: { role: 'tool', name: string, tool_call_id: string, content: string }
 */
export interface BackendStep {
  id: string
  session_id: string
  sequence: number
  role: 'user' | 'assistant' | 'tool'
  content: string | null
  // Assistant step: list of tool calls to execute
  tool_calls?: Array<{
    id: string
    type: string
    function: {
      name: string
      arguments: string
    }
    index?: number
  }>
  // Tool step: name of the tool that was called
  name?: string
  // Tool step: ID linking to the tool_call in assistant step
  tool_call_id?: string
  created_at: string
}

/**
 * Convert backend steps to frontend timeline events.
 * 
 * The conversion handles the relationship between:
 * 1. Assistant step's tool_calls[] - contains tool invocation (name, arguments)
 * 2. Tool step - contains tool result (content) linked by tool_call_id
 * 
 * We merge them by matching tool_call_id to create complete tool events
 * with both invocation info and results.
 * 
 * @param steps - Array of backend steps from the API
 * @returns Array of timeline events for display
 * 
 * @example
 * // Backend steps:
 * // 1. { role: 'user', content: 'What is the weather?' }
 * // 2. { role: 'assistant', tool_calls: [{ id: 'call-1', function: { name: 'get_weather', arguments: '{"city":"Tokyo"}' } }] }
 * // 3. { role: 'tool', tool_call_id: 'call-1', name: 'get_weather', content: '{"temp": 22}' }
 * // 4. { role: 'assistant', content: 'The weather in Tokyo is 22°C.' }
 * 
 * // Converted to:
 * // 1. { type: 'user', content: 'What is the weather?' }
 * // 2. { type: 'tool', toolName: 'get_weather', toolArgs: '{"city":"Tokyo"}', toolResult: '{"temp": 22}', toolStatus: 'completed' }
 * // 3. { type: 'assistant', content: 'The weather in Tokyo is 22°C.' }
 */
export function stepsToEvents(steps: BackendStep[]): TimelineEvent[] {
  const events: TimelineEvent[] = []
  
  // First pass: collect tool results by tool_call_id for quick lookup
  // This allows us to match tool results with their corresponding tool calls
  const toolResultsMap = new Map<string, { content: string; name: string; timestamp: number }>()
  for (const step of steps) {
    if (step.role === 'tool' && step.tool_call_id) {
      toolResultsMap.set(step.tool_call_id, {
        content: step.content || '',
        name: step.name || 'Unknown Tool',
        timestamp: new Date(step.created_at).getTime(),
      })
    }
  }
  
  // Second pass: build events
  for (const step of steps) {
    if (step.role === 'user') {
      // User messages are straightforward
      events.push({
        id: step.id,
        type: 'user',
        content: step.content || '',
        timestamp: new Date(step.created_at).getTime(),
      })
    } else if (step.role === 'assistant') {
      // Add assistant text content if present
      if (step.content) {
        events.push({
          id: step.id,
          type: 'assistant',
          content: step.content,
          timestamp: new Date(step.created_at).getTime(),
        })
      }
      
      // Add tool call events from assistant's tool_calls
      // Each tool_call becomes a separate tool event
      if (step.tool_calls && Array.isArray(step.tool_calls)) {
        for (const tc of step.tool_calls) {
          const toolCallId = tc.id
          // Look up the result from the tool step (if executed)
          const toolResult = toolCallId ? toolResultsMap.get(toolCallId) : undefined
          
          events.push({
            id: toolCallId || `${step.id}_tool_${tc.index ?? 0}`,
            type: 'tool',
            toolName: tc.function?.name || 'Unknown Tool',
            toolArgs: tc.function?.arguments || '{}',
            toolResult: toolResult?.content,
            toolStatus: toolResult ? 'completed' : 'running',
            timestamp: new Date(step.created_at).getTime(),
          })
        }
      }
    }
    // Note: tool role steps are handled via toolResultsMap, not added directly
    // Their content is merged into the tool events created from assistant's tool_calls
  }
  
  return events
}
