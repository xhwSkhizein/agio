# Agio FastAPI Backend

## Overview

The Agio FastAPI backend provides a complete RESTful API with SSE streaming support for real-time agent interactions. Features include:

- 🚀 **RESTful API** - Complete CRUD operations
- 📡 **SSE Streaming** - Real-time chat with agents
- ⏸️ **Execution Control** - Pause/Resume/Cancel runs
- 💾 **Checkpoint Management** - Create, restore, and fork checkpoints
- 📊 **Auto Documentation** - OpenAPI/Swagger UI

## Quick Start

### 1. Install Dependencies

```bash
pip install fastapi uvicorn sse-starlette
```

### 2. Run the Server

```bash
# Development mode with auto-reload
python main.py

# Or with uvicorn directly
uvicorn agio.api.app:app --reload
```

### 3. Access the API

- **API Base**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Health Check

```http
GET /api/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-01-01T00:00:00"
}
```

### Agents

#### List Agents
```http
GET /api/agents?limit=20&offset=0&tag=production
```

#### Get Agent
```http
GET /api/agents/{agent_id}
```

#### Delete Agent
```http
DELETE /api/agents/{agent_id}
```

### Chat

#### Stream Chat (SSE)
```http
POST /api/chat
Content-Type: application/json

{
  "agent_id": "customer_support",
  "message": "Hello!",
  "stream": true
}
```

Response (SSE):
```
event: run_started
data: {"run_id": "run_123"}

event: content_delta
data: {"content": "Hello"}

event: run_completed
data: {"metrics": {...}}
```

#### Non-Streaming Chat
```http
POST /api/chat
Content-Type: application/json

{
  "agent_id": "customer_support",
  "message": "Hello!",
  "stream": false
}
```

### Runs

#### Pause Run
```http
POST /api/runs/{run_id}/pause
```

#### Resume Run
```http
POST /api/runs/{run_id}/resume
```

#### Cancel Run
```http
POST /api/runs/{run_id}/cancel
```

### Checkpoints

#### List Checkpoints
```http
GET /api/checkpoints/runs/{run_id}/checkpoints
```

#### Get Checkpoint
```http
GET /api/checkpoints/{checkpoint_id}
```

#### Restore from Checkpoint
```http
POST /api/checkpoints/{checkpoint_id}/restore
Content-Type: application/json

{
  "create_new_run": true,
  "modifications": {
    "modified_query": "New query"
  }
}
```

#### Fork Checkpoint
```http
POST /api/checkpoints/{checkpoint_id}/fork
Content-Type: application/json

{
  "modifications": {
    "system_prompt": "New prompt"
  }
}
```

## Client Examples

### Python Client

```python
import httpx

# List agents
response = httpx.get("http://localhost:8000/api/agents")
agents = response.json()

# Chat (non-streaming)
response = httpx.post(
    "http://localhost:8000/api/chat",
    json={
        "agent_id": "assistant",
        "message": "Hello!",
        "stream": False
    }
)
result = response.json()
print(result["response"])
```

### SSE Streaming Client

```python
import httpx

with httpx.stream(
    "POST",
    "http://localhost:8000/api/chat",
    json={
        "agent_id": "assistant",
        "message": "Tell me a story",
        "stream": True
    },
    headers={"Accept": "text/event-stream"}
) as response:
    for line in response.iter_lines():
        if line.startswith("data:"):
            data = line[5:].strip()
            print(data)
```

### JavaScript/TypeScript Client

```typescript
const eventSource = new EventSource('/api/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    agent_id: 'assistant',
    message: 'Hello',
    stream: true
  })
});

eventSource.addEventListener('content_delta', (event) => {
  const data = JSON.parse(event.data);
  console.log(data.content);
});

eventSource.addEventListener('run_completed', (event) => {
  console.log('Completed');
  eventSource.close();
});
```

## Testing

Run the API tests:

```bash
pytest tests/test_api.py -v
```

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "agio.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production

```bash
# With multiple workers
uvicorn agio.api.app:app --host 0.0.0.0 --port 8000 --workers 4
```

## Configuration

The API uses environment variables for configuration. Set them in `.env` file or environment:

```bash
# .env
AGIO_OPENAI_API_KEY=sk-...
AGIO_LOG_LEVEL=INFO
AGIO_MONGO_URI=mongodb://localhost:27017
```

## Next Steps

- Check out `agio/api/DESIGN.md` for detailed design documentation
- Explore the React frontend for a complete UI
- Learn about authentication and authorization
