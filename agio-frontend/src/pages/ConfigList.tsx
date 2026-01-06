import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { configService, Config } from '../services/api'
import { RefreshCw, Trash2, Bot, Wrench, Database, Server, ChevronDown, Loader2, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'

// Type metadata for display
const TYPE_META: Record<string, { icon: typeof Bot; label: string; color: string; description: string }> = {
  agent: { 
    icon: Bot, 
    label: 'Agents', 
    color: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    description: 'AI agents with specific capabilities'
  },
  model: { 
    icon: Server, 
    label: 'Models', 
    color: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
    description: 'LLM model configurations'
  },
  tool: { 
    icon: Wrench, 
    label: 'Tools', 
    color: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    description: 'Tools available to agents'
  },
  repository: { 
    icon: Database, 
    label: 'Storage', 
    color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
    description: 'Data persistence for agent runs'
  },
}

// Order for display
const TYPE_ORDER = ['agent', 'model', 'tool', 'repository']

export default function ConfigList() {
  const queryClient = useQueryClient()
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set(['agent', 'model', 'tool']))

  const { data: configs, isLoading, error } = useQuery({
    queryKey: ['configs'],
    queryFn: () => configService.listConfigs(),
  })

  const reloadMutation = useMutation({
    mutationFn: () => configService.reloadConfigs(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['configs'] })
      toast.success('Configurations reloaded')
    },
    onError: (error) => {
      toast.error(`Failed to reload: ${(error as Error).message}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: ({ type, name }: { type: string; name: string }) => 
      configService.deleteConfig(type, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['configs'] })
      toast.success('Configuration deleted')
    },
    onError: () => {
      toast.error('Failed to delete configuration')
    },
  })

  const toggleType = (type: string) => {
    setExpandedTypes(prev => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 bg-white/5 border border-white/10 border-dashed rounded-3xl">
        <Loader2 className="w-10 h-10 text-primary-500 animate-spin mb-4" />
        <p className="text-gray-500 font-medium tracking-tight">Syncing system configurations...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center gap-3 p-6 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-400">
        <AlertCircle className="w-6 h-6 shrink-0" />
        <div>
          <p className="font-bold text-sm uppercase tracking-widest">Configuration Error</p>
          <p className="text-xs opacity-80 mt-1">{(error as Error).message}</p>
        </div>
      </div>
    )
  }

  // Group configs by type and ensure each config has type field
  const configsByType: Record<string, Config[]> = {}
  if (configs) {
    Object.entries(configs).forEach(([type, items]) => {
      if (Array.isArray(items) && items.length > 0) {
        configsByType[type] = items
          .map((item: any) => ({
            ...item,
            type: item.type || type,
          }))
          .filter((item: Config) => item.name && item.type)
      }
    })
  }

  const sortedTypes = Object.keys(configsByType).sort((a, b) => {
    const aIndex = TYPE_ORDER.indexOf(a)
    const bIndex = TYPE_ORDER.indexOf(b)
    if (aIndex === -1 && bIndex === -1) return a.localeCompare(b)
    if (aIndex === -1) return 1
    if (bIndex === -1) return -1
    return aIndex - bIndex
  })

  return (
    <div className="max-w-6xl mx-auto px-4 py-4 space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-200 tracking-tight mb-1 flex items-center gap-2.5 uppercase tracking-wider">
            <Server className="w-6 h-6 text-primary-500/80" />
            Configuration
          </h1>
          <p className="text-gray-500 text-[13px] font-medium">Orchestrate your system components: agents, models, tools, and repositories.</p>
        </div>
        <button 
          onClick={() => reloadMutation.mutate()}
          disabled={reloadMutation.isPending}
          className="group flex items-center gap-1.5 px-4 py-2 bg-primary-600/90 text-white rounded-xl text-[11px] font-black hover:bg-primary-500 transition-all shadow-lg shadow-primary-500/10 active:scale-95 disabled:opacity-50 disabled:shadow-none uppercase tracking-widest"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${reloadMutation.isPending ? 'animate-spin' : 'group-hover:rotate-180 transition-transform duration-500'}`} />
          RELOAD ALL
        </button>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {TYPE_ORDER.map(type => {
          const meta = TYPE_META[type]
          const count = configsByType[type]?.length || 0
          const Icon = meta?.icon || Server
          return (
            <div 
              key={type}
              className={`p-4 rounded-2xl border transition-all cursor-pointer group hover:bg-white/[0.03] ${meta?.color || 'text-gray-500 bg-white/5 border-white/5'}`}
              onClick={() => {
                if (count > 0) {
                  setExpandedTypes(new Set([type]))
                  document.getElementById(`section-${type}`)?.scrollIntoView({ behavior: 'smooth' })
                }
              }}
            >
              <div className="flex items-center justify-between mb-3">
                <div className={`p-1.5 rounded-lg bg-black/20 ${meta?.color.split(' ')[0]}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="text-[9px] font-black uppercase tracking-[0.2em] opacity-40">{meta?.label || type}</div>
              </div>
              <div className="flex items-end justify-between">
                <div className="text-2xl font-black tracking-tighter text-gray-200">{count}</div>
                <div className="text-[9px] font-black text-gray-700 group-hover:text-gray-500 transition-colors uppercase tracking-widest">Active Units</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Grouped Sections */}
      <div className="space-y-4">
        {sortedTypes.map(type => {
          const items = configsByType[type]
          const meta = TYPE_META[type]
          const Icon = meta?.icon || Server
          const isExpanded = expandedTypes.has(type)

          return (
            <div 
              key={type} 
              id={`section-${type}`}
              className="bg-white/5 border border-white/5 rounded-3xl overflow-hidden shadow-sm"
            >
              {/* Section Header */}
              <button
                onClick={() => toggleType(type)}
                className="w-full flex items-center justify-between p-5 hover:bg-white/[0.03] transition-all group"
              >
                <div className="flex items-center gap-4">
                  <div className={`p-2.5 rounded-xl shadow-inner border border-white/5 ${meta?.color || 'bg-white/5'}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="text-left">
                    <div className="flex items-center gap-2.5">
                      <h2 className="text-lg font-bold text-gray-200 tracking-tight uppercase tracking-wider">
                        {meta?.label || type}
                      </h2>
                      <span className="px-1.5 py-0.5 rounded bg-black/40 border border-white/5 text-[9px] font-bold text-gray-600 font-mono tracking-tighter">{items.length} COMPONENT{items.length !== 1 ? 'S' : ''}</span>
                    </div>
                    <p className="text-[10px] text-gray-600 font-bold mt-0.5 uppercase tracking-[0.15em]">{meta?.description}</p>
                  </div>
                </div>
                <div className={`p-1.5 rounded-lg transition-all ${isExpanded ? 'rotate-180 bg-white/10 text-white' : 'text-gray-700 group-hover:text-gray-500'}`}>
                  <ChevronDown className="w-4 h-4" />
                </div>
              </button>

              {/* Section Content */}
              {isExpanded && (
                <div className="border-t border-white/5 bg-black/20 p-5">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {items
                      .filter((config) => config.type && config.name)
                      .map((config, index) => (
                        <ConfigCard 
                          key={`${config.type}-${config.name}-${index}`} 
                          config={config}
                          typeMeta={meta}
                          onDelete={(type, name) => {
                            if (confirm(`Irreversible Action: Are you sure you want to delete ${name}?`)) {
                              deleteMutation.mutate({ type, name })
                            }
                          }}
                        />
                      ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {sortedTypes.length === 0 && (
        <div className="text-center py-24 bg-white/5 border border-white/10 border-dashed rounded-3xl">
          <div className="p-6 rounded-full bg-white/5 w-fit mx-auto mb-6">
            <Server className="w-12 h-12 text-gray-700 opacity-30" />
          </div>
          <h3 className="text-lg font-bold text-gray-400 mb-2">System Empty</h3>
          <p className="text-sm text-gray-600 max-w-xs mx-auto">No components detected. Add configuration files to your YAML directory to populate this view.</p>
        </div>
      )}
    </div>
  )
}

interface ConfigCardProps {
  config: Config
  typeMeta?: { icon: typeof Bot; label: string; color: string }
  onDelete: (type: string, name: string) => void
}

function ConfigCard({ config, onDelete }: ConfigCardProps) {
  return (
    <Link
      to={`/config/${config.type}/${config.name}`}
      className="block relative bg-black/40 border border-white/5 rounded-2xl p-4 hover:border-primary-500/30 hover:bg-white/[0.05] transition-all duration-200 group overflow-hidden shadow-sm"
    >
      {/* Glow effect */}
      <div className="absolute -inset-1 bg-gradient-to-r from-primary-500/0 to-primary-500/0 group-hover:from-primary-500/5 group-hover:to-transparent blur-xl transition-all" />

      {/* Delete button - appears on hover */}
      <button 
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onDelete(config.type, config.name)
        }}
        className="absolute top-2.5 right-2.5 p-1.5 text-gray-700 hover:text-red-400 hover:bg-red-500/10 rounded-lg opacity-0 group-hover:opacity-100 transition-all z-20"
        title="Delete"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>

      <div className="relative z-10">
        <div className="flex justify-between items-start mb-1.5 pr-6">
          <h3 className="text-sm font-bold text-gray-300 group-hover:text-primary-400/90 transition-colors truncate tracking-tight uppercase">
            {config.name}
          </h3>
          {config.enabled === false && (
            <span className="px-1.5 py-0.5 text-[8px] font-black uppercase tracking-widest bg-gray-800/50 text-gray-600 rounded border border-white/5">
              OFFLINE
            </span>
          )}
        </div>
        
        {config.description ? (
          <p className="text-[11px] text-gray-600 line-clamp-2 mb-3 font-bold uppercase tracking-tighter leading-relaxed">
            {config.description}
          </p>
        ) : (
          <div className="h-3" />
        )}

        {config.tags && config.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-auto">
            {config.tags.slice(0, 3).map(tag => (
              <span key={tag} className="px-1.5 py-0.5 text-[8px] font-black bg-white/5 text-gray-700 rounded border border-white/5 uppercase tracking-tighter">
                {tag}
              </span>
            ))}
            {config.tags.length > 3 && (
              <span className="px-1.5 py-0.5 text-[8px] font-black text-gray-800">
                +{config.tags.length - 3}
              </span>
            )}
          </div>
        )}
      </div>
    </Link>
  )
}
