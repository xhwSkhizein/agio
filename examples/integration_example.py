"""
示例：如何在现有 FastAPI 应用中集成 Agio

这个文件展示了多种集成 Agio 的方式。
"""

# ============================================================================
# 方式 1：完整集成（推荐）
# ============================================================================
# 最简单的方式，自动配置 API 和前端

from agio.api import create_app_with_frontend

app = create_app_with_frontend(
    api_prefix="/agio",
    frontend_path="/",
    enable_frontend=True,
)

# 访问：
# - 前端控制面板：http://localhost:8000/
# - API 文档：http://localhost:8000/agio/docs


# ============================================================================
# 方式 2：仅集成 API
# ============================================================================
# 如果你只需要 API 功能，不需要前端

from fastapi import FastAPI  # noqa: E402
from agio.api import create_router  # noqa: E402

app = FastAPI(title="My Application")

# 挂载 Agio API
app.include_router(create_router(prefix="/agio"))

# 你的其他路由
@app.get("/")
async def root():
    return {"message": "Hello from my app"}

@app.get("/api/custom")
async def custom():
    return {"data": "custom endpoint"}


# ============================================================================
# 方式 3：自定义集成
# ============================================================================
# 如果你需要更多控制，可以分别挂载 API 和前端

from fastapi import FastAPI  # noqa: E402
from agio.api import create_router, mount_frontend  # noqa: E402

app = FastAPI(title="My Application")

# 1. 先挂载 API 路由（重要：必须在挂载前端之前）
app.include_router(create_router(prefix="/agio"))

# 2. 然后挂载前端（SPA 路由会注册在最后）
mount_frontend(app, path="/", api_prefix="/agio")

# 3. 你的其他路由
@app.get("/api/custom2")
async def custom2():
    return {"message": "Custom endpoint"}


# ============================================================================
# 方式 4：挂载到子路径
# ============================================================================
# 如果你想把 Agio 挂载到子路径（例如 /admin/agio）

from fastapi import FastAPI  # noqa: E402
from agio.api import create_router, mount_frontend  # noqa: E402

app = FastAPI()

# API 挂载到 /admin/agio
app.include_router(create_router(prefix="/admin/agio"))

# 前端挂载到 /admin/agio/panel
mount_frontend(app, path="/admin/agio/panel", api_prefix="/admin/agio")

# 访问：
# - 前端：http://localhost:8000/admin/agio/panel
# - API：http://localhost:8000/admin/agio/...


# ============================================================================
# 方式 5：仅使用 Agio 核心功能（不启动 API）
# ============================================================================
# 如果你只需要使用 Agio 的 Agent 功能，不需要 API 服务器

import asyncio  # noqa: E402
from agio import get_config_system  # noqa: E402


async def main():
    # 初始化配置系统
    config_system = get_config_system()
    await config_system.load_from_directory("./configs")
    await config_system.build_all()
    
    # 获取 Agent
    agent = await config_system.get_agent("my-agent")
    
    # 运行 Agent
    result = await agent.run("Hello, Agio!")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())


# ============================================================================
# 运行示例
# ============================================================================
# 使用 uvicorn 运行：
#
#   uvicorn examples.integration_example:app --reload
#
# 或者使用 agio-server 命令：
#
#   agio-server --host 0.0.0.0 --port 8000
