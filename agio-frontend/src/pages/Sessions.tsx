import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { sessionService, SessionSummary } from '../services/api'
import { History, Trash2, ChevronRight, Loader2, MessageSquare, GitBranch, X } from 'lucide-react'
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
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  // Use new session summary API for aggregated view
  const { data: sessions, isLoading } = useQuery({
    queryKey: ['session-summaries'],
    queryFn: () => sessionService.listSessionSummaries({ limit: 50 }),
  })

  const { data: sessionSteps, isLoading: stepsLoading } = useQuery({
    queryKey: ['session-steps', selectedSession],
    queryFn: () => sessionService.getSessionSteps(selectedSession!),
    enabled: !!selectedSession,
  })

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
  const handleContinueChat = (sessionId: string) => {
    navigate(`/chat/${sessionId}`)
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

  return (
    <div className="max-w-5xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white mb-2">Sessions</h1>
        <p className="text-gray-400">View and manage agent conversation sessions.</p>
      </div>

      {isLoading ? (
        <div className="text-gray-500">Loading sessions...</div>
      ) : !sessions || sessions.items.length === 0 ? (
        <div className="bg-surface border border-border rounded-lg p-8 text-center">
          <History className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">No sessions found.</p>
        </div>
      ) : (
        <div className="flex gap-6">
          {/* Session List */}
          <div className="w-80 flex-shrink-0">
            <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
              Recent Sessions
            </h2>
            <div className="space-y-2">
              {sessions.items.map((session: SessionSummary) => (
                <div
                  key={session.session_id}
                  onClick={() => setSelectedSession(session.session_id)}
                  className={`bg-surface border rounded-lg p-3 cursor-pointer transition-all ${
                    selectedSession === session.session_id
                      ? 'border-primary-500'
                      : 'border-border hover:border-primary-500/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-gray-400">
                      {session.agent_id}
                    </span>
                    <span className="text-[10px] text-gray-500">
                      {session.run_count} runs · {session.step_count} steps
                    </span>
                  </div>
                  <p className="text-sm text-white truncate mb-1">
                    {session.last_message || 'No messages'}
                  </p>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-gray-500">
                      {formatDate(session.last_activity)}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleContinueChat(session.session_id)
                      }}
                      className="flex items-center gap-1 px-2 py-1 text-xs bg-primary-500/20 text-primary-400 rounded hover:bg-primary-500/30 transition-colors"
                    >
                      <MessageSquare className="w-3 h-3" />
                      Continue
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Session Detail */}
          <div className="flex-1 min-w-0">
            {selectedSession ? (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Session Steps
                  </h2>
                  <div className="flex items-center gap-2">
                    {selectedSession && (
                      <button
                        onClick={() => handleContinueChat(selectedSession)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-primary-600 text-white rounded-lg hover:bg-primary-500 transition-colors"
                      >
                        <MessageSquare className="w-3.5 h-3.5" />
                        Continue Chat
                      </button>
                    )}
                    <button
                      onClick={() => deleteMutation.mutate(selectedSession)}
                      disabled={deleteMutation.isPending}
                      className="p-2 text-gray-400 hover:text-red-400 hover:bg-red-900/20 rounded transition-colors"
                      title="Delete session"
                    >
                      {deleteMutation.isPending ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>

                {stepsLoading ? (
                  <div className="text-gray-500">Loading steps...</div>
                ) : !sessionSteps || sessionSteps.length === 0 ? (
                  <div className="text-gray-500">No steps found</div>
                ) : (
                  <div className="space-y-2">
                    {sessionSteps.map((step) => (
                      <div
                        key={step.id}
                        className="bg-surface border border-border rounded-lg p-4 group"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-500">#{step.sequence}</span>
                            <span className={`px-2 py-0.5 text-xs rounded ${
                              step.role === 'user'
                                ? 'bg-blue-900/30 text-blue-400'
                                : step.role === 'assistant'
                                ? 'bg-green-900/30 text-green-400'
                                : 'bg-purple-900/30 text-purple-400'
                            }`}>
                              {step.role}
                            </span>
                          </div>
                          {/* Fork button - for assistant and user steps */}
                          {(step.role === 'assistant' || step.role === 'user') && (
                            <button
                              onClick={() => {
                                const currentSession = sessions?.items.find((s: SessionSummary) => s.session_id === selectedSession)
                                openForkModal(
                                  selectedSession!, 
                                  step.sequence, 
                                  step.role as 'assistant' | 'user',
                                  step.content || '',
                                  step.tool_calls,
                                  currentSession?.agent_id
                                )
                              }}
                              className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-primary-400 hover:bg-primary-500/10 rounded transition-all"
                              title={step.role === 'user' ? 'Fork and edit this message' : 'Fork from this response'}
                            >
                              <GitBranch className="w-3 h-3" />
                              Fork
                            </button>
                          )}
                        </div>
                        {step.content && (
                          <p className="text-sm text-gray-300 whitespace-pre-wrap">
                            {step.content}
                          </p>
                        )}
                        {step.tool_calls && step.tool_calls.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {step.tool_calls.map((tc: any, i: number) => (
                              <div key={i} className="text-xs text-gray-500">
                                <span className="text-primary-400">{tc.function?.name}</span>
                                ({tc.function?.arguments?.slice(0, 200)}...)
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-500">
                <div className="text-center">
                  <ChevronRight className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>Select a session to view details</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Fork Modal */}
      {forkModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-surface border border-border rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <GitBranch className="w-5 h-5 text-primary-400" />
                <h3 className="text-lg font-semibold text-white">
                  Fork {forkModal.role === 'user' ? 'User Message' : 'Assistant Response'}
                </h3>
              </div>
              <button
                onClick={() => setForkModal(null)}
                className="p-1 text-gray-400 hover:text-white rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-4 space-y-4 overflow-y-auto flex-1">
              {forkModal.role === 'user' ? (
                <>
                  <p className="text-sm text-gray-400">
                    Fork from user message at step #{forkModal.sequence}. The message will be placed in the input box for you to edit and send.
                  </p>
                  <div className="bg-background border border-border rounded-lg p-3">
                    <p className="text-sm text-gray-300 whitespace-pre-wrap">{forkModal.originalContent}</p>
                  </div>
                </>
              ) : (
                <>
                  <p className="text-sm text-gray-400">
                    Fork from assistant response at step #{forkModal.sequence}. You can edit the content and/or tool calls.
                  </p>
                  
                  <div>
                    <label className="block text-xs font-medium text-gray-400 mb-2">
                      Content
                    </label>
                    <textarea
                      value={forkContent}
                      onChange={(e) => setForkContent(e.target.value)}
                      className="w-full h-32 bg-background border border-border rounded-lg p-3 text-sm text-gray-300 resize-none focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500"
                      placeholder="Edit the assistant's response..."
                    />
                  </div>
                  
                  {forkModal.originalToolCalls && forkModal.originalToolCalls.length > 0 && (
                    <div>
                      <label className="block text-xs font-medium text-gray-400 mb-2">
                        Tool Calls (JSON)
                      </label>
                      <textarea
                        value={forkToolCalls}
                        onChange={(e) => setForkToolCalls(e.target.value)}
                        className="w-full h-32 bg-background border border-border rounded-lg p-3 text-xs text-gray-300 font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500"
                        placeholder="[]"
                      />
                      <p className="text-xs text-gray-500 mt-1">Clear to remove all tool calls</p>
                    </div>
                  )}
                </>
              )}
            </div>
            
            <div className="flex justify-end gap-3 p-4 border-t border-border">
              <button
                onClick={() => setForkModal(null)}
                className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              {forkModal.role === 'user' ? (
                <button
                  onClick={() => handleFork(false)}
                  className="px-4 py-2 text-sm bg-primary-500 rounded-lg text-white hover:bg-primary-600 transition-colors"
                >
                  Fork & Edit
                </button>
              ) : (
                <>
                  <button
                    onClick={() => handleFork(false)}
                    className="px-4 py-2 text-sm bg-surface border border-border rounded-lg text-white hover:bg-surfaceHighlight transition-colors"
                  >
                    Fork as-is
                  </button>
                  <button
                    onClick={() => handleFork(true)}
                    disabled={
                      forkContent === forkModal.originalContent && 
                      forkToolCalls === JSON.stringify(forkModal.originalToolCalls, null, 2)
                    }
                    className="px-4 py-2 text-sm bg-primary-500 rounded-lg text-white hover:bg-primary-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Fork with changes
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
