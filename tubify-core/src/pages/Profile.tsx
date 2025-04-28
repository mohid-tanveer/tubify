import { useContext, useEffect, useState, useRef } from "react"
import { AuthContext } from "@/contexts/auth"
import { TubifyTitle } from "@/components/ui/tubify-title"
import api, { AxiosError } from "@/lib/axios"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Pencil, X, Check, Music } from "lucide-react"
import { toast } from "sonner"
import { z } from "zod"
import { Icons } from "@/components/icons"
import { useNavigate, useLoaderData } from "react-router-dom"
import { ProfileData } from "@/loaders/user-loaders"
import { LikedSongsSync } from "@/components/ui/liked-songs-sync"

const profileSchema = z.object({
  username: z
    .string()
    .min(3, "username must be at least 3 characters")
    .max(50, "username must be less than 50 characters")
    .regex(
      /^[a-zA-Z0-9._-]+$/,
      "username can only contain letters, numbers, periods, underscores, and hyphens",
    ),
  bio: z.string().max(500, "bio must be less than 500 characters"),
})

interface Profile {
  user_name: string
  profile_picture: string
  bio: string
}

interface Friend {
  id: number
  username: string
  profile_picture: string
}

interface FriendRequest {
  sender_id: number
  receiver_id: number
  status: string
  username: string
}

