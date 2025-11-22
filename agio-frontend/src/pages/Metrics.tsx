import { useState, useEffect } from 'react'
import { metricsService, SystemMetrics } from '../services/api'

export default function Metrics() {
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadMetrics()
  }, [])

  const loadMetrics = async () => {
    try {
      setLoading(true)
      const metrics = await metricsService.getSystemMetrics()
      setSystemMetrics(metrics)
    } catch (error) {
      console.error('Failed to load metrics:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-white">Metrics Dashboard</h1>
          <p className="mt-1 text-sm text-gray-400">System-wide performance metrics</p>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Agents"
          value={systemMetrics?.total_agents || 0}
          icon="👤"
          color="blue"
        />
        <MetricCard
          title="Total Runs"
          value={systemMetrics?.total_runs || 0}
          icon="🔄"
          color="green"
        />
        <MetricCard
          title="Active Runs"
          value={systemMetrics?.active_runs || 0}
          icon="⚡"
          color="yellow"
        />
        <MetricCard
          title="Tokens Today"
          value={(systemMetrics?.total_tokens_today || 0).toLocaleString()}
          icon="💬"
          color="purple"
        />
      </div>

      {/* Performance Stats */}
      <div className="bg-surface border border-border rounded-xl p-4">
        <h2 className="text-lg font-semibold text-white mb-3">Performance</h2>
        <div className="space-y-2">
          <StatRow
            label="Average Response Time"
            value={`${(systemMetrics?.avg_response_time || 0).toFixed(2)}s`}
          />
          <StatRow
            label="Success Rate"
            value="N/A"
            note="Coming soon"
          />
          <StatRow
            label="Throughput"
            value="N/A"
            note="Coming soon"
          />
        </div>
      </div>

      {/* Placeholder for Charts */}
      <div className="bg-surface border border-border rounded-xl p-4">
        <h2 className="text-lg font-semibold text-white mb-3">Usage Trends</h2>
        <div className="h-48 flex items-center justify-center bg-surfaceHighlight rounded-lg border border-border border-dashed">
          <p className="text-gray-500 text-sm">Charts coming soon</p>
        </div>
      </div>
    </div>
  )
}

interface MetricCardProps {
  title: string
  value: number | string
  icon: string
  color: 'blue' | 'green' | 'yellow' | 'purple'
}

function MetricCard({ title, value, icon, color }: MetricCardProps) {
  const colorClasses = {
    blue: 'bg-blue-900/20 text-blue-400 border-blue-900/50',
    green: 'bg-green-900/20 text-green-400 border-green-900/50',
    yellow: 'bg-yellow-900/20 text-yellow-400 border-yellow-900/50',
    purple: 'bg-purple-900/20 text-purple-400 border-purple-900/50',
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-4 hover:border-primary-500/30 transition-colors">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">{title}</p>
          <p className="mt-1 text-2xl font-bold text-white">{value}</p>
        </div>
        <div className={`${colorClasses[color]} border rounded-lg p-2 text-xl`}>
          {icon}
        </div>
      </div>
    </div>
  )
}

interface StatRowProps {
  label: string
  value: string
  note?: string
}

function StatRow({ label, value, note }: StatRowProps) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-border/50 last:border-0">
      <span className="text-gray-400 text-sm">{label}</span>
      <div className="text-right">
        <span className="text-gray-200 font-mono text-sm">{value}</span>
        {note && <span className="ml-2 text-xs text-gray-600">({note})</span>}
      </div>
    </div>
  )
}
