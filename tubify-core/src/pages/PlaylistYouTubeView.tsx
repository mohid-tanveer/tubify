import { useState } from "react"
import { useParams, useNavigate, useLoaderData } from "react-router-dom"
import { ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { YouTubePlayer, QueueItem } from "@/components/ui/youtube-player"

interface PlaylistYouTubeData {
  queue_items: QueueItem[]
  queue_type: string
  error?: string
}

export default function PlaylistYouTubeView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const data = useLoaderData() as PlaylistYouTubeData
  const [preferLive] = useState(() => {
    // check localStorage for preference
    const saved = localStorage.getItem("tubify_prefer_live")
    return saved ? saved === "true" : false
  })

  // extract the queue and error from loader data
  const queue = data.queue_items || []
  const error = data.error

  // parse URL to get index if present, defaulting to 0
  const urlParams = new URLSearchParams(window.location.search)
  const initialIndex = parseInt(urlParams.get("index") || "0")

  const handleClose = () => {
    // clear youtube queue cache from localStorage
    const queueType = urlParams.get("queue_type") || "sequential"
    const cacheKey = `tubify_youtube_queue_${id}_${queueType}`
    localStorage.removeItem(cacheKey)

    // go back to playlist detail
    navigate(`/playlists/${id}`)
  }

  if (error) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black text-white">
        <div className="text-center max-w-md p-6">
          <div className="text-red-500 mb-4">⚠️</div>
          <p className="mb-4">{error}</p>
          <Button variant="outline" onClick={handleClose}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            back to playlist
          </Button>
        </div>
      </div>
    )
  }

  if (queue.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black text-white">
        <div className="text-center max-w-md p-6">
          <p className="mb-4">no videos available for this playlist</p>
          <Button variant="outline" onClick={handleClose}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            back to playlist
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 bg-black overflow-hidden">
      <YouTubePlayer
        queue={queue}
        initialIndex={initialIndex}
        onClose={handleClose}
        autoplay={true}
        preferLivePerformance={preferLive}
      />
    </div>
  )
}
