import { RouterProvider, createBrowserRouter, Navigate, useLocation, redirect, LoaderFunction, Outlet } from 'react-router-dom'
import { useContext, useEffect, useState } from 'react'
import { Homepage, AuthPage, EmailVerification, ResetPassword, RequestReset, WatchPage, Profile, Search, Playlists, PlaylistDetail, UserProfile, UserPlaylists, UserPlaylistDetail, LikedSongs } from './pages'
import { Spinner } from './components/ui/spinner'
import { AuthContext } from './contexts/auth'
import { Toaster } from "@/components/ui/sonner"
import api from './lib/axios'
import { playlistsLoader, playlistDetailLoader, userProfileLoader, userPlaylistsLoader, userPlaylistDetailLoader, profileLoader } from './loaders'
import './App.css'
import FriendLikedSongs from './pages/FriendLikedSongs'

interface User {
  id: number
  username: string
  email: string
  is_email_verified: boolean
}

// loader function to check spotify status
const spotifyAuthLoader: LoaderFunction = async () => {
  try {
    const response = await api.get('/api/spotify/status')
    return { isSpotifyConnected: response.data.is_connected }
  } catch {
    return { isSpotifyConnected: false }
  }
}

// loader function to check auth and spotify status for playlists
const fullAuthLoader: LoaderFunction = async () => {
  try {
    // check auth status
    const authResponse = await api.get('/api/auth/me')
    if (!authResponse.data) {
      return redirect('/auth')
    }

    // check spotify connection
    const spotifyResponse = await api.get('/api/spotify/status')
    if (!spotifyResponse.data.is_connected) {
      return redirect('/?spotify_required=true')
    }

    return null
  } catch {
    // if any error occurs during auth or spotify check, redirect to auth
    return redirect('/auth')
  }
}

// create router with all routes
const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      {
        path: "/",
        element: <Homepage />,
        loader: spotifyAuthLoader,
      },
      {
        path: "/auth",
        element: <AuthPage />,
      },
      {
        path: "/verify-email/:token",
        element: <EmailVerification />,
      },
      {
        path: "/reset-password",
        element: <RequestReset />,
      },
      {
        path: "/reset-password/:token",
        element: <ResetPassword />,
      },
      {
        path: "/auth/google/callback",
        element: <AuthPage />,
      },
      {
        path: "/auth/github/callback",
        element: <AuthPage />,
      },
      {
        path: "/watch",
        element: <ProtectedRoute><WatchPage /></ProtectedRoute>,
        loader: fullAuthLoader,
      },
      {
        path: "/profile",
        element: <ProtectedRoute><Profile /></ProtectedRoute>,
        loader: profileLoader,
      },
      {
        path: "/users/:username",
        element: <ProtectedRoute><UserProfile /></ProtectedRoute>,
        loader: userProfileLoader,
      },
      {
        path: "/users/:username/playlists",
        element: <ProtectedRoute><UserPlaylists /></ProtectedRoute>,
        loader: userPlaylistsLoader,
      },
      {
        path: "/users/playlists/:id",
        element: <UserPlaylistDetail />,
        loader: userPlaylistDetailLoader,
      },
      {
        path: "/playlists",
        element: <ProtectedRoute><Playlists /></ProtectedRoute>,
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through
          
          // if auth and spotify checks pass, load playlists
          return playlistsLoader()
        },
      },
      {
        path: "/playlists/:id",
        element: <ProtectedRoute><PlaylistDetail /></ProtectedRoute>,
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through
          
          // if auth and spotify checks pass, load playlist detail
          return playlistDetailLoader(args)
        },
      },
      {
        path: "/search",
        element: <ProtectedRoute><Search /></ProtectedRoute>,
      },
      {
        path: "/liked-songs",
        element: <ProtectedRoute><LikedSongs /></ProtectedRoute>,
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through
          
          return null
        },
      },
      {
        path: "/users/:username/liked-songs",
        element: <ProtectedRoute><FriendLikedSongs /></ProtectedRoute>,
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through
          
          return null
        },
      },
    ],
  },
])

function Layout() {
  return (
    <>
      <Toaster 
        richColors 
        position="top-center" 
        duration={3000}
      />
      <EmailVerificationBanner />
      <Outlet />
    </>
  )
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
      if (process.env.NODE_ENV === 'development') {
        console.error('Failed to resend verification email:', error)
      }
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
      if (process.env.NODE_ENV === 'development') {
        console.error('Logout failed:', error)
      }
    }
  }

  useEffect(() => {
    checkAuth()
  }, [])

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, user, login, logout }}>
      <RouterProvider router={router} />
    </AuthContext.Provider>
  )
}

export default App