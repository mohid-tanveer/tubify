import { useEffect, useState, useContext } from "react"
import { AuthContext } from "@/contexts/auth"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { LikedSongsSync } from "@/components/ui/liked-songs-sync"
import { Loader2, ArrowLeft, Music, ChevronLeft, ChevronRight } from "lucide-react"
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

export default function LikedSongs() {
  const { isAuthenticated } = useContext(AuthContext)
  const navigate = useNavigate()
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [songs, setSongs] = useState<LikedSong[]>([])
  const [page, setPage] = useState(1)
  const [totalSongs, setTotalSongs] = useState(0)
  const pageSize = 20
  
  // get liked songs
  useEffect(() => {
    const fetchLikedSongs = async () => {
      try {
        setIsLoading(true)
        
        // get liked songs count
        const countResponse = await api.get("/api/liked-songs/count")
        setTotalSongs(countResponse.data.count || 0)
        
        if (countResponse.data.count > 0) {
          // get liked songs for current page
          const offset = (page - 1) * pageSize
          const songsResponse = await api.get(`/api/liked-songs?limit=${pageSize}&offset=${offset}`)
          setSongs(songsResponse.data)
        }
        
        setIsLoading(false)
      } catch (error) {
        console.error("failed to fetch liked songs:", error)
        setError("failed to load liked songs. please try again.")
        setIsLoading(false)
      }
    }
    
    if (isAuthenticated) {
      fetchLikedSongs()
    }
  }, [isAuthenticated, page, pageSize])
  
  // redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth")
    }
  }, [isAuthenticated, navigate])
  
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
        
        <LikedSongsSync />
        
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
              <h3 className="mt-4 text-xl font-medium text-white">no liked songs yet</h3>
              <p className="mt-2 text-slate-400">
                like songs on spotify to see them here
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
              
              {/* Pagination */}
              {maxPage > 1 && (
                <div className="mt-8 flex items-center justify-center gap-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePrevPage}
                    disabled={page === 1}
                    className="bg-slate-800 hover:bg-slate-700"
                  >
                    <ChevronLeft className="h-4 w-4" />
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
                    <ChevronRight className="h-4 w-4" />
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