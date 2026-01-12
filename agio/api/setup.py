"""
Manual component initialization for Agio API.
"""

import os
from pathlib import Path
from pydantic import SecretStr

from agio.agent import Agent
from agio.api.agio_app import AgioApp
from agio.llm import AnthropicModel, NvidiaModel, OpenAIModel
from agio.runtime.agent_tool import as_tool
from agio.skills.manager import SkillManager
from agio.storage.session import MongoSessionStore
from agio.storage.trace.store import TraceStore
from agio.tools.builtin import (
    BashTool,
    FileEditTool,
    FileReadTool,
    FileWriteTool,
    GlobTool,
    GrepTool,
    LSTool,
    WebFetchTool,
    WebSearchTool,
    WebSearchApiTool,
    WebReaderApiTool,
)
from agio.utils.logging import get_logger

logger = get_logger(__name__)


async def initialize_components(app_state_agio_app: AgioApp) -> None:
    """
    Initialize all Agio components and register them to the AgioApp instance.
    """
    try:
        # 1. Initialize Stores (MongoDB)
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("AGIO_DB_NAME", "agio")

        # Session Store
        session_store = MongoSessionStore(uri=mongo_uri, db_name=db_name)
        # Ensure connection (optional, as methods usually connect on demand, but good for check)
        # await session_store._ensure_connection()

        # Trace Store
        trace_store = TraceStore(mongo_uri=mongo_uri, db_name=db_name)
        await trace_store.initialize()

        # Update AgioApp with stores
        app_state_agio_app.session_store = session_store
        app_state_agio_app.trace_store = trace_store

        # 2. Initialize Models
        # Minimax Model (via Anthropic Interface)
        minimax_model = AnthropicModel(
            id="anthropic/minimax-m2.1",
            name="minimax21",
            model_name="MiniMax-M2.1",
            base_url="https://api.minimaxi.com/anthropic",
            api_key=SecretStr(os.getenv("MINIMAX_API_KEY", "mock-key"))
            if os.getenv("MINIMAX_API_KEY")
            else None,
            max_tokens_to_sample=4096,
            temperature=0.7,
        )

        # Nvidia Model
        nvidia_model = NvidiaModel(
            id="nvidia/glm-4-7",
            name="nvidia/glm-4-7",
            model_name="z-ai/glm4.7",
            # API key should be in env NVIDIA_API_KEY
            temperature=0.6,
            top_p=0.7,
            max_tokens=4096,
        )

        # GPT-4o-mini (Optional/Backup)
        openai_model = OpenAIModel(
            id="openai/gpt-4o-mini",
            name="gpt-4o-mini",
            model_name="gpt-4o-mini",
            temperature=0.7,
        )

        # 3. Initialize Tools
        # Common tools
        ls_tool = LSTool()
        file_read_tool = FileReadTool()
        file_write_tool = FileWriteTool()
        file_edit_tool = FileEditTool()
        grep_tool = GrepTool()
        glob_tool = GlobTool()
        bash_tool = BashTool()
        web_search_tool = WebSearchTool()
        web_fetch_tool = WebFetchTool()
        web_search_api_tool = WebSearchApiTool()
        web_fetch_api_tool = WebReaderApiTool()

        full_tools = [
            ls_tool,
            file_read_tool,
            file_write_tool,
            file_edit_tool,
            grep_tool,
            glob_tool,
            bash_tool,
            web_search_api_tool,
            web_fetch_api_tool,
            # web_search_tool, web_fetch_tool
        ]

        # 4. Initialize Skills
        # Resolve skill directories (using examples/skills)
        skill_dirs = [Path("examples/skills").resolve()]
        skill_manager = SkillManager(skill_dirs=skill_dirs)
        await skill_manager.initialize()

        # 5. Initialize Agents

        # -- Collector Agent --
        collector_prompt = """You are an **Intelligence Scout Agent**. You always find *valuable* information for the User.

  You may receive **Context Hints** or **Known Paths** from the User. 

    1. **CHECK HINTS FIRST**: 
      - If the User says "The file is located at `/path/to/auth.py`", **DO NOT** run `ls` or `find` again. 
      - Go STRAIGHT to `file_read("/path/to/auth.py")`.
      
    2. **NARROW SCOPE**:
      - If the User says "Focus only on `/path/to/frontend/` folder", do not waste tools searching outside that directory.

  ## REVISED WORKFLOW

    IF (specific_file_paths_provided):
        -> READ (Jump to Extraction Phase)
    ELSE IF (folder_hint_provided):
        -> LS/GREP that specific folder (Targeted Discovery)
    ELSE:
        -> LS/GLOB root (General Discovery) - *Only do this as a last resort*

  ## OPERATIONAL CONSTRAINTS

    1. **No Hallucinations**: If you can't find it, say "Not Found". Do not make up information or facts.
    2. **Context Economy**:
        - If a file is 5000 lines long, try to read only the relevant parts if possible, or send warning.
        - For Web, fetch the main text, avoid navigation menus/footers if your tool allows.
    3. **Safety Valve**: If your Discovery phase returns > 20 candidates, STOP. Do not Fetch. Refine your search or report the list of candidates.

  ## REPORTING FORMAT

    You must return a structured report so the User knows what you found without seeing the raw data.

  ```markdown
  ## Mission Status
  [Succinctly state if you found the target info or if it's missing]

  ## Key Findings (The "Meat")
  1. **[Finding Title]**: [1-2 sentence summary of the fact]
    - Source: `/path/to/file` OR `https://url...`
    
  2. **[Finding Title]**: ...
    - Source: ...

  ## Investigation Log
  - Searched for "keyword" using `web_search`.
  - Found 5 results, discarded 3 marketing pages.
  - Fetched content from [Title](URL).
  ```"""

        collector_agent = Agent(
            name="collector",
            model=minimax_model,
            tools=[
                file_read_tool,
                grep_tool,
                ls_tool,
                glob_tool,
                bash_tool,
                web_search_api_tool,
                web_fetch_api_tool,
                # web_search_tool, web_fetch_tool
            ],
            session_store=session_store,
            system_prompt=collector_prompt,
            max_steps=5,
            enable_termination_summary=True,
        )
        app_state_agio_app.register_agent(collector_agent)

        # Create Collector Tool for other agents
        collector_tool = as_tool(
            collector_agent,
            description="""Information Collector, use for ANY information gathering task:
      - Reading files, searching code
      - Web search, page fetching
      - Directory listing""",
        )

        # -- Simple Assistant --
        simple_prompt = "You are a helpful assistant."
        simple_assistant = Agent(
            name="simple_assistant",
            model=minimax_model,
            tools=[ls_tool],
            session_store=session_store,
            skill_manager=skill_manager,
            system_prompt=simple_prompt,
            max_steps=10,
        )
        app_state_agio_app.register_agent(simple_assistant)

        # -- Master Orchestrator --
        orchestrator_prompt = """You are the **Master Orchestrator**.

  ## YOUR ROLE
  You are the brain. You plan, coordinate, and synthesize. You DO NOT touch tools directly.
  You break down complex user requests into **precise, isolated investigation missions** for the Collector Agent.

  ## THE COLLECTOR AGENT
  The Collector is a powerful but stateless tool-user. It has access to:
  - **Local Context**: `file_read`, `grep`, `ls`, `glob`
  - **External Context**: `web_search`, `web_fetch`

  ### How to Assign Tasks (CRITICAL)
  Your instructions to the Collector must be **scoped** and **specific**. 
  NEVER simply pass the user's raw prompt. Translate it into an actionable mission.
  **ALWAYS use absolute paths**.

  **Bad Delegation:**
  - "Find info about Redis." (Too vague, Collector will panic-search everything)
  - "Analyze the code." (No scope)

  **Good Delegation:**
  - [Local] "Locate the `RedisConfig` class in the backend folder and retrieve its connection settings."
  - [Web] "Search for 'LangChain v0.1 migration guide' and fetch the breaking changes section."
  - [Hybrid] "First search the web for 'CVE-2024-xxxx', then grep the local codebase for vulnerable dependency versions."

  ## WORKFLOW
  1. **Analyze**: Deconstruct the User's request.
  2. **Plan**: .
  3. **Dispatch**: Call `Collector` with a clear `mission` and `scope`.
    - You MAY call multiple Collectors in parallel if the tasks are unrelated (e.g., one checks Web, one checks Local DB).
  4. **Route**: Receive the Collector's summary and refs. Pass these IDs to specialized Processors (e.g., CodeAnalyzer, Summarizer) if deep analysis is needed.
  5. **Synthesize**: Present the final answer to the User.

  ## KEY RULES
  - **Parallelism**: Use parallel Collector calls for *different domains* (e.g., Task A: "Check GitHub issues", Task B: "Check local logs"). Do not split a single linear investigation.
  - **Data Flow**: You trade in **Summaries** and **References**. You act as a router for the heavy data.

  ## KEY RESPONSIBILITY: Knowledge Management

  You are not just coordinating tasks; you are **accumulating environmental knowledge**.

  When a Collector returns a report, look for two things:
  1. **The Answer**: Result of the specific query.
  2. **The Map**: What did we learn about the project structure? (e.g., "The frontend is in `/Absolute/path/to/packages/web`", "The main config is `/Absolute/path/to/config.yaml`")

  ## HOW TO DELEGATE (The "Handover" Protocol)

  When calling a Collector, you MUST provide `known_context` to prevent redundant work.

  **Scenario**: You previously asked Collector A to "Explore the project". It found that source code is in `src/`.
  **Next Step**: Now you want Collector B to "Check login logic".

  **Bad Instruction**: 
  "Check login logic." (Collector B will start `ls` from root again)

  **Good Instruction**: 
  "Mission: Check login logic. 
  Context Hints: We already know the source code is in `/Absolute/path/to/src/`. Focus your search there. Do NOT scan the root directory or `node_modules`."

  ## INSTRUCTION TEMPLATE for Collector
  Always format your input to Collector as:
  
  MISSION: [Specific Goal]
  KNOWN_PATHS: [List relevant file paths found by previous agents]
  AVOID: [Paths or actions that are proven useless]
  

  ## Context Hints
  - Current Working Directory: {{ work_dir }}
  - Current Date: {{ date }}"""

        master_orchestrator = Agent(
            name="master_orchestrator",
            model=minimax_model,
            tools=[collector_tool],
            session_store=session_store,
            skill_manager=skill_manager,
            system_prompt=orchestrator_prompt,
            max_steps=10,
            enable_termination_summary=True,
        )
        app_state_agio_app.register_agent(master_orchestrator)

        # -- Worker Agent --
        worker_prompt = """You are an **Intelligence Agent**. You solve problems by plan base & frequency record/check work flow."""

        worker_agent = Agent(
            name="worker",
            model=nvidia_model,
            tools=full_tools + [collector_tool],
            session_store=session_store,
            system_prompt=worker_prompt,
            max_steps=10,
            enable_termination_summary=True,
        )
        app_state_agio_app.register_agent(worker_agent)

        logger.info(
            "agio_components_initialized",
            agents_count=len(app_state_agio_app._agents),
            skills_count=len(skill_manager._metadata_cache),
            session_store="mongo",
            trace_store="mongo",
        )

    except Exception as e:
        logger.error("agio_components_init_failed", error=str(e), exc_info=True)
        # Re-raise so the caller knows init failed
        raise
