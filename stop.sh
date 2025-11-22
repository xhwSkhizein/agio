#!/bin/bash

# Agio 服务停止脚本

echo "🛑 Stopping Agio Services..."

# 读取 PIDs
if [ -f "logs/backend.pid" ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    kill $BACKEND_PID 2>/dev/null && echo "✅ Backend stopped (PID: $BACKEND_PID)" || echo "⚠️  Backend not running"
    rm logs/backend.pid
fi

if [ -f "logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    kill $FRONTEND_PID 2>/dev/null && echo "✅ Frontend stopped (PID: $FRONTEND_PID)" || echo "⚠️  Frontend not running"
    rm logs/frontend.pid
fi

# 清理可能残留的进程
pkill -f "uvicorn agio.api.app:app" 2>/dev/null
pkill -f "vite" 2>/dev/null

echo ""
echo "✅ All services stopped"
