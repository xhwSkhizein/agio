/**
 * ChatTimeline - Timeline component for displaying chat events
 */

import type { RefObject } from 'react'
import { TimelineItem } from './TimelineItem'
import { ToolCall } from './ToolCall'
import { MessageContent } from './MessageContent'
import { WorkflowContainer } from './WorkflowContainer'
import { ParallelNestedRunnables } from './ParallelNestedRunnables'
import type { TimelineEvent } from '../types/chat'
import type { WorkflowNode } from '../types/workflow'

interface ChatTimelineProps {
  events: TimelineEvent[]
  workflowNodes: Map<string, WorkflowNode>
  isStreaming: boolean
  currentRunId: string | null
  scrollContainerRef: RefObject<HTMLDivElement>
  messagesEndRef: RefObject<HTMLDivElement>
}

export function ChatTimeline({
  events,
  workflowNodes,
  isStreaming,
  currentRunId,
  scrollContainerRef,
  messagesEndRef,
}: ChatTimelineProps) {
  return (
    <div
      ref={scrollContainerRef}
      className="flex-1 overflow-y-auto pr-4 -mr-4 mb-4"
    >
      <div className="space-y-0 -mt-1">
        {events.map((event, index) => (
          <TimelineItem
            key={event.id}
            type={event.type}
            isLast={index === events.length - 1}
            depth={event.nestedDepth || 0}
          >
            {event.type === 'workflow' && event.runId && workflowNodes.get(event.runId) ? (
              /* Workflow container */
              <WorkflowContainer
                workflow={workflowNodes.get(event.runId)!}
                renderEvent={(nestedEvent) => (
                  <div className={`text-xs leading-relaxed ${
                    nestedEvent.type === 'error' ? 'text-red-400' : 'text-gray-300'
                  }`}>
                    <MessageContent content={nestedEvent.content || ''} />
                  </div>
                )}
              />
            ) : event.type === 'tool' ? (
              <ToolCall
                toolName={event.toolName || 'Unknown Tool'}
                args={event.toolArgs || '{}'}
                result={event.toolResult}
                status={event.toolStatus || 'running'}
                duration={event.toolDuration}
              />
            ) : event.type === 'parallel_nested' && event.nestedExecutions ? (
              /* Parallel nested RunnableTool executions */
              <ParallelNestedRunnables
                executions={event.nestedExecutions}
              />
            ) : event.type === 'nested' ? (
              /* Legacy nested execution indicator */
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-2">
                <div className="flex items-center gap-2">
                  <span className="text-amber-400 text-xs">⚙️</span>
                  <span className="text-xs text-amber-300 font-medium">
                    {event.content}
                  </span>
                </div>
                {event.toolResult && (
                  <div className="mt-2 text-xs text-gray-400 bg-background/50 rounded p-2 max-h-32 overflow-y-auto">
                    <pre className="whitespace-pre-wrap break-words">{event.toolResult}</pre>
                  </div>
                )}
              </div>
            ) : (
              <div>
                {/* Reasoning content (thinking mode) - shown before main content */}
                {event.type === 'assistant' && event.reasoning_content && (
                  <div className="mb-2 rounded-lg border border-blue-500/30 bg-blue-500/10 p-2">
                    <details className="group">
                      <summary className="cursor-pointer text-[10px] text-blue-400 font-medium flex items-center gap-1.5 hover:text-blue-300">
                        <span className="transition-transform group-open:rotate-90">▶</span>
                        <span>Thinking</span>
                      </summary>
                      <div className="mt-2 text-[10px] text-blue-300/80 leading-relaxed">
                        <MessageContent content={event.reasoning_content} />
                      </div>
                    </details>
                  </div>
                )}
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
  )
}
