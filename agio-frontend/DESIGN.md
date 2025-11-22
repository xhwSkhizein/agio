# Agio React Frontend 详细设计

> **目标**：打造现代化可观测平台 - 美观、易用、功能强大的 Agent 管理界面

## 📋 目录

1. [设计理念](#设计理念)
2. [技术栈](#技术栈)
3. [项目结构](#项目结构)
4. [核心页面](#核心页面)
5. [组件设计](#组件设计)
6. [状态管理](#状态管理)
7. [路由设计](#路由设计)
8. [UI/UX 设计](#uiux-设计)
9. [实时功能](#实时功能)
10. [部署配置](#部署配置)

---

## 设计理念

### 核心原则

1. **用户体验优先** - 直观、流畅、响应式
2. **数据可视化** - 图表、时间线、实时流
3. **性能优化** - 虚拟滚动、懒加载、缓存
4. **类型安全** - TypeScript 全覆盖
5. **现代化设计** - 简洁、美观、专业

### 设计目标

- ✅ **Dashboard** - 一目了然的系统概览
- ✅ **Agent 管理** - 可视化配置和管理
- ✅ **Chat 界面** - 实时流式交互
- ✅ **Run 详情** - 完整的执行追踪
- ✅ **时光旅行** - 可视化调试工具
- ✅ **配置编辑** - 在线编辑 YAML 配置

---

## 技术栈

### 核心技术

```json
{
  "framework": "React 18+",
  "language": "TypeScript",
  "build": "Vite",
  "styling": "TailwindCSS + shadcn/ui",
  "state": "Zustand + TanStack Query",
  "routing": "React Router v6",
  "charts": "Recharts / Apache ECharts",
  "forms": "React Hook Form + Zod",
  "streaming": "EventSource API",
  "markdown": "react-markdown",
  "code": "Monaco Editor"
}
```

### 依赖包

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "zustand": "^4.4.0",
    "@tanstack/react-query": "^5.0.0",
    "axios": "^1.6.0",
    "tailwindcss": "^3.3.0",
    "@radix-ui/react-*": "latest",
    "lucide-react": "^0.300.0",
    "recharts": "^2.10.0",
    "react-hook-form": "^7.48.0",
    "zod": "^3.22.0",
    "react-markdown": "^9.0.0",
    "@monaco-editor/react": "^4.6.0",
    "date-fns": "^3.0.0"
  }
}
```

---

## 项目结构

```
agio-frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── main.tsx                # 入口
│   ├── App.tsx                 # 根组件
│   ├── components/             # 通用组件
│   │   ├── ui/                 # shadcn/ui 组件
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   └── ...
│   │   ├── layout/             # 布局组件
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── Layout.tsx
│   │   ├── chat/               # Chat 组件
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   └── ChatStream.tsx
│   │   ├── run/                # Run 组件
│   │   │   ├── RunTimeline.tsx
│   │   │   ├── RunMetrics.tsx
│   │   │   └── StepViewer.tsx
│   │   └── common/             # 通用组件
│   │       ├── CodeBlock.tsx
│   │       ├── JsonViewer.tsx
│   │       └── LoadingSpinner.tsx
│   ├── pages/                  # 页面
│   │   ├── Dashboard.tsx
│   │   ├── AgentList.tsx
│   │   ├── AgentDetail.tsx
│   │   ├── ChatPage.tsx
│   │   ├── RunList.tsx
│   │   ├── RunDetail.tsx
│   │   ├── ConfigEditor.tsx
│   │   └── MetricsDashboard.tsx
│   ├── hooks/                  # 自定义 Hooks
│   │   ├── useAgents.ts
│   │   ├── useChat.ts
│   │   ├── useRuns.ts
│   │   ├── useCheckpoints.ts
│   │   └── useSSE.ts
│   ├── services/               # API 服务
│   │   ├── api.ts              # Axios 配置
│   │   ├── agents.ts
│   │   ├── chat.ts
│   │   ├── runs.ts
│   │   └── config.ts
│   ├── stores/                 # Zustand 状态
│   │   ├── authStore.ts
│   │   ├── uiStore.ts
│   │   └── chatStore.ts
│   ├── types/                  # TypeScript 类型
│   │   ├── agent.ts
│   │   ├── run.ts
│   │   ├── checkpoint.ts
│   │   └── api.ts
│   ├── utils/                  # 工具函数
│   │   ├── format.ts
│   │   ├── date.ts
│   │   └── validation.ts
│   └── styles/                 # 样式
│       └── globals.css
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

---

## 核心页面

### 1. Dashboard (仪表盘)

**功能**：系统概览、关键指标、最近活动

**布局**：
```
┌─────────────────────────────────────────────────────────┐
│  Header (Logo, Search, User)                            │
├──────┬──────────────────────────────────────────────────┤
│      │  📊 Dashboard                                     │
│      │                                                   │
│ Side │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐│
│ bar  │  │ Agents  │ │  Runs   │ │ Tokens  │ │ Uptime ││
│      │  │   10    │ │  1,234  │ │ 150K    │ │ 99.9%  ││
│      │  └─────────┘ └─────────┘ └─────────┘ └────────┘│
│      │                                                   │
│      │  📈 Usage Trends (Last 7 Days)                   │
│      │  ┌─────────────────────────────────────────────┐│
│      │  │         [Line Chart]                        ││
│      │  └─────────────────────────────────────────────┘│
│      │                                                   │
│      │  📋 Recent Runs                                  │
│      │  ┌─────────────────────────────────────────────┐│
│      │  │ Run #123 | Agent: support | 2m ago | ✓     ││
│      │  │ Run #122 | Agent: analyst | 5m ago | ✓     ││
│      │  └─────────────────────────────────────────────┘│
└──────┴──────────────────────────────────────────────────┘
```

**组件**：
```tsx
// src/pages/Dashboard.tsx

import { Card } from '@/components/ui/card';
import { useQuery } from '@tanstack/react-query';
import { getSystemMetrics, getRecentRuns } from '@/services/api';

export function Dashboard() {
  const { data: metrics } = useQuery({
    queryKey: ['system-metrics'],
    queryFn: getSystemMetrics
  });

  const { data: recentRuns } = useQuery({
    queryKey: ['recent-runs'],
    queryFn: () => getRecentRuns({ limit: 10 })
  });

  return (
    <div className="p-6 space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="Total Agents"
          value={metrics?.total_agents}
          icon={<BotIcon />}
        />
        <StatCard
          title="Total Runs"
          value={metrics?.total_runs}
          icon={<ActivityIcon />}
        />
        <StatCard
          title="Tokens Today"
          value={formatNumber(metrics?.total_tokens_today)}
          icon={<ZapIcon />}
        />
        <StatCard
          title="Avg Response Time"
          value={`${metrics?.avg_response_time}s`}
          icon={<ClockIcon />}
        />
      </div>

      {/* Usage Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Usage Trends</CardTitle>
        </CardHeader>
        <CardContent>
          <UsageChart data={metrics?.timeseries} />
        </CardContent>
      </Card>

      {/* Recent Runs */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Runs</CardTitle>
        </CardHeader>
        <CardContent>
          <RunsTable runs={recentRuns} />
        </CardContent>
      </Card>
    </div>
  );
}
```

---

### 2. Agent 管理

**功能**：列表、创建、编辑、删除 Agent

**Agent 列表页**：
```tsx
// src/pages/AgentList.tsx

import { useAgents } from '@/hooks/useAgents';
import { AgentCard } from '@/components/agent/AgentCard';
import { Button } from '@/components/ui/button';

export function AgentList() {
  const { data: agents, isLoading } = useAgents();
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Agents</h1>
        <Button onClick={() => setShowCreateDialog(true)}>
          <PlusIcon className="mr-2" />
          Create Agent
        </Button>
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {agents?.map(agent => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      )}

      <CreateAgentDialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
      />
    </div>
  );
}
```

**Agent 卡片组件**：
```tsx
// src/components/agent/AgentCard.tsx

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface AgentCardProps {
  agent: Agent;
}

export function AgentCard({ agent }: AgentCardProps) {
  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer">
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <CardTitle>{agent.name}</CardTitle>
            <CardDescription>{agent.description}</CardDescription>
          </div>
          <Badge variant={agent.enabled ? "success" : "secondary"}>
            {agent.enabled ? "Active" : "Inactive"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 text-sm">
          <div className="flex items-center">
            <BrainIcon className="mr-2 h-4 w-4" />
            <span>Model: {agent.model}</span>
          </div>
          <div className="flex items-center">
            <WrenchIcon className="mr-2 h-4 w-4" />
            <span>Tools: {agent.tools.length}</span>
          </div>
        </div>
        <div className="flex gap-2 mt-4">
          {agent.tags.map(tag => (
            <Badge key={tag} variant="outline">{tag}</Badge>
          ))}
        </div>
      </CardContent>
      <CardFooter className="flex justify-between">
        <Button variant="ghost" size="sm">
          <PlayIcon className="mr-2 h-4 w-4" />
          Test
        </Button>
        <Button variant="ghost" size="sm">
          <SettingsIcon className="mr-2 h-4 w-4" />
          Configure
        </Button>
      </CardFooter>
    </Card>
  );
}
```

---

### 3. Chat 界面

**功能**：实时流式对话、消息历史、多会话

**布局**：
```
┌─────────────────────────────────────────────────────────┐
│  Chat with customer_support                             │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  👤 User                                                 │
│  ┌────────────────────────────────────────────────────┐ │
│  │ How do I reset my password?                        │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  🤖 Assistant                                            │
│  ┌────────────────────────────────────────────────────┐ │
│  │ To reset your password, follow these steps:        │ │
│  │ 1. Go to the login page                            │ │
│  │ 2. Click "Forgot Password"                         │ │
│  │                                                     │ │
│  │ 🔧 Tool Call: search_knowledge_base                │ │
│  │    query: "reset password"                         │ │
│  │    ✓ Completed in 0.5s                             │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  [Type your message...]                          [Send] │
└──────────────────────────────────────────────────────────┘
```

**实现**：
```tsx
// src/pages/ChatPage.tsx

import { useState } from 'react';
import { useChat } from '@/hooks/useChat';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';

export function ChatPage() {
  const [agentId] = useState('customer_support');
  const { messages, sendMessage, isStreaming } = useChat(agentId);

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="border-b p-4">
        <h1 className="text-xl font-semibold">
          Chat with {agentId}
        </h1>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <ChatMessage key={index} message={message} />
        ))}
        {isStreaming && <StreamingIndicator />}
      </div>

      {/* Input */}
      <div className="border-t p-4">
        <ChatInput
          onSend={sendMessage}
          disabled={isStreaming}
        />
      </div>
    </div>
  );
}
```

**Chat Hook (SSE)**：
```tsx
// src/hooks/useChat.ts

import { useState, useCallback } from 'react';
import { useSSE } from './useSSE';

export function useChat(agentId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  const sendMessage = useCallback(async (content: string) => {
    // 添加用户消息
    const userMessage: Message = {
      role: 'user',
      content,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);

    // 开始流式接收
    setIsStreaming(true);
    let assistantContent = '';

    const eventSource = new EventSource(
      `/api/chat?agent_id=${agentId}&message=${encodeURIComponent(content)}`
    );

    eventSource.addEventListener('content_delta', (event) => {
      const data = JSON.parse(event.data);
      assistantContent += data.content;
      
      // 更新最后一条消息
      setMessages(prev => {
        const newMessages = [...prev];
        const lastMessage = newMessages[newMessages.length - 1];
        
        if (lastMessage?.role === 'assistant') {
          lastMessage.content = assistantContent;
        } else {
          newMessages.push({
            role: 'assistant',
            content: assistantContent,
            timestamp: new Date()
          });
        }
        
        return newMessages;
      });
    });

    eventSource.addEventListener('tool_call_started', (event) => {
      const data = JSON.parse(event.data);
      // 显示 Tool Call
      setMessages(prev => [...prev, {
        role: 'tool',
        tool: data.tool,
        args: data.args,
        timestamp: new Date()
      }]);
    });

    eventSource.addEventListener('run_completed', () => {
      setIsStreaming(false);
      eventSource.close();
    });

    eventSource.addEventListener('error', () => {
      setIsStreaming(false);
      eventSource.close();
    });
  }, [agentId]);

  return { messages, sendMessage, isStreaming };
}
```

---

### 4. Run 详情页

**功能**：完整执行追踪、时间线、Metrics、Checkpoint

**布局**：
```
┌─────────────────────────────────────────────────────────┐
│  Run #123 | customer_support | Completed                │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  📊 Metrics                                              │
│  ┌────────┬────────┬────────┬────────┐                  │
│  │ Steps  │ Tokens │Duration│ Cost   │                  │
│  │   3    │  150   │  2.5s  │ $0.01  │                  │
│  └────────┴────────┴────────┴────────┘                  │
│                                                          │
│  📍 Timeline                                             │
│  ┌────────────────────────────────────────────────────┐ │
│  │ ● Step 1: LLM Call (1.2s)                          │ │
│  │   ├─ Input: "Hello"                                │ │
│  │   └─ Output: "Hi! How can I help?"                 │ │
│  │                                                     │ │
│  │ ● Step 2: Tool Call (0.8s)                         │ │
│  │   ├─ Tool: search_kb                               │ │
│  │   ├─ Args: {"query": "..."}                        │ │
│  │   └─ Result: "..."                                 │ │
│  │                                                     │ │
│  │ ● Step 3: LLM Call (0.5s)                          │ │
│  │   └─ Final Response                                │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  💾 Checkpoints                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ ckpt_1 | Step 2 | Before tool call | [Restore]    │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

**实现**：
```tsx
// src/pages/RunDetail.tsx

import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getRun, getRunCheckpoints } from '@/services/runs';
import { RunTimeline } from '@/components/run/RunTimeline';
import { RunMetrics } from '@/components/run/RunMetrics';
import { CheckpointList } from '@/components/run/CheckpointList';

export function RunDetail() {
  const { runId } = useParams();
  
  const { data: run } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => getRun(runId!)
  });

  const { data: checkpoints } = useQuery({
    queryKey: ['checkpoints', runId],
    queryFn: () => getRunCheckpoints(runId!)
  });

  if (!run) return <LoadingSpinner />;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Run #{run.id}</h1>
          <p className="text-muted-foreground">
            Agent: {run.agent_id} | {formatDate(run.created_at)}
          </p>
        </div>
        <Badge variant={getStatusVariant(run.status)}>
          {run.status}
        </Badge>
      </div>

      {/* Metrics */}
      <RunMetrics metrics={run.metrics} />

      {/* Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Execution Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <RunTimeline steps={run.steps} />
        </CardContent>
      </Card>

      {/* Checkpoints */}
      <Card>
        <CardHeader>
          <CardTitle>Checkpoints</CardTitle>
        </CardHeader>
        <CardContent>
          <CheckpointList checkpoints={checkpoints} />
        </CardContent>
      </Card>
    </div>
  );
}
```

**Timeline 组件**：
```tsx
// src/components/run/RunTimeline.tsx

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface RunTimelineProps {
  steps: RunStep[];
}

export function RunTimeline({ steps }: RunTimelineProps) {
  return (
    <div className="space-y-4">
      {steps.map((step, index) => (
        <div key={step.id} className="flex gap-4">
          {/* Timeline Line */}
          <div className="flex flex-col items-center">
            <div className="w-3 h-3 rounded-full bg-primary" />
            {index < steps.length - 1 && (
              <div className="w-0.5 h-full bg-border" />
            )}
          </div>

          {/* Step Content */}
          <Card className="flex-1">
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="text-base">
                    Step {step.step_num}: {getStepType(step)}
                  </CardTitle>
                  <CardDescription>
                    {formatDuration(step.metrics.duration)}
                  </CardDescription>
                </div>
                <Badge>{step.metrics.total_tokens} tokens</Badge>
              </div>
            </CardHeader>
            <CardContent>
              {/* Messages */}
              {step.model_response && (
                <div className="space-y-2">
                  <div className="text-sm font-medium">Response:</div>
                  <div className="bg-muted p-3 rounded">
                    {step.model_response.content}
                  </div>
                </div>
              )}

              {/* Tool Calls */}
              {step.tool_results?.map(tool => (
                <div key={tool.id} className="mt-4">
                  <div className="flex items-center gap-2 mb-2">
                    <WrenchIcon className="h-4 w-4" />
                    <span className="font-medium">{tool.name}</span>
                  </div>
                  <CodeBlock
                    language="json"
                    code={JSON.stringify(tool.args, null, 2)}
                  />
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      ))}
    </div>
  );
}
```

---

### 5. 配置编辑器

**功能**：在线编辑 YAML 配置、实时验证、热重载

**实现**：
```tsx
// src/pages/ConfigEditor.tsx

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import Editor from '@monaco-editor/react';
import { getConfig, updateConfig } from '@/services/config';

export function ConfigEditor() {
  const [selectedComponent, setSelectedComponent] = useState('gpt4');
  const [code, setCode] = useState('');

  const { data: config } = useQuery({
    queryKey: ['config', selectedComponent],
    queryFn: () => getConfig(selectedComponent),
    onSuccess: (data) => {
      setCode(yaml.stringify(data));
    }
  });

  const updateMutation = useMutation({
    mutationFn: (newConfig: any) => 
      updateConfig(selectedComponent, newConfig),
    onSuccess: () => {
      toast.success('Configuration updated successfully');
    }
  });

  const handleSave = () => {
    try {
      const parsed = yaml.parse(code);
      updateMutation.mutate(parsed);
    } catch (error) {
      toast.error('Invalid YAML');
    }
  };

  return (
    <div className="flex h-screen">
      {/* Sidebar: Component List */}
      <div className="w-64 border-r p-4">
        <h2 className="font-semibold mb-4">Components</h2>
        <ComponentTree onSelect={setSelectedComponent} />
      </div>

      {/* Editor */}
      <div className="flex-1 flex flex-col">
        <div className="border-b p-4 flex justify-between">
          <h1 className="text-xl font-semibold">{selectedComponent}</h1>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setCode(yaml.stringify(config))}>
              Reset
            </Button>
            <Button onClick={handleSave}>
              Save
            </Button>
          </div>
        </div>
        
        <Editor
          height="100%"
          language="yaml"
          value={code}
          onChange={(value) => setCode(value || '')}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 14
          }}
        />
      </div>
    </div>
  );
}
```

---

## 组件设计

### 1. 通用组件

#### LoadingSpinner
```tsx
export function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center p-8">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>
  );
}
```

#### CodeBlock
```tsx
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';

interface CodeBlockProps {
  language: string;
  code: string;
}

export function CodeBlock({ language, code }: CodeBlockProps) {
  return (
    <SyntaxHighlighter language={language} style={vscDarkPlus}>
      {code}
    </SyntaxHighlighter>
  );
}
```

#### JsonViewer
```tsx
import ReactJson from 'react-json-view';

interface JsonViewerProps {
  data: any;
}

export function JsonViewer({ data }: JsonViewerProps) {
  return (
    <ReactJson
      src={data}
      theme="monokai"
      collapsed={1}
      displayDataTypes={false}
    />
  );
}
```

---

## 状态管理

### 1. Zustand Store

```tsx
// src/stores/authStore.ts

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  token: string | null;
  user: User | null;
  login: (token: string, user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      login: (token, user) => set({ token, user }),
      logout: () => set({ token: null, user: null })
    }),
    {
      name: 'auth-storage'
    }
  )
);
```

### 2. TanStack Query

```tsx
// src/services/api.ts

