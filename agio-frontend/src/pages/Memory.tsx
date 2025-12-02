import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { memoryService } from '../services/api'
import { Brain, Search, Loader2 } from 'lucide-react'

export default function Memory() {
  const [selectedMemory, setSelectedMemory] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [userId, setUserId] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [isSearching, setIsSearching] = useState(false)

  const { data: memoryList, isLoading } = useQuery({
    queryKey: ['memory'],
    queryFn: () => memoryService.listMemories(),
  })

  const handleSearch = async () => {
    if (!selectedMemory || !searchQuery.trim()) return

    setIsSearching(true)
    try {
      const results = await memoryService.searchMemory(
        selectedMemory,
        searchQuery,
        userId || undefined
      )
      setSearchResults(results)
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white mb-2">Memory</h1>
        <p className="text-gray-400">View and manage user memories and learnings.</p>
      </div>

      {isLoading ? (
        <div className="text-gray-500">Loading memory stores...</div>
      ) : !memoryList || memoryList.length === 0 ? (
        <div className="bg-surface border border-border rounded-lg p-8 text-center">
          <Brain className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">No memory stores configured.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Memory List */}
          <div>
            <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
              Memory Stores
            </h2>
            <div className="grid gap-3">
              {memoryList.map((mem) => (
                <button
                  key={mem.name}
                  onClick={() => setSelectedMemory(mem.name)}
                  className={`bg-surface border rounded-lg p-4 text-left transition-all ${
                    selectedMemory === mem.name
                      ? 'border-primary-500'
                      : 'border-border hover:border-primary-500/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Brain className="w-5 h-5 text-gray-400" />
                      <div>
                        <div className="text-sm font-medium text-white">{mem.name}</div>
                        <div className="text-xs text-gray-500">Type: {mem.type}</div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {mem.has_history && (
                        <span className="px-2 py-0.5 text-xs bg-blue-900/30 text-blue-400 rounded">
                          History
                        </span>
                      )}
                      {mem.has_semantic && (
                        <span className="px-2 py-0.5 text-xs bg-purple-900/30 text-purple-400 rounded">
                          Semantic
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Search Section */}
          {selectedMemory && (
            <div>
              <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
                Search "{selectedMemory}"
              </h2>
              <div className="space-y-3 mb-4">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    placeholder="User ID (optional)"
                    className="w-48 px-3 py-2 bg-surface border border-border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 text-sm"
                  />
                </div>
                <div className="flex gap-2">
                  <div className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                      placeholder="Search memories..."
                      className="w-full pl-10 pr-4 py-2 bg-surface border border-border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500"
                    />
                  </div>
                  <button
                    onClick={handleSearch}
                    disabled={isSearching || !searchQuery.trim()}
                    className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {isSearching ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      'Search'
                    )}
                  </button>
                </div>
              </div>

              {/* Results */}
              {searchResults.length > 0 && (
                <div className="space-y-2">
                  {searchResults.map((result, index) => (
                    <div
                      key={index}
                      className="bg-surface border border-border rounded-lg p-4"
                    >
                      <p className="text-sm text-gray-300 whitespace-pre-wrap">
                        {result.content}
                      </p>
                      {result.category && (
                        <div className="mt-2">
                          <span className="px-2 py-0.5 text-xs bg-surfaceHighlight text-gray-400 rounded">
                            {result.category}
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
