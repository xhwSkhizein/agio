/**
 * Hook for managing scroll behavior in chat
 */

import { useEffect, useRef, useCallback } from 'react'

export function useScrollManagement() {
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const isUserScrolledUpRef = useRef(false)
  const scrollTimeoutRef = useRef<number | null>(null)

  const scrollToBottom = useCallback((force = false) => {
    if (!force && isUserScrolledUpRef.current) {
      return
    }

    const scrollContainer = scrollContainerRef.current
    if (!scrollContainer) return

    // Clear any pending scroll
    if (scrollTimeoutRef.current !== null) {
      cancelAnimationFrame(scrollTimeoutRef.current)
    }

    // Use requestAnimationFrame to ensure DOM is updated
    scrollTimeoutRef.current = requestAnimationFrame(() => {
      // Use scrollTop instead of scrollIntoView to avoid visual jumps
      // This provides smoother scrolling during streaming updates
      scrollContainer.scrollTop = scrollContainer.scrollHeight
      scrollTimeoutRef.current = null
    })
  }, [])

  // Check if user is near bottom of scroll container
  const isNearBottom = useCallback((element: HTMLElement): boolean => {
    const threshold = 150
    const distanceFromBottom = element.scrollHeight - element.scrollTop - element.clientHeight
    return distanceFromBottom < threshold
  }, [])

  // Handle scroll events to detect user scrolling up
  useEffect(() => {
    const scrollContainer = scrollContainerRef.current
    if (!scrollContainer) return

    const handleScroll = () => {
      isUserScrolledUpRef.current = !isNearBottom(scrollContainer)
    }

    scrollContainer.addEventListener('scroll', handleScroll, { passive: true })
    return () => scrollContainer.removeEventListener('scroll', handleScroll)
  }, [isNearBottom])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current !== null) {
        cancelAnimationFrame(scrollTimeoutRef.current)
      }
    }
  }, [])

  return {
    messagesEndRef,
    scrollContainerRef,
    isUserScrolledUpRef,
    scrollToBottom,
    isNearBottom,
  }
}
