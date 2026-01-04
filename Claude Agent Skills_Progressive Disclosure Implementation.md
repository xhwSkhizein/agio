# Claude Agent Skills: Progressive Disclosure Implementation

### 一、Claude Agent Skills 渐进式披露机制的实现

渐进式披露（Progressive Disclosure）是 Claude Agent Skills 的核心设计理念，核心目标是 **“仅在需要时提供刚好足够的信息”**，通过分阶段加载内容，在不牺牲功能的前提下控制上下文冗余，平衡 Agent 的响应速度与任务复杂度。其实现完全围绕“信息按需暴露”展开，分为三个关键阶段，每个阶段的加载内容、实现方式和设计目的都有明确边界：

#### 1. 启动阶段：仅加载「元数据」（Discovery）

- **加载内容**：所有可用技能的 `name`（名称）和 `description`（描述），不加载 [SKILL.md](SKILL.md) 正文、脚本或资源文件。
- **实现方式**：
  
  - Agent 启动时，扫描配置目录（如 `~/.config/claude/skills/`、`.claude/skills/`）、插件和内置技能，提取每个技能 [SKILL.md](SKILL.md) 文件的 **YAML 前置元数据**（仅 name 和 description 字段）。
  - 由「Skill 元工具」（大写 S，位于 tools 数组中）动态生成 prompt：将所有技能的元数据聚合为 `<available_skills>` 列表，嵌入到 Skill 工具的描述中，发送给 Claude。
  - 示例：Skill 工具的 prompt 会包含 `"<skill><name>pdf</name><description>Extract text from PDF files...</description></skill>"` 这类精简信息，每个技能仅占用 50-100 tokens。
- **设计目的**：
  
  - 让 Claude 快速知晓“有哪些技能可用”，能够通过自然语言推理匹配用户意图，同时避免初始上下文被大量冗余信息占用（如完整指令、脚本代码），保证启动速度。

#### 2. 激活阶段：加载「完整 [SKILL.md](SKILL.md) 指令」（Activation）

- **加载触发条件**：Claude 通过 LLM 原生推理（无算法匹配、无关键词检索），判断用户任务与某个技能的 description 匹配（例如用户说“提取 PDF 文本”，匹配 `pdf` 技能描述），进而调用 Skill 工具激活该技能。
- **加载内容**：被激活技能的完整 [SKILL.md](SKILL.md) 文件（含 YAML 前置元数据 + Markdown 正文指令）。
- **实现方式**：
  
  - Skill 工具验证技能存在性和权限后，读取该技能的 [SKILL.md](SKILL.md) 完整内容，通过「双消息注入」机制传入上下文：
    
    - 可见消息（`isMeta: false`）：向用户展示精简状态（如 `<command-message>The "pdf" skill is loading</command-message>`），保证透明度。
    - 隐藏消息（`isMeta: true`）：将 [SKILL.md](SKILL.md) 的完整指令（步骤、示例、错误处理等）作为用户消息注入，但不显示在 UI 中，仅供 Claude 读取。
  - [SKILL.md](SKILL.md) 正文建议控制在 5000 字（~800 行）内，避免单次注入过多 tokens。
- **设计目的**：提供完成任务所需的详细指导，此时才加载完整指令，既保证 Claude 有足够上下文，又避免未激活技能的指令占用资源。

#### 3. 执行阶段：按需加载「引用资源」（Execution）

- **加载触发条件**：Claude 遵循 [SKILL.md](SKILL.md) 的步骤指令，在执行特定子任务时（如“初始化技能”“读取框架文档”），才加载对应的引用文件。
- **加载内容**：[SKILL.md](SKILL.md) 中明确引用的 `scripts/`（脚本）、`references/`（文档）、`assets/`（静态资源），而非一次性加载所有关联文件。
- **实现方式**：
  
  - 通过 `{baseDir}` 变量定位资源路径（技能安装目录的绝对路径，自动解析，避免硬编码）。
  - 不同类型资源的加载逻辑由 [SKILL.md](SKILL.md) 指令明确指定，依赖 Read/Bash 等工具触发：
    
    - 文档类资源（references/）：用 Read 工具读取内容，加载到上下文。
    - 脚本类资源（scripts/）：用 Bash 工具执行代码，需在 allowed-tools 中授权。
    - 静态资源（assets/）：仅引用路径，不加载内容到上下文。
