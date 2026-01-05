# Agio Frontend

现代化 React 仪表盘，面向 Agio Agent 框架的可观测性与控制面。

## ✨ 特性

- 📊 Dashboard：系统指标总览、运行态状态
- 🤖 Agents：列表、状态与跳转测试
- 💬 Chat：SSE 流式对话，支持 session 继续 / 分叉
- 📈 Metrics & LLM Logs：模型调用日志、统计与流式订阅
- ⚡ 技术栈：Vite + React 18 + TypeScript + TailwindCSS + TanStack Query

## 🚀 快速开始

```bash
cd agio-frontend
npm install
npm run dev
# 浏览器访问 http://localhost:3000
```

生产构建：

```bash
npm run build
```

## ⚙️ 后端联调

- 后端默认前缀：`/agio`
- 前端 API 基址：`/agio`（见 `src/services/api.ts`）
- 开发代理：在 `vite.config.ts` 将 `/agio` 转发到 `http://localhost:8900`

确保后端启动且 `AGIO_CONFIG_DIR=./configs` 已加载所需 Agent。  

## 🗂️ 目录速览

```
agio-frontend/
├── src/
│   ├── components/      # 布局与通用组件
│   ├── pages/           # Dashboard/Chat/Config/Sessions/Traces
│   ├── services/        # API 封装（axios，基址 /agio）
│   ├── hooks/           # 数据/状态 hooks
│   ├── stores/          # Zustand 全局状态
│   ├── utils/           # SSE 解析等工具
│   ├── App.tsx          # 路由入口
│   └── main.tsx         # 应用挂载
└── vite.config.ts       # 开发代理与构建配置
```

## 🔌 主要功能入口

- Dashboard：系统概览与关键指标
- Chat：流式对话，支持 sessionId 续聊与 fork
- Config：读取/编辑配置（通过后端 ConfigSystem）
- Sessions：会话/运行历史与步骤明细
- Traces：LLM 调用日志与统计

## 🧪 开发与校验

```bash
npm run dev      # 本地调试
npm run build    # 类型检查 + 产物构建
npm run test     # 运行前端内置单测
```

## 🚀 部署参考

```dockerfile
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

Nginx 需转发 `/agio` 到后端 `http://backend:8900`，其余路径静态托管 `dist/`。

## 📄 许可证

MIT
