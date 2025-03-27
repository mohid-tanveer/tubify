import { Button } from "@/components/ui/button"
import { Music, Play } from "lucide-react"

// song type
interface Song {
  id: number
  spotify_id: string
  name: string
  artist: string
  album?: string
  duration_ms?: number
  spotify_uri?: string
  album_art_url?: string
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
    <div className="grid grid-cols-12 gap-4 rounded-md p-2 text-xs md:text-sm hover:bg-slate-900">
      <div className="col-span-1 flex items-center text-slate-400">
        {index + 1}
      </div>
      <div className="col-span-5 flex items-center gap-2 md:gap-3">
        {song.album_art_url ? (
          <img
            src={song.album_art_url}
            alt={song.name}
            className="h-8 w-8 md:h-10 md:w-10 rounded object-cover"
          />
        ) : (
          <div className="flex h-8 w-8 md:h-10 md:w-10 items-center justify-center rounded bg-slate-800">
            <Music className="h-4 w-4 md:h-5 md:w-5 text-slate-600" />
          </div>
        )}
        <div className="truncate">
          <div className="font-medium text-white text-xs md:text-sm">{song.name}</div>
          {song.album && (
            <div className="truncate text-[10px] md:text-xs text-slate-500">
              {song.album}
            </div>
          )}
        </div>
      </div>
      <div className="col-span-3 flex items-center text-slate-300 text-xs md:text-sm">
        {song.artist}
      </div>
      <div className="col-span-2 flex items-center justify-end gap-2 text-slate-400 text-xs md:text-sm">
        {song.spotify_uri && (
          <Button
            size="icon"
            variant="ghost"
            className="h-5 w-5 md:h-6 md:w-6 rounded-full hover:bg-green-900/30 hover:text-green-500"
            onClick={(e) => {
              e.stopPropagation()
              window.open(song.spotify_uri, "_blank")
            }}
          >
            <Play className="h-2 w-2 md:h-3 md:w-3" />
          </Button>
        )}
        <span>{formatDuration(song.duration_ms)}</span>
      </div>
    </div>
  )
} 