import axios from 'axios';
import { useAuthStore } from '@/stores/authStore';

export const api = axios.create({
  baseURL: '/api'
});

// 请求拦截器：添加 Token
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：处理错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  }
);
```

---

## 路由设计

```tsx
// src/App.tsx

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from '@/components/layout/Layout';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="agents" element={<AgentList />} />
          <Route path="agents/:agentId" element={<AgentDetail />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="runs" element={<RunList />} />
          <Route path="runs/:runId" element={<RunDetail />} />
          <Route path="config" element={<ConfigEditor />} />
          <Route path="metrics" element={<MetricsDashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

---

## UI/UX 设计

### 1. 设计系统

**颜色方案**：
```css
:root {
  --primary: 222.2 47.4% 11.2%;
  --secondary: 210 40% 96.1%;
  --accent: 210 40% 96.1%;
  --destructive: 0 84.2% 60.2%;
  --success: 142 76% 36%;
  --warning: 38 92% 50%;
}
```

**Typography**：
```css
body {
  font-family: 'Inter', sans-serif;
}

h1 { @apply text-4xl font-bold; }
h2 { @apply text-3xl font-semibold; }
h3 { @apply text-2xl font-semibold; }
```

### 2. 响应式设计

```tsx
// 移动端优先
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {/* Cards */}
</div>
```

---

## 实时功能

### SSE Hook
```tsx
// src/hooks/useSSE.ts

import { useEffect, useState } from 'react';

export function useSSE<T>(url: string) {
  const [data, setData] = useState<T[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const eventSource = new EventSource(url);

    eventSource.onopen = () => setIsConnected(true);
    eventSource.onerror = () => setIsConnected(false);
    
    eventSource.addEventListener('message', (event) => {
      const newData = JSON.parse(event.data);
      setData(prev => [...prev, newData]);
    });

    return () => eventSource.close();
  }, [url]);

  return { data, isConnected };
}
```

---

## 部署配置

### Vite 配置
```ts
// vite.config.ts

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
});
```

### Docker 部署
```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

## 总结

这个 React Frontend 设计具备以下特点：

1. **✅ 现代化技术栈** - React 18 + TypeScript + Vite
2. **✅ 美观 UI** - TailwindCSS + shadcn/ui
3. **✅ 实时交互** - SSE 流式 Chat
4. **✅ 完整功能** - Dashboard、Agent、Run、Config
5. **✅ 类型安全** - TypeScript 全覆盖
6. **✅ 性能优化** - TanStack Query + 虚拟滚动

通过这个 Frontend，用户可以：
- 📊 一目了然的系统概览
- 🤖 可视化管理 Agents
- 💬 实时流式对话
- 🔍 完整的执行追踪
- ⚙️ 在线配置编辑
- 📈 详细的 Metrics 分析
