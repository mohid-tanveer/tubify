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
  const { isAuthenticated } = useContext(AuthContext)
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
      <div className="overflow-hidden flex flex-col min-h-screen">
        <div className="absolute top-0 left-0">
          <TubifyTitle />
        </div>
        <div className="absolute top-0 right-0 p-10">
          <Button
            asChild
            className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
          >
            <Link to="/profile">Profile</Link>
          </Button>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <p className="text-white">Welcome to Tubify!</p>

            <Button
              asChild
              className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
            >
              <Link to="/search">Search</Link>
            </Button>
            
            {isSpotifyConnected ? (
              <>
                <Button
                  onClick={handleSpotifyDisconnect}
                  disabled={isLoading}
                  className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
                >
                  {isLoading ? (
                    <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Icons.spotify className="mr-2 h-4 w-4" />
                  )}
                  Disconnect Spotify
                </Button>
                <Button
                  onClick={handlePlaylistsClick}
                  variant="spotify"
                >
                  <Icons.spotify className="mr-2 h-4 w-4" />
                  My Playlists
                </Button>
              </>
            ) : (
              <>
                <Button
                  onClick={handleSpotifyConnect}
                  disabled={isLoading}
                  className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
                >
                  {isLoading ? (
                    <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Icons.spotify className="mr-2 h-4 w-4" />
                  )}
                  Connect Spotify
                </Button>
                <Button
                  onClick={() => toast.error("Please connect Spotify to access playlists")}
                  className="bg-gray-600 hover:bg-gray-700 cursor-not-allowed"
                >
                  <Icons.spotify className="mr-2 h-4 w-4" />
                  My Playlists
                </Button>
              </>
            )}
            <Button
              asChild
              className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
            >
              <Link to="/watch">Watch</Link>
            </Button>
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
          className="hover:text-red-500 transition-colors"
        >
          <Link to="/auth">Sign in</Link>
        </Button>
      </div>
    </div>
  )
}