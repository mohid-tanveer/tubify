import { Button } from "@/components/ui/button"
import { Link } from "react-router-dom"
import { useContext, useEffect, useState } from "react"
import { AuthContext } from "@/contexts/auth"
import { TubifyTitle } from "@/components/ui/tubify-title"
import api from "@/lib/axios"
import { Icons } from "@/components/icons"

export default function Homepage() {
  const { isAuthenticated, logout } = useContext(AuthContext)
  const [isSpotifyConnected, setIsSpotifyConnected] = useState<boolean>(false)
  const [isLoading, setIsLoading] = useState<boolean>(false)

  // check spotify connection status when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      checkSpotifyStatus()
    }
  }, [isAuthenticated])

  const checkSpotifyStatus = async () => {
    try {
      const response = await api.get("/api/spotify/status")
      setIsSpotifyConnected(response.data.is_connected)
    } catch (error) {
      console.error("failed to check spotify status:", error)
    }
  }

  const handleSpotifyConnect = async () => {
    try {
      setIsLoading(true)
      const response = await api.get("/api/spotify/connect")
      window.location.href = response.data.url
    } catch (error) {
      console.error("failed to connect spotify:", error)
      setIsLoading(false)
    }
  }

  const handleSpotifyDisconnect = async () => {
    try {
      setIsLoading(true)
      await api.delete("/api/spotify/disconnect")
      setIsSpotifyConnected(false)
    } catch (error) {
      console.error("failed to disconnect spotify:", error)
    } finally {
      setIsLoading(false)
    }
  }

  if (isAuthenticated) {
    return (
      <div className="overflow-hidden flex flex-col min-h-screen">
        <div className="absolute top-0 left-0">
          <TubifyTitle />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <p className="text-white">Welcome to Tubify!</p>
            
            {isSpotifyConnected ? (
              <Button
                onClick={handleSpotifyDisconnect}
                disabled={isLoading}
                variant="outline"
                className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
              >
                {isLoading ? (
                  <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Icons.spotify className="mr-2 h-4 w-4" />
                )}
                Disconnect Spotify
              </Button>
            ) : (
              <Button
                onClick={handleSpotifyConnect}
                disabled={isLoading}
                variant="outline"
                className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
              >
                {isLoading ? (
                  <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Icons.spotify className="mr-2 h-4 w-4" />
                )}
                Connect Spotify
              </Button>
            )}         
            <Button
              asChild
              className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
            >
              <Link to="/watch">Watch</Link>
            </Button>
            
            <Button 
              onClick={logout}
              className="text-white hover:text-red-500 transition-colors"
            >
              Sign out
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