/**
 * Hook for managing execution tree state
 * 
 * This hook wraps ExecutionTreeBuilder and provides React state management
 * for the unified execution tree.
 */

import { useRef, useCallback, useState } from 'react'
import { ExecutionTreeBuilder, createExecutionTreeBuilder } from '../utils/executionTreeBuilder'
import type { ExecutionTree } from '../types/execution'
import { createEmptyTree } from '../types/execution'
import type { BackendStep } from '../utils/stepsToEvents'
import { stepsToEvents } from '../utils/stepsToEvents'
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

  const events = stepsToEvents(steps)
  const firstTimestamp = new Date(steps[0].created_at).getTime()
  const lastTimestamp = new Date(steps[steps.length - 1].created_at).getTime()

  const exec: RunnableExecution = {
    id: 'history',
    runnableId: 'history',
    runnableType: 'agent',
    depth: 0,
    status: 'completed',
    steps: [],
    children: [],
    startTime: firstTimestamp,
    endTime: lastTimestamp,
  }

  for (const event of events) {
    if (event.type === 'user') {
      tree.messages.push({
        id: event.id,
        type: 'user',
        content: event.content || '',
        timestamp: event.timestamp,
      })
      continue
    }

    if (event.type === 'assistant') {
      const step: ExecutionStep = {
        type: 'assistant_content',
        stepId: event.id,
        content: event.content || '',
        reasoning_content: event.reasoning_content,
      }
      exec.steps.push(step)
      continue
    }

    if (event.type === 'tool') {
      // Create tool_call entry
      exec.steps.push({
        type: 'tool_call',
        stepId: `${event.id}_call`,
        toolCallId: event.id,
        toolName: event.toolName || 'Tool',
        toolArgs: event.toolArgs || '{}',
      })

      // If tool result exists, add result entry
      if (event.toolResult !== undefined) {
        exec.steps.push({
          type: 'tool_result',
          stepId: `${event.id}_result`,
          toolCallId: event.id,
          result: event.toolResult,
          status: event.toolStatus === 'failed' ? 'failed' : 'completed',
        })
      }
      continue
    }
  }

  tree.executions.push(exec)
  tree.executionMap.set(exec.id, exec)

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
