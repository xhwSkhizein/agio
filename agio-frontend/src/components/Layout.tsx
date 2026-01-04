import { Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { healthService } from '../services/api'
import {
  Home,
  MessageSquare,
  Database,
  Brain,
  History,
  Settings,
  FileText,
  ExternalLink,
  Activity,
} from 'lucide-react'

interface LayoutProps {
  children: React.ReactNode
}

const navItems = [
  { path: '/', label: 'Home', icon: Home },
  { path: '/chat', label: 'Chat', icon: MessageSquare },
  { path: '/knowledge', label: 'Knowledge', icon: Database },
  { path: '/memory', label: 'Memory', icon: Brain },
  { path: '/sessions', label: 'Sessions', icon: History },
  { path: '/traces', label: 'Traces', icon: Activity },
]

const bottomNavItems = [
  { path: '/config', label: 'Settings', icon: Settings },
]

const externalLinks = [
  { href: '/agio/docs', label: 'Docs', icon: FileText },
  { href: 'https://github.com/agio-ai/agio', label: 'GitHub', icon: ExternalLink },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => healthService.ready(),
    refetchInterval: 30000,
  })

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside className="w-56 bg-surface border-r border-border flex flex-col fixed h-full">
        {/* Logo & Status */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center text-white font-bold text-sm">
              A
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-white truncate">Agio</div>
              <div className="text-xs text-gray-500 truncate">Control Plane</div>
            </div>
            {/* Status Indicator */}
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
              health?.ready ? 'bg-green-400' : 'bg-yellow-400 animate-pulse'
            }`} title={health?.ready ? 'Running' : 'Starting'} />
          </div>
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon
            const active = isActive(item.path)
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  active
                    ? 'bg-surfaceHighlight text-white'
                    : 'text-gray-400 hover:text-white hover:bg-surfaceHighlight/50'
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            )
          })}
        </nav>

        {/* Bottom Section */}
        <div className="p-3 border-t border-border space-y-1">
          {bottomNavItems.map((item) => {
            const Icon = item.icon
            const active = isActive(item.path)
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  active
                    ? 'bg-surfaceHighlight text-white'
                    : 'text-gray-400 hover:text-white hover:bg-surfaceHighlight/50'
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            )
          })}

          <div className="pt-2 space-y-1">
            {externalLinks.map((item) => {
              const Icon = item.icon
              return (
                <a
                  key={item.href}
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-500 hover:text-gray-300 transition-colors"
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                  <ExternalLink className="w-3 h-3 ml-auto opacity-50" />
                </a>
              )
            })}
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 ml-56 flex flex-col min-h-screen">
        {/* Page Content */}
        <main className="flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
