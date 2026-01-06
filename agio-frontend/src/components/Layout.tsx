import { Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { healthService } from '../services/api'
import {
  Home,
  MessageSquare,
  History,
  Settings,
  FileText,
  ExternalLink,
  Activity,
  Cpu
} from 'lucide-react'

interface LayoutProps {
  children: React.ReactNode
}

const navItems = [
  { path: '/', label: 'Dashboard', icon: Home },
  { path: '/chat', label: 'Chat Engine', icon: MessageSquare },
  { path: '/sessions', label: 'Narratives', icon: History },
  { path: '/traces', label: 'Telemetry', icon: Activity },
]

const bottomNavItems = [
  { path: '/config', label: 'System Config', icon: Settings },
]

const externalLinks = [
  { href: '/agio/docs', label: 'Documentation', icon: FileText },
  { href: 'https://github.com/agio-ai/agio', label: 'Source Code', icon: ExternalLink },
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
    <div className="min-h-screen bg-[#050505] text-gray-300 flex font-sans selection:bg-primary-500/30">
      {/* Sidebar */}
      <aside className="w-60 bg-[#0a0a0a] border-r border-white/5 flex flex-col fixed h-full z-30 transition-all duration-300">
        {/* Logo & Status */}
        <div className="p-5 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="relative group">
              <div className="absolute -inset-1 bg-gradient-to-tr from-primary-600 to-primary-400 rounded-lg blur opacity-10 group-hover:opacity-30 transition duration-500" />
              <div className="relative w-9 h-9 bg-black border border-white/10 rounded-lg flex items-center justify-center text-gray-200 font-black text-lg shadow-2xl">
                A
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-black text-gray-200 tracking-tighter uppercase">Agio</div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className={`w-1 h-1 rounded-full ${
                  health?.ready ? 'bg-emerald-500/80 shadow-[0_0_8px_rgba(16,185,129,0.3)]' : 'bg-amber-500/80 animate-pulse'
                }`} />
                <span className="text-[9px] font-bold text-gray-600 uppercase tracking-widest leading-none">
                  {health?.ready ? 'Operational' : 'Initializing'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 p-3 space-y-6 overflow-y-auto custom-scrollbar pt-6">
          <div className="space-y-1">
            <div className="px-3 mb-3 text-[8px] font-black text-gray-800 uppercase tracking-[0.3em]">Main Interface</div>
            {navItems.map((item) => {
              const Icon = item.icon
              const active = isActive(item.path)
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`group flex items-center justify-between px-3 py-2 rounded-lg text-[13px] font-bold transition-all duration-200 ${
                    active
                      ? 'bg-white/5 text-primary-400/90 shadow-sm border border-white/5'
                      : 'text-gray-600 hover:text-gray-300 hover:bg-white/[0.02]'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-3.5 h-3.5 transition-colors ${active ? 'text-primary-500/80' : 'group-hover:text-gray-400'}`} />
                    <span>{item.label}</span>
                  </div>
                  {active && <div className="w-1 h-1 rounded-full bg-primary-500/60 shadow-[0_0_8px_rgba(59,130,246,0.4)]" />}
                </Link>
              )
            })}
          </div>

          <div className="space-y-1">
            <div className="px-3 mb-3 text-[8px] font-black text-gray-800 uppercase tracking-[0.3em]">Management</div>
            {bottomNavItems.map((item) => {
              const Icon = item.icon
              const active = isActive(item.path)
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`group flex items-center justify-between px-3 py-2 rounded-lg text-[13px] font-bold transition-all duration-200 ${
                    active
                      ? 'bg-white/5 text-primary-400/90 shadow-sm border border-white/5'
                      : 'text-gray-600 hover:text-gray-300 hover:bg-white/[0.02]'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-3.5 h-3.5 transition-colors ${active ? 'text-primary-500/80' : 'group-hover:text-gray-400'}`} />
                    <span>{item.label}</span>
                  </div>
                  {active && <div className="w-1 h-1 rounded-full bg-primary-500/60 shadow-[0_0_8px_rgba(59,130,246,0.4)]" />}
                </Link>
              )
            })}
          </div>
        </nav>

        {/* Bottom Section */}
        <div className="p-3 border-t border-white/5 bg-black/20">
          <div className="px-3 mb-2 text-[8px] font-black text-gray-800 uppercase tracking-[0.3em]">Resources</div>
          <div className="space-y-0.5">
            {externalLinks.map((item) => {
              const Icon = item.icon
              return (
                <a
                  key={item.href}
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between px-3 py-1.5 rounded-lg text-[11px] font-bold text-gray-600 hover:text-gray-400 hover:bg-white/5 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <Icon className="w-3 h-3" />
                    <span>{item.label}</span>
                  </div>
                  <ExternalLink className="w-2.5 h-2.5 opacity-20" />
                </a>
              )
            })}
          </div>
          
          <div className="mt-4 px-3 py-2 bg-white/5 rounded-lg border border-white/5 flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
              <Cpu className="w-3.5 h-3.5 text-emerald-500/70" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[9px] font-black text-gray-500 uppercase tracking-tighter">v0.8.2-beta</p>
              <p className="text-[8px] text-gray-700 font-bold truncate">Build #20260105</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 ml-60 flex flex-col min-h-screen relative overflow-hidden">
        {/* Subtle background glow */}
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary-500/5 blur-[120px] rounded-full -mr-64 -mt-64 pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-emerald-500/5 blur-[100px] rounded-full -ml-32 -mb-32 pointer-events-none" />

        {/* Page Content */}
        <main className="flex-1 p-6 relative z-10">
          {children}
        </main>
      </div>
    </div>
  )
}
