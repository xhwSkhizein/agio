import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { configService } from '../services/api'
import { ArrowLeft, Save, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'

export default function ConfigEditor() {
  const { type, name } = useParams<{ type: string; name: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [configContent, setConfigContent] = useState<string>('')

  const { data: config, isLoading, error } = useQuery({
    queryKey: ['config', type, name],
    queryFn: () => configService.getConfig(type!, name!),
    enabled: !!type && !!name,
  })

  useEffect(() => {
    if (config) {
      setConfigContent(JSON.stringify(config, null, 2))
    }
  }, [config])

  const saveMutation = useMutation({
    mutationFn: async (content: string) => {
      const parsedConfig = JSON.parse(content)
      await configService.updateConfig(type!, name!, parsedConfig)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['configs'] })
      queryClient.invalidateQueries({ queryKey: ['config', type, name] })
      toast.success('Configuration saved')
    },
    onError: (error) => {
      toast.error(`Failed to save: ${(error as Error).message}`)
    },
  })

  const handleSave = () => {
    try {
      JSON.parse(configContent)
      saveMutation.mutate(configContent)
    } catch (e) {
      toast.error('Invalid JSON content')
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
    <div className="max-w-4xl">
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={() => navigate('/config')}
          className="p-2 text-gray-400 hover:text-white hover:bg-surfaceHighlight rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-xs uppercase tracking-wider bg-surfaceHighlight rounded text-gray-500">
              {type}
            </span>
          </div>
          <h1 className="text-xl font-semibold text-white mt-1">{name}</h1>
        </div>
        <button
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-500 disabled:opacity-50 text-sm transition-colors"
        >
          {saveMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Save
        </button>
      </div>

      <div className="bg-surface border border-border rounded-lg overflow-hidden">
        <div className="px-4 py-2 bg-surfaceHighlight border-b border-border text-xs text-gray-500">
          JSON Configuration
        </div>
        <textarea
          value={configContent}
          onChange={(e) => setConfigContent(e.target.value)}
          className="w-full h-[500px] font-mono text-sm p-4 bg-background text-gray-200 focus:outline-none resize-none"
          spellCheck={false}
        />
      </div>
    </div>
  )
}
