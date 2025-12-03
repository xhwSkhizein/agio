import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { agentService, sessionService } from '../services/api'
import { TimelineItem } from '../components/TimelineItem'
import { ToolCall } from '../components/ToolCall'
import { MessageContent } from '../components/MessageContent'
import { AgentConfigModal } from '../components/AgentConfigModal'
import { ChevronDown, Plus, Settings, MessageSquare, Play } from 'lucide-react'

// Generate unique ID
let idCounter = 0
const generateId = () => `event_${Date.now()}_${++idCounter}`

interface TimelineEvent {
  id: string
  type: 'user' | 'assistant' | 'tool' | 'error'
  content?: string
  toolName?: string
  toolArgs?: string
  toolResult?: string
  toolStatus?: 'running' | 'completed' | 'failed'
  toolDuration?: number
  timestamp: number
  // For assistant messages - token usage
  metrics?: {
    input_tokens?: number
    output_tokens?: number
    total_tokens?: number
    duration_ms?: number
  }
}

// Track tool calls by step_id + index (OpenAI streaming uses index, not id)
interface ToolCallTracker {
  [key: string]: {  // key = `${step_id}_${index}`
    eventId: string  // The event ID in newEvents
    toolCallId?: string  // The actual tool_call_id from OpenAI
  }
}

// Helper: Convert backend steps to frontend events
function stepsToEvents(steps: any[]): TimelineEvent[] {
  return steps.map(step => {
    if (step.role === 'tool') {
      return {
        id: step.id,
        type: 'tool' as const,
        toolName: step.name || 'Tool',
        toolArgs: step.tool_calls?.[0]?.function?.arguments || '{}',
        toolResult: step.content,
        toolStatus: 'completed' as const,
        timestamp: new Date(step.created_at).getTime(),
      }
    }
    
    return {
      id: step.id,
      type: step.role as 'user' | 'assistant',
      content: step.content || '',
      timestamp: new Date(step.created_at).getTime(),
    }
  })
}

// Default agent to use when none is specified
const DEFAULT_AGENT = 'code_assistant'

