import { useState, useRef, useEffect, useCallback } from "react"
import { useNavigate, useLoaderData, useRevalidator } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LikedSongsSync } from "@/components/ui/liked-songs-sync"
import { Loader2, ArrowLeft, Music, Search } from "lucide-react"
import api from "@/lib/axios"
import { formatDistanceToNow } from "date-fns"

interface LikedSong {
  id: string
  name: string
  artist: string
  album: string
  duration_ms: number
  album_art_url: string | null
  liked_at: string
}

interface LikedSongsData {
  songs: LikedSong[]
  totalCount: number
  error?: string
}

export default function LikedSongs() {
  const navigate = useNavigate()
  const initialData = useLoaderData() as LikedSongsData
  const [songs, setSongs] = useState<LikedSong[]>(initialData.songs || [])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(initialData.error || null)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(true)
  const pageSize = 20
  const loadingRef = useRef<HTMLDivElement>(null)
  const revalidator = useRevalidator()
  const [searchQuery, setSearchQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  
  // fetch songs with search query
  const fetchSongs = useCallback(async (
    pageNum: number,
    search: string,
    isNewQuery = false
  ) => {
    try {
      setIsLoading(true)
      setError(null)
      
      const offset = (pageNum - 1) * pageSize
      let url = `/api/liked-songs?limit=${pageSize}&offset=${offset}`
      
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
  }, [pageSize])
  
  // handle search input debounce
  useEffect(() => {
    const timerId = setTimeout(() => {
      if (searchQuery !== debouncedQuery) {
        setDebouncedQuery(searchQuery)
        // reset songs and pagination when search changes
        setSongs([])
        setPage(1)
        setHasMore(true)
        fetchSongs(1, searchQuery, true)
      }
    }, 500)
    
    return () => clearTimeout(timerId)
  }, [searchQuery, debouncedQuery, fetchSongs])
  
  // load more songs
  const loadMore = useCallback(async () => {
    if (isLoading || !hasMore) return
    
    const nextPage = page + 1
    fetchSongs(nextPage, debouncedQuery)
  }, [isLoading, hasMore, page, debouncedQuery, fetchSongs])
  
  // load more songs when scrolling
  useEffect(() => {
    if (!hasMore) return
    
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !isLoading) {
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
  
  const formatDuration = (ms: number) => {
    const minutes = Math.floor(ms / 60000)
    const seconds = Math.floor((ms % 60000) / 1000)
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }

  // reload liked songs data
  const refreshData = () => {
    revalidator.revalidate()
  }
  
  // handle search input change
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value)
  }
  
  return (
    <div className="scrollable-page bg-linear-to-b from-slate-900 to-black">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="pt-6 pb-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/profile")}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            back to profile
          </Button>
        </div>

        <div className="mb-8">
          <h1 className="text-2xl md:text-3xl font-bold text-white">liked songs</h1>
          <p className="mt-2 text-slate-400">view and browse your spotify liked songs</p>
        </div>
        
        <LikedSongsSync onSyncComplete={refreshData} />
        
        {/* search input */}
        <div className="relative flex-1 mt-6">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            type="text"
            placeholder="Search songs..."
            className="pl-9"
            value={searchQuery}
            onChange={handleSearchChange}
          />
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
              <h3 className="mt-4 text-xl font-medium text-white">no liked songs found</h3>
              <p className="mt-2 text-slate-400">
                {searchQuery ? "try a different search term" : "like songs on spotify to see them here"}
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
                        <p className="truncate font-medium">{song.name}</p>
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