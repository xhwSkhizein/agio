/**
 * ChatEmptyState - Empty state component when no messages
 */

import { MessageSquare } from 'lucide-react'
import { getToolDisplayName, getToolKey } from '../utils/toolHelpers'

interface Agent {
  name?: string
  system_prompt?: string
  tools?: Array<any>
}

interface ChatEmptyStateProps {
  agent?: Agent
}

export function ChatEmptyState({ agent }: ChatEmptyStateProps) {
  return (
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
          {agent.tools.slice(0, 6).map((tool, idx) => (
            <span key={getToolKey(tool, idx)} className="px-2 py-1 text-xs bg-surface border border-border rounded text-gray-400">
              {getToolDisplayName(tool)}
            </span>
          ))}
          {agent.tools.length > 6 && (
            <span className="px-2 py-1 text-xs text-gray-500">+{agent.tools.length - 6} more</span>
          )}
        </div>
      )}
    </div>
  )
}
