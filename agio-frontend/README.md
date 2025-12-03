# Agio Frontend

Modern React-based observability platform for the Agio Agent Framework.

## Features

- 📊 **Dashboard** - System overview with key metrics
- 🤖 **Agent Management** - List and manage agents
- 💬 **Real-time Chat** - SSE streaming chat interface
- 🎨 **Modern UI** - TailwindCSS + Dark mode support
- ⚡ **Fast** - Vite + React 18
- 🔄 **State Management** - TanStack Query for server state

## Quick Start

### Install Dependencies

```bash
cd agio-frontend
npm install
```

### Run Development Server

```bash
npm run dev
```

The app will be available at http://localhost:3000

### Build for Production

```bash
npm run build
```

## Project Structure

```
agio-frontend/
├── src/
│   ├── components/      # Reusable components
│   │   └── Layout.tsx   # Main layout with navigation
│   ├── pages/           # Page components
│   │   ├── Dashboard.tsx
│   │   ├── AgentList.tsx
│   │   └── Chat.tsx
│   ├── services/        # API services
│   │   └── api.ts
│   ├── hooks/           # Custom hooks
│   ├── stores/          # Zustand stores
│   ├── types/           # TypeScript types
│   ├── utils/           # Utility functions
│   ├── App.tsx          # Main app component
│   ├── main.tsx         # Entry point
│   └── index.css        # Global styles
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

## Pages

### Dashboard
- System overview
- Key metrics (agents, runs, checkpoints, tokens)
- Recent activity

### Agent List
- View all agents
- Filter by tags
- Quick access to chat

### Chat
- Real-time streaming chat with agents
- SSE-based message streaming
- Message history

## API Integration

The frontend connects to the Agio API backend at `http://localhost:8900/api`.

API proxy is configured in `vite.config.ts`:

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8900',
      changeOrigin: true,
    },
  },
}
```

## Technologies

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **TailwindCSS** - Styling
- **React Router** - Routing
- **TanStack Query** - Server state management
- **Axios** - HTTP client

## Development

### Hot Reload

Vite provides instant hot module replacement (HMR) for a smooth development experience.

### Type Checking

```bash
npm run build  # Runs tsc for type checking
```

## Deployment

### Docker

```dockerfile
FROM node:18-alpine as build

WORKDIR /app
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Nginx Configuration

```nginx
server {
  listen 80;
  
  location / {
    root /usr/share/nginx/html;
    try_files $uri $uri/ /index.html;
  }
  
  location /api {
    proxy_pass http://backend:8900;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }
}
```

## Next Steps

- Add authentication
- Implement run detail page
- Add checkpoint visualization
- Implement config editor
- Add metrics charts

## License

MIT
