import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { agentService } from '../services/api'
import {
  MessageSquare,
  History,
  ArrowUpRight,
  RefreshCw,
  Layout,
  Activity,
  ChevronRight,
  Sparkles
} from 'lucide-react'

const exploreCards = [
  {
    title: 'Chat',
    description: 'Engage with orchestrators and specialized agents in a narrative execution environment.',
    icon: MessageSquare,
    path: '/chat',
    color: 'text-primary-400',
    bg: 'bg-primary-500/10',
  },
  {
    title: 'Sessions',
    description: 'Review and fork previous conversation trajectories and execution logs.',
    icon: History,
    path: '/sessions',
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
  },
  {
    title: 'Traces',
    description: 'Deep dive into performance metrics and LLM interaction waterfalls.',
    icon: Activity,
    path: '/traces',
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
  },
]

export default function Dashboard() {
  const { data: agents, isLoading: agentsLoading, refetch } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentService.listAgents(),
  })

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-10 animate-in fade-in duration-700">
      {/* Welcome Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <div className="p-1 rounded-lg bg-primary-500/10 text-primary-500/80">
              <Sparkles className="w-3.5 h-3.5" />
            </div>
            <span className="text-[9px] font-black text-gray-700 uppercase tracking-[0.3em]">System Overview</span>
          </div>
          <h1 className="text-3xl font-bold text-gray-200 tracking-tight uppercase tracking-wider">
            Welcome to Agio
          </h1>
          <p className="text-gray-500 mt-1.5 max-w-lg leading-relaxed text-[13px] font-medium">
            Your unified control plane for autonomous agent orchestration and trajectory monitoring.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="group flex items-center gap-1.5 px-3 py-1.5 bg-white/5 border border-white/5 rounded-lg text-[11px] font-black tracking-widest text-gray-500 hover:text-gray-300 transition-all"
        >
          <RefreshCw className="w-3.5 h-3.5 group-hover:rotate-180 transition-transform duration-500" />
          REFRESH ENGINE
        </button>
      </div>

      {/* Explore Section */}
      <div className="space-y-4">
        <h2 className="text-[10px] font-black text-gray-700 uppercase tracking-[0.25em] ml-1">
          CORE CAPABILITIES
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {exploreCards.map((card) => {
            const Icon = card.icon
            return (
              <Link
                key={card.path}
                to={card.path}
                className="group relative bg-white/5 border border-white/5 rounded-2xl p-5 hover:border-white/10 hover:bg-white/[0.08] transition-all duration-300 shadow-sm overflow-hidden"
              >
                <div className="relative z-10">
                  <div className="flex items-start justify-between mb-4">
                    <div className={`p-2.5 rounded-xl ${card.bg} ${card.color} shadow-inner border border-white/5 opacity-80 group-hover:opacity-100 transition-opacity`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="p-1.5 rounded-lg bg-white/5 group-hover:bg-white/10 transition-colors">
                      <ArrowUpRight className="w-3.5 h-3.5 text-gray-700 group-hover:text-gray-400 transition-colors" />
                    </div>
                  </div>
                  <h3 className="text-base font-bold text-gray-300 mb-1.5 group-hover:text-primary-400/90 transition-colors uppercase tracking-tight">{card.title}</h3>
                  <p className="text-[11px] text-gray-600 leading-relaxed font-bold uppercase tracking-tighter opacity-80">
                    {card.description}
                  </p>
                </div>
                
                {/* Background Decoration */}
                <div className={`absolute -right-4 -bottom-4 w-24 h-24 rounded-full ${card.bg} blur-3xl opacity-0 group-hover:opacity-20 transition-opacity duration-500`} />
              </Link>
            )
          })}
        </div>
      </div>

      {/* Agents Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-[10px] font-black text-gray-700 uppercase tracking-[0.25em]">
            ACTIVE AGENTS
          </h2>
          <Link to="/config" className="text-[9px] font-black text-primary-500/80 hover:text-primary-400 tracking-widest uppercase">Manage Configurations</Link>
        </div>

        {agentsLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-24 bg-white/5 rounded-2xl border border-white/10 border-dashed animate-pulse" />
            ))}
          </div>
        ) : !agents || agents?.items.length === 0 ? (
          <div className="bg-white/5 border border-white/10 border-dashed rounded-3xl p-16 text-center">
            <Layout className="w-16 h-16 text-gray-700 mx-auto mb-4 opacity-20" />
            <h3 className="text-lg font-bold text-gray-400 mb-2">No Agents Available</h3>
            <p className="text-sm text-gray-600 max-w-xs mx-auto font-medium">Configure your first agent in the settings panel to begin orchestrating.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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
    <div className="group relative bg-white/5 border border-white/5 rounded-2xl p-4 hover:border-primary-500/30 hover:bg-white/[0.08] transition-all duration-200">
      <div className="flex items-center justify-between relative z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary-500/10 rounded-xl flex items-center justify-center border border-primary-500/20 group-hover:bg-primary-500/20 transition-colors shadow-inner">
            <span className="text-primary-500/80 text-base font-black uppercase">
              {agent.name.charAt(0)}
            </span>
          </div>
          <div>
            <div className="text-[13px] font-bold text-gray-300 uppercase tracking-tight group-hover:text-primary-400/90 transition-colors">
              {agent.name.replace(/_/g, ' ')}
            </div>
            <div className="text-[9px] font-bold font-mono text-gray-700 mt-0.5 uppercase tracking-tighter">
              MODEL: {agent.model.split('/').pop()}
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-1.5">
          <Link
            to={`/chat/${agent.name}`}
            className="p-1.5 rounded-lg bg-white/5 text-gray-600 hover:text-primary-400/80 hover:bg-primary-500/10 transition-all border border-transparent hover:border-primary-500/10"
            title="Start Chat"
          >
            <MessageSquare className="w-3.5 h-3.5" />
          </Link>
          <Link
            to={`/config/agent/${agent.name}`}
            className="p-1.5 rounded-lg bg-white/5 text-gray-600 hover:text-gray-300 hover:bg-white/10 transition-all border border-transparent hover:border-white/10"
            title="Configure"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
      
      {/* Activity Indicator Decoration */}
      <div className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] opacity-0 group-hover:opacity-100 transition-opacity" />
    </div>
  )
}
