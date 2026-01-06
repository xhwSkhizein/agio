import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { configService } from '../services/api'
import { ArrowLeft, Save, Loader2, Code2, ShieldCheck, AlertCircle } from 'lucide-react'
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
      toast.success('Configuration updated successfully')
    },
    onError: (error) => {
      toast.error(`Save failed: ${(error as Error).message}`)
    },
  })

  const handleSave = () => {
    try {
      JSON.parse(configContent)
      saveMutation.mutate(configContent)
    } catch (e) {
      toast.error('Syntax Error: Invalid JSON configuration')
    }
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="w-12 h-12 border-4 border-primary-500/20 border-t-primary-500 rounded-full animate-spin mb-4"></div>
        <p className="text-gray-500 font-medium">Fetching configuration details...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center gap-3 p-6 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-400 max-w-2xl mx-auto mt-10">
        <AlertCircle className="w-6 h-6 shrink-0" />
        <div>
          <p className="font-bold text-sm uppercase tracking-widest">Access Denied or Not Found</p>
          <p className="text-xs opacity-80 mt-1">{(error as Error).message}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-4 space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/config')}
            className="group p-2 rounded-lg bg-white/5 border border-white/5 text-gray-600 hover:text-gray-300 hover:bg-white/10 transition-all"
            title="Back to List"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          </button>
          
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-500/10 flex items-center justify-center border border-primary-500/20 shadow-lg shadow-primary-500/5">
              <Code2 className="w-5 h-5 text-primary-500/80" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="px-1.5 py-0.5 text-[9px] font-black uppercase tracking-[0.2em] bg-white/5 border border-white/5 rounded text-gray-700">
                  {type}
                </span>
                <div className="flex items-center gap-1 text-[9px] text-emerald-500/80 font-bold uppercase tracking-widest">
                  <ShieldCheck className="w-2.5 h-2.5" />
                  Live Edit
                </div>
              </div>
              <h1 className="text-2xl font-bold text-gray-200 tracking-tight mt-0.5 uppercase tracking-wider">{name}</h1>
            </div>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="group flex items-center gap-1.5 px-6 py-2.5 bg-primary-600/90 text-white rounded-xl text-[11px] font-black hover:bg-primary-500 transition-all shadow-lg shadow-primary-500/10 active:scale-95 disabled:opacity-50 disabled:shadow-none uppercase tracking-widest"
        >
          {saveMutation.isPending ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Save className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
          )}
          COMMIT CHANGES
        </button>
      </div>

      {/* Editor Container */}
      <div className="bg-white/5 border border-white/5 rounded-3xl overflow-hidden shadow-2xl relative">
        <div className="flex items-center justify-between px-5 py-2.5 bg-white/5 border-b border-white/5">
          <div className="flex items-center gap-2.5">
            <div className="flex gap-1">
              <div className="w-2 h-2 rounded-full bg-red-500/20 border border-red-500/30" />
              <div className="w-2 h-2 rounded-full bg-yellow-500/20 border border-yellow-500/30" />
              <div className="w-2 h-2 rounded-full bg-emerald-500/20 border border-emerald-500/30" />
            </div>
            <span className="text-[9px] font-black text-gray-700 uppercase tracking-[0.3em] ml-1.5">JSON OBJECT SPECIFICATION</span>
          </div>
          <div className="px-1.5 py-0.5 rounded bg-black/40 text-[8px] font-mono text-gray-700 border border-white/5 uppercase font-bold">
            UTF-8 Encoding
          </div>
        </div>
        
        <div className="relative group">
          <textarea
            value={configContent}
            onChange={(e) => setConfigContent(e.target.value)}
            className="w-full h-[540px] font-mono text-[13px] p-6 bg-black/40 text-primary-400/70 focus:outline-none resize-none leading-relaxed selection:bg-primary-500/20 custom-scrollbar"
            spellCheck={false}
            placeholder='{ "config": "..." }'
          />
          
          {/* Overlay hints */}
          <div className="absolute bottom-4 right-6 pointer-events-none opacity-0 group-focus-within:opacity-100 transition-opacity duration-500">
            <div className="text-[9px] font-black text-gray-700 bg-black/60 backdrop-blur-sm px-2.5 py-1 rounded-lg border border-white/5 uppercase tracking-widest">
              AUTO-SAVE DISABLED · ESC TO EXIT
            </div>
          </div>
        </div>
      </div>
      
      {/* Footer Info */}
      <div className="flex items-center gap-2 px-2">
        <div className="w-1 h-1 rounded-full bg-primary-500/60 animate-pulse" />
        <p className="text-[9px] font-black text-gray-700 uppercase tracking-widest">Modified content is verified against system schema before commit</p>
      </div>
    </div>
  )
}
