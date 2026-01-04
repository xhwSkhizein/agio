# YAML 配置和 Prompt 模板变量替换调研报告

## 执行摘要

本报告调研了当前代码库中所有涉及 YAML 配置和 Prompt 变量替换的实现，评估了使用 Jinja2 模板引擎优化现有实现的可行性，并提出了优化建议。

**主要发现**：
1. 当前系统存在**三套不同的变量替换机制**，语法不统一
2. Agent Prompt 目前**不支持变量替换**，只有简单的 Python `.format()` 调用
3. 使用 Jinja2 可以统一模板语法，支持更强大的功能（条件、循环、过滤器等）
4. 需要分阶段迁移，保持向后兼容性

---

## 一、当前变量替换实现分析

### 1.1 配置 YAML 中的环境变量渲染（Jinja2）

**位置**：`agio/config/loader.py` → `ConfigLoader._resolve_env_vars()`

**语法格式**：
- `{{ env.VAR_NAME }}`
- `{{ env.VAR_NAME | default("value") }}`

**变量来源**：环境变量（`os.environ`），未定义变量由 `SilentUndefined` 返回空字符串。

**处理时机**：YAML 文件加载后递归渲染所有字符串；渲染失败保留原值并记录 warning。

**实现方式**：统一使用 `TemplateRenderer`（Jinja2 + 沙箱 + 缓存）。

**使用示例**：
```yaml
# configs/storages/session_stores/mongodb.yaml
backend:
  uri: "{{ env.AGIO_MONGO_URI | default('mongodb://localhost:27017') }}"
  db_name: "{{ env.AGIO_MONGO_DB | default('agio') }}"
```

**特点**：
- ✅ 支持默认值、过滤器与表达式
- ✅ 递归处理嵌套结构（dict、list）
- ✅ 沙箱 + SilentUndefined，缺失变量不抛错
- ✅ 语法与 Workflow/Agent 模板统一（Jinja2）

---

### 1.2 Workflow 模板变量替换（Jinja2）

#### 1.2.1 ContextResolver（主要实现）

**位置**：`agio/workflow/resolver.py` → `ContextResolver.resolve_template()`

**语法格式**：
- `{{ input }}` - 原始 workflow 输入
- `{{ nodes.<id>.output }}` - 节点输出
- `{{ loop.iteration }}` - 循环迭代次数
- `{{ loop.last.<id> }}` - 上一轮迭代的节点输出

**变量来源**：
- Workflow 执行上下文（`self._input`）
- SessionStore 查询（通过 `get_node_output()`）
- Loop 上下文（`self._loop_context`）
- 额外变量（`additional_vars` 参数）

**处理时机**：Workflow 执行时，每个节点执行前调用

**实现方式**：`TemplateRenderer`（Jinja2），上下文自动注入 `input/nodes/loop/env`，可传入 `additional_vars`。

**使用示例**：
```yaml
# configs/workflows/examples/example_pipeline.yaml
stages:
  - id: research
    runnable: collector
    input: |
      Analysis: {analyze.output}
      Topic: {input}
```

**特点**：
- ✅ 支持嵌套变量访问（点号语法）
- ✅ 支持动态查询（从 SessionStore 获取历史输出）
- ❌ 不支持条件表达式
- ❌ 不支持循环/迭代（模板层面）
- ❌ 不支持函数调用或过滤器
- ❌ 错误处理简单（未找到变量返回空字符串）

#### 1.2.2 InputMapping（简化版实现）

**位置**：`agio/workflow/mapping.py` → `InputMapping.build()`

**语法格式**：与 `ContextResolver` 相同

**变量来源**：传入的 `outputs` 字典

**使用场景**：构建节点输入（与 `ContextResolver` 功能重叠）

**特点**：
- 功能与 `ContextResolver` 重叠
- 不支持 SessionStore 查询
- 仅支持传入的 outputs 字典

#### 1.2.3 ConditionEvaluator（条件表达式中的变量）

**位置**：`agio/workflow/condition.py` → `ConditionEvaluator._resolve_variables()`

**语法格式**：`{variable}` 或 `{nested.variable}`

**变量来源**：`outputs` 字典

**使用场景**：评估 workflow 节点的条件表达式

**特点**：
- 与 `ContextResolver` 实现类似
- 仅用于条件表达式中的变量替换
- 不支持条件表达式本身（条件表达式是自定义语法）

#### 1.2.4 ParallelWorkflow merge_template

**位置**：`agio/workflow/parallel.py` → `ParallelWorkflow._execute()`

**语法格式**：`{{results}}`（双大括号，特殊处理）

**变量来源**：合并后的所有分支输出

**实现方式**：简单的字符串替换
```python
final_response = self.merge_template.replace("{{results}}", final_response)
```

**特点**：
- ❌ 仅支持一个特殊变量 `{{results}}`
- ❌ 不支持其他变量替换
- ❌ 功能非常有限

---

