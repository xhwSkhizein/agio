# 工具执行权限设计（草案）

## 目标
- 在工具调用前统一进行权限判定，未授权时向用户请求授权。
- 授权结果可复用，支持 allow/deny pattern，避免重复确认。
- 不影响现有分层（Agent → runtime → providers → config），最小侵入。
- 保持可观测与可恢复：授权阻塞可被前端感知，授权后可继续执行。

## 术语
- ToolExecutor：负责实际调度并执行工具。
- PermissionService：策略决策器，基于配置和上下文生成需要授权/拒绝/直接通过的决定。
- ConsentStore：存储用户授权记录（allow/deny pattern + 过期时间）。
- ConsentWaiter：基于 `asyncio.Event` 的协调器，挂起等待用户授权，收到结果后唤醒继续。
- tool_call_id：工具调用唯一标识，用于事件关联与恢复执行。

## 角色与职责
- PermissionService：
  - 输入：user_id、tool_name、工具参数摘要、上下文元数据。
  - 输出：PermissionDecision（allowed/denied/requires_consent、reason、suggested_scopes/patterns、expires_at）。
  - 职责：集中策略，避免在工具内分散判断。
- ConsentStore：
  - 读写用户授权记录（allow/deny patterns、expires_at、created_at/updated_at）。
  - 支持持久化（推荐复用 SessionStore 的存储后端，或单独集合/表）。
- ConsentWaiter：
  - `wait_for_consent(tool_call_id) -> Awaitable[ConsentDecision]`：若未决，挂起等待。
  - `resolve(tool_call_id, decision)`：写入授权结果并唤醒挂起的执行。
  - 防泄漏：支持超时/取消，重复 resolve 幂等。
- ToolExecutor：
  - 调用前询问 PermissionService；未授权时发事件并挂起等待。
  - 授权后重试同一次工具调用，保证幂等。

## 授权记录格式（示例）
```json
{
  "allow": [
    "bash(npm run lint)",
    "bash(npm run test:*)",
    "file_read(~/.zshrc)"
  ],
  "deny": [
    "bash(curl:*)",
    "file_read(./.env)",
    "file_read(./.env.*)",
    "file_read(./secrets/**)"
  ],
  "expires_at": "2025-12-31T00:00:00Z"
}
```
- 匹配策略：先匹配 deny，再匹配 allow；未命中视为未授权。
- Pattern 支持：glob/前缀/正则（推荐安全子集，默认 glob）。

## 流程（含 asyncio.Event 挂起/恢复）
1. **工具调用拦截**  
   - ToolExecutor 判断该工具 `requires_consent`。  
   - 查询 ConsentStore（user_id + tool_name）命中 allow/deny 即决；未命中继续。
2. **触发授权请求**  
   - 调用 PermissionService 得到 `requires_consent` 决定，构造事件 `TOOL_AUTH_REQUIRED`：包含 `tool_call_id`, `tool_name`, 参数摘要、建议 pattern、reason。  
   - 写入 `ctx.wire` 后调用 `await ConsentWaiter.wait_for_consent(tool_call_id)` 挂起。
3. **用户授权**  
   - 前端/调用方展示授权卡片，调用后端 `/tool-consent` 提交决策：`tool_call_id`, `decision(allow|deny)`, `patterns`, `expires_at`, `user_id`。  
   - 后端 `ConsentStore` 写入 allow/deny patterns（先写存储再唤醒）。  
   - `ConsentWaiter.resolve(tool_call_id, decision)`：设置 Event，挂起的任务恢复；拒绝时也要唤醒避免泄漏。
4. **恢复执行**  
   - 恢复后再次走授权匹配，此时应命中新写入的 allow → 正常执行工具。  
   - 若决策为 deny：写拒绝事件 `TOOL_AUTH_DENIED`，向模型返回“用户拒绝”信号。
5. **结束与清理**  
   - ConsentWaiter 维护 `tool_call_id -> Event`，重复 resolve 幂等；支持超时/取消，防止悬挂。  
   - Metrics 可记录阻塞时间与决策来源（consent）。

## 接口与事件建议
- 事件 `TOOL_AUTH_REQUIRED` 字段：`tool_call_id`, `tool_name`, `args_preview`, `suggested_patterns`, `reason`, `expires_at_hint`。  
- 事件 `TOOL_AUTH_DENIED` 字段：`tool_call_id`, `tool_name`, `decision=deny`, `reason`。  
- API `/tool-consent`：  
  - 请求：`tool_call_id`, `decision`(`allow|deny`), `patterns`(list), `expires_at`(可选), `user_id`.  
  - 响应：确认写入后通知 ConsentWaiter 并触发重试。

## 配置与默认策略
- 工具层仅需配置 `requires_consent: bool`；默认开启：`bash`, `file_edit`, `file_read`, 网络敏感类。  
- Agent/Workflow 可进一步限制（如只读工具集）。  
- Pattern 提示模板可在工具配置中提供 `consent_prompt`，但不要求写死 allow/deny。

## 设计考量
- 职责单一：PermissionService 判定，ConsentStore 持久化，ConsentWaiter 同步等待，ToolExecutor 执行。  
- 幂等与安全：拒绝/超时都要唤醒等待；执行前再校验授权，避免越权。  
- 可观测：事件流经 Wire，前端可感知阻塞；Metrics 记录等待时长。  
- 安全默认：deny 优先，未命中视为未授权；限制过宽 pattern（可在后端校验，如拒绝 `bash(*)`）。
