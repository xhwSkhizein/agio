# Agio FastAPI Backend

Agio 的控制平面 API，基于 FastAPI + SSE，前缀默认 `/agio`。启动时会通过 `ConfigSystem` 读取 `configs/` 下的组件并构建 Agent/Workflow，可直接被前端仪表盘使用。

## ✨ 能力概览

- 🔌 **配置驱动**：热重载 `configs/`，拓扑排序构建组件
- 💬 **聊天与流式事件**：SSE 方式返回 `StepEvent`，兼容非流式
- 🧠 **多组件管理**：Agent / Workflow / Tool / Memory / Knowledge / Repository
- 📈 **观测性**：LLM 调用日志与 Metrics 查询
- 🩺 **健康检查**：就绪与存活探针

## ⚡ 快速开始

```bash
python main.py               # 监听 0.0.0.0:8900
# 或使用 uvicorn
uvicorn agio.api.app:app --host 0.0.0.0 --port 8900 --reload
```

关键环境变量：

```bash
AGIO_CONFIG_DIR=./configs
AGIO_OPENAI_API_KEY=sk-...
AGIO_ANTHROPIC_API_KEY=sk-...
AGIO_DEEPSEEK_API_KEY=sk-...
AGIO_MONGO_URI=mongodb://localhost:27017   # 如需持久化
```

文档入口（默认前缀 `/agio`）：

- OpenAPI: `http://localhost:8900/agio/docs`
- Redoc: `http://localhost:8900/agio/redoc`

## 🗺️ 路由速览（前缀 `/agio`）

- `GET /health` / `GET /health/ready`：健康与就绪
- `GET /config`、`GET/PUT/DELETE /config/{type}/{name}`、`POST /config/reload`
- `GET /agents`、`GET /agents/{name}`、`GET /agents/{name}/status`
- `POST /chat/{agent_name}`：`stream=true` SSE，`stream=false` 普通响应
- `GET /sessions`、`/sessions/summary`、`/sessions/{id}`、`POST /sessions/{id}/fork`、`GET /sessions/{id}/steps`、`POST /sessions/{id}/resume`
- `GET /memory`、`GET /memory/{name}`、`POST /memory/{name}/search`
- `GET /knowledge`、`GET /knowledge/{name}`、`POST /knowledge/{name}/search`
- `GET /metrics/system`、`GET /metrics/agents/{agent_id}`
- `GET /llm/logs`、`GET /llm/logs/{id}`、`GET /llm/logs/stream` (SSE) 、`GET /llm/stats`
- `GET /runnables`、`GET /runnables/{id}`、`POST /runnables/{id}/run` (SSE)
- `GET /workflows`、`GET /workflows/{id}`

## 💬 示例：SSE Chat

```python
import httpx, json

with httpx.stream(
    "POST",
    "http://localhost:8900/agio/chat/code_assistant",
    json={"message": "Hello", "stream": True},
    headers={"Accept": "text/event-stream"},
) as resp:
    for line in resp.iter_lines():
        if line.startswith("data:"):
            print(json.loads(line[5:]))
```

## 🧪 测试

```bash
pytest tests/workflow -q
pytest tests/config -q
```

## 🚀 部署

```bash
uvicorn agio.api.app:app --host 0.0.0.0 --port 8900 --workers 4
```

容器示例：参考根目录 `start.sh` / `stop.sh` 或自行编写 Dockerfile。