### 1.3 Agent Prompt 变量替换（Jinja2 运行时渲染）

#### 1.3.1 system_prompt / termination_summary_prompt

**位置**：`agio/agent/agent.py`（运行时渲染 system_prompt），`agio/agent/summarizer.py`（termination_summary_prompt）

**当前实现**：
- 直接存储字符串，**无任何变量替换**
- 从配置中读取后直接使用

**使用位置**：
- `agio/agent/context.py` → `build_context_from_steps()` - 直接插入 messages
- `agio/agent/agent.py` → `Agent.run()` - 直接使用

**特点**：
- ❌ **完全不支持变量替换**
- ❌ 无法根据运行时上下文动态调整
- ❌ 无法引用其他配置值

#### 1.3.2 termination_summary_prompt

**位置**：`agio/agent/summarizer.py` → `build_termination_messages()`

**当前实现**：使用 Python `.format()` 方法
```python
prompt_template = custom_prompt or DEFAULT_TERMINATION_USER_PROMPT
user_prompt = prompt_template.format(
    termination_reason=_format_termination_reason(termination_reason),
)
```

**支持的变量**：
- `{termination_reason}` - 终止原因

**特点**：
- ✅ 支持基本变量替换
- ❌ 仅支持一个变量
- ❌ 不支持条件、循环等高级功能
- ❌ 语法与 Workflow 模板不一致（Python `.format()` vs `{}`）

**默认模板**：
```python
DEFAULT_TERMINATION_USER_PROMPT = """**IMPORTANT: Execution Limit Reached**

The execution has been interrupted due to {termination_reason}. ...
"""
```

---

## 二、变量来源分析

### 2.1 配置加载阶段（ConfigLoader）

**变量来源**：
- 环境变量（`os.getenv()`）
- 默认值（配置中指定）

**可用变量范围**：
- 系统环境变量
- 进程环境变量

**使用场景**：
- 数据库连接字符串
- API 密钥
- 文件路径
- 端口号等配置项

### 2.2 Workflow 执行阶段（ContextResolver）

**变量来源**：
1. **Workflow 输入**：`{input}`
2. **节点输出**：`{node_id.output}`（从 SessionStore 查询）
3. **Loop 上下文**：
   - `{loop.iteration}` - 当前迭代次数
   - `{loop.last.node_id}` - 上一轮迭代输出
4. **额外变量**：通过 `additional_vars` 参数传入

**可用变量范围**：
- 当前 workflow 执行上下文
- SessionStore 中的历史数据
- 运行时动态生成的数据

**使用场景**：
- 节点间数据传递
- 条件判断
- 循环迭代

### 2.3 Agent Prompt 阶段

**当前变量来源**：
- `termination_summary_prompt`：仅 `{termination_reason}`

**潜在变量来源**（如果支持模板）：
- Agent 配置信息（name, model, tools 列表等）
- 执行上下文（session_id, run_id, user_id 等）
- 工具信息（可用工具列表、工具描述等）
- 环境信息（当前时间、工作目录等）
- 其他配置值（引用其他组件的配置）

---

## 三、Jinja2 模板引擎评估

### 3.1 Jinja2 优势

#### 3.1.1 统一语法

- 配置 YAML：`{{ env.* }}`（Jinja2）
- Workflow 模板：`{{ input }}`, `{{ nodes.* }}`, `{{ loop.* }}`（Jinja2）
- Agent Prompt：`{{ agent.* }}`, `{{ model.* }}`, `{{ tools }}`, `{{ session }}`, `{{ env.* }}`（Jinja2，运行时）

**Jinja2 解决方案**：
- 统一使用 `{{ variable }}` 语法
- 条件表达式：`{% if condition %}...{% endif %}`
- 循环：`{% for item in items %}...{% endfor %}`

#### 3.1.2 强大的功能

**支持的功能**：
1. **变量访问**：
   - `{{ variable }}`
   - `{{ object.attribute }}`
   - `{{ dict['key'] }}`
   - `{{ list[0] }}`

2. **条件表达式**：
   ```jinja2
   {% if condition %}
     content
   {% elif other_condition %}
     other content
   {% else %}
     default content
   {% endif %}
   ```

3. **循环**：
   ```jinja2
   {% for item in items %}
     {{ item }}
   {% endfor %}
   ```

4. **过滤器**：
   - `{{ value|default('N/A') }}`
   - `{{ value|upper }}`
   - `{{ value|length }}`
   - `{{ value|join(', ') }}`

5. **宏（函数）**：
   ```jinja2
   {% macro tool_list(tools) %}
     {% for tool in tools %}
       - {{ tool.name }}: {{ tool.description }}
     {% endfor %}
   {% endmacro %}
   ```

6. **包含和继承**：
   - `{% include 'template.yaml' %}`
   - `{% extends 'base.yaml' %}`

#### 3.1.3 安全性

- **沙箱模式**：可以限制可用的函数和过滤器
- **自动转义**：防止 XSS 等安全问题
- **错误处理**：清晰的错误信息

