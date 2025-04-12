import { useEffect, useState, useRef, useCallback } from "react"
import api from "@/lib/axios"
import { TubifyTitle } from "@/components/ui/tubify-title"
import { Button } from "@/components/ui/button"
import { ArrowLeft, Music, Clock } from "lucide-react"
import { useNavigate } from "react-router-dom"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

// Improved truncated text component
function TruncatedText({ text, className }: { text: string, className?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const [isTruncated, setIsTruncated] = useState(false)
  
  // Check if element is truncated
  const checkTruncation = useCallback(() => {
    const element = ref.current
    if (!element) return
    
    // Reset before checking to get accurate measurements
    element.style.textOverflow = 'clip'
    const isOverflowing = element.scrollWidth > element.clientWidth
    element.style.textOverflow = 'ellipsis'
    
    setIsTruncated(isOverflowing)
  }, [])

  useEffect(() => {
    checkTruncation()

    // Create resize observer to check again when dimensions change
    const resizeObserver = new ResizeObserver(() => {
      checkTruncation()
    })
    
    if (ref.current) {
      resizeObserver.observe(ref.current)
    }

    // Check again after a slight delay to ensure fonts are loaded
    const timeoutId = setTimeout(checkTruncation, 500)

    return () => {
      resizeObserver.disconnect()
      clearTimeout(timeoutId)
    }
  }, [text, checkTruncation])

  // Always use tooltip but make it empty when not truncated
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span 
            ref={ref} 
            className={`truncate block w-full ${className || ''}`}
          >
            {text}
          </span>
        </TooltipTrigger>
        {isTruncated && (
          <TooltipContent side="bottom" className="max-w-[350px] break-words">
            <p>{text}</p>
          </TooltipContent>
        )}
      </Tooltip>
    </TooltipProvider>
  )
}

interface Track {
  track_name: string
  artist_name: string[]
  album_name: string
  played_at: string
  spotify_url: string
  album_art_url?: string
}

export default function RecentlyPlayed() {
  const [tracks, setTracks] = useState<Track[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    const fetchRecentlyPlayed = async () => {
      try {
        const response = await api.get("/api/spotify/recently-played")
        setTracks(response.data.recently_played)
      } catch (error) {
        console.error("failed to fetch recently played tracks:", error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchRecentlyPlayed()
  }, [])

  // format date as relative time (e.g. "2 hours ago")
  const formatRelativeTime = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    
    // convert to seconds
    const diffSecs = Math.floor(diffMs / 1000)
    
    // less than a minute
    if (diffSecs < 60) {
      return 'just now'
    }
    
    // less than an hour
    if (diffSecs < 3600) {
      const mins = Math.floor(diffSecs / 60)
      return `${mins} ${mins === 1 ? 'minute' : 'minutes'} ago`
    }
    
    // less than a day
    if (diffSecs < 86400) {
      const hours = Math.floor(diffSecs / 3600)
      return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`
    }
    
    // less than a week
    if (diffSecs < 604800) {
      const days = Math.floor(diffSecs / 86400)
      return `${days} ${days === 1 ? 'day' : 'days'} ago`
    }
    
    // otherwise show the date
    return date.toLocaleDateString()
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col bg-black text-white">
        <TubifyTitle />
        <div className="container mx-auto mt-4 pb-16 text-center">
          <div className="mt-8">
            <p>loading recently played tracks...</p>
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
            onClick={() => navigate("/profile")}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            back to profile
          </Button>
        </div>

        {/* header */}
        <div className="mb-8">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl md:text-3xl font-bold text-white">Recently Played Tracks</h1>
          </div>
          
          <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-slate-500">
            <div className="flex items-center">
              <Music className="mr-1 h-4 w-4" />
              {tracks.length} tracks
            </div>
            
            <div>
              last updated {new Date().toLocaleDateString()}
            </div>
          </div>
        </div>

        {/* tracks list */}
        <div className="mt-4 md:mt-8">
          <div className="mb-4 grid grid-cols-8 md:grid-cols-11 gap-4 border-b border-slate-800 pb-2 text-xs md:text-sm font-medium text-slate-500">
            <div className="col-span-5 md:col-span-4">title</div>
            <div className="col-span-3 md:col-span-3">artist</div>
            <div className="hidden md:block md:col-span-2">album</div>
            <div className="hidden md:block md:col-span-2 text-right">played</div>
          </div>

          {tracks.length > 0 ? (
            <div className="space-y-2">
              {tracks.map((track, index) => (
                <div key={index} className="grid grid-cols-8 md:grid-cols-11 gap-4 rounded-md p-2 hover:bg-slate-800/50 text-sm">
                  <div className="col-span-5 md:col-span-4 flex items-center min-w-0">
                    <div className="mr-3 h-10 w-10 flex-shrink-0">
                      {track.album_art_url ? (
                        <img
                          src={track.album_art_url}
                          alt={track.track_name}
                          className="h-full w-full rounded object-cover"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center rounded bg-slate-800">
                          <Music className="h-5 w-5 text-slate-500" />
                        </div>
                      )}
                    </div>
                    <div className="min-w-0 flex-1 flex flex-col">
                      <a
                        href={track.spotify_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-white hover:underline min-w-0 flex-1"
                      >
                        <TruncatedText text={track.track_name} />
                      </a>
                      <div className="md:hidden text-xs text-slate-500">
                        {formatRelativeTime(track.played_at)}
                      </div>
                    </div>
                  </div>
                  <div className="col-span-3 md:col-span-3 flex items-center min-w-0">
                    <TruncatedText 
                      text={track.artist_name.join(", ")} 
                      className="text-slate-300"
                    />
                  </div>
                  <div className="hidden md:flex md:col-span-2 items-center min-w-0">
                    <TruncatedText 
                      text={track.album_name} 
                      className="text-slate-400"
                    />
                  </div>
                  <div className="hidden md:flex md:col-span-2 items-center justify-end text-slate-500">
                    <div className="flex items-center whitespace-nowrap">
                      <Clock className="mr-1 h-3 w-3" />
                      {formatRelativeTime(track.played_at)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-8 text-center text-slate-400 pb-8">
              <Music className="mx-auto h-12 w-12 opacity-50" />
              <p className="mt-2">no recently played tracks found</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
