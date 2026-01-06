/**
 * ChatTimeline - Timeline component for displaying chat events
 * 
 * Uses unified ExecutionTree and RunnableExecutionView for display.
 */

import type { RefObject } from 'react'
import { TimelineItem } from './TimelineItem'
import { MessageContent } from './MessageContent'
import { RunnableExecutionView } from './RunnableExecutionView'
import type { ExecutionTree } from '../types/execution'

interface ChatTimelineProps {
  tree: ExecutionTree
  isStreaming: boolean
  currentRunId: string | null
  scrollContainerRef: RefObject<HTMLDivElement>
  messagesEndRef: RefObject<HTMLDivElement>
}

export function ChatTimeline({
  tree,
  isStreaming,
  currentRunId,
  scrollContainerRef,
  messagesEndRef,
}: ChatTimelineProps) {
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
                isLast={index === items.length - 1}
              >
                <div className={`max-w-[90%] rounded-2xl px-5 py-3 text-sm leading-relaxed shadow-sm transition-all duration-300 ${
                  msg.type === 'error' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                  msg.type === 'user' ? 'bg-primary-600/10 text-primary-400 border border-primary-500/20 ml-auto' : 'bg-white/5 text-gray-300 border border-white/5'
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
              isLast={index === items.length - 1}
            >
              <RunnableExecutionView 
                execution={exec} 
                isRoot={true}
              />
            </TimelineItem>
          )
        })}

        {isStreaming && items.length > 0 && (
          <TimelineItem type="assistant" isLast={true}>
            <div className="flex items-center gap-3 px-4 py-2 rounded-xl bg-white/5 border border-white/5 w-fit animate-pulse">
              <div className="flex items-center gap-1.5 text-primary-400 text-[10px] font-black uppercase tracking-[0.2em]">
                <div className="w-1.5 h-1.5 bg-primary-500 rounded-full animate-ping" />
                <span>Thinking</span>
              </div>
              {currentRunId && (
                <div className="h-3 w-px bg-white/10" />
              )}
              {currentRunId && (
                <span className="text-[9px] text-gray-600 font-black font-mono uppercase tracking-widest">
                  PROC_ID: {currentRunId.slice(0, 8)}
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