#### 3.1.4 性能

- **编译缓存**：模板可以预编译
- **高效渲染**：C 扩展支持，性能优秀

### 3.2 Jinja2 适用场景分析

#### 3.2.1 配置 YAML（✅ 非常适合）

**当前需求**：
- 环境变量替换
- 条件配置（根据环境选择不同配置）
- 循环生成配置项

**Jinja2 优势**：
```yaml
# 示例：条件配置
backend:
  type: mongodb
  uri: "{{ env.AGIO_MONGO_URI | default('mongodb://localhost:27017') }}"
  {% if env.ENVIRONMENT == 'production' %}
  enable_ssl: true
  {% else %}
  enable_ssl: false
  {% endif %}

# 示例：循环生成工具列表
tools:
  {% for tool_name in env.ENABLED_TOOLS.split(',') %}
  - {{ tool_name }}
  {% endfor %}
```

#### 3.2.2 Workflow 模板（✅ 非常适合）

**当前需求**：
- 节点输出引用
- 条件输入构建
- 循环迭代处理

**Jinja2 优势**：
```yaml
# 示例：条件输入
stages:
  - id: analyze
    runnable: analyzer
    input: |
      {% if input %}
      Analyze: {{ input }}
      {% else %}
      Please provide input to analyze.
      {% endif %}

# 示例：循环生成输入
stages:
  - id: process
    runnable: processor
    input: |
      Process the following items:
      {% for item in items %}
      - {{ item }}
      {% endfor %}
```

#### 3.2.3 Agent Prompt（✅ 非常适合）

**当前需求**：
- 动态生成 system_prompt
- 引用工具列表
- 条件提示内容

**Jinja2 优势**：
```yaml
# 示例：动态 system_prompt
system_prompt: |
  You are {{ name }}, a helpful assistant.
  
  {% if tools %}
  Available tools:
  {% for tool in tools %}
  - {{ tool.name }}: {{ tool.description }}
  {% endfor %}
  {% endif %}
  
  {% if user_id %}
  User ID: {{ user_id }}
  {% endif %}
  
  Current working directory: {{ env.PWD }}
```

### 3.3 潜在问题和注意事项

#### 3.3.1 语法冲突

**问题**：YAML 中的 `{{ }}` 可能与 Jinja2 语法冲突

**解决方案**：
- 使用 YAML 的 `|` 或 `>` 多行字符串
- 或者使用自定义分隔符（Jinja2 支持）

#### 3.3.2 性能考虑

**问题**：每次执行都需要渲染模板

**解决方案**：
- 使用 Jinja2 的 `Environment` 和模板缓存
- 配置加载时预编译模板
- 运行时模板可以缓存

#### 3.3.3 错误处理

**问题**：模板语法错误可能导致配置加载失败

**解决方案**：
- 提供清晰的错误信息
- 支持模板验证工具
- 在开发阶段进行模板检查

#### 3.3.4 安全性

**问题**：模板可能执行危险操作

**解决方案**：
- 使用 Jinja2 的沙箱模式
- 限制可用的函数和过滤器
- 对用户输入的模板进行严格验证

#### 3.3.5 向后兼容性

**问题**：现有配置需要迁移

**解决方案**：
- 现有配置不多，不想后兼容，直接全部替换即可

---

## 四、优化建议

### 4.1 统一模板引擎

**建议**：使用 Jinja2 统一所有模板处理

**实施步骤**：
1. **阶段一**：在 `ConfigLoader` 中集成 Jinja2
   - 替换现有的环境变量替换逻辑
   - 支持 Jinja2 语法
   - 直接替换，不保持向后兼容

2. **阶段二**：在 `ContextResolver` 中集成 Jinja2
   - 替换现有的变量替换逻辑
   - 支持条件表达式和循环
   - 添加变量验证和文档
   - 直接替换，不保持向后兼容

3. **阶段三**：在 Agent 运行时集成 Jinja2（**重要**：不在 Builder 中）
   - 在 `Agent.run()` 或 `build_context_from_steps()` 中渲染 `system_prompt`
   - 在 `build_termination_messages()` 中渲染 `termination_summary_prompt`
   - 提供运行时变量上下文
   - 支持基于运行时状态动态渲染

### 4.2 变量上下文设计

#### 4.2.1 配置加载阶段

**变量上下文**：
```python
{
    'env': os.environ,  # 环境变量
    'config': {...},    # 当前配置对象（可选）
}
```

**示例**：
```yaml
backend:
  uri: "{{ env.AGIO_MONGO_URI | default('mongodb://localhost:27017') }}"
  {% if env.ENVIRONMENT == 'production' %}
  enable_ssl: true
  {% endif %}
```

#### 4.2.2 Workflow 执行阶段

