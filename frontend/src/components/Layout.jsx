import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, LayoutDashboard, Calendar, MessageCircle, GraduationCap, Moon, Sun, LogOut } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useStore } from '../contexts/StoreContext'
import './Layout.css'

const TABS = [
  { id: 'upload', label: 'Upload', icon: Upload },
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'calendar', label: 'Calendar', icon: Calendar },
  { id: 'ask', label: 'Ask', icon: MessageCircle },
  { id: 'grades', label: 'Grades', icon: GraduationCap },
]

export default function Layout({ tab, setTab, children }) {
  const { user, logout } = useAuth()
  const { syllabi, activeId, setActiveId } = useStore()
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem('theme')
    if (saved) return saved === 'dark'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  const toggleTheme = () => {
    const next = !dark
    setDark(next)
    document.documentElement.dataset.theme = next ? 'dark' : 'light'
    localStorage.setItem('theme', next ? 'dark' : 'light')
  }

  // Set initial theme
  if (!document.documentElement.dataset.theme) {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
  }

  const ids = Object.keys(syllabi)

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-box">S</div>
          <span>Syllabus Helper</span>
        </div>

        <nav className="sidebar-nav">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={`nav-btn ${tab === id ? 'active' : ''}`}
              onClick={() => setTab(id)}
            >
              <Icon size={16} />
              <span className="nav-label">{label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          {ids.length > 0 && (
            <>
              <div className="sidebar-label">Courses</div>
              {ids.map(id => {
                const s = syllabi[id]
                const code = s?.course_info?.course_code || id.replace(/_/g, ' ')
                return (
                  <button
                    key={id}
                    className={`course-btn ${id === activeId ? 'active' : ''}`}
                    onClick={() => { setActiveId(id); setTab('dashboard') }}
                  >
                    {code}
                    <span className="course-badge">{s?.deadlines?.length || 0}</span>
                  </button>
                )
              })}
            </>
          )}

          <div className="sidebar-actions">
            <button className="icon-btn" onClick={toggleTheme} title="Toggle theme">
              {dark ? <Sun size={14} /> : <Moon size={14} />}
              <span>{dark ? 'Light' : 'Dark'}</span>
            </button>
            <button className="icon-btn" onClick={logout} title="Sign out">
              <LogOut size={14} />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.15 }}
            className="page-wrapper"
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  )
}
