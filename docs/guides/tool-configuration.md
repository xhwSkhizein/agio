# 工具配置指南

本文档说明 Agio 工具系统的配置方式，包括 YAML 配置、环境变量和编程式配置。

## 目录

- [配置方式概述](#配置方式概述)
- [YAML 配置](#yaml-配置)
- [环境变量配置](#环境变量配置)
- [编程式配置](#编程式配置)
- [配置优先级](#配置优先级)
- [工具配置参考](#工具配置参考)

## 配置方式概述

Agio 工具系统支持三种配置方式，按优先级从高到低：

1. **构造函数参数**（最高优先级）- 通过 YAML 配置的 `params` 或编程式传参
2. **环境变量**（中等优先级）- 支持 `AGIO_TOOL_*` 前缀的环境变量
3. **默认值**（最低优先级）- 配置类的默认值

## YAML 配置

### 基本配置格式

在 `configs/tools/` 目录下创建 YAML 配置文件：

```yaml
type: tool
name: file_read
tool_name: file_read
params:
  max_output_size_mb: 10.0
  timeout_seconds: 30
enabled: true
tags:
  - file
  - read
```

### 配置参数说明

- `type`: 固定为 `tool`
- `name`: 工具实例名称（在配置系统中唯一）
- `tool_name`: 内置工具名称（如 `file_read`, `web_fetch` 等）
- `params`: 工具配置参数（对应配置类的字段）
- `dependencies`: 工具依赖（如 `llm_model`, `citation_source_store`）
- `enabled`: 是否启用
- `tags`: 标签列表

### 示例：FileReadTool

```yaml
type: tool
name: file_read
tool_name: file_read
params:
  max_output_size_mb: 10.0
  max_image_size_mb: 5.0
  max_image_width: 1920
  max_image_height: 1080
  timeout_seconds: 30
enabled: true
```

### 示例：WebFetchTool（带依赖）

```yaml
type: tool
name: web_fetch
tool_name: web_fetch
dependencies:
  llm_model: deepseek
  citation_source_store: citation_store_mongodb
params:
  timeout_seconds: 30
  max_content_length: 4096
  headless: true
  max_retries: 1
enabled: true
```

## 环境变量配置

所有工具配置都支持通过环境变量设置，使用 `AGIO_TOOL_*` 前缀。

### 环境变量命名规则

格式：`AGIO_{TOOL_NAME}_{PARAM_NAME}`

- 工具名称使用大写，下划线分隔
- 参数名称使用大写，下划线分隔
- 布尔值使用 `true`/`false` 字符串

### 示例

```bash
# FileReadTool 配置
export AGIO_FILE_READ_MAX_SIZE_MB=15.0
export AGIO_FILE_READ_TIMEOUT=60

# WebFetchTool 配置
export AGIO_WEB_FETCH_HEADLESS=false
export AGIO_WEB_FETCH_TIMEOUT=60
export AGIO_WEB_FETCH_MAX_RETRIES=3

# GrepTool 配置
export AGIO_GREP_MAX_RESULTS=2000
export AGIO_GREP_TIMEOUT=45
```

### 环境变量列表

#### FileReadTool

- `AGIO_FILE_READ_MAX_SIZE_MB`: 最大输出大小（MB），默认 `10.0`
- `AGIO_FILE_READ_MAX_IMAGE_SIZE_MB`: 最大图片大小（MB），默认 `5.0`
- `AGIO_FILE_READ_MAX_IMAGE_WIDTH`: 最大图片宽度，默认 `1920`
- `AGIO_FILE_READ_MAX_IMAGE_HEIGHT`: 最大图片高度，默认 `1080`
- `AGIO_FILE_READ_TIMEOUT`: 超时时间（秒），默认 `30`

#### FileWriteTool

- `AGIO_FILE_WRITE_TIMEOUT`: 超时时间（秒），默认 `30`
- `AGIO_FILE_WRITE_MAX_SIZE_MB`: 最大文件大小（MB），默认 `10.0`

#### FileEditTool

- `AGIO_FILE_EDIT_TIMEOUT`: 超时时间（秒），默认 `60`

#### GrepTool

- `AGIO_GREP_TIMEOUT`: 超时时间（秒），默认 `30`
- `AGIO_GREP_MAX_RESULTS`: 最大结果数，默认 `1000`

#### GlobTool

- `AGIO_GLOB_TIMEOUT`: 超时时间（秒），默认 `30`
- `AGIO_GLOB_MAX_RESULTS`: 最大结果数，默认 `1000`
- `AGIO_GLOB_MAX_SEARCH_DEPTH`: 最大搜索深度，默认 `10`
- `AGIO_GLOB_MAX_PATH_LENGTH`: 最大路径长度，默认 `500`
- `AGIO_GLOB_MAX_PATTERN_LENGTH`: 最大模式长度，默认 `200`

#### LSTool

- `AGIO_LS_TIMEOUT`: 超时时间（秒），默认 `30`
- `AGIO_LS_MAX_FILES`: 最大文件数，默认 `1000`
- `AGIO_LS_MAX_LINES`: 最大行数，默认 `100`

#### BashTool

- `AGIO_BASH_TIMEOUT`: 超时时间（秒），默认 `300`
- `AGIO_BASH_MAX_OUTPUT_SIZE_KB`: 最大输出大小（KB），默认 `1024`
- `AGIO_BASH_MAX_OUTPUT_LENGTH`: 最大输出长度（字符），默认 `30000`

#### WebSearchTool

- `AGIO_WEB_SEARCH_TIMEOUT`: 超时时间（秒），默认 `30`
- `AGIO_WEB_SEARCH_MAX_RESULTS`: 最大结果数，默认 `10`

#### WebFetchTool

- `AGIO_WEB_FETCH_TIMEOUT`: 超时时间（秒），默认 `30`
- `AGIO_WEB_FETCH_MAX_CONTENT_LENGTH`: 最大内容长度，默认 `4096`
- `AGIO_WEB_FETCH_MAX_RETRIES`: 最大重试次数，默认 `1`
- `AGIO_WEB_FETCH_WAIT_STRATEGY`: 等待策略，默认 `domcontentloaded`
- `AGIO_WEB_FETCH_MAX_SIZE_MB`: 最大大小（MB），默认 `10.0`
- `AGIO_WEB_FETCH_HEADLESS`: 无头模式，默认 `true`
- `AGIO_WEB_FETCH_SAVE_LOGIN_STATE`: 保存登录状态，默认 `false`
- `AGIO_WEB_FETCH_USER_DATA_DIR`: 用户数据目录，默认 `chrome_user_data`
- `AGIO_WEB_FETCH_BROWSER_LAUNCH_TIMEOUT`: 浏览器启动超时（秒），默认 `30`

## 编程式配置

### 方式一：使用配置对象

```python
from agio.tools.builtin.file_read_tool import FileReadTool
from agio.tools.builtin.config import FileReadConfig

# 创建配置对象
config = FileReadConfig(
    max_output_size_mb=5.0,
    timeout_seconds=60
)

# 使用配置对象创建工具
tool = FileReadTool(config=config)
```

### 方式二：使用关键字参数

```python
from agio.tools.builtin.file_read_tool import FileReadTool

# 直接传递关键字参数
tool = FileReadTool(
    max_output_size_mb=5.0,
    timeout_seconds=60
)
```

### 方式三：使用默认配置

```python
from agio.tools.builtin.file_read_tool import FileReadTool

# 使用默认配置
tool = FileReadTool()
```

### 配置覆盖

关键字参数可以覆盖配置对象中的值：

```python
from agio.tools.builtin.config import FileReadConfig

config = FileReadConfig(max_output_size_mb=5.0)
tool = FileReadTool(config=config, max_output_size_mb=10.0)
# max_output_size_mb 最终为 10.0（kwargs 优先级更高）
```

### 带依赖的工具

```python
from agio.tools.builtin.web_fetch_tool import WebFetchTool
from agio.tools.builtin.config import WebFetchConfig

config = WebFetchConfig(headless=False)
tool = WebFetchTool(
    config=config,
    citation_source_store=my_citation_store,
    llm_model=my_llm_model
)
```

### project_root 参数

某些工具（如 `GrepTool`, `GlobTool`, `LSTool`）支持 `project_root` 参数：

```python
from pathlib import Path
from agio.tools.builtin.grep_tool import GrepTool

tool = GrepTool(project_root=Path("/path/to/project"))
```

## 配置优先级

配置优先级从高到低：

1. **构造函数关键字参数**（`tool = FileReadTool(max_output_size_mb=20.0)`）
2. **YAML 配置的 params**（通过 `ToolBuilder` 构建时）
3. **环境变量**（`AGIO_FILE_READ_MAX_SIZE_MB=15.0`）
4. **配置对象中的值**（如果使用 `config=` 参数）
5. **默认值**（配置类字段的默认值）

### 优先级示例

```python
# 环境变量设置
# export AGIO_FILE_READ_MAX_SIZE_MB=15.0

# YAML 配置
# params:
#   max_output_size_mb: 10.0

# 编程式配置
tool = FileReadTool(max_output_size_mb=20.0)

# 最终值：20.0（关键字参数优先级最高）
```

## 工具配置参考

### FileReadConfig

```python
@dataclass
class FileReadConfig:
    max_output_size_mb: float = 10.0
    max_image_size_mb: float = 5.0
    max_image_width: int = 1920
    max_image_height: int = 1080
    timeout_seconds: int = 30
```

### FileWriteConfig

```python
@dataclass
class FileWriteConfig:
    timeout_seconds: int = 30
    max_file_size_mb: float = 10.0
```

### FileEditConfig

```python
@dataclass
class FileEditConfig:
    timeout_seconds: int = 60
```

### GrepConfig

```python
@dataclass
class GrepConfig:
    timeout_seconds: int = 30
    max_results: int = 1000
```

### GlobConfig

```python
@dataclass
class GlobConfig:
    timeout_seconds: int = 30
    max_results: int = 1000
    max_search_depth: int = 10
    max_path_length: int = 500
    max_pattern_length: int = 200
```

### LSConfig

```python
@dataclass
class LSConfig:
    timeout_seconds: int = 30
    max_files: int = 1000
    max_lines: int = 100
```

### BashConfig

```python
@dataclass
class BashConfig:
    timeout_seconds: int = 300
    max_output_size_kb: int = 1024
    max_output_length: int = 30000
```

### WebSearchConfig

```python
@dataclass
class WebSearchConfig:
    timeout_seconds: int = 30
    max_results: int = 10
```

### WebFetchConfig

```python
@dataclass
class WebFetchConfig:
    timeout_seconds: int = 30
    max_content_length: int = 4096
    max_retries: int = 1
    wait_strategy: str = "domcontentloaded"
    max_size_mb: float = 10.0
    headless: bool = True
    save_login_state: bool = False
    user_data_dir: str = "chrome_user_data"
    browser_launch_timeout: int = 30
```

## 最佳实践

1. **开发环境**：使用 YAML 配置文件，便于版本控制和团队协作
2. **生产环境**：使用环境变量，便于不同环境使用不同配置
3. **测试环境**：使用编程式配置，便于测试用例中精确控制
4. **敏感信息**：使用环境变量存储 API keys 等敏感信息

## 迁移指南

### 从旧配置系统迁移

如果你之前使用 `AppSettings`，现在需要：

1. **移除 `AppSettings` 依赖**：所有工具已不再需要 `AppSettings`
2. **使用配置对象**：通过 `config=` 参数传递配置对象
3. **更新 YAML 配置**：确保 `params` 中的字段名与配置类字段一致
4. **设置环境变量**：使用 `AGIO_TOOL_*` 前缀的环境变量

### 示例迁移

**旧代码**：
```python
from agio.tools.builtin.adapter import AppSettings
tool = FileReadTool(settings=AppSettings())
```

**新代码**：
```python
from agio.tools.builtin.file_read_tool import FileReadTool
tool = FileReadTool()  # 使用默认配置
# 或
tool = FileReadTool(max_output_size_mb=5.0)  # 自定义配置
```

## 常见问题

### Q: 如何查看工具的默认配置？

A: 查看 `agio/providers/tools/builtin/config.py` 中对应配置类的默认值。

### Q: 环境变量不生效？

A: 确保环境变量名称正确，使用 `AGIO_TOOL_*` 前缀，并且工具在读取环境变量之前创建。

### Q: YAML 配置不生效？

A: 确保 `params` 中的字段名与配置类字段名完全一致（区分大小写）。

### Q: 如何为自定义工具添加配置支持？

A: 创建配置数据类，继承自 `dataclass`，并在 `ToolBuilder._build_config_object` 中添加映射。

## 相关文档

- [配置系统文档](./CONFIG_SYSTEM_V2.md)
- [工具系统架构](./ARCHITECTURE.md#工具系统)

