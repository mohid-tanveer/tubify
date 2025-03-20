import { useNavigate, useLoaderData } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Globe, Music, ArrowLeft } from "lucide-react"

interface Playlist {
  id: number
  public_id: string
  name: string
  description?: string
  is_public: boolean
  image_url?: string
  created_at: string
  updated_at: string
  song_count: number
}

interface UserPlaylistsData {
  username: string
  playlists: Playlist[]
}

export default function UserPlaylists() {
  const { username, playlists } = useLoaderData() as UserPlaylistsData
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

        <div className="mb-8">
          <h1 className="text-2xl md:text-3xl font-bold text-white">{username}'s playlists</h1>
          <p className="mt-2 text-slate-400">browse public playlists by {username}</p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 pb-8">
          {playlists.map((playlist) => (
            <div
              key={playlist.id}
              className="group relative overflow-hidden rounded-lg border border-slate-800 bg-slate-900/50 p-4 transition-all hover:border-slate-600"
              onClick={() => navigate(`/users/playlists/${playlist.public_id}`)}
            >
              <div className="flex items-start gap-4">
                {/* playlist image */}
                <div className="h-16 w-16 shrink-0 overflow-hidden rounded-md bg-slate-800">
                  {playlist.image_url ? (
                    <img
                      src={playlist.image_url}
                      alt={playlist.name}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center">
                      <Music className="h-8 w-8 text-slate-600" />
                    </div>
                  )}
                </div>
                
                {/* playlist info */}
                <div className="flex-1 overflow-hidden">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate text-lg font-medium text-white">
                      {playlist.name}
                    </h3>
                    <Globe className="h-3 w-3 shrink-0 text-slate-400" />
                  </div>
                  
                  {playlist.description && (
                    <p className="mt-1 truncate text-sm text-slate-400">
                      {playlist.description}
                    </p>
                  )}
                  
                  <p className="mt-2 text-xs text-slate-500">
                    {playlist.song_count} {playlist.song_count === 1 ? "song" : "songs"}
                  </p>
                </div>
              </div>
              
              <div className="absolute inset-0 flex items-center justify-center bg-black/70 opacity-0 transition-opacity group-hover:opacity-100">
                <Button variant="outline" size="sm" className="bg-black text-white">
                  view playlist
                </Button>
              </div>
            </div>
          ))}
        </div>

        {playlists.length === 0 && (
          <div className="mt-8 rounded-lg border border-slate-800 bg-slate-900/20 p-8 text-center">
            <Music className="mx-auto h-12 w-12 text-slate-600" />
            <h3 className="mt-4 text-xl font-medium text-white">no public playlists</h3>
            <p className="mt-2 text-slate-400">
              {username} hasn't created any public playlists yet
            </p>
          </div>
        )}
      </div>
    </div>
  )
} 