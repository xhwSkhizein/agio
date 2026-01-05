/**
 * Tests for SSE Parser utility.
 * 
 * Run with: npx vitest run src/utils/sseParser.test.ts
 * Or manually by importing and calling testAll().
 * 
 * These tests ensure SSE parsing handles both CRLF and LF line endings correctly.
 * This is important because:
 * - HTTP standard uses CRLF (\r\n)
 * - Some servers/proxies may use LF (\n) only
 * - Mixed scenarios can occur with different middleware
 */

import { parseSSEBuffer, parseSSEBlock, type SSEEvent } from './sseParser'

// Test helper
function assertEqual<T>(actual: T, expected: T, message: string): void {
  const actualStr = JSON.stringify(actual)
  const expectedStr = JSON.stringify(expected)
  if (actualStr !== expectedStr) {
    throw new Error(`${message}\nExpected: ${expectedStr}\nActual: ${actualStr}`)
  }
}

/**
 * Test: Parse single event with LF line endings (Unix style)
 */
function testParseSingleEventLF(): void {
  const buffer = 'event: step_delta\ndata: {"content":"hello"}\n\n'
  const result = parseSSEBuffer(buffer)
  
  assertEqual(result.events.length, 1, 'Should have 1 event')
  assertEqual(result.events[0].event, 'step_delta', 'Event type should match')
  assertEqual(result.events[0].data, '{"content":"hello"}', 'Data should match')
  assertEqual(result.remaining, '', 'Remaining should be empty')
  
  console.log('✓ testParseSingleEventLF passed')
}

/**
 * Test: Parse single event with CRLF line endings (HTTP/Windows style)
 */
function testParseSingleEventCRLF(): void {
  const buffer = 'event: step_delta\r\ndata: {"content":"hello"}\r\n\r\n'
  const result = parseSSEBuffer(buffer)
  
  assertEqual(result.events.length, 1, 'Should have 1 event')
  assertEqual(result.events[0].event, 'step_delta', 'Event type should match')
  assertEqual(result.events[0].data, '{"content":"hello"}', 'Data should match')
  assertEqual(result.remaining, '', 'Remaining should be empty')
  
  console.log('✓ testParseSingleEventCRLF passed')
}

/**
 * Test: Parse multiple events with LF line endings
 */
function testParseMultipleEventsLF(): void {
  const buffer = 'event: run_started\ndata: {"run_id":"123"}\n\nevent: step_delta\ndata: {"content":"hi"}\n\n'
  const result = parseSSEBuffer(buffer)
  
  assertEqual(result.events.length, 2, 'Should have 2 events')
  assertEqual(result.events[0].event, 'run_started', 'First event type')
  assertEqual(result.events[1].event, 'step_delta', 'Second event type')
  
  console.log('✓ testParseMultipleEventsLF passed')
}

/**
 * Test: Parse multiple events with CRLF line endings
 */
function testParseMultipleEventsCRLF(): void {
  const buffer = 'event: run_started\r\ndata: {"run_id":"123"}\r\n\r\nevent: step_delta\r\ndata: {"content":"hi"}\r\n\r\n'
  const result = parseSSEBuffer(buffer)
  
  assertEqual(result.events.length, 2, 'Should have 2 events')
  assertEqual(result.events[0].event, 'run_started', 'First event type')
  assertEqual(result.events[1].event, 'step_delta', 'Second event type')
  
  console.log('✓ testParseMultipleEventsCRLF passed')
}

/**
 * Test: Incomplete event stays in remaining buffer (LF)
 */
function testIncompleteEventLF(): void {
  const buffer = 'event: complete\ndata: {"done":true}\n\nevent: incomplete\ndata: {"partial":'
  const result = parseSSEBuffer(buffer)
  
  assertEqual(result.events.length, 1, 'Should have 1 complete event')
  assertEqual(result.events[0].event, 'complete', 'Complete event type')
  assertEqual(result.remaining, 'event: incomplete\ndata: {"partial":', 'Remaining should contain incomplete event')
  
  console.log('✓ testIncompleteEventLF passed')
}

/**
 * Test: Incomplete event stays in remaining buffer (CRLF)
 */
function testIncompleteEventCRLF(): void {
  const buffer = 'event: complete\r\ndata: {"done":true}\r\n\r\nevent: incomplete\r\ndata: {"partial":'
  const result = parseSSEBuffer(buffer)
  
  assertEqual(result.events.length, 1, 'Should have 1 complete event')
  assertEqual(result.events[0].event, 'complete', 'Complete event type')
  // Note: remaining may have mixed line endings depending on where split happened
  assertEqual(result.remaining.includes('incomplete'), true, 'Remaining should contain incomplete event')
  
  console.log('✓ testIncompleteEventCRLF passed')
}

/**
 * Test: Mixed line endings (some CRLF, some LF)
 */
function testMixedLineEndings(): void {
  // First event uses CRLF, second uses LF
  const buffer = 'event: first\r\ndata: {"a":1}\r\n\r\nevent: second\ndata: {"b":2}\n\n'
  const result = parseSSEBuffer(buffer)
  
  assertEqual(result.events.length, 2, 'Should have 2 events')
  assertEqual(result.events[0].event, 'first', 'First event type')
  assertEqual(result.events[0].data, '{"a":1}', 'First event data')
  assertEqual(result.events[1].event, 'second', 'Second event type')
  assertEqual(result.events[1].data, '{"b":2}', 'Second event data')
  
  console.log('✓ testMixedLineEndings passed')
}