- **设计目的**：最后一层“瘦身”，仅加载当前步骤必需的资源，进一步控制上下文规模，避免无关资源占用 tokens。

### 二、“执行阶段：遵循指令，按需加载引用文件（脚本、资源）或执行代码”的具体含义

这句话的核心是：**技能激活后，Claude 不会一次性加载所有关联文件，而是严格按照 [SKILL.md](SKILL.md) 的步骤指令，在需要完成特定子任务时，才加载或执行对应的文件**。其本质是“子任务驱动的资源加载”，结合技能的目录结构和工具授权实现，具体拆解如下：

#### 1. 引用文件的分类与加载逻辑

技能的关联文件按功能分为 3 个目录（博客明确定义），每种文件的“按需加载”方式和场景完全不同：

|目录|内容类型|加载方式|核心用途|
|---|---|---|---|
|`scripts/`|可执行代码（Python/Bash）|通过 Bash 工具执行（需授权）|处理复杂、确定性任务（如生成模板、数据转换）|
|`references/`|文本文档（Markdown/JSON）|通过 Read 工具读取内容到上下文|提供详细规范、Schema、最佳实践等|
|`assets/`|静态资源（模板/图片/二进制）|仅引用路径，不加载内容|作为操作对象（如填充模板、引用图片）|

#### 2. 每种文件的“按需加载”示例（基于博客案例）

##### （1）scripts/：执行可执行代码

- 触发场景：当 [SKILL.md](SKILL.md) 指令要求“自动化完成某步骤”时（如生成技能目录、数据解析）。
- 加载/执行流程：
  
  1. [SKILL.md](SKILL.md) 明确步骤：`Step 3: 运行 init_skill.py 脚本生成技能模板`。
  2. Claude 检查 frontmatter 的 `allowed-tools`（如 `allowed-tools: "Bash(python:*), Read"`），确认权限。
  3. 通过 `{baseDir}` 定位脚本路径，执行命令：`python {baseDir}/scripts/init_skill.py <skill-name>`。
  4. 仅在该步骤执行时加载脚本，执行完成后不保留冗余代码在上下文。
- 例子：`skill-creator` 技能的 [init_skill.py](init_skill.py) 脚本，仅在“初始化新技能”步骤时执行，用于自动创建 [SKILL.md](SKILL.md) 模板和资源目录，替代手动编写的繁琐步骤。

##### （2）references/：读取文本文档到上下文

- 触发场景：当 [SKILL.md](SKILL.md) 指令要求“参考详细文档”时（如学习框架规范、查看 Schema）。
- 加载/执行流程：
  
  1. [SKILL.md](SKILL.md) 明确步骤：`1.4 学习框架文档：Load and read references/mcp_best_practices.md`。
  2. Claude 通过 Read 工具读取文件内容：`Read({baseDir}/references/mcp_best_practices.md)`。
  3. 文件内容被加载到 Claude 的上下文，供后续步骤参考（如“按最佳实践搭建 MCP 服务器”）。
  4. 仅加载当前步骤必需的文档，其他无关文档（如 Python/TypeScript 二选一的 SDK 文档）不加载。
- 例子：`mcp-creator` 技能的 [mcp_best_practices.md](mcp_best_practices.md)，仅在“学习 MCP 框架”步骤时读取，提供服务器搭建的核心规范，避免 [SKILL.md](SKILL.md) 因包含冗长规范而臃肿。

##### （3）assets/：引用静态资源路径

- 触发场景：当 [SKILL.md](SKILL.md) 指令要求“使用模板或静态文件”时（如生成报告、引用图片）。
- 加载/执行流程：
  
  1. [SKILL.md](SKILL.md) 明确步骤：`Use the template at {baseDir}/assets/report-template.html as the report structure`。
  2. Claude 仅获取文件路径，不读取内容到上下文，而是通过 Write 工具操作该路径：如复制模板到输出目录，填充用户数据后生成新文件。
  3. 资源本身不占用上下文 tokens，仅在“填充模板”“引用图片”等步骤时被操作。
