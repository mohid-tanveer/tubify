import { useContext, useEffect, useState } from "react"
import { AuthContext } from "@/contexts/auth"
import { Button } from "@/components/ui/button"
import api from "@/lib/axios"
import { useNavigate, useLoaderData } from "react-router-dom"
import { clearPlaylistsCache, setPlaylistsCache } from "@/loaders/playlist-loaders"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"
import { Lock, Globe, Music, Plus, Loader2, ArrowLeft } from "lucide-react"
import { toast } from "sonner"

// form schema for creating/editing playlists
const playlistFormSchema = z.object({
  name: z.string().min(1, "name is required"),
  description: z.string().optional(),
  is_public: z.boolean().default(true),
  spotify_playlist_id: z.string().optional(),
})

type PlaylistFormValues = z.infer<typeof playlistFormSchema>

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
  song_count: number
}

interface SpotifyPlaylist {
  id: string
  name: string
  description?: string
  is_imported?: boolean
}

interface PlaylistsLoaderData {
  playlists: Playlist[]
  isSpotifyConnected: boolean
  spotifyPlaylists: SpotifyPlaylist[]
}

export default function Playlists() {
  const { isAuthenticated } = useContext(AuthContext)
  const navigate = useNavigate()
  
  const { playlists: initialPlaylists, isSpotifyConnected, spotifyPlaylists: initialSpotifyPlaylists } = useLoaderData() as PlaylistsLoaderData
  
  
  const [playlists, setPlaylists] = useState<Playlist[]>(initialPlaylists)
  const [spotifyPlaylists, setSpotifyPlaylists] = useState<SpotifyPlaylist[]>(initialSpotifyPlaylists)
  const [isCreating, setIsCreating] = useState(false)
  const [selectedSpotifyPlaylist, setSelectedSpotifyPlaylist] = useState<string>("")
  const [dialogOpen, setDialogOpen] = useState(false)
  const [showImportedPlaylists, setShowImportedPlaylists] = useState(false)

  // form for creating new playlists
  const form = useForm<PlaylistFormValues>({
    resolver: zodResolver(playlistFormSchema),
    defaultValues: {
      name: "",
      description: "",
      is_public: true,
    },
  })

  // update form when spotify playlist is selected
  useEffect(() => {
    if (selectedSpotifyPlaylist) {
      const playlist = spotifyPlaylists.find(p => p.id === selectedSpotifyPlaylist)
      if (playlist) {
        form.setValue("name", playlist.name)
        form.setValue("description", playlist.description || "")
      }
    } else {
      form.reset()
    }
  }, [selectedSpotifyPlaylist, spotifyPlaylists, form])

  // redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth")
    }
  }, [isAuthenticated, navigate])

  const handleCreatePlaylist = async (values: PlaylistFormValues) => {
    try {
      setIsCreating(true)
      
      const response = await api.post("/api/playlists", {
        ...values,
        spotify_playlist_id: selectedSpotifyPlaylist || undefined,
      })
      
      // clear the cache when a new playlist is created
      clearPlaylistsCache()

      // fetch updated playlists instead of reloading the page
      try {
        const { data } = await api.get("/api/playlists")
      
        const spotifyResponse = await api.get("/api/spotify/playlists")
        let spotifyPlaylists = []
        spotifyPlaylists = spotifyResponse.data
        
        // update the cache with fresh data
        const cacheData = {
          playlists: data,
          isSpotifyConnected: true,
          spotifyPlaylists,
        }
        
        // update the local state and cache
        setPlaylists(data)
        setSpotifyPlaylists(spotifyPlaylists)
        setPlaylistsCache(cacheData)
        
        toast.success("playlist created successfully")
      } catch {
        // if fetching fails, still show the new playlist
        setPlaylists([response.data, ...playlists])
      }
      
      // close the dialog
      setDialogOpen(false)
      
      // reset form
      form.reset()
      setSelectedSpotifyPlaylist("")
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error("failed to create playlist:", error)
      }
      toast.error("failed to create playlist")
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="min-h-screen bg-linear-to-b from-slate-900 to-black pb-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="pt-6 pb-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            back
          </Button>
        </div>

        <div className="mb-8">
          <h1 className="text-2xl md:text-3xl font-bold text-white">my playlists</h1>
          <p className="mt-2 text-slate-400">create and manage your music playlists</p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {/* create new playlist card */}
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <div className="flex h-full min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-slate-700 bg-slate-900/50 p-6 text-center transition-colors hover:border-slate-500 hover:bg-slate-900">
                <Plus className="mb-2 h-8 w-8 text-slate-400" />
                <h3 className="text-lg font-medium text-white">create new playlist</h3>
                <p className="mt-1 text-sm text-slate-400">start a fresh playlist from scratch</p>
              </div>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>create new playlist</DialogTitle>
                <DialogDescription>
                  <br/>
                  fill out the details below to create a new playlist. you can add songs later.
                </DialogDescription>
              </DialogHeader>
              <Form {...form}>
                <form onSubmit={form.handleSubmit(handleCreatePlaylist)} className="space-y-4">
                  <FormField
                    control={form.control}
                    name="name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>name</FormLabel>
                        <FormControl>
                          <Input 
                            placeholder="my awesome playlist" 
                            {...field} 
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  
                  <FormField
                    control={form.control}
                    name="description"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>description (optional)</FormLabel>
                        <FormControl>
                          <Textarea 
                            placeholder="a collection of my favorite songs" 
                            {...field} 
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                  
                  <FormField
                    control={form.control}
                    name="is_public"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center gap-2 space-y-0">
                        <FormControl>
                          <div className="flex items-center space-x-2">
                            <Switch 
                              id="is-public" 
                              checked={field.value} 
                              onCheckedChange={field.onChange}
                            />
                            <label 
                              htmlFor="is-public" 
                              className="text-sm text-muted-foreground font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                            >
                              make playlist public
                            </label>
                          </div>
                        </FormControl>
                      </FormItem>
                    )}
                  />

                  {isSpotifyConnected && spotifyPlaylists.length > 0 && (
                    <div className="space-y-2">
                      <FormLabel>import from spotify (optional)</FormLabel>
                      <FormControl>
                        <select
                          value={selectedSpotifyPlaylist}
                          onChange={(e) => setSelectedSpotifyPlaylist(e.target.value)}
                          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <option value="">select a spotify playlist</option>
                          {spotifyPlaylists
                            .filter(playlist => showImportedPlaylists || !playlist.is_imported)
                            .map((playlist) => (
                            <option 
                              key={playlist.id} 
                              value={playlist.id}
                              disabled={playlist.is_imported}
                            >
                              {playlist.name}{playlist.is_imported ? ' (already imported)' : ''}
                            </option>
                          ))}
                        </select>
                      </FormControl>
                      <div className="flex items-center space-x-2 mt-2">
                        <Switch 
                          id="show-imported" 
                          checked={showImportedPlaylists} 
                          onCheckedChange={(checked) => setShowImportedPlaylists(checked === true)}
                        />
                        <label 
                          htmlFor="show-imported" 
                          className="text-sm text-muted-foreground font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                        >
                          show already imported playlists
                        </label>
                      </div>
                    </div>
                  )}
                  
                  <DialogFooter className="mt-6">
                    <Button type="submit" disabled={isCreating}>
                      {isCreating ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          creating...
                        </>
                      ) : (
                        "create playlist"
                      )}
                    </Button>
                  </DialogFooter>
                </form>
              </Form>
            </DialogContent>
          </Dialog>

          {/* playlist cards */}
          {playlists.map((playlist) => (
            <div
              key={playlist.id}
              className="group relative overflow-hidden rounded-lg border border-slate-800 bg-slate-900/50 p-4 transition-all hover:border-slate-600"
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
                    {playlist.is_public ? (
                      <Globe className="h-3 w-3 shrink-0 text-slate-400" />
                    ) : (
                      <Lock className="h-3 w-3 shrink-0 text-slate-400" />
                    )}
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
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="bg-black text-white"
                  onClick={() => navigate(`/playlists/${playlist.public_id}`)}
                >
                  view playlist
                </Button>
              </div>
            </div>
          ))}
        </div>

        {playlists.length === 0 && !isCreating && (
          <div className="mt-8 rounded-lg border border-slate-800 bg-slate-900/20 p-8 text-center">
            <Music className="mx-auto h-12 w-12 text-slate-600" />
            <h3 className="mt-4 text-xl font-medium text-white">no playlists yet</h3>
            <p className="mt-2 text-slate-400">
              create your first playlist to get started
            </p>
          </div>
        )}
      </div>
    </div>
  )
} 