import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useContext, useEffect, useState } from 'react'
import { Homepage, AuthPage, EmailVerification, ResetPassword, RequestReset, WatchPage } from './pages'
import { Spinner } from './components/ui/spinner'
import { AuthContext } from './contexts/auth'
import api from './lib/axios'
import './App.css'

interface User {
  id: number
  username: string
  email: string
  is_email_verified: boolean
}

function EmailVerificationBanner() {
  const { user } = useContext(AuthContext)
  const location = useLocation()
  const [isVisible, setIsVisible] = useState(true)
  const [isResending, setIsResending] = useState(false)
  const [resendStatus, setResendStatus] = useState<'idle' | 'success' | 'error'>('idle')

  // don't show if: no user, email is verified, banner dismissed, or on verification page
  if (!user || 
      user.is_email_verified || 
      !isVisible || 
      location.pathname.startsWith('/verify-email')) return null

  const handleResend = async () => {
    setIsResending(true)
    setResendStatus('idle')
    try {
      await api.post('/api/auth/resend-verification')
      setResendStatus('success')
    } catch (error) {
      console.error('Failed to resend verification email:', error)
      setResendStatus('error')
    } finally {
      setIsResending(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="relative bg-white p-8 rounded-lg shadow-lg w-full max-w-lg">
        <button
          onClick={() => setIsVisible(false)}
          className="absolute top-4 right-4 text-white hover:text-slate-400"
          aria-label="Close"
        >
          ✕
        </button>
        <div className="space-y-4 flex flex-col items-center">
          <p className="text-black text-lg font-bold text-center">
            <br/><br/>Please verify your email address. Check your inbox for a verification link.<br/>
          </p>
          {resendStatus === 'success' && (
            <p className="text-green-600 text-center">✓ New verification email sent!</p>
          )}
          {resendStatus === 'error' && (
            <p className="text-red-600 text-center">Failed to send verification email.</p>
          )}
          <button
            onClick={handleResend}
            disabled={isResending}
            className="text-sm text-white hover:text-slate-400 disabled:opacity-50 mt-2"
          >
            {isResending ? 'Sending...' : 'Resend verification email'}
          </button>
        </div>
      </div>
    </div>
  )
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useContext(AuthContext)
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth" state={{ from: location }} replace />
  }

  return <>{children}</>
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [user, setUser] = useState<User | null>(null)

  const checkAuth = async () => {
    try {
      const response = await api.get('/api/auth/me')
      if (response.data) {
        setUser(response.data)
        setIsAuthenticated(true)
      }
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Auth check failed:', error)
      }
      setIsAuthenticated(false)
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  const login = async () => {
    try {
      const response = await api.get('/api/auth/me')
      if (response.data) {
        setUser(response.data)
        setIsAuthenticated(true)
      }
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Login check failed:', error)
      }
    }
  }

  const logout = async () => {
    try {
      await api.post('/api/auth/logout')
      setIsAuthenticated(false)
      setUser(null)
    } catch (error) {
      console.error('Logout failed:', error)
    }
  }

  useEffect(() => {
    checkAuth()
  }, [])

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, user, login, logout }}>
      <Router>
        <EmailVerificationBanner />
        <Routes>
          {/* public routes (users don't have to be signed in to access) */}
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/verify-email/:token" element={<EmailVerification />} />
          <Route path="/reset-password" element={<RequestReset />} />
          <Route path="/reset-password/:token" element={<ResetPassword />} />
          <Route path="/auth/google/callback" element={<AuthPage />} />
          <Route path="/auth/github/callback" element={<AuthPage />} />
          {/* homepage is accessible to all, but shows different content based on auth status */}
          <Route path="/" element={<Homepage />} />
          <Route path="/watch" element={<WatchPage />} /> 
          {/* protected routes (requires authentication) */}
          {/*<Route
            path=path
            element={
              <ProtectedRoute>
                <Page />
              </ProtectedRoute>
            }
          />*/}
        </Routes>
      </Router>
    </AuthContext.Provider>
  )
}

export default App