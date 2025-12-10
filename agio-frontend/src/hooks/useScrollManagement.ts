/**
 * Hook for managing scroll behavior in chat
 */

import { useEffect, useRef } from 'react'

export function useScrollManagement() {
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const isUserScrolledUpRef = useRef(false)

  const scrollToBottom = (force = false) => {
    if (!force && isUserScrolledUpRef.current) {
      // User has scrolled up, don't auto-scroll unless forced
      return
    }
    // Use requestAnimationFrame to ensure DOM is updated
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: force ? 'auto' : 'smooth' })
    })
  }

  // Check if user is near bottom of scroll container
  const isNearBottom = (element: HTMLElement): boolean => {
    const threshold = 150 // pixels from bottom - consider "near bottom" if within 150px
    const distanceFromBottom = element.scrollHeight - element.scrollTop - element.clientHeight
    return distanceFromBottom < threshold
  }

  // Handle scroll events to detect user scrolling up
  useEffect(() => {
    const scrollContainer = scrollContainerRef.current
    if (!scrollContainer) return

    const handleScroll = () => {
      isUserScrolledUpRef.current = !isNearBottom(scrollContainer)
    }

    scrollContainer.addEventListener('scroll', handleScroll, { passive: true })
    return () => scrollContainer.removeEventListener('scroll', handleScroll)
  }, [])

  return {
    messagesEndRef,
    scrollContainerRef,
    isUserScrolledUpRef,
    scrollToBottom,
    isNearBottom,
  }
}
