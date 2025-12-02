import axios, { AxiosError } from 'axios'
import toast from 'react-hot-toast'

const api = axios.create({
  baseURL: '/agio',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Error handling interceptor
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Extract error details
    const statusCode = error.response?.status
    const errorData = error.response?.data as any
    const errorMessage = errorData?.detail || errorData?.message || error.message
    
    // User-friendly toast message
    const toastMessage = `API Error: ${errorMessage}`
    toast.error(toastMessage, {
      duration: 5000,
      position: 'top-right',
    })
    
    // Detailed console logging for debugging
    console.group(`🔴 API Error [${statusCode || 'Network'}]`)
    console.error('URL:', error.config?.url)
    console.error('Method:', error.config?.method?.toUpperCase())
    console.error('Status:', statusCode)
    console.error('Message:', errorMessage)
    console.error('Response Data:', errorData)
    console.error('Full Error:', error)
    console.groupEnd()
    
    return Promise.reject(error)
  }
)

export interface Agent {
  name: string
  model: string
  tools: string[]
  memory: string | null
  knowledge: string | null
  system_prompt: string | null
  tags: string[]
}

export interface PaginatedResponse<T> {
  total: number
  items: T[]
  limit: number
  offset: number
}

export const agentService = {
  async listAgents(params?: {
    limit?: number
    offset?: number
    tag?: string
  }): Promise<PaginatedResponse<Agent>> {
    const response = await api.get('/agents', { params })
    return response.data
  },

  async getAgent(agentId: string): Promise<Agent> {
    const response = await api.get(`/agents/${agentId}`)
    return response.data
  },

  async deleteAgent(agentId: string): Promise<void> {
    await api.delete(`/agents/${agentId}`)
  },
}

export interface ChatRequest {
  agent_id: string
  message: string
  user_id?: string
  session_id?: string
  stream: boolean
}

export interface ChatResponse {
  run_id: string
  response: string
  metrics: Record<string, any>
}

export const chatService = {
  async chat(agentName: string, request: Omit<ChatRequest, 'agent_id'>): Promise<ChatResponse> {
    const response = await api.post(`/chat/${agentName}`, request)
    return response.data
  },

  // SSE streaming handled separately with EventSource
}

export interface Config {
  type: string
  name: string
  description?: string
  enabled?: boolean
  tags?: string[]
  [key: string]: any
}

export const configService = {
  async listConfigs(): Promise<Record<string, Config[]>> {
    const response = await api.get('/config')
    return response.data
  },

  async getConfig(type: string, name: string): Promise<Config> {
    const response = await api.get(`/config/${type}/${name}`)
    return response.data
  },

  async updateConfig(type: string, name: string, config: Partial<Config>): Promise<void> {
    await api.put(`/config/${type}/${name}`, { config })
  },

  async deleteConfig(type: string, name: string): Promise<void> {
    await api.delete(`/config/${type}/${name}`)
  },

  async reloadConfigs(): Promise<void> {
    await api.post('/config/reload')
  },
}

export interface Run {
  id: string
  agent_id: string
  user_id: string | null
  session_id: string | null
  status: string
  input_query: string
  response_content: string | null
  metrics: {
    total_tokens: number
    duration: number
    total_steps: number
  }
  created_at: string
}

export const sessionService = {
  async listSessions(params?: {
    user_id?: string
    limit?: number
    offset?: number
  }): Promise<PaginatedResponse<Run>> {
    const response = await api.get('/sessions', { params })
    return response.data
  },

  async getSession(sessionId: string): Promise<any> {
    const response = await api.get(`/sessions/${sessionId}`)
    return response.data
  },

  async deleteSession(sessionId: string): Promise<void> {
    await api.delete(`/sessions/${sessionId}`)
  },

  async getSessionSteps(sessionId: string): Promise<any[]> {
    const response = await api.get(`/sessions/${sessionId}/steps`)
    return response.data
  },
}

export interface AgentMetrics {
  agent_id: string
  total_runs: number
  success_rate: number
  avg_duration: number
  total_tokens: number
  avg_tokens_per_run: number
}

export interface SystemMetrics {
  total_agents: number
  total_runs: number
  active_runs: number
  total_tokens_today: number
  avg_response_time: number
}

export const metricsService = {
  async getAgentMetrics(agentId: string): Promise<AgentMetrics> {
    const response = await api.get(`/metrics/agents/${agentId}`)
    return response.data
  },

  async getSystemMetrics(): Promise<SystemMetrics> {
    const response = await api.get('/metrics/system')
    return response.data
  },
}

// Memory Service
export interface MemoryInfo {
  name: string
  type: string
  has_history: boolean
  has_semantic: boolean
}

export const memoryService = {
  async listMemories(): Promise<MemoryInfo[]> {
    const response = await api.get('/memory')
    return response.data
  },

  async getMemory(name: string): Promise<MemoryInfo> {
    const response = await api.get(`/memory/${name}`)
    return response.data
  },

  async searchMemory(name: string, query: string, userId?: string): Promise<any[]> {
    const response = await api.post(`/memory/${name}/search`, { query, user_id: userId })
    return response.data
  },
}

// Knowledge Service
export interface KnowledgeInfo {
  name: string
  type: string
}

export const knowledgeService = {
  async listKnowledge(): Promise<KnowledgeInfo[]> {
    const response = await api.get('/knowledge')
    return response.data
  },

  async getKnowledge(name: string): Promise<KnowledgeInfo> {
    const response = await api.get(`/knowledge/${name}`)
    return response.data
  },

  async searchKnowledge(name: string, query: string, limit?: number): Promise<any[]> {
    const response = await api.post(`/knowledge/${name}/search`, { query, limit })
    return response.data
  },
}

// Health Service
export const healthService = {
  async check(): Promise<{ status: string; version: string }> {
    const response = await api.get('/health')
    return response.data
  },

  async ready(): Promise<{ ready: boolean; components: number; configs: number }> {
    const response = await api.get('/health/ready')
    return response.data
  },
}

export default api
