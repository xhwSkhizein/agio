export default function Dashboard() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-white">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-gray-400">
          Welcome to Agio Agent Framework
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Agents"
          value="12"
          icon="🤖"
          trend="+2 this week"
        />
        <StatCard
          title="Active Runs"
          value="5"
          icon="▶️"
          trend="3 completed today"
        />
        <StatCard
          title="Checkpoints"
          value="48"
          icon="💾"
          trend="12 this week"
        />
        <StatCard
          title="Total Tokens"
          value="1.2M"
          icon="📊"
          trend="+15% this month"
        />
      </div>

      {/* Recent Activity */}
      <div className="bg-surface border border-border rounded-xl p-4">
        <h2 className="text-lg font-semibold text-white mb-3">
          Recent Activity
        </h2>
        <div className="text-sm text-gray-400">
          No recent activity
        </div>
      </div>
    </div>
  )
}

interface StatCardProps {
  title: string
  value: string
  icon: string
  trend: string
}

function StatCard({ title, value, icon, trend }: StatCardProps) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4 hover:border-primary-500/50 transition-colors group">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-gray-400 group-hover:text-primary-400 transition-colors uppercase tracking-wider">
            {title}
          </p>
          <p className="mt-1 text-2xl font-semibold text-white">
            {value}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            {trend}
          </p>
        </div>
        <div className="text-2xl opacity-50 group-hover:opacity-100 transition-opacity">{icon}</div>
      </div>
    </div>
  )
}
