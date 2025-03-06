import { useContext, useEffect, useState, useRef } from "react"
import { AuthContext } from "@/contexts/auth"
import { TubifyTitle } from "@/components/ui/tubify-title"
import api from "@/lib/axios"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Pencil, X, Check, Music } from "lucide-react"
import { toast } from "sonner"
import { z } from "zod"
import { Icons } from "@/components/icons"
import { useNavigate, useLoaderData } from "react-router-dom"
import { ProfileData } from "@/loaders/user-loaders"

const profileSchema = z.object({
  username: z.string()
    .min(3, "username must be at least 3 characters")
    .max(50, "username must be less than 50 characters")
    .regex(/^[a-zA-Z0-9._-]+$/, "username can only contain letters, numbers, periods, underscores, and hyphens"),
  bio: z.string().max(500, "bio must be less than 500 characters"),
})

interface Profile {
  user_name: string
  profile_picture: string
  bio: string
}

interface Friend {
  id: number;
  username: string;
  profile_picture: string;
}

interface FriendRequest {
  sender_id: number;
  receiver_id: number;
  status: string;
  username: string;
}

export default function Profile() {
  const { isAuthenticated, logout } = useContext(AuthContext)
  const { profile, friends, friendRequests, isSpotifyConnected } = useLoaderData() as ProfileData
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState<{
    username: string
    bio: string
  }>({
    username: profile?.user_name || "",
    bio: profile?.bio || "",
  })
  const [isSaving, setIsSaving] = useState(false)
  const [isCheckingUsername, setIsCheckingUsername] = useState(false)
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const usernameCheckTimeout = useRef<NodeJS.Timeout>()
  const navigate = useNavigate()
  const [searchUsername, setSearchUsername] = useState("")
  const [isAddingFriend, setIsAddingFriend] = useState(false)
  const [localFriends, setLocalFriends] = useState<Friend[]>(friends)
  const [localFriendRequests, setLocalFriendRequests] = useState<FriendRequest[]>(friendRequests)

  const handleAddFriend = async () => {
    try {
      setIsAddingFriend(true)
      await api.post(`/api/profile/add-friend/${searchUsername}`)
      toast.success("Friend request sent!")
      setSearchUsername("")
      // refresh friend requests
      const response = await api.get("/api/profile/friend-requests")
      setLocalFriendRequests(response.data)
    } catch {
      toast.error("Failed to send friend request.")
    } finally {
      setIsAddingFriend(false)
    }
  }

  const handleAcceptFriendRequest = async (senderId: number) => {
    try {
      await api.post(`/api/profile/accept-friend-request/${senderId}`)
      toast.success("Friend request accepted!")
      // refresh friends and friend requests
      const [friendsResponse, requestsResponse] = await Promise.all([
        api.get("/api/profile/friends"),
        api.get("/api/profile/friend-requests")
      ])
      setLocalFriends(friendsResponse.data)
      setLocalFriendRequests(requestsResponse.data)
    } catch {
      toast.error("Failed to accept friend request.")
    }
  }

  const handleRemoveFriend = async (friendId: number) => {
    try {
      await api.post(`/api/profile/remove-friend/${friendId}`)
      toast.success("Friend removed!")
      // refresh friends
      const response = await api.get("/api/profile/friends")
      setLocalFriends(response.data)
    } catch {
      toast.error("Failed to remove friend.")
    }
  }

  // username check effect
  useEffect(() => {
    if (!isEditing) return

    const username = editForm.username
    if (!username || username.length < 3 || username === profile?.user_name) {
      setUsernameError(null)
      return
    }

    // clear any existing timeout
    if (usernameCheckTimeout.current) {
      clearTimeout(usernameCheckTimeout.current)
    }

    // set a new timeout to check username
    usernameCheckTimeout.current = setTimeout(async () => {
      try {
        setIsCheckingUsername(true)
        const response = await api.get(`/api/auth/check-username/${username}`)
        if (!response.data.available) {
          setUsernameError("this username is already taken")
        } else {
          setUsernameError(null)
        }
      } catch (error) {
        if (process.env.NODE_ENV === "development") {
          console.error("Failed to check username:", error)
        }
      } finally {
        setIsCheckingUsername(false)
      }
    }, 500) // debounce for 500ms

    return () => {
      if (usernameCheckTimeout.current) {
        clearTimeout(usernameCheckTimeout.current)
      }
    }
  }, [editForm.username, isEditing, profile?.user_name])

  const handleEdit = () => {
    if (!profile) return
    setEditForm({
      username: profile.user_name,
      bio: profile.bio,
    })
    setIsEditing(true)
  }

  const handleCancel = () => {
    setIsEditing(false)
    if (profile) {
      setEditForm({
        username: profile.user_name,
        bio: profile.bio,
      })
    }
  }

  const handleSave = async () => {
    try {
      const validationResult = profileSchema.safeParse(editForm)
      if (!validationResult.success) {
        const error = validationResult.error.issues[0]
        toast.error(error.message)
        return
      }

      if (usernameError) {
        toast.error(usernameError)
        return
      }

      setIsSaving(true)
      await api.put("/api/profile", editForm)
      // update local profile state
      navigate(".", { replace: true }) // refresh the page to get updated data
      setIsEditing(false)
      toast.success("Profile updated successfully")
    } catch (error) {
      if (process.env.NODE_ENV === "development") {
        console.error("failed to update profile:", error)
      }
      toast.error("Failed to update profile")
    } finally {
      setIsSaving(false)
    }
  }

  const handleLogout = async () => {
    // clear all local storage
    localStorage.clear()
    
    await logout()
  }

  if (!isAuthenticated) {
    return (
      <div className="overflow-hidden flex flex-col min-h-screen">
        <div className="absolute top-0 left-0">
          <TubifyTitle />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-white">Please sign in to view your profile.</p>
        </div>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="overflow-hidden flex flex-col min-h-screen">
        <div className="absolute top-0 left-0">
          <TubifyTitle />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-white">No profile data available.</p>
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
        <div className="flex flex-col items-center gap-4 w-full max-w-md px-4">
          <img
            src={profile.profile_picture}
            alt={`${profile.user_name}'s profile`}
            className="w-32 h-32 rounded-full object-cover"
          />

          {isEditing ? (
            <>
              <div className="w-full space-y-4">
                <div className="space-y-2">
                  <label className="text-sm text-white">username</label>
                  <div className="relative">
                    <Input
                      value={editForm.username}
                      onChange={(e) =>
                        setEditForm({ ...editForm, username: e.target.value })
                      }
                      className={`bg-white/10 border-white/20 text-white ${usernameError ? 'border-red-500' : ''}`}
                      placeholder="Enter your username"
                    />
                    {isCheckingUsername && (
                      <div className="absolute right-3 top-1/2 -translate-y-1/2">
                        <Icons.spinner className="h-4 w-4 animate-spin text-white/50" />
                      </div>
                    )}
                  </div>
                  {usernameError && (
                    <p className="text-sm text-red-500">{usernameError}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <label className="text-sm text-white">bio</label>
                  <div className="relative">
                    <Textarea
                      value={editForm.bio}
                      onChange={(e) =>
                        setEditForm({ ...editForm, bio: e.target.value })
                      }
                      className="bg-white/10 border-white/20 text-white min-h-[100px]"
                      placeholder="Tell us about yourself"
                      maxLength={500}
                    />
                    <div className="absolute bottom-2 right-2 text-xs text-white/50">
                      {editForm.bio.length}/500
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={handleSave}
                  disabled={isSaving}
                  className="bg-green-600 hover:bg-green-700"
                >
                  <Check className="w-4 h-4 mr-2" />
                  {isSaving ? "Saving..." : "Save"}
                </Button>
                <Button
                  onClick={handleCancel}
                  disabled={isSaving}
                  className="bg-red-600 hover:bg-red-700"
                >
                  <X className="w-4 h-4 mr-2" />
                  Cancel
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <h2 className="text-white text-2xl">{profile.user_name}</h2>
                <Button
                  onClick={handleEdit}
                  variant="ghost"
                  size="icon"
                  className="text-white hover:bg-white/30"
                >
                  <Pencil className="w-4 h-4" />
                </Button>
              </div>
              <p className="text-white text-center">{profile.bio || "No bio yet"}</p>

              <div className="flex flex-col items-center gap-4">
                  <h2 className="text-white text-xl">Friends</h2>
                  <ul className="text-white">
                    {localFriends.map((friend) => (
                      <li key={friend.id} className="flex items-center gap-2">
                        <img
                          src={friend.profile_picture}
                          alt={friend.username}
                          className="w-8 h-8 rounded-full"
                        />
                        <span>{friend.username}</span>
                        <Button
                          onClick={() => handleRemoveFriend(friend.id)}
                          className="text-red-500 hover:text-red-700 transition-colors"
                        >
                          Remove
                        </Button>
                      </li>
                    ))}
                  </ul>
                  <h2 className="text-white text-xl">Friend Requests</h2>
                  <ul className="text-white">
                    {localFriendRequests.map((request) => (
                      <li
                        key={request.sender_id}
                        className="flex items-center gap-2"
                      >
                        <span>{request.username}</span>
                        <Button
                          onClick={() =>
                            handleAcceptFriendRequest(request.sender_id)
                          }
                          className="text-green-500 hover:text-green-700 transition-colors"
                        >
                          Accept
                        </Button>
                      </li>
                    ))}
                  </ul>
                  <div className="flex items-center gap-2">
                    <Input
                      value={searchUsername}
                      onChange={(e) => setSearchUsername(e.target.value)}
                      placeholder="Search username"
                      className="text-black"
                    />
                    <Button
                      onClick={handleAddFriend}
                      disabled={isAddingFriend}
                      className="text-white hover:text-blue-500 transition-colors"
                    >
                      Add Friend
                    </Button>
                  </div>
                </div>
              
              <div className="flex flex-col gap-4 w-full">
                {isSpotifyConnected ? (
                  <Button
                    onClick={() => navigate("/playlists")}
                    className="flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 w-full"
                  >
                    <Music className="w-4 h-4" />
                    My Playlists
                  </Button>
                ) : (
                  <Button
                    className="flex items-center justify-center gap-2 bg-gray-600 hover:bg-gray-700 cursor-not-allowed w-full"
                    onClick={() => toast.error("Please connect Spotify to access playlists")}
                  >
                    <Music className="w-4 h-4" />
                    Connect Spotify to Create Playlists
                  </Button>
                )}
                
                <Button
                  onClick={handleLogout}
                  className="text-white transition-colors w-full"
                >
                  Sign out
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}