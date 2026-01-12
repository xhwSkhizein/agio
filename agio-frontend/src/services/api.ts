import axios, { AxiosError } from "axios";
import toast from "react-hot-toast";

const API_BASE_URL = "/agio";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Error handling interceptor
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Extract error details
    const statusCode = error.response?.status;
    const errorData = error.response?.data as any;
    const errorMessage =
      errorData?.detail || errorData?.message || error.message;

    // User-friendly toast message
    const toastMessage = `API Error: ${errorMessage}`;
    toast.error(toastMessage, {
      duration: 5000,
      position: "top-right",
    });

    // Detailed console logging for debugging
    console.group(`🔴 API Error [${statusCode || "Network"}]`);
    console.error("URL:", error.config?.url);
    console.error("Method:", error.config?.method?.toUpperCase());
    console.error("Status:", statusCode);
    console.error("Message:", errorMessage);
    console.error("Response Data:", errorData);
    console.error("Full Error:", error);
    console.groupEnd();

    return Promise.reject(error);
  }
);

export interface ToolInfo {
  type: string;
  name?: string | null;
  agent?: string | null;
  description?: string | null;
}

export interface Agent {
  name: string;
  model?: string | null;
  tools: (string | ToolInfo)[];
  system_prompt: string | null;
  tags: string[];
}

export interface PaginatedResponse<T> {
  total: number;
  items: T[];
  limit: number;
  offset: number;
}

export const agentService = {
  async listAgents(params?: {
    limit?: number;
    offset?: number;
    tag?: string;
  }): Promise<PaginatedResponse<Agent>> {
    const response = await api.get("/agents", { params });
    return response.data;
  },

  async getAgent(agentId: string): Promise<Agent> {
    const response = await api.get(`/agents/${agentId}`);
    return response.data;
  },

  async deleteAgent(agentId: string): Promise<void> {
    await api.delete(`/agents/${agentId}`);
  },
};

export interface Config {
  type: string;
  name: string;
  description?: string;
  enabled?: boolean;
  tags?: string[];
  [key: string]: any;
}

export const configService = {
  async listConfigs(): Promise<Record<string, Config[]>> {
    const response = await api.get("/config");
    return response.data;
  },

  async getConfig(type: string, name: string): Promise<Config> {
    const response = await api.get(`/config/${type}/${name}`);
    return response.data;
  },

  async updateConfig(
    type: string,
    name: string,
    config: Partial<Config>
  ): Promise<void> {
    await api.put(`/config/${type}/${name}`, { config });
  },

  async deleteConfig(type: string, name: string): Promise<void> {
    await api.delete(`/config/${type}/${name}`);
  },

  async reloadConfigs(): Promise<void> {
    await api.post("/config/reload");
  },
};

export interface Run {
  id: string;
  agent_id: string;
  user_id: string | null;
  session_id: string | null;
  status: string;
  input_query: string;
  response_content: string | null;
  metrics: {
    total_tokens: number;
    duration: number;
    total_steps: number;
  };
  created_at: string;
}

// Session Summary for aggregated view
export interface SessionSummary {
  session_id: string;
  agent_id: string | null;
  user_id: string | null;
  run_count: number;
  step_count: number;
  last_message: string | null;
  last_activity: string;
  status: string;
}

export interface SessionStep {
  id: string;
  session_id: string;
  sequence: number;
  role: "user" | "assistant" | "tool";
  content: string | null;
  reasoning_content?: string | null;
  tool_calls?: Array<{
    id: string;
    type: string;
    function: {
      name: string;
      arguments: string;
    };
    index?: number;
  }>;
  name?: string;
  tool_call_id?: string;
  created_at: string;
}

export const sessionService = {
  async listSessions(params?: {
    user_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<PaginatedResponse<Run>> {
    const response = await api.get("/sessions", { params });
    return response.data;
  },

  async listSessionSummaries(params?: {
    user_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<PaginatedResponse<SessionSummary>> {
    const response = await api.get("/sessions/summary", { params });
    return response.data;
  },

  async getSession(sessionId: string): Promise<any> {
    const response = await api.get(`/sessions/${sessionId}`);
    return response.data;
  },

  async deleteSession(sessionId: string): Promise<void> {
    await api.delete(`/sessions/${sessionId}`);
  },

  async getSessionSteps(
    sessionId: string,
    limit: number = 100,
    offset: number = 0
  ): Promise<PaginatedResponse<SessionStep>> {
    const params = { limit, offset };
    const response = await api.get(`/sessions/${sessionId}/steps`, { params });
    return response.data;
  },

  async getAllSessionSteps(sessionId: string): Promise<SessionStep[]> {
    const allSteps: SessionStep[] = [];
    let offset = 0;
    const limit = 100;

    while (true) {
      const response = await this.getSessionSteps(sessionId, limit, offset);
      allSteps.push(...response.items);

      if (response.items.length < limit || allSteps.length >= response.total) {
        break;
      }
      offset += limit;
    }

    return allSteps;
  },

  async forkSession(
    sessionId: string,
    sequence: number,
    options?: { content?: string; tool_calls?: any[] }
  ): Promise<{
    new_session_id: string;
    copied_steps: number;
    last_sequence: number;
    pending_user_message?: string;
  }> {
    const response = await api.post(`/sessions/${sessionId}/fork`, {
      sequence,
      content: options?.content,
      tool_calls: options?.tool_calls,
    });
    return response.data;
  },

  // Resume session URL for SSE streaming (used directly with fetch POST)
  getResumeSessionUrl(sessionId: string, agentId: string): string {
    return `${API_BASE_URL}/sessions/${sessionId}/resume?agent_id=${encodeURIComponent(
      agentId
    )}`;
  },
};

// Runnable Service (unified Agent API)
export interface AgentInfo {
  id: string;
  type: string; // "Agent"
  description?: string;
}

export interface AgentListResponse {
  items: AgentInfo[];
  total: number;
}

export const runnableService = {
  async listRunnables(): Promise<AgentListResponse> {
    const response = await api.get("/agents");
    return response.data;
  },

  async getRunnableInfo(runnableId: string): Promise<any> {
    const response = await api.get(`/agents/${runnableId}`);
    return response.data;
  },

  // Get SSE stream URL for running a Runnable
  getRunUrl(runnableId: string): string {
    return `${API_BASE_URL}/agents/${runnableId}/run`;
  },
};

// Health Service
export const healthService = {
  async check(): Promise<{ status: string; version: string }> {
    const response = await api.get("/health");
    return response.data;
  },

  async ready(): Promise<{
    ready: boolean;
    components: number;
    configs: number;
  }> {
    const response = await api.get("/health/ready");
    return response.data;
  },
};

export default api;
