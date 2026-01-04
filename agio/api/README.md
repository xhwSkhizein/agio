# Agio API 集成指南

本指南说明如何在你的 FastAPI 应用中集成 Agio 的 API 和前端控制面板。

## 快速集成

### 方式 1：完整集成（API + 前端）

最简单的方式是使用 `create_app_with_frontend`，它会自动配置 API 和前端：

```python
from agio.api import create_app_with_frontend

app = create_app_with_frontend(
    api_prefix="/agio",      # API 路径前缀
    frontend_path="/",        # 前端挂载路径
    enable_frontend=True,     # 是否启用前端
)
```

访问：
- 前端控制面板：`http://localhost:8000/`
- API 文档：`http://localhost:8000/agio/docs`
- API 端点：`http://localhost:8000/agio/...`

### 方式 2：仅集成 API

如果你只需要 API 功能，不需要前端：

```python
from fastapi import FastAPI
from agio.api import create_router

app = FastAPI()

# 挂载 Agio API
app.include_router(create_router(prefix="/agio"))
```

### 方式 3：自定义集成

如果你需要更多控制，可以分别挂载 API 和前端：

```python
from fastapi import FastAPI
from agio.api import create_router, mount_frontend

app = FastAPI(title="My Application")

# 1. 先挂载 API 路由（重要：必须在挂载前端之前）
app.include_router(create_router(prefix="/agio"))

# 2. 然后挂载前端（SPA 路由会注册在最后）
mount_frontend(app, path="/", api_prefix="/agio")

# 3. 你的其他路由
@app.get("/api/custom")
async def custom():
    return {"message": "Custom endpoint"}
```

**重要提示**：
- API 路由必须在挂载前端之前注册，这样 SPA 的 catch-all 路由不会拦截 API 请求
- 前端路径和 API 路径不能重叠

### 方式 4：挂载到子路径

如果你想把 Agio 挂载到子路径（例如 `/admin/agio`）：

```python
from fastapi import FastAPI
from agio.api import create_router, mount_frontend

app = FastAPI()

# API 挂载到 /admin/agio
app.include_router(create_router(prefix="/admin/agio"))

# 前端挂载到 /admin/agio/panel
mount_frontend(app, path="/admin/agio/panel", api_prefix="/admin/agio")
```

访问：
- 前端：`http://localhost:8000/admin/agio/panel`
- API：`http://localhost:8000/admin/agio/...`

## 环境变量配置

Agio 使用环境变量进行配置：

```bash
# 配置目录（包含 Agent、Tool、Workflow 等配置）
export AGIO_CONFIG_DIR=./configs

# LLM API Keys
export AGIO_OPENAI_API_KEY=sk-...
export AGIO_ANTHROPIC_API_KEY=sk-...
export AGIO_DEEPSEEK_API_KEY=sk-...

# 存储配置（可选）
export AGIO_MONGO_URI=mongodb://localhost:27017
```

## 前端配置

前端会自动使用你指定的 `api_prefix` 作为 API 基础路径。例如：

- 如果 `api_prefix="/agio"`，前端会请求 `/agio/agents`、`/agio/sessions` 等
- 如果 `api_prefix="/admin/agio"`，前端会请求 `/admin/agio/agents` 等

## 故障排除

### 前端无法加载

1. 确保前端已构建并包含在包中：
   ```bash
   # 在开发时，确保前端已构建
   cd agio-frontend
   npm run build
   ```

2. 检查前端文件是否存在：
   ```python
   from agio.api import get_frontend_dist_path
   print(get_frontend_dist_path())  # 应该返回路径，而不是 None
   ```

### API 路由被前端拦截

确保 API 路由在挂载前端之前注册：

```python
# ✅ 正确顺序
app.include_router(create_router(prefix="/agio"))  # 先注册 API
mount_frontend(app, path="/", api_prefix="/agio")  # 后挂载前端

# ❌ 错误顺序
mount_frontend(app, path="/", api_prefix="/agio")  # 前端会拦截所有请求
app.include_router(create_router(prefix="/agio"))  # API 无法访问
```

### 静态资源 404

确保前端构建产物包含 `assets` 目录，并且构建脚本已正确复制文件到包中。