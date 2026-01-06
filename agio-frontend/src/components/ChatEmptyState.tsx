/**
 * ChatEmptyState - Empty state component when no messages
 */

import { MessageSquare, Cpu, Sparkles } from 'lucide-react'
import { getToolDisplayName, getToolKey } from '../utils/toolHelpers'

interface Agent {
  name?: string
  system_prompt?: string | null
  tools?: Array<any>
}

interface ChatEmptyStateProps {
  agent?: Agent
}

export function ChatEmptyState({ agent }: ChatEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center py-12 animate-in fade-in zoom-in duration-700">
      <div className="relative mb-6 group">
        <div className="absolute -inset-3 bg-gradient-to-tr from-primary-600 to-primary-400 rounded-full blur-xl opacity-10 group-hover:opacity-20 transition duration-500" />
        <div className="relative w-16 h-16 bg-white/5 border border-white/5 rounded-2xl flex items-center justify-center shadow-2xl backdrop-blur-sm">
          <MessageSquare className="w-8 h-8 text-primary-500/80" />
        </div>
        <div className="absolute -bottom-1 -right-1 p-1 bg-[#0a0a0a] border border-white/5 rounded-lg shadow-xl">
          <Cpu className="w-3.5 h-3.5 text-emerald-500/70" />
        </div>
      </div>

      <div className="space-y-1.5 mb-6">
        <div className="flex items-center justify-center gap-2">
          <Sparkles className="w-3 h-3 text-primary-500/40" />
          <h2 className="text-xl font-black text-gray-200 tracking-tight uppercase tracking-wider">
            {agent?.name?.replace(/_/g, ' ') || 'Neural Link Ready'}
          </h2>
          <Sparkles className="w-3 h-3 text-primary-500/40" />
        </div>
        <div className="h-px w-10 bg-primary-500/20 mx-auto" />
      </div>

      <p className="text-gray-600 max-w-sm text-[13px] leading-relaxed font-bold mb-8 px-6 italic uppercase tracking-tight opacity-80">
        {agent?.system_prompt?.slice(0, 180) || 'Initialize a new instruction sequence to begin autonomous orchestration.'}
        {agent?.system_prompt && agent.system_prompt.length > 180 ? '...' : ''}
      </p>

      {agent?.tools && agent.tools.length > 0 && (
        <div className="space-y-3">
          <p className="text-[9px] font-black text-gray-800 uppercase tracking-[0.3em]">Registered Capability Modules</p>
          <div className="flex flex-wrap gap-1.5 justify-center max-w-lg px-4">
            {agent.tools.slice(0, 8).map((tool, idx) => (
              <span 
                key={getToolKey(tool, idx)} 
                className="px-2.5 py-1 text-[9px] font-black bg-white/5 border border-white/5 rounded-lg text-gray-600 hover:text-primary-400/80 hover:bg-white/[0.08] transition-all cursor-default uppercase tracking-widest"
              >
                {getToolDisplayName(tool)}
              </span>
            ))}
            {agent.tools.length > 8 && (
              <span className="px-2.5 py-1 text-[9px] font-black text-gray-800 uppercase tracking-widest">+{agent.tools.length - 8} OVERFLOW</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
