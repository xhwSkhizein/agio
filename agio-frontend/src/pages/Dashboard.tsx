import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { agentService } from '../services/api'
import {
  MessageSquare,
  Database,
  Brain,
  BarChart3,
  History,
  ArrowUpRight,
  RefreshCw,
} from 'lucide-react'

const exploreCards = [
  {
    title: 'Chat',
    description: 'Interact with your agents, teams and workflows.',
    icon: MessageSquare,
    path: '/chat',
  },
  {
    title: 'Knowledge',
    description: 'View and manage your knowledge bases.',
    icon: Database,
    path: '/knowledge',
  },
  {
    title: 'Memory',
    description: 'View and manage user memories and learnings.',
    icon: Brain,
    path: '/memory',
  },
  {
    title: 'Sessions',
    description: 'View and manage agents, teams and workflow sessions.',
    icon: History,
    path: '/sessions',
  },
  {
    title: 'Metrics',
    description: 'Monitor the usage of your agents, teams and workflows.',
    icon: BarChart3,
    path: '/metrics',
  },
]

export default function Dashboard() {
  const { data: agents, isLoading: agentsLoading, refetch } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentService.listAgents(),
  })


  return (
    <div className="max-w-5xl">
      {/* Welcome Header */}
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold text-white">
          Welcome to Agio
        </h1>
        <button
          onClick={() => refetch()}
          className="p-2 text-gray-400 hover:text-white hover:bg-surfaceHighlight rounded-lg transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Explore Section */}
      <div className="mb-8">
        <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-4">
          Explore
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {exploreCards.map((card) => {
            const Icon = card.icon
            return (
              <Link
                key={card.path}
                to={card.path}
                className="group bg-surface border border-border rounded-lg p-4 hover:border-primary-500/50 transition-all"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Icon className="w-4 h-4 text-gray-400" />
                    <span className="text-sm font-medium text-white">{card.title}</span>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-gray-600 group-hover:text-gray-400 transition-colors" />
                </div>
                <p className="text-xs text-gray-500 leading-relaxed">
                  {card.description}
                </p>
              </Link>
            )
          })}
        </div>
      </div>

      {/* Agents Section */}
      <div>
        <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-4">
          Agents
        </h2>

        {agentsLoading ? (
          <div className="text-sm text-gray-500">Loading agents...</div>
        ) : agents?.items.length === 0 ? (
          <div className="text-sm text-gray-500">No agents configured</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {agents?.items.map((agent) => (
              <AgentCard key={agent.name} agent={agent} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

interface AgentCardProps {
  agent: {
    name: string
    model: string
    tools: (string | { type?: string; name?: string | null; description?: string | null })[]
    system_prompt: string | null
  }
}

function AgentCard({ agent }: AgentCardProps) {
  return (
    <div className="bg-surface border border-border rounded-lg p-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-primary-600/20 rounded-lg flex items-center justify-center">
          <span className="text-primary-400 text-sm font-medium">
            {agent.name.charAt(0).toUpperCase()}
          </span>
        </div>
        <div>
          <div className="text-sm font-medium text-white uppercase tracking-wide">
            {agent.name.replace(/_/g, ' ')}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Link
          to={`/chat/${agent.name}`}
          className="px-3 py-1.5 text-xs font-medium text-gray-300 bg-surfaceHighlight border border-border rounded hover:bg-border transition-colors"
        >
          CHAT
        </Link>
        <Link
          to={`/config/agent/${agent.name}`}
          className="px-3 py-1.5 text-xs font-medium text-gray-300 bg-surfaceHighlight border border-border rounded hover:bg-border transition-colors"
        >
          CONFIG
        </Link>
      </div>
    </div>
  )
}