**变量上下文**：
```python
{
    'input': workflow_input,
    'nodes': {
        'node_id': {
            'output': node_output,
            'metrics': {...},
        },
    },
    'loop': {
        'iteration': current_iteration,
        'last': {
            'node_id': last_output,
        },
    },
    'env': os.environ,  # 可选：环境变量
}
```

**示例**：
```yaml
stages:
  - id: process
    runnable: processor
    input: |
      {% if nodes.analyze.output %}
      Based on analysis: {{ nodes.analyze.output }}
      {% endif %}
      Process: {{ input }}
```

#### 4.2.3 Agent Prompt 阶段

**变量上下文**：
```python
{
    'agent': {
        'name': agent.name,
        'model': agent.model.name,
        'tools': [
            {'name': tool.name, 'description': tool.description},
            ...
        ],
    },
    'context': {
        'session_id': context.session_id,
        'run_id': context.run_id,
        'user_id': agent.user_id,
    },
    'env': os.environ,
    'datetime': datetime,  # 时间相关函数
}
```

**示例**：
```yaml
system_prompt: |
  You are {{ agent.name }}.
  
  {% if agent.tools %}
  Available tools:
  {% for tool in agent.tools %}
  - {{ tool.name }}: {{ tool.description }}
  {% endfor %}
  {% endif %}
  
  Current time: {{ datetime.now().strftime('%Y-%m-%d %H:%M:%S') }}
```

### 4.3 实现架构设计

#### 4.3.1 模板渲染器抽象

**建议创建**：`agio/config/template.py`

```python
from jinja2 import Environment, Template, select_autoescape
from typing import Any, Dict

class TemplateRenderer:
    """统一的模板渲染器"""
    
    def __init__(self, enable_sandbox: bool = True):
        self.env = Environment(
            autoescape=select_autoescape(['html', 'xml']),
            # 沙箱模式配置
        )
    
    def render_config(
        self, 
        config_data: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """渲染配置 YAML"""
        # 递归处理所有字符串值
        pass
    
    def render_workflow_template(
        self,
        template: str,
        context: Dict[str, Any]
    ) -> str:
        """渲染 Workflow 模板"""
        pass
    
    def render_prompt(
        self,
        prompt: str,
        context: Dict[str, Any]
    ) -> str:
        """渲染 Agent Prompt"""
        pass
```

#### 4.3.2 集成点

1. **ConfigLoader**：
   ```python
   # agio/config/loader.py
   from agio.config.template import TemplateRenderer
   
   class ConfigLoader:
       def __init__(self, config_dir: str | Path):
           self.template_renderer = TemplateRenderer()
       
       def _load_yaml_file(self, file_path: Path) -> dict[str, Any] | None:
           data = yaml.safe_load(f)
           # 使用 Jinja2 渲染
           context = {'env': os.environ}
           data = self.template_renderer.render_config(data, context)
           return data
   ```

2. **ContextResolver**：
   ```python
   # agio/workflow/resolver.py
   from agio.config.template import TemplateRenderer
   
   class ContextResolver:
       def __init__(self, ...):
           self.template_renderer = TemplateRenderer()
       
       async def resolve_template(self, template: str, ...) -> str:
           context = self._build_context()
           return self.template_renderer.render_workflow_template(
               template, context
           )
   ```

3. **Agent 运行时渲染**（**重要**：不在 Builder 中渲染）：
   ```python
   # agio/agent/context.py 或 agio/agent/agent.py
   from agio.config.template import TemplateRenderer
   
   class Agent:
       async def run(self, input: str, *, context: ExecutionContext, ...):
           # 在运行时渲染 system_prompt
           if self.system_prompt:
               renderer = TemplateRenderer()
               prompt_context = self._build_runtime_context(context)
               system_prompt = renderer.render_prompt(
                   self.system_prompt, prompt_context
               )
           else:
               system_prompt = None
           
           # 使用渲染后的 system_prompt 构建消息
           messages = await build_context_from_steps(
               ...,
               system_prompt=system_prompt,  # 使用渲染后的 prompt
           )
   ```
   
   **为什么在运行时渲染**：
   - AgentBuilder 加载配置时，运行时状态数据（如 session_id, run_id, tools 列表）可能还不存在
   - 工具列表可能在运行时才确定（动态工具注入）
   - 用户上下文、会话历史等运行时数据需要在执行时才能获取
   - 支持基于运行时状态动态调整 Prompt

### 4.4 Workflow 状态变量清晰度改进方案

#### 4.4.1 问题分析

**当前问题**：
1. **隐式变量**：变量如 `{input}`, `{node_id.output}`, `{loop.iteration}` 是隐式约定
2. **无类型提示**：用户不知道变量类型（字符串、数字、对象？）
3. **无文档化**：需要查看代码才能知道有哪些变量可用
4. **无验证**：配置错误只能在运行时发现
5. **不直观**：`{node_id.output}` 这种语法不够清晰

**用户负担**：
- 需要记忆变量名称和格式
- 不知道哪些变量在什么场景下可用
- 配置错误难以发现和调试

