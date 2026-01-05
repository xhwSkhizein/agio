import { RunnableExecution, ExecutionStep } from '../../types/execution'

export type InfoDensity = 'L1' | 'L2' | 'L3'

export interface ToolCallSummary {
  toolName: string
  count: number
  status: 'completed' | 'failed' | 'running'
  icon?: string
}

export interface ExecutionSummaryV2 {
  agentName: string
  intent?: string
  status: 'completed' | 'failed' | 'running'
  stepCount: number
  childCount: number
  keyOutputs: string[]
  toolSummaries: ToolCallSummary[]
}

/**
 * Extracts the "intent" from reasoning content (Thinking).
 * V1 simply shows the thinking. V2 aims to summarize or extract the core intent.
 */
export function extractIntent(reasoning?: string): string | undefined {
  if (!reasoning) return undefined
  
  // Simple heuristic: take the first sentence or first 100 characters
  const trimmed = reasoning.trim()
  if (!trimmed) return undefined
  
  const firstSentence = trimmed.split(/[.!?]\s/)[0]
  if (firstSentence.length < 150) {
    return firstSentence + (firstSentence.length < trimmed.length ? '...' : '')
  }
  
  return trimmed.slice(0, 147) + '...'
}

/**
 * Merges consecutive tool calls of the same type.
 */
export function mergeToolCalls(steps: ExecutionStep[]): Array<ExecutionStep | { type: 'merged_tool_calls', toolName: string, count: number, steps: ExecutionStep[] }> {
  const result: Array<ExecutionStep | { type: 'merged_tool_calls', toolName: string, count: number, steps: ExecutionStep[] }> = []
  
  let currentGroup: { toolName: string, steps: ExecutionStep[] } | null = null
  
  for (const step of steps) {
    if (step.type === 'tool_call') {
      const hasChild = !!step.childRunId
      
      if (!hasChild && currentGroup && currentGroup.toolName === step.toolName) {
        currentGroup.steps.push(step)
      } else {
        if (currentGroup) {
          if (currentGroup.steps.length > 1) {
            result.push({ type: 'merged_tool_calls', toolName: currentGroup.toolName, count: currentGroup.steps.length, steps: currentGroup.steps })
          } else {
            result.push(currentGroup.steps[0])
          }
        }
        currentGroup = { toolName: step.toolName, steps: [step] }
      }
    } else if (step.type === 'tool_result') {
      // Find the corresponding tool_call in the current group or previous results
      if (currentGroup) {
        currentGroup.steps.push(step)
      } else {
        result.push(step)
      }
    } else {
      if (currentGroup) {
        if (currentGroup.steps.length > 1) {
          result.push({ type: 'merged_tool_calls', toolName: currentGroup.toolName, count: currentGroup.steps.length / 2, steps: currentGroup.steps })
        } else {
          result.push(...currentGroup.steps)
        }
        currentGroup = null
      }
      result.push(step)
    }
  }
  
  if (currentGroup) {
    if (currentGroup.steps.length > 2) { // 2 because tool_call + tool_result
        result.push({ type: 'merged_tool_calls', toolName: currentGroup.toolName, count: currentGroup.steps.filter(s => s.type === 'tool_call').length, steps: currentGroup.steps })
    } else {
        result.push(...currentGroup.steps)
    }
  }
  
  return result
}

/**
 * Generates a summary for L1 density.
 */
export function summarizeExecution(execution: RunnableExecution): ExecutionSummaryV2 {
  const toolCalls = execution.steps.filter(s => s.type === 'tool_call') as Extract<ExecutionStep, { type: 'tool_call' }>[]
  
  // Group tool calls for summary
  const toolMap = new Map<string, { count: number, status: 'completed' | 'failed' | 'running' }>()
  toolCalls.forEach(tc => {
    const existing = toolMap.get(tc.toolName) || { count: 0, status: 'completed' }
    // In a real app we'd check tool_result status here
    toolMap.set(tc.toolName, { 
      count: existing.count + 1, 
      status: execution.status === 'running' ? 'running' : 'completed' 
    })
  })
  
  const toolSummaries: ToolCallSummary[] = Array.from(toolMap.entries()).map(([name, info]) => ({
    toolName: name,
    count: info.count,
    status: info.status
  }))

  const assistantStep = execution.steps.find(s => s.type === 'assistant_content') as Extract<ExecutionStep, { type: 'assistant_content' }> | undefined
  const intent = extractIntent(assistantStep?.reasoning_content)
  
  // Extract key outputs (e.g. final answer)
  const keyOutputs: string[] = []
  if (assistantStep?.content) {
    keyOutputs.push(assistantStep.content.slice(0, 200) + (assistantStep.content.length > 200 ? '...' : ''))
  }

  return {
    agentName: execution.runnableId.replace(/_/g, ' '),
    intent,
    status: execution.status,
    stepCount: execution.steps.length,
    childCount: execution.children.length,
    keyOutputs,
    toolSummaries
  }
}
