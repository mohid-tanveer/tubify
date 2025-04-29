import { Button } from "@/components/ui/button"
import { Link, useSearchParams, useNavigate, useLoaderData } from "react-router-dom"
import { useContext, useState } from "react"
import { AuthContext } from "@/contexts/auth"
import { TubifyTitle } from "@/components/ui/tubify-title"
import api from "@/lib/axios"
import { Icons } from "@/components/icons"
import { toast } from "sonner"

interface LoaderData {
  isSpotifyConnected: boolean
}

export default function Homepage() {
  const { isAuthenticated, user } = useContext(AuthContext)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const { isSpotifyConnected } = useLoaderData() as LoaderData
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // show toast if redirected from playlists due to missing spotify connection
  if (searchParams.get('spotify_required') === 'true') {
    toast.error('Please connect your Spotify account to access playlists')
  }

  const handleSpotifyConnect = async () => {
    try {
      setIsLoading(true)
      const response = await api.get("/api/spotify/connect")
      window.location.href = response.data.url
    } catch (error) {
      if (process.env.NODE_ENV === "development") {
        console.error("failed to connect spotify:", error)
      }
      toast.error("Failed to connect to Spotify")
    } finally {
      setIsLoading(false)
    }
  }

  const handleSpotifyDisconnect = async () => {
    try {
      setIsLoading(true)
      await api.delete("/api/spotify/disconnect")
      // after disconnecting, reload the page to get fresh loader data
      window.location.reload()
    } catch (error) {
      if (process.env.NODE_ENV === "development") {
        console.error("failed to disconnect spotify:", error)
      }
      toast.error("Failed to disconnect from Spotify")
    } finally {
      setIsLoading(false)
    }
  }

  const handlePlaylistsClick = () => {
    navigate('/playlists')
  }

  if (isAuthenticated) {
    return (
      <div className="scrollable-page bg-linear-to-b from-slate-900 to-black">
        <div className="relative sm:absolute top-0 left-0">
          <TubifyTitle />
        </div>

        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          
          <div className="pt-6 pb-4 mt-0 sm:mt-16">
            <div className="mb-8">
              <h1 className="text-2xl md:text-3xl font-bold text-white">
                Welcome back, {user?.username}
              </h1>
              <p className="mt-2 text-slate-400">
                Manage your profile and playlists
              </p>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 pb-8">
            {/* profile Card */}
            <div 
              className="flex h-full cursor-pointer flex-col items-center justify-center rounded-lg border border-slate-700 bg-slate-900/50 p-6 text-center transition-colors hover:border-slate-500 hover:bg-slate-900"
              onClick={() => navigate("/profile")}
            >
              <h3 className="text-lg font-medium text-white">Profile</h3>
              <p className="mt-1 text-sm text-slate-400">View and edit your profile</p>
            </div>

            {/* search Card */}
            <div 
              className="flex h-full cursor-pointer flex-col items-center justify-center rounded-lg border border-slate-700 bg-slate-900/50 p-6 text-center transition-colors hover:border-slate-500 hover:bg-slate-900"
              onClick={() => navigate("/search")}
            >
              <h3 className="text-lg font-medium text-white">Search</h3>
              <p className="mt-1 text-sm text-slate-400">Find users and playlists</p>
            </div>

            {/* playlists Card */}
            {isSpotifyConnected ? (
              <div 
                className="flex h-full cursor-pointer flex-col items-center justify-center rounded-lg border border-slate-700 bg-slate-900/50 p-6 text-center transition-colors hover:border-slate-500 hover:bg-slate-900"
                onClick={handlePlaylistsClick}
              >
                <Icons.spotify className="mb-2 h-8 w-8 text-green-500" />
                <h3 className="text-lg font-medium text-white">My Playlists</h3>
                <p className="mt-1 text-sm text-slate-400">View and manage your playlists</p>
              </div>
            ) : (
              <div 
                className="flex h-full cursor-not-allowed flex-col items-center justify-center rounded-lg border border-slate-700 bg-slate-900/50 p-6 text-center"
                onClick={() => toast.error("Please connect Spotify to access playlists")}
              >
                <Icons.spotify className="mb-2 h-8 w-8 text-slate-400" />
                <h3 className="text-lg font-medium text-slate-300">My Playlists</h3>
                <p className="mt-1 text-sm text-slate-400">Connect Spotify to access playlists</p>
              </div>
            )}

            {/* recommendations Card */}
            {isSpotifyConnected && (
              <div 
                className="flex h-full cursor-pointer flex-col items-center justify-center rounded-lg border border-slate-700 bg-slate-900/50 p-6 text-center transition-colors hover:border-slate-500 hover:bg-slate-900"
                onClick={() => navigate("/recommendations")}
            >
              <h3 className="text-lg font-medium text-white">Recommendations</h3>
              <p className="mt-1 text-sm text-slate-400">
                View your personalized recommendations
                </p>
              </div>
            )}

            {/* Reviews Card */}
            <div 
              className="flex h-full cursor-pointer flex-col items-center justify-center rounded-lg border border-slate-700 bg-slate-900/50 p-6 text-center transition-colors hover:border-slate-500 hover:bg-slate-900"
              onClick={() => navigate("/enter-review")}
            >
              
              <h3 className="text-lg font-medium text-white">Write a Review</h3>
              <p className="mt-1 text-sm text-slate-400">Rate and review songs or albums</p>
            </div>

            {/* Read Reviews Card */}
            <div 
              className="flex h-full cursor-pointer flex-col items-center justify-center rounded-lg border border-slate-700 bg-slate-900/50 p-6 text-center transition-colors hover:border-slate-500 hover:bg-slate-900"
              onClick={() => navigate("/read-reviews")}
            >
              
              <h3 className="text-lg font-medium text-white">Read Reviews</h3>
              <p className="mt-1 text-sm text-slate-400">See what you and your friends think</p>
            </div>

            {/* spotify connection Card */}
            <div 
              className="flex h-full cursor-pointer flex-col items-center justify-center rounded-lg border border-slate-700 bg-slate-900/50 p-6 text-center transition-colors hover:border-slate-500 hover:bg-slate-900"
              onClick={isSpotifyConnected ? handleSpotifyDisconnect : handleSpotifyConnect}
            >
              {isLoading ? (
                <Icons.spinner className="mb-2 h-8 w-8 animate-spin text-slate-400" />
              ) : (
                <Icons.spotify className="mb-2 h-8 w-8 text-slate-400" />
              )}
              <h3 className="text-lg font-medium text-white">
                {isSpotifyConnected ? "Disconnect Spotify" : "Connect Spotify"}
              </h3>
              <p className="mt-1 text-sm text-slate-400">
                {isSpotifyConnected ? "Remove Spotify connection" : "Link your Spotify account"}
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="overflow-hidden flex flex-col min-h-screen">
      <div className="absolute top-0 left-0">
        <TubifyTitle />
      </div>
      <div className="flex-1 flex items-center justify-center">
        <Button 
          asChild
          className="hover:text-blue-700"
        >
          <Link to="/auth">Sign in</Link>
        </Button>
      </div>
    </div>
  )
}