#### 4.4.2 改进方案

##### 方案一：显式变量声明（推荐）

**核心思想**：在 Workflow 配置中显式声明可用变量，提供类型和描述

**实现方式**：

1. **扩展 StageConfig Schema**：
```python
# agio/config/schema.py
from pydantic import BaseModel, Field
from typing import Literal

class VariableDeclaration(BaseModel):
    """变量声明"""
    name: str
    type: Literal["string", "number", "boolean", "object", "array"]
    description: str
    source: Literal["input", "node_output", "loop", "env", "custom"]
    required: bool = False
    default: Any = None

class StageConfig(BaseModel):
    id: str
    runnable: str | dict
    input: str = "{query}"
    condition: str | None = None
    
    # 新增：显式声明可用变量
    variables: list[VariableDeclaration] = Field(
        default_factory=list,
        description="Available variables for this stage's templates"
    )
```

2. **配置示例**：
```yaml
type: workflow
name: example_pipeline
workflow_type: pipeline

stages:
  - id: analyze
    runnable: analyzer
    input: |
      Analyze: {{ input }}
      Context: {{ env.CONTEXT }}
    variables:
      - name: input
        type: string
        description: "Original workflow input"
        source: input
        required: true
      - name: env.CONTEXT
        type: string
        description: "Environment variable CONTEXT"
        source: env
        default: "default"

  - id: process
    runnable: processor
    input: |
      Process: {{ input }}
      Based on: {{ nodes.analyze.output }}
    variables:
      - name: input
        type: string
        description: "Original workflow input"
        source: input
      - name: nodes.analyze.output
        type: string
        description: "Output from analyze stage"
        source: node_output
        required: true
```

**优势**：
- ✅ 显式声明，用户一目了然
- ✅ 类型安全，支持验证
- ✅ 自文档化，配置即文档
- ✅ IDE 友好，支持自动补全（如果工具支持）

**劣势**：
- ❌ 配置更冗长
- ❌ 需要维护变量声明

##### 方案二：结构化上下文对象（更优雅）

**核心思想**：使用结构化的上下文对象，而不是字符串模板

**实现方式**：

1. **定义上下文 Schema**：
```python
# agio/workflow/context.py
from pydantic import BaseModel
from typing import Dict, Any, Optional

class WorkflowContext(BaseModel):
    """Workflow 执行上下文 - 显式结构"""
    input: str
    nodes: Dict[str, "NodeOutput"] = {}
    loop: Optional["LoopContext"] = None
    env: Dict[str, str] = {}
    custom: Dict[str, Any] = {}

class NodeOutput(BaseModel):
    output: str
    metrics: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class LoopContext(BaseModel):
    iteration: int
    last: Dict[str, str] = {}
```

2. **配置示例**：
```yaml
type: workflow
name: example_pipeline
workflow_type: pipeline

stages:
  - id: analyze
    runnable: analyzer
    # 使用结构化输入，而不是字符串模板
    input:
      type: template  # 或 "object", "json"
      template: |
        Analyze: {{ context.input }}
      context:
        # 显式指定使用的上下文变量
        input: true  # 使用 context.input
        env:
          - CONTEXT  # 使用 context.env.CONTEXT

  - id: process
    runnable: processor
    input:
      type: template
      template: |
        Process: {{ context.input }}
        Based on: {{ context.nodes.analyze.output }}
      context:
        input: true
        nodes:
          - analyze  # 需要 analyze 节点的输出
```

**优势**：
- ✅ 更结构化，类型安全
- ✅ 显式依赖声明
- ✅ 支持复杂数据结构
- ✅ 易于验证和调试

**劣势**：
- ❌ 配置格式变化较大
- ❌ 需要重构现有代码

##### 方案三：变量文档 + 运行时验证（折中方案）

**核心思想**：保持现有语法，但添加文档和运行时验证

**实现方式**：

1. **在 Schema 中添加变量文档**：
```python
class StageConfig(BaseModel):
    id: str
    runnable: str | dict
    input: str = Field(
        default="{query}",
        description="""
        Input template for this stage. Available variables:
        - {input}: Original workflow input (string)
        - {nodes.<stage_id>.output}: Output from stage <stage_id> (string)
        - {loop.iteration}: Current loop iteration (number, LoopWorkflow only)
        - {loop.last.<stage_id>}: Last iteration output (string, LoopWorkflow only)
        - {env.<VAR_NAME>}: Environment variable (string)
        
        Example: "Process {{ input }} based on {{ nodes.analyze.output }}"
        """
    )
```

2. **运行时验证**：
```python
class ContextResolver:
    async def resolve_template(self, template: str, ...) -> str:
        # 1. 解析模板，提取所有变量引用
        variables = self._extract_variables(template)
        
        # 2. 验证变量是否存在
        missing = []
        for var in variables:
            if not self._variable_exists(var):
                missing.append(var)
        
        if missing:
            raise TemplateError(
                f"Unknown variables in template: {missing}. "
                f"Available: {self._list_available_variables()}"
            )
        
        # 3. 渲染模板
        return self._render(template, context)
```

