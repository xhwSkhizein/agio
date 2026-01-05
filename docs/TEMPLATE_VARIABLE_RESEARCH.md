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
- ✅ 语法与 Agent 模板统一（Jinja2）

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


### 2.2 Agent Prompt 阶段

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


#### 3.2.2 Agent Prompt（✅ 非常适合）

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


#### 4.2.2 Agent Prompt 阶段

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


2. **Agent 运行时渲染**（**重要**：不在 Builder 中渲染）：
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

---

## 附录

### A. 当前变量替换实现位置汇总

| 位置 | 文件 | 方法 | 语法 | 变量来源 |
|------|------|------|------|----------|
| 配置加载 | `agio/config/loader.py` | `_resolve_env_vars()` | `{{ env.VAR | default() }}` | 环境变量 |
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

