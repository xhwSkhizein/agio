import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { configService, Agent } from '../services/api'
import toast from 'react-hot-toast'
import { toolsToString, stringToTools } from '../utils/toolHelpers'

interface AgentConfigModalProps {
  agent: Agent
  isOpen: boolean
  onClose: () => void
}

export function AgentConfigModal({ agent, isOpen, onClose }: AgentConfigModalProps) {
  const queryClient = useQueryClient()
  const [config, setConfig] = useState<Agent>(agent)
  const [toolsInput, setToolsInput] = useState(toolsToString(agent.tools || []))
  const [tagsInput, setTagsInput] = useState(agent.tags?.join(', ') || '')

  useEffect(() => {
    setConfig(agent)
    setToolsInput(toolsToString(agent.tools || []))
    setTagsInput(agent.tags?.join(', ') || '')
  }, [agent])

  const updateMutation = useMutation({
    mutationFn: async (updatedConfig: Partial<Agent>) => {
      await configService.updateConfig('agent', agent.name, updatedConfig)
    },
    onSuccess: () => {
      toast.success('Agent configuration updated')
      queryClient.invalidateQueries({ queryKey: ['agent', agent.name] })
      onClose()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update configuration')
    },
  })

  const handleSave = () => {
    const updatedConfig = {
      ...config,
      tools: stringToTools(toolsInput),
      tags: tagsInput.split(',').map(t => t.trim()).filter(Boolean),
    }
    updateMutation.mutate(updatedConfig)
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-surface border border-border rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold text-white">Agent Configuration</h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 overflow-y-auto max-h-[calc(90vh-140px)] space-y-4">
          {/* Name (readonly) */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Name</label>
            <input
              type="text"
              value={config.name}
              disabled
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-gray-500 cursor-not-allowed"
            />
          </div>

          {/* Model */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Model</label>
            <input
              type="text"
              value={config.model || ''}
              onChange={(e) => setConfig({ ...config, model: e.target.value })}
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500"
              placeholder="e.g., gpt-4o-mini"
            />
          </div>

          {/* Tools */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">
              Tools <span className="text-gray-600">(comma separated)</span>
            </label>
            <input
              type="text"
              value={toolsInput}
              onChange={(e) => setToolsInput(e.target.value)}
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500"
              placeholder="file_read, grep, bash"
            />
            <p className="mt-1 text-xs text-gray-600">
              Available: file_read, file_edit, file_write, grep, glob, ls, bash, web_search, web_fetch
            </p>
          </div>

          {/* System Prompt */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">System Prompt</label>
            <textarea
              value={config.system_prompt || ''}
              onChange={(e) => setConfig({ ...config, system_prompt: e.target.value })}
              rows={6}
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 resize-none"
              placeholder="You are a helpful assistant..."
            />
          </div>

          {/* Tags */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">
              Tags <span className="text-gray-600">(comma separated)</span>
            </label>
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500"
              placeholder="development, coding"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border bg-background/50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {updateMutation.isPending && (
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            Save Changes
          </button>
        </div>
      </div>
    </div>
  )
}
