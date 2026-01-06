import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { sessionService, SessionSummary, SessionStep } from '../services/api'
import { History, Trash2, ChevronRight, Loader2, MessageSquare, GitBranch, X, Maximize2, Minimize2, Calendar, Layout, Search } from 'lucide-react'
import toast from 'react-hot-toast'

interface ForkModalState {
  sessionId: string
  sequence: number
  role: 'assistant' | 'user'
  originalContent: string
  originalToolCalls?: any[]
  agentId: string
}


export default function Sessions() {
  const [selectedSession, setSelectedSession] = useState<string | null>(null)
  const [forkModal, setForkModal] = useState<ForkModalState | null>(null)
  const [forkContent, setForkContent] = useState('')
  const [forkToolCalls, setForkToolCalls] = useState('')
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set())
  const [stepsOffset, setStepsOffset] = useState(0)
  const [allLoadedSteps, setAllLoadedSteps] = useState<SessionStep[]>([])
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  // Use new session summary API for aggregated view
  const { data: sessions, isLoading } = useQuery({
    queryKey: ['session-summaries'],
    queryFn: () => sessionService.listSessionSummaries({ limit: 50 }),
  })

  const { data: stepsPage, isLoading: stepsLoading } = useQuery({
    queryKey: ['session-steps', selectedSession, stepsOffset],
    queryFn: () => sessionService.getSessionSteps(selectedSession!, 100, stepsOffset),
    enabled: !!selectedSession,
  })

  // Reset and load first page when session changes
  useEffect(() => {
    if (selectedSession) {
      setStepsOffset(0)
      setAllLoadedSteps([])
    }
  }, [selectedSession])

  // Accumulate loaded steps
  useEffect(() => {
    if (stepsPage) {
      if (stepsOffset === 0) {
        setAllLoadedSteps(stepsPage.items)
      } else {
        setAllLoadedSteps(prev => [...prev, ...stepsPage.items])
      }
    }
  }, [stepsPage, stepsOffset])

  const handleLoadMore = () => {
    if (stepsPage && allLoadedSteps.length < stepsPage.total) {
      setStepsOffset(allLoadedSteps.length)
    }
  }

  const hasMore = stepsPage ? allLoadedSteps.length < stepsPage.total : false
  const sessionSteps = allLoadedSteps

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => sessionService.deleteSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['session-summaries'] })
      setSelectedSession(null)
      toast.success('Session deleted')
    },
    onError: () => {
      toast.error('Failed to delete session')
    },
  })

  // Continue chat handler
  const handleContinueChat = (session: SessionSummary) => {
    const agentId = session.agent_id ?? undefined
    navigate(`/chat/${session.session_id}`, { state: { agentId } })
  }

  // Open fork modal
  const openForkModal = (sessionId: string, sequence: number, role: 'assistant' | 'user', content: string, toolCalls?: any[], agentId?: string) => {
    setForkModal({ sessionId, sequence, role, originalContent: content, originalToolCalls: toolCalls, agentId: agentId || '' })
    setForkContent(content)
    setForkToolCalls(toolCalls ? JSON.stringify(toolCalls, null, 2) : '')
  }

  // Fork session handler
  const handleFork = async (useModified: boolean) => {
    if (!forkModal) return
    
    try {
      // For user step, just fork and navigate with pending message
      if (forkModal.role === 'user') {
        const result = await sessionService.forkSession(forkModal.sessionId, forkModal.sequence)
        toast.success(`Forked session`)
        setForkModal(null)
        // Navigate with pending message in state
        navigate(`/chat/${result.new_session_id}`, { 
          state: { pendingMessage: result.pending_user_message, agentId: forkModal.agentId } 
        })
        return
      }
      
      // For assistant step, can modify content and tool_calls
      const options: { content?: string; tool_calls?: any[] } = {}
      if (useModified) {
        if (forkContent !== forkModal.originalContent) {
          options.content = forkContent
        }
        // Parse tool_calls if modified
        if (forkToolCalls !== JSON.stringify(forkModal.originalToolCalls, null, 2)) {
          try {
            options.tool_calls = forkToolCalls ? JSON.parse(forkToolCalls) : []
          } catch {
            toast.error('Invalid tool_calls JSON')
            return
          }
        }
      }
      
      const result = await sessionService.forkSession(forkModal.sessionId, forkModal.sequence, options)
      toast.success(`Forked session with ${result.copied_steps} steps`)
      setForkModal(null)
      navigate(`/chat/${result.new_session_id}`, { state: { agentId: forkModal.agentId } })
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Failed to fork session')
    }
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString()
  }

  // Toggle step content expansion
  const toggleStepExpand = (stepId: string) => {
    setExpandedSteps(prev => {
      const next = new Set(prev)
      if (next.has(stepId)) {
        next.delete(stepId)
      } else {
        next.add(stepId)
      }
      return next
    })
  }

  // Render a single session item
  const renderSessionItem = (session: SessionSummary) => (
    <div
      key={session.session_id}
      onClick={() => setSelectedSession(session.session_id)}
      className={`group relative bg-white/5 border rounded-xl p-3.5 cursor-pointer transition-all duration-200 ${
        selectedSession === session.session_id
          ? 'border-primary-500/40 bg-primary-500/5 ring-1 ring-primary-500/10'
          : 'border-white/5 hover:border-white/10 hover:bg-white/10'
      }`}
    >
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1 rounded-lg bg-white/5 text-gray-500 group-hover:text-primary-400/80 transition-colors">
            <Layout className="w-3 h-3" />
          </div>
          <span className="text-[11px] font-bold text-gray-400 truncate uppercase tracking-tight">
            {session.agent_id?.replace(/_/g, ' ')}
          </span>
        </div>
        <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-white/5 border border-white/5 text-[9px] text-gray-600 font-mono">
          <span>{session.run_count}R</span>
          <span className="w-px h-2 bg-white/10" />
          <span>{session.step_count}S</span>
        </div>
      </div>
      
      <p className="text-[13px] text-gray-400 line-clamp-2 mb-2 min-h-[2.5rem] leading-relaxed">
        {session.last_message || 'No messages'}
      </p>
      
      <div className="flex items-center justify-between pt-2 border-t border-white/5">
        <div className="flex items-center gap-1 text-[9px] text-gray-600 font-bold uppercase tracking-tighter">
          <Calendar className="w-2.5 h-2.5 opacity-50" />
          {formatDate(session.last_activity).split(',')[0]}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation()
            handleContinueChat(session)
          }}
          className="flex items-center gap-1 px-2 py-1 text-[10px] font-black bg-primary-600/10 text-primary-400/80 rounded-lg hover:bg-primary-600/20 transition-all border border-primary-500/10 uppercase tracking-widest"
        >
          <MessageSquare className="w-2.5 h-2.5" />
          CONTINUE
        </button>
      </div>
      
      {selectedSession === session.session_id && (
        <div className="absolute -right-0.5 top-1/2 -translate-y-1/2 w-1 h-6 bg-primary-500/60 rounded-l-full shadow-[0_0_8px_rgba(59,130,246,0.3)]" />
      )}
    </div>
  )


  return (
    <div className="max-w-6xl mx-auto px-4 py-4">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-200 tracking-tight mb-1 flex items-center gap-2.5">
            <History className="w-6 h-6 text-primary-500/80" />
            Sessions
          </h1>
          <p className="text-gray-500 text-[13px] font-medium">View and manage agent conversation histories with narrative trajectories.</p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white/5 rounded-2xl border border-white/10 border-dashed">
          <Loader2 className="w-8 h-8 text-primary-500 animate-spin mb-4" />
          <p className="text-gray-500 font-medium">Loading session history...</p>
        </div>
      ) : !sessions || sessions.items.length === 0 ? (
        <div className="bg-white/5 border border-white/10 border-dashed rounded-2xl p-16 text-center">
          <History className="w-16 h-16 text-gray-700 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-300 mb-2">No Sessions Found</h3>
          <p className="text-gray-500 max-w-sm mx-auto">Start a conversation with an agent to see your session history here.</p>
        </div>
      ) : (
        <div className="flex gap-6 items-start">
          {/* Session List */}
          <div className="w-72 flex-shrink-0 sticky top-4">
            <div className="flex items-center justify-between mb-3 px-1">
              <h2 className="text-[10px] font-black text-gray-600 uppercase tracking-[0.25em]">
                RECENT SESSIONS
              </h2>
              <span className="text-[9px] text-gray-700 font-bold font-mono uppercase tracking-tighter">{sessions.items.length} TOTAL</span>
            </div>
            <div className="space-y-2.5 max-h-[calc(100vh-10rem)] overflow-y-auto pr-2 custom-scrollbar">
              {sessions.items.map((session) => renderSessionItem(session))}
            </div>
          </div>

          {/* Session Detail */}
          <div className="flex-1 min-w-0 bg-white/5 rounded-2xl border border-white/5 overflow-hidden flex flex-col h-[calc(100vh-10rem)] shadow-xl">
            {selectedSession ? (
              <>
                <div className="flex items-center justify-between px-5 py-3 bg-white/5 border-b border-white/5 backdrop-blur-md">
                  <div className="flex flex-col">
                    <h2 className="text-[10px] font-black text-gray-600 uppercase tracking-widest mb-0.5">
                      SESSION LOGS
                    </h2>
                    <span className="text-[9px] font-bold text-gray-700 font-mono truncate max-w-[240px]">ID: {selectedSession}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => {
                        const sessionMeta = sessions?.items?.find((s) => s.session_id === selectedSession)
                        if (!sessionMeta) return
                        handleContinueChat(sessionMeta)
                      }}
                      className="flex items-center gap-2 px-3 py-1.5 text-[11px] font-black bg-primary-600/10 text-primary-400 border border-primary-500/20 rounded-xl hover:bg-primary-600/20 transition-all shadow-lg shadow-primary-500/5 active:scale-95 uppercase tracking-widest"
                    >
                      <MessageSquare className="w-3 h-3" />
                      CONTINUE CHAT
                    </button>
                    <div className="w-px h-4 bg-white/10" />
                    <button
                      onClick={() => deleteMutation.mutate(selectedSession)}
                      disabled={deleteMutation.isPending}
                      className="p-2 text-gray-600 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all"
                      title="Delete session"
                    >
                      {deleteMutation.isPending ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto p-5 space-y-4 custom-scrollbar bg-black/20">
                  {stepsLoading && allLoadedSteps.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20">
                      <Loader2 className="w-6 h-6 text-primary-500 animate-spin mb-3" />
                      <p className="text-gray-500 text-sm">Retrieving steps...</p>
                    </div>
                  ) : !sessionSteps || sessionSteps.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20 text-gray-600 border border-white/5 border-dashed rounded-xl">
                      <Search className="w-8 h-8 mb-2 opacity-30" />
                      <p className="text-sm font-medium">No steps found for this session</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {sessionSteps.map((step) => {
                        const isExpanded = expandedSteps.has(step.id)
                        const contentLength = (step.content?.length || 0) + (step.reasoning_content?.length || 0)
                        const hasLongContent = contentLength > 300 || (step.tool_calls?.length || 0) > 0
                        
                        return (
                          <div
                            key={step.id}
                            className={`group relative bg-white/5 border border-white/5 rounded-xl p-4 transition-all hover:bg-white/[0.07] ${
                              step.role === 'user' ? 'border-l-4 border-l-primary-500/40' : ''
                            }`}
                          >
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center gap-2.5">
                                <div className="flex items-center justify-center w-5 h-5 rounded bg-white/5 text-[9px] font-bold text-gray-600 font-mono">
                                  {step.sequence}
                                </div>
                                <span className={`px-2 py-0.5 text-[9px] font-black uppercase tracking-tighter rounded-md ${
                                  step.role === 'user'
                                    ? 'bg-primary-500/10 text-primary-400/80 border border-primary-500/10'
                                    : step.role === 'assistant'
                                    ? 'bg-emerald-500/10 text-emerald-400/80 border border-emerald-500/10'
                                    : 'bg-purple-500/10 text-purple-400/80 border border-purple-500/10'
                                }`}>
                                  {step.role}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                {hasLongContent && (
                                  <button
                                    onClick={() => toggleStepExpand(step.id)}
                                    className="p-1 text-gray-600 hover:text-gray-300 hover:bg-white/5 rounded-lg transition-all"
                                    title={isExpanded ? 'Collapse' : 'Expand'}
                                  >
                                    {isExpanded ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
                                  </button>
                                )}
                                {(step.role === 'assistant' || step.role === 'user') && (
                                  <button
                                    onClick={() => {
                                      const currentSession = sessions?.items?.find((s) => s.session_id === selectedSession)
                                      openForkModal(selectedSession!, step.sequence, step.role as 'assistant' | 'user', step.content || '', step.tool_calls, currentSession?.agent_id ?? undefined)
                                    }}
                                    className="flex items-center gap-1 px-2 py-1 text-[10px] font-black text-gray-600 hover:text-primary-400/80 hover:bg-primary-500/5 rounded-lg border border-transparent hover:border-primary-500/10 transition-all uppercase tracking-widest"
                                  >
                                    <GitBranch className="w-2.5 h-2.5" />
                                    FORK
                                  </button>
                                )}
                              </div>
                            </div>
                            
                            <div className={`transition-all duration-300 relative ${isExpanded ? 'max-h-none' : 'max-h-24 overflow-hidden'}`}>
                              {step.reasoning_content && (
                                <div className="mb-3 p-3 bg-purple-500/5 border border-purple-500/10 rounded-xl">
                                  <div className="flex items-center gap-2 text-[9px] font-black text-purple-400/70 uppercase tracking-widest mb-1.5">
                                    <MessageSquare className="w-2.5 h-2.5" />
                                    Reasoning
                                  </div>
                                  <pre className="text-[11px] text-purple-300/60 whitespace-pre-wrap break-words font-mono leading-relaxed">{step.reasoning_content}</pre>
                                </div>
                              )}
                              
                              {step.content && (
                                <div className="text-[13px] text-gray-400 whitespace-pre-wrap leading-relaxed">
                                  {step.content}
                                </div>
                              )}
                              
                              {step.tool_calls && step.tool_calls.length > 0 && (
                                <div className="mt-3 space-y-1.5">
                                  <div className="text-[9px] font-black text-gray-700 uppercase tracking-widest mb-1">Tool Executions</div>
                                  {step.tool_calls.map((tc: any, i: number) => (
                                    <div key={i} className="flex items-start gap-2 p-2 bg-white/5 rounded-lg border border-white/5 font-mono text-[10px]">
                                      <span className="text-primary-400/70 shrink-0 font-bold">{tc.function?.name}</span>
                                      <span className="text-gray-600 break-all line-clamp-1">
                                        ({tc.function?.arguments})
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}
                              
                              {!isExpanded && hasLongContent && (
                                <div className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-black/20 to-transparent pointer-events-none" />
                              )}
                            </div>
                            
                            {!isExpanded && hasLongContent && (
                              <button
                                onClick={() => toggleStepExpand(step.id)}
                                className="mt-2 text-xs font-bold text-primary-500 hover:text-primary-400 transition-colors"
                              >
                                SHOW FULL TRAJECTORY
                              </button>
                            )}
                          </div>
                        )
                      })}
                      
                      {hasMore && (
                        <div className="flex justify-center pt-4 pb-8">
                          <button
                            onClick={handleLoadMore}
                            disabled={stepsLoading}
                            className="group flex items-center gap-3 px-6 py-3 bg-white/5 border border-white/10 rounded-xl text-sm font-bold text-gray-300 hover:bg-white/10 hover:border-primary-500/30 transition-all disabled:opacity-50"
                          >
                            {stepsLoading ? (
                              <Loader2 className="w-4 h-4 animate-spin text-primary-500" />
                            ) : (
                              <>
                                <Maximize2 className="w-4 h-4 text-primary-500 group-hover:scale-110 transition-transform" />
                                LOAD MORE LOGS ({allLoadedSteps.length} / {stepsPage?.total || 0})
                              </>
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-gray-600 bg-black/20">
                <div className="p-8 rounded-full bg-white/5 mb-6 border border-white/10 border-dashed animate-pulse">
                  <ChevronRight className="w-12 h-12 opacity-20" />
                </div>
                <h3 className="text-xl font-bold text-gray-500 mb-2">Select a Narrative</h3>
                <p className="text-sm max-w-[240px] text-center text-gray-600 font-medium">Choose a session from the list to view its complete execution logs and results.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Fork Modal */}
      {forkModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-50 p-6">
          <div className="bg-surface border border-white/10 rounded-3xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in duration-300">
            <div className="flex items-center justify-between p-6 border-b border-white/10 bg-white/5">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-primary-500/20">
                  <GitBranch className="w-6 h-6 text-primary-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white">
                    Fork Trajectory
                  </h3>
                  <p className="text-xs text-gray-500 font-medium tracking-tight">Step #{forkModal.sequence} · {forkModal.role.toUpperCase()}</p>
                </div>
              </div>
              <button
                onClick={() => setForkModal(null)}
                className="p-2 text-gray-500 hover:text-white hover:bg-white/10 rounded-xl transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-8 space-y-6 overflow-y-auto flex-1 custom-scrollbar">
              {forkModal.role === 'user' ? (
                <>
                  <div className="flex items-start gap-3 p-4 bg-primary-500/5 border border-primary-500/10 rounded-2xl">
                    <MessageSquare className="w-5 h-5 text-primary-400 shrink-0 mt-0.5" />
                    <p className="text-sm text-gray-400 leading-relaxed">
                      You are forking from this user message. The session will be copied up to this point, and this message will be available for you to edit before continuing.
                    </p>
                  </div>
                  <div className="bg-black/40 border border-white/5 rounded-2xl p-6">
                    <div className="text-[10px] font-black text-gray-600 uppercase tracking-widest mb-3">Original Message</div>
                    <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed italic">"{forkModal.originalContent}"</p>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-start gap-3 p-4 bg-primary-500/5 border border-primary-500/10 rounded-2xl">
                    <GitBranch className="w-5 h-5 text-primary-400 shrink-0 mt-0.5" />
                    <p className="text-sm text-gray-400 leading-relaxed">
                      Forking from an assistant response allows you to rewrite history by modifying the content or tool calls before the agent continues.
                    </p>
                  </div>
                  
                  <div className="space-y-4">
                    <div>
                      <label className="block text-[10px] font-black text-gray-500 uppercase tracking-[0.2em] mb-3 ml-1">
                        RESPONSE CONTENT
                      </label>
                      <textarea
                        value={forkContent}
                        onChange={(e) => setForkContent(e.target.value)}
                        className="w-full h-40 bg-black/40 border border-white/10 rounded-2xl p-4 text-sm text-gray-200 resize-none focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-all leading-relaxed"
                        placeholder="Edit response content..."
                      />
                    </div>
                    
                    {forkModal.originalToolCalls && forkModal.originalToolCalls.length > 0 && (
                      <div>
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-[0.2em] mb-3 ml-1">
                          TOOL CALLS (RAW JSON)
                        </label>
                        <textarea
                          value={forkToolCalls}
                          onChange={(e) => setForkToolCalls(e.target.value)}
                          className="w-full h-40 bg-black/40 border border-white/10 rounded-2xl p-4 text-xs text-primary-300 font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-all"
                          placeholder="[]"
                        />
                        <p className="text-[10px] text-gray-600 mt-2 px-1">Tip: Modifying tool calls may lead to unexpected agent behavior if the session state depends on their results.</p>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
            
            <div className="flex items-center justify-end gap-4 p-6 border-t border-white/10 bg-white/5">
              <button
                onClick={() => setForkModal(null)}
                className="px-6 py-2.5 text-sm font-bold text-gray-500 hover:text-white transition-all"
              >
                CANCEL
              </button>
              {forkModal.role === 'user' ? (
                <button
                  onClick={() => handleFork(false)}
                  className="px-8 py-3 bg-primary-600 text-white text-sm font-black rounded-2xl hover:bg-primary-500 transition-all shadow-xl shadow-primary-500/20 active:scale-95"
                >
                  FORK & REDIRECT
                </button>
              ) : (
                <>
                  <button
                    onClick={() => handleFork(false)}
                    className="px-6 py-3 bg-white/5 border border-white/10 rounded-2xl text-white text-sm font-bold hover:bg-white/10 transition-all"
                  >
                    FORK AS-IS
                  </button>
                  <button
                    onClick={() => handleFork(true)}
                    disabled={
                      forkContent === forkModal.originalContent && 
                      forkToolCalls === JSON.stringify(forkModal.originalToolCalls, null, 2)
                    }
                    className="px-8 py-3 bg-primary-600 text-white text-sm font-black rounded-2xl hover:bg-primary-500 transition-all shadow-xl shadow-primary-500/20 active:scale-95 disabled:opacity-50 disabled:shadow-none disabled:scale-100"
                  >
                    FORK WITH CHANGES
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
