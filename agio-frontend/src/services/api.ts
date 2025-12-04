import axios, { AxiosError } from 'axios'
import toast from 'react-hot-toast'

const API_BASE_URL = '/agio'

const api = axios.create({
  baseURL: API_BASE_URL,
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

// Session Summary for aggregated view
export interface SessionSummary {
  session_id: string
  agent_id: string
  user_id: string | null
  workflow_id: string | null
  run_count: number
  step_count: number
  last_message: string | null
  last_activity: string
  status: string
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

  async listSessionSummaries(params?: {
    user_id?: string
    limit?: number
    offset?: number
  }): Promise<PaginatedResponse<SessionSummary>> {
    const response = await api.get('/sessions/summary', { params })
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

  async forkSession(
    sessionId: string, 
    sequence: number, 
    options?: { content?: string; tool_calls?: any[] }
  ): Promise<{ 
    new_session_id: string
    copied_steps: number
    last_sequence: number
    pending_user_message?: string 
  }> {
    const response = await api.post(`/sessions/${sessionId}/fork`, { 
      sequence, 
      content: options?.content,
      tool_calls: options?.tool_calls,
    })
    return response.data
  },

  // Resume session URL for SSE streaming (used directly with fetch POST)
  getResumeSessionUrl(sessionId: string, agentId: string): string {
    return `${API_BASE_URL}/sessions/${sessionId}/resume?agent_id=${encodeURIComponent(agentId)}`
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

// Runnable Service (unified Agent/Workflow API)
export interface RunnableInfo {
  id: string
  type: string  // "Agent", "PipelineWorkflow", "LoopWorkflow", "ParallelWorkflow"
  description?: string
}

export interface RunnableListResponse {
  agents: RunnableInfo[]
  workflows: RunnableInfo[]
}

export interface WorkflowStage {
  id: string
  runnable: string
  input_template: string
  condition: string | null
}

export interface WorkflowStructure {
  id: string
  type: string
  stages: WorkflowStage[]
  loop_condition?: string
  max_iterations?: number
  merge_template?: string
}

export const runnableService = {
  async listRunnables(): Promise<RunnableListResponse> {
    const response = await api.get('/runnables')
    return response.data
  },

  async getRunnableInfo(runnableId: string): Promise<any> {
    const response = await api.get(`/runnables/${runnableId}`)
    return response.data
  },

  // Get SSE stream URL for running a Runnable
  getRunUrl(runnableId: string): string {
    return `${API_BASE_URL}/runnables/${runnableId}/run`
  },
}

export const workflowService = {
  async listWorkflows(): Promise<Array<{ id: string; type: string; stage_count: number }>> {
    const response = await api.get('/workflows')
    return response.data
  },

  async getWorkflowStructure(workflowId: string): Promise<WorkflowStructure> {
    const response = await api.get(`/workflows/${workflowId}`)
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

// LLM Logs Service
export interface LLMCallLog {
  id: string
  timestamp: string
  agent_name: string | null
  session_id: string | null
  run_id: string | null
  model_id: string
  model_name: string | null
  provider: string
  request: Record<string, any>
  messages: Array<{ role: string; content: string; [key: string]: any }>
  tools: Array<Record<string, any>> | null
  response_content: string | null
  response_tool_calls: Array<Record<string, any>> | null
  finish_reason: string | null
  status: 'running' | 'completed' | 'error'
  error: string | null
  duration_ms: number | null
  first_token_ms: number | null
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
}

export interface LLMLogListResponse {
  total: number
  items: LLMCallLog[]
  limit: number
  offset: number
}

export interface LLMStats {
  total_calls: number
  completed_calls: number
  error_calls: number
  running_calls: number
  success_rate: number
  total_tokens: number
  total_input_tokens: number
  total_output_tokens: number
  avg_duration_ms: number
  avg_first_token_ms: number
  provider_breakdown: Record<string, number>
}

export const llmLogsService = {
  async listLogs(params?: {
    agent_name?: string
    session_id?: string
    run_id?: string
    model_id?: string
    provider?: string
    status?: string
    limit?: number
    offset?: number
  }): Promise<LLMLogListResponse> {
    const response = await api.get('/llm/logs', { params })
    return response.data
  },

  async getLog(logId: string): Promise<LLMCallLog> {
    const response = await api.get(`/llm/logs/${logId}`)
    return response.data
  },

  async getStats(params?: {
    agent_name?: string
    start_time?: string
    end_time?: string
  }): Promise<LLMStats> {
    const response = await api.get('/llm/stats', { params })
    return response.data
  },

  // SSE streaming endpoint URL
  getStreamUrl(params?: {
    agent_name?: string
    session_id?: string
    run_id?: string
  }): string {
    const searchParams = new URLSearchParams()
    if (params?.agent_name) searchParams.set('agent_name', params.agent_name)
    if (params?.session_id) searchParams.set('session_id', params.session_id)
    if (params?.run_id) searchParams.set('run_id', params.run_id)
    const query = searchParams.toString()
    return `/agio/llm/logs/stream${query ? `?${query}` : ''}`
  },
}

export default api
