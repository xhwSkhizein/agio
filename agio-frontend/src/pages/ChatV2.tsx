import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { agentService, sessionService } from '../services/api'
import { parseSSEBuffer } from '../utils/sseParser'
import { useScrollManagement } from '../hooks/useScrollManagement'
import { useAgentSelection } from '../hooks/useAgentSelection'
import { useExecutionTree } from '../hooks/useExecutionTree'
import { ChatHeader } from '../components/ChatHeader'
import { ChatTimelineV2 } from '../components/v2/ChatTimelineV2'
import { ChatInput } from '../components/ChatInput'
import { ChatEmptyState } from '../components/ChatEmptyState'
import { AgentConfigModal } from '../components/AgentConfigModal'
import { LayoutPanelLeft, Bug } from 'lucide-react'

export default function ChatV2() {
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
  const [debugMode, setDebugMode] = useState(true)
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

  // Current agent details
  const { data: agent } = useQuery({
    queryKey: ['agent', selectedAgentId],
    queryFn: () => agentService.getAgent(selectedAgentId),
    enabled: !!selectedAgentId,
  })

  // Load existing session steps if sessionId is provided in URL
  const { data: existingSteps, refetch: refetchSteps } = useQuery({
    queryKey: ['session-steps', urlSessionId],
    queryFn: () => sessionService.getAllSessionSteps(urlSessionId!),
    enabled: !!urlSessionId,
  })

  // Check if session has pending tool_calls
  const hasPendingToolCalls = existingSteps && existingSteps.length > 0 && (() => {
    const lastStep = existingSteps[existingSteps.length - 1]
    return lastStep.role === 'assistant' && lastStep.tool_calls && lastStep.tool_calls.length > 0
  })()

  // Hydrate execution tree when session changes
  useEffect(() => {
    if (!existingSteps || existingSteps.length === 0) return
    if (!urlSessionId) return

    const needsReset = treeSessionId !== null && treeSessionId !== urlSessionId

    if (!needsReset && executionTree.executions.length > 0 && treeSessionId === urlSessionId) {
      return
    }

    if (needsReset) {
      resetTree()
    }

    hydrateFromSteps(existingSteps)
    setCurrentSessionId(urlSessionId)
  }, [existingSteps, urlSessionId, treeSessionId, executionTree.executions.length, hydrateFromSteps, resetTree])

  // Preselect agent when navigating with state
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

  // Update URL when session is created
  useEffect(() => {
    if (currentSessionId && !urlSessionId) {
      navigate(`/chat/${currentSessionId}`, { replace: true })
    }
  }, [currentSessionId, urlSessionId, navigate])

  // Track previous scroll height
  const prevScrollHeightRef = useRef<number>(0)

  // Auto-scroll
  useEffect(() => {
    const scrollContainer = scrollContainerRef.current
    if (!scrollContainer) return

    const currentScrollHeight = scrollContainer.scrollHeight
    const hasContentGrown = currentScrollHeight > prevScrollHeightRef.current
    prevScrollHeightRef.current = currentScrollHeight

    if (hasContentGrown && isNearBottom(scrollContainer)) {
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
      processTreeEvent('error', { error: 'Request cancelled by user' })
    }
  }

  const handleSend = async () => {
    if (!input.trim() || !selectedAgentId) return

    addTreeUserMessage(input)
    setInput('')
    setIsStreaming(true)
    isUserScrolledUpRef.current = false
    setTimeout(() => scrollToBottom(true), 100)

    const userMessage = input
    abortControllerRef.current = new AbortController()

    try {
      const apiUrl = `/agio/agents/${selectedAgentId}/run`
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

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to start execution' }))
        processTreeEvent('error', { error: errorData.detail || 'Failed to start execution' })
        setIsStreaming(false)
        return
      }

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
          try {
            let data: any
            try {
              data = JSON.parse(sseEvent.data)
            } catch (parseErr) {
              // Fallback for non-JSON error messages
              if (sseEvent.event === 'error') {
                data = { error: sseEvent.data }
              } else {
                throw parseErr
              }
            }
            handleSSEEvent(sseEvent.event, data)
          } catch (e) {
            console.error('Parse error:', e)
          }
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError') return
      console.error('Streaming error:', error)
      processTreeEvent('error', { error: 'Failed to send message' })
    } finally {
      setIsStreaming(false)
      setCurrentRunId(null)
      abortControllerRef.current = null
    }
  }

  const handleContinue = async () => {
    if (!currentSessionId || !hasPendingToolCalls) return
    setIsStreaming(true)
    abortControllerRef.current = new AbortController()
    try {
      const response = await fetch(sessionService.getResumeSessionUrl(currentSessionId, selectedAgentId), {
        method: 'POST',
        headers: { Accept: 'text/event-stream' },
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to continue' }))
        processTreeEvent('error', { error: errorData.detail || 'Failed to continue' })
        setIsStreaming(false)
        return
      }

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
          try {
            let data: any
            try {
              data = JSON.parse(sseEvent.data)
            } catch (parseErr) {
              // Fallback for non-JSON error messages
              if (sseEvent.event === 'error') {
                data = { error: sseEvent.data }
              } else {
                throw parseErr
              }
            }
            handleSSEEvent(sseEvent.event, data)
          } catch (e) {
            console.error('Parse error:', e)
          }
        }
      }
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

  const handleNewChat = () => {
    setCurrentSessionId(null)
    setCurrentRunId(null)
    resetTree()
    navigate('/chat')
  }

  const hasContent = executionTree.messages.length > 0 || executionTree.executions.length > 0

  return (
    <div className="flex flex-col h-[calc(100vh-2.5rem)] max-w-5xl mx-auto px-2 animate-in fade-in duration-700">
      {/* Sticky Header with Mode Switcher */}
      <div className="sticky top-0 z-20 bg-background/80 backdrop-blur-md">
        <ChatHeader
          selectedAgentId={selectedAgentId}
          setSelectedAgentId={setSelectedAgentId}
          showAgentDropdown={showAgentDropdown}
          setShowAgentDropdown={setShowAgentDropdown}
          agents={agents}
          agent={agent}
          onNewChat={handleNewChat}
          onOpenSettings={() => setShowConfigModal(true)}
        />
        
        <div className="flex items-center justify-between pb-2 px-1">
           <div className="flex items-center gap-1.5">
             <button 
               onClick={() => navigate(urlSessionId ? `/chat-v1/${urlSessionId}` : '/chat-v1')}
               className="flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-bold bg-white/5 text-gray-500 hover:text-gray-300 transition-colors"
             >
               <LayoutPanelLeft className="w-3 h-3" />
               Legacy V1
             </button>
           </div>
           
           <div className="flex items-center gap-1.5">
             <button 
               onClick={() => setDebugMode(!debugMode)}
               className={`flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-bold transition-colors ${
                 debugMode 
                   ? 'bg-blue-500/10 text-blue-400/80 border border-blue-500/20' 
                   : 'bg-white/5 text-gray-500 hover:text-gray-300 border border-transparent'
               }`}
             >
               <Bug className="w-3 h-3" />
               {debugMode ? 'Debug: ON' : 'Debug: OFF'}
             </button>
           </div>
        </div>
      </div>

      {/* Timeline */}
      {!hasContent && !isStreaming ? (
        <div ref={scrollContainerRef} className="flex-1 overflow-y-auto pr-4 -mr-4 mb-4">
          <ChatEmptyState agent={agent} />
        </div>
      ) : (
        <ChatTimelineV2
          tree={executionTree}
          isStreaming={isStreaming}
          currentRunId={currentRunId}
          scrollContainerRef={scrollContainerRef}
          messagesEndRef={messagesEndRef}
          debugMode={debugMode}
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
