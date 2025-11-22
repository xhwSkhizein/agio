import { Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AgentList from './pages/AgentList'
import ConfigList from './pages/ConfigList'
import ConfigEditor from './pages/ConfigEditor'
import Chat from './pages/Chat'
import Runs from './pages/Runs'
import Metrics from './pages/Metrics'

function App() {
  return (
    <>
      <Toaster />
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/agents" element={<AgentList />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/config" element={<ConfigList />} />
          <Route path="/config/:name" element={<ConfigEditor />} />
          <Route path="/chat/:agentId" element={<Chat />} />
        </Routes>
      </Layout>
    </>
  )
}

export default App
