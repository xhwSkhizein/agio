"""
Simple script to run the FastAPI server.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "agio.api.app:app",
        host="0.0.0.0",
        port=8900,
        reload=True,
        log_level="info",
        # Concurrency settings
        limit_concurrency=100,  # Allow more concurrent connections
        limit_max_requests=None,  # No limit on requests per worker
        timeout_keep_alive=30,  # Standard keep-alive
    )
