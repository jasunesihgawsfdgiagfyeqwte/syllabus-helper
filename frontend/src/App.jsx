import { useState } from 'react'
import { useAuth } from './contexts/AuthContext'
import { StoreProvider } from './contexts/StoreContext'
import Login from './pages/Login'
import Layout from './components/Layout'
import UploadPage from './pages/UploadPage'
import DashboardPage from './pages/DashboardPage'
import CalendarPage from './pages/CalendarPage'
import AskPage from './pages/AskPage'
import GradesPage from './pages/GradesPage'

export default function App() {
  const { user, loading } = useAuth()
  const [tab, setTab] = useState('upload')

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-logo">S</div>
        <p>Loading...</p>
      </div>
    )
  }

  if (!user) return <Login />

  return (
    <StoreProvider>
      <Layout tab={tab} setTab={setTab}>
        {tab === 'upload' && <UploadPage onDone={() => setTab('dashboard')} />}
        {tab === 'dashboard' && <DashboardPage />}
        {tab === 'calendar' && <CalendarPage />}
        {tab === 'ask' && <AskPage />}
        {tab === 'grades' && <GradesPage />}
      </Layout>
    </StoreProvider>
  )
}
