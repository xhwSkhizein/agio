/**
 * Hook for managing execution tree state
 * 
 * This hook wraps ExecutionTreeBuilder and provides React state management
 * for the unified execution tree.
 */

import { useRef, useCallback, useState } from 'react'
import { ExecutionTreeBuilder, createExecutionTreeBuilder } from '../utils/executionTreeBuilder'
import type { ExecutionTree, BackendStep } from '../types/execution'
import { createEmptyTree } from '../types/execution'
import type { ExecutionStep, RunnableExecution } from '../types/execution'

interface UseExecutionTreeResult {
  tree: ExecutionTree
  sessionId: string | null
  processEvent: (eventType: string, data: any) => void
  addUserMessage: (content: string) => void
  hydrateFromSteps: (steps: BackendStep[]) => void
  reset: () => void
}

function buildExecutionTreeFromSteps(steps: BackendStep[]): ExecutionTree {
  const tree = createEmptyTree()
  if (!steps || steps.length === 0) {
    return tree
  }

  // Sort steps by sequence to ensure correct order
  const sortedSteps = [...steps].sort((a, b) => a.sequence - b.sequence)
  
  // Group steps by run_id to build executions
  const runStepsMap = new Map<string, BackendStep[]>()
  
  // First pass: group all steps by run_id (including user steps)
  for (const step of sortedSteps) {
    if (step.run_id) {
      if (!runStepsMap.has(step.run_id)) {
        runStepsMap.set(step.run_id, [])
      }
      runStepsMap.get(step.run_id)!.push(step)
    }
  }

  // Build executions from steps
  const executionsMap = new Map<string, RunnableExecution>()
  
  // First pass: create all executions
  for (const [runId, runSteps] of runStepsMap.entries()) {
    if (runSteps.length === 0) continue
    
    const firstStep = runSteps[0]
    const lastStep = runSteps[runSteps.length - 1]
    const firstTimestamp = new Date(firstStep.created_at).getTime()
    const lastTimestamp = new Date(lastStep.created_at).getTime()
    
    // Determine runnable type
    const runnableType = 'agent' as const
    
    // Determine nesting type
    let nestingType: 'tool_call' | undefined = undefined
    if (firstStep.parent_run_id) {
      // Check if this is a tool_call nested execution
      // We'll determine this when linking parent-child relationships
      nestingType = 'tool_call'
    }
    
    const exec: RunnableExecution = {
      id: runId,
      runnableId: firstStep.runnable_id || 'unknown',
      runnableType,
      nestingType,
      parentRunId: firstStep.parent_run_id || undefined,
      depth: firstStep.depth || 0,
      status: 'completed',
      steps: [],
      children: [],
      startTime: firstTimestamp,
      endTime: lastTimestamp,
    }
    
    // Build execution steps directly from BackendStep
    // First, collect tool results by tool_call_id for matching
    const toolResultsMap = new Map<string, BackendStep>()
    for (const step of runSteps) {
      if (step.role === 'tool' && step.tool_call_id) {
        toolResultsMap.set(step.tool_call_id, step)
      }
    }
    
    // Process steps in sequence order
    for (const step of runSteps) {
      if (step.role === 'user') {
        // Add user step to execution only if this is a nested execution
        // Top-level user messages will be added to tree.messages later
        if (firstStep.parent_run_id) {
          exec.steps.push({
            type: 'user',
            stepId: step.id,
            content: step.content || '',
          })
        }
      } else if (step.role === 'assistant') {
        // Add assistant content step
        if (step.content || step.reasoning_content) {
          exec.steps.push({
            type: 'assistant_content',
            stepId: step.id,
            content: step.content || '',
            reasoning_content: step.reasoning_content || undefined,
            metrics: step.metrics,
          })
        }
        
        // Add tool call steps
        if (step.tool_calls && Array.isArray(step.tool_calls)) {
          for (const tc of step.tool_calls) {
            const toolCallId = tc.id || `${step.id}_tool_${tc.index ?? 0}`
            const toolResultStep = toolCallId ? toolResultsMap.get(toolCallId) : undefined
            
            exec.steps.push({
              type: 'tool_call',
              stepId: `${toolCallId}_call`,
              toolCallId,
              toolName: tc.function?.name || 'Unknown Tool',
              toolArgs: tc.function?.arguments || '{}',
            })
            
            // Add tool result if exists
            if (toolResultStep) {
              exec.steps.push({
                type: 'tool_result',
                stepId: `${toolCallId}_result`,
                toolCallId,
                result: toolResultStep.content || '',
                status: 'completed', // Tool steps are always completed when stored
                // Note: duration not available in BackendStep currently
              })
            }
          }
        }
      }
      // Note: tool role steps are handled via toolResultsMap above
    }
    
    executionsMap.set(runId, exec)
  }
  
  // Second pass: establish parent-child relationships
  for (const exec of executionsMap.values()) {
    if (exec.parentRunId && executionsMap.has(exec.parentRunId)) {
      const parent = executionsMap.get(exec.parentRunId)!
      parent.children.push(exec)
      
      // Determine nesting type based on tool calls
      // Find the first tool_call that matches this execution's runnableId AND doesn't have a childRunId yet
      // This prevents matching the same tool_call multiple times when there are sequential calls to the same agent
      const matchingToolCall = parent.steps.find(
        step => step.type === 'tool_call' && 
        !step.childRunId &&  // Only match tool_calls that haven't been linked yet
        (step.toolName.startsWith('call_') 
          ? step.toolName.slice(5) === exec.runnableId
          : step.toolName === exec.runnableId)
      ) as Extract<ExecutionStep, { type: 'tool_call' }> | undefined
      
      if (matchingToolCall) {
        exec.nestingType = 'tool_call'
        matchingToolCall.childRunId = exec.id
      }
    } else {
      // Root execution
      tree.executions.push(exec)
    }
    
    // Add to execution map
    tree.executionMap.set(exec.id, exec)
  }
  
  // Third pass: add top-level user messages to tree
  // Top-level user messages are those without run_id, or whose run_id corresponds to a root execution
  const rootRunIds = new Set(tree.executions.map(e => e.id))
  
  for (const step of sortedSteps) {
    if (step.role === 'user') {
      // Only add top-level user messages:
      // 1. No run_id (session-level user message)
      // 2. run_id corresponds to a root execution (no parent_run_id)
      if (!step.run_id || rootRunIds.has(step.run_id)) {
        tree.messages.push({
          id: step.id,
          type: 'user',
          content: step.content || '',
          timestamp: new Date(step.created_at).getTime(),
        })
      }
      // Nested execution user messages are already added to their execution's steps above
    }
  }
  
  // Sort executions by start time
  tree.executions.sort((a, b) => (a.startTime || 0) - (b.startTime || 0))
  
  // Sort messages by timestamp
  tree.messages.sort((a, b) => a.timestamp - b.timestamp)
  
  return tree
}

