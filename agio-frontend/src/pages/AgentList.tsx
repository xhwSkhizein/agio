import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { agentService } from '../services/api'

export default function AgentList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentService.listAgents(),
  })

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-400">Loading...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-error">
        Error loading agents: {(error as Error).message}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-white">
          Agents
        </h1>
        <Link 
          to="/config/new"
          className="px-3 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-500 transition-colors text-sm"
        >
          Create Agent
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.items.map((agent) => (
          <AgentCard key={agent.id} agent={agent} />
        ))}
      </div>

      {data?.items.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          No agents found
        </div>
      )}
    </div>
  )
}

interface AgentCardProps {
  agent: {
    id: string
    name: string
    description: string | null
    model: string
    tools: string[]
    enabled: boolean
    tags: string[]
  }
}

function AgentCard({ agent }: AgentCardProps) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4 hover:border-primary-500/50 transition-all duration-200 hover:shadow-lg group">
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="text-base font-semibold text-white group-hover:text-primary-400 transition-colors">
            {agent.name}
          </h3>
          {agent.description && (
            <p className="mt-1 text-xs text-gray-400 line-clamp-2">
              {agent.description}
            </p>
          )}
        </div>
        <span
          className={`px-1.5 py-0.5 text-[10px] rounded-full border ${
            agent.enabled
              ? 'bg-green-900/30 text-green-400 border-green-900'
              : 'bg-gray-800 text-gray-400 border-gray-700'
          }`}
        >
          {agent.enabled ? 'Active' : 'Inactive'}
        </span>
      </div>

      <div className="space-y-1.5 mb-4">
        <div className="text-xs text-gray-400">
          <span className="text-gray-500">Model:</span> {agent.model}
        </div>
        {agent.tools.length > 0 && (
          <div className="text-xs text-gray-400">
            <span className="text-gray-500">Tools:</span> {agent.tools.length}
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <Link
          to={`/chat/${agent.id}`}
          className="flex-1 px-3 py-1.5 bg-primary-600 text-white text-center rounded-lg hover:bg-primary-500 transition-colors text-xs"
        >
          Chat
        </Link>
        <Link 
          to={`/config/${agent.name}`}
          className="px-3 py-1.5 border border-border text-gray-300 rounded-lg hover:bg-surfaceHighlight transition-colors text-xs text-center"
        >
          Details
        </Link>
      </div>
    </div>
  )
}
