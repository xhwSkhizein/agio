# Session & Chat 功能重构方案

## 一、当前架构分析

### 1.1 核心概念定义

| 概念 | 定义 | 存储位置 |
|------|------|----------|
| **Session** | 一个完整的会话容器，包含多轮用户交互 | `session_id` 作为 Steps 的分组键 |
| **Run** | 一次用户查询 → Agent 响应的完整周期 | `AgentRun` 表，通过 `session_id` 关联 |
| **Step** | 单条消息（user/assistant/tool），直接映射 LLM 消息格式 | `Step` 表，按 `sequence` 排序 |

**关系图：**
```
Session (session_id)
├── Run 1 (run_id_1)
│   ├── Step 1: user message (seq=1)
│   ├── Step 2: assistant message (seq=2)
│   └── Step 3: tool result (seq=3)
├── Run 2 (run_id_2)
│   ├── Step 4: user message (seq=4)
│   └── Step 5: assistant message (seq=5)
└── Run N...
```

### 1.2 现有代码结构

#### 后端核心组件

| 文件 | 职责 |
|------|------|
| `agio/agent.py` | Agent 入口，提供 `arun_stream`, `retry_from_sequence`, `fork_session` |
| `agio/runtime/runner.py` | `StepRunner` 执行器，管理 Run 生命周期 |
| `agio/runtime/context.py` | `build_context_from_steps` 从 Steps 构建 LLM 上下文 |
| `agio/runtime/control.py` | `retry_from_sequence`, `fork_session` 实现 |
| `agio/api/routes/chat.py` | Chat API，处理 SSE 流式响应 |
| `agio/api/routes/sessions.py` | Sessions API，查询/删除会话 |

#### 前端核心组件

| 文件 | 职责 |
|------|------|
| `Chat.tsx` | 聊天页面，SSE 流式交互 |
| `Sessions.tsx` | 会话列表页，只读查看历史 |
| `api.ts` | API 服务封装 |

---

## 二、问题详细分析

### 2.1 Session 与 Run 概念混淆

**问题：** 当前 `Sessions.tsx` 页面实际展示的是 `Run` 列表，而非真正的 Session 聚合视图。

**代码证据：**
```typescript
// Sessions.tsx:11-14
const { data: sessions, isLoading } = useQuery({
  queryKey: ['sessions'],
  queryFn: () => sessionService.listSessions({ limit: 50 }),
})
```

后端 API 返回的是 `list_runs` 的结果：
```python
# sessions.py:51-59
@router.get("")
async def list_sessions(...):
    runs = await repository.list_runs(user_id=user_id, limit=limit, offset=offset)
    # 返回的是 Run 列表，不是 Session 聚合
```

**影响：**
- 用户看到的是一个个独立的 Run，而非会话历史
- 无法直观看到同一个 Session 下的多轮对话

### 2.2 Chat 页面无法持续会话

**问题：** Chat 页面每次发送消息都不传 `session_id`，导致每次都创建新 Session。

**代码证据：**
```typescript
// Chat.tsx:102-112
const response = await fetch(`/agio/chat/${agentId}`, {
  method: 'POST',
  headers: {...},
  body: JSON.stringify({
    message: userMessage,
    stream: true,
    // 注意：没有传递 session_id
  }),
})
```

后端处理：
```python
# agent.py:54
current_session_id = session_id or str(uuid.uuid4())  # 每次都生成新 ID
```

**影响：**
- 刷新页面后聊天历史丢失
- 多轮对话无法携带上下文
- 即使同一个页面会话，每次请求也是独立的

### 2.3 Sessions 页面只读，无法继续聊天

**问题：** Sessions 页面只能查看历史，无法从历史会话继续聊天。

**代码证据：**
```typescript
// Sessions.tsx 只有查看和删除功能
// 没有 "Continue Chat" 或跳转到 Chat 页面的入口
```

**影响：**
- 用户无法从历史对话继续
- 浪费已有的对话上下文

### 2.4 Fork/Retry 功能未暴露

