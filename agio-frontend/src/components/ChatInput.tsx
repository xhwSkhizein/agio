/**
 * ChatInput - Input area component for chat messages
 */

import { Play, Send, Square, Cpu } from 'lucide-react'

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
    <div className="relative mt-auto pt-4 pb-1">
      {/* Visual top fade to separate from timeline */}
      <div className="absolute inset-x-0 -top-8 h-8 bg-gradient-to-t from-[#050505] to-transparent pointer-events-none z-10" />

      {/* Action Area */}
      <div className="relative z-20">
        {hasPendingToolCalls && !isStreaming ? (
          <div className="bg-primary-500/5 border border-primary-500/10 rounded-3xl p-5 shadow-xl animate-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-1.5 rounded-xl bg-primary-500/10 text-primary-400/80">
                <Cpu className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[13px] font-bold text-gray-200 uppercase tracking-tight">Sequence Paused</p>
                <p className="text-[11px] text-gray-600 font-medium">Pending tool executions require explicit continuation.</p>
              </div>
            </div>
            <button
              onClick={onContinue}
              className="group w-full py-3 bg-primary-600/90 text-white rounded-xl hover:bg-primary-500 transition-all flex items-center justify-center gap-2 font-black text-xs tracking-widest shadow-lg shadow-primary-500/10 active:scale-[0.98]"
            >
              <Play className="w-4 h-4 fill-current group-hover:scale-110 transition-transform" />
              RESUME TRAJECTORY
            </button>
          </div>
        ) : (
          <div className={`relative group bg-white/5 border transition-all duration-300 rounded-[1.5rem] shadow-2xl flex flex-col overflow-hidden ${
            isStreaming ? 'border-blue-500/20 ring-1 ring-blue-500/5' : 'border-white/5 focus-within:border-primary-500/30 focus-within:ring-1 focus-within:ring-primary-500/10'
          }`}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  onSend()
                }
              }}
              placeholder={isStreaming ? "Agent is processing..." : "Initialize new instruction sequence..."}
              disabled={isStreaming}
              rows={1}
              className="w-full px-6 py-4 bg-transparent text-gray-200 placeholder-gray-700 focus:outline-none resize-none min-h-[60px] max-h-[200px] text-[15px] leading-relaxed selection:bg-primary-500/20 custom-scrollbar"
              style={{ height: 'auto' }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement
                target.style.height = 'auto'
                target.style.height = `${target.scrollHeight}px`
              }}
            />
            
            <div className="flex items-center justify-between px-5 pb-3 pt-1.5 border-t border-white/[0.03] bg-black/20">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5 opacity-30 hover:opacity-100 transition-opacity cursor-default">
                  <div className="w-1 h-1 rounded-full bg-emerald-500/60" />
                  <span className="text-[8px] font-black text-gray-600 uppercase tracking-widest">Kernel Ready</span>
                </div>
                <div className="text-[8px] font-bold text-gray-800 uppercase tracking-widest">Shift + Enter for new line</div>
              </div>

              {isStreaming ? (
                <button
                  onClick={onCancel}
                  className="flex items-center gap-1.5 px-4 py-2 bg-red-500/10 text-red-400/80 border border-red-500/10 rounded-lg hover:bg-red-500/20 transition-all font-black text-[9px] tracking-widest uppercase active:scale-95"
                  title="Abort execution"
                >
                  <Square className="w-3 h-3 fill-current" />
                  Abort
                </button>
              ) : (
                <button
                  onClick={onSend}
                  disabled={!input.trim()}
                  className="flex items-center gap-1.5 px-5 py-2 bg-primary-600/90 text-white rounded-lg hover:bg-primary-500 disabled:opacity-20 disabled:grayscale transition-all font-black text-[9px] tracking-widest uppercase shadow-lg shadow-primary-500/5 active:scale-95"
                >
                  <Send className="w-3 h-3" />
                  Execute
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-center gap-2 mt-3 opacity-20 hover:opacity-40 transition-opacity duration-500">
        <div className="h-px w-6 bg-gray-800" />
        <span className="text-[8px] font-black text-gray-700 uppercase tracking-[0.4em]">
          Agio Engine v0.8.2
        </span>
        <div className="h-px w-6 bg-gray-800" />
      </div>
    </div>
  )
}
