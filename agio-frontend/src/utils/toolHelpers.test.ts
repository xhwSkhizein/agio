/**
 * Tests for tool helper utilities
 */

import { 
  getToolDisplayName, 
  getToolKey, 
  toolsToString, 
  stringToTools,
  getToolTypeLabel 
} from './toolHelpers'
import type { ToolInfo } from '../services/api'

// Test helpers
function assert(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(`❌ Assertion failed: ${message}`)
  }
}

function assertEquals(actual: any, expected: any, message: string) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`❌ ${message}\n  Expected: ${JSON.stringify(expected)}\n  Actual: ${JSON.stringify(actual)}`)
  }
}

// Test cases
function testGetToolDisplayName() {
  console.log('Testing getToolDisplayName...')
  
  // String tool
  assertEquals(
    getToolDisplayName('web_search'),
    'web_search',
    'Should return string tool as-is'
  )
  
  // ToolInfo with name
  const toolWithName: ToolInfo = {
    type: 'function',
    name: 'file_read',
    description: 'Read files'
  }
  assertEquals(
    getToolDisplayName(toolWithName),
    'file_read',
    'Should return name from ToolInfo'
  )
  
  // ToolInfo with agent (agent_tool)
  const agentTool: ToolInfo = {
    type: 'agent_tool',
    agent: 'researcher',
    description: 'Research agent'
  }
  assertEquals(
    getToolDisplayName(agentTool),
    'researcher',
    'Should return agent name for agent_tool'
  )
  
  // ToolInfo with workflow (workflow_tool)
  const workflowTool: ToolInfo = {
    type: 'workflow_tool',
    workflow: 'data_pipeline',
    description: 'Data processing workflow'
  }
  assertEquals(
    getToolDisplayName(workflowTool),
    'data_pipeline',
    'Should return workflow name for workflow_tool'
  )
  
  // ToolInfo with no identifiers
  const unknownTool: ToolInfo = {
    type: 'custom',
    description: 'Unknown tool'
  }
  assertEquals(
    getToolDisplayName(unknownTool),
    'unknown',
    'Should return "unknown" for tool without identifiers'
  )
  
  console.log('✓ testGetToolDisplayName passed')
}

function testGetToolKey() {
  console.log('Testing getToolKey...')
  
  // String tool
  assertEquals(
    getToolKey('web_search', 0),
    'web_search',
    'Should return string tool as key'
  )
  
  // ToolInfo
  const tool: ToolInfo = {
    type: 'agent_tool',
    agent: 'researcher'
  }
  assertEquals(
    getToolKey(tool, 0),
    'agent_tool-researcher-0',
    'Should generate composite key for ToolInfo'
  )
  
  // Different indices
  assertEquals(
    getToolKey(tool, 5),
    'agent_tool-researcher-5',
    'Should include index in key'
  )
  
  // Ensure uniqueness with same tool at different indices
  const key1 = getToolKey(tool, 0)
  const key2 = getToolKey(tool, 1)
  assert(key1 !== key2, 'Keys should be unique for different indices')
  
  console.log('✓ testGetToolKey passed')
}

function testToolsToString() {
  console.log('Testing toolsToString...')
  
  // Empty array
  assertEquals(
    toolsToString([]),
    '',
    'Should return empty string for empty array'
  )
  
  // String tools only
  assertEquals(
    toolsToString(['web_search', 'file_read', 'bash']),
    'web_search, file_read, bash',
    'Should join string tools with comma'
  )
  
  // ToolInfo objects only
  const tools: ToolInfo[] = [
    { type: 'function', name: 'grep' },
    { type: 'agent_tool', agent: 'researcher' },
    { type: 'workflow_tool', workflow: 'pipeline' }
  ]
  assertEquals(
    toolsToString(tools),
    'grep, researcher, pipeline',
    'Should extract names from ToolInfo objects'
  )
  
  // Mixed string and ToolInfo
  const mixedTools: (string | ToolInfo)[] = [
    'web_search',
    { type: 'agent_tool', agent: 'analyst' },
    'file_read',
    { type: 'workflow_tool', workflow: 'etl' }
  ]
  assertEquals(
    toolsToString(mixedTools),
    'web_search, analyst, file_read, etl',
    'Should handle mixed array of strings and ToolInfo'
  )
  
  console.log('✓ testToolsToString passed')
}

