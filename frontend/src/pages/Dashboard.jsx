import { useAuth } from '../contexts/AuthContext'
import './Dashboard.css'

export default function Dashboard() {
  const { user, logout } = useAuth()

  return (
    <div className="dash-shell">
      <header className="dash-topbar">
        <div className="topbar-left">
          <span className="topbar-logo">S</span>
          <span className="topbar-title">Syllabus Helper</span>
        </div>
        <div className="topbar-right">
          <span className="topbar-user">
            {user.picture && <img src={user.picture} alt="" className="topbar-avatar" />}
            {user.name || user.email}
          </span>
          <button className="topbar-logout" onClick={logout}>Sign out</button>
        </div>
      </header>
      <iframe
        src="http://localhost:8000"
        className="dash-iframe"
        title="Syllabus Helper App"
      />
    </div>
  )
}
