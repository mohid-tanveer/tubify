import {
  RouterProvider,
  createBrowserRouter,
  Navigate,
  useLocation,
  redirect,
  LoaderFunction,
  Outlet,
} from "react-router-dom"
import { useContext, useEffect, useState } from "react"
import {
  Homepage,
  AuthPage,
  EmailVerification,
  ResetPassword,
  RequestReset,
  WatchPage,
  Profile,
  Search,
  Playlists,
  PlaylistDetail,
  UserProfile,
  UserPlaylists,
  UserPlaylistDetail,
  LikedSongs,
  FriendLikedSongs,
  PlaylistYouTubeView,
  RecentlyPlayed,
  Recommendations,
  ListeningHabits,
  RecommendationAnalysis,
  RecommendationYouTubeView,
  EnterReview,
  ReadReviews,
  UserReviews
} from "./pages"
import { Spinner } from "./components/ui/spinner"
import { AuthContext } from "./contexts/auth"
import { Toaster } from "@/components/ui/sonner"
import { toast } from "sonner"
import api from "./lib/axios"
import {
  playlistsLoader,
  playlistDetailLoader,
  userProfileLoader,
  userPlaylistsLoader,
  userPlaylistDetailLoader,
  profileLoader,
  likedSongsLoader,
  friendLikedSongsLoader,
  playlistYouTubeQueueLoader,
  listeningHabitsLoader,
  recommendationsLoader,
  recommendationAnalysisLoader,
  recommendationYouTubeQueueLoader,
  reviewsLoader,
  userReviewsLoader
} from "./loaders"
import "./App.css"

interface User {
  id: number
  username: string
  email: string
  is_email_verified: boolean
}

// loader function to check spotify status
const spotifyAuthLoader: LoaderFunction = async () => {
  try {
    const response = await api.get("/api/spotify/status")
    return { isSpotifyConnected: response.data.is_connected }
  } catch {
    return { isSpotifyConnected: false }
  }
}

// loader function to check auth and spotify status
const fullAuthLoader: LoaderFunction = async () => {
  try {
    // check auth status
    const authResponse = await api.get("/api/auth/me")
    if (!authResponse.data) {
      return redirect("/auth")
    }

    // check spotify connection
    const spotifyResponse = await api.get("/api/spotify/status")
    if (!spotifyResponse.data.is_connected) {
      return redirect("/?spotify_required=true")
    }

    return null
  } catch {
    // if any error occurs during auth or spotify check, redirect to auth
    return redirect("/auth")
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
        element: (
          <ProtectedRoute>
            <WatchPage />
          </ProtectedRoute>
        ),
        loader: fullAuthLoader,
      },
      {
        path: "/profile",
        element: (
          <ProtectedRoute>
            <Profile />
          </ProtectedRoute>
        ),
        loader: profileLoader,
      },
      {
        path: "/enter-review",
        element: (
          <ProtectedRoute>
            <EnterReview />
          </ProtectedRoute>
        ),
        loader: fullAuthLoader,
      },
      {
        path: "/users/:username",
        element: (
          <ProtectedRoute>
            <UserProfile />
          </ProtectedRoute>
        ),
        loader: userProfileLoader,
      },
      {
        path: "/users/:username/playlists",
        element: (
          <ProtectedRoute>
            <UserPlaylists />
          </ProtectedRoute>
        ),
        loader: userPlaylistsLoader,
      },
      {
        path: "/users/playlists/:id",
        element: <UserPlaylistDetail />,
        loader: userPlaylistDetailLoader,
      },
      {
        path: "/listening-habits",
        element: (
          <ProtectedRoute>
            <ListeningHabits />
          </ProtectedRoute>
        ),
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through

          // if auth checks pass, load listening habits
          return listeningHabitsLoader()
        },
      },
      {
        path: "/playlists",
        element: (
          <ProtectedRoute>
            <Playlists />
          </ProtectedRoute>
        ),
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
        element: (
          <ProtectedRoute>
            <PlaylistDetail />
          </ProtectedRoute>
        ),
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through

          // if auth and spotify checks pass, load playlist detail
          return playlistDetailLoader(args)
        },
      },
      {
        path: "/watch/:id",
        element: (
          <ProtectedRoute>
            <PlaylistYouTubeView />
          </ProtectedRoute>
        ),
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through

          // load YouTube queue data
          return playlistYouTubeQueueLoader(args)
        },
      },
      {
        path: "/search",
        element: (
          <ProtectedRoute>
            <Search />
          </ProtectedRoute>
        ),
      },
      {
        path: "/recently-played",
        element: (
          <ProtectedRoute>
            <RecentlyPlayed />
          </ProtectedRoute>
        ),
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through

          // if auth checks pass, load recently played
          return likedSongsLoader(args)
        },
      },
      {
        path: "/liked-songs",
        element: (
          <ProtectedRoute>
            <LikedSongs />
          </ProtectedRoute>
        ),
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through

          // if auth checks pass, load liked songs
          return likedSongsLoader(args)
        },
      },
      {
        path: "/recommendations",
        element: (
          <ProtectedRoute>
            <Recommendations />
          </ProtectedRoute>
        ),
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through

          // load recommendations with video availability check
          return recommendationsLoader()
        },
      },
      {
        path: "/recommendations/watch",
        element: (
          <ProtectedRoute>
            <RecommendationYouTubeView />
          </ProtectedRoute>
        ),
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through

          // load YouTube queue data for recommendations
          return recommendationYouTubeQueueLoader()
        },
      },
      {
        path: "/recommendation-analysis",
        element: (
          <ProtectedRoute>
            <RecommendationAnalysis />
          </ProtectedRoute>
        ),
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through

          // load recommendation analysis
          return recommendationAnalysisLoader()
        },
      },
      {
        path: "/users/:username/liked-songs",
        element: (
          <ProtectedRoute>
            <FriendLikedSongs />
          </ProtectedRoute>
        ),
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through

          // if auth checks pass, load friend's liked songs
          return friendLikedSongsLoader(args)
        },
      },
      {
        path: "/listening-habits",
        element: (
          <ProtectedRoute>
            <ListeningHabits />
          </ProtectedRoute>
        ),
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through

          // if auth checks pass, load listening habits
          return listeningHabitsLoader()
        },
      },
      {
        path: "/read-reviews",
        element: (
          <ProtectedRoute>
            <ReadReviews />
          </ProtectedRoute>
        ),
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through

          // load reviews
          return reviewsLoader()
        },
      },
      {
        path: "/users/:username/reviews",
        element: (
          <ProtectedRoute>
            <UserReviews />
          </ProtectedRoute>
        ),
        loader: async (args) => {
          // first check auth and spotify status
          const result = await fullAuthLoader(args)
          if (result) return result // if it returns a redirect, pass it through

          // load user reviews
          return userReviewsLoader(args as unknown as { params: { username: string } })
        },
      }
    ],
  },
])

