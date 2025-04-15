import { useLoaderData, useNavigate } from "react-router-dom"
import { TubifyTitle } from "@/components/ui/tubify-title"
import { Button } from "@/components/ui/button"
import { Music, Heart, ArrowLeft } from "lucide-react"

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
  const { profile, likedSongsStats } = useLoaderData() as { 
    profile: UserProfileData, 
    likedSongsStats: LikedSongsStats | null 
  }
  const navigate = useNavigate()

  return (
    <div className="overflow-hidden flex flex-col min-h-screen bg-neutral-800">
      <div className="absolute top-0 left-0">
        <TubifyTitle />
      </div>
      <div className="flex-1 flex flex-col items-center justify-center gap-4 p-4 mt-16 sm:mt-0">
        <div className="flex flex-col sm:flex-row gap-8 w-full max-w-6xl px-4">
          {/* profile section - full width on mobile, 1/3 on desktop */}
          <div className="flex flex-col items-center gap-4 w-full sm:w-1/3 bg-neutral-700 border border-neutral-600 rounded-lg p-6 relative h-fit sm:self-center">
            <img
              src={profile.profilePicture}
              alt={`${profile.username}'s profile`}
              className="w-32 h-32 rounded-full object-cover"
            />
            
            <div className="flex flex-col items-center w-full">
              <div className="flex flex-col items-center flex-grow mb-8">
                <h2 className="text-white text-2xl mb-4">{profile.username}</h2>
                <p className="text-white text-center break-all whitespace-pre-wrap max-w-full overflow-hidden">
                  {profile.bio || "No bio yet"}
                </p>
              </div>
              <Button
                onClick={() => navigate(-1)}
                variant="outline"
                className="w-full sm:w-auto px-8"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
            </div>
          </div>

          {/* content section - full width on mobile, 2/3 on desktop */}
          <div className="flex flex-col items-center gap-4 w-full sm:w-2/3 bg-neutral-700 border border-neutral-600 rounded-lg p-6">
            <h2 className="text-white text-xl">Activity</h2>
            
            <div className="flex flex-col gap-4 w-full">
              <Button 
                onClick={() => navigate(`/users/${profile.username}/playlists`)}
                variant="spotify"
                className="flex items-center justify-center gap-2 w-full"
              >
                <Music className="mr-2 h-4 w-4" />
                View Playlists ({profile.playlistCount})
              </Button>
              
              {likedSongsStats && likedSongsStats.friend_likes_count > 0 && (
                <>
                  <Button 
                    onClick={() => navigate(`/users/${profile.username}/liked-songs`)}
                    variant="outline"
                    className="flex items-center justify-center gap-2 w-full"
                  >
                    <Heart className="mr-2 h-4 w-4" />
                    View Liked Songs ({likedSongsStats.friend_likes_count})
                  </Button>
                  
                  <div className="bg-[#1e2d40] rounded-lg p-4 text-white w-full">
                    <h3 className="font-medium mb-3 text-lg">Music Compatibility</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="flex flex-col items-center p-3 bg-[#2c3e50] rounded-lg">
                        <span className="block text-slate-300 mb-1 text-sm">Shared Songs</span>
                        <span className="text-xl font-bold">{likedSongsStats.shared_likes_count}</span>
                      </div>
                      <div className="flex flex-col items-center p-3 bg-[#2c3e50] rounded-lg">
                        <span className="block text-slate-300 mb-1 text-sm">Compatibility</span>
                        <span className="text-xl font-bold">{likedSongsStats.compatibility_percentage}%</span>
                      </div>
                    </div>
                    
                    <div className="mt-4 grid grid-cols-2 gap-4">
                      <div className="flex flex-col items-center p-3 bg-[#2c3e50] rounded-lg">
                        <span className="block text-slate-300 mb-1 text-sm">Your Liked Songs</span>
                        <span className="text-xl font-bold">{likedSongsStats.user_likes_count}</span>
                      </div>
                      <div className="flex flex-col items-center p-3 bg-[#2c3e50] rounded-lg">
                        <span className="block text-slate-300 mb-1 text-sm">Their Unique Songs</span>
                        <span className="text-xl font-bold">{likedSongsStats.friend_unique_count}</span>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
} 