import { useState, useEffect } from 'react'
import { runService, Run } from '../services/api'

export default function Runs() {
  const [runs, setRuns] = useState<Run[]>([])
  const [loading, setLoading] = useState(true)
  const [filterAgent, setFilterAgent] = useState('')
  const [filterStatus, setFilterStatus] = useState('')

  useEffect(() => {
    loadRuns()
  }, [filterAgent, filterStatus])

  const loadRuns = async () => {
    try {
      setLoading(true)
      const response = await runService.listRuns({
        agent_id: filterAgent || undefined,
        status: filterStatus || undefined,
        limit: 50,
      })
      setRuns(response.items)
    } catch (error) {
      console.error('Failed to load runs:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
        return 'bg-green-900/30 text-green-400 border border-green-900'
      case 'running':
        return 'bg-blue-900/30 text-blue-400 border border-blue-900'
      case 'failed':
        return 'bg-red-900/30 text-red-400 border border-red-900'
      case 'cancelled':
        return 'bg-gray-800 text-gray-400 border border-gray-700'
      default:
        return 'bg-gray-800 text-gray-400 border border-gray-700'
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-white">Runs</h1>
          <p className="mt-1 text-sm text-gray-400">View and manage agent execution runs</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <input
          type="text"
          placeholder="Filter by Agent ID"
          value={filterAgent}
          onChange={(e) => setFilterAgent(e.target.value)}
          className="px-3 py-1.5 bg-surface border border-border rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary-500"
        />
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-1.5 bg-surface border border-border rounded-lg text-sm text-white focus:outline-none focus:border-primary-500"
        >
          <option value="">All Statuses</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Runs Table */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-surfaceHighlight">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Run ID
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Agent
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Query
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Tokens
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Duration
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                    No runs found
                  </td>
                </tr>
              ) : (
                runs.map((run) => (
                  <tr
                    key={run.id}
                    className="hover:bg-surfaceHighlight transition-colors cursor-pointer"
                    onClick={() => (window.location.href = `/runs/${run.id}`)}
                  >
                    <td className="px-4 py-3 whitespace-nowrap text-xs font-mono text-primary-400">
                      {run.id.substring(0, 8)}...
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-300">
                      {run.agent_id}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span
                        className={`px-2 py-0.5 inline-flex text-[10px] uppercase tracking-wider font-semibold rounded-full ${getStatusColor(
                          run.status
                        )}`}
                      >
                        {run.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-400 max-w-md truncate">
                      {run.input_query}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {run.metrics.total_tokens}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {run.metrics.duration.toFixed(2)}s
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-600">
                      {new Date(run.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
