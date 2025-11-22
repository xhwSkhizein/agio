import axios, { AxiosError } from 'axios'
import toast from 'react-hot-toast'

const api = axios.create({
  baseURL: '/api',
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
  id: string
  name: string
  description: string | null
  model: string
  tools: string[]
  enabled: boolean
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
  async chat(request: ChatRequest): Promise<ChatResponse> {
    const response = await api.post('/chat', request)
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
  async listConfigs(): Promise<Record<string, Config>> {
    const response = await api.get('/config/')
    return response.data
  },

  async getConfig(name: string): Promise<Config> {
    const response = await api.get(`/config/${name}`)
    return response.data
  },

  async updateConfig(name: string, config: Config): Promise<void> {
    await api.put(`/config/${name}`, { config })
  },

  async deleteConfig(name: string): Promise<void> {
    await api.delete(`/config/${name}`)
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

export const runService = {
  async listRuns(params?: {
    agent_id?: string
    user_id?: string
    status?: string
    limit?: number
    offset?: number
  }): Promise<PaginatedResponse<Run>> {
    const response = await api.get('/runs', { params })
    return response.data
  },

  async getRun(runId: string): Promise<Run> {
    const response = await api.get(`/runs/${runId}`)
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

export default api