3. **提供变量列表 API**：
```python
# agio/api/routes/workflows.py
@router.get("/workflows/{workflow_id}/variables")
async def get_workflow_variables(workflow_id: str):
    """获取 Workflow 可用变量列表"""
    workflow = config_sys.get(workflow_id)
    return {
        "variables": [
            {
                "name": "input",
                "type": "string",
                "description": "Original workflow input",
                "available": True
            },
            {
                "name": "nodes.<stage_id>.output",
                "type": "string",
                "description": "Output from stage <stage_id>",
                "available": True
            },
            # ...
        ]
    }
```

**优势**：
- ✅ 保持现有语法，改动最小
- ✅ 运行时验证，及早发现错误
- ✅ 提供 API 查询可用变量
- ✅ 文档化变量

**劣势**：
- ❌ 仍然是隐式约定
- ❌ 需要运行时才能验证

#### 4.4.3 推荐方案

**推荐采用方案三（变量文档 + 运行时验证）作为过渡方案**，理由：

1. **最小改动**：保持现有语法，不需要大规模重构
2. **快速实施**：可以立即添加文档和验证
3. **向后兼容**：现有配置无需修改
4. **渐进式改进**：后续可以逐步迁移到方案一或方案二

**长期目标**：考虑迁移到方案一（显式变量声明），提供更好的类型安全和 IDE 支持。

#### 4.4.4 实施建议

**立即实施方案三的具体代码**：

1. **更新 StageConfig Schema**：
```python
# agio/config/schema.py
class StageConfig(BaseModel):
    """Configuration for a workflow stage"""
    
    id: str
    runnable: str | dict
    input: str = Field(
        default="{query}",
        description="""
        Input template for this stage (Jinja2 syntax).
        
        Available variables:
        - {{ input }}: Original workflow input (string)
        - {{ nodes.<stage_id>.output }}: Output from stage <stage_id> (string)
        - {{ loop.iteration }}: Current loop iteration (number, LoopWorkflow only)
        - {{ loop.last.<stage_id> }}: Last iteration output (string, LoopWorkflow only)
        - {{ env.<VAR_NAME> }}: Environment variable (string)
        
        Examples:
        - "Process {{ input }}"
        - "Based on {{ nodes.analyze.output }}, process {{ input }}"
        - "Iteration {{ loop.iteration }}: {{ input }}"
        """
    )
    condition: str | None = Field(
        default=None,
        description="""
        Condition expression for conditional execution (Jinja2 syntax).
        
        Available variables: Same as input template.
        The expression should evaluate to a boolean value.
        
        Examples:
        - "{{ nodes.analyze.output }}"
        - "{{ loop.iteration }} < 5"
        - "{{ nodes.check.result }} == 'success'"
        """
    )
```

2. **增强 ContextResolver 验证**：
```python
# agio/workflow/resolver.py
class ContextResolver:
    # 定义可用变量模式
    AVAILABLE_VARIABLES = {
        'input': {
            'type': 'string',
            'description': 'Original workflow input',
            'source': 'workflow'
        },
        'nodes': {
            'type': 'object',
            'description': 'Node outputs: nodes.<stage_id>.output',
            'source': 'workflow'
        },
        'loop': {
            'type': 'object',
            'description': 'Loop context: loop.iteration, loop.last.<stage_id>',
            'source': 'workflow',
            'available_in': ['LoopWorkflow']
        },
        'env': {
            'type': 'object',
            'description': 'Environment variables: env.<VAR_NAME>',
            'source': 'system'
        }
    }
    
    async def resolve_template(self, template: str, ...) -> str:
        # 1. 提取模板中的变量引用
        from jinja2 import Environment, meta
        env = Environment()
        ast = env.parse(template)
        variables = meta.find_undeclared_variables(ast)
        
        # 2. 验证变量是否存在（可选，用于更好的错误提示）
        # 注意：Jinja2 本身会在渲染时处理未定义变量，这里主要用于提前验证
        
        # 3. 构建上下文并渲染
        context = self._build_context()
        template_obj = env.from_string(template)
        return template_obj.render(**context)
    
    def _build_context(self) -> Dict[str, Any]:
        """构建 Jinja2 渲染上下文"""
        context = {
            'input': self._input or '',
            'nodes': self._build_nodes_context(),
            'env': os.environ,
        }
        
        if self._loop_context:
            context['loop'] = self._loop_context
        
        return context
    
    def _build_nodes_context(self) -> Dict[str, Dict[str, Any]]:
        """构建节点输出上下文"""
        # 返回结构：{'stage_id': {'output': '...', 'metrics': {...}}}
        # 这里需要从 state 或 store 获取
        # 实现细节...
        pass
    
    def get_available_variables(self) -> Dict[str, Any]:
        """返回可用变量列表（用于错误提示和文档）"""
        return self.AVAILABLE_VARIABLES
```

