import { Link, useLocation } from 'react-router-dom'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  
  const isActive = (path: string) => {
    return location.pathname === path ? 'bg-surfaceHighlight text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-surfaceHighlight/50';
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="bg-surface/50 backdrop-blur-md border-b border-border sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-14">
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-2">
                <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center text-white font-bold">
                  A
                </div>
                <span className="text-xl font-bold text-white tracking-tight">
                  Agio
                </span>
              </Link>
              <nav className="hidden md:flex space-x-1">
                {[
                  { path: '/', label: 'Dashboard' },
                  { path: '/agents', label: 'Agents' },
                  { path: '/runs', label: 'Runs' },
                  { path: '/metrics', label: 'Metrics' },
                  { path: '/config', label: 'Config' },
                ].map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${isActive(item.path)}`}
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col">
        {children}
      </main>
    </div>
  )
}
