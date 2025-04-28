import { Button } from "@/components/ui/button"
import { Music, Play } from "lucide-react"

// song type
interface Song {
  id: string
  name: string
  artist: string[]
  album: string
  duration_ms: number
  spotify_uri: string
  album_art_url: string
  created_at: string
}

// format duration from ms to mm:ss
const formatDuration = (ms: number | undefined) => {
  if (!ms) return "--:--"
  const minutes = Math.floor(ms / 60000)
  const seconds = Math.floor((ms % 60000) / 1000)
  return `${minutes}:${seconds.toString().padStart(2, "0")}`
}

interface SongItemProps {
  song: Song
  index: number
  playlistPublicId: string
}

export function SongItem({ song, index }: SongItemProps) {
  return (
    <div className="grid grid-cols-12 gap-4 rounded-md p-3 text-xs md:text-sm hover:bg-slate-800/80 transition-colors border border-transparent hover:border-slate-700">
      <div className="col-span-1 flex items-center text-slate-400 font-medium">
        {index + 1}
      </div>
      <div className="col-span-5 flex items-center gap-3 md:gap-4">
        {song.album_art_url ? (
          <img
            src={song.album_art_url}
            alt={song.name}
            className="h-10 w-10 md:h-12 md:w-12 rounded-md object-cover shadow-md"
          />
        ) : (
          <div className="flex h-10 w-10 md:h-12 md:w-12 items-center justify-center rounded-md bg-slate-800 shadow-md">
            <Music className="h-5 w-5 md:h-6 md:w-6 text-slate-500" />
          </div>
        )}
        <div className="truncate">
          <div className="font-medium text-white text-xs md:text-sm">
            {song.name}
          </div>
          {song.album && (
            <div className="truncate text-[10px] md:text-xs text-slate-400">
              {song.album}
            </div>
          )}
        </div>
      </div>
      <div className="col-span-3 flex items-center text-slate-300 text-xs md:text-sm font-medium">
        {Array.isArray(song.artist) ? song.artist.join(", ") : song.artist}
      </div>
      <div className="col-span-3 flex items-center justify-end gap-3 text-slate-400 text-xs md:text-sm">
        {song.spotify_uri && (
          <Button
            size="icon"
            variant="ghost"
            className="h-6 w-6 md:h-7 md:w-7 rounded-full hover:bg-green-900/50 hover:text-green-400 transition-colors"
            onClick={(e) => {
              e.stopPropagation()
              window.open(song.spotify_uri, "_blank")
            }}
          >
            <Play className="h-3 w-3 md:h-4 md:w-4" />
          </Button>
        )}
        <span className="font-medium">{formatDuration(song.duration_ms)}</span>
      </div>
    </div>
  )
}
