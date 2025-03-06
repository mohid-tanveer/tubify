import { useState, useEffect, useCallback } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Search, Plus, Music, Loader2 } from "lucide-react"
import api, { AxiosError } from "@/lib/axios"
import { toast } from "sonner"

// song type from spotify search
interface SpotifySearchResult {
  spotify_id: string
  name: string
  artist: string
  album: string
  duration_ms: number
  preview_url?: string
  album_art_url?: string
  spotify_uri: string
  spotify_url: string
}

// format duration from ms to mm:ss
const formatDuration = (ms: number) => {
  const minutes = Math.floor(ms / 60000)
  const seconds = Math.floor((ms % 60000) / 1000)
  return `${minutes}:${seconds.toString().padStart(2, "0")}`
}

interface SongSearchProps {
  playlistPublicId: string
  onSongAdded: () => void
}

export function SongSearchSkeleton() {
  return (
    <div className="space-y-4">
      <div className="relative">
        <Loader2 className="absolute left-3 top-1/4 h-4 w-4 animate-spin text-slate-400" />
      </div>
    </div>
  )
}

export function SongSearch({ playlistPublicId, onSongAdded }: SongSearchProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<SpotifySearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [isAdding, setIsAdding] = useState<Record<string, boolean>>({})

  const handleSearch = useCallback(async () => {
    if (!searchQuery || searchQuery.length < 2) return

    try {
      setIsSearching(true)
      const response = await api.get(`/api/songs/search?query=${encodeURIComponent(searchQuery)}`)
      setSearchResults(response.data)
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error("failed to search songs:", error)
      }
      toast.error("failed to search songs")
    } finally {
      setIsSearching(false)
    }
  }, [searchQuery])

  // debounce search
  useEffect(() => {
    if (!searchQuery || searchQuery.length < 2) {
      setSearchResults([])
      return
    }

    const timer = setTimeout(() => {
      handleSearch()
    }, 500)

    return () => clearTimeout(timer)
  }, [searchQuery, handleSearch])

  const handleAddSong = async (song: SpotifySearchResult) => {
    try {
      setIsAdding(prev => ({ ...prev, [song.spotify_id]: true }))
      
      // prepare song data for api
      const songData = {
        spotify_id: song.spotify_id,
        name: song.name,
        artist: song.artist,
        album: song.album,
        duration_ms: song.duration_ms,
        preview_url: song.preview_url,
        album_art_url: song.album_art_url,
        spotify_uri: song.spotify_uri,
        spotify_url: song.spotify_url
      }

      // add song to playlist
      await api.post(`/api/playlists/${playlistPublicId}/songs`, [songData])
      
      // notify parent component
      onSongAdded()
      
      // show success message
      toast.success(`added "${song.name}" to playlist`)
      
      // clear search results
      setSearchQuery("")
      setSearchResults([])
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error("failed to add song:", error)
      }
      if (error instanceof AxiosError && error.response?.status === 409) {
        toast.error("song already in playlist")
        return
      }
      toast.error("failed to add song to playlist")
    } finally {
      setIsAdding(prev => ({ ...prev, [song.spotify_id]: false }))
    }
  }

  return (
    <div className="space-y-4">
      <div className="relative">
        {isSearching ? (
          <Loader2 className="absolute left-3 top-1/4 h-4 w-4 animate-spin text-slate-400" />
        ) : (
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        )}
        <Input
          type="text"
          placeholder="search for songs on spotify..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>


      {searchResults.length > 0 && (
        <div className="max-h-[400px] overflow-y-auto rounded-md border border-slate-800 bg-slate-950 p-2">
          <div className="space-y-2">
            {searchResults.map((song) => (
              <div
                key={song.spotify_id}
                className="grid grid-cols-12 gap-4 rounded-md p-2 text-sm hover:bg-slate-900"
              >
                <div className="col-span-5 flex items-center gap-3">
                  {song.album_art_url ? (
                    <img
                      src={song.album_art_url}
                      alt={song.name}
                      className="h-10 w-10 rounded object-cover"
                    />
                  ) : (
                    <div className="flex h-10 w-10 items-center justify-center rounded bg-slate-800">
                      <Music className="h-5 w-5 text-slate-600" />
                    </div>
                  )}
                  <div className="truncate">
                    <div className="font-medium text-white">{song.name}</div>
                    {song.artist && (
                      <div className="truncate text-xs text-slate-500">
                        {song.artist}
                      </div>
                    )}
                  </div>
                </div>
                <div className="col-span-4 flex items-center text-slate-300">
                  {song.album}
                </div>
                <div className="col-span-2 flex items-center text-slate-400">
                  {formatDuration(song.duration_ms)}
                </div>
                <div className="col-span-1 flex items-center justify-end">
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-7 w-7 rounded-full hover:bg-green-900/30 hover:text-green-500"
                    onClick={() => handleAddSong(song)}
                    disabled={isAdding[song.spotify_id]}
                  >
                    {isAdding[song.spotify_id] ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Plus className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
} 