/**
 * Clone ExecutionTree properly, preserving Map instance.
 * Spread operator {...tree} converts Map to empty object {}, breaking Map methods.
 */
function cloneExecutionTree(tree: ExecutionTree): ExecutionTree {
  return {
    messages: [...tree.messages],
    executions: [...tree.executions],
    executionMap: new Map(tree.executionMap),
  }
}

export function useExecutionTree(): UseExecutionTreeResult {
  const builderRef = useRef<ExecutionTreeBuilder>(createExecutionTreeBuilder())
  const [tree, setTree] = useState<ExecutionTree>(createEmptyTree())
  const [sessionId, setSessionId] = useState<string | null>(null)

  const processEvent = useCallback((eventType: string, data: any) => {
    builderRef.current.processEvent(eventType, data)
    
    // Update React state with new tree (properly clone Map)
    setTree(cloneExecutionTree(builderRef.current.getTree()))
    
    // Update session ID if changed
    const newSessionId = builderRef.current.getSessionId()
    if (newSessionId !== sessionId) {
      setSessionId(newSessionId)
    }
  }, [sessionId])

  const addUserMessage = useCallback((content: string) => {
    builderRef.current.addUserMessage(content)
    setTree(cloneExecutionTree(builderRef.current.getTree()))
  }, [])

  const hydrateFromSteps = useCallback((steps: BackendStep[]) => {
    const hydrated = buildExecutionTreeFromSteps(steps)
    // Reset builder state and seed with hydrated tree
    builderRef.current.reset()
    builderRef.current.importTree(hydrated)
    setTree(cloneExecutionTree(hydrated))
    setSessionId(steps[0]?.session_id || null)
  }, [])

  const reset = useCallback(() => {
    builderRef.current.reset()
    setTree(createEmptyTree())
    setSessionId(null)
  }, [])

  return {
    tree,
    sessionId,
    processEvent,
    addUserMessage,
    hydrateFromSteps,
    reset,
  }
}
