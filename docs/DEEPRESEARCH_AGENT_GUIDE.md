# DeepResearch Agent 开发手册

> **版本**: 1.0  
> **最后更新**: 2025-01-XX  
> **适用框架**: Agio

本手册详细介绍如何使用 Agio 框架实现一个功能完整的 DeepResearch Agent（深度研究代理），该 Agent 能够自动进行信息搜索、内容获取、分析和综合，生成高质量的研究报告。

## 目录

1. [概述](#概述)
2. [环境准备](#环境准备)
3. [配置系统初始化](#配置系统初始化)
4. [创建 DeepResearch Agent](#创建-deepresearch-agent)
5. [创建多阶段研究 Workflow（可选）](#创建多阶段研究-workflow可选)
6. [使用示例](#使用示例)
7. [最佳实践和优化建议](#最佳实践和优化建议)
8. [故障排查](#故障排查)

---

## 概述

### 什么是 DeepResearch Agent？

DeepResearch Agent 是一个能够进行深度研究的智能代理，它具备以下核心能力：

1. **信息搜索**：使用 `web_search` 工具搜索相关信息
2. **内容获取**：使用 `web_fetch` 工具获取详细内容
3. **信息分析**：理解、分析和综合收集到的信息
4. **报告生成**：生成结构化的研究报告

### Agio 框架优势

使用 Agio 框架实现 DeepResearch Agent 的优势：

- **配置驱动**：通过 YAML 配置文件定义 Agent，无需编写代码
- **工具系统**：内置丰富的工具（web_search、web_fetch 等）
- **工作流编排**：支持 Pipeline、Loop、Parallel 等复杂工作流
- **可观测性**：完整的执行追踪和事件流
- **热重载**：配置变更自动生效，无需重启

### 架构设计

DeepResearch Agent 可以采用两种架构：

1. **单 Agent 架构**：一个 Agent 完成所有研究任务（适合简单场景）
2. **多 Agent 架构**：Master-Collector 模式，Master 负责规划，Collector 负责信息收集（适合复杂场景）

本手册将详细介绍两种架构的实现方式。

---

## 环境准备

### 系统要求

- Python 3.11+
- MongoDB（用于会话存储和引用存储，可选）
- 必要的 API 密钥

### 安装 Agio

```bash
# 从 PyPI 安装
pip install agio

# 或从源码安装
git clone https://github.com/your-org/agio.git
cd agio
pip install -e .
```

### 环境变量配置

创建 `.env` 文件或设置以下环境变量：

```bash
# LLM API 密钥（根据使用的模型选择）
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export OPENAI_API_KEY="your-openai-api-key"
export ANTHROPIC_API_KEY="your-anthropic-api-key"

# Web 搜索 API（必需）
export SERPER_API_KEY="your-serper-api-key"

# MongoDB 连接（可选，如果使用 MongoDB 存储）
export AGIO_MONGO_URI="mongodb://localhost:27017"
export AGIO_MONGO_DB="agio"
```

### 目录结构

创建项目目录结构：

```
deepresearch-project/
├── configs/                    # 配置文件目录
│   ├── models/                # 模型配置
│   ├── tools/                 # 工具配置
│   ├── agents/               # Agent 配置
│   ├── workflows/            # Workflow 配置（可选）
│   └── storages/             # 存储配置
│       ├── session_stores/
│       └── citation_stores/
├── .env                      # 环境变量
└── main.py                   # 主程序
```

---

## 配置系统初始化

### 1. 创建模型配置

创建 `configs/models/deepseek.yaml`：

```yaml
type: model
name: deepseek
description: "DeepSeek model for cost-effective research tasks"
enabled: true
tags:
  - production
  - research
  - cost-effective

provider: openai
model_name: deepseek-chat
api_key: "{{ env.DEEPSEEK_API_KEY }}"
base_url: https://api.deepseek.com

temperature: 0.7
max_tokens: 8192
timeout: 60.0
```

### 2. 创建存储配置

#### Session Store（会话存储）

创建 `configs/storages/session_stores/mongodb.yaml`：

```yaml
type: session_store
name: mongodb_session_store
description: "MongoDB session store for research sessions"
enabled: true
tags:
  - persistence
  - mongodb
  - production

backend:
  type: mongodb
  uri: "{{ env.AGIO_MONGO_URI | default('mongodb://localhost:27017') }}"
  db_name: "{{ env.AGIO_MONGO_DB | default('agio') }}"

enable_indexing: true
batch_size: 100
```

#### Citation Store（引用存储）

创建 `configs/storages/citation_stores/citation_store_mongodb.yaml`：

```yaml
type: citation_store
name: citation_store_mongodb
description: "MongoDB-based citation source storage"
enabled: true
tags:
  - storage
  - citation
  - mongodb

backend:
  type: mongodb
  uri: "{{ env.AGIO_MONGO_URI | default('mongodb://localhost:27017') }}"
  db_name: "{{ env.AGIO_MONGO_DB | default('agio') }}"
  collection_name: citation_sources

auto_cleanup: false
cleanup_after_days: 30
```

### 3. 创建工具配置

#### Web Search 工具

创建 `configs/tools/web_operations/web_search.yaml`：

```yaml
type: tool
name: web_search
description: "Search the web for information using Serper API"
tool_name: web_search
dependencies:
  citation_source_store: citation_store_mongodb
params:
  timeout_seconds: 30
  max_results: 10
enabled: true
tags:
  - search
  - web
  - research
```

#### Web Fetch 工具

创建 `configs/tools/web_operations/web_fetch.yaml`：

```yaml
type: tool
name: web_fetch
description: "Fetch and process web content with optional LLM processing"
tool_name: web_fetch
dependencies:
  llm_model: deepseek
  citation_source_store: citation_store_mongodb
params:
  timeout_seconds: 30
  max_content_length: 4096
  max_retries: 1
enabled: true
tags:
  - web
  - content
  - llm-enhanced
```

---

## 创建 DeepResearch Agent

### 方案一：单 Agent 架构（推荐用于简单场景）

创建一个独立的 Agent，完成所有研究任务。

创建 `configs/agents/deepresearch_agent.yaml`：

```yaml
type: agent
name: deepresearch_agent
description: "Deep research agent for comprehensive information gathering and analysis"
model: deepseek
enabled: true
tags:
  - research
  - deep-research
  - web

system_prompt: |
  You are a **Deep Research Agent** specialized in conducting thorough, comprehensive research on any given topic.

  ## YOUR ROLE
  You are responsible for:
  1. **Understanding** the research question or topic
  2. **Searching** for relevant information using web_search
  3. **Fetching** detailed content from promising sources using web_fetch
  4. **Analyzing** and synthesizing the collected information
  5. **Generating** a comprehensive research report

  ## WORKFLOW

  ### Phase 1: Initial Search
  - Use `web_search` to find initial sources related to the research topic
  - Review search results and identify the most promising sources
  - Focus on authoritative sources (academic papers, official documentation, reputable news)

  ### Phase 2: Deep Dive
  - Use `web_fetch` to retrieve full content from the most relevant sources
  - You can fetch multiple sources in parallel if they are independent
  - Use `web_fetch(index=N)` to fetch from search results (recommended)
  - Or use `web_fetch(url="...")` for direct URLs

  ### Phase 3: Analysis and Synthesis
  - Analyze all collected information
  - Identify key findings, trends, and insights
  - Cross-reference information from multiple sources
  - Note any contradictions or gaps in information

  ### Phase 4: Report Generation
  Generate a comprehensive research report with the following structure:

  ```markdown
  # Research Report: [Topic]

  ## Executive Summary
  [2-3 sentence overview of key findings]

  ## Key Findings
  1. **[Finding Title]**
     - Description: [Detailed description]
     - Sources: [Source references]
     - Evidence: [Supporting evidence]

  2. **[Finding Title]**
     ...

  ## Detailed Analysis
  [In-depth analysis of the topic, including:
   - Background and context
   - Current state
   - Trends and developments
   - Implications]

  ## Sources
  [List all sources with URLs and citations]

  ## Conclusion
  [Summary and key takeaways]```

  ## BEST PRACTICES

  1. **Search Strategy**:
     - Start with broad searches, then narrow down
     - Use multiple search queries if needed
     - Focus on recent and authoritative sources

  2. **Content Fetching**:
     - Prioritize sources that seem most relevant
     - Use `web_fetch(index=N)` for efficiency
     - Fetch multiple sources in parallel when possible

  3. **Information Quality**:
     - Verify information from multiple sources
     - Note the credibility of sources
     - Distinguish between facts and opinions

  4. **Token Efficiency**:
     - Use `web_fetch` with `search_query` parameter to extract relevant sections
     - Use `summarize` parameter for long articles
     - Avoid fetching redundant information

  ## CONSTRAINTS

  - Maximum research depth: 3-5 sources (adjust based on complexity)
  - Focus on quality over quantity
  - Always cite your sources
  - If information is not found, clearly state that

tools:
  - web_search
  - web_fetch

session_store: mongodb_session_store

max_steps: 20
max_tokens: 16384
enable_termination_summary: true
enable_skills: false
```

### 方案二：多 Agent 架构（推荐用于复杂场景）

采用 Master-Collector 模式，Master 负责规划，Collector 负责信息收集。

#### 2.1 创建 Collector Agent

创建 `configs/agents/collector.yaml`：

```yaml
type: agent
name: collector
description: "Information collector - gathers and reports with tool_call references"
model: deepseek
enabled: true
tags:
  - collector
  - information-gathering

system_prompt: |
  You are an **Intelligence Scout Agent**. You always find *valuable* information for the User.

  ## YOUR ROLE
  You are a specialized information collector. Your job is to:
  1. Search for information using `web_search`
  2. Fetch detailed content using `web_fetch`
  3. Return a structured report with key findings

  ## WORKFLOW

  1. **Search Phase**:
     - Use `web_search` to find relevant sources
     - Review results and identify promising sources

  2. **Fetch Phase**:
     - Use `web_fetch(index=N)` to fetch from search results
     - Prioritize authoritative and relevant sources

  3. **Report Phase**:
     - Generate a concise report with key findings
     - Include source references

  ## REPORTING FORMAT

  ```markdown
  ## Mission Status
  [State if you found the target info or if it's missing]

  ## Key Findings
  1. **[Finding Title]**: [1-2 sentence summary]
     - Source: [URL or index reference]

  2. **[Finding Title]**: ...
     - Source: ...

  ## Investigation Log
  - Searched for "keyword" using web_search
  - Found N results, selected M most relevant
  - Fetched content from [sources]```

  ## CONSTRAINTS

  - Maximum 5 search queries per mission
  - Maximum 3 content fetches per mission
  - Keep reports concise but informative
  - Always cite sources

tools:
  - web_search
  - web_fetch

session_store: mongodb_session_store

max_steps: 10
enable_termination_summary: true
enable_skills: false
```

#### 2.2 创建 Master Orchestrator Agent

创建 `configs/agents/master_orchestrator.yaml`：

```yaml
type: agent
name: master_orchestrator
description: "Master orchestrator - delegates to collectors and synthesizes results"
model: deepseek
enabled: true
tags:
  - orchestrator
  - multi-agent
  - master

system_prompt: |
  You are the **Master Research Orchestrator**.

  ## YOUR ROLE
  You are the brain. You plan, coordinate, and synthesize. You DO NOT touch tools directly.
  You break down complex research requests into **precise, isolated investigation missions** for the Collector Agent.

  ## THE COLLECTOR AGENT
  The Collector is a specialized information gathering agent. It has access to:
  - `web_search`: Search the web for information
  - `web_fetch`: Fetch detailed content from URLs or search results

  ## WORKFLOW

  1. **Analyze**: Understand the research request
  2. **Plan**: Break down into specific investigation missions
  3. **Dispatch**: Call Collector with clear, specific missions
     - You MAY call multiple Collectors in parallel if the tasks are unrelated
  4. **Synthesize**: Combine results from multiple Collectors
  5. **Generate**: Create the final comprehensive research report

  ## HOW TO DELEGATE

  When calling Collector, provide clear instructions:

  **Good Delegation:**
  - "Mission: Search for recent developments in [topic] from 2024. Focus on academic sources and official documentation."
  - "Mission: Find information about [specific aspect]. Prioritize sources from [authoritative domain]."

  **Bad Delegation:**
  - "Find info about [topic]." (Too vague)
  - "Research everything." (No scope)

  ## INSTRUCTION TEMPLATE for Collector

  Always format your input to Collector as:
  """
  MISSION: [Specific Goal]
  FOCUS: [What to prioritize]
  AVOID: [What to skip]
  """

  ## FINAL REPORT STRUCTURE

  After collecting information from Collectors, generate a comprehensive report:

  ```markdown
  # Research Report: [Topic]

  ## Executive Summary
  [Overview of findings]

  ## Key Findings
  [Synthesized findings from all Collectors]

  ## Detailed Analysis
  [In-depth analysis]

  ## Sources
  [All sources with citations]

  ## Conclusion
  [Summary and takeaways]```

tools:
  - type: agent_tool
    agent: collector
    description: |
      Information Collector, use for ANY information gathering task:
      - Web search and content fetching
      - Information synthesis and reporting

session_store: mongodb_session_store

max_steps: 15
max_tokens: 16384
enable_termination_summary: true
enable_skills: false
```

---

## 创建多阶段研究 Workflow（可选）

对于更复杂的研究场景，可以使用 Workflow 来编排多阶段研究流程。

### Pipeline Workflow 示例

创建 `configs/workflows/deepresearch_pipeline.yaml`：

```yaml
type: workflow
name: deepresearch_pipeline
description: "Multi-stage deep research pipeline"
workflow_type: pipeline
enabled: true
tags:
  - research
  - pipeline
  - multi-stage

stages:
  # Stage 1: Initial Research
  - id: initial_research
    runnable: collector
    input: |
      MISSION: Conduct initial research on {{ input }}
      FOCUS: Find authoritative sources and recent developments
      AVOID: Marketing pages and low-quality sources

  # Stage 2: Deep Dive
  - id: deep_dive
    runnable: collector
    input: |
      MISSION: Deep dive into specific aspects mentioned in the initial research
      CONTEXT: {{ nodes.initial_research.output }}
      FOCUS: Technical details, implementation, and case studies

  # Stage 3: Synthesis
  - id: synthesis
    runnable: master_orchestrator
    input: |
      Synthesize the following research findings into a comprehensive report:
      
      Initial Research:
      {{ nodes.initial_research.output }}
      
      Deep Dive:
      {{ nodes.deep_dive.output }}
      
      Generate a final research report with all findings, analysis, and sources.

session_store: mongodb_session_store
```

### Parallel Workflow 示例

创建 `configs/workflows/parallel_research.yaml`：

```yaml
type: workflow
name: parallel_research
description: "Parallel research from multiple angles"
workflow_type: parallel
enabled: true
tags:
  - research
  - parallel
  - multi-angle

stages:
  # Parallel research from different angles
  - id: academic_research
    runnable: collector
    input: |
      MISSION: Search for academic papers and research articles on {{ input }}
      FOCUS: Peer-reviewed sources, academic databases

  - id: industry_research
    runnable: collector
    input: |
      MISSION: Search for industry reports and news on {{ input }}
      FOCUS: Industry publications, news articles, official announcements

  - id: technical_research
    runnable: collector
    input: |
      MISSION: Search for technical documentation and implementation guides on {{ input }}
      FOCUS: Official documentation, technical blogs, GitHub repositories

merge_template: |
  # Research Report: {{ input }}

  ## Academic Research
  {{ nodes.academic_research.output }}

  ## Industry Research
  {{ nodes.industry_research.output }}

  ## Technical Research
  {{ nodes.technical_research.output }}

  ## Synthesis
  [Master Orchestrator will synthesize these findings]

session_store: mongodb_session_store
```

---

## 使用示例

### 方式一：使用 Python API

创建 `main.py`：

```python
import asyncio
from agio import get_config_system
from agio.runtime import Wire, RunnableExecutor
from agio.runtime.protocol import ExecutionContext
from uuid import uuid4


async def main():
    # 1. 初始化配置系统
    config_system = get_config_system()
    
    # 2. 加载配置
    stats = await config_system.load_from_directory("./configs")
    print(f"Loaded {stats['loaded']} configs, {stats['failed']} failed")
    
    # 3. 构建所有组件
    await config_system.build_all()
    
    # 4. 获取 Agent 实例
    agent = config_system.get_instance("deepresearch_agent")
    
    # 5. 创建执行上下文
    wire = Wire()
    context = ExecutionContext(
        run_id=str(uuid4()),
        session_id=str(uuid4()),
        wire=wire,
    )
    
    # 6. 执行 Agent
    executor = RunnableExecutor(store=config_system.get_instance("mongodb_session_store"))
    
    research_topic = "最新的 AI 大模型发展趋势"
    print(f"开始研究: {research_topic}")
    
    result = await executor.execute(
        runnable=agent,
        input=research_topic,
        context=context,
    )
    
    # 7. 输出结果
    print("\n" + "="*80)
    print("研究结果:")
    print("="*80)
    print(result.response)
    print("\n" + "="*80)
    print(f"执行指标: {result.metrics}")


if __name__ == "__main__":
    asyncio.run(main())
```

### 方式二：使用 API 服务器

启动 API 服务器：

```bash
agio-server --host 0.0.0.0 --port 8900
```

使用 HTTP API：

```bash
# 创建会话
curl -X POST http://localhost:8900/sessions \
  -H "Content-Type: application/json" \
  -d '{}'

# 执行研究
curl -X POST http://localhost:8900/runnables/deepresearch_agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "input": "最新的 AI 大模型发展趋势",
    "session_id": "your-session-id"
  }'
```

### 方式三：使用前端控制面板

启动带前端的 API 服务器：

```python
from agio.api import create_app_with_frontend

app = create_app_with_frontend(
    api_prefix="/agio",
    frontend_path="/",
    enable_frontend=True,
)

# 使用 uvicorn 运行
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8900)
```

访问 `http://localhost:8900` 使用 Web 界面进行研究。

---

## 最佳实践和优化建议

### 1. 系统提示词设计

- **明确角色**：清晰定义 Agent 的角色和职责
- **结构化工作流**：使用 Markdown 格式描述工作流程
- **约束条件**：明确设置搜索深度、来源数量等限制
- **输出格式**：定义清晰的报告结构

### 2. 工具使用策略

- **搜索优化**：
  - 使用多个搜索查询覆盖不同角度
  - 优先使用 `web_fetch(index=N)` 提高效率
  - 利用 `search_query` 参数提取相关内容

- **内容获取**：
  - 使用 `summarize` 参数处理长文章
  - 并行获取多个独立来源
  - 避免获取冗余信息

### 3. 性能优化

- **步数限制**：合理设置 `max_steps`，避免无限循环
- **Token 管理**：使用 `max_tokens` 限制输出长度
- **缓存利用**：工具支持缓存，重复查询自动使用缓存

### 4. 多 Agent 协作

- **职责分离**：Master 负责规划，Collector 负责执行
- **上下文隔离**：使用独立的 Agent 避免上下文污染
- **并行执行**：对于独立任务，使用并行调用提高效率

### 5. 错误处理

- **优雅降级**：工具失败时继续执行，在报告中说明
- **信息验证**：交叉验证多个来源的信息
- **缺失处理**：明确说明未找到的信息

### 6. 可观测性

- **事件流**：使用 Wire 监听执行事件
- **追踪查询**：使用 Trace Store 查询执行历史
- **指标监控**：关注 Token 使用、执行时间等指标

---

## 故障排查

### 常见问题

#### 1. 配置加载失败

**错误信息**:
```
ConfigError: Missing 'type' field in config.yaml
```

**解决方案**:
- 检查 YAML 文件格式
- 确保包含 `type` 和 `name` 字段
- 验证环境变量是否正确设置

#### 2. 工具执行失败

**错误信息**:
```
ToolExecutionError: web_search failed: API key not found
```

**解决方案**:
- 检查 `SERPER_API_KEY` 环境变量
- 验证 API 密钥是否有效
- 检查工具配置中的依赖是否正确

#### 3. Agent 执行超时

**错误信息**:
```
TimeoutError: Agent execution exceeded max_steps
```

**解决方案**:
- 增加 `max_steps` 配置
- 优化系统提示词，减少不必要的工具调用
- 使用多 Agent 架构分担任务

#### 4. MongoDB 连接失败

**错误信息**:
```
ConnectionError: Failed to connect to MongoDB
```

**解决方案**:
- 检查 MongoDB 服务是否运行
- 验证连接 URI 是否正确
- 检查网络连接和防火墙设置

#### 5. 依赖解析失败

**错误信息**:
```
ConfigError: Circular dependency detected
```

**解决方案**:
- 检查配置中的依赖关系
- 移除循环依赖
- 使用 `agent_tool` 或 `workflow_tool` 替代直接依赖

### 调试技巧

1. **查看配置加载统计**:
   ```python
   stats = await config_system.load_from_directory("./configs")
   print(stats)  # {"loaded": 10, "failed": 0}
   ```

2. **查看组件列表**:
   ```python
   components = config_system.list_components()
   for comp in components:
       print(f"{comp['name']}: {comp['type']}")
   ```

3. **监听事件流**:
   ```python
   async for event in wire.read():
       if event.type == StepEventType.STEP_CREATED:
           print(f"Step: {event.step.role} - {event.step.content[:100]}")
   ```

4. **启用详细日志**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

---

## 总结

本手册详细介绍了如何使用 Agio 框架实现一个功能完整的 DeepResearch Agent。通过配置驱动的方式，你可以快速创建和定制研究代理，无需编写复杂的代码。

**核心要点**：

1. **配置驱动**：通过 YAML 配置文件定义所有组件
2. **工具系统**：利用内置工具（web_search、web_fetch）进行信息收集
3. **灵活架构**：支持单 Agent 和多 Agent 架构
4. **工作流编排**：使用 Workflow 实现复杂的研究流程
5. **可观测性**：完整的执行追踪和事件流

**下一步**：

- 根据实际需求调整系统提示词
- 优化工具使用策略
- 探索多 Agent 协作模式
- 使用 Workflow 实现更复杂的研究流程

---

**文档版本**: 1.0  
**最后更新**: 2025-01-XX  
**维护者**: Agio 开发团队

