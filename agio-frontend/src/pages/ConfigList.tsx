import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { configService, Config } from '../services/api'
import { RefreshCw, Trash2, Bot, Wrench, Database, Brain, BookOpen, Server, ChevronDown, ChevronRight } from 'lucide-react'
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
  memory: { 
    icon: Brain, 
    label: 'Memory', 
    color: 'text-green-400 bg-green-500/10 border-green-500/30',
    description: 'Conversation memory backends'
  },
  knowledge: { 
    icon: BookOpen, 
    label: 'Knowledge', 
    color: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30',
    description: 'Knowledge bases and RAG sources'
  },
}

// Order for display
const TYPE_ORDER = ['agent', 'model', 'tool', 'repository', 'memory', 'knowledge']

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
      if (next.has(type)) {
        next.delete(type)
      } else {
        next.add(type)
      }
      return next
    })
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-400">Loading configurations...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-red-400 bg-red-900/20 border border-red-500/30 rounded-lg p-4">
        Error loading configurations: {(error as Error).message}
      </div>
    )
  }

  // Group configs by type and ensure each config has type field
  const configsByType: Record<string, Config[]> = {}
  if (configs) {
    Object.entries(configs).forEach(([type, items]) => {
      if (Array.isArray(items) && items.length > 0) {
        // Ensure each config item has the type field (from the key)
        configsByType[type] = items
          .map((item: any) => ({
            ...item,
            type: item.type || type,
          }))
          .filter((item: Config) => item.name && item.type) // Filter out items without name or type
      }
    })
  }

  // Sort types by predefined order
  const sortedTypes = Object.keys(configsByType).sort((a, b) => {
    const aIndex = TYPE_ORDER.indexOf(a)
    const bIndex = TYPE_ORDER.indexOf(b)
    if (aIndex === -1 && bIndex === -1) return a.localeCompare(b)
    if (aIndex === -1) return 1
    if (bIndex === -1) return -1
    return aIndex - bIndex
  })

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-white">Configuration</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage agents, models, tools, and other system components
          </p>
        </div>
        <button 
          onClick={() => reloadMutation.mutate()}
          disabled={reloadMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-500 disabled:opacity-50 text-sm transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${reloadMutation.isPending ? 'animate-spin' : ''}`} />
          Reload All
        </button>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {TYPE_ORDER.map(type => {
          const meta = TYPE_META[type]
          const count = configsByType[type]?.length || 0
          const Icon = meta?.icon || Server
          return (
            <div 
              key={type}
              className={`p-3 rounded-lg border ${meta?.color || 'text-gray-400 bg-gray-500/10 border-gray-500/30'} cursor-pointer hover:opacity-80 transition-opacity`}
              onClick={() => {
                if (count > 0) {
                  setExpandedTypes(new Set([type]))
                  document.getElementById(`section-${type}`)?.scrollIntoView({ behavior: 'smooth' })
                }
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <Icon className="w-4 h-4" />
                <span className="text-xs font-medium">{meta?.label || type}</span>
              </div>
              <div className="text-2xl font-bold">{count}</div>
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
              className="bg-surface border border-border rounded-xl overflow-hidden"
            >
              {/* Section Header */}
              <button
                onClick={() => toggleType(type)}
                className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${meta?.color || 'bg-gray-500/10'}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="text-left">
                    <h2 className="text-lg font-medium text-white">
                      {meta?.label || type}
                      <span className="ml-2 text-sm text-gray-500">({items.length})</span>
                    </h2>
                    <p className="text-xs text-gray-500">{meta?.description}</p>
                  </div>
                </div>
                {isExpanded ? (
                  <ChevronDown className="w-5 h-5 text-gray-400" />
                ) : (
                  <ChevronRight className="w-5 h-5 text-gray-400" />
                )}
              </button>

              {/* Section Content */}
              {isExpanded && (
                <div className="border-t border-border">
                  <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {items
                      .filter((config) => config.type && config.name)
                      .map((config, index) => (
                        <ConfigCard 
                          key={`${config.type}-${config.name}-${index}`} 
                          config={config}
                          typeMeta={meta}
                          onDelete={(type, name) => {
                            if (confirm(`Are you sure you want to delete ${name}?`)) {
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
        <div className="text-center py-16 text-gray-400">
          <Server className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No configurations found</p>
          <p className="text-sm mt-1">Add configuration files to the configs directory</p>
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
      className="block bg-background border border-border rounded-lg p-3 hover:border-primary-500/50 hover:bg-white/[0.02] transition-all group relative cursor-pointer"
    >
      {/* Delete button - appears on hover */}
      <button 
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onDelete(config.type, config.name)
        }}
        className="absolute top-2 right-2 p-1.5 text-gray-600 hover:text-red-400 hover:bg-red-900/20 rounded opacity-0 group-hover:opacity-100 transition-all"
        title="Delete"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>

      <div className="flex justify-between items-start mb-1 pr-6">
        <h3 className="text-sm font-medium text-white group-hover:text-primary-400 transition-colors truncate">
          {config.name}
        </h3>
        {config.enabled === false && (
          <span className="px-1.5 py-0.5 text-[10px] bg-gray-700 text-gray-400 rounded flex-shrink-0">
            Disabled
          </span>
        )}
      </div>
      
      {config.description && (
        <p className="text-xs text-gray-500 line-clamp-2 mb-2">
          {config.description}
        </p>
      )}

      {config.tags && config.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {config.tags.slice(0, 3).map(tag => (
            <span key={tag} className="px-1.5 py-0.5 text-[10px] bg-surfaceHighlight text-gray-400 rounded">
              {tag}
            </span>
          ))}
          {config.tags.length > 3 && (
            <span className="px-1.5 py-0.5 text-[10px] text-gray-500">
              +{config.tags.length - 3}
            </span>
          )}
        </div>
      )}
    </Link>
  )
}
