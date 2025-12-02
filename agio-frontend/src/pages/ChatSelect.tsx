import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { agentService } from '../services/api'
import { MessageSquare } from 'lucide-react'

export default function ChatSelect() {
  const { data: agents, isLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentService.listAgents(),
  })

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white mb-2">Chat</h1>
        <p className="text-gray-400">Select an agent to start a conversation.</p>
      </div>

      {isLoading ? (
        <div className="text-gray-500">Loading agents...</div>
      ) : agents?.items.length === 0 ? (
        <div className="bg-surface border border-border rounded-lg p-8 text-center">
          <MessageSquare className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400 mb-4">No agents configured yet.</p>
          <Link
            to="/config"
            className="text-primary-400 hover:text-primary-300 text-sm"
          >
            Configure an agent →
          </Link>
        </div>
      ) : (
        <div className="grid gap-3">
          {agents?.items.map((agent) => (
            <Link
              key={agent.name}
              to={`/chat/${agent.name}`}
              className="bg-surface border border-border rounded-lg p-4 hover:border-primary-500/50 transition-all flex items-center gap-4 group"
            >
              <div className="w-10 h-10 bg-primary-600/20 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="text-primary-400 font-medium">
                  {agent.name.charAt(0).toUpperCase()}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-white group-hover:text-primary-400 transition-colors">
                  {agent.name.replace(/_/g, ' ')}
                </div>
                {agent.system_prompt && (
                  <p className="text-xs text-gray-500 truncate mt-0.5">
                    {agent.system_prompt.slice(0, 100)}
                  </p>
                )}
              </div>
              <div className="text-xs text-gray-600">
                {agent.tools.length} tools
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
