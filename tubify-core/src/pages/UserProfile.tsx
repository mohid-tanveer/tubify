import { useLoaderData, useNavigate } from "react-router-dom"
import { TubifyTitle } from "@/components/ui/tubify-title"
import { Button } from "@/components/ui/button"
import { Music } from "lucide-react"

interface UserProfileData {
  username: string
  profilePicture: string
  bio: string
  playlistCount: number
}

export default function UserProfile() {
  const { profile } = useLoaderData() as { profile: UserProfileData }
  const navigate = useNavigate()

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
          
          <div className="flex gap-4 mt-4">
            <Button 
              onClick={() => navigate(`/users/${profile.username}/playlists`)}
              className="flex items-center gap-2"
            >
              <Music className="h-4 w-4" />
              View Playlists ({profile.playlistCount})
            </Button>
            
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