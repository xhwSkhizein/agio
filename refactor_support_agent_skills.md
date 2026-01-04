# Agent Skills 集成方案

## 一、概述

本文档规划了将 [Agent Skills](https://agentskills.io/specification) 规范集成到 Agio 项目的详细方案。Agent Skills 是一个标准化的技能格式，通过渐进式披露（Progressive Disclosure）机制，实现"仅在需要时提供刚好足够的信息"，从而在保证功能完整性的同时控制上下文规模。

### 1.1 核心设计理念

**渐进式披露（Progressive Disclosure）**分为三个阶段：

1. **启动阶段（Discovery）**：仅加载所有技能的元数据（name + description），约 50-100 tokens/技能
2. **激活阶段（Activation）**：LLM 推理匹配后，加载被激活技能的完整 `SKILL.md` 文件
3. **执行阶段（Execution）**：按需加载 `scripts/`、`references/`、`assets/` 等资源文件

### 1.2 集成目标

- ✅ 支持 Agent Skills 规范的技能发现和加载
- ✅ 实现渐进式披露机制，优化上下文使用
- ✅ 与现有工具系统无缝集成
- ✅ 支持技能作为工具使用，同时保持技能的特殊性
- ✅ 兼容现有配置系统，支持技能目录配置

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Skills System                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ Skill        │    │ Skill        │    │ Skill        │ │
│  │ Registry     │───►│ Loader       │───►│ Tool         │ │
│  │ (元数据管理)   │    │ (文件加载)    │    │ (工具实现)    │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                  │                    │          │
│         │                  │                    │          │
│         ▼                  ▼                    ▼          │
│  ┌──────────────────────────────────────────────────────┐ │
│  │         Skill Metadata Cache (启动时加载)              │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent System                            │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐│
│  │ Agent        │───►│ AgentExecutor│───►│ ToolExecutor  ││
│  │ (配置容器)    │    │ (执行循环)    │    │ (工具执行)    ││
│  └──────────────┘    └──────────────┘    └──────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 SkillRegistry（技能注册表）

**职责**：
- 扫描技能目录，发现所有可用技能
- 解析 `SKILL.md` 的 YAML frontmatter，提取元数据
- 缓存技能元数据，支持热重载
- 提供技能查询接口

**位置**：`agio/skills/registry.py`

**关键接口**：
```python
class SkillMetadata(BaseModel):
    name: str  # 技能名称（1-64字符，小写字母、数字、连字符）
    description: str  # 技能描述（1-1024字符）
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    path: Path  # SKILL.md 文件路径
    base_dir: Path  # 技能根目录（用于解析 {baseDir} 变量）

class SkillRegistry:
    async def discover_skills(self, skill_dirs: list[Path]) -> list[SkillMetadata]
    async def get_metadata(self, skill_name: str) -> SkillMetadata | None
    async def reload(self) -> None  # 热重载
    def list_available(self) -> list[str]
```

#### 2.2.2 SkillLoader（技能加载器）

**职责**：
- 加载技能的完整 `SKILL.md` 文件（激活阶段）
- 按需加载 `scripts/`、`references/`、`assets/` 资源（执行阶段）
- 解析 `{baseDir}` 变量，替换为技能根目录绝对路径
- 处理文件引用和路径解析

**位置**：`agio/skills/loader.py`

**关键接口**：
```python
class SkillContent(BaseModel):
    metadata: SkillMetadata
    body: str  # SKILL.md 的 Markdown 正文
    frontmatter: dict[str, Any]  # 完整的 YAML frontmatter

class SkillLoader:
    async def load_skill(self, skill_name: str) -> SkillContent
    async def load_reference(self, skill_name: str, rel_path: str) -> str
    async def get_script_path(self, skill_name: str, script_name: str) -> Path
    async def get_asset_path(self, skill_name: str, asset_name: str) -> Path
    def resolve_base_dir(self, skill_name: str, content: str) -> str  # 替换 {baseDir}
```

#### 2.2.3 SkillTool（技能工具）

**职责**：
- 作为工具集成到 Agent 的工具列表中
- 实现技能激活逻辑：加载完整 `SKILL.md` 并注入上下文
- 通过 `content` 和 `content_for_user` 分离 LLM 内容和用户显示内容

**位置**：`agio/skills/tool.py`

**关键接口**：
```python
class SkillTool(BaseTool):
    def __init__(
        self,
        registry: SkillRegistry,
        loader: SkillLoader,
    ):
        ...
    
    async def execute(
        self,
        parameters: dict[str, Any],
        context: ExecutionContext,
        abort_signal: AbortSignal | None = None,
    ) -> ToolResult:
        """
        激活技能：
        1. 验证技能存在性
        2. 加载完整 SKILL.md
        3. 返回 ToolResult（content 包含技能内容，content_for_user 包含用户提示）
        
        注意：权限控制由 PermissionManager 统一处理，不在技能层面检查
        """
```

**工具定义**：
```python
def get_parameters(self) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "要激活的技能名称",
            },
        },
        "required": ["skill_name"],
    }
```

#### 2.2.4 SkillManager（技能管理器）

**职责**：
- 统一管理 SkillRegistry、SkillLoader、SkillTool
- 在系统启动时初始化技能发现
- 提供技能元数据聚合，用于生成系统提示词
- 支持配置驱动的技能目录管理

**位置**：`agio/skills/manager.py`

**关键接口**：
```python
class SkillManager:
    def __init__(
        self,
        skill_dirs: list[Path],
    ):
        ...
    
    async def initialize(self) -> None  # 启动时发现技能
    def get_skill_tool(self) -> SkillTool  # 获取 Skill 工具实例
    def render_skills_section(self) -> str  # 生成技能列表的系统提示词
    async def reload(self) -> None  # 热重载
```

## 三、实现细节

### 3.1 技能发现机制

#### 3.1.1 技能目录配置

支持多个技能目录来源：

1. **配置目录**：`skills/`（项目内置技能）
2. **用户目录**：`~/.agio/skills/`（用户自定义技能）
3. **环境变量**：`AGIO_SKILLS_DIR`（自定义技能目录，逗号分隔）

**配置示例**（`agio/config/settings.py`）：
```python
class AgioSettings(BaseSettings):
    # ... existing fields ...
    
    # Skills configuration
    skills_dirs: list[str] = Field(
        default_factory=lambda: [
            "skills",
            "~/.agio/skills",
        ],
        description="Skill directories to scan",
    )
```

#### 3.1.2 技能目录结构

```
skill-name/
├── SKILL.md          # 必需：技能定义文件
├── scripts/          # 可选：可执行脚本
│   └── init.py
├── references/       # 可选：参考文档
│   └── REFERENCE.md
└── assets/           # 可选：静态资源
    └── template.html
```

#### 3.1.3 元数据解析

**SKILL.md 格式**：
```yaml
---
name: pdf-processing
description: Extract text and tables from PDF files, fill forms, merge documents.
license: Apache-2.0
metadata:
  author: example-org
  version: "1.0"
---

# PDF Processing Skill

Step-by-step instructions...
```

**注意**：`allowed-tools` 字段暂时不支持，权限控制由 `PermissionManager` 统一处理。

**解析逻辑**（`agio/skills/registry.py`）：
```python
def _parse_skill_frontmatter(self, skill_path: Path) -> SkillMetadata:
    """解析 SKILL.md 的 YAML frontmatter"""
    content = skill_path.read_text(encoding="utf-8")
    
    # 提取 YAML frontmatter
    match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not match:
        raise SkillError(f"Missing YAML frontmatter in {skill_path}")
    
    frontmatter = yaml.safe_load(match.group(1))
    
    # 验证必需字段
    if "name" not in frontmatter or "description" not in frontmatter:
        raise SkillError(f"Missing required fields in {skill_path}")
    
    # 验证 name 格式（1-64字符，小写字母、数字、连字符）
    name = frontmatter["name"]
    if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", name):
        raise SkillError(f"Invalid skill name: {name}")
    
    return SkillMetadata(
        name=name,
        description=frontmatter["description"],
        license=frontmatter.get("license"),
        compatibility=frontmatter.get("compatibility"),
        metadata=frontmatter.get("metadata", {}),
        path=skill_path,
        base_dir=skill_path.parent,
    )
```

### 3.2 渐进式披露实现

#### 3.2.1 启动阶段：元数据发现

**时机**：系统启动时（ConfigSystem 初始化后）

**实现位置**：`agio/skills/manager.py`

```python
class SkillManager:
    async def initialize(self) -> None:
        """启动时发现所有技能，仅加载元数据"""
        skill_dirs = self._resolve_skill_dirs()
        self.metadata_cache = await self.registry.discover_skills(skill_dirs)
        logger.info(f"Discovered {len(self.metadata_cache)} skills")
```

**元数据聚合**：生成技能列表的系统提示词

```python
def render_skills_section(self) -> str:
    """生成技能列表的系统提示词（仅包含元数据）"""
    if not self.metadata_cache:
        return ""
    
    lines = ["## Available Skills"]
    lines.append(
        "These skills are discovered at startup. Each entry includes a name "
        "and description. Use the Skill tool to activate a skill when needed."
    )
    
    for metadata in self.metadata_cache:
        lines.append(f"- **{metadata.name}**: {metadata.description}")
    
    lines.append(
        "\n### How to use skills:\n"
        "1. When a user task matches a skill's description, use the Skill tool "
        "to activate it.\n"
        "2. After activation, follow the instructions in the skill's SKILL.md file.\n"
        "3. Load reference files (references/) only when needed for specific steps.\n"
        "4. Execute scripts (scripts/) only when the skill instructions require it.\n"
        "5. Use assets (assets/) as templates or resources, don't load their content."
    )
    
    return "\n".join(lines)
```

**集成点**：在 Agent 的 `system_prompt` 中注入技能列表

**修改位置**：`agio/agent/agent.py`

```python
async def run(self, input: str, *, context: ExecutionContext, ...) -> RunOutput:
    # ... existing code ...
    
    # 注入技能列表到 system_prompt
    if hasattr(self, "_skill_manager") and self._skill_manager:
        skills_section = self._skill_manager.render_skills_section()
        if skills_section:
            if rendered_prompt:
                rendered_prompt = f"{rendered_prompt}\n\n{skills_section}"
            else:
                rendered_prompt = skills_section
    
    # ... rest of the code ...
```

#### 3.2.2 激活阶段：加载完整 SKILL.md

**触发条件**：LLM 调用 Skill 工具，传入 `skill_name` 参数

**实现位置**：`agio/skills/tool.py`

**技能激活和上下文注入机制**：

```python
class SkillTool(BaseTool):
    async def execute(
        self,
        parameters: dict[str, Any],
        context: ExecutionContext,
        abort_signal: AbortSignal | None = None,
    ) -> ToolResult:
        skill_name = parameters.get("skill_name")
        
        # 1. 验证技能存在性
        metadata = await self.registry.get_metadata(skill_name)
        if not metadata:
            return self._create_error_result(
                parameters, f"Skill '{skill_name}' not found", time.time()
            )
        
        # 2. 加载完整 SKILL.md
        skill_content = await self.loader.load_skill(skill_name)
        
        # 3. 解析 {baseDir} 变量
        resolved_body = self.loader.resolve_base_dir(skill_name, skill_content.body)
        
        # 4. 返回 ToolResult：
        #    - content: 传递给 LLM 的消息内容（包含技能完整内容）
        #    - content_for_user: 展示给用户的信息（简洁提示）
        
        return ToolResult(
            tool_name=self.name,
            tool_call_id=parameters.get("tool_call_id", ""),
            input_args=parameters,
            content=resolved_body,  # 完整技能内容，传递给 LLM
            content_for_user=f'The skill "{skill_name}" has been activated.',  # 用户可见信息
            output={
                "skill_name": skill_name,
                "metadata": metadata.dict(),
            },
            is_success=True,
            start_time=time.time(),
            end_time=time.time(),
        )
```

**实现要点**：

1. **扩展 ToolResult 模型**（`agio/domain/events.py`）：
```python
class ToolResult(BaseModel):
    """Result of a tool execution"""
    
    tool_name: str
    tool_call_id: str
    input_args: dict[str, Any]
    content: str  # Result for LLM（构建消息时使用）
    content_for_user: str | None = None  # Display content for frontend（前端渲染时优先使用）
    output: Any  # Raw execution result
    error: str | None = None
    start_time: float
    end_time: float
    duration: float
    is_success: bool = True
```

2. **扩展 Step 模型**（`agio/domain/models.py`）：
```python
class Step(BaseModel):
    # ... existing fields ...
    content_for_user: str | None = None  # 用户可见内容（前端渲染时优先使用）
```

3. **在 StepAdapter 中处理**（`agio/domain/adapters.py`）：
```python
@staticmethod
def to_llm_message(step: Step) -> dict[str, Any]:
    """转换为 LLM 消息格式，只使用 content，不使用 content_for_user"""
    msg: dict[str, Any] = {"role": step.role.value}
    
    if step.content is not None:
        msg["content"] = step.content  # 只使用 content，不包含 content_for_user
    
    # ... rest of the code ...
```

4. **在 StepFactory 中支持**（`agio/runtime/step_factory.py`）：
```python
def tool_step(
    self,
    sequence: int,
    tool_call_id: str,
    name: str,
    content: str,
    content_for_user: str | None = None,  # 新增参数
    metrics: StepMetrics | None = None,
    **overrides,
) -> Step:
    """Create a TOOL step."""
    return Step(
        # ... existing fields ...
        content=content,
        content_for_user=content_for_user,  # 新增字段
        # ... rest of the code ...
    )
```

5. **在 AgentExecutor 中使用**（`agio/agent/executor.py`）：
```python
async def _execute_tools(self, state: RunState, tool_calls: list[dict], ...) -> None:
    results = await self.tool_executor.execute_batch(...)
    
    for result in results:
        seq = await self._allocate_sequence(state.context)
        step = state.sf.tool_step(
            sequence=seq,
            tool_call_id=result.tool_call_id,
            name=result.tool_name,
            content=result.content,  # 传递给 LLM 的内容
            content_for_user=result.content_for_user,  # 用户可见内容
            metrics=StepMetrics(...),
        )
        await state.record_step(step)
```

**前端渲染逻辑**：
- 如果 `Step.content_for_user` 存在，优先显示 `content_for_user`
- 如果 `Step.content_for_user` 不存在，显示 `content`
- 构建 LLM 消息时，始终只使用 `content`，不使用 `content_for_user`

#### 3.2.3 执行阶段：按需加载资源

**触发条件**：LLM 根据 `SKILL.md` 的指令，调用 Read/Bash 等工具加载资源

**实现方式**：通过 `{baseDir}` 变量解析资源路径

**示例**（SKILL.md 中的指令）：
```markdown
## Step 1: Initialize

Run the initialization script:
```bash
python {baseDir}/scripts/init.py
```

## Step 2: Load Reference

Read the reference documentation:
{baseDir}/references/REFERENCE.md
```

**路径解析**（`agio/skills/loader.py`）：

```python
def resolve_base_dir(self, skill_name: str, content: str) -> str:
    """替换内容中的 {baseDir} 变量为技能根目录绝对路径"""
    metadata = self.registry.get_metadata(skill_name)
    if not metadata:
        return content
    
    base_dir = str(metadata.base_dir.absolute())
    return content.replace("{baseDir}", base_dir)
```

**资源加载工具集成**：

现有的 `file_read` 和 `bash` 工具已经支持文件路径，无需修改。技能内容中的 `{baseDir}` 会被解析为绝对路径，工具可以直接使用。

### 3.3 权限控制

**设计原则**：技能层面的权限控制暂时不支持，全权交由现有的 `PermissionManager` 统一处理。

**实现方式**：
- Skill 工具本身不进行权限检查
- 当技能激活后，LLM 调用其他工具（如 Bash、Read）时，由 `PermissionManager` 统一进行权限检查和申请
- 如果工具执行需要权限，`PermissionManager` 会发送权限申请事件（`TOOL_AUTH_REQUIRED`）
- 用户授权后，工具继续执行

**优势**：
- 统一的权限管理机制，避免重复实现
- 技能开发者无需关心权限细节
- 权限策略集中配置和管理

### 3.4 配置系统集成

#### 3.4.1 Agent 配置扩展

**位置**：`agio/config/schema.py`

```python
class AgentConfig(ComponentConfig):
    # ... existing fields ...
    
    # Skills configuration
    enable_skills: bool = Field(
        default=True,
        description="Enable Agent Skills support",
    )
    skill_dirs: list[str] | None = Field(
        default=None,
        description="Custom skill directories for this agent (overrides global)",
    )
```

#### 3.4.2 AgentBuilder 集成

**位置**：`agio/config/builders.py`

```python
class AgentBuilder(ComponentBuilder):
    async def build(self, config: AgentConfig) -> Agent:
        # ... existing code ...
        
        # 初始化技能管理器
        skill_manager = None
        if config.enable_skills:
            from agio.skills.manager import SkillManager
            
            skill_dirs = config.skill_dirs or settings.skills_dirs
            skill_manager = SkillManager(
                skill_dirs=[Path(d).expanduser() for d in skill_dirs],
            )
            await skill_manager.initialize()
            
            # 添加 Skill 工具到工具列表
            skill_tool = skill_manager.get_skill_tool()
            tools.append(skill_tool)
        
        agent = Agent(
            # ... existing parameters ...
        )
        
        # 保存 skill_manager 引用（用于 system_prompt 注入）
        if skill_manager:
            agent._skill_manager = skill_manager
        
        return agent
```

#### 3.4.3 热重载支持

**位置**：`agio/config/hot_reload.py`

```python
class HotReloadManager:
    async def _handle_skill_change(self, file_path: Path) -> None:
        """处理技能文件变更"""
        if file_path.name == "SKILL.md":
            # 重新加载技能元数据
            if hasattr(self.config_system, "_skill_manager"):
                await self.config_system._skill_manager.reload()
            
            # 触发 Agent 重建（如果 Agent 启用了技能）
            affected_agents = self._find_agents_with_skills()
            for agent_name in affected_agents:
                await self._rebuild_component(ComponentType.AGENT, agent_name)
```

## 四、文件结构

### 4.1 新增文件

```
agio/
├── skills/
│   ├── __init__.py
│   ├── registry.py          # 技能注册表（元数据管理）
│   ├── loader.py            # 技能加载器（文件加载）
│   ├── tool.py              # Skill 工具实现
│   ├── manager.py           # 技能管理器（统一入口）
│   └── exceptions.py        # 技能相关异常
```

### 4.2 修改文件

- `agio/config/settings.py`：添加 `skills_dirs` 配置
- `agio/config/schema.py`：扩展 `AgentConfig`，添加技能配置
- `agio/config/builders.py`：在 `AgentBuilder` 中集成技能管理器
- `agio/agent/agent.py`：在 `run()` 方法中注入技能列表到 system_prompt
- `agio/agent/context.py`：处理技能激活的上下文注入
- `agio/domain/models.py`：扩展 `Step` 模型，添加 `skill_activation` 字段

### 4.3 配置目录

```
configs/
└── skills/                  # 项目内置技能目录
    ├── pdf-processing/
    │   ├── SKILL.md
    │   ├── scripts/
    │   ├── references/
    │   └── assets/
    └── code-review/
        ├── SKILL.md
        └── ...
```

## 五、实施计划

### 5.1 第一阶段：核心功能（MVP）

**目标**：实现基本的技能发现和激活功能

**任务**：
1. ✅ 创建 `agio/skills/` 模块结构
2. ✅ 实现 `SkillRegistry`：技能发现和元数据解析
3. ✅ 实现 `SkillLoader`：加载完整 SKILL.md
4. ✅ 实现 `SkillTool`：技能激活工具
5. ✅ 实现 `SkillManager`：统一管理入口
6. ✅ 集成到 `AgentBuilder`：在 Agent 构建时初始化技能管理器
7. ✅ 扩展 `Agent.run()`：注入技能列表到 system_prompt
8. ✅ 实现技能激活的上下文注入机制

**验收标准**：
- 系统启动时能够发现所有技能
- LLM 可以通过 Skill 工具激活技能
- 激活后技能内容能够注入到上下文
- 基本的错误处理（技能不存在、文件读取失败等）

### 5.2 第二阶段：渐进式披露完善

**目标**：完善渐进式披露机制，优化上下文使用

**任务**：
1. ✅ 实现 `{baseDir}` 变量解析
2. ✅ 完善技能激活的双消息注入机制
3. ✅ 实现资源文件的按需加载（references/、scripts/、assets/）
4. ✅ 优化系统提示词生成（技能列表格式）
5. ✅ 添加技能激活的持久化（通过 Step）

**验收标准**：
- 技能激活时仅加载 SKILL.md，不预加载资源
- 资源文件通过现有工具（Read/Bash）按需加载
- 技能激活历史可以被查询和追踪

### 5.3 第三阶段：权限和安全

**目标**：确保技能激活后的工具调用由 `PermissionManager` 统一处理

**任务**：
1. ✅ 验证技能工具不进行权限检查
2. ✅ 确保技能激活后，LLM 调用的其他工具由 `PermissionManager` 处理
3. ✅ 测试权限申请流程（TOOL_AUTH_REQUIRED 事件）

**验收标准**：
- 技能激活不触发权限检查
- 技能执行过程中的工具调用由 `PermissionManager` 统一处理
- 权限申请流程正常工作

### 5.4 第四阶段：热重载和配置

**目标**：支持技能热重载和配置管理

**任务**：
1. ✅ 实现技能元数据的热重载
2. ✅ 集成到 `HotReloadManager`
3. ✅ 支持多技能目录配置
4. ✅ 添加技能验证（SKILL.md 格式验证）

**验收标准**：
- 修改 SKILL.md 后自动重载
- 支持多个技能目录（项目、用户、环境变量）
- 技能格式错误有清晰的提示

### 5.5 第五阶段：测试和文档

**目标**：完善测试和文档

**任务**：
1. ✅ 编写单元测试
2. ✅ 编写集成测试
3. ✅ 更新架构文档
4. ✅ 编写使用示例

**验收标准**：
- 测试覆盖率 > 80%
- 文档完整且易于理解
- 提供至少 2 个示例技能

## 六、技术细节

### 6.1 技能元数据缓存

**设计**：使用内存缓存，启动时加载，支持热重载

**实现**：
```python
class SkillRegistry:
    def __init__(self):
        self._metadata_cache: dict[str, SkillMetadata] = {}
        self._skill_dirs: list[Path] = []
    
    async def discover_skills(self, skill_dirs: list[Path]) -> list[SkillMetadata]:
        """发现所有技能，返回元数据列表"""
        self._skill_dirs = skill_dirs
        cache = {}
        
        for skill_dir in skill_dirs:
            skill_dir = Path(skill_dir).expanduser().resolve()
            if not skill_dir.exists():
                continue
            
            for skill_path in skill_dir.iterdir():
                if not skill_path.is_dir():
                    continue
                
                skill_md = skill_path / "SKILL.md"
                if not skill_md.exists():
                    continue
                
                try:
                    metadata = self._parse_skill_frontmatter(skill_md)
                    cache[metadata.name] = metadata
                except Exception as e:
                    logger.warning(f"Failed to parse skill {skill_path}: {e}")
        
        self._metadata_cache = cache
        return list(cache.values())
```

### 6.2 技能内容加载

**设计**：按需加载，支持 `{baseDir}` 变量替换

**实现**：
```python
class SkillLoader:
    def __init__(self, registry: SkillRegistry):
        self.registry = registry
    
    async def load_skill(self, skill_name: str) -> SkillContent:
        """加载完整 SKILL.md"""
        metadata = await self.registry.get_metadata(skill_name)
        if not metadata:
            raise SkillNotFoundError(skill_name)
        
        content = metadata.path.read_text(encoding="utf-8")
        
        # 提取 frontmatter 和 body
        match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
        if not match:
            raise SkillParseError(f"Invalid SKILL.md format: {metadata.path}")
        
        frontmatter_str = match.group(1)
        body = match.group(2)
        
        frontmatter = yaml.safe_load(frontmatter_str)
        
        # 替换 {baseDir}
        base_dir = str(metadata.base_dir.absolute())
        body = body.replace("{baseDir}", base_dir)
        
        return SkillContent(
            metadata=metadata,
            body=body,
            frontmatter=frontmatter,
        )
```

### 6.3 上下文注入机制

**设计**：通过 `ToolResult.content` 和 `ToolResult.content_for_user` 实现内容分离

**实现**：

1. **扩展 ToolResult 模型**（`agio/domain/events.py`）：
```python
class ToolResult(BaseModel):
    tool_name: str
    tool_call_id: str
    input_args: dict[str, Any]
    content: str  # 传递给 LLM 的内容
    content_for_user: str | None = None  # 用户可见内容
    output: Any
    error: str | None = None
    start_time: float
    end_time: float
    duration: float
    is_success: bool = True
```

2. **扩展 Step 模型**（`agio/domain/models.py`）：
```python
class Step(BaseModel):
    # ... existing fields ...
    content: str | None = None  # LLM 消息内容
    content_for_user: str | None = None  # 用户可见内容
```

3. **在 SkillTool 中返回分离的内容**：
```python
async def execute(self, ...) -> ToolResult:
    # ... load skill content ...
    
    return ToolResult(
        tool_name=self.name,
        tool_call_id=call_id,
        input_args=parameters,
        content=resolved_body,  # 完整技能内容，传递给 LLM
        content_for_user=f'The skill "{skill_name}" has been activated.',  # 用户可见提示
        output={"skill_name": skill_name, "metadata": metadata.dict()},
        is_success=True,
        start_time=time.time(),
        end_time=time.time(),
    )
```

4. **在 AgentExecutor 中传递 content_for_user**：
```python
async def _execute_tools(self, state: RunState, tool_calls: list[dict], ...) -> None:
    results = await self.tool_executor.execute_batch(...)
    
    for result in results:
        step = state.sf.tool_step(
            sequence=seq,
            tool_call_id=result.tool_call_id,
            name=result.tool_name,
            content=result.content,  # 传递给 LLM
            content_for_user=result.content_for_user,  # 用户可见
            metrics=StepMetrics(...),
        )
        await state.record_step(step)
```

5. **在 StepAdapter 中只使用 content**：
```python
@staticmethod
def to_llm_message(step: Step) -> dict[str, Any]:
    """转换为 LLM 消息，只使用 content"""
    msg = {"role": step.role.value}
    if step.content is not None:
        msg["content"] = step.content  # 只使用 content
    # content_for_user 不包含在 LLM 消息中
    return msg
```

### 6.4 错误处理

**异常类型**：
```python
class SkillError(Exception):
    """技能相关错误的基类"""

class SkillNotFoundError(SkillError):
    """技能未找到"""

class SkillParseError(SkillError):
    """技能解析错误"""

class SkillPermissionError(SkillError):
    """技能权限错误"""
```

**错误处理策略**：
- 技能发现失败：记录警告，继续加载其他技能
- 技能激活失败：返回错误 ToolResult，不中断执行
- 资源加载失败：返回错误，LLM 可以处理或重试

## 七、兼容性考虑

### 7.1 向后兼容

- ✅ 技能功能是可选的（`enable_skills: bool = True`），默认启用但可以禁用
- ✅ 不影响现有工具系统
- ✅ 不影响现有 Agent 配置

### 7.2 扩展性

- ✅ 支持自定义技能目录
- ✅ 支持技能元数据扩展（metadata 字段）
- ✅ 支持未来添加技能版本管理
- ✅ 支持技能依赖关系（未来扩展）

## 八、性能考虑

### 8.1 启动性能

- **技能发现**：异步扫描，不阻塞启动
- **元数据缓存**：内存缓存，快速查询
- **延迟加载**：仅加载元数据，不加载完整内容

### 8.2 运行时性能

- **技能激活**：按需加载，不预加载
- **资源加载**：按需加载，不批量加载
- **上下文大小**：渐进式披露，控制 tokens 使用

## 九、测试策略

### 9.1 单元测试

- `SkillRegistry`：技能发现、元数据解析、缓存管理
- `SkillLoader`：文件加载、路径解析、变量替换
- `SkillTool`：工具执行、权限检查、错误处理
- `SkillManager`：初始化、热重载、提示词生成

### 9.2 集成测试

- Agent 启动时技能发现
- 技能激活和上下文注入
- 资源文件按需加载
- 热重载功能

### 9.3 示例技能

创建至少 2 个示例技能用于测试：
1. **simple-skill**：最小化技能，仅包含 SKILL.md
2. **complex-skill**：完整技能，包含 scripts/、references/、assets/

## 十、后续优化

### 10.1 技能市场

- 技能仓库（GitHub/GitLab）
- 技能搜索和发现
- 技能版本管理
- 技能评分和评论

### 10.2 技能组合

- 技能依赖关系
- 技能组合执行
- 技能执行顺序优化

### 10.3 技能调试

- 技能执行追踪
- 技能性能分析
- 技能错误诊断

## 十一、参考资料

- [Agent Skills Specification](https://agentskills.io/specification)
- [Claude Agent Skills Implementation](Claude Agent Skills_Progressive Disclosure Implementation.md)
- [Agio Architecture](./docs/ARCHITECTURE.md)
- [Agent System](./docs/AGENT_SYSTEM.md)