**问题：** 后端已实现 `fork_session` 和 `retry_from_sequence`，但没有对应的 HTTP API。

**代码证据：**
```python
# agent.py:75-103 - 方法存在但未暴露
async def retry_from_sequence(self, session_id: str, sequence: int): ...
async def fork_session(self, session_id: str, sequence: int): ...
```

```python
# sessions.py - 没有 fork/retry 端点
# 只有 list, get, delete, steps 端点
```

**影响：**
- 用户无法从特定 step 重试
- 用户无法 fork 会话创建分支

### 2.5 前端状态仅在内存

**问题：** Chat 页面的 `events` 状态仅存在于 React 组件内存。

**代码证据：**
```typescript
// Chat.tsx:43
const [events, setEvents] = useState<TimelineEvent[]>([])  // 刷新即丢失
```

**影响：**
- 页面刷新后聊天内容全部丢失
- 无法恢复到之前的对话状态

---

## 三、Run 与 Session 的概念澄清

### 3.1 语义区别

| 维度 | Session | Run |
|------|---------|-----|
| **粒度** | 粗（会话级） | 细（单次请求级） |
| **生命周期** | 长期存在，可跨多次交互 | 单次请求开始到结束 |
| **用户感知** | 一个"对话窗口" | 一次"发送-响应" |
| **数据存储** | 作为 Steps 的分组键 | 独立记录，包含元数据和指标 |

### 3.2 设计意图

**Session：**
- 是对话上下文的容器
- 所有历史 Steps 通过 `session_id` 关联
- 用于构建 LLM 的 `messages` 上下文

**Run：**
- 是单次执行的记录
- 便于追踪性能指标、状态、错误
- 便于实现 retry（重试某个 Run）

**结论：** 两者不冲突，是不同层次的抽象。Session 是用户视角，Run 是系统视角。

---

## 四、后端 API 重构方案

### 4.1 Sessions API 重构

#### 现有端点
```
GET    /sessions                  # 列出 Runs（命名不准确）
GET    /sessions/{session_id}     # 获取 Session 详情
DELETE /sessions/{session_id}     # 删除 Session
GET    /sessions/{session_id}/runs   # 获取 Session 的 Runs
GET    /sessions/{session_id}/steps  # 获取 Session 的 Steps
```

#### 新增端点
```
POST   /sessions/{session_id}/fork    # Fork 会话到新 Session
POST   /sessions/{session_id}/retry   # 从指定 step 重试
```

#### 具体实现

**4.1.1 Fork Session API**

```python
# agio/api/routes/sessions.py

class ForkRequest(BaseModel):
    sequence: int  # Fork 起点的 sequence（包含）

class ForkResponse(BaseModel):
    new_session_id: str
    copied_steps: int

@router.post("/{session_id}/fork")
async def fork_session(
    session_id: str,
    request: ForkRequest,
    repository: AgentRunRepository = Depends(get_repository),
) -> ForkResponse:
    """
    Fork a session at a specific sequence.
    
    Creates a new session with a copy of all steps up to and including
    the specified sequence. The new session can be used for branching
    conversations.
    """
    from agio.runtime import fork_session as do_fork
    
    new_session_id = await do_fork(session_id, request.sequence, repository)
    
    # Get the count of copied steps
    steps = await repository.get_steps(new_session_id)
    
    return ForkResponse(
        new_session_id=new_session_id,
        copied_steps=len(steps),
    )
```

**4.1.2 Retry API**

```python
# agio/api/routes/sessions.py

class RetryRequest(BaseModel):
    sequence: int  # 从此 sequence 开始重试
    agent_name: str  # 使用的 Agent 名称

@router.post("/{session_id}/retry")
async def retry_session(
    session_id: str,
    request: RetryRequest,
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> EventSourceResponse:
    """
    Retry from a specific sequence.
    
    Deletes all steps with sequence >= N and resumes execution.
    Returns SSE stream of events.
    """
    agent = config_sys.get(request.agent_name)
    
    async def event_generator():
        async for event in agent.retry_from_sequence(session_id, request.sequence):
            event_dict = event.model_dump(mode="json", exclude_none=True)
            event_type = event_dict.pop("type", "message")
            yield {"event": event_type, "data": json.dumps(event_dict)}
    
    return EventSourceResponse(event_generator(), sep="\n")
```

