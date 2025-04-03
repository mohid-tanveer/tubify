import { useEffect, useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue 
} from "@/components/ui/select"
import { Loader2, ArrowLeft, Music, Heart, Search } from "lucide-react"
import api from "@/lib/axios"
import { formatDistanceToNow } from "date-fns"
import { Badge } from "@/components/ui/badge"

interface LikedSong {
  id: string
  name: string
  artist: string
  album: string
  duration_ms: number
  album_art_url: string | null
  liked_at: string
  is_shared: boolean
}

interface LikedSongsStats {
  friend_likes_count: number
  shared_likes_count: number
  user_likes_count: number
  friend_unique_count: number
  compatibility_percentage: number
}

export default function FriendLikedSongs() {
  const { username } = useParams<{ username: string }>()
  const navigate = useNavigate()
  
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [songs, setSongs] = useState<LikedSong[]>([])
  const [stats, setStats] = useState<LikedSongsStats | null>(null)
  const [page, setPage] = useState(1)
  const [totalSongs, setTotalSongs] = useState(0)
  const [filterType, setFilterType] = useState("all")  // "all", "shared", "unique"
  const [searchQuery, setSearchQuery] = useState("")
  const [isSearching, setIsSearching] = useState(false)
  const pageSize = 20
  
  // fetch stats on load
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await api.get(`/api/liked-songs/friends/${username}/stats`)
        setStats(response.data)
        setTotalSongs(response.data.friend_likes_count || 0)
      } catch (error) {
        console.error("Failed to fetch stats:", error)
      }
    }
    
    fetchStats()
  }, [username])
  
  // fetch songs when page, filter or search changes
  useEffect(() => {
    const fetchSongs = async () => {
      try {
        setIsLoading(true)
        setError(null)
        
        const offset = (page - 1) * pageSize
        let url = `/api/liked-songs/friends/${username}?limit=${pageSize}&offset=${offset}&filter_type=${filterType}`
        
        if (searchQuery) {
          url += `&search=${encodeURIComponent(searchQuery)}`
        }
        
        const response = await api.get(url)
        setSongs(response.data)
        
        // update total count based on filter
        if (stats) {
          if (filterType === "all") {
            setTotalSongs(stats.friend_likes_count)
          } else if (filterType === "shared") {
            setTotalSongs(stats.shared_likes_count)
          } else if (filterType === "unique") {
            setTotalSongs(stats.friend_unique_count)
          }
        }
      } catch (error) {
        console.error("Failed to fetch liked songs:", error)
        setError("Failed to load liked songs. Please try again.")
      } finally {
        setIsLoading(false)
        setIsSearching(false)
      }
    }
    
    fetchSongs()
  }, [username, page, filterType, searchQuery, stats])
  
  const formatDuration = (ms: number) => {
    const minutes = Math.floor(ms / 60000)
    const seconds = Math.floor((ms % 60000) / 1000)
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }
  
  const maxPage = Math.ceil(totalSongs / pageSize) || 1
  
  const handlePrevPage = () => {
    if (page > 1) {
      setPage(page - 1)
    }
  }
  
  const handleNextPage = () => {
    if (page < maxPage) {
      setPage(page + 1)
    }
  }
  
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setIsSearching(true)
    setPage(1) // reset to first page on new search
  }
  
  const handleFilterChange = (value: string) => {
    setFilterType(value)
    setPage(1) // reset to first page on filter change
  }
  
  return (
    <div className="scrollable-page bg-linear-to-b from-slate-900 to-black">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="pt-6 pb-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/users/${username}`)}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            back to profile
          </Button>
        </div>

        <div className="mb-8">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl md:text-3xl font-bold text-white">
              {username}'s liked songs
            </h1>
            <Heart className="h-5 w-5 text-pink-400" />
          </div>
          
          {stats && (
            <p className="mt-2 text-slate-400">
              You share {stats.shared_likes_count} songs ({stats.compatibility_percentage}% compatibility)
            </p>
          )}
        </div>
        
        {/* search and filter controls */}
        <div className="mb-6 flex flex-col md:flex-row gap-4">
          <form onSubmit={handleSearch} className="flex-1 flex gap-2">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by song, artist or album..."
              className="flex-1"
            />
            <Button type="submit" disabled={isSearching}>
              {isSearching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
            </Button>
          </form>
          
          <div className="w-full md:w-48">
            <Select value={filterType} onValueChange={handleFilterChange}>
              <SelectTrigger>
                <SelectValue placeholder="Filter songs" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All songs</SelectItem>
                <SelectItem value="shared">Shared songs only</SelectItem>
                <SelectItem value="unique">Unique to friend</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <div className="mt-8">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
            </div>
          ) : error ? (
            <div className="rounded-lg border border-red-800 bg-red-900/20 p-4 text-center">
              <p className="text-red-400">{error}</p>
            </div>
          ) : songs.length === 0 ? (
            <div className="mt-8 rounded-lg border border-slate-800 bg-slate-900/20 p-8 text-center">
              <Music className="mx-auto h-12 w-12 text-slate-600" />
              <h3 className="mt-4 text-xl font-medium text-white">No liked songs found</h3>
              <p className="mt-2 text-slate-400">
                {searchQuery ? "Try a different search term" : 
                  filterType !== "all" ? "Try a different filter" : "This user hasn't liked any songs yet"}
              </p>
            </div>
          ) : (
            <>
              <div className="mb-4 grid grid-cols-12 gap-4 border-b border-slate-800 pb-2 text-xs md:text-sm font-medium text-slate-500">
                <div className="col-span-1">#</div>
                <div className="col-span-5">title</div>
                <div className="col-span-3">artist</div>
                <div className="col-span-2">album</div>
                <div className="col-span-1 text-right">duration</div>
              </div>
              
              <div className="space-y-2">
                {songs.map((song, index) => (
                  <div 
                    key={song.id}
                    className={`grid grid-cols-12 gap-4 rounded-md py-2 px-2 text-white hover:bg-slate-800/50 ${
                      song.is_shared ? "border-l-2 border-pink-500" : ""
                    }`}
                  >
                    <div className="col-span-1 flex items-center text-slate-400">
                      {(page - 1) * pageSize + index + 1}
                    </div>
                    <div className="col-span-5 flex items-center">
                      <div 
                        className="mr-3 h-10 w-10 flex-shrink-0 overflow-hidden rounded-md"
                        style={{ backgroundColor: 'rgba(25, 25, 25, 0.6)' }}
                      >
                        {song.album_art_url ? (
                          <img
                            src={song.album_art_url}
                            alt={song.name}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center">
                            <Music className="h-5 w-5 text-slate-500" />
                          </div>
                        )}
                      </div>
                      <div className="overflow-hidden">
                        <div className="flex items-center gap-2">
                          <p className="truncate font-medium">{song.name}</p>
                          {song.is_shared && (
                            <Badge 
                              variant="outline" 
                              className="border-pink-500 text-pink-500 hover:bg-pink-500/10"
                            >
                              <Heart className="h-3 w-3 mr-1" />
                              Both
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-slate-400">
                          liked {formatDistanceToNow(new Date(song.liked_at))} ago
                        </p>
                      </div>
                    </div>
                    <div className="col-span-3 flex items-center">
                      <span className="truncate">{song.artist}</span>
                    </div>
                    <div className="col-span-2 flex items-center">
                      <span className="truncate">{song.album}</span>
                    </div>
                    <div className="col-span-1 flex items-center justify-end text-slate-400">
                      {formatDuration(song.duration_ms)}
                    </div>
                  </div>
                ))}
              </div>
              
              {/* pagination */}
              {maxPage > 1 && (
                <div className="mt-8 flex items-center justify-center gap-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePrevPage}
                    disabled={page === 1}
                    className="bg-slate-800 hover:bg-slate-700"
                  >
                    <ArrowLeft className="h-4 w-4" />
                  </Button>
                  
                  <span className="text-sm text-slate-400">
                    page {page} of {maxPage}
                  </span>
                  
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleNextPage}
                    disabled={page === maxPage}
                    className="bg-slate-800 hover:bg-slate-700"
                  >
                    <ArrowLeft className="h-4 w-4 rotate-180" />
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
} 