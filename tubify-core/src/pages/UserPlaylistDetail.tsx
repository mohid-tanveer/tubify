import { ArrowLeft, Globe, Music } from "lucide-react"
import { useLoaderData, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { SongItem } from "@/components/ui/song-item"

// song type
interface Song {
  id: number
  spotify_id: string
  name: string
  artist: string
  album?: string
  duration_ms?: number
  spotify_uri: string
  album_art_url?: string
  created_at: string
}

// playlist type
interface Playlist {
  id: number
  public_id: string
  name: string
  description?: string
  is_public: boolean
  spotify_playlist_id?: string
  image_url?: string
  created_at: string
  updated_at: string
  songs: Song[]
  username: string
}

export default function UserPlaylistDetail() {
  const { playlist } = useLoaderData() as { playlist: Playlist }
  const navigate = useNavigate()

  return (
    <div className="scrollable-page bg-linear-to-b from-slate-900 to-black">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="pt-6 pb-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            back
          </Button>
        </div>

        {/* playlist header */}
        <div className="flex flex-col md:flex-row gap-6 mb-8">
          {/* playlist image */}
          <div className="w-full md:w-1/3 max-w-[300px] mx-auto md:mx-0">
            <div className="aspect-square overflow-hidden rounded-lg border border-slate-800 bg-slate-950">
              {playlist.image_url ? (
                <img
                  src={playlist.image_url}
                  alt={playlist.name}
                  className="h-full w-full object-cover"
                />
              ) : playlist.songs && playlist.songs.length > 0 && playlist.songs[0].album_art_url ? (
                <img
                  src={playlist.songs[0].album_art_url}
                  alt={playlist.name}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center">
                  <Music className="h-12 w-12 text-slate-600" />
                </div>
              )}
            </div>
          </div>

          {/* playlist info */}
          <div className="flex flex-col justify-between w-full md:w-2/3">
            <div>
              <div className="mb-2 flex items-center gap-2">
                <Globe className="h-4 w-4 text-slate-400" />
                <span className="text-sm text-slate-400">Public Playlist</span>
              </div>
              <h1 className="mb-2 text-2xl md:text-3xl font-bold text-white">
                {playlist.name}
              </h1>
              {playlist.description && (
                <p className="mb-4 text-slate-300">{playlist.description}</p>
              )}
              <div className="mb-2 text-sm text-slate-400">
                Created by <span className="text-white">{playlist.username}</span>
              </div>
              <div className="mb-4 text-sm text-slate-400">
                {playlist.songs.length} songs
              </div>
            </div>
          </div>
        </div>

        {/* songs list */}
        <div className="mt-4 md:mt-8">
          <div className="mb-4 grid grid-cols-12 gap-4 border-b border-slate-800 pb-2 text-xs md:text-sm font-medium text-slate-500">
            <div className="col-span-1">#</div>
            <div className="col-span-5">title</div>
            <div className="col-span-3">artist</div>
            <div className="col-span-2 text-right">duration</div>
            <div className="col-span-1"></div>
          </div>

          {playlist.songs.length > 0 ? (
            <div className="space-y-1 pb-4">
              {playlist.songs.map((song, index) => (
                <SongItem
                  key={song.id}
                  song={song}
                  index={index}
                  playlistPublicId={playlist.public_id}
                />
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-slate-400">
              <Music className="mx-auto mb-2 h-8 w-8 opacity-50" />
              <p>This playlist is empty</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
} 