### 4.2 Chat API 改进

#### 现有问题
- `session_id` 是可选的，不传就每次新建
- 无法从已有 session 继续聊天

#### 改进方案

保持兼容性，但增强 `session_id` 的语义：

```python
# agio/api/routes/chat.py

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None  # 传入则继续该 session，否则新建
    user_id: str | None = None
    stream: bool = True

@router.post("/{agent_name}")
async def chat(...):
    # 现有逻辑已正确处理 session_id
    # 只需确保前端正确传递即可
    pass
```

**关键：** 后端逻辑已正确（`runner.py:132-134` 会从 repository 加载历史 steps）。
问题在于前端没有传递 `session_id`。

### 4.3 新增 Session 聚合视图 API

当前 `list_sessions` 返回的是 Runs，需要新增真正的 Session 聚合视图：

```python
# agio/api/routes/sessions.py

class SessionSummary(BaseModel):
    session_id: str
    agent_id: str
    user_id: str | None
    run_count: int
    step_count: int
    last_message: str | None  # 最后一条用户消息
    last_activity: str  # 最后活动时间
    status: str  # 最后一个 run 的状态

@router.get("/summary")
async def list_session_summaries(
    user_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    repository: AgentRunRepository = Depends(get_repository),
) -> list[SessionSummary]:
    """
    List sessions with aggregated summary.
    
    Groups runs by session_id and returns summary for each session.
    """
    runs = await repository.list_runs(user_id=user_id, limit=200, offset=0)
    
    # Group by session_id
    sessions: dict[str, list[AgentRun]] = {}
    for run in runs:
        if run.session_id not in sessions:
            sessions[run.session_id] = []
        sessions[run.session_id].append(run)
    
    summaries = []
    for session_id, session_runs in sessions.items():
        session_runs.sort(key=lambda r: r.created_at, reverse=True)
        latest = session_runs[0]
        step_count = await repository.get_step_count(session_id)
        
        summaries.append(SessionSummary(
            session_id=session_id,
            agent_id=latest.agent_id,
            user_id=latest.user_id,
            run_count=len(session_runs),
            step_count=step_count,
            last_message=latest.input_query,
            last_activity=latest.created_at.isoformat(),
            status=latest.status.value,
        ))
    
    # Sort by last activity and paginate
    summaries.sort(key=lambda s: s.last_activity, reverse=True)
    return summaries[offset:offset + limit]
```

### 4.4 StepRunner 增强

需要为 `StepRunner` 添加 resume 方法来支持 retry：

```python
# agio/runtime/runner.py

class StepRunner:
    # ... 现有代码 ...
    
    async def resume_from_user_step(
        self, session_id: str, last_step: Step
    ) -> AsyncIterator[StepEvent]:
        """Resume from a user step - regenerate response."""
        session = AgentSession(session_id=session_id)
        
        # Build context from all existing steps
        messages = await build_context_from_steps(
            session_id, self.repository, system_prompt=self.agent.system_prompt
        )
        
        # Execute from the last user message
        async for event in self._execute_with_context(session, messages, last_step):
            yield event
    
    async def resume_from_tool_step(
        self, session_id: str, last_step: Step
    ) -> AsyncIterator[StepEvent]:
        """Resume after a tool result - continue execution."""
        session = AgentSession(session_id=session_id)
        messages = await build_context_from_steps(
            session_id, self.repository, system_prompt=self.agent.system_prompt
        )
        
        async for event in self._execute_with_context(session, messages, last_step):
            yield event
    
    async def resume_from_assistant_with_tools(
        self, session_id: str, last_step: Step
    ) -> AsyncIterator[StepEvent]:
        """Resume from assistant step with pending tool calls."""
        session = AgentSession(session_id=session_id)
        messages = await build_context_from_steps(
            session_id, self.repository, system_prompt=self.agent.system_prompt
        )
        
        # Re-execute pending tool calls
        async for event in self._execute_tool_calls(session, messages, last_step):
            yield event
```

