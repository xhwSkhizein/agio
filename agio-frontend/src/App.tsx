import { Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import ConfigList from './pages/ConfigList'
import ConfigEditor from './pages/ConfigEditor'
import Chat from './pages/Chat'
import ChatV2 from './pages/ChatV2'
import Sessions from './pages/Sessions'
import Traces from './pages/Traces'
import TraceDetail from './pages/TraceDetail'

function App() {
  return (
    <>
      <Toaster position="top-right" />
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/chat" element={<ChatV2 />} />
          <Route path="/chat/:sessionId" element={<ChatV2 />} />
          <Route path="/chat-v1" element={<Chat />} />
          <Route path="/chat-v1/:sessionId" element={<Chat />} />
          <Route path="/chat-v2" element={<ChatV2 />} />
          <Route path="/chat-v2/:sessionId" element={<ChatV2 />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/traces" element={<Traces />} />
          <Route path="/traces/:traceId" element={<TraceDetail />} />
          <Route path="/config" element={<ConfigList />} />
          <Route path="/config/:type/:name" element={<ConfigEditor />} />
        </Routes>
      </Layout>
    </>
  )
}

export default App
