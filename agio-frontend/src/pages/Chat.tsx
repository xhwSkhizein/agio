import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { agentService, sessionService, runnableService } from '../services/api'
import { parseSSEBuffer } from '../utils/sseParser'
import { stepsToEvents } from '../utils/stepsToEvents'
import { generateId, type TimelineEvent } from '../types/chat'
import type { WorkflowNode } from '../types/workflow'
import { useScrollManagement } from '../hooks/useScrollManagement'
import { useAgentSelection } from '../hooks/useAgentSelection'
import { useSSEStream } from '../hooks/useSSEStream'
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
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [input, setInput] = useState(pendingMessage || '')
  const [isStreaming, setIsStreaming] = useState(false)
  const [showConfigModal, setShowConfigModal] = useState(false)
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Workflow state management
  const [workflowNodes, setWorkflowNodes] = useState<Map<string, WorkflowNode>>(new Map())
  const workflowNodesRef = useRef<Map<string, WorkflowNode>>(new Map())

  // SSE stream processing
  const { processSSEEvent, resetTracking } = useSSEStream({
    onEvent: setEvents,
    onSessionId: (sessionId) => {
      if (!currentSessionId) {
        setCurrentSessionId(sessionId)
      }
    },
    onRunId: setCurrentRunId,
    onRunCompleted: () => {
      // Invalidate session cache so Sessions page shows the new session
      queryClient.invalidateQueries({ queryKey: ['session-summaries'] })
    },
    onWorkflowNodesUpdate: (nodes) => {
      setWorkflowNodes(nodes)
    },
    workflowNodesRef,
  })

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
  const { data: existingSteps, refetch: refetchSteps } = useQuery({
    queryKey: ['session-steps', urlSessionId],
    queryFn: () => sessionService.getSessionSteps(urlSessionId!),
    enabled: !!urlSessionId,
  })

  // Check if session has pending tool_calls (last step is assistant with tool_calls)
  const hasPendingToolCalls = existingSteps && existingSteps.length > 0 && (() => {
    const lastStep = existingSteps[existingSteps.length - 1]
    return lastStep.role === 'assistant' && lastStep.tool_calls && lastStep.tool_calls.length > 0
  })()

  // Convert steps to events when loading existing session
  useEffect(() => {
    if (existingSteps && existingSteps.length > 0 && events.length === 0) {
      const loadedEvents = stepsToEvents(existingSteps)
      setEvents(loadedEvents)
      setCurrentSessionId(urlSessionId!)
    }
  }, [existingSteps, urlSessionId])

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

  // Auto-scroll only if user is near bottom
  useEffect(() => {
    const scrollContainer = scrollContainerRef.current
    if (!scrollContainer) return

    // Only auto-scroll if user is near bottom (hasn't scrolled up)
    if (isNearBottom(scrollContainer)) {
      scrollToBottom()
      isUserScrolledUpRef.current = false
    }
  }, [events])

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
      setIsStreaming(false)
      setEvents(prev => [...prev, {
        id: generateId(),
        type: 'error',
        content: 'Request cancelled by user',
        timestamp: Date.now()
      }])
    }
  }

  const handleSend = async () => {
    if (!input.trim() || !selectedAgentId) return

    const userEvent: TimelineEvent = {
      id: generateId(),
      type: 'user',
      content: input,
      timestamp: Date.now(),
    }

    setEvents((prev) => [...prev, userEvent])
    setInput('')
    setIsStreaming(true)
    // Force scroll to bottom when user sends a message
    isUserScrolledUpRef.current = false
    setTimeout(() => scrollToBottom(true), 100)
    resetTracking()

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
            processSSEEvent(eventType, data)
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
      setEvents(prev => [...prev, {
        id: generateId(),
        type: 'error',
        content: 'Failed to send message',
        timestamp: Date.now()
      }])
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
    resetTracking()
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
            processSSEEvent(eventType, data)
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
      setEvents(prev => [...prev, { id: generateId(), type: 'error', content: 'Failed to continue', timestamp: Date.now() }])
    } finally {
      setIsStreaming(false)
      abortControllerRef.current = null
    }
  }

  // Start new chat
  const handleNewChat = () => {
    setEvents([])
    setCurrentSessionId(null)
    setCurrentRunId(null)
    navigate('/chat')
  }

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
      {events.length === 0 && !isStreaming ? (
        <div
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto pr-4 -mr-4 mb-4"
        >
          <ChatEmptyState agent={agent} />
        </div>
      ) : (
        <ChatTimeline
          events={events}
          workflowNodes={workflowNodes}
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
