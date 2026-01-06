import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { configService, Agent } from '../services/api'
import toast from 'react-hot-toast'
import { toolsToString, stringToTools } from '../utils/toolHelpers'
import { X, Save, Loader2, ShieldCheck, Settings2 } from 'lucide-react'

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
      toast.success('Agent logic recalculated successfully')
      queryClient.invalidateQueries({ queryKey: ['agent', agent.name] })
      onClose()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Recalculation failed: Protocol error')
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
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 animate-in fade-in duration-300">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/80 backdrop-blur-md"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-[#0a0a0a] border border-white/5 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col animate-in zoom-in-95 duration-300">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-white/5 relative overflow-hidden">
          <div className="flex items-center gap-3 relative z-10">
            <div className="w-10 h-10 rounded-xl bg-primary-500/10 flex items-center justify-center border border-primary-500/20 shadow-lg shadow-primary-500/5">
              <Settings2 className="w-5 h-5 text-primary-500/80" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-200 tracking-tight uppercase tracking-wider">Agent Logic</h2>
              <div className="flex items-center gap-2 mt-0.5">
                <div className="flex items-center gap-1 text-[9px] text-emerald-500/80 font-bold uppercase tracking-widest">
                  <ShieldCheck className="w-2.5 h-2.5" />
                  Kernel Auth
                </div>
                <span className="text-[9px] font-mono text-gray-700 bg-black/40 px-1.5 py-0.5 rounded border border-white/5 uppercase font-bold tracking-tighter">
                  ID: {agent.name}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-gray-600 hover:text-gray-300 hover:bg-white/5 rounded-lg transition-all relative z-10"
          >
            <X className="w-5 h-5" />
          </button>
          
          <Settings2 className="absolute -right-8 -bottom-8 w-48 h-48 opacity-[0.02] text-primary-500 pointer-events-none" />
        </div>

        {/* Content */}
        <div className="px-6 py-6 overflow-y-auto custom-scrollbar space-y-6 bg-black/20">
          {/* Model */}
          <div className="space-y-1.5">
            <label className="block text-[9px] font-black text-gray-700 uppercase tracking-[0.25em] ml-1">NEURAL ENGINE MODEL</label>
            <input
              type="text"
              value={config.model || ''}
              onChange={(e) => setConfig({ ...config, model: e.target.value })}
              className="w-full px-3.5 py-2 bg-black/40 border border-white/5 rounded-xl text-[13px] text-gray-300 placeholder-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500/30 transition-all font-mono"
              placeholder="e.g., gpt-4o-mini"
            />
          </div>

          {/* Tools */}
          <div className="space-y-1.5">
            <label className="block text-[9px] font-black text-gray-700 uppercase tracking-[0.25em] ml-1">
              CAPABILITY PROTOCOLS <span className="text-gray-800 font-bold">(COMMA SEPARATED)</span>
            </label>
            <input
              type="text"
              value={toolsInput}
              onChange={(e) => setToolsInput(e.target.value)}
              className="w-full px-3.5 py-2 bg-black/40 border border-white/5 rounded-xl text-[13px] text-primary-500/70 placeholder-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500/30 transition-all font-mono"
              placeholder="file_read, grep, bash"
            />
            <div className="bg-white/5 rounded-lg p-2.5 border border-white/5">
              <p className="text-[9px] text-gray-700 font-black uppercase tracking-widest mb-1">Registered Modules:</p>
              <p className="text-[9px] text-gray-600 leading-relaxed font-bold uppercase tracking-tight">
                file_read, file_edit, file_write, grep, glob, ls, bash, web_search, web_fetch, sql_exec
              </p>
            </div>
          </div>

          {/* System Prompt */}
          <div className="space-y-1.5">
            <label className="block text-[9px] font-black text-gray-700 uppercase tracking-[0.25em] ml-1">SYSTEM INSTRUCTION SET</label>
            <textarea
              value={config.system_prompt || ''}
              onChange={(e) => setConfig({ ...config, system_prompt: e.target.value })}
              rows={6}
              className="w-full px-3.5 py-3 bg-black/40 border border-white/5 rounded-xl text-[13px] text-gray-400 placeholder-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500/30 transition-all resize-none leading-relaxed custom-scrollbar"
              placeholder="Inject core behavioral directives here..."
            />
          </div>

          {/* Tags */}
          <div className="space-y-1.5">
            <label className="block text-[9px] font-black text-gray-700 uppercase tracking-[0.25em] ml-1">
              METADATA LABELS
            </label>
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              className="w-full px-3.5 py-2 bg-black/40 border border-white/5 rounded-xl text-[13px] text-gray-300 placeholder-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500/30 transition-all"
              placeholder="development, production, high-priority"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/5 bg-white/5 relative z-10">
          <button
            onClick={onClose}
            className="px-4 py-2 text-[11px] font-black text-gray-600 hover:text-gray-300 transition-all uppercase tracking-widest"
          >
            DISCARD
          </button>
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className="group flex items-center gap-1.5 px-6 py-2.5 bg-primary-600/90 text-white rounded-xl text-[11px] font-black hover:bg-primary-500 transition-all shadow-lg shadow-primary-500/10 active:scale-95 disabled:opacity-50 disabled:shadow-none uppercase tracking-widest"
          >
            {updateMutation.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Save className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
            )}
            COMMIT LOGIC
          </button>
        </div>
      </div>
    </div>
  )
}
