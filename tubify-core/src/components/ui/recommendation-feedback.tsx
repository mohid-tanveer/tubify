import React, { useState, useEffect } from "react"
import { Button } from "./button"
import { ThumbsUp, ThumbsDown } from "lucide-react"
import api from "@/lib/axios"
import { toast } from "sonner"
import { clearRecommendationsCache } from "@/loaders/recommendation-loaders"

interface RecommendationFeedbackProps {
  songId: string
  recommendationId?: number
  initialFeedback?: boolean
  onFeedbackChange?: (songId: string, liked: boolean) => void
  mini?: boolean
}

const RecommendationFeedback: React.FC<RecommendationFeedbackProps> = ({
  songId,
  recommendationId,
  initialFeedback,
  onFeedbackChange,
  mini = false,
}) => {
  const [feedback, setFeedback] = useState<boolean | undefined>(initialFeedback)
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)

  // sync with external initialFeedback changes
  useEffect(() => {
    // only update internal state when the prop changes and is different
    if (initialFeedback !== undefined && initialFeedback !== feedback) {
      console.log(
        `Syncing feedback state for song ${songId} to ${initialFeedback}`,
      )
      setFeedback(initialFeedback)
    }
  }, [initialFeedback, songId, feedback])

  // add effect to log when component receives new props
  useEffect(() => {
    if (recommendationId) {
      console.log(
        `Recommendation feedback loaded for song ${songId} with recommendation_id ${recommendationId}`,
      )
    }
  }, [songId, recommendationId])

  const handleFeedback = async (liked: boolean) => {
    // toggle if clicking the same button
    if (feedback === liked) {
      liked = !liked
    }

    setIsSubmitting(true)

    // show a pending toast that we'll update based on success/failure
    const toastId = toast.loading(
      liked ? "saving your like..." : "saving your dislike...",
    )

    try {
      // make sure we're sending the recommendation_id if available
      const payload = {
        song_id: songId,
        liked: liked,
        recommendation_id: recommendationId,
      }

      console.log(`Submitting feedback for song ${songId}:`, payload)

      const response = await api.post("/api/recommendations/feedback", payload)

      console.log(`Feedback response:`, response.data)

      if (response.data.success) {
        // update local state
        setFeedback(liked)

        // call the callback if provided
        if (onFeedbackChange) {
          console.log(`Calling onFeedbackChange callback for song ${songId}`)
          onFeedbackChange(songId, liked)
        }

        // clear recommendation cache so next page load gets fresh data
        clearRecommendationsCache()

        // update the toast to show success
        toast.success(
          liked ? "you liked this song!" : "you disliked this song",
          { id: toastId },
        )
      } else {
        // handle unsuccessful response
        console.error("Feedback submission failed:", response.data)
        toast.error("couldn't save your feedback", { id: toastId })
      }
    } catch (error) {
      console.error("Failed to submit feedback:", error)
      // log more detailed error info
      if (error && typeof error === "object" && "response" in error) {
        const axiosError = error as {
          response: { data: unknown; status: number }
        }
        console.error("Response data:", axiosError.response.data)
        console.error("Response status:", axiosError.response.status)
      }
      toast.error("failed to save your feedback", { id: toastId })
    } finally {
      setIsSubmitting(false)
    }
  }

  if (mini) {
    return (
      <div className="flex space-x-1">
        <Button
          variant="ghost"
          size="icon"
          className={`w-7 h-7 rounded-full flex items-center justify-center ${feedback === true ? "bg-green-900/50 text-green-400" : "text-slate-400"}`}
          onClick={() => handleFeedback(true)}
          disabled={isSubmitting}
        >
          <ThumbsUp className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className={`w-7 h-7 rounded-full flex items-center justify-center ${feedback === false ? "bg-red-900/50 text-red-400" : "text-slate-400"}`}
          onClick={() => handleFeedback(false)}
          disabled={isSubmitting}
        >
          <ThumbsDown className="h-3.5 w-3.5" />
        </Button>
      </div>
    )
  }

  return (
    <div className="flex space-x-2">
      <Button
        variant="outline"
        size="sm"
        className={`flex items-center justify-center ${feedback === true ? "bg-green-900/50 text-green-400 border-green-800" : ""}`}
        onClick={() => handleFeedback(true)}
        disabled={isSubmitting}
      >
        <ThumbsUp className="h-4 w-4 mr-1.5" />
        <span>like</span>
      </Button>
      <Button
        variant="outline"
        size="sm"
        className={`flex items-center justify-center ${feedback === false ? "bg-red-900/50 text-red-400 border-red-800" : ""}`}
        onClick={() => handleFeedback(false)}
        disabled={isSubmitting}
      >
        <ThumbsDown className="h-4 w-4 mr-1.5" />
        <span>dislike</span>
      </Button>
    </div>
  )
}

export default RecommendationFeedback
