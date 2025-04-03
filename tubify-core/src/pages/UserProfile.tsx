import { useLoaderData, useNavigate } from "react-router-dom"
import { TubifyTitle } from "@/components/ui/tubify-title"
import { Button } from "@/components/ui/button"
import { Music, Heart } from "lucide-react"
import api from "@/lib/axios"
import { useState, useEffect } from "react"

interface UserProfileData {
  username: string
  profilePicture: string
  bio: string
  playlistCount: number
}

interface LikedSongsStats {
  friend_likes_count: number
  shared_likes_count: number
  user_likes_count: number
  friend_unique_count: number
  compatibility_percentage: number
}

export default function UserProfile() {
  const { profile } = useLoaderData() as { profile: UserProfileData }
  const navigate = useNavigate()
  const [likedSongsStats, setLikedSongsStats] = useState<LikedSongsStats | null>(null)

  // fetch liked songs stats when viewing a friend's profile
  useEffect(() => {
    const fetchLikedSongsStats = async () => {
      try {
        const response = await api.get(`/api/liked-songs/friends/${profile.username}/stats`)
        setLikedSongsStats(response.data)
      } catch (error) {
        console.error("Failed to fetch liked songs stats:", error)
        // if not found, just don't show the liked songs option
      }
    }

    fetchLikedSongsStats()
  }, [profile.username])

  return (
    <div className="overflow-hidden flex flex-col min-h-screen">
      <div className="absolute top-0 left-0">
        <TubifyTitle />
      </div>
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 w-full max-w-md px-4">
          <img
            src={profile.profilePicture}
            alt={`${profile.username}'s profile`}
            className="w-32 h-32 rounded-full object-cover"
          />
          
          <h2 className="text-white text-2xl">{profile.username}</h2>
          <p className="text-white text-center">{profile.bio || "No bio yet"}</p>
          
          <div className="flex flex-col gap-4 mt-4 w-full">
            <Button 
              onClick={() => navigate(`/users/${profile.username}/playlists`)}
              className="flex items-center gap-2"
            >
              <Music className="h-4 w-4" />
              View Playlists ({profile.playlistCount})
            </Button>
            
            {likedSongsStats && likedSongsStats.friend_likes_count > 0 && (
              <>
                <Button 
                  onClick={() => navigate(`/users/${profile.username}/liked-songs`)}
                  className="flex items-center gap-2 bg-pink-700 hover:bg-pink-800"
                >
                  <Heart className="h-4 w-4" />
                  View Liked Songs ({likedSongsStats.friend_likes_count})
                </Button>
                
                <div className="bg-slate-800 rounded-lg p-4 text-white text-sm">
                  <h3 className="font-medium mb-2">Music Compatibility</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <span className="block text-slate-400">Shared Songs</span>
                      <span className="text-lg font-bold">{likedSongsStats.shared_likes_count}</span>
                    </div>
                    <div>
                      <span className="block text-slate-400">Compatibility</span>
                      <span className="text-lg font-bold">{likedSongsStats.compatibility_percentage}%</span>
                    </div>
                  </div>
                </div>
              </>
            )}
            
            <Button 
              variant="outline" 
              onClick={() => navigate(-1)}
            >
              Back
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
} 