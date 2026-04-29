import { useState, useEffect, useRef } from 'react'
import { FileSearch, CalendarDays, MessageSquare } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import './Login.css'

export default function Login() {
  const { login, register, googleLogin } = useAuth()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleReady, setGoogleReady] = useState(false)
  const googleBtnRef = useRef(null)

  // Fetch Google Client ID from backend and initialize Google SDK
  useEffect(() => {
    let cancelled = false
    async function initGoogle() {
      try {
        const res = await fetch('/api/auth/google-client-id')
        if (!res.ok) return
        const { client_id } = await res.json()
        if (!client_id || cancelled) return

        // Wait for Google SDK to load
        const waitForGoogle = () => new Promise((resolve) => {
          if (window.google?.accounts?.id) return resolve()
          const timer = setInterval(() => {
            if (window.google?.accounts?.id) { clearInterval(timer); resolve() }
          }, 100)
          setTimeout(() => { clearInterval(timer); resolve() }, 5000)
        })

        await waitForGoogle()
        if (!window.google?.accounts?.id || cancelled) return

        window.google.accounts.id.initialize({
          client_id,
          callback: (response) => {
            googleLogin(response.credential).catch(err => setError(err.message))
          },
        })
        setGoogleReady(true)
        if (googleBtnRef.current) {
          window.google.accounts.id.renderButton(googleBtnRef.current, {
            theme: 'outline', size: 'large', width: '100%', text: 'continue_with',
          })
        }
      } catch {}
    }
    initGoogle()
    return () => { cancelled = true }
  }, [googleLogin])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'register') {
        await register(email, password, name)
      } else {
        await login(email, password)
      }
    } catch (err) {
      setError(err.message)
    }
    setLoading(false)
  }

  const handleGoogle = () => {
    if (window.google?.accounts?.id) {
      window.google.accounts.id.prompt()
    } else {
      setError('Google sign-in is loading, please try again.')
    }
  }

  return (
    <div className="login-page">
      <div className="login-left">
        <div className="login-brand">
          <div className="login-logo">S</div>
          <h1>Syllabus Helper</h1>
          <p className="login-tagline">Upload. Understand. Plan.</p>
        </div>
        <div className="login-features">
          <div className="login-feature">
            <span className="feature-icon"><FileSearch size={20} /></span>
            <div>
              <strong>Smart Extraction</strong>
              <p>Automatically parse deadlines, grading, and policies from any syllabus.</p>
            </div>
          </div>
          <div className="login-feature">
            <span className="feature-icon"><CalendarDays size={20} /></span>
            <div>
              <strong>Semester Calendar</strong>
              <p>See all your deadlines across courses in one visual calendar.</p>
            </div>
          </div>
          <div className="login-feature">
            <span className="feature-icon"><MessageSquare size={20} /></span>
            <div>
              <strong>Ask Anything</strong>
              <p>Get instant answers grounded in your course documents.</p>
            </div>
          </div>
        </div>
      </div>

      <div className="login-right">
        <div className="login-card">
          <h2>{mode === 'login' ? 'Welcome back' : 'Get started'}</h2>
          <p className="login-subtitle">
            {mode === 'login'
              ? 'Sign in to your account'
              : 'Create your free account'}
          </p>

          <div ref={googleBtnRef} className="google-btn-container" style={{ display: googleReady ? 'block' : 'none' }} />
          <button className="google-btn" onClick={handleGoogle} type="button" style={{ display: googleReady ? 'none' : 'flex' }}>
            <svg width="18" height="18" viewBox="0 0 48 48">
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            </svg>
            Continue with Google
          </button>

          <div className="divider">
            <span>or</span>
          </div>

          <form onSubmit={handleSubmit}>
            {mode === 'register' && (
              <input
                type="text"
                placeholder="Your name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="login-input"
              />
            )}
            <input
              type="email"
              placeholder="Email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="login-input"
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="login-input"
              required
              minLength={6}
            />

            {error && <div className="login-error">{error}</div>}

            <button type="submit" className="login-submit" disabled={loading}>
              {loading ? 'Loading...' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <p className="login-switch">
            {mode === 'login' ? (
              <>
                Don&apos;t have an account?{' '}
                <button type="button" onClick={() => { setMode('register'); setError('') }}>
                  Sign up
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button type="button" onClick={() => { setMode('login'); setError('') }}>
                  Sign in
                </button>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  )
}