export default function Profile() {
  const { isAuthenticated, logout } = useContext(AuthContext)
  const { profile, friends, friendRequests, isSpotifyConnected, likedSongs } =
    useLoaderData() as ProfileData
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
  const [localFriendRequests, setLocalFriendRequests] =
    useState<FriendRequest[]>(friendRequests)

  const handleAddFriend = async () => {
    try {
      setIsAddingFriend(true)
      await api.post(`/api/profile/add-friend/${searchUsername}`)
      toast.success("Friend request sent!")

      // clear the search input
      setSearchUsername("")
    } catch (error) {
      if (process.env.NODE_ENV === "development") {
        console.error("failed to add friend:", error)
      }

      // display the specific error message from the backend
      const axiosError = error as AxiosError<{ detail: string }>
      if (axiosError.response?.data?.detail) {
        toast.error(axiosError.response.data.detail)
      } else {
        toast.error("Failed to send friend request.")
      }
    } finally {
      setIsAddingFriend(false)
    }
  }

  const handleAcceptFriendRequest = async (senderId: number) => {
    try {
      const response = await api.post(
        `/api/profile/accept-friend-request/${senderId}`,
      )
      toast.success("Friend request accepted!")

      // get the accepted friend from the response
      const acceptedFriend = response.data

      // update local state
      setLocalFriends((prevFriends) => [...prevFriends, acceptedFriend])
      setLocalFriendRequests((prevRequests) =>
        prevRequests.filter((request) => request.sender_id !== senderId),
      )
    } catch (error) {
      console.error("failed to accept friend request:", error)

      // display the specific error message from the backend
      const axiosError = error as AxiosError<{ detail: string }>
      if (axiosError.response?.data?.detail) {
        toast.error(axiosError.response.data.detail)
      } else {
        toast.error("Failed to accept friend request.")
      }
    }
  }

  const handleRejectFriendRequest = async (senderId: number) => {
    try {
      await api.post(`/api/profile/reject-friend-request/${senderId}`)
      toast.success("Friend request rejected")

      // update local state by removing the rejected request
      setLocalFriendRequests((prevRequests) =>
        prevRequests.filter((request) => request.sender_id !== senderId),
      )
    } catch (error) {
      console.error("failed to reject friend request:", error)

      // display the specific error message from the backend
      const axiosError = error as AxiosError<{ detail: string }>
      if (axiosError.response?.data?.detail) {
        toast.error(axiosError.response.data.detail)
      } else {
        toast.error("Failed to reject friend request.")
      }
    }
  }

  const handleRemoveFriend = async (friendId: number) => {
    try {
      await api.post(`/api/profile/remove-friend/${friendId}`)
      toast.success("Friend removed!")
      // update local friends state by filtering out the removed friend
      setLocalFriends((prevFriends) =>
        prevFriends.filter((friend) => friend.id !== friendId),
      )
    } catch (error) {
      console.error("failed to remove friend:", error)

      // display the specific error message from the backend
      const axiosError = error as AxiosError<{ detail: string }>
      if (axiosError.response?.data?.detail) {
        toast.error(axiosError.response.data.detail)
      } else {
        toast.error("Failed to remove friend.")
      }
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

  // redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth")
    }
  }, [isAuthenticated, navigate])

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
    <div className="overflow-hidden flex flex-col min-h-screen bg-neutral-800">
      <div className="absolute top-0 left-0">
        <TubifyTitle />
      </div>
      <div className="flex-1 flex flex-col items-center justify-center gap-4 p-4 mt-16 sm:mt-0">
        <div className="flex flex-col sm:flex-row gap-8 w-full max-w-6xl px-4">
          {/* profile section - full width on mobile, 1/3 on desktop */}
          <div className="flex flex-col items-center gap-4 w-full sm:w-1/3 bg-neutral-700 border border-neutral-600 rounded-lg p-6 relative h-fit sm:self-center">
            <Button
              onClick={handleEdit}
              variant="ghost"
              size="icon"
              className="absolute top-4 right-4 text-white hover:bg-white/30"
            >
              <Pencil className="w-4 h-4" />
            </Button>
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
                        className={`bg-white/10 border-white/20 text-white ${usernameError ? "border-red-500" : ""}`}
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
                        className="bg-white/10 border-white/20 text-white min-h-[100px] break-all overflow-hidden"
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
                    variant="spotify"
                  >
                    <Check className="w-4 h-4 mr-2" />
                    {isSaving ? "Saving..." : "Save"}
                  </Button>
                  <Button
                    onClick={handleCancel}
                    disabled={isSaving}
                    variant="destructive"
                  >
                    <X className="w-4 h-4 mr-2" />
                    Cancel
                  </Button>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center w-full">
                <div className="flex flex-col items-center flex-grow mb-8">
                  <h2 className="text-white text-2xl mb-4">
                    {profile.user_name}
                  </h2>
                  <p className="text-white text-center break-all whitespace-pre-wrap max-w-full overflow-hidden">
                    {profile.bio || "No bio yet"}
                  </p>
                </div>
                <Button
                  onClick={handleLogout}
                  variant="destructive"
                  className="w-full sm:w-auto px-8"
                >
                  Sign out
                </Button>
              </div>
            )}
          </div>

          {/* friends section - full width on mobile, 2/3 on desktop */}
          <div className="flex flex-col items-center gap-4 w-full sm:w-2/3 bg-neutral-700 border border-neutral-600 rounded-lg p-6">
            <h2 className="text-white text-xl">Friends</h2>
            <ul className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4 w-full">
              {localFriends.map((friend) => (
                <li
                  key={friend.id}
                  className="flex flex-col items-center gap-3 bg-slate-700 border border-neutral-600 rounded-lg hover:bg-slate-800 p-4 transition-[color,box-shadow,background-color,border-color] duration-200"
                >
                  <div
                    className="flex flex-col items-center gap-3 cursor-pointer w-full"
                    onClick={() => navigate(`/users/${friend.username}`)}
                  >
                    <img
                      src={friend.profile_picture}
                      alt={friend.username}
                      className="w-20 h-20 rounded-full object-cover"
                    />
                    <span className="text-white text-center font-medium">
                      {friend.username}
                    </span>
                  </div>
                  <Button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRemoveFriend(friend.id)
                    }}
                    variant="destructive"
                    className="w-full"
                  >
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
            <h2 className="text-white text-xl">Friend Requests</h2>
            <ul className="text-white">
              {localFriendRequests.map((request) => (
                <li key={request.sender_id} className="flex items-center gap-2">
                  <span>{request.username}</span>
                  <Button
                    onClick={() => handleAcceptFriendRequest(request.sender_id)}
                    variant="spotify"
                  >
                    Accept
                  </Button>
                  <Button
                    onClick={() => handleRejectFriendRequest(request.sender_id)}
                    variant="destructive"
                  >
                    Reject
                  </Button>
                </li>
              ))}
            </ul>
            <div className="flex items-center gap-2">
              <Input
                value={searchUsername}
                onChange={(e) => setSearchUsername(e.target.value)}
                placeholder="Search username"
              />
              <Button
                onClick={handleAddFriend}
                disabled={isAddingFriend}
                className="text-slate-700 transition-colors"
              >
                Add Friend
              </Button>
            </div>

            <div className="flex flex-col gap-4 w-full">
              {isSpotifyConnected ? (
                <>
                  <Button
                    onClick={() => navigate("/playlists")}
                    variant="spotify"
                    className="flex items-center justify-center gap-2 w-full"
                  >
                    <Icons.spotify className="mr-2 h-4 w-4" />
                    My Playlists
                  </Button>
                  <Button
                    onClick={() => navigate("/recently-played")}
                    className="flex items-center justify-center gap-2 w-full"
                  >
                    View Recently Played Tracks
                  </Button>
                  <Button
                    onClick={() => navigate("/listening-habits")}
                    className="flex items-center justify-center gap-2 w-full"
                  >
                    <Icons.chartBarBig className="mr-2 h-4 w-4" />
                    View Listening Habits
                  </Button>
                  <LikedSongsSync
                    initialStatus={
                      profile && profile.user_name && likedSongs
                        ? {
                            syncStatus: likedSongs.syncStatus,
                            lastSynced: likedSongs.lastSynced,
                            count: likedSongs.count,
                          }
                        : undefined
                    }
                  />

                  {likedSongs && likedSongs.count > 0 && (
                    <Button
                      onClick={() => navigate("/liked-songs")}
                      variant="outline"
                      className="flex items-center justify-center gap-2 w-full"
                    >
                      <Music className="mr-2 h-4 w-4" />
                      View Liked Songs
                    </Button>
                  )}
                </>
              ) : (
                <Button
                  className="flex items-center justify-center gap-2 bg-gray-600 hover:bg-gray-700 cursor-not-allowed w-full"
                  onClick={() =>
                    toast.error("Please connect Spotify to access playlists")
                  }
                >
                  <Icons.spotify className="mr-2 h-4 w-4" />
                  Connect Spotify to Create Playlists
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
