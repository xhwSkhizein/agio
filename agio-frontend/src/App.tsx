import { Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import ConfigList from './pages/ConfigList'
import ConfigEditor from './pages/ConfigEditor'
import Chat from './pages/Chat'
import Knowledge from './pages/Knowledge'
import Memory from './pages/Memory'
import Sessions from './pages/Sessions'
import Metrics from './pages/Metrics'
import Traces from './pages/Traces'
import TraceDetail from './pages/TraceDetail'

function App() {
  return (
    <>
      <Toaster position="top-right" />
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/chat/:sessionId" element={<Chat />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/memory" element={<Memory />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/metrics" element={<Metrics />} />
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
