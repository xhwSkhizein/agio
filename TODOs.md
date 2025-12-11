## processing

## issues

- [ ] Traces 目前完全不可用，没有实际实现 Trace 功能，需要重新设计&实现
- [ ] 没有 HITL(Human-in-the-loop) ， 而且工具执行没有用户授权鉴权的逻辑，Agent 执行过程中也不能主动询问用户或阻塞等待用户相应， 期望 HITL 是可以持久化的状态，即是否授权 or 用户 feedback 之前状态是暂停的，用户操作后状态恢复继续执行，不会因页面刷新或网络中断等问题重置或丢失
- [ ] config yaml 支持 Jinja2 模版，可以支持条件表达式/loop 等
- [x] 支持 deepseek thinking 模式 (https://api-docs.deepseek.com/zh-cn/guides/thinking_mode) ； 支持 reasoning_content 字段的处理

- [ ] system prompt 中强调所有 path 相关参数使用绝对路径

## 🤔 疑问

- [ ] web 端直接与 Workflow 对话，使用的那个 api
- [ ] 在配置文件配置了 tool 后，Agent 实际调用时，传递给 LLM 的 Tools 信息是如何构建的？

## archived

- [x] BUG: Glob tool 无法处理 **/\*.json 这样的模式 (已修复：使用 rglob() 方法处理 **/ 开头的模式)

```
2025-12-09T10:53:15.791819Z [error    ] Glob search failed             [agio.providers.tools.builtin.glob_tool.glob_tool] extra={'pattern': '**/*.json', 'path': '/Users/hongv/workspace/agio'}
Traceback (most recent call last):
  File "/Users/hongv/workspace/agio/agio/providers/tools/builtin/glob_tool/glob_tool.py", line 181, in _glob_search
    for file_path in search_dir.glob(glob_pattern):
  File "/Users/hongv/.local/share/uv/python/cpython-3.11.10-macos-aarch64-none/lib/python3.11/pathlib.py", line 952, in glob
    selector = _make_selector(tuple(pattern_parts), self._flavour)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/hongv/.local/share/uv/python/cpython-3.11.10-macos-aarch64-none/lib/python3.11/pathlib.py", line 289, in _make_selector
    raise ValueError("Invalid pattern: '**' can only be an entire path component")
ValueError: Invalid pattern: '**' can only be an entire path component
Traceback (most recent call last):
  File "/Users/hongv/workspace/agio/agio/providers/tools/builtin/glob_tool/glob_tool.py", line 181, in _glob_search
    for file_path in search_dir.glob(glob_pattern):
  File "/Users/hongv/.local/share/uv/python/cpython-3.11.10-macos-aarch64-none/lib/python3.11/pathlib.py", line 952, in glob
    selector = _make_selector(tuple(pattern_parts), self._flavour)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/hongv/.local/share/uv/python/cpython-3.11.10-macos-aarch64-none/lib/python3.11/pathlib.py", line 289, in _make_selector
    raise ValueError("Invalid pattern: '**' can only be an entire path component")
ValueError: Invalid pattern: '**' can only be an entire path component
```

- [x] BUG: web 页面处理问题（已修复）
      1）ParallelNestedRunnables 中的工具信息未正确展示工具参数，而且 Assistant Step 的消息堆积在了最前面，并没有像正常聊天时那样展示（content / toolcalls / tool result）
      2） 相同 key 的组件

  **修复方案**：

  - 重新设计了数据结构，使用`steps`数组来保持步骤的正确执行顺序
  - 修复了工具参数的流式 JSON 字符串累积逻辑
  - 修复了 React key 冲突问题，每个步骤都有唯一的 key
  - 按照实际执行顺序展示：assistant content -> tool calls -> tool results

- [x] 已经 cancel 的请求，LLMLog 中还一直是 running，需要更新状态, 并优化相关 web 状态展示; LLM Logs web 展示时并未显示历史 Assistant Step 中的 toolcall 详细信息，只单独展示了最新的 Assistant Step 的 toolcall 信息
- [x] agent 执行达到限制后(Timeout/max steps/limit toolcall), 需要可以针对当前已做工作进行总结和汇总并生成一个最终相应，而不是直接停止。（生成总结汇总这个逻辑要可以通过配置系统进行配置，这应该是一个公共功能）
- [x] 当 Agent 并行调用工具时，Chat 页面展示信息时会出现混乱，参考 Workflow 的 Parallel 方式进行优化，使用多个并行的流来展示并行的工具调用和后续结果（请创建单独的组件进行实现）
  - [x] 展示在聊天界面的消息在流式实时拼接时有重复的问题，最终会被 snapshot 替换为正常文本，展示在 ParallelNestedRunnables 中的也有同样的问题，而且 ParallelNestedRunnables 中最后一个文本消息还会在外层进行渲染，同样是大量重复文本但不会变回正常
