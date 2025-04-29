import { useState, useEffect } from "react"
import { useNavigate, useLoaderData } from "react-router-dom"
import { ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { RecommendationYouTubePlayer } from "@/components/ui/recommendation-youtube-player"
import { QueueItem } from "@/components/ui/youtube-player"
import api from "@/lib/axios"
import { toast } from "sonner"
import { clearRecommendationsCache } from "@/loaders/recommendation-loaders"

interface RecommendationYouTubeData {
  queue_items: QueueItem[]
  error?: string
}

export default function RecommendationYouTubeView() {
  const navigate = useNavigate()
  const data = useLoaderData() as RecommendationYouTubeData
  const [preferLive] = useState(() => {
    // check localStorage for preference
    const saved = localStorage.getItem("tubify_prefer_live")
    return saved ? saved === "true" : false
  })

  // feedback state tracking
  const [hasFeedbackChanges, setHasFeedbackChanges] = useState(false)

  // extract the queue and error from loader data
  const queue = data.queue_items || []
  const error = data.error

  // parse URL to get index if present, defaulting to 0
  const urlParams = new URLSearchParams(window.location.search)
  const initialIndex = parseInt(urlParams.get("index") || "0")

  // handle user feedback
  const handleFeedback = async (songId: string, liked: boolean) => {
    setHasFeedbackChanges(true)

    try {
      // submit the feedback to the API
      await api.post("/api/recommendations/feedback", {
        song_id: songId,
        liked: liked,
      })

      // prompt to refresh recommendations if liked
      if (liked) {
        toast("like recorded! refresh recommendations?", {
          action: {
            label: "refresh now",
            onClick: () => {
              clearRecommendationsCache()
              navigate("/recommendations")
            },
          },
          duration: 5000,
        })
      }
    } catch (error) {
      console.error("Failed to submit feedback:", error)
      toast.error("failed to save your feedback")
    }
  }

  // sync feedback changes on unmount
  useEffect(() => {
    return () => {
      if (hasFeedbackChanges) {
        clearRecommendationsCache()
      }
    }
  }, [hasFeedbackChanges])

  const handleClose = () => {
    // clear youtube queue cache from localStorage
    localStorage.removeItem("tubify_youtube_recommendations_all")

    // go back to recommendations page
    navigate(`/recommendations`)
  }

  if (error) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black text-white">
        <div className="text-center max-w-md p-6">
          <div className="text-red-500 mb-4">⚠️</div>
          <p className="mb-4">{error}</p>
          <Button variant="outline" onClick={handleClose}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            back to recommendations
          </Button>
        </div>
      </div>
    )
  }

  if (queue.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black text-white">
        <div className="text-center max-w-md p-6">
          <p className="mb-4">no videos available for these recommendations</p>
          <Button variant="outline" onClick={handleClose}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            back to recommendations
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 bg-black overflow-hidden">
      <RecommendationYouTubePlayer
        queue={queue}
        initialIndex={initialIndex}
        onClose={handleClose}
        autoplay={true}
        preferLivePerformance={preferLive}
        onFeedback={handleFeedback}
      />
    </div>
  )
}