3. **改进错误信息**：
```python
# agio/workflow/resolver.py
class TemplateError(Exception):
    """模板渲染错误"""
    def __init__(self, message: str, template: str, available_vars: Dict[str, Any]):
        self.message = message
        self.template = template
        self.available_vars = available_vars
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """格式化错误信息，包含可用变量列表"""
        msg = f"{self.message}\n\nTemplate: {self.template}\n\n"
        msg += "Available variables:\n"
        for var_name, var_info in self.available_vars.items():
            msg += f"  - {var_name}: {var_info['description']}\n"
        return msg
```

4. **更新文档**：
在 `docs/WORKFLOW_ORCHESTRATION.md` 中添加详细的变量说明章节。

#### 4.4.5 实施建议

1. **立即行动**：
   - 在 `StageConfig` 的 `input` 和 `condition` 字段添加详细的变量文档
   - 在 `ContextResolver` 中添加变量验证
   - 提供清晰的错误信息

2. **短期改进**：
   - 添加 API 查询可用变量
   - 在文档中详细列出所有变量
   - 提供配置验证工具

3. **长期优化**：
   - 考虑引入显式变量声明（方案一）
   - 支持 IDE 插件提供自动补全
   - 提供配置迁移工具

### 4.5 性能优化建议

1. **模板缓存**：
   - 配置加载时预编译模板
   - 运行时模板缓存（LRU Cache）
   - 模板变更检测（文件监控）

2. **延迟渲染**：
   - 配置加载时：渲染所有静态部分
   - 运行时：仅渲染动态部分（如 Workflow 模板）

3. **批量渲染**：
   - 合并多个模板渲染操作
   - 减少 Jinja2 Environment 创建开销

### 4.6 安全性建议

1. **沙箱模式**：
   ```python
   from jinja2.sandbox import SandboxedEnvironment
   
   env = SandboxedEnvironment()
   ```

2. **限制函数**：
   ```python
   env.globals['env'] = os.environ  # 仅允许 env
   # 禁止其他危险函数
   ```

3. **输入验证**：
   - 模板语法检查
   - 变量名白名单
   - 模板大小限制

---

## 五、实施路线图

### 阶段一：基础集成（1-2 周）

**目标**：在 ConfigLoader 中集成 Jinja2

**任务**：
1. 创建 `TemplateRenderer` 类
2. 在 `ConfigLoader` 中集成
3. 支持环境变量访问：`{{ env.VAR_NAME }}`
4. 保持 `${VAR_NAME}` 向后兼容
5. 添加单元测试

**验收标准**：
- ✅ 现有配置仍能正常工作
- ✅ 新语法 `{{ env.VAR_NAME }}` 可用
- ✅ 支持默认值：`{{ env.VAR_NAME | default('default') }}`

### 阶段二：Workflow 模板升级（2-3 周）

**目标**：在 ContextResolver 中集成 Jinja2

**任务**：
1. 升级 `ContextResolver.resolve_template()`
2. 支持条件表达式和循环
3. 保持 `{variable}` 语法向后兼容
4. 更新文档和示例
5. 添加集成测试

**验收标准**：
- ✅ 现有 Workflow 配置仍能正常工作
- ✅ 支持条件表达式：`{% if condition %}...{% endif %}`
- ✅ 支持循环：`{% for item in items %}...{% endfor %}`

### 阶段三：Agent Prompt 支持（1-2 周）

**目标**：Agent Prompt 支持 Jinja2 模板（**运行时渲染**）

**任务**：
1. 在 `Agent.run()` 或 `build_context_from_steps()` 中渲染 `system_prompt`（**不在 Builder 中**）
2. 在 `build_termination_messages()` 中渲染 `termination_summary_prompt`
3. 构建运行时 Prompt 变量上下文（包含 tools, context, env 等）
4. 支持基于运行时状态动态渲染
5. 添加示例配置

**验收标准**：
- ✅ `system_prompt` 在运行时支持变量替换
- ✅ `termination_summary_prompt` 支持 Jinja2
- ✅ 可以引用工具列表、运行时上下文等
- ✅ 渲染时机正确（运行时，非构建时）

### 阶段四：Workflow 变量清晰度改进（1-2 周）

**目标**：改进 Workflow 状态变量的清晰度和可用性

**任务**：
1. 在 `StageConfig` 中添加变量文档（Field description）
2. 在 `ContextResolver` 中添加变量验证
3. 提供清晰的错误信息（列出可用变量）
4. 添加 API 查询可用变量（可选）
5. 更新 Workflow 文档，列出所有变量

**验收标准**：
- ✅ 配置字段有详细的变量文档
- ✅ 运行时变量验证，清晰的错误信息
- ✅ 用户能够清楚知道有哪些变量可用

### 阶段五：优化和文档（1 周）

**目标**：性能优化和完善文档

