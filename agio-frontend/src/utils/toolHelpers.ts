/**
 * Tool reference helper utilities
 */

import { ToolInfo } from '../services/api'

/**
 * Get display name from a tool reference
 */
export function getToolDisplayName(tool: string | ToolInfo): string {
  if (typeof tool === 'string') {
    return tool
  }
  
  // For ToolInfo objects, prefer name, then agent
  return tool.name || tool.agent || 'unknown'
}

/**
 * Get unique key for a tool reference (for React keys)
 */
export function getToolKey(tool: string | ToolInfo, index: number): string {
  if (typeof tool === 'string') {
    return tool
  }
  
  const name = getToolDisplayName(tool)
  return `${tool.type}-${name}-${index}`
}

/**
 * Convert tools array to display string (comma-separated)
 */
export function toolsToString(tools: (string | ToolInfo)[]): string {
  return tools.map(getToolDisplayName).join(', ')
}

/**
 * Parse comma-separated tool string to tools array
 * Note: This only creates string tools, not ToolInfo objects
 */
export function stringToTools(toolsStr: string): string[] {
  return toolsStr
    .split(',')
    .map(t => t.trim())
    .filter(Boolean)
}

/**
 * Get tool type description for display
 */
export function getToolTypeLabel(tool: string | ToolInfo): string {
  if (typeof tool === 'string') {
    return 'Function'
  }
  
  switch (tool.type) {
    case 'agent_tool':
      return 'Agent'
    case 'function':
      return 'Function'
    default:
      return tool.type
  }
}