---

## 五、前端重构方案

### 5.1 路由结构重构

#### 现有路由
```typescript
/chat              -> ChatSelect (选择 Agent)
/chat/:agentId     -> Chat (与 Agent 聊天)
/sessions          -> Sessions (查看历史)
```

#### 新路由结构
```typescript
/chat                           -> ChatSelect (选择 Agent)
/chat/:agentId                  -> Chat (新会话)
/chat/:agentId/:sessionId       -> Chat (继续已有会话)
/sessions                       -> Sessions (会话列表)
/sessions/:sessionId            -> SessionDetail (会话详情，可继续/fork/retry)
```

#### App.tsx 修改

```tsx
// App.tsx
<Routes>
  <Route path="/" element={<Dashboard />} />
  <Route path="/chat" element={<ChatSelect />} />
  <Route path="/chat/:agentId" element={<Chat />} />
  <Route path="/chat/:agentId/:sessionId" element={<Chat />} />  {/* 新增 */}
  <Route path="/sessions" element={<Sessions />} />
  <Route path="/sessions/:sessionId" element={<SessionDetail />} />  {/* 新增 */}
  {/* ... 其他路由 */}
</Routes>
```

### 5.2 Chat.tsx 重构

#### 核心变更

1. **支持 sessionId 路由参数**
2. **加载历史对话**
3. **维护 session 状态**
4. **在请求中传递 session_id**

```tsx
// Chat.tsx 重构版本

import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { agentService, sessionService } from '../services/api'

export default function Chat() {
  const { agentId, sessionId: urlSessionId } = useParams<{ 
    agentId: string
    sessionId?: string 
  }>()
  const navigate = useNavigate()
  
  // Session state - 关键改动
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(
    urlSessionId || null
  )
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [isLoading, setIsLoading] = useState(false)
  
  // Load agent info
  const { data: agent } = useQuery({
    queryKey: ['agent', agentId],
    queryFn: () => agentService.getAgent(agentId!),
    enabled: !!agentId,
  })
  
  // Load existing session steps if sessionId is provided
  const { data: existingSteps, isLoading: stepsLoading } = useQuery({
    queryKey: ['session-steps', urlSessionId],
    queryFn: () => sessionService.getSessionSteps(urlSessionId!),
    enabled: !!urlSessionId,
  })
  
  // Convert steps to events on load
  useEffect(() => {
    if (existingSteps && existingSteps.length > 0) {
      const loadedEvents = stepsToEvents(existingSteps)
      setEvents(loadedEvents)
      setCurrentSessionId(urlSessionId!)
    }
  }, [existingSteps, urlSessionId])
  
  // Handle send with session_id
  const handleSend = async () => {
    if (!input.trim() || !agentId) return
    
    // ... existing event setup ...
    
    try {
      const response = await fetch(`/agio/chat/${agentId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          message: userMessage,
          stream: true,
          session_id: currentSessionId,  // 关键：传递 session_id
        }),
      })
      
      // ... existing SSE handling ...
      
      // Capture new session_id from run_started event
      // 在 run_started 事件中更新 currentSessionId
      
    } catch (error) {
      // ... error handling ...
    }
  }
  
  // ... rest of the component
}

