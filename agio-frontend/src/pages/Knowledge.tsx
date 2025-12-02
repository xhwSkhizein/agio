import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { knowledgeService } from '../services/api'
import { Database, Search, Loader2 } from 'lucide-react'

export default function Knowledge() {
  const [selectedKnowledge, setSelectedKnowledge] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [isSearching, setIsSearching] = useState(false)

  const { data: knowledgeList, isLoading } = useQuery({
    queryKey: ['knowledge'],
    queryFn: () => knowledgeService.listKnowledge(),
  })

  const handleSearch = async () => {
    if (!selectedKnowledge || !searchQuery.trim()) return

    setIsSearching(true)
    try {
      const results = await knowledgeService.searchKnowledge(
        selectedKnowledge,
        searchQuery,
        10
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
        <h1 className="text-2xl font-semibold text-white mb-2">Knowledge</h1>
        <p className="text-gray-400">View and search your knowledge bases.</p>
      </div>

      {isLoading ? (
        <div className="text-gray-500">Loading knowledge bases...</div>
      ) : !knowledgeList || knowledgeList.length === 0 ? (
        <div className="bg-surface border border-border rounded-lg p-8 text-center">
          <Database className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">No knowledge bases configured.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Knowledge List */}
          <div>
            <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
              Knowledge Bases
            </h2>
            <div className="grid gap-3">
              {knowledgeList.map((kb) => (
                <button
                  key={kb.name}
                  onClick={() => setSelectedKnowledge(kb.name)}
                  className={`bg-surface border rounded-lg p-4 text-left transition-all ${
                    selectedKnowledge === kb.name
                      ? 'border-primary-500'
                      : 'border-border hover:border-primary-500/50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Database className="w-5 h-5 text-gray-400" />
                    <div>
                      <div className="text-sm font-medium text-white">{kb.name}</div>
                      <div className="text-xs text-gray-500">Type: {kb.type}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Search Section */}
          {selectedKnowledge && (
            <div>
              <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
                Search "{selectedKnowledge}"
              </h2>
              <div className="flex gap-2 mb-4">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    placeholder="Search knowledge base..."
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
                      {result.score && (
                        <div className="mt-2 text-xs text-gray-500">
                          Score: {result.score.toFixed(3)}
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
