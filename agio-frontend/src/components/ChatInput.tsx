/**
 * ChatInput - Input area component for chat messages
 */

import { Play } from 'lucide-react'

interface ChatInputProps {
  input: string
  setInput: (value: string) => void
  isStreaming: boolean
  hasPendingToolCalls: boolean
  onSend: () => void
  onCancel: () => void
  onContinue: () => void
}

export function ChatInput({
  input,
  setInput,
  isStreaming,
  hasPendingToolCalls,
  onSend,
  onCancel,
  onContinue,
}: ChatInputProps) {
  return (
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
            onClick={onContinue}
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
                onSend()
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
              onClick={onCancel}
              className="p-3 bg-red-600 text-white rounded-lg hover:bg-red-500 transition-colors mb-0.5"
              title="Cancel"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
              </svg>
            </button>
          ) : (
            <button
              onClick={onSend}
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
  )
}