// Helper: Convert backend steps to frontend events
function stepsToEvents(steps: StepResponse[]): TimelineEvent[] {
  return steps.map(step => {
    if (step.role === 'tool') {
      return {
        id: step.id,
        type: 'tool' as const,
        toolName: step.name || 'Unknown',
        toolArgs: '{}',  // Parse from step if available
        toolResult: step.content,
        toolStatus: 'completed' as const,
        timestamp: new Date(step.created_at).getTime(),
      }
    }
    
    return {
      id: step.id,
      type: step.role as 'user' | 'assistant',
      content: step.content || '',
      timestamp: new Date(step.created_at).getTime(),
    }
  })
}
```

#### SSE 事件处理更新

在 `run_started` 事件中捕获并保存 session_id：

```tsx
case 'run_started': {
  const runId = data.run_id
  setCurrentRunId(runId)
  
  // 从 SSE 中获取 session_id（需要后端在事件中返回）
  if (data.session_id && !currentSessionId) {
    setCurrentSessionId(data.session_id)
    // 可选：更新 URL 以便刷新后恢复
    navigate(`/chat/${agentId}/${data.session_id}`, { replace: true })
  }
  break
}
```

### 5.3 Sessions.tsx 重构

#### 核心变更

1. **展示真正的 Session 聚合视图**
2. **添加"继续聊天"按钮**
3. **添加 Fork/Retry 功能入口**

```tsx
// Sessions.tsx 重构版本

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { sessionService } from '../services/api'
import { 
  History, Trash2, MessageSquare, GitBranch, RotateCcw,
  ChevronRight, Loader2 
} from 'lucide-react'

