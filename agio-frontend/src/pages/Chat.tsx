import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { agentService } from '../services/api'
import { TimelineItem } from '../components/TimelineItem'
import { ToolCall } from '../components/ToolCall'
import { MessageContent } from '../components/MessageContent'

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
}

export default function Chat() {
  const { agentId } = useParams<{ agentId: string }>()
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { data: agent } = useQuery({
    queryKey: ['agent', agentId],
    queryFn: () => agentService.getAgent(agentId!),
    enabled: !!agentId,
  })

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [events])

  const handleSend = async () => {
    if (!input.trim() || !agentId) return

    const userEvent: TimelineEvent = {
      id: Date.now().toString(),
      type: 'user',
      content: input,
      timestamp: Date.now(),
    }

    setEvents((prev) => [...prev, userEvent])
    setInput('')
    setIsStreaming(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          agent_id: agentId,
          message: input,
          stream: true,
        }),
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) return

      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let currentEvent = ''
        
        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            const dataStr = line.slice(5).trim()
            if (!dataStr) continue

            try {
              const data = JSON.parse(dataStr)
              
              setEvents((prev) => {
                const newEvents = [...prev]
                
                // Handle different event types
                switch (currentEvent) {
                  case 'text_delta': {
                    const lastEvent = newEvents[newEvents.length - 1]
                    if (lastEvent && lastEvent.type === 'assistant') {
                      lastEvent.content += data.content || ''
                    } else {
                      newEvents.push({
                        id: Date.now().toString(),
                        type: 'assistant',
                        content: data.content || '',
                        timestamp: Date.now(),
                      })
                    }
                    break
                  }
                  
                  case 'tool_call_started': {
                    newEvents.push({
                      id: data.tool_call_id,
                      type: 'tool',
                      toolName: data.tool_name,
                      toolArgs: data.arguments,
                      toolStatus: 'running',
                      timestamp: Date.now(),
                    })
                    break
                  }
                  
                  case 'tool_call_completed': {
                    const toolEventIndex = newEvents.findIndex(e => e.id === data.tool_call_id)
                    if (toolEventIndex !== -1) {
                      newEvents[toolEventIndex] = {
                        ...newEvents[toolEventIndex],
                        toolResult: data.result,
                        toolStatus: data.is_success ? 'completed' : 'failed',
                        toolDuration: data.duration,
                      }
                    }
                    break
                  }

                  case 'tool_call_failed': {
                    const toolEventIndex = newEvents.findIndex(e => e.id === data.tool_call_id)
                    if (toolEventIndex !== -1) {
                      newEvents[toolEventIndex] = {
                        ...newEvents[toolEventIndex],
                        toolResult: data.result || data.error,
                        toolStatus: 'failed',
                        toolDuration: data.duration,
                      }
                    }
                    break
                  }
                  
                  case 'error': {
                    newEvents.push({
                      id: Date.now().toString(),
                      type: 'error',
                      content: data.error,
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
      }
    } catch (error) {
      console.error('Streaming error:', error)
      setEvents(prev => [...prev, {
        id: Date.now().toString(),
        type: 'error',
        content: 'Failed to send message',
        timestamp: Date.now()
      }])
    } finally {
      setIsStreaming(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] max-w-4xl mx-auto p-4">
      {/* Header */}
      <div className="mb-8 pt-4">
        <h1 className="text-3xl font-bold text-white mb-2 tracking-tight">
          {agent?.name || 'Agio Chat'}
        </h1>
        <p className="text-gray-400 text-lg">
          {agent?.description || 'AI Agent Workspace'}
        </p>
      </div>

      {/* Timeline */}
      <div className="flex-1 overflow-y-auto pr-4 -mr-4 mb-4">
        <div className="space-y-0">
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
                <div className={`text-sm leading-relaxed ${
                  event.type === 'error' ? 'text-red-400' : 
                  event.type === 'user' ? 'text-white font-medium' : 'text-gray-300'
                }`}>
                  <MessageContent content={event.content || ''} />
                </div>
              )}
            </TimelineItem>
          ))}
          
          {isStreaming && events.length > 0 && events[events.length - 1].type !== 'assistant' && (
             <TimelineItem type="assistant" isLast={true}>
               <div className="flex items-center gap-2 text-gray-500 text-sm">
                 <span className="w-2 h-2 bg-primary-500 rounded-full animate-pulse" />
                 Thinking...
               </div>
             </TimelineItem>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="relative mt-auto">
        <div className="absolute inset-0 bg-gradient-to-t from-background to-transparent -top-10 pointer-events-none" />
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
          <button
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
            className="p-3 bg-primary-600 text-white rounded-lg hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors mb-0.5"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
        <div className="text-center mt-2">
          <span className="text-xs text-gray-600">
            Powered by Agio • AI Agent Framework
          </span>
        </div>
      </div>
    </div>
  )
}