/**
 * Test: Empty buffer
 */
function testEmptyBuffer(): void {
  const result = parseSSEBuffer('')
  
  assertEqual(result.events.length, 0, 'Should have 0 events')
  assertEqual(result.remaining, '', 'Remaining should be empty')
  
  console.log('✓ testEmptyBuffer passed')
}

/**
 * Test: Buffer with only whitespace
 */
function testWhitespaceBuffer(): void {
  const result = parseSSEBuffer('   \n\n   ')
  
  assertEqual(result.events.length, 0, 'Should have 0 events')
  
  console.log('✓ testWhitespaceBuffer passed')
}

/**
 * Test: Event without data line is ignored
 */
function testEventWithoutData(): void {
  const buffer = 'event: no_data\n\nevent: has_data\ndata: {"value":1}\n\n'
  const result = parseSSEBuffer(buffer)
  
  assertEqual(result.events.length, 1, 'Should have 1 event (ignoring one without data)')
  assertEqual(result.events[0].event, 'has_data', 'Should be the event with data')
  
  console.log('✓ testEventWithoutData passed')
}

/**
 * Test: Data line without event type is ignored
 */
function testDataWithoutEvent(): void {
  const buffer = 'data: {"orphan":true}\n\nevent: proper\ndata: {"ok":true}\n\n'
  const result = parseSSEBuffer(buffer)
  
  assertEqual(result.events.length, 1, 'Should have 1 event (ignoring one without event type)')
  assertEqual(result.events[0].event, 'proper', 'Should be the event with type')
  
  console.log('✓ testDataWithoutEvent passed')
}

/**
 * Test: parseSSEBlock with LF
 */
function testParseBlockLF(): void {
  const block = 'event: test_event\ndata: {"key":"value"}'
  const result = parseSSEBlock(block)
  
  assertEqual(result !== null, true, 'Result should not be null')
  assertEqual(result!.event, 'test_event', 'Event type should match')
  assertEqual(result!.data, '{"key":"value"}', 'Data should match')
  
  console.log('✓ testParseBlockLF passed')
}

/**
 * Test: parseSSEBlock with CRLF
 */
function testParseBlockCRLF(): void {
  const block = 'event: test_event\r\ndata: {"key":"value"}'
  const result = parseSSEBlock(block)
  
  assertEqual(result !== null, true, 'Result should not be null')
  assertEqual(result!.event, 'test_event', 'Event type should match')
  assertEqual(result!.data, '{"key":"value"}', 'Data should match')
  
  console.log('✓ testParseBlockCRLF passed')
}


/**
 * Test: Streaming simulation - data arrives in chunks
 */
function testStreamingChunks(): void {
  let buffer = ''
  let allEvents: SSEEvent[] = []
  
  // Chunk 1: partial event
  buffer += 'event: first\r\ndata: {"a":'
  let result = parseSSEBuffer(buffer)
  allEvents.push(...result.events)
  buffer = result.remaining
  assertEqual(allEvents.length, 0, 'No complete events yet')
  
  // Chunk 2: complete first event, start second
  buffer += '1}\r\n\r\nevent: second\r\n'
  result = parseSSEBuffer(buffer)
  allEvents.push(...result.events)
  buffer = result.remaining
  assertEqual(allEvents.length, 1, 'First event complete')
  assertEqual(allEvents[0].event, 'first', 'First event type')
  
  // Chunk 3: complete second event
  buffer += 'data: {"b":2}\r\n\r\n'
  result = parseSSEBuffer(buffer)
  allEvents.push(...result.events)
  buffer = result.remaining
  assertEqual(allEvents.length, 2, 'Both events complete')
  assertEqual(allEvents[1].event, 'second', 'Second event type')
  assertEqual(buffer, '', 'Buffer should be empty')
  
  console.log('✓ testStreamingChunks passed')
}

/**
 * Run all tests
 */
export function testAll(): void {
  console.log('Running SSE Parser tests...\n')
  
  try {
    // Basic parsing tests
    testParseSingleEventLF()
    testParseSingleEventCRLF()
    testParseMultipleEventsLF()
    testParseMultipleEventsCRLF()
    
    // Incomplete/remaining buffer tests
    testIncompleteEventLF()
    testIncompleteEventCRLF()
    
    // Edge cases
    testMixedLineEndings()
    testEmptyBuffer()
    testWhitespaceBuffer()
    testEventWithoutData()
    testDataWithoutEvent()
    
    // Block parsing
    testParseBlockLF()
    testParseBlockCRLF()
    
    // Real-world scenarios
    testStreamingChunks()
    
    console.log('\n✅ All SSE Parser tests passed!')
  } catch (error) {
    console.error('\n❌ Test failed:', error)
    throw error
  }
}

// Export for manual testing in browser console:
// import { testAll } from './utils/sseParser.test'
// testAll()

// Auto-run if executed directly
if (typeof window === 'undefined') {
  testAll()
}
