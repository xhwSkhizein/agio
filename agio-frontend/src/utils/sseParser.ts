/**
 * SSE (Server-Sent Events) Parser Utility
 * 
 * Handles parsing of SSE event streams, supporting both:
 * - CRLF (\r\n) line endings (HTTP standard / Windows)
 * - LF (\n) line endings (Unix)
 */

export interface SSEEvent {
  event: string
  data: string
}

/**
 * Parse SSE event blocks from a buffer string.
 * 
 * @param buffer - The accumulated buffer containing SSE data
 * @returns An object containing parsed events and the remaining buffer
 */
export function parseSSEBuffer(buffer: string): {
  events: SSEEvent[]
  remaining: string
} {
  // Split by double newline - handle both \r\n\r\n (CRLF) and \n\n (LF)
  const eventBlocks = buffer.split(/\r?\n\r?\n/)
  
  // Keep the last incomplete block in remaining buffer
  const remaining = eventBlocks.pop() || ''
  
  const events: SSEEvent[] = []
  
  for (const block of eventBlocks) {
    if (!block.trim()) continue
    
    // Split lines handling both \r\n and \n
    const lines = block.split(/\r?\n/)
    let eventType = ''
    let dataStr = ''
    
    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        // SSE spec: multiple data lines should be concatenated with newlines
        if (dataStr) {
          dataStr += '\n' + line.slice(5).trim()
        } else {
          dataStr = line.slice(5).trim()
        }
      }
    }
    
    if (eventType && dataStr) {
      events.push({ event: eventType, data: dataStr })
    }
  }
  
  return { events, remaining }
}

/**
 * Parse a single SSE event block.
 * 
 * @param block - A single SSE event block (without trailing double newline)
 * @returns The parsed event or null if invalid
 */
export function parseSSEBlock(block: string): SSEEvent | null {
  if (!block.trim()) return null
  
  const lines = block.split(/\r?\n/)
  let eventType = ''
  let dataStr = ''
  
  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      if (dataStr) {
        dataStr += '\n' + line.slice(5).trim()
      } else {
        dataStr = line.slice(5).trim()
      }
    }
  }
  
  if (!eventType || !dataStr) return null
  
  return { event: eventType, data: dataStr }
}