function Layout() {
  const { user } = useContext(AuthContext)
  const location = useLocation()
  const [isResending, setIsResending] = useState(false)

  // check if the user needs to verify email and display a toast
  useEffect(() => {
    if (user && !user.is_email_verified && !location.pathname.startsWith("/verify-email")) {
      const handleResend = async () => {
        if (isResending) return;
        
        try {
          setIsResending(true)
          await api.post("/api/auth/resend-verification")
          toast.success("Verification email sent!", {
            description: "Please check your inbox for the verification link.",
          })
        } catch (error) {
          if (process.env.NODE_ENV === "development") {
            console.error("Failed to resend verification email:", error)
          }
          toast.error("Failed to send verification email", {
            description: "Please try again later.",
          })
        } finally {
          setIsResending(false)
        }
      }

      // display persistent toast for email verification
      toast.info("Please verify your email address", {
        description: "Check your inbox for a verification link",
        duration: Infinity,
        action: {
          label: isResending ? "Sending..." : "Resend email",
          onClick: handleResend,
        },
        id: "verify-email-toast", // use a fixed id to prevent duplicates
      })
    }
  }, [user, location.pathname, isResending])

  return (
    <>
      <Toaster richColors position="top-center" />
      <Outlet />
    </>
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
      const response = await api.get("/api/auth/me")
      if (response.data) {
        setUser(response.data)
        setIsAuthenticated(true)
      }
    } catch (error) {
      if (process.env.NODE_ENV === "development") {
        console.error("Auth check failed:", error)
      }
      setIsAuthenticated(false)
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  const login = async () => {
    try {
      const response = await api.get("/api/auth/me")
      if (response.data) {
        setUser(response.data)
        setIsAuthenticated(true)
      }
    } catch (error) {
      if (process.env.NODE_ENV === "development") {
        console.error("Login check failed:", error)
      }
    }
  }

  const logout = async () => {
    try {
      await api.post("/api/auth/logout")
      setIsAuthenticated(false)
      setUser(null)
    } catch (error) {
      if (process.env.NODE_ENV === "development") {
        console.error("Logout failed:", error)
      }
    }
  }

  useEffect(() => {
    checkAuth()
  }, [])

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, isLoading, user, login, logout }}
    >
      <RouterProvider router={router} />
    </AuthContext.Provider>
  )
}

export default App
