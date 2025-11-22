import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { configService } from '../services/api'
import { useState, useEffect } from 'react'

export default function ConfigEditor() {
  const { name } = useParams<{ name: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isNew = name === 'new'

  const [configContent, setConfigContent] = useState<string>('')

  const { data: config, isLoading, error } = useQuery({
    queryKey: ['config', name],
    queryFn: () => configService.getConfig(name!),
    enabled: !isNew,
  })

  useEffect(() => {
    if (config) {
      setConfigContent(JSON.stringify(config, null, 2))
    } else if (isNew) {
      setConfigContent(JSON.stringify({
        type: 'model',
        name: 'new-component',
        description: 'Description here',
        enabled: true
      }, null, 2))
    }
  }, [config, isNew])

  const saveMutation = useMutation({
    mutationFn: async (content: string) => {
      const parsedConfig = JSON.parse(content)
      const configName = isNew ? parsedConfig.name : name!
      
      await configService.updateConfig(configName, parsedConfig)
      return configName
    },
    onSuccess: (savedName) => {
      queryClient.invalidateQueries({ queryKey: ['configs'] })
      queryClient.invalidateQueries({ queryKey: ['config', savedName] })
      if (isNew) {
        navigate(`/config/${savedName}`)
      } else {
        alert('Configuration saved successfully')
      }
    },
    onError: (error) => {
      alert(`Failed to save configuration: ${(error as Error).message}`)
    },
  })

  const handleSave = () => {
    try {
      // Validate JSON
      JSON.parse(configContent)
      saveMutation.mutate(configContent)
    } catch (e) {
      alert('Invalid JSON content')
    }
  }

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
        Error loading configuration: {(error as Error).message}
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col space-y-4 h-full min-h-[600px]">
      <div className="flex justify-between items-center shrink-0">
        <h1 className="text-2xl font-bold text-white">
          {isNew ? 'Create Configuration' : `Edit ${name}`}
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => navigate('/config')}
            className="px-3 py-1.5 border border-border text-gray-300 rounded-lg hover:bg-surfaceHighlight text-sm transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="px-3 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-500 disabled:opacity-50 text-sm transition-colors"
          >
            {saveMutation.isPending ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      <div className="flex-1 bg-surface border border-border rounded-xl shadow-lg p-0 flex flex-col overflow-hidden">
        <div className="px-4 py-2 bg-surfaceHighlight border-b border-border text-xs text-gray-400 flex justify-between items-center shrink-0">
          <span>JSON Editor</span>
          <span className="text-gray-500">Ensure 'name' matches the intended component name.</span>
        </div>
        <textarea
          value={configContent}
          onChange={(e) => setConfigContent(e.target.value)}
          className="flex-1 w-full font-mono text-sm p-4 bg-background text-gray-200 focus:outline-none resize-none"
          spellCheck={false}
        />
      </div>
    </div>
  )
}
