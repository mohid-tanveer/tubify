import { useState, useEffect, useContext } from "react"
import { TubifyTitle } from "@/components/ui/tubify-title"
import api, { AxiosError } from "@/lib/axios"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { SearchIcon, UserPlusIcon, CheckIcon } from "lucide-react"
import { AuthContext } from "@/contexts/auth"

// define interfaces for search results
interface UserSearchResult {
  id: number
  username: string
  profile_picture: string
}

interface PlaylistSearchResult {
  public_id: string
  name: string
  description?: string
}

interface Friend {
  id: number
  username: string
  profile_picture: string
}

export default function Search() {
  const [searchQuery, setSearchQuery] = useState("")
  const [userResults, setUserResults] = useState<UserSearchResult[]>([])
  const [playlistResults, setPlaylistResults] = useState<
    PlaylistSearchResult[]
  >([])
  const [isAddingFriend, setIsAddingFriend] = useState<{
    [key: number]: boolean
  }>({})
  const [friends, setFriends] = useState<Friend[]>([])
  const [loadingFriends, setLoadingFriends] = useState(true)
  const { user } = useContext(AuthContext)

  const navigate = useNavigate()

  // fetch current friends on component mount
  useEffect(() => {
    const fetchFriends = async () => {
      try {
        setLoadingFriends(true)
        const response = await api.get('/api/profile/friends')
        if (Array.isArray(response.data)) {
          setFriends(response.data)
        }
      } catch (error) {
        console.error("Error fetching friends:", error)
      } finally {
        setLoadingFriends(false)
      }
    }
    
    fetchFriends()
  }, [])

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value)
  }

  useEffect(() => {
    if (searchQuery) {
      // run the queries when the searchQuery changes
      const fetchResults = async () => {
        try {
          const userResponse = await api.get<UserSearchResult[]>(
            `/api/search/users?query=${searchQuery}`,
          )
          const playlistResponse = await api.get<PlaylistSearchResult[]>(
            `/api/search/playlists?query=${searchQuery}`,
          )
          
          // Filter out the current user from search results
          let filteredUsers = Array.isArray(userResponse.data) ? userResponse.data : []
          if (user && user.id) {
            filteredUsers = filteredUsers.filter(result => result.id !== user.id)
          }
          
          setUserResults(filteredUsers)
          setPlaylistResults(
            Array.isArray(playlistResponse.data) ? playlistResponse.data : [],
          )
        } catch (error) {
          console.error("Error fetching search results:", error)
          setUserResults([])
          setPlaylistResults([])
        }
      }

      fetchResults()
    } else {
      setUserResults([])
      setPlaylistResults([])
    }
  }, [searchQuery, user])

  const handleAddFriend = async (username: string, userId: number) => {
    try {
      setIsAddingFriend((prev) => ({ ...prev, [userId]: true }))
      await api.post(`/api/profile/add-friend/${username}`)
      toast.success("Friend request sent!")
    } catch (error) {
      const axiosError = error as AxiosError<{ detail: string }>
      if (axiosError.response?.data?.detail) {
        toast.error(axiosError.response.data.detail)
      } else {
        toast.error("Failed to send friend request")
      }
    } finally {
      setIsAddingFriend((prev) => ({ ...prev, [userId]: false }))
    }
  }

  // check if user is already a friend
  const isUserAlreadyFriend = (userId: number) => {
    return friends.some(friend => friend.id === userId)
  }

  return (
    <div className="scrollable-page bg-linear-to-b from-slate-900 to-black">
      <div className="absolute top-0 left-0">
        <TubifyTitle />
      </div>

      <div className="flex items-center justify-center min-h-screen">
        <div className="mx-auto max-w-7xl w-full px-4 sm:px-6 lg:px-8 pt-16 pb-8">
          <div className="flex flex-col sm:flex-row gap-6 w-full">
            {/* search input section - full width on mobile, 1/3 on desktop */}
            <div className="flex flex-col items-center gap-4 w-full sm:w-1/3 bg-slate-800/60 border border-slate-700 rounded-xl p-5">
              <h2 className="text-lg font-semibold text-white flex items-center">
                <SearchIcon className="w-5 h-5 mr-2" />
                Search
              </h2>
              <div className="w-full">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={handleInputChange}
                  placeholder="Search users or playlists..."
                  className="w-full p-3 rounded-md bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500"
                />
              </div>
            </div>

            {/* results section - full width on mobile, 2/3 on desktop */}
            <div className="flex flex-col gap-4 w-full sm:w-2/3 bg-slate-800/60 border border-slate-700 rounded-xl p-5">
              <h2 className="text-lg font-semibold text-white">results</h2>

              {/* users section */}
              {userResults.length > 0 && (
                <div className="w-full">
                  <h3 className="text-white text-md mb-4 border-b border-slate-700 pb-2">users</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 max-h-[260px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-600 scrollbar-track-slate-800">
                    {userResults.map((user) => (
                      <div
                        key={user.id}
                        className="flex flex-col items-center gap-2 bg-slate-700/50 border border-slate-600 rounded-lg hover:bg-slate-700 p-3 transition-colors duration-200"
                      >
                        <div
                          className="flex flex-col items-center gap-2 cursor-pointer w-full"
                          onClick={() => navigate(`/users/${user.username}`)}
                        >
                          <img
                            src={user.profile_picture}
                            alt={user.username}
                            className="w-12 h-12 sm:w-16 sm:h-16 rounded-full object-cover border-2 border-slate-600"
                          />
                          <span className="text-white text-center font-medium truncate w-full">
                            {user.username}
                          </span>
                        </div>
                        {isUserAlreadyFriend(user.id) ? (
                          <Button 
                            variant="outline" 
                            size="sm"
                            className="w-full mt-1 bg-slate-700 border-slate-600 cursor-default opacity-70 h-7 text-xs"
                            disabled
                          >
                            <CheckIcon className="mr-2 h-4 w-4" />
                            Already Friends
                          </Button>
                        ) : (
                          <Button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleAddFriend(user.username, user.id)
                            }}
                            disabled={isAddingFriend[user.id]}
                            variant="outline"
                            size="sm"
                            className="w-full mt-1 bg-slate-700/50 border-slate-600 hover:bg-slate-700 h-7 text-xs"
                          >
                            {isAddingFriend[user.id] ? "Sending..." : (
                              <>
                                <UserPlusIcon className="mr-2 h-4 w-4" />
                                Add Friend
                              </>
                            )}
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* playlists section */}
              {playlistResults.length > 0 && (
                <div className="w-full mt-4">
                  <h3 className="text-white text-md mb-4 border-b border-slate-700 pb-2">playlists</h3>
                  <div className="grid grid-cols-1 gap-3 max-h-[180px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-600 scrollbar-track-slate-800">
                    {playlistResults.map((playlist) => (
                      <div
                        key={playlist.public_id}
                        className="flex flex-col gap-1 bg-slate-700/50 border border-slate-600 rounded-lg hover:bg-slate-700 p-3 transition-colors duration-200 cursor-pointer"
                        onClick={() =>
                          navigate(`/users/playlists/${playlist.public_id}`)
                        }
                      >
                        <span className="text-white font-medium truncate">
                          {playlist.name}
                        </span>
                        {playlist.description && (
                          <p className="text-sm text-slate-400 truncate">
                            {playlist.description}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* no results message */}
              {searchQuery && !userResults.length && !playlistResults.length && (
                <div className="text-center text-slate-400 py-8 bg-slate-800/30 border border-slate-700/50 rounded-lg">
                  no results found
                </div>
              )}
              
              {/* loading state */}
              {searchQuery && loadingFriends && (
                <div className="text-center text-slate-400 text-sm">
                  Loading friends list...
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
