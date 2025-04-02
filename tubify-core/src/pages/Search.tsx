import { useState, useEffect } from "react"
import { TubifyTitle } from "@/components/ui/tubify-title"
import api from "@/lib/axios"
import { useNavigate } from "react-router-dom"

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

export default function Search() {
  const [searchQuery, setSearchQuery] = useState("")
  const [userResults, setUserResults] = useState<UserSearchResult[]>([])
  const [playlistResults, setPlaylistResults] = useState<PlaylistSearchResult[]>([])

  const navigate = useNavigate()

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value)
  }

  useEffect(() => {
    if (searchQuery) {
      // run the queries when the searchQuery changes
      const fetchResults = async () => {
        try {
          const userResponse = await api.get<UserSearchResult[]>(`/api/search/users?query=${searchQuery}`)
          const playlistResponse = await api.get<PlaylistSearchResult[]>(`/api/search/playlists?query=${searchQuery}`)
          setUserResults(Array.isArray(userResponse.data) ? userResponse.data : [])
          setPlaylistResults(Array.isArray(playlistResponse.data) ? playlistResponse.data : [])
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
  }, [searchQuery])

  return (
    <div className="overflow-hidden flex flex-col min-h-screen bg-neutral-800">
      <div className="absolute top-0 left-0">
        <TubifyTitle />
      </div>
      
      <div className="flex-1 flex flex-col items-center justify-center gap-4">
        <div className="flex flex-row gap-8 w-full max-w-6xl px-4">
          {/* left column for search input */}
          <div className="flex flex-col items-center gap-4 w-1/3 bg-neutral-700 border border-neutral-600 rounded-lg p-6">
            <h2 className="text-white text-xl">Search</h2>
            <div className="w-full">
              <input
                type="text"
                value={searchQuery}
                onChange={handleInputChange}
                placeholder="Search users or playlists..."
                className="w-full p-3 rounded-md bg-white/10 border-white/20 text-white placeholder:text-white/50 focus:outline-none focus:ring-2 focus:ring-white/20"
              />
            </div>
          </div>

          {/* right column for search results */}
          <div className="flex flex-col gap-4 w-2/3 bg-neutral-700 border border-neutral-600 rounded-lg p-6">
            <h2 className="text-white text-xl">Results</h2>
            
            {/* users section */}
            {userResults.length > 0 && (
              <div className="w-full">
                <h3 className="text-white text-lg mb-4">Users</h3>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {userResults.map((user) => (
                    <div 
                      key={user.id}
                      className="flex flex-col items-center gap-3 bg-slate-700 border border-neutral-600 rounded-lg hover:bg-slate-800 p-4 transition-[color,box-shadow,background-color,border-color] duration-200 cursor-pointer"
                      onClick={() => navigate(`/users/${user.username}`)}
                    >
                      <img
                        src={user.profile_picture}
                        alt={user.username}
                        className="w-20 h-20 rounded-full object-cover"
                      />
                      <span className="text-white text-center font-medium">{user.username}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* playlists section */}
            {playlistResults.length > 0 && (
              <div className="w-full mt-6">
                <h3 className="text-white text-lg mb-4">Playlists</h3>
                <div className="grid grid-cols-1 gap-4">
                  {playlistResults.map((playlist) => (
                    <div
                      key={playlist.public_id}
                      className="flex flex-col gap-2 bg-slate-700 border border-neutral-600 rounded-lg hover:bg-slate-800 p-4 transition-[color,box-shadow,background-color,border-color] duration-200 cursor-pointer"
                      onClick={() => navigate(`/users/playlists/${playlist.public_id}`)}
                    >
                      <span className="text-white font-medium">{playlist.name}</span>
                      {playlist.description && (
                        <p className="text-sm text-neutral-400">{playlist.description}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* no results message */}
            {searchQuery && !userResults.length && !playlistResults.length && (
              <div className="text-center text-neutral-400 py-8">
                No results found
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}