import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sessionService } from '../services/api'
import { History, Trash2, ChevronRight, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'

export default function Sessions() {
  const [selectedSession, setSelectedSession] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: sessions, isLoading } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => sessionService.listSessions({ limit: 50 }),
  })

  const { data: sessionSteps, isLoading: stepsLoading } = useQuery({
    queryKey: ['session-steps', selectedSession],
    queryFn: () => sessionService.getSessionSteps(selectedSession!),
    enabled: !!selectedSession,
  })

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => sessionService.deleteSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      setSelectedSession(null)
      toast.success('Session deleted')
    },
    onError: () => {
      toast.error('Failed to delete session')
    },
  })

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
              {sessions.items.map((session) => (
                <button
                  key={session.id}
                  onClick={() => setSelectedSession(session.session_id)}
                  className={`w-full bg-surface border rounded-lg p-3 text-left transition-all ${
                    selectedSession === session.session_id
                      ? 'border-primary-500'
                      : 'border-border hover:border-primary-500/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-gray-400">
                      {session.agent_id}
                    </span>
                    <span className={`px-1.5 py-0.5 text-[10px] rounded ${
                      session.status === 'completed'
                        ? 'bg-green-900/30 text-green-400'
                        : session.status === 'failed'
                        ? 'bg-red-900/30 text-red-400'
                        : 'bg-yellow-900/30 text-yellow-400'
                    }`}>
                      {session.status}
                    </span>
                  </div>
                  <p className="text-sm text-white truncate mb-1">
                    {session.input_query}
                  </p>
                  <div className="text-xs text-gray-500">
                    {formatDate(session.created_at)}
                  </div>
                </button>
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

                {stepsLoading ? (
                  <div className="text-gray-500">Loading steps...</div>
                ) : !sessionSteps || sessionSteps.length === 0 ? (
                  <div className="text-gray-500">No steps found</div>
                ) : (
                  <div className="space-y-2">
                    {sessionSteps.map((step) => (
                      <div
                        key={step.id}
                        className="bg-surface border border-border rounded-lg p-4"
                      >
                        <div className="flex items-center gap-2 mb-2">
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
                                ({tc.function?.arguments?.slice(0, 50)}...)
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
    </div>
  )
}
