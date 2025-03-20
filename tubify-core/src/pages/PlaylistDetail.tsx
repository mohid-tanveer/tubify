import { useNavigate, useLoaderData } from "react-router-dom"
import { TubifyTitle } from "@/components/ui/tubify-title"
import { Button } from "@/components/ui/button"
import { Globe, Lock, Music, ArrowLeft, Trash2, Plus, Loader2 } from "lucide-react"
import { useState, useEffect } from "react"
import api from "@/lib/axios"
import { clearPlaylistsCache, clearPlaylistDetailCache, setPlaylistDetailCache } from "@/loaders/playlist-loaders"
import { toast } from "sonner"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { SongSearch } from "@/components/ui/song-search"
import { DraggableSongList } from "@/components/ui/draggable-song-list"

// song type
interface Song {
  id: string
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
}

export default function PlaylistDetail() {
  const navigate = useNavigate()
  const { playlist: initialPlaylist, error } = useLoaderData() as { 
    playlist: Playlist | null
    error?: string
  }
  const [playlist, setPlaylist] = useState<Playlist | null>(initialPlaylist)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isAddSongDialogOpen, setIsAddSongDialogOpen] = useState(false)

  // update local state when initialPlaylist changes
  useEffect(() => {
    setPlaylist(initialPlaylist)
  }, [initialPlaylist])

  const handleDeletePlaylist = async () => {
    if (!playlist) return
    
    try {
      setIsDeleting(true)
      await api.delete(`/api/playlists/${playlist.public_id}`)
      
      // clear the cache when a playlist is deleted
      clearPlaylistsCache()
      clearPlaylistDetailCache(playlist.public_id)
      
      setIsDialogOpen(false)
      navigate("/playlists")
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error("failed to delete playlist:", error)
      }
      toast.error("failed to delete playlist")
    } finally {
      setIsDeleting(false)
    }
  }

  const handleSongAdded = async () => {
    if (!playlist) return
    
    // refresh playlist data
    try {
      const response = await api.get(`/api/playlists/${playlist.public_id}`)
      const updatedPlaylist = response.data
      
      // update cache with new data
      setPlaylistDetailCache(playlist.public_id, { playlist: updatedPlaylist })
      
      // clear main playlists cache to update song count
      clearPlaylistsCache()
      
      // update local state
      setPlaylist(updatedPlaylist)
      
      // close the dialog
      setIsAddSongDialogOpen(false)
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error("failed to refresh playlist:", error)
      }
      toast.error("failed to update playlist")
    }
  }

  const handleSongRemoved = async () => {
    if (!playlist) return;
    
    // refresh playlist data
    try {
      const response = await api.get(`/api/playlists/${playlist.public_id}`);
      const updatedPlaylist = response.data;
      
      // update cache with new data
      setPlaylistDetailCache(playlist.public_id, { playlist: updatedPlaylist });
      
      // clear main playlists cache to update song count
      clearPlaylistsCache();
      
      // update local state
      setPlaylist(updatedPlaylist);
      
      // show success message
      toast.success("song removed from playlist");
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error("failed to refresh playlist:", error);
      }
      toast.error("failed to update playlist view");
    }
  };

  const handleSongsReordered = (reorderedSongs: Song[]) => {
    if (!playlist) return;
    
    // update local state with reordered songs
    setPlaylist({
      ...playlist,
      songs: reorderedSongs
    });
  };

  if (!playlist) {
    return (
      <div className="flex min-h-screen flex-col bg-black text-white">
        <TubifyTitle />
        <div className="container mx-auto mt-4 pb-16">
          <div className="flex items-center gap-2">
            <Button 
              variant="ghost"
              size="sm"
              onClick={() => navigate("/playlists")}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              back to playlists
            </Button>
          </div>
          
          <div className="mt-8 text-center">
            <h1 className="text-2xl font-bold">playlist not found</h1>
            {error && <p className="mt-2 text-slate-400">{error}</p>}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="scrollable-page bg-linear-to-b from-slate-900 to-black">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="pt-6 pb-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/playlists")}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            back to playlists
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

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl md:text-3xl font-bold text-white">{playlist.name}</h1>
              {playlist.is_public ? (
                <Globe className="h-4 w-4 text-slate-400" />
              ) : (
                <Lock className="h-4 w-4 text-slate-400" />
              )}
            </div>
            
            {playlist.description && (
              <p className="mt-2 text-slate-400">{playlist.description}</p>
            )}
            
            <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-slate-500">
              <div className="flex items-center">
                <Music className="mr-1 h-4 w-4" />
                {playlist.songs ? playlist.songs.length : 0} songs
              </div>
              
              {playlist.created_at && (
                <div>
                  created {new Date(playlist.created_at).toLocaleDateString()}
                </div>
              )}
              
              {playlist.updated_at && playlist.updated_at !== playlist.created_at && (
                <div>
                  updated {new Date(playlist.updated_at).toLocaleDateString()}
                </div>
              )}
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <Dialog open={isAddSongDialogOpen} onOpenChange={setIsAddSongDialogOpen}>
                <DialogTrigger asChild>
                  <Button variant="spotify" className="text-white" size="sm">
                    <Plus className="mr-2 h-4 w-4" />
                    add songs
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>add songs to playlist</DialogTitle>
                    <DialogDescription>
                      <br/>
                      search for songs on spotify and add them to your Tubify playlist.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="mt-4">
                    <SongSearch playlistPublicId={playlist.public_id} onSongAdded={handleSongAdded} />
                  </div>
                </DialogContent>
              </Dialog>
              
              <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogTrigger asChild>
                  <Button variant="destructive" size="sm" disabled={isDeleting}>
                    <Trash2 className="mr-2 h-4 w-4" />
                    delete playlist
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>are you sure?</DialogTitle>
                    <DialogDescription>
                      <br/>
                      this action cannot be undone. this will permanently delete the
                      playlist "{playlist.name}" and remove it from our servers.
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter className="mt-4">
                    <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                      cancel
                    </Button>
                    <Button 
                      variant="destructive" 
                      onClick={handleDeletePlaylist}
                      disabled={isDeleting}
                    >
                      {isDeleting ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          deleting...
                        </>
                      ) : (
                        <>
                          <Trash2 className="mr-2 h-4 w-4" />
                          delete
                        </>
                      )}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
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

          {playlist.songs && playlist.songs.length > 0 ? (
            <DraggableSongList 
              songs={playlist.songs}
              playlistPublicId={playlist.public_id}
              onSongRemoved={handleSongRemoved}
              onSongsReordered={handleSongsReordered}
            />
          ) : (
            <div className="mt-8 text-center text-slate-400 pb-8">
              <Music className="mx-auto h-12 w-12 opacity-50" />
              <p className="mt-2">no songs in this playlist yet</p>
              <Button 
                variant="spotify" 
                className="text-white mt-4"
                onClick={() => setIsAddSongDialogOpen(true)}
              >
                <Plus className="mr-2 h-4 w-4" />
                add songs
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
} 