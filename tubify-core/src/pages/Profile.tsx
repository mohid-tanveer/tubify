import { useContext, useEffect, useState, useRef } from "react"
import { AuthContext } from "@/contexts/auth"
import { TubifyTitle } from "@/components/ui/tubify-title"
import api from "@/lib/axios"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Pencil, X, Check } from "lucide-react"
import { toast } from "sonner"
import { z } from "zod"
import { Icons } from "@/components/icons"

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

export default function Profile() {
  const { isAuthenticated, logout } = useContext(AuthContext)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState<{
    username: string
    bio: string
  }>({
    username: "",
    bio: "",
  })
  const [isSaving, setIsSaving] = useState(false)
  const [isCheckingUsername, setIsCheckingUsername] = useState(false)
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const usernameCheckTimeout = useRef<NodeJS.Timeout>()

  const fetchProfile = async () => {
    try {
      setIsLoading(true)
      const response = await api.get("/api/profile")
      setProfile(response.data)
      setEditForm({
        username: response.data.user_name,
        bio: response.data.bio,
      })
    } catch (error) {
      console.error("failed to fetch profile:", error)
      toast.error("Failed to load profile")
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (isAuthenticated) {
      fetchProfile()
    }
  }, [isAuthenticated])

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
        console.error("Failed to check username:", error)
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
      const response = await api.put("/api/profile", editForm)
      setProfile(response.data)
      setIsEditing(false)
      toast.success("Profile updated successfully")
    } catch (error) {
      console.error("failed to update profile:", error)
      toast.error("Failed to update profile")
    } finally {
      setIsSaving(false)
    }
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

  if (isLoading) {
    return (
      <div className="overflow-hidden flex flex-col min-h-screen">
        <div className="absolute top-0 left-0">
          <TubifyTitle />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-white">Loading...</p>
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
              <Button
                onClick={logout}
                className="text-white hover:text-red-500 transition-colors"
              >
                Sign out
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}