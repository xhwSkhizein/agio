/**
 * Chat page types and interfaces
 * 
 * Note: Most types have been moved to types/execution.ts
 * This file contains legacy types for backward compatibility.
 */

// Generate unique ID
let idCounter = 0
export const generateId = () => `event_${Date.now()}_${++idCounter}`
