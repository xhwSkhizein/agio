/**
 * Hook for managing agent/workflow selection
 */

import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'

const DEFAULT_AGENT = 'master_orchestrator'

export function useAgentSelection() {
  const location = useLocation()
  const locationState = location.state as { pendingMessage?: string; agentId?: string } | null
  const forkedAgentId = locationState?.agentId

  const [selectedAgentId, setSelectedAgentId] = useState<string>(forkedAgentId || DEFAULT_AGENT)
  const [showAgentDropdown, setShowAgentDropdown] = useState(false)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (showAgentDropdown) {
        const target = e.target as HTMLElement
        if (!target.closest('[data-agent-dropdown]')) {
          setShowAgentDropdown(false)
        }
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [showAgentDropdown])

  return {
    selectedAgentId,
    setSelectedAgentId,
    showAgentDropdown,
    setShowAgentDropdown,
  }
}
