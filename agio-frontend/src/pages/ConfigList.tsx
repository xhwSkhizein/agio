import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { configService, Config } from '../services/api'
import { useState } from 'react'

export default function ConfigList() {
  const queryClient = useQueryClient()
  const [filterType, setFilterType] = useState<string>('all')

  const { data: configs, isLoading, error } = useQuery({
    queryKey: ['configs'],
    queryFn: () => configService.listConfigs(),
  })

  const reloadMutation = useMutation({
    mutationFn: () => configService.reloadConfigs(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['configs'] })
      alert('Configurations reloaded successfully')
    },
    onError: (error) => {
      alert(`Failed to reload configurations: ${(error as Error).message}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (name: string) => configService.deleteConfig(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['configs'] })
    },
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
        Error loading configurations: {(error as Error).message}
      </div>
    )
  }

  const configList = Object.values(configs || {})
  const types = Array.from(new Set(configList.map((c) => c.type)))
  
  const filteredConfigs = filterType === 'all' 
    ? configList 
    : configList.filter((c) => c.type === filterType)

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-white">
          Configurations
        </h1>
        <div className="flex gap-2">
          <button 
            onClick={() => reloadMutation.mutate()}
            disabled={reloadMutation.isPending}
            className="px-3 py-1.5 bg-surfaceHighlight text-gray-300 rounded-lg hover:bg-border disabled:opacity-50 text-sm transition-colors"
          >
            {reloadMutation.isPending ? 'Reloading...' : 'Reload from Disk'}
          </button>
          <Link
            to="/config/new"
            className="px-3 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-500 text-sm transition-colors"
          >
            Create Config
          </Link>
        </div>
      </div>

      <div className="flex gap-2 overflow-x-auto pb-2">
        <button
          onClick={() => setFilterType('all')}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            filterType === 'all'
              ? 'bg-primary-500/20 text-primary-400 border border-primary-500/50'
              : 'bg-surfaceHighlight text-gray-400 border border-transparent hover:border-gray-600'
          }`}
        >
          All
        </button>
        {types.map((type) => (
          <button
            key={type}
            onClick={() => setFilterType(type)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              filterType === type
                ? 'bg-primary-500/20 text-primary-400 border border-primary-500/50'
                : 'bg-surfaceHighlight text-gray-400 border border-transparent hover:border-gray-600'
            }`}
          >
            {type}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filteredConfigs.map((config) => (
          <ConfigCard 
            key={config.name} 
            config={config} 
            onDelete={(name) => {
              if (confirm(`Are you sure you want to delete ${name}?`)) {
                deleteMutation.mutate(name)
              }
            }}
          />
        ))}
      </div>

      {filteredConfigs.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          No configurations found
        </div>
      )}
    </div>
  )
}

function ConfigCard({ config, onDelete }: { config: Config; onDelete: (name: string) => void }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4 hover:border-primary-500/50 transition-all duration-200 hover:shadow-lg group">
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-white group-hover:text-primary-400 transition-colors">
              {config.name}
            </h3>
            <span className="px-1.5 py-0.5 text-[10px] uppercase tracking-wider bg-surfaceHighlight rounded text-gray-400">
              {config.type}
            </span>
          </div>
          {config.description && (
            <p className="mt-1 text-xs text-gray-400 line-clamp-2">
              {config.description}
            </p>
          )}
        </div>
        {config.enabled !== undefined && (
          <span
            className={`px-1.5 py-0.5 text-[10px] rounded-full border ${
              config.enabled
                ? 'bg-green-900/30 text-green-400 border-green-900'
                : 'bg-gray-800 text-gray-400 border-gray-700'
            }`}
          >
            {config.enabled ? 'Active' : 'Inactive'}
          </span>
        )}
      </div>

      {config.tags && config.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-4">
          {config.tags.map((tag) => (
            <span key={tag} className="text-[10px] text-gray-400 bg-surfaceHighlight px-1.5 py-0.5 rounded">
              #{tag}
            </span>
          ))}
        </div>
      )}

      <div className="flex gap-2 mt-auto pt-2 border-t border-border/50">
        <Link
          to={`/config/${config.name}`}
          className="flex-1 px-3 py-1.5 bg-surfaceHighlight text-gray-300 text-center rounded-md hover:bg-border text-xs transition-colors"
        >
          Edit
        </Link>
        <button 
          onClick={() => onDelete(config.name)}
          className="px-3 py-1.5 border border-red-900/30 text-red-400 rounded-md hover:bg-red-900/20 text-xs transition-colors"
        >
          Delete
        </button>
      </div>
    </div>
  )
}
