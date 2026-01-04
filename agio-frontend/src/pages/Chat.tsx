import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { agentService, sessionService, runnableService } from '../services/api'
import { parseSSEBuffer } from '../utils/sseParser'
import { useScrollManagement } from '../hooks/useScrollManagement'
import { useAgentSelection } from '../hooks/useAgentSelection'
import { useExecutionTree } from '../hooks/useExecutionTree'
import { ChatHeader } from '../components/ChatHeader'
import { ChatTimeline } from '../components/ChatTimeline'
import { ChatInput } from '../components/ChatInput'
import { ChatEmptyState } from '../components/ChatEmptyState'
import { AgentConfigModal } from '../components/AgentConfigModal'

export default function Chat() {
  const { sessionId: urlSessionId } = useParams<{ sessionId?: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()

  // Get state from navigation (fork)
  const locationState = location.state as { pendingMessage?: string; agentId?: string } | null
  const pendingMessage = locationState?.pendingMessage

  // Agent selection
  const {
    selectedAgentId,
    setSelectedAgentId,
    showAgentDropdown,
    setShowAgentDropdown,
  } = useAgentSelection()

  // Scroll management
  const {
    messagesEndRef,
    scrollContainerRef,
    isUserScrolledUpRef,
    scrollToBottom,
    isNearBottom,
  } = useScrollManagement()

  // Session state
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(urlSessionId || null)
  const [input, setInput] = useState(pendingMessage || '')
  const [isStreaming, setIsStreaming] = useState(false)
  const [showConfigModal, setShowConfigModal] = useState(false)
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Execution tree state
  const { 
    tree: executionTree,
    sessionId: treeSessionId,
    processEvent: processTreeEvent, 
    addUserMessage: addTreeUserMessage,
    hydrateFromSteps,
    reset: resetTree,
  } = useExecutionTree()

  // SSE event processor
  const handleSSEEvent = (eventType: string, data: any) => {
    processTreeEvent(eventType, data)
    
    // Extract session ID from run_started
    if (eventType === 'run_started' && data.data?.session_id && !currentSessionId) {
      setCurrentSessionId(data.data.session_id)
    }
    
    // Update run ID
    if (eventType === 'run_started' && data.run_id) {
      setCurrentRunId(data.run_id)
    }
    
    // Clear run ID and invalidate cache on completion
    if (eventType === 'run_completed' || eventType === 'run_failed') {
      setCurrentRunId(null)
      queryClient.invalidateQueries({ queryKey: ['session-summaries'] })
    }
  }

  // Fetch all available agents
  const { data: agents } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentService.listAgents(),
  })

  // Fetch all available runnables (agents + workflows)
  const { data: runnables } = useQuery({
    queryKey: ['runnables'],
    queryFn: () => runnableService.listRunnables(),
  })

  // Check if selected is a workflow
  const isWorkflow = runnables?.workflows?.some(w => w.id === selectedAgentId) ?? false

  // Current agent details (only for agents, not workflows)
  const { data: agent } = useQuery({
    queryKey: ['agent', selectedAgentId],
    queryFn: () => agentService.getAgent(selectedAgentId),
    enabled: !!selectedAgentId && !isWorkflow,
  })

  // Current runnable info (for display)
  const { data: runnableInfo } = useQuery({
    queryKey: ['runnable', selectedAgentId],
    queryFn: () => runnableService.getRunnableInfo(selectedAgentId),
    enabled: !!selectedAgentId && isWorkflow,
  })

  // Load existing session steps if sessionId is provided in URL
  // Use getAllSessionSteps to fetch all steps via pagination for continue functionality
  const { data: existingSteps, refetch: refetchSteps } = useQuery({
    queryKey: ['session-steps', urlSessionId],
    queryFn: () => sessionService.getAllSessionSteps(urlSessionId!),
    enabled: !!urlSessionId,
  })

  // Check if session has pending tool_calls (last step is assistant with tool_calls)
  const hasPendingToolCalls = existingSteps && existingSteps.length > 0 && (() => {
    const lastStep = existingSteps[existingSteps.length - 1]
    return lastStep.role === 'assistant' && lastStep.tool_calls && lastStep.tool_calls.length > 0
  })()

  // Hydrate execution tree when session changes
  useEffect(() => {
    if (!existingSteps || existingSteps.length === 0) return
    if (!urlSessionId) return

    // If tree has different session ID, reset and rehydrate
    const needsReset = treeSessionId !== null && treeSessionId !== urlSessionId

    // If tree already has data for this session, skip hydration
    if (!needsReset && executionTree.executions.length > 0 && treeSessionId === urlSessionId) {
      return
    }

    // Reset tree if switching to different session
    if (needsReset) {
      resetTree()
    }

    // Hydrate with new session's steps
    hydrateFromSteps(existingSteps)
    setCurrentSessionId(urlSessionId)
  }, [existingSteps, urlSessionId, treeSessionId, executionTree.executions.length, hydrateFromSteps, resetTree])

  // Preselect agent/workflow when navigating with state (e.g., from Sessions continue)
  useEffect(() => {
    if (locationState?.agentId) {
      setSelectedAgentId(locationState.agentId)
    }
  }, [locationState?.agentId, setSelectedAgentId])

  // Sync URL sessionId to state when navigating
  useEffect(() => {
    if (urlSessionId && urlSessionId !== currentSessionId) {
      setCurrentSessionId(urlSessionId)
    }
  }, [urlSessionId])

  // Update URL when session is created (to persist conversation on refresh)
  useEffect(() => {
    if (currentSessionId && !urlSessionId) {
      navigate(`/chat/${currentSessionId}`, { replace: true })
    }
  }, [currentSessionId, urlSessionId, navigate])

  // Clear location state after using pending message (to prevent refill on refresh)
  useEffect(() => {
    if (pendingMessage) {
      // Replace current history entry without the state
      navigate(location.pathname, { replace: true, state: {} })
    }
  }, [])

  // Track previous scroll height to detect content growth
  const prevScrollHeightRef = useRef<number>(0)

  // Auto-scroll only if user is near bottom (with debouncing for streaming)
  useEffect(() => {
    const scrollContainer = scrollContainerRef.current
    if (!scrollContainer) return

    const currentScrollHeight = scrollContainer.scrollHeight
    const hasContentGrown = currentScrollHeight > prevScrollHeightRef.current
    prevScrollHeightRef.current = currentScrollHeight

    // Only auto-scroll if:
    // 1. User is near bottom (hasn't scrolled up)
    // 2. Content has actually grown (new content added)
    if (hasContentGrown && isNearBottom(scrollContainer)) {
      // Use a small delay to batch rapid updates during streaming
      // This prevents excessive scrolling when content updates frequently
      const timeoutId = setTimeout(() => {
        if (scrollContainer && isNearBottom(scrollContainer)) {
          scrollToBottom()
          isUserScrolledUpRef.current = false
        }
      }, 50)

      return () => clearTimeout(timeoutId)
    }
  }, [executionTree, isNearBottom, scrollToBottom])

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
      setIsStreaming(false)
      // Add cancel error via tree
      processTreeEvent('error', { error: 'Request cancelled by user' })
    }
  }

  const handleSend = async () => {
    if (!input.trim() || !selectedAgentId) return

    addTreeUserMessage(input)
    setInput('')
    setIsStreaming(true)
    // Force scroll to bottom when user sends a message
    isUserScrolledUpRef.current = false
    setTimeout(() => scrollToBottom(true), 100)

    const userMessage = input
    abortControllerRef.current = new AbortController()

    try {
      // Use unified runnable API for both agents and workflows
      const apiUrl = `/agio/runnables/${selectedAgentId}/run`

      const requestBody = {
        query: userMessage,
        session_id: currentSessionId,
        stream: true,
      }

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify(requestBody),
        signal: abortControllerRef.current.signal,
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) return

      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE events using utility (handles both CRLF and LF line endings)
        const { events: sseEvents, remaining } = parseSSEBuffer(buffer)
        buffer = remaining

        for (const sseEvent of sseEvents) {
          const eventType = sseEvent.event
          const dataStr = sseEvent.data

          try {
            const data = JSON.parse(dataStr)
            handleSSEEvent(eventType, data)
          } catch (e) {
            console.error('Parse error:', e)
          }
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
        // Already handled in handleCancel
        return
      }
      console.error('Streaming error:', error)
      processTreeEvent('error', { error: 'Failed to send message' })
    } finally {
      setIsStreaming(false)
      setCurrentRunId(null)
      abortControllerRef.current = null
    }
  }

  // Handle continue (resume from pending tool_calls)
  const handleContinue = async () => {
    if (!currentSessionId || !hasPendingToolCalls) return

    setIsStreaming(true)
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(sessionService.getResumeSessionUrl(currentSessionId, selectedAgentId), {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
        },
        signal: abortControllerRef.current.signal,
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) return

      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const { events: sseEvents, remaining } = parseSSEBuffer(buffer)
        buffer = remaining

        for (const sseEvent of sseEvents) {
          const eventType = sseEvent.event
          const dataStr = sseEvent.data

          if (!eventType || !dataStr) continue

          try {
            const data = JSON.parse(dataStr)
            if (eventType !== 'step_delta') {
              console.log('Resume SSE Event:', eventType, data)
            }
            handleSSEEvent(eventType, data)
          } catch (e) {
            console.error('Parse error:', e)
          }
        }
      }

      // Refetch steps to update hasPendingToolCalls state
      refetchSteps()
    } catch (error: any) {
      if (error.name === 'AbortError') return
      console.error('Resume error:', error)
      processTreeEvent('error', { error: 'Failed to continue' })
    } finally {
      setIsStreaming(false)
      abortControllerRef.current = null
    }
  }

  // Start new chat
  const handleNewChat = () => {
    setCurrentSessionId(null)
    setCurrentRunId(null)
    resetTree()
    navigate('/chat')
  }

  // Determine if timeline has content
  const hasContent = executionTree.messages.length > 0 || executionTree.executions.length > 0

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] max-w-4xl mx-auto">
      {/* Header with Agent Selector */}
      <ChatHeader
        selectedAgentId={selectedAgentId}
        setSelectedAgentId={setSelectedAgentId}
        showAgentDropdown={showAgentDropdown}
        setShowAgentDropdown={setShowAgentDropdown}
        agents={agents}
        runnables={runnables}
        agent={agent}
        runnableInfo={runnableInfo}
        isWorkflow={isWorkflow}
        onNewChat={handleNewChat}
        onOpenSettings={() => setShowConfigModal(true)}
      />

      {/* Timeline */}
      {!hasContent && !isStreaming ? (
        <div
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto pr-4 -mr-4 mb-4"
        >
          <ChatEmptyState agent={agent} />
        </div>
      ) : (
        <ChatTimeline
          tree={executionTree}
          isStreaming={isStreaming}
          currentRunId={currentRunId}
          scrollContainerRef={scrollContainerRef}
          messagesEndRef={messagesEndRef}
        />
      )}

      {/* Input Area */}
      <ChatInput
        input={input}
        setInput={setInput}
        isStreaming={isStreaming}
        hasPendingToolCalls={!!hasPendingToolCalls}
        onSend={handleSend}
        onCancel={handleCancel}
        onContinue={handleContinue}
      />

      {/* Agent Config Modal */}
      {agent && (
        <AgentConfigModal
          agent={agent}
          isOpen={showConfigModal}
          onClose={() => setShowConfigModal(false)}
        />
      )}
    </div>
  )
}
