/**
 * ChatHeader - Header component with agent selector and settings
 */

import { Link } from 'react-router-dom'
import { ChevronDown, Plus, Settings, UserCircle2, Cpu } from 'lucide-react'

interface Agent {
  name: string
  system_prompt?: string | null
}

interface ChatHeaderProps {
  selectedAgentId: string
  setSelectedAgentId: (id: string) => void
  showAgentDropdown: boolean
  setShowAgentDropdown: (show: boolean) => void
  agents?: { items?: Agent[] }
  agent?: Agent
  onNewChat: () => void
  onOpenSettings: () => void
}

export function ChatHeader({
  selectedAgentId,
  setSelectedAgentId,
  showAgentDropdown,
  setShowAgentDropdown,
  agents,
  agent,
  onNewChat,
  onOpenSettings,
}: ChatHeaderProps) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-white/5 mb-4 bg-[#0a0a0a]/50 backdrop-blur-xl sticky top-0 z-30 px-2 rounded-2xl mt-1.5">
      <div className="flex items-center gap-3">
        {/* New Chat Button */}
        <button
          onClick={onNewChat}
          className="group p-2 bg-white/5 text-gray-600 hover:text-gray-300 hover:bg-white/10 border border-white/5 rounded-lg transition-all duration-300 active:scale-95 shadow-sm"
          title="Initialize New Narrative"
        >
          <Plus className="w-4 h-4 group-hover:rotate-90 transition-transform duration-300" />
        </button>

        <div className="h-6 w-px bg-white/5 mx-0.5" />

        {/* Agent Selector Dropdown */}
        <div className="relative" data-agent-dropdown>
          <button
            onClick={() => setShowAgentDropdown(!showAgentDropdown)}
            className="flex items-center gap-2.5 px-3 py-1.5 bg-black/40 border border-white/5 rounded-xl hover:border-primary-500/30 hover:bg-white/5 transition-all group shadow-inner"
          >
            <div className="w-5 h-5 rounded bg-primary-500/10 flex items-center justify-center border border-primary-500/20 group-hover:bg-primary-500/20 transition-colors">
              <Cpu className="w-3 h-3 text-primary-500/80" />
            </div>
            <div className="flex flex-col items-start">
              <span className="text-[8px] font-black text-gray-700 uppercase tracking-widest leading-none mb-0.5">Active Orchestrator</span>
              <span className="text-[13px] font-bold text-gray-200 tracking-tight leading-none">
                {agent?.name?.replace(/_/g, ' ') || 'Select Neural Link'}
              </span>
            </div>
            <ChevronDown className={`w-3.5 h-3.5 text-gray-700 group-hover:text-gray-500 transition-all duration-300 ml-1 ${showAgentDropdown ? 'rotate-180 text-primary-500/80' : ''}`} />
          </button>

          {showAgentDropdown && (
            <div className="absolute top-full left-0 mt-2 w-72 bg-[#0f0f0f] border border-white/5 rounded-2xl shadow-2xl z-50 py-2 animate-in fade-in slide-in-from-top-2 duration-300 overflow-hidden ring-1 ring-black">
              {/* Agents Section */}
              <div className="px-4 py-1.5 mb-1.5">
                <span className="text-[8px] font-black text-gray-800 uppercase tracking-[0.3em]">Available Logical Units</span>
              </div>
              
              <div className="max-h-80 overflow-y-auto custom-scrollbar px-1.5 space-y-0.5">
                {agents?.items?.map((a) => (
                  <button
                    key={a.name}
                    onClick={() => {
                      setSelectedAgentId(a.name)
                      setShowAgentDropdown(false)
                    }}
                    className={`w-full text-left px-3.5 py-2.5 rounded-xl transition-all duration-200 group/item ${
                      selectedAgentId === a.name 
                        ? 'bg-primary-500/5 border border-primary-500/10' 
                        : 'hover:bg-white/[0.02] border border-transparent'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <div className="text-[13px] font-bold text-gray-300 group-hover/item:text-gray-100 transition-colors">{a.name.replace(/_/g, ' ')}</div>
                      {selectedAgentId === a.name && <div className="w-1 h-1 rounded-full bg-primary-500/60 shadow-[0_0_8px_rgba(59,130,246,0.4)]" />}
                    </div>
                    <div className="text-[9px] text-gray-700 font-bold line-clamp-1 group-hover/item:text-gray-600 transition-colors uppercase tracking-tight italic">
                      {a.system_prompt?.slice(0, 60) || 'Generic AI Intelligence Unit'}
                    </div>
                  </button>
                ))}
              </div>
              
              <div className="mt-2 pt-2 border-t border-white/5 px-4 flex items-center justify-between">
                <span className="text-[8px] font-bold text-gray-800 italic">Agio Kernel v0.8.2</span>
                <Link to="/config" className="text-[8px] font-black text-primary-500/80 hover:text-primary-400 uppercase tracking-widest">Register New Unit</Link>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right side - Settings */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-white/5 rounded-full border border-white/5 mr-1.5">
          <div className="w-1 h-1 rounded-full bg-emerald-500/60 animate-pulse" />
          <span className="text-[8px] font-black text-gray-700 uppercase tracking-widest">Uplink Stable</span>
        </div>
        
        <button
          onClick={onOpenSettings}
          className="group p-2 text-gray-600 hover:text-gray-300 hover:bg-white/10 border border-white/5 rounded-lg transition-all duration-300 active:scale-95"
          title="Orchestrator Protocol Settings"
        >
          <Settings className="w-4 h-4 group-hover:rotate-45 transition-transform duration-500" />
        </button>
        
        <div className="w-9 h-9 rounded-lg bg-white/5 border border-white/5 flex items-center justify-center text-gray-700 hover:text-gray-500 transition-colors cursor-default">
          <UserCircle2 className="w-5 h-5" />
        </div>
      </div>
    </div>
  )
}
