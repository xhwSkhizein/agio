/**
 * Tests for stepsToEvents utility.
 * 
 * Run with: npx vitest run src/utils/stepsToEvents.test.ts
 * Or add vitest to devDependencies and run: npm test
 * 
 * These tests can also be run manually by importing and calling testAll().
 */

import { stepsToEvents, BackendStep } from './stepsToEvents'

// Test helper
function assertEqual<T>(actual: T, expected: T, message: string): void {
  const actualStr = JSON.stringify(actual)
  const expectedStr = JSON.stringify(expected)
  if (actualStr !== expectedStr) {
    throw new Error(`${message}\nExpected: ${expectedStr}\nActual: ${actualStr}`)
  }
}


/**
 * Test: User step converts correctly
 */
function testUserStep(): void {
  const steps: BackendStep[] = [
    {
      id: 'step-1',
      session_id: 'session-1',
      sequence: 1,
      role: 'user',
      content: 'Hello, world!',
      created_at: '2024-01-01T00:00:00Z',
    },
  ]

  const events = stepsToEvents(steps)

  assertEqual(events.length, 1, 'Should have 1 event')
  assertEqual(events[0].type, 'user', 'Type should be user')
  assertEqual(events[0].content, 'Hello, world!', 'Content should match')
  console.log('✓ testUserStep passed')
}

/**
 * Test: Assistant step with content only
 */
function testAssistantStepWithContent(): void {
  const steps: BackendStep[] = [
    {
      id: 'step-1',
      session_id: 'session-1',
      sequence: 1,
      role: 'assistant',
      content: 'Hello! How can I help you?',
      created_at: '2024-01-01T00:00:00Z',
    },
  ]

  const events = stepsToEvents(steps)

  assertEqual(events.length, 1, 'Should have 1 event')
  assertEqual(events[0].type, 'assistant', 'Type should be assistant')
  assertEqual(events[0].content, 'Hello! How can I help you?', 'Content should match')
  console.log('✓ testAssistantStepWithContent passed')
}

/**
 * Test: Assistant step with tool_calls creates tool events
 */
function testAssistantStepWithToolCalls(): void {
  const steps: BackendStep[] = [
    {
      id: 'step-1',
      session_id: 'session-1',
      sequence: 1,
      role: 'assistant',
      content: null,
      tool_calls: [
        {
          id: 'call-123',
          type: 'function',
          function: {
            name: 'get_weather',
            arguments: '{"city": "Tokyo"}',
          },
        },
      ],
      created_at: '2024-01-01T00:00:00Z',
    },
  ]

  const events = stepsToEvents(steps)

  assertEqual(events.length, 1, 'Should have 1 tool event')
  assertEqual(events[0].type, 'tool', 'Type should be tool')
  assertEqual(events[0].toolName, 'get_weather', 'Tool name should be get_weather')
  assertEqual(events[0].toolArgs, '{"city": "Tokyo"}', 'Tool args should match')
  assertEqual(events[0].toolStatus, 'running', 'Status should be running (no result yet)')
  console.log('✓ testAssistantStepWithToolCalls passed')
}

/**
 * Test: Tool result is merged with tool call
 */
function testToolResultMerging(): void {
  const steps: BackendStep[] = [
    {
      id: 'step-1',
      session_id: 'session-1',
      sequence: 1,
      role: 'assistant',
      content: null,
      tool_calls: [
        {
          id: 'call-123',
          type: 'function',
          function: {
            name: 'get_weather',
            arguments: '{"city": "Tokyo"}',
          },
        },
      ],
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 'step-2',
      session_id: 'session-1',
      sequence: 2,
      role: 'tool',
      content: '{"temperature": 22, "condition": "sunny"}',
      name: 'get_weather',
      tool_call_id: 'call-123',
      created_at: '2024-01-01T00:00:01Z',
    },
  ]

  const events = stepsToEvents(steps)

  assertEqual(events.length, 1, 'Should have 1 merged tool event')
  assertEqual(events[0].type, 'tool', 'Type should be tool')
  assertEqual(events[0].toolName, 'get_weather', 'Tool name should be get_weather')
  assertEqual(events[0].toolArgs, '{"city": "Tokyo"}', 'Tool args should match')
  assertEqual(events[0].toolResult, '{"temperature": 22, "condition": "sunny"}', 'Tool result should match')
  assertEqual(events[0].toolStatus, 'completed', 'Status should be completed')
  console.log('✓ testToolResultMerging passed')
}

/**
 * Test: Multiple tool calls in one assistant step
 */
