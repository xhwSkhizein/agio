import { RefObject } from 'react'
import { TimelineItem } from '../TimelineItem'
import { MessageContent } from '../MessageContent'
import { AgentExecutionCardV2 } from './AgentExecutionCardV2'
import type { ExecutionTree } from '../../types/execution'
import { Activity } from 'lucide-react'

interface ChatTimelineV2Props {
  tree: ExecutionTree
  isStreaming: boolean
  currentRunId: string | null
  scrollContainerRef: RefObject<HTMLDivElement>
  messagesEndRef: RefObject<HTMLDivElement>
  debugMode?: boolean
}

export function ChatTimelineV2({
  tree,
  isStreaming,
  currentRunId,
  scrollContainerRef,
  messagesEndRef,
  debugMode = false,
}: ChatTimelineV2Props) {
  // Interleave messages and executions by timestamp
  const items: Array<
    | { type: 'message'; data: typeof tree.messages[0] }
    | { type: 'execution'; data: typeof tree.executions[0] }
  > = []

  // Add messages
  for (const msg of tree.messages) {
    items.push({ type: 'message', data: msg })
  }

  // Add root executions
  for (const exec of tree.executions) {
    items.push({ type: 'execution', data: exec })
  }

  // Sort by timestamp/startTime
  items.sort((a, b) => {
    const timeA = a.type === 'message' ? a.data.timestamp : (a.data.startTime || 0)
    const timeB = b.type === 'message' ? b.data.timestamp : (b.data.startTime || 0)
    return timeA - timeB
  })

  return (
    <div
      ref={scrollContainerRef}
      className="flex-1 overflow-y-auto pr-4 -mr-4 mb-4"
    >
      <div className="space-y-0 -mt-1">
        {items.map((item, index) => {
          if (item.type === 'message') {
            const msg = item.data
            return (
              <TimelineItem
                key={msg.id}
                type={msg.type}
                isLast={index === items.length - 1 && !isStreaming}
              >
                <div className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm leading-relaxed ${
                  msg.type === 'error' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                  msg.type === 'user' ? 'bg-primary-600/20 text-primary-400 border border-primary-500/30 ml-auto' : 'bg-surface text-gray-300'
                }`}>
                  <MessageContent content={msg.content} />
                </div>
              </TimelineItem>
            )
          }

          // Execution
          const exec = item.data
          return (
            <TimelineItem
              key={exec.id}
              type="assistant"
              isLast={index === items.length - 1 && !isStreaming}
            >
              <AgentExecutionCardV2 
                execution={exec} 
                isRoot={true}
                debugMode={debugMode}
              />
            </TimelineItem>
          )
        })}

        {isStreaming && (
          <TimelineItem type="assistant" isLast={true}>
            <div className="flex items-center gap-2 text-blue-400 text-xs font-medium animate-pulse">
              <Activity className="w-3 h-3" />
              <span>Agent is thinking...</span>
              {currentRunId && (
                <span className="text-[10px] opacity-50 font-mono ml-1">
                  ({currentRunId.slice(0, 8)})
                </span>
              )}
            </div>
          </TimelineItem>
        )}

        <div ref={messagesEndRef} />
      </div>
    </div>
  )
}
