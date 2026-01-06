## processing


## issues

- [ ] 去掉 Runnable & RunnableExecutor， 简化 Agent 执行流程
- [ ] 优化 TraceCollector, 降低使用时的代码复杂度（使用者无感知，提供配置接口即可）
- [ ] 支持 AgentLoop 的 Hooks 逻辑
- [ ] 优化 ToolExec 的 PermissionCheck，参考 Codex& Kode 等实现
- [ ] 优化内部工具实现， 参考 Codex& Kode 等强化 Bash 实现

- [ ] 常见问题：
    - [ ] toolcall 的参数过于巨大导致的失败
        - 事前：可以在 System Prompt 和 Tool‘s Prompt 中增加强调说明
        - 事后：可以通过注入 System notice 来提醒 Agent
    - [ ] 


## 🤔 疑问


## archived
