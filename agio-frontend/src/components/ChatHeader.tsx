/**
 * ChatHeader - Header component with agent selector and settings
 */

import { ChevronDown, Plus, Settings } from 'lucide-react'

interface Agent {
  name: string
  system_prompt?: string | null
}

interface Workflow {
  id: string
  type: string
}

interface RunnableInfo {
  id?: string
  type?: string
}

interface ChatHeaderProps {
  selectedAgentId: string
  setSelectedAgentId: (id: string) => void
  showAgentDropdown: boolean
  setShowAgentDropdown: (show: boolean) => void
  agents?: { items?: Agent[] }
  runnables?: { workflows?: Workflow[] }
  agent?: Agent
  runnableInfo?: RunnableInfo
  isWorkflow: boolean
  onNewChat: () => void
  onOpenSettings: () => void
}

export function ChatHeader({
  selectedAgentId,
  setSelectedAgentId,
  showAgentDropdown,
  setShowAgentDropdown,
  agents,
  runnables,
  agent,
  runnableInfo,
  isWorkflow,
  onNewChat,
  onOpenSettings,
}: ChatHeaderProps) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-border mb-4">
      <div className="flex items-center gap-3">
        {/* New Chat Button */}
        <button
          onClick={onNewChat}
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
            {isWorkflow && (
              <span className="px-1.5 py-0.5 text-[10px] bg-primary-500/20 text-primary-400 rounded">
                {runnableInfo?.type?.replace('Workflow', '') || 'WF'}
              </span>
            )}
            <span className="text-sm font-medium text-white">
              {isWorkflow
                ? (runnableInfo?.id || selectedAgentId)?.replace(/_/g, ' ')
                : agent?.name?.replace(/_/g, ' ') || 'Select Agent'}
            </span>
            <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${showAgentDropdown ? 'rotate-180' : ''}`} />
          </button>

          {showAgentDropdown && (
            <div className="absolute top-full left-0 mt-1 w-72 bg-surface border border-border rounded-lg shadow-xl z-50 py-1 max-h-96 overflow-y-auto">
              {/* Workflows Section */}
              {runnables?.workflows && runnables.workflows.length > 0 && (
                <>
                  <div className="px-3 py-2 text-xs font-semibold text-primary-400 uppercase tracking-wider border-b border-border">
                    Workflows
                  </div>
                  {runnables.workflows.map((w) => (
                    <button
                      key={w.id}
                      onClick={() => {
                        setSelectedAgentId(w.id)
                        setShowAgentDropdown(false)
                      }}
                      className={`w-full text-left px-3 py-2 hover:bg-surfaceHighlight transition-colors ${
                        selectedAgentId === w.id ? 'bg-surfaceHighlight' : ''
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 text-[10px] bg-primary-500/20 text-primary-400 rounded">
                          {w.type.replace('Workflow', '')}
                        </span>
                        <span className="text-sm font-medium text-white">{w.id.replace(/_/g, ' ')}</span>
                      </div>
                    </button>
                  ))}
                </>
              )}

              {/* Agents Section */}
              <div className="px-3 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-border mt-1">
                Agents
              </div>
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
        onClick={onOpenSettings}
        className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
        title="Agent Settings"
      >
        <Settings className="w-5 h-5" />
      </button>
    </div>
  )
}