**任务**：
1. 实现模板缓存
2. 性能测试和优化
3. 编写迁移指南
4. 更新所有文档
5. 添加更多示例

**验收标准**：
- ✅ 模板渲染性能满足要求
- ✅ 文档完整清晰
- ✅ 配置示例完整

---

## 六、风险评估

### 6.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 语法冲突 | 中 | 低 | 使用 YAML 多行字符串，明确分隔 |
| 性能下降 | 中 | 中 | 模板缓存，延迟渲染 |
| 向后兼容性问题 | 高 | 中 | 双语法支持，充分测试 |

### 6.2 实施风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 迁移工作量大 | 中 | 高 | 分阶段迁移，提供工具 |
| 学习曲线 | 低 | 中 | 完善文档，提供示例 |
| 用户接受度 | 低 | 低 | 保持向后兼容，逐步推广 |

---

## 七、结论

### 7.1 总结

1. **当前状态**：
   - 存在三套不同的变量替换机制
   - Agent Prompt 不支持变量替换
   - 语法不统一，功能有限

2. **Jinja2 优势**：
   - 统一语法，功能强大
   - 支持条件、循环、过滤器等
   - 成熟稳定，性能优秀

3. **实施建议**：
   - ✅ **强烈建议**使用 Jinja2 统一模板引擎
   - ✅ 分阶段实施，保持向后兼容
   - ✅ 重点关注安全性和性能

### 7.2 推荐方案

**推荐使用 Jinja2 模板引擎**，理由：

1. **统一性**：统一所有模板语法，降低学习成本
2. **功能性**：支持条件、循环等高级功能，满足复杂需求
3. **可扩展性**：易于扩展自定义过滤器和函数
4. **成熟度**：Jinja2 是 Python 生态中最成熟的模板引擎
5. **社区支持**：文档完善，社区活跃

### 7.3 下一步行动

1. **立即行动**：
   - 创建 `TemplateRenderer` 类
   - 在 `ConfigLoader` 中集成 Jinja2
   - 编写单元测试

2. **短期计划**：
   - 完成阶段一和阶段二
   - 更新 Workflow 模板支持

3. **中期计划**：
   - 完成 Agent Prompt 支持
   - 性能优化
   - 文档完善

---

## 附录

### A. 当前变量替换实现位置汇总

| 位置 | 文件 | 方法 | 语法 | 变量来源 |
|------|------|------|------|----------|
| 配置加载 | `agio/config/loader.py` | `_resolve_env_vars()` | `{{ env.VAR | default() }}` | 环境变量 |
| Workflow 模板 | `agio/workflow/resolver.py` | `resolve_template()` | `{{ ... }}` | 执行上下文 |
| Workflow 输入 | `agio/workflow/mapping.py` | `build()` | `{{ ... }}` | outputs 字典 |
| Workflow 条件 | `agio/workflow/condition.py` | `evaluate()` | `{{ ... }}` | outputs 字典 |
| Parallel 合并 | `agio/workflow/parallel.py` | `_execute()` | `{{results}}` | 合并输出 |
| Agent Prompt | `agio/agent/summarizer.py` | `build_termination_messages()` | `{variable}` | Python format |

### B. Jinja2 语法参考

**变量**：
```jinja2
{{ variable }}
{{ object.attribute }}
{{ dict['key'] }}
{{ list[0] }}
```

**条件**：
```jinja2
{% if condition %}
  content
{% elif other %}
  other content
{% else %}
  default
{% endif %}
```

**循环**：
```jinja2
{% for item in items %}
  {{ item }}
{% endfor %}
```

**过滤器**：
```jinja2
{{ value | default('N/A') }}
{{ value | upper }}
{{ value | length }}
{{ value | join(', ') }}
```

### C. 示例配置对比

#### 当前语法（环境变量）
```yaml
backend:
  uri: "${AGIO_MONGO_URI:mongodb://localhost:27017}"
```

#### Jinja2 语法
```yaml
backend:
  uri: "{{ env.AGIO_MONGO_URI | default('mongodb://localhost:27017') }}"
```

#### 当前语法（Workflow）
```yaml
input: "Analysis: {analyze.output}, Topic: {input}"
```

#### Jinja2 语法
```yaml
input: |
  {% if nodes.analyze.output %}
  Analysis: {{ nodes.analyze.output }}
  {% endif %}
  Topic: {{ input }}
```

#### 当前语法（Agent Prompt）
```yaml
system_prompt: "You are a helpful assistant."
```

#### Jinja2 语法
```yaml
system_prompt: |
  You are {{ agent.name }}, a helpful assistant.
  
  {% if agent.tools %}
  Available tools:
  {% for tool in agent.tools %}
  - {{ tool.name }}: {{ tool.description }}
  {% endfor %}
  {% endif %}
```

---

**报告生成时间**：2025-01-XX  
**调研范围**：整个代码库  
**涉及文件数**：20+  
**代码行数**：1000+

