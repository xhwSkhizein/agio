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

interface UseExecutionTreeResult {
  tree: ExecutionTree
  sessionId: string | null
  processEvent: (eventType: string, data: any) => void
  addUserMessage: (content: string) => void
  reset: () => void
}

export function useExecutionTree(): UseExecutionTreeResult {
  const builderRef = useRef<ExecutionTreeBuilder>(createExecutionTreeBuilder())
  const [tree, setTree] = useState<ExecutionTree>(createEmptyTree())
  const [sessionId, setSessionId] = useState<string | null>(null)

  const processEvent = useCallback((eventType: string, data: any) => {
    builderRef.current.processEvent(eventType, data)
    
    // Update React state with new tree
    setTree({ ...builderRef.current.getTree() })
    
    // Update session ID if changed
    const newSessionId = builderRef.current.getSessionId()
    if (newSessionId !== sessionId) {
      setSessionId(newSessionId)
    }
  }, [sessionId])

  const addUserMessage = useCallback((content: string) => {
    builderRef.current.addUserMessage(content)
    setTree({ ...builderRef.current.getTree() })
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
    reset,
  }
}
