import { useEffect, useState, useRef, useCallback } from "react"
import { useParams, useNavigate, useLoaderData, useRevalidator } from "react-router-dom"
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

interface LikedSongsData {
  songs: LikedSong[]
  totalCount: number
  stats?: LikedSongsStats
  error?: string
}

export default function FriendLikedSongs() {
  const { username } = useParams<{ username: string }>()
  const navigate = useNavigate()
  const initialData = useLoaderData() as LikedSongsData
  const revalidator = useRevalidator()
  
  // state for songs and stats
  const [songs, setSongs] = useState<LikedSong[]>(initialData.songs || [])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(initialData.error || null)
  const stats = initialData.stats
  
  // state for pagination and filtering
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(true)
  const [filterType, setFilterType] = useState<string>("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const loadingRef = useRef<HTMLDivElement>(null)
  const pageSize = 20
  
  // fetch songs with filter and search
  const fetchSongs = useCallback(async (
    pageNum: number, 
    filter: string, 
    search: string, 
    isNewQuery = false
  ) => {
    if (!username) return
    
    try {
      setIsLoading(true)
      setError(null)
      
      const offset = (pageNum - 1) * pageSize
      let url = `/api/liked-songs/friends/${username}?limit=${pageSize}&offset=${offset}&filter_type=${filter}`
      
      if (search) {
        url += `&search=${encodeURIComponent(search)}`
      }
      
      const response = await api.get(url)
      const newSongs = response.data
      
      if (isNewQuery) {
        setSongs(newSongs)
      } else {
        setSongs(prev => [...prev, ...newSongs])
      }
      
      // check if there are more songs to load
      setHasMore(newSongs.length === pageSize)
      setPage(pageNum)
    } catch (error) {
      console.error("failed to fetch songs:", error)
      setError("failed to load songs")
    } finally {
      setIsLoading(false)
    }
  }, [username, pageSize, setIsLoading, setError, setSongs, setHasMore, setPage])
  
  // handle search input debounce
  useEffect(() => {
    const timerId = setTimeout(() => {
      if (searchQuery !== debouncedQuery) {
        setDebouncedQuery(searchQuery)
        // reset songs and pagination when search changes
        setSongs([])
        setPage(1)
        setHasMore(true)
        fetchSongs(1, filterType, searchQuery, true)
      }
    }, 500)
    
    return () => clearTimeout(timerId)
  }, [searchQuery, debouncedQuery, filterType, fetchSongs, setSongs, setPage, setHasMore])
  
  // handle filter change
  const handleFilterChange = (value: string) => {
    if (value !== filterType) {
      setFilterType(value)
      // reset songs and pagination when filter changes
      setSongs([])
      setPage(1) 
      setHasMore(true)
      fetchSongs(1, value, debouncedQuery, true)
    }
  }
  
  // function to load more songs
  const loadMore = useCallback(() => {
    if (isLoading || !hasMore) return
    
    const nextPage = page + 1
    fetchSongs(nextPage, filterType, debouncedQuery)
  }, [isLoading, hasMore, page, filterType, debouncedQuery, fetchSongs])
  
  // load more when scrolling to bottom
  useEffect(() => {
    if (!hasMore || isLoading) return
    
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadMore()
        }
      },
      { threshold: 0.1 }
    )
    
    const currentRef = loadingRef.current
    if (currentRef) {
      observer.observe(currentRef)
    }
    
    return () => {
      if (currentRef) {
        observer.unobserve(currentRef)
      }
    }
  }, [hasMore, isLoading, loadMore])
  
  // handle search input change
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value)
  }
  
  // format album title for display
  const formatAlbumTitle = (title: string) => {
    return title
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
        <div className="flex flex-col gap-4 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              type="text"
              placeholder="Search songs..."
              className="pl-9"
              value={searchQuery}
              onChange={handleSearchChange}
            />
          </div>
          
          <div className="w-full sm:w-48">
            <Select value={filterType} onValueChange={(value) => handleFilterChange(value)}>
              <SelectTrigger className="w-full">
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
          {revalidator.state === "loading" ? (
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
                <div className="col-span-3">album</div>
              </div>
              
              <div className="space-y-2">
                {songs.map((song, index) => (
                  <div 
                    key={song.id}
                    className="grid grid-cols-12 gap-4 rounded-md py-2 px-2 text-white hover:bg-slate-800/50"
                  >
                    <div className="col-span-1 flex items-center text-slate-400">
                      {index + 1}
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
                    <div className="col-span-3 flex items-center">
                      <span className="truncate">{formatAlbumTitle(song.album)}</span>
                    </div>
                  </div>
                ))}
              </div>
              
              {/* loading indicator for infinite scroll */}
              <div 
                ref={loadingRef} 
                className="mt-8 flex items-center justify-center py-4"
              >
                {isLoading ? (
                  <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                ) : hasMore ? (
                  <div className="h-10" />
                ) : (
                  <p className="text-sm text-slate-500">no more songs to load</p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
} 