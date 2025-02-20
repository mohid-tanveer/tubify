import { useContext, useEffect, useState } from "react"
import { AuthContext } from "@/contexts/auth"
import { TubifyTitle } from "@/components/ui/tubify-title"
import { Button } from "@/components/ui/button"
import { Icons } from "@/components/icons"
import api from "@/lib/axios"
import { useNavigate } from "react-router-dom"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormDescription,
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
import { Loader2, Lock, Globe, Music, Plus } from "lucide-react"

// form schema for creating/editing playlists
const playlistFormSchema = z.object({
  name: z.string().min(1, "name is required"),
  description: z.string().optional(),
  is_public: z.boolean().default(true),
  spotify_playlist_id: z.string().optional(),
})

type PlaylistFormValues = z.infer<typeof playlistFormSchema>

// song type
interface Song {
  id: number
  spotify_id: string
  name: string
  artist: string
  album?: string
  duration_ms?: number
  preview_url?: string
  album_art_url?: string
  created_at: string
}

// playlist type
interface Playlist {
  id: number
  name: string
  description?: string
  is_public: boolean
  spotify_playlist_id?: string
  created_at: string
  updated_at: string
  songs: Song[]
}

interface SpotifyPlaylist {
  id: string
  name: string
}

export default function PlaylistsPage() {
  const { isAuthenticated } = useContext(AuthContext)
  const navigate = useNavigate()
  const [playlists, setPlaylists] = useState<Playlist[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSpotifyConnected, setIsSpotifyConnected] = useState(false)
  const [spotifyPlaylists, setSpotifyPlaylists] = useState<SpotifyPlaylist[]>([])
  const [isCreating, setIsCreating] = useState(false)
  const [selectedSpotifyPlaylist, setSelectedSpotifyPlaylist] = useState<string>("")

  // form for creating new playlists
  const form = useForm<PlaylistFormValues>({
    resolver: zodResolver(playlistFormSchema),
    defaultValues: {
      name: "",
      description: "",
      is_public: true,
    },
  })

  // check spotify connection and fetch playlists on mount
  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/auth")
      return
    }

    const init = async () => {
      try {
        // check spotify connection
        const statusResponse = await api.get("/api/spotify/status")
        setIsSpotifyConnected(statusResponse.data.is_connected)

        // fetch tubify playlists
        const playlistsResponse = await api.get("/api/playlists")
        setPlaylists(playlistsResponse.data)

        // fetch spotify playlists if connected
        if (statusResponse.data.is_connected) {
          const spotifyResponse = await api.get("/api/spotify/playlists")
          setSpotifyPlaylists(spotifyResponse.data)
        }
      } catch (error) {
        console.error("failed to initialize playlists page:", error)
      } finally {
        setIsLoading(false)
      }
    }

    init()
  }, [isAuthenticated, navigate])

  const handleCreatePlaylist = async (values: PlaylistFormValues) => {
    try {
      setIsCreating(true)
      const response = await api.post("/api/playlists", {
        ...values,
        spotify_playlist_id: selectedSpotifyPlaylist || undefined,
      })
      setPlaylists([response.data, ...playlists])
      form.reset()
      setSelectedSpotifyPlaylist("")
    } catch (error) {
      console.error("failed to create playlist:", error)
    } finally {
      setIsCreating(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-white" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-black p-8">
      <div className="mb-8">
        <TubifyTitle />
      </div>

      <div className="mx-auto max-w-4xl">
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-white">Your Playlists</h1>
          
          <Dialog>
            <DialogTrigger asChild>
              <Button className="bg-green-600 hover:bg-green-700">
                <Plus className="mr-2 h-4 w-4" />
                Create Playlist
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Playlist</DialogTitle>
                <DialogDescription>
                  Create a new playlist from scratch or import from Spotify
                </DialogDescription>
              </DialogHeader>

              <Form {...form}>
                <form
                  onSubmit={form.handleSubmit(handleCreatePlaylist)}
                  className="space-y-4"
                >
                  <FormField
                    control={form.control}
                    name="name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Name</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="my awesome playlist" />
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
                        <FormLabel>Description (optional)</FormLabel>
                        <FormControl>
                          <Textarea
                            {...field}
                            placeholder="describe your playlist..."
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="is_public"
                    render={({ field }) => (
                      <FormItem className="flex items-center justify-between rounded-lg border p-4">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">
                            Public Playlist
                          </FormLabel>
                          <FormDescription>
                            Anyone can view public playlists
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />

                  {isSpotifyConnected && spotifyPlaylists.length > 0 && (
                    <div className="space-y-2">
                      <FormLabel>Import from Spotify (optional)</FormLabel>
                      <select
                        value={selectedSpotifyPlaylist}
                        onChange={(e) => setSelectedSpotifyPlaylist(e.target.value)}
                        className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option value="">Select a Spotify playlist</option>
                        {spotifyPlaylists.map((playlist) => (
                          <option key={playlist.id} value={playlist.id}>
                            {playlist.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  <Button
                    type="submit"
                    className="w-full"
                    disabled={isCreating}
                  >
                    {isCreating && (
                      <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    Create Playlist
                  </Button>
                </form>
              </Form>
            </DialogContent>
          </Dialog>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {playlists.map((playlist) => (
            <div
              key={playlist.id}
              className="group relative overflow-hidden rounded-lg border border-slate-800 bg-black p-4 transition-all hover:border-slate-600"
              onClick={() => navigate(`/playlists/${playlist.id}`)}
            >
              <div className="mb-2 flex items-center justify-between">
                <h3 className="font-medium text-white">{playlist.name}</h3>
                {playlist.is_public ? (
                  <Globe className="h-4 w-4 text-slate-400" />
                ) : (
                  <Lock className="h-4 w-4 text-slate-400" />
                )}
              </div>
              
              {playlist.description && (
                <p className="mb-4 text-sm text-slate-400 line-clamp-2">
                  {playlist.description}
                </p>
              )}

              <div className="flex items-center text-sm text-slate-500">
                <Music className="mr-1 h-4 w-4" />
                {playlist.songs.length} songs
              </div>

              <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50 opacity-0 transition-opacity group-hover:opacity-100">
                <Button variant="outline" className="bg-black text-white">
                  View Playlist
                </Button>
              </div>
            </div>
          ))}
        </div>

        {playlists.length === 0 && (
          <div className="mt-8 text-center text-slate-400">
            <Music className="mx-auto h-12 w-12 opacity-50" />
            <p className="mt-2">no playlists yet</p>
            <p className="text-sm">create one to get started!</p>
          </div>
        )}
      </div>
    </div>
  )
} 