export default function Chat() {
  const { sessionId: urlSessionId } = useParams<{ sessionId?: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  
  // Get state from navigation (fork)
  const locationState = location.state as { pendingMessage?: string; agentId?: string } | null
  const pendingMessage = locationState?.pendingMessage
  const forkedAgentId = locationState?.agentId
  
  // Agent selection state - use forked agentId if available
  const [selectedAgentId, setSelectedAgentId] = useState<string>(forkedAgentId || DEFAULT_AGENT)
  const [showAgentDropdown, setShowAgentDropdown] = useState(false)
  
  // Session state - key for persistent conversations
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(urlSessionId || null)
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [input, setInput] = useState(pendingMessage || '')
  const [isStreaming, setIsStreaming] = useState(false)
  const [showConfigModal, setShowConfigModal] = useState(false)
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const toolCallTrackerRef = useRef<ToolCallTracker>({})
  // Use ref to accumulate streaming content to avoid React StrictMode double-execution issues
  const streamingContentRef = useRef<{ [stepId: string]: string }>({})

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

  // Clear location state after using pending message (to prevent refill on refresh)
  useEffect(() => {
    if (pendingMessage) {
      // Replace current history entry without the state
      navigate(location.pathname, { replace: true, state: {} })
    }
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (showAgentDropdown) {
        const target = e.target as HTMLElement
        if (!target.closest('[data-agent-dropdown]')) {
          setShowAgentDropdown(false)
        }
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [showAgentDropdown])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
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
    toolCallTrackerRef.current = {}  // Reset tracker for new request
    streamingContentRef.current = {}  // Reset streaming content tracker

    const userMessage = input
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(`/agio/chat/${selectedAgentId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          message: userMessage,
          stream: true,
          session_id: currentSessionId,
        }),
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
        
        // Parse SSE events - split by double newline (event separator)
        const eventBlocks = buffer.split('\n\n')
        // Keep the last incomplete block in buffer
        buffer = eventBlocks.pop() || ''
        
        for (const block of eventBlocks) {
          if (!block.trim()) continue
          
          const lines = block.split('\n')
          let eventType = ''
          let dataStr = ''
          
          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              dataStr = line.slice(5).trim()
            }
          }
          
          if (!eventType || !dataStr) continue

          try {
            const data = JSON.parse(dataStr)
            // Reduce console noise - only log non-delta events
            if (eventType !== 'step_delta') {
              console.log('SSE Event:', eventType, data)
            }
            
            // Capture event type and data in closure
            const currentEvent = eventType
            const stepId = data.step_id || 'unknown'
            
            // Accumulate content OUTSIDE setEvents to avoid double-execution in StrictMode
            if (currentEvent === 'step_delta' && data.delta?.content) {
              const contentRef = streamingContentRef.current
              if (!contentRef[stepId]) {
                contentRef[stepId] = ''
              }
              contentRef[stepId] += data.delta.content
            }
            
            setEvents((prev) => {
              const newEvents = [...prev]
              
              // Handle different event types based on StepEvent format
              switch (currentEvent) {
                  case 'step_delta': {
                    // Handle text content
                    if (data.delta?.content) {
                      const accumulatedContent = streamingContentRef.current[stepId] || ''
                      
                      const existingIdx = newEvents.findIndex(e => e.type === 'assistant' && e.id === stepId)
                      if (existingIdx !== -1) {
                        // Update existing assistant event with accumulated content
                        newEvents[existingIdx] = {
                          ...newEvents[existingIdx],
                          content: accumulatedContent,
                        }
                      } else {
                        // Create new assistant event
                        newEvents.push({
                          id: stepId,
                          type: 'assistant',
                          content: accumulatedContent,
                          timestamp: Date.now(),
                        })
                      }
                    }
                    
                    // Handle tool calls in delta - use index to track, not id
                    // OpenAI streaming: id only appears in first chunk, subsequent chunks only have index
                    if (data.delta?.tool_calls) {
                      for (const toolCall of data.delta.tool_calls) {
                        const tcIndex = toolCall.index ?? 0
                        const trackerKey = `${stepId}_${tcIndex}`
                        const tracker = toolCallTrackerRef.current
                        
                        if (tracker[trackerKey]) {
                          // Existing tool call - accumulate arguments
                          const eventIdx = newEvents.findIndex(e => e.id === tracker[trackerKey].eventId)
                          if (eventIdx !== -1) {
                            const existing = newEvents[eventIdx]
                            const deltaArgs = toolCall.function?.arguments || ''
                            const deltaName = toolCall.function?.name || ''
                            newEvents[eventIdx] = {
                              ...existing,
                              toolName: deltaName 
                                ? (existing.toolName ? existing.toolName + deltaName : deltaName) 
                                : existing.toolName,
                              toolArgs: (existing.toolArgs || '') + deltaArgs,
                            }
                            // Update tool_call_id if we receive it
                            if (toolCall.id) {
                              tracker[trackerKey].toolCallId = toolCall.id
                              newEvents[eventIdx].id = toolCall.id
                            }
                          }
                        } else {
                          // New tool call
                          const eventId = toolCall.id || `${stepId}_tool_${tcIndex}`
                          tracker[trackerKey] = {
                            eventId,
                            toolCallId: toolCall.id,
                          }
                          newEvents.push({
                            id: eventId,
                            type: 'tool',
                            toolName: toolCall.function?.name || '',
                            toolArgs: toolCall.function?.arguments || '',
                            toolStatus: 'running',
                            timestamp: Date.now(),
                          })
                        }
                      }
                    }
                    break
                  }
                  
                  case 'step_completed': {
                    const snapshot = data.snapshot
                    if (snapshot) {
                      // Handle assistant step completion - update metrics and finalize tool calls
                      if (snapshot.role === 'assistant') {
                        const assistantIdx = newEvents.findIndex(e => e.id === data.step_id)
                        if (assistantIdx !== -1 && snapshot.metrics) {
                          newEvents[assistantIdx] = {
                            ...newEvents[assistantIdx],
                            metrics: {
                              input_tokens: snapshot.metrics.input_tokens,
                              output_tokens: snapshot.metrics.output_tokens,
                              total_tokens: snapshot.metrics.total_tokens,
                              duration_ms: snapshot.metrics.duration_ms,
                            }
                          }
                        }
                        
                        // Finalize tool calls from snapshot (in case delta was incomplete)
                        if (snapshot.tool_calls && Array.isArray(snapshot.tool_calls)) {
                          for (const tc of snapshot.tool_calls) {
                            if (!tc.id) continue
                            
                            // Find existing tool event or create new one
                            let toolIdx = newEvents.findIndex(e => e.id === tc.id)
                            
                            // Also check tracker
                            if (toolIdx === -1) {
                              const tracker = toolCallTrackerRef.current
                              for (const key of Object.keys(tracker)) {
                                if (tracker[key].toolCallId === tc.id) {
                                  toolIdx = newEvents.findIndex(e => e.id === tracker[key].eventId)
                                  break
                                }
                              }
                            }
                            
                            if (toolIdx !== -1) {
                              // Update existing
                              newEvents[toolIdx] = {
                                ...newEvents[toolIdx],
                                id: tc.id,
                                toolName: tc.function?.name || newEvents[toolIdx].toolName,
                                toolArgs: tc.function?.arguments || newEvents[toolIdx].toolArgs,
                              }
                            } else {
                              // Create new tool event from snapshot
                              newEvents.push({
                                id: tc.id,
                                type: 'tool',
                                toolName: tc.function?.name || 'Unknown Tool',
                                toolArgs: tc.function?.arguments || '{}',
                                toolStatus: 'running',
                                timestamp: Date.now(),
                              })
                            }
                          }
                        }
                      }
                      
                      // Handle tool results
                      if (snapshot.role === 'tool' && snapshot.tool_call_id) {
                        // Find by tool_call_id in tracker or direct match
                        let toolIndex = newEvents.findIndex(e => e.id === snapshot.tool_call_id)
                        
                        // Also check tracker for matching tool_call_id
                        if (toolIndex === -1) {
                          const tracker = toolCallTrackerRef.current
                          for (const key of Object.keys(tracker)) {
                            if (tracker[key].toolCallId === snapshot.tool_call_id) {
                              toolIndex = newEvents.findIndex(e => e.id === tracker[key].eventId)
                              break
                            }
                          }
                        }
                        
                        if (toolIndex !== -1) {
                          newEvents[toolIndex] = {
                            ...newEvents[toolIndex],
                            id: snapshot.tool_call_id,  // Update to real ID
                            toolResult: snapshot.content,
                            toolStatus: snapshot.is_error ? 'failed' : 'completed',
                            toolDuration: snapshot.metrics?.duration_ms,
                          }
                        } else {
                          // Tool result without matching tool call - create one
                          newEvents.push({
                            id: snapshot.tool_call_id,
                            type: 'tool',
                            toolName: snapshot.name || 'Unknown Tool',
                            toolArgs: '{}',
                            toolResult: snapshot.content,
                            toolStatus: snapshot.is_error ? 'failed' : 'completed',
                            toolDuration: snapshot.metrics?.duration_ms,
                            timestamp: Date.now(),
                          })
                        }
                      }
                    }
                    break
                  }
                  
                  case 'run_started': {
                    console.log('Run started:', data.run_id, 'Session:', data.data?.session_id)
                    setCurrentRunId(data.run_id)
                    
                    // Capture session_id from event and update URL for persistence
                    const eventSessionId = data.data?.session_id
                    if (eventSessionId && !currentSessionId) {
                      setCurrentSessionId(eventSessionId)
                      // Update URL to include sessionId so refresh preserves the conversation
                      navigate(`/chat/${eventSessionId}`, { replace: true })
                    }
                    break
                  }
                  
                  case 'run_completed': {
                    console.log('Run completed:', data)
                    setCurrentRunId(null)
                    // Mark any still-running tool calls as completed
                    newEvents.forEach((event, idx) => {
                      if (event.type === 'tool' && event.toolStatus === 'running') {
                        newEvents[idx] = { ...event, toolStatus: 'completed' }
                      }
                    })
                    // Check for termination reason
                    if (data.data?.termination_reason) {
                      const reason = data.data.termination_reason
                      if (reason === 'max_steps') {
                        newEvents.push({
                          id: generateId(),
                          type: 'error',
                          content: `Reached maximum steps limit (${data.data.max_steps || 30}). You can continue the conversation.`,
                          timestamp: Date.now(),
                        })
                      } else if (reason === 'timeout') {
                        newEvents.push({
                          id: generateId(),
                          type: 'error',
                          content: 'Request timed out. You can continue the conversation.',
                          timestamp: Date.now(),
                        })
                      }
                    }
                    break
                  }
                  
                  case 'run_failed': {
                    console.log('Run failed:', data)
                    setCurrentRunId(null)
                    newEvents.push({
                      id: generateId(),
                      type: 'error',
                      content: data.data?.error || data.error || 'Run failed',
                      timestamp: Date.now(),
                    })
                    break
                  }
                  
                  case 'error': {
                    newEvents.push({
                      id: generateId(),
                      type: 'error',
                      content: data.error || data.data?.error || 'An error occurred',
                      timestamp: Date.now(),
                    })
                    break
                  }
                }
                
                return newEvents
              })
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
    toolCallTrackerRef.current = {}
    streamingContentRef.current = {}
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
        
        const eventBlocks = buffer.split('\n\n')
        buffer = eventBlocks.pop() || ''
        
        for (const block of eventBlocks) {
          if (!block.trim()) continue
          
          const lines = block.split('\n')
          let eventType = ''
          let dataStr = ''
          
          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              dataStr = line.slice(5).trim()
            }
          }
          
          if (!eventType || !dataStr) continue

          try {
            const data = JSON.parse(dataStr)
            if (eventType !== 'step_delta') {
              console.log('Resume SSE Event:', eventType, data)
            }
            
            const currentEvent = eventType
            const stepId = data.step_id || 'unknown'
            
            if (currentEvent === 'step_delta' && data.delta?.content) {
              const contentRef = streamingContentRef.current
              if (!contentRef[stepId]) {
                contentRef[stepId] = ''
              }
              contentRef[stepId] += data.delta.content
            }
            
            setEvents((prev) => {
              const newEvents = [...prev]
              
              switch (currentEvent) {
                case 'step_delta': {
                  if (data.delta?.content) {
                    const accumulatedContent = streamingContentRef.current[stepId] || ''
                    const existingIdx = newEvents.findIndex(e => e.type === 'assistant' && e.id === stepId)
                    if (existingIdx !== -1) {
                      newEvents[existingIdx] = { ...newEvents[existingIdx], content: accumulatedContent }
                    } else {
                      newEvents.push({ id: stepId, type: 'assistant', content: accumulatedContent, timestamp: Date.now() })
                    }
                  }
                  
                  if (data.delta?.tool_calls) {
                    for (const toolCall of data.delta.tool_calls) {
                      const tcIndex = toolCall.index ?? 0
                      const trackerKey = `${stepId}_${tcIndex}`
                      const tracker = toolCallTrackerRef.current
                      
                      if (tracker[trackerKey]) {
                        const eventIdx = newEvents.findIndex(e => e.id === tracker[trackerKey].eventId)
                        if (eventIdx !== -1) {
                          const existing = newEvents[eventIdx]
                          newEvents[eventIdx] = {
                            ...existing,
                            toolName: toolCall.function?.name ? (existing.toolName || '') + toolCall.function.name : existing.toolName,
                            toolArgs: (existing.toolArgs || '') + (toolCall.function?.arguments || ''),
                          }
                          if (toolCall.id) {
                            tracker[trackerKey].toolCallId = toolCall.id
                            newEvents[eventIdx].id = toolCall.id
                          }
                        }
                      } else {
                        const eventId = toolCall.id || `${stepId}_tool_${tcIndex}`
                        tracker[trackerKey] = { eventId, toolCallId: toolCall.id }
                        newEvents.push({
                          id: eventId, type: 'tool', toolName: toolCall.function?.name || '',
                          toolArgs: toolCall.function?.arguments || '', toolStatus: 'running', timestamp: Date.now(),
                        })
                      }
                    }
                  }
                  break
                }
                
                case 'step_completed': {
                  const snapshot = data.snapshot
                  if (snapshot?.role === 'tool' && snapshot.tool_call_id) {
                    let toolIndex = newEvents.findIndex(e => e.id === snapshot.tool_call_id)
                    if (toolIndex === -1) {
                      const tracker = toolCallTrackerRef.current
                      for (const key of Object.keys(tracker)) {
                        if (tracker[key].toolCallId === snapshot.tool_call_id) {
                          toolIndex = newEvents.findIndex(e => e.id === tracker[key].eventId)
                          break
                        }
                      }
                    }
                    if (toolIndex !== -1) {
                      newEvents[toolIndex] = {
                        ...newEvents[toolIndex], id: snapshot.tool_call_id,
                        toolResult: snapshot.content, toolStatus: snapshot.is_error ? 'failed' : 'completed',
                        toolDuration: snapshot.metrics?.duration_ms,
                      }
                    } else {
                      newEvents.push({
                        id: snapshot.tool_call_id, type: 'tool', toolName: snapshot.name || 'Unknown Tool',
                        toolArgs: '{}', toolResult: snapshot.content, toolStatus: snapshot.is_error ? 'failed' : 'completed',
                        toolDuration: snapshot.metrics?.duration_ms, timestamp: Date.now(),
                      })
                    }
                  }
                  if (snapshot?.role === 'assistant' && snapshot.metrics) {
                    const assistantIdx = newEvents.findIndex(e => e.id === data.step_id)
                    if (assistantIdx !== -1) {
                      newEvents[assistantIdx] = {
                        ...newEvents[assistantIdx],
                        metrics: {
                          input_tokens: snapshot.metrics.input_tokens,
                          output_tokens: snapshot.metrics.output_tokens,
                          total_tokens: snapshot.metrics.total_tokens,
                          duration_ms: snapshot.metrics.duration_ms,
                        }
                      }
                    }
                  }
                  break
                }
                
                case 'error': {
                  newEvents.push({ id: generateId(), type: 'error', content: data.error || 'An error occurred', timestamp: Date.now() })
                  break
                }
              }
              
              return newEvents
            })
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
      <div className="flex items-center justify-between py-3 border-b border-border mb-4">
        <div className="flex items-center gap-3">
          {/* New Chat Button */}
          <button
            onClick={handleNewChat}
            className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
            title="New Chat"
          >
            <Plus className="w-5 h-5" />
          </button>
          
          {/* Agent Selector Dropdown */}
          <div className="relative" data-agent-dropdown>
            <button
              onClick={() => setShowAgentDropdown(!showAgentDropdown)}
              className="flex items-center gap-2 px-3 py-2 bg-surface border border-border rounded-lg hover:border-primary-500/50 transition-colors"
            >
              <span className="text-sm font-medium text-white">
                {agent?.name?.replace(/_/g, ' ') || 'Select Agent'}
              </span>
              <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${showAgentDropdown ? 'rotate-180' : ''}`} />
            </button>
            
            {showAgentDropdown && (
              <div className="absolute top-full left-0 mt-1 w-64 bg-surface border border-border rounded-lg shadow-xl z-50 py-1 max-h-80 overflow-y-auto">
                {agents?.items?.map((a) => (
                  <button
                    key={a.name}
                    onClick={() => {
                      setSelectedAgentId(a.name)
                      setShowAgentDropdown(false)
                    }}
                    className={`w-full text-left px-3 py-2 hover:bg-surfaceHighlight transition-colors ${
                      selectedAgentId === a.name ? 'bg-surfaceHighlight' : ''
                    }`}
                  >
                    <div className="text-sm font-medium text-white">{a.name.replace(/_/g, ' ')}</div>
                    <div className="text-xs text-gray-500 truncate">{a.system_prompt?.slice(0, 60) || 'AI Assistant'}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        
        {/* Right side - Settings */}
        <button
          onClick={() => setShowConfigModal(true)}
          className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          title="Agent Settings"
        >
          <Settings className="w-5 h-5" />
        </button>
      </div>

      {/* Timeline */}
      <div className="flex-1 overflow-y-auto pr-4 -mr-4 mb-4">
        {/* Empty state - welcome message */}
        {events.length === 0 && !isStreaming && (
          <div className="flex flex-col items-center justify-center h-full text-center py-20">
            <div className="w-16 h-16 bg-primary-500/10 rounded-2xl flex items-center justify-center mb-4">
              <MessageSquare className="w-8 h-8 text-primary-400" />
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">
              {agent?.name?.replace(/_/g, ' ') || 'AI Assistant'}
            </h2>
            <p className="text-gray-500 max-w-md text-sm">
              {agent?.system_prompt?.slice(0, 150) || 'Start a conversation by typing a message below.'}
              {agent?.system_prompt && agent.system_prompt.length > 150 ? '...' : ''}
            </p>
            {agent?.tools && agent.tools.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2 justify-center max-w-md">
                {agent.tools.slice(0, 6).map((tool) => (
                  <span key={tool} className="px-2 py-1 text-xs bg-surface border border-border rounded text-gray-400">
                    {tool}
                  </span>
                ))}
                {agent.tools.length > 6 && (
                  <span className="px-2 py-1 text-xs text-gray-500">+{agent.tools.length - 6} more</span>
                )}
              </div>
            )}
          </div>
        )}
        
        <div className="space-y-0 -mt-1">
          {events.map((event, index) => (
            <TimelineItem 
              key={event.id} 
              type={event.type}
              isLast={index === events.length - 1}
            >
              {event.type === 'tool' ? (
                <ToolCall
                  toolName={event.toolName || 'Unknown Tool'}
                  args={event.toolArgs || '{}'}
                  result={event.toolResult}
                  status={event.toolStatus || 'running'}
                  duration={event.toolDuration}
                />
              ) : (
                <div>
                  <div className={`text-xs leading-relaxed ${
                    event.type === 'error' ? 'text-red-400' : 
                    event.type === 'user' ? 'text-white font-medium' : 'text-gray-300'
                  }`}>
                    <MessageContent content={event.content || ''} />
                  </div>
                  {/* Token usage for assistant messages */}
                  {event.type === 'assistant' && event.metrics && (
                    <div className="mt-0.5 flex items-center gap-2 text-[9px] text-gray-500 font-mono">
                      {event.metrics.input_tokens && (
                        <span title="Input tokens">in: {event.metrics.input_tokens}</span>
                      )}
                      {event.metrics.output_tokens && (
                        <span title="Output tokens">out: {event.metrics.output_tokens}</span>
                      )}
                      {event.metrics.duration_ms && (
                        <span title="Response time">{(event.metrics.duration_ms / 1000).toFixed(2)}s</span>
                      )}
                    </div>
                  )}
                </div>
              )}
            </TimelineItem>
          ))}
          
          {isStreaming && events.length > 0 && events[events.length - 1].type !== 'assistant' && (
             <TimelineItem type="assistant" isLast={true}>
               <div className="flex items-center gap-1.5 text-gray-500 text-xs">
                 <span className="w-1.5 h-1.5 bg-primary-500 rounded-full animate-pulse" />
                 Thinking...
                 {currentRunId && (
                   <span className="text-[9px] text-gray-600 font-mono ml-1.5">
                     {currentRunId.slice(0, 8)}
                   </span>
                 )}
               </div>
             </TimelineItem>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="relative mt-auto">
        <div className="absolute inset-0 bg-gradient-to-t from-background to-transparent -top-10 pointer-events-none" />
        
        {/* Show Continue button when there are pending tool_calls */}
        {hasPendingToolCalls && !isStreaming ? (
          <div className="bg-surface border border-border rounded-xl shadow-2xl p-4 flex flex-col gap-3">
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Play className="w-4 h-4 text-primary-400" />
              <span>This session has pending tool calls that need to be executed.</span>
            </div>
            <button
              onClick={handleContinue}
              className="w-full py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-500 transition-colors flex items-center justify-center gap-2 font-medium"
            >
              <Play className="w-5 h-5" />
              Continue
            </button>
          </div>
        ) : (
          <div className="bg-surface border border-border rounded-xl shadow-2xl p-2 flex gap-2 items-end transition-all focus-within:ring-2 focus-within:ring-primary-500/50 focus-within:border-primary-500">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder="Ask anything..."
              disabled={isStreaming}
              rows={1}
              className="flex-1 px-4 py-3 bg-transparent text-white placeholder-gray-500 focus:outline-none resize-none min-h-[48px] max-h-[200px]"
              style={{ height: 'auto', minHeight: '48px' }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement
                target.style.height = 'auto'
                target.style.height = `${target.scrollHeight}px`
              }}
            />
            {isStreaming ? (
              <button
                onClick={handleCancel}
                className="p-3 bg-red-600 text-white rounded-lg hover:bg-red-500 transition-colors mb-0.5"
                title="Cancel"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                </svg>
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="p-3 bg-primary-600 text-white rounded-lg hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors mb-0.5"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            )}
          </div>
        )}
        <div className="text-center mt-2">
          <span className="text-xs text-gray-600">
            Powered by Agio • AI Agent Framework
          </span>
        </div>
      </div>

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