function testStringToTools() {
  console.log('Testing stringToTools...')
  
  // Empty string
  assertEquals(
    stringToTools(''),
    [],
    'Should return empty array for empty string'
  )
  
  // Single tool
  assertEquals(
    stringToTools('web_search'),
    ['web_search'],
    'Should parse single tool'
  )
  
  // Multiple tools
  assertEquals(
    stringToTools('web_search, file_read, bash'),
    ['web_search', 'file_read', 'bash'],
    'Should parse comma-separated tools'
  )
  
  // With extra whitespace
  assertEquals(
    stringToTools('  web_search  ,  file_read  ,  bash  '),
    ['web_search', 'file_read', 'bash'],
    'Should trim whitespace from tool names'
  )
  
  // With empty entries
  assertEquals(
    stringToTools('web_search, , file_read, , bash'),
    ['web_search', 'file_read', 'bash'],
    'Should filter out empty entries'
  )
  
  // Only commas and whitespace
  assertEquals(
    stringToTools('  ,  ,  '),
    [],
    'Should return empty array for whitespace-only string'
  )
  
  console.log('✓ testStringToTools passed')
}

function testGetToolTypeLabel() {
  console.log('Testing getToolTypeLabel...')
  
  // String tool
  assertEquals(
    getToolTypeLabel('web_search'),
    'Function',
    'Should return "Function" for string tools'
  )
  
  // Function type
  const functionTool: ToolInfo = {
    type: 'function',
    name: 'grep'
  }
  assertEquals(
    getToolTypeLabel(functionTool),
    'Function',
    'Should return "Function" for function type'
  )
  
  // Agent tool
  const agentTool: ToolInfo = {
    type: 'agent_tool',
    agent: 'researcher'
  }
  assertEquals(
    getToolTypeLabel(agentTool),
    'Agent',
    'Should return "Agent" for agent_tool type'
  )
  
  // Workflow tool
  const workflowTool: ToolInfo = {
    type: 'workflow_tool',
    workflow: 'pipeline'
  }
  assertEquals(
    getToolTypeLabel(workflowTool),
    'Workflow',
    'Should return "Workflow" for workflow_tool type'
  )
  
  // Unknown type
  const customTool: ToolInfo = {
    type: 'custom_type',
    name: 'custom'
  }
  assertEquals(
    getToolTypeLabel(customTool),
    'custom_type',
    'Should return type as-is for unknown types'
  )
  
  console.log('✓ testGetToolTypeLabel passed')
}

function testRoundTripConversion() {
  console.log('Testing round-trip conversion...')
  
  // String tools
  const stringTools = ['web_search', 'file_read', 'bash']
  const stringToolsStr = toolsToString(stringTools)
  const parsedStringTools = stringToTools(stringToolsStr)
  assertEquals(
    parsedStringTools,
    stringTools,
    'Should preserve string tools in round-trip'
  )
  
  // Note: ToolInfo objects are converted to strings, so round-trip doesn't preserve type
  // This is expected behavior for the config editor
  const mixedTools: (string | ToolInfo)[] = [
    'web_search',
    { type: 'agent_tool', agent: 'researcher' }
  ]
  const mixedStr = toolsToString(mixedTools)
  assertEquals(
    mixedStr,
    'web_search, researcher',
    'Should convert mixed tools to string'
  )
  
  const parsedMixed = stringToTools(mixedStr)
  assertEquals(
    parsedMixed,
    ['web_search', 'researcher'],
    'Should parse back to string array (loses type info)'
  )
  
  console.log('✓ testRoundTripConversion passed')
}

function testEdgeCases() {
  console.log('Testing edge cases...')
  
  // Null/undefined handling in ToolInfo
  const toolWithNulls: ToolInfo = {
    type: 'function',
    name: null,
    agent: null,
    workflow: null
  }
  assertEquals(
    getToolDisplayName(toolWithNulls),
    'unknown',
    'Should handle all-null ToolInfo'
  )
  
  // Empty string in tools array
  const toolsWithEmpty = stringToTools('web_search,,file_read')
  assertEquals(
    toolsWithEmpty,
    ['web_search', 'file_read'],
    'Should filter empty strings'
  )
  
  // Special characters in tool names
  const specialTools = ['web_search', 'file-read', 'bash_exec']
  const specialStr = toolsToString(specialTools)
  const parsedSpecial = stringToTools(specialStr)
  assertEquals(
    parsedSpecial,
    specialTools,
    'Should preserve special characters in tool names'
  )
  
  console.log('✓ testEdgeCases passed')
}

// Run all tests
console.log('\n🧪 Running toolHelpers tests...\n')

try {
  testGetToolDisplayName()
  testGetToolKey()
  testToolsToString()
  testStringToTools()
  testGetToolTypeLabel()
  testRoundTripConversion()
  testEdgeCases()
  
  console.log('\n✅ All toolHelpers tests passed!\n')
  if (typeof process !== 'undefined') process.exit(0)
} catch (error) {
  console.error('\n❌ Test failed:', error)
  if (typeof process !== 'undefined') process.exit(1)
  throw error
}