- 例子：HTML 报告模板，Claude 在“生成最终报告”步骤时引用该路径，无需加载模板内容，仅需替换占位符并写入新文件。

#### 3. 按需加载的关键实现细节

- **路径可移植性**：通过 `{baseDir}` 变量自动解析技能安装目录，避免硬编码绝对路径（如 `/home/user/skills/`），确保技能在不同环境下都能正确加载资源。
- **权限控制**：脚本执行需在 frontmatter 的 `allowed-tools` 中明确授权（如 `Bash(python:*)` 仅允许执行 Python 脚本），避免未授权代码运行，兼顾灵活性和安全性。
- **触发粒度**：加载行为与 [SKILL.md](SKILL.md) 的步骤强绑定，例如“Step 1 读取参考文档”“Step 2 执行脚本”，每个步骤仅加载该步骤必需的资源，不跨步骤预加载。

#### 4. 设计意义

- **控制上下文规模**：避免 10KB 级别的参考文档、数百行脚本一次性加载到上下文，导致 tokens 溢出（LLM 上下文窗口有限）。
- **提升执行效率**：仅处理当前步骤必需的资源，减少无效加载带来的延迟。
- **增强可维护性**：资源（脚本、文档）可独立更新（如优化脚本逻辑、迭代参考文档），无需修改 [SKILL.md](SKILL.md) 的核心指令。

> （注：文档部分内容可能由 AI 生成）



![sequence-diagram](https://leehanchung.github.io/assets/img/2025-10-26/07-claude-skill-sequence-diagram.png)



## Codex source code


```rust

pub fn render_skills_section(skills: &[SkillMetadata]) -> Option<String> {
    if skills.is_empty() {
        return None;
    }

    let mut lines: Vec<String> = Vec::new();
    lines.push("## Skills".to_string());
    lines.push("These skills are discovered at startup from multiple local sources. Each entry includes a name, description, and file path so you can open the source for full instructions.".to_string());

    for skill in skills {
        let path_str = skill.path.to_string_lossy().replace('\\', "/");
        let name = skill.name.as_str();
        let description = skill.description.as_str();
        lines.push(format!("- {name}: {description} (file: {path_str})"));
    }

    lines.push(
        r###"- Discovery: Available skills are listed in project docs and may also appear in a runtime "## Skills" section (name + description + file path). These are the sources of truth; skill bodies live on disk at the listed paths.
- Trigger rules: If the user names a skill (with `$SkillName` or plain text) OR the task clearly matches a skill's description, you must use that skill for that turn. Multiple mentions mean use them all. Do not carry skills across turns unless re-mentioned.
- Missing/blocked: If a named skill isn't in the list or the path can't be read, say so briefly and continue with the best fallback.
- How to use a skill (progressive disclosure):
  1) After deciding to use a skill, open its `SKILL.md`. Read only enough to follow the workflow.
  2) If `SKILL.md` points to extra folders such as `references/`, load only the specific files needed for the request; don't bulk-load everything.
  3) If `scripts/` exist, prefer running or patching them instead of retyping large code blocks.
  4) If `assets/` or templates exist, reuse them instead of recreating from scratch.
- Description as trigger: The YAML `description` in `SKILL.md` is the primary trigger signal; rely on it to decide applicability. If unsure, ask a brief clarification before proceeding.
- Coordination and sequencing:
  - If multiple skills apply, choose the minimal set that covers the request and state the order you'll use them.
  - Announce which skill(s) you're using and why (one short line). If you skip an obvious skill, say why.
- Context hygiene:
  - Keep context small: summarize long sections instead of pasting them; only load extra files when needed.
  - Avoid deeply nested references; prefer one-hop files explicitly linked from `SKILL.md`.
  - When variants exist (frameworks, providers, domains), pick only the relevant reference file(s) and note that choice.
- Safety and fallback: If a skill can't be applied cleanly (missing files, unclear instructions), state the issue, pick the next-best approach, and continue."###
            .to_string(),
    );

    Some(lines.join("\n"))

```




## References

- https://agentskills.io/home
- https://deepwiki.com/search/codex-agent-skills_f9034c3d-b4f2-40f5-8485-38276788359b
- https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/