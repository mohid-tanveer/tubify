import { useState, useEffect } from "react"
import { TubifyTitle } from "@/components/ui/tubify-title"
import api from "@/lib/axios"
import { Link } from "react-router-dom"

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

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value)
  }

  useEffect(() => {
    if (searchQuery) {
      // Run the queries when the searchQuery changes
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
    <div className="h-screen bg-linear-to-b from-gray-950 to-gray-700">
      <div className="overflow-hidden flex flex-col min-h-screen">
        <div className="absolute top-0 left-0">
          <TubifyTitle />
        </div>

        <div className="flex flex-col items-center gap-40">
          <h1 className="text-white text-2xl tracking-normal py-10">Search</h1>
        </div>

        <div className="flex-1 flex items-top justify-center">
          <div className="flex flex-col items-center gap-4">
            <form>
              <div className="mb-6">
                <label
                  htmlFor="searchQuery"
                  className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                >
                  Search Query
                </label>
                <input
                  type="text"
                  id="searchQuery"
                  value={searchQuery}
                  onChange={handleInputChange}
                  className="block w-full p-3 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 text-base focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                />
              </div>
            </form>

            <div className="w-full">
              <h2 className="text-white text-xl">Results:</h2>
              <div className="mt-4">
                {userResults.length > 0 && (
                  <div className="bg-gray-800 p-4 rounded-lg text-white">
                    <h3 className="text-lg">Users:</h3>
                    {userResults.map((user) => (
                      <div key={user.id} className="p-2 border-b border-gray-700 flex items-center gap-3">
                        <img src={user.profile_picture} alt={user.username} className="w-10 h-10 rounded-full" />
                        <Link to={`/users/${user.username}`}>{user.username}</Link>
                      </div>
                    ))}
                  </div>
                )}
                {playlistResults.length > 0 && (
                  <div className="bg-gray-800 p-4 rounded-lg text-white mt-4">
                    <h3 className="text-lg">Playlists:</h3>
                    {playlistResults.map((playlist) => (
                      <div key={playlist.public_id} className="p-2 border-b border-gray-700">
                        <Link to={`/public/playlists/${playlist.public_id}`}>{playlist.name}</Link>
                        {playlist.description && <p className="text-sm text-gray-400">{playlist.description}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}