export default function Sessions() {
  const navigate = useNavigate()
  const [selectedSession, setSelectedSession] = useState<string | null>(null)
  
  // 使用新的 session summary API
  const { data: sessions, isLoading } = useQuery({
    queryKey: ['session-summaries'],
    queryFn: () => sessionService.listSessionSummaries({ limit: 50 }),
  })
  
  // Load steps for selected session
  const { data: sessionSteps } = useQuery({
    queryKey: ['session-steps', selectedSession],
    queryFn: () => sessionService.getSessionSteps(selectedSession!),
    enabled: !!selectedSession,
  })
  
  // Continue chat handler
  const handleContinueChat = (sessionId: string, agentId: string) => {
    navigate(`/chat/${agentId}/${sessionId}`)
  }
  
  // Fork handler
  const handleFork = async (sessionId: string, sequence: int) => {
    const result = await sessionService.forkSession(sessionId, { sequence })
    // Navigate to new forked session
    navigate(`/chat/${agentId}/${result.new_session_id}`)
  }
  
  return (
    <div className="max-w-6xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white mb-2">Sessions</h1>
        <p className="text-gray-400">
          View and continue agent conversations.
        </p>
      </div>
      
      {/* Session List with enhanced actions */}
      <div className="flex gap-6">
        {/* Left: Session List */}
        <div className="w-96 flex-shrink-0 space-y-2">
          {sessions?.map((session) => (
            <div
              key={session.session_id}
              className={`bg-surface border rounded-lg p-4 cursor-pointer transition-all ${
                selectedSession === session.session_id
                  ? 'border-primary-500'
                  : 'border-border hover:border-primary-500/50'
              }`}
              onClick={() => setSelectedSession(session.session_id)}
            >
              {/* Session info */}
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-400">{session.agent_id}</span>
                <span className="text-xs text-gray-500">
                  {session.run_count} runs · {session.step_count} steps
                </span>
              </div>
              <p className="text-sm text-white truncate mb-2">
                {session.last_message}
              </p>
              
              {/* Action buttons */}
              <div className="flex gap-2 mt-3">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleContinueChat(session.session_id, session.agent_id)
                  }}
                  className="flex items-center gap-1 px-2 py-1 text-xs bg-primary-500/20 text-primary-400 rounded hover:bg-primary-500/30"
                >
                  <MessageSquare className="w-3 h-3" />
                  Continue
                </button>
              </div>
            </div>
          ))}
        </div>
        
        {/* Right: Session Detail with Steps */}
        <div className="flex-1">
          {selectedSession && sessionSteps && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-4">
                Conversation Steps
              </h3>
              
              {sessionSteps.map((step, index) => (
                <div
                  key={step.id}
                  className="group bg-surface border border-border rounded-lg p-4 mb-2 relative"
                >
                  {/* Step content */}
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs text-gray-500">#{step.sequence}</span>
                    <RoleBadge role={step.role} />
                  </div>
                  <p className="text-sm text-gray-300 whitespace-pre-wrap">
                    {step.content}
                  </p>
                  
                  {/* Hover actions for fork/retry */}
                  <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                    <button
                      onClick={() => handleFork(selectedSession, step.sequence)}
                      className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded"
                      title="Fork from here"
                    >
                      <GitBranch className="w-3.5 h-3.5" />
                    </button>
                    {step.role === 'user' && (
                      <button
                        onClick={() => handleRetry(selectedSession, step.sequence)}
                        className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded"
                        title="Retry from here"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
```

### 5.4 API 服务更新

```typescript
// services/api.ts 新增

// Session Summary 类型
export interface SessionSummary {
  session_id: string
  agent_id: string
  user_id: string | null
  run_count: number
  step_count: number
  last_message: string | null
  last_activity: string
  status: string
}

// Fork 相关类型
export interface ForkRequest {
  sequence: number
}

export interface ForkResponse {
  new_session_id: string
  copied_steps: number
}

export const sessionService = {
  // ... existing methods ...
  
  // 新增：获取 Session 聚合列表
  async listSessionSummaries(params?: {
    user_id?: string
    limit?: number
    offset?: number
  }): Promise<SessionSummary[]> {
    const response = await api.get('/sessions/summary', { params })
    return response.data
  },
  
  // 新增：Fork Session
  async forkSession(
    sessionId: string, 
    request: ForkRequest
  ): Promise<ForkResponse> {
    const response = await api.post(`/sessions/${sessionId}/fork`, request)
    return response.data
  },
  
  // 新增：Retry（返回 SSE URL，由调用方处理流）
  getRetryStreamUrl(sessionId: string, sequence: number, agentName: string): string {
    return `/agio/sessions/${sessionId}/retry?sequence=${sequence}&agent_name=${agentName}`
  },
}
```

### 5.5 后端事件增强

为了让前端在新会话时获取 `session_id`，需要在 `run_started` 事件中包含：

```python
# agio/domain/events.py

def create_run_started_event(
    run_id: str, 
    query: str,
    session_id: str | None = None,  # 新增
) -> StepEvent:
    return StepEvent(
        type=StepEventType.RUN_STARTED,
        run_id=run_id,
        data={
            "query": query,
            "session_id": session_id,  # 新增
        },
    )
```

```python
# agio/runtime/runner.py - run_stream 方法

yield create_run_started_event(
    run_id=run.id, 
    query=query,
    session_id=session.session_id,  # 新增
)
```

---

## 六、实施计划

### 6.1 阶段划分

| 阶段 | 目标 | 预估工作量 | 优先级 |
|------|------|-----------|--------|
| **Phase 1** | Session 持续对话 | 1-2 天 | P0 |
| **Phase 2** | Session 聚合视图 & Continue | 1 天 | P1 |
| **Phase 3** | Fork & Retry 功能 | 2 天 | P2 |
| **Phase 4** | 用户体验优化 | 1 天 | P3 |

### 6.2 Phase 1: Session 持续对话（P0 核心）

**目标：** 解决"刷新丢失对话"和"多轮对话无上下文"问题

#### 后端改动

1. **修改 `create_run_started_event` 包含 `session_id`**
   - 文件：`agio/domain/events.py`
   - 改动量：~5 行

2. **修改 `runner.py` 传递 `session_id` 到事件**
   - 文件：`agio/runtime/runner.py`
   - 改动量：~3 行

#### 前端改动

1. **Chat.tsx 支持 `sessionId` 路由参数**
   - 新增路由：`/chat/:agentId/:sessionId`
   - 改动量：~20 行

2. **Chat.tsx 加载历史 Steps**
   - 使用 `useQuery` 加载 steps
   - 转换为 `TimelineEvent[]`
   - 改动量：~40 行

3. **Chat.tsx 请求中传递 `session_id`**
   - 修改 `handleSend` 函数
   - 改动量：~5 行

4. **Chat.tsx 从 `run_started` 事件捕获并保存 `session_id`**
   - 更新 URL（可选）
   - 改动量：~15 行

5. **App.tsx 新增路由**
   - 改动量：~1 行

### 6.3 Phase 2: Session 聚合视图 & Continue（P1）

**目标：** 提供真正的 Session 列表视图，支持"继续聊天"

#### 后端改动

1. **新增 `GET /sessions/summary` API**
   - 文件：`agio/api/routes/sessions.py`
   - 改动量：~50 行

#### 前端改动

1. **Sessions.tsx 使用新 API**
   - 改动量：~10 行

2. **Sessions.tsx 添加 "Continue" 按钮**
   - 跳转到 `/chat/:agentId/:sessionId`
   - 改动量：~15 行

3. **api.ts 新增类型和方法**
   - 改动量：~20 行

### 6.4 Phase 3: Fork & Retry（P2）

**目标：** 支持从历史对话分支和重试

#### 后端改动

1. **新增 `POST /sessions/{session_id}/fork` API**
   - 文件：`agio/api/routes/sessions.py`
   - 改动量：~25 行

2. **新增 `POST /sessions/{session_id}/retry` API**
   - 文件：`agio/api/routes/sessions.py`
   - 改动量：~30 行

3. **StepRunner 添加 resume 方法**
   - 文件：`agio/runtime/runner.py`
   - 改动量：~60 行

#### 前端改动

1. **Sessions.tsx 添加 Fork/Retry 按钮**
   - 改动量：~30 行

2. **api.ts 新增 fork/retry 方法**
   - 改动量：~15 行

3. **处理 Retry SSE 流（可复用 Chat 逻辑）**
   - 改动量：~20 行

### 6.5 Phase 4: 用户体验优化（P3）

1. **Session 标题自动生成**（基于首条消息）
2. **Session 标签/分组**
3. **快捷键支持**
4. **Loading 状态优化**
5. **错误处理增强**

---

## 七、文件改动清单

### 后端文件

| 文件 | 改动类型 | Phase |
|------|---------|-------|
| `agio/domain/events.py` | 修改 | 1 |
| `agio/runtime/runner.py` | 修改 | 1, 3 |
| `agio/api/routes/sessions.py` | 新增端点 | 2, 3 |

### 前端文件

| 文件 | 改动类型 | Phase |
|------|---------|-------|
| `src/App.tsx` | 路由修改 | 1 |
| `src/pages/Chat.tsx` | 重构 | 1 |
| `src/pages/Sessions.tsx` | 重构 | 2, 3 |
| `src/services/api.ts` | 新增方法 | 2, 3 |

---

## 八、验收标准

### Phase 1 验收

- [ ] 发送消息后，刷新页面可以看到历史对话
- [ ] 多次发送消息，每次都能携带之前的上下文
- [ ] URL 中包含 `sessionId`，可以分享链接

### Phase 2 验收

- [ ] Sessions 页面展示按 Session 聚合的视图
- [ ] 每个 Session 显示 run 数量、step 数量、最后活动时间
- [ ] 点击 "Continue" 可以跳转到 Chat 页面继续对话

### Phase 3 验收

- [ ] 在 Session 详情中，可以对任意 step 点击 "Fork"
- [ ] Fork 后跳转到新 session 的 Chat 页面
- [ ] 对 user step 可以点击 "Retry" 重新生成回复

---

## 九、总结

### 核心问题根因

| 问题 | 根因 | 解决方案 |
|------|------|---------|
| 刷新丢失对话 | 前端未传 session_id，后端每次新建 | 前端传递并持久化 session_id |
| 多轮无上下文 | 同上 | 同上 |
| Session/Run 混淆 | API 命名不准确 | 新增 session summary API |
| 无法继续聊天 | 缺少入口和路由 | 新增路由和跳转逻辑 |
| Fork/Retry 未暴露 | 缺少 HTTP API | 新增 API 端点 |

### 设计亮点

1. **最小改动原则**：后端 Chat 逻辑基本不变，只需前端正确传参
2. **渐进式实施**：分 4 个 Phase，每个 Phase 独立可交付
3. **向后兼容**：不改变现有 API 语义，只新增功能
4. **复用已有代码**：`fork_session` 和 `retry_from_sequence` 已实现，只需暴露 API