function testMultipleToolCalls(): void {
  const steps: BackendStep[] = [
    {
      id: 'step-1',
      session_id: 'session-1',
      sequence: 1,
      role: 'assistant',
      content: null,
      tool_calls: [
        {
          id: 'call-1',
          type: 'function',
          function: { name: 'tool_a', arguments: '{"x": 1}' },
        },
        {
          id: 'call-2',
          type: 'function',
          function: { name: 'tool_b', arguments: '{"y": 2}' },
        },
      ],
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 'step-2',
      session_id: 'session-1',
      sequence: 2,
      role: 'tool',
      content: 'result_a',
      name: 'tool_a',
      tool_call_id: 'call-1',
      created_at: '2024-01-01T00:00:01Z',
    },
    {
      id: 'step-3',
      session_id: 'session-1',
      sequence: 3,
      role: 'tool',
      content: 'result_b',
      name: 'tool_b',
      tool_call_id: 'call-2',
      created_at: '2024-01-01T00:00:02Z',
    },
  ]

  const events = stepsToEvents(steps)

  assertEqual(events.length, 2, 'Should have 2 tool events')
  
  assertEqual(events[0].toolName, 'tool_a', 'First tool name')
  assertEqual(events[0].toolResult, 'result_a', 'First tool result')
  assertEqual(events[0].toolStatus, 'completed', 'First tool status')
  
  assertEqual(events[1].toolName, 'tool_b', 'Second tool name')
  assertEqual(events[1].toolResult, 'result_b', 'Second tool result')
  assertEqual(events[1].toolStatus, 'completed', 'Second tool status')
  
  console.log('✓ testMultipleToolCalls passed')
}

/**
 * Test: Full conversation flow
 */
function testFullConversation(): void {
  const steps: BackendStep[] = [
    {
      id: 'step-1',
      session_id: 'session-1',
      sequence: 1,
      role: 'user',
      content: 'What is the weather in Tokyo?',
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 'step-2',
      session_id: 'session-1',
      sequence: 2,
      role: 'assistant',
      content: null,
      tool_calls: [
        {
          id: 'call-weather',
          type: 'function',
          function: { name: 'get_weather', arguments: '{"city": "Tokyo"}' },
        },
      ],
      created_at: '2024-01-01T00:00:01Z',
    },
    {
      id: 'step-3',
      session_id: 'session-1',
      sequence: 3,
      role: 'tool',
      content: '{"temp": 22}',
      name: 'get_weather',
      tool_call_id: 'call-weather',
      created_at: '2024-01-01T00:00:02Z',
    },
    {
      id: 'step-4',
      session_id: 'session-1',
      sequence: 4,
      role: 'assistant',
      content: 'The weather in Tokyo is 22°C.',
      created_at: '2024-01-01T00:00:03Z',
    },
  ]

  const events = stepsToEvents(steps)

  assertEqual(events.length, 3, 'Should have 3 events (user, tool, assistant)')
  
  assertEqual(events[0].type, 'user', 'First event type')
  assertEqual(events[0].content, 'What is the weather in Tokyo?', 'User content')
  
  assertEqual(events[1].type, 'tool', 'Second event type')
  assertEqual(events[1].toolName, 'get_weather', 'Tool name')
  assertEqual(events[1].toolResult, '{"temp": 22}', 'Tool result')
  
  assertEqual(events[2].type, 'assistant', 'Third event type')
  assertEqual(events[2].content, 'The weather in Tokyo is 22°C.', 'Assistant content')
  
  console.log('✓ testFullConversation passed')
}

/**
 * Test: Assistant step with both content and tool_calls
 */
function testAssistantWithContentAndToolCalls(): void {
  const steps: BackendStep[] = [
    {
      id: 'step-1',
      session_id: 'session-1',
      sequence: 1,
      role: 'assistant',
      content: 'Let me check that for you.',
      tool_calls: [
        {
          id: 'call-1',
          type: 'function',
          function: { name: 'search', arguments: '{"q": "test"}' },
        },
      ],
      created_at: '2024-01-01T00:00:00Z',
    },
  ]

  const events = stepsToEvents(steps)

  assertEqual(events.length, 2, 'Should have 2 events (assistant content + tool)')
  assertEqual(events[0].type, 'assistant', 'First should be assistant')
  assertEqual(events[0].content, 'Let me check that for you.', 'Assistant content')
  assertEqual(events[1].type, 'tool', 'Second should be tool')
  assertEqual(events[1].toolName, 'search', 'Tool name')
  
  console.log('✓ testAssistantWithContentAndToolCalls passed')
}

/**
 * Run all tests
 */
export function testAll(): void {
  console.log('Running stepsToEvents tests...\n')
  
  try {
    testUserStep()
    testAssistantStepWithContent()
    testAssistantStepWithToolCalls()
    testToolResultMerging()
    testMultipleToolCalls()
    testFullConversation()
    testAssistantWithContentAndToolCalls()
    
    console.log('\n✅ All tests passed!')
  } catch (error) {
    console.error('\n❌ Test failed:', error)
    throw error
  }
}

// Export for manual testing in browser console:
// import { testAll } from './utils/stepsToEvents.test'
// testAll()

// Auto-run if executed directly
if (typeof window === 'undefined') {
  testAll()
}
