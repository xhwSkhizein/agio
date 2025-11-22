#!/bin/bash

# Agio 服务启动脚本 (使用 uv)
# 同时启动 FastAPI 后端和 React 前端

set -e

echo "🚀 Starting Agio Services..."
echo ""

# 检查 uv
if ! command -v uv &> /dev/null; then
    echo "❌ uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
fi

echo "📦 Setting up backend environment with uv..."
# 使用 uv 同步依赖
uv sync

echo "📦 Checking frontend dependencies..."
if [ ! -d "agio-frontend/node_modules" ]; then
    echo "⚠️  Installing frontend dependencies..."
    cd agio-frontend
    npm install
    cd ..
fi

echo ""
echo "✅ All dependencies installed"
echo ""

# 创建日志目录
mkdir -p logs

# 设置默认环境变量以避免组件加载失败
export TICKETING_API_URL="http://mock-ticketing-api.com"
export TICKETING_API_KEY="mock-key"
export SMTP_SERVER="smtp.mock.com"
export SMTP_USERNAME="mock-user"
export SMTP_PASSWORD="mock-pass"
export REPO_PATH="./"

# 启动后端 (使用 uv run)
echo "🔧 Starting FastAPI backend on port 8900..."
uv run uvicorn agio.api.app:app --host 0.0.0.0 --port 8900 > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# 等待后端启动
echo "⏳ Waiting for backend to start..."
sleep 5

# 检查后端是否启动成功
if ! curl -s http://localhost:8900/api/health > /dev/null; then
    echo "❌ Backend failed to start. Check logs/backend.log"
    echo ""
    echo "Last 20 lines of backend.log:"
    tail -n 20 logs/backend.log
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo "✅ Backend started successfully"
echo ""

# 启动前端
echo "🎨 Starting React frontend on port 3000..."
cd agio-frontend
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo "   Frontend PID: $FRONTEND_PID"

echo ""
echo "✅ All services started!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📱 Frontend:  http://localhost:3000"
echo "🔌 API:       http://localhost:8900"
echo "📖 API Docs:  http://localhost:8900/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Logs:"
echo "   Backend:  logs/backend.log"
echo "   Frontend: logs/frontend.log"
echo ""
echo "🛑 To stop services:"
echo "   kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "💡 Or press Ctrl+C to stop all services"
echo ""

# 保存 PIDs 到文件
echo "$BACKEND_PID" > logs/backend.pid
echo "$FRONTEND_PID" > logs/frontend.pid

# 等待用户中断
trap "echo ''; echo '🛑 Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; echo '✅ Services stopped'; exit 0" INT TERM

# 保持脚本运行
wait
