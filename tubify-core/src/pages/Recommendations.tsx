import React, { useState, useEffect, useCallback } from "react"
import { useLoaderData, useNavigate } from "react-router-dom"
import RecommendationsList from "../components/ui/recommendations-list"
import { TubifyTitle } from "../components/ui/tubify-title"
import { Button } from "../components/ui/button"
import {
  ArrowLeft,
  InfoIcon,
  ThumbsUp,
  ThumbsDown,
  Play,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Skeleton } from "@/components/ui/skeleton"
import api from "@/lib/axios"
import { clearRecommendationsCache } from "@/loaders/recommendation-loaders"
import { RecommendationYouTubePlayer } from "@/components/ui/recommendation-youtube-player"
import { toast } from "sonner"
import { QueueItem } from "@/components/ui/youtube-player"

type RecommendationSource = "friends" | "similar_music"

interface RecommendedSong {
  id: string
  name: string
  spotify_uri: string
  spotify_url: string
  popularity: number
  album_name: string
  album_image_url: string
  artist_names: string
  recommendation_score?: number
  recommendation_sources?: RecommendationSource[]
  similarity_score?: number
  lyrics_similarity?: number
  friend_count?: number
  friends_who_like?: Array<{
    friend_id: number
    friend_name: string
    friend_image: string
  }>
  duration_ms?: number
  user_feedback?: boolean
  recommendation_id?: number
}

interface RecommendationsData {
  hybrid: RecommendedSong[]
  friends: RecommendedSong[]
  similar: RecommendedSong[]
  lyrical: RecommendedSong[]
  error?: string
}

interface AnalyticsData {
  feedback_stats?: {
    total: number
    positive: number
    negative: number
  }
}

interface LoaderData {
  recommendations: RecommendationsData
  analytics?: AnalyticsData
  hasPlayableVideos: boolean
}

const RecommendationsPage: React.FC = () => {
  const data = useLoaderData() as LoaderData
  const { recommendations, analytics, hasPlayableVideos } = data
  const { hybrid, friends, similar, lyrical, error } = recommendations
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState("for-you")
  const [isLoading, setIsLoading] = useState(false)
  const [hasFeedback, setHasFeedback] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [checkingVideos, setCheckingVideos] = useState(false)

  // tinder-like youtube player state
  const [youtubeQueue, setYoutubeQueue] = useState<QueueItem[]>([])
  const [showYoutubeCard, setShowYoutubeCard] = useState(false)
  const [currentYoutubeIndex, setCurrentYoutubeIndex] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStartX, setDragStartX] = useState(0)
  const [dragOffsetX, setDragOffsetX] = useState(0)
  const [swipeDirection, setSwipeDirection] = useState<"left" | "right" | null>(
    null,
  )

  // calculate feedback percentage if available
  const feedbackPercentage = analytics?.feedback_stats?.total
    ? (analytics.feedback_stats.positive / analytics.feedback_stats.total) * 100
    : 0

  // skeleton loader components
  const RecommendationSkeleton = () => (
    <div className="space-y-4">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="bg-slate-800/30 p-3 rounded-md">
          <div className="flex items-center space-x-3">
            <Skeleton className="h-10 w-10 rounded-md" />
            <div className="space-y-2 flex-1">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/2" />
            </div>
            <Skeleton className="h-8 w-14 rounded-md" />
          </div>
        </div>
      ))}
    </div>
  )

  // handle watch button click - load the youtube queue and show the card
  const handleWatchVideos = async () => {
    try {
      setCheckingVideos(true)

      // fetch the videos queue
      const response = await api.get("/api/youtube/recommendations/all")
      const queueItems = response.data.queue_items || []

      if (queueItems.length === 0) {
        toast.error("no videos available for these recommendations")
        return
      }

      setYoutubeQueue(queueItems)
      setCurrentYoutubeIndex(0)
      setShowYoutubeCard(true)
    } catch (error) {
      console.error("Failed to load YouTube queue:", error)
      toast.error("failed to load videos")
    } finally {
      setCheckingVideos(false)
    }
  }

  // function to refresh recommendations
  const handleRefreshRecommendations = useCallback(() => {
    setIsRefreshing(true)
    // clear cache and reload page
    clearRecommendationsCache()
    // also clear video check state
    localStorage.removeItem("tubify_video_check_state")
    window.location.reload()
  }, [])

  // handle feedback for youtube cards - modified to not automatically advance
  const handleYoutubeFeedback = useCallback(
    async (songId: string, liked: boolean) => {
      try {
        // submit the feedback to the API
        await api.post("/api/recommendations/feedback", {
          song_id: songId,
          liked: liked,
        })

        setHasFeedback(true)

        // show toast notification with refresh action for likes
        if (liked) {
          toast("song liked! refresh recommendations?", {
            icon: "👍",
            action: {
              label: "refresh now",
              onClick: handleRefreshRecommendations,
            },
            duration: 5000,
          })
        } else {
          toast("song disliked", {
            icon: "👎",
          })
        }

        // no automatic advance to next song here - will be handled by the swipe logic
      } catch (error) {
        console.error("Failed to submit feedback:", error)
        toast.error("failed to save your feedback")
      }
    },
    [handleRefreshRecommendations],
  )

  // track feedback changes from recommendation list
  const handleFeedbackReceived = () => {
    setHasFeedback(true)
  }

  // handle mouse/touch events for card swiping
  const handleDragStart = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      // don't initiate drag on buttons or controls
      const target = e.target as HTMLElement
      if (target.closest("button") || target.closest(".controls")) {
        return
      }

      setIsDragging(true)
      setSwipeDirection(null)

      // prevent default to stop text selection
      e.preventDefault()

      // get the starting position
      const clientX = "touches" in e ? e.touches[0].clientX : e.clientX

      setDragStartX(clientX)
      setDragOffsetX(0)
    },
    [],
  )

  const handleDragMove = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      if (!isDragging) return

      // prevent default to avoid text selection during drag
      e.preventDefault()

      // get current position
      const clientX = "touches" in e ? e.touches[0].clientX : e.clientX

      const offsetX = clientX - dragStartX
      setDragOffsetX(offsetX)

      // determine swipe direction for visual feedback
      if (offsetX > 50) {
        setSwipeDirection("right")
      } else if (offsetX < -50) {
        setSwipeDirection("left")
      } else {
        setSwipeDirection(null)
      }
    },
    [isDragging, dragStartX],
  )

  const handleDragEnd = useCallback(() => {
    if (!isDragging) return

    const threshold = 100 // minimum distance to register as a swipe

    // check if we have a valid YouTube queue item to provide feedback on
    if (youtubeQueue[currentYoutubeIndex]) {
      if (dragOffsetX > threshold) {
        // swiped right - like
        handleYoutubeFeedback(youtubeQueue[currentYoutubeIndex].song_id, true)

        // move to next song if available
        if (currentYoutubeIndex < youtubeQueue.length - 1) {
          setTimeout(() => {
            setCurrentYoutubeIndex(currentYoutubeIndex + 1)
          }, 300) // slight delay for visual feedback
        } else {
          // we're at the end of the queue
          toast("you've reached the end of recommendations")
        }
      } else if (dragOffsetX < -threshold) {
        // swiped left - dislike
        handleYoutubeFeedback(youtubeQueue[currentYoutubeIndex].song_id, false)

        // move to next song if available
        if (currentYoutubeIndex < youtubeQueue.length - 1) {
          setTimeout(() => {
            setCurrentYoutubeIndex(currentYoutubeIndex + 1)
          }, 300) // slight delay for visual feedback
        } else {
          // we're at the end of the queue
          toast("you've reached the end of recommendations")
        }
      }
    }

    // reset drag state
    setIsDragging(false)
    setDragOffsetX(0)
    setSwipeDirection(null)
  }, [
    isDragging,
    dragOffsetX,
    youtubeQueue,
    currentYoutubeIndex,
    handleYoutubeFeedback,
  ])

  // add event listeners for mouse/touch events outside component
  useEffect(() => {
    if (isDragging) {
      let hasMoved = false
      const dragTimeoutId = setTimeout(() => {
        // if still dragging after 3 seconds, reset the state
        if (isDragging) {
          setIsDragging(false)
          setDragOffsetX(0)
          setSwipeDirection(null)
        }
      }, 3000)

      const handleMouseMove = (e: MouseEvent) => {
        e.preventDefault()
        hasMoved = true

        // create a synthetic React mouse event from the native event
        const syntheticEvent = {
          clientX: e.clientX,
          preventDefault: () => e.preventDefault(),
        } as unknown as React.MouseEvent

        handleDragMove(syntheticEvent)
      }

      const handleMouseUp = () => {
        // only trigger drag end if there was actual movement
        if (hasMoved) {
          handleDragEnd()
        } else {
          // if no movement, just reset the drag state
          setIsDragging(false)
          setDragOffsetX(0)
          setSwipeDirection(null)
        }
      }

      // handle when mouse goes outside the window
      const handleMouseLeave = () => {
        if (isDragging) {
          setIsDragging(false)
          setDragOffsetX(0)
          setSwipeDirection(null)
        }
      }

      const handleTouchMove = (e: TouchEvent) => {
        e.preventDefault()
        hasMoved = true

        // create a synthetic React touch event from the native event
        const syntheticEvent = {
          touches: e.touches,
          preventDefault: () => e.preventDefault(),
        } as unknown as React.TouchEvent

        handleDragMove(syntheticEvent)
      }

      const handleTouchEnd = () => {
        // only trigger drag end if there was actual movement
        if (hasMoved) {
          handleDragEnd()
        } else {
          // if no movement, just reset the drag state
          setIsDragging(false)
          setDragOffsetX(0)
          setSwipeDirection(null)
        }
      }

      // add an escape key handler to cancel dragging
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          setIsDragging(false)
          setDragOffsetX(0)
          setSwipeDirection(null)
        }
      }

      // use passive: false to allow preventDefault
      document.addEventListener("mousemove", handleMouseMove, {
        passive: false,
      })
      document.addEventListener("mouseup", handleMouseUp)
      document.addEventListener("mouseleave", handleMouseLeave)
      document.addEventListener("touchmove", handleTouchMove, {
        passive: false,
      })
      document.addEventListener("touchend", handleTouchEnd)
      document.addEventListener("keydown", handleKeyDown)

      // disable text selection during dragging
      document.body.style.userSelect = "none"
      document.body.style.webkitUserSelect = "none"
      document.body.style.touchAction = "none" // prevent scrolling during drag

      return () => {
        clearTimeout(dragTimeoutId)
        document.removeEventListener("mousemove", handleMouseMove)
        document.removeEventListener("mouseup", handleMouseUp)
        document.removeEventListener("mouseleave", handleMouseLeave)
        document.removeEventListener("touchmove", handleTouchMove)
        document.removeEventListener("touchend", handleTouchEnd)
        document.removeEventListener("keydown", handleKeyDown)

        // re-enable text selection and touch actions
        document.body.style.userSelect = ""
        document.body.style.webkitUserSelect = ""
        document.body.style.touchAction = ""
      }
    }
  }, [isDragging, dragStartX, handleDragMove, handleDragEnd])

  // hide youtube card when navigating away
  useEffect(() => {
    return () => {
      // clean up when component unmounts
      setShowYoutubeCard(false)
    }
  }, [])

  // make sure we clean up the state when card is closed
  const handleCloseYoutubeCard = () => {
    setShowYoutubeCard(false)
    setYoutubeQueue([])
    setCurrentYoutubeIndex(0)
  }

  return (
    <div className="scrollable-page bg-gradient-to-b from-slate-900 to-black min-h-screen">
      <div className="absolute top-4 left-4 z-10">
        <TubifyTitle />
      </div>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-24">
        <div className="pt-6 pb-4 flex justify-between items-center">
          <Button variant="ghost" size="sm" onClick={() => navigate("/")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            back
          </Button>

          <div className="flex items-center gap-2">
            {hasFeedback && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefreshRecommendations}
                disabled={isRefreshing}
              >
                {isRefreshing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                refresh recommendations
              </Button>
            )}
            {hasPlayableVideos && (
              <Button
                variant="default"
                size="sm"
                onClick={handleWatchVideos}
                disabled={checkingVideos}
                className="mr-4"
              >
                {checkingVideos ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Play className="mr-2 h-4 w-4" />
                )}
                watch videos
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/recommendation-analysis")}
            >
              view recommendation analysis
            </Button>
          </div>
        </div>

        <div className="mb-8">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-white">
                music recommendations
              </h1>
              <p className="mt-2 text-slate-400">
                personalized music recommendations based on your taste
              </p>
            </div>

            {/* move the video button to the top section for easier access */}
            <div className="flex items-center">
              {analytics?.feedback_stats &&
                analytics.feedback_stats.total > 0 && (
                  <div className="bg-slate-800/50 p-4 rounded-lg border border-slate-700">
                    <h3 className="text-sm font-medium text-slate-300 mb-2">
                      your feedback
                    </h3>
                    <div className="flex items-center gap-3">
                      <div className="flex items-center text-green-400">
                        <ThumbsUp className="h-4 w-4 mr-1" />
                        <span>{analytics.feedback_stats.positive}</span>
                      </div>
                      <div className="flex items-center text-red-400">
                        <ThumbsDown className="h-4 w-4 mr-1" />
                        <span>{analytics.feedback_stats.negative}</span>
                      </div>
                    </div>
                    {analytics.feedback_stats.total >= 5 && (
                      <div className="mt-2">
                        <div className="h-2 w-full bg-slate-700 rounded-full overflow-hidden">
                          <div
                            className="h-2 bg-green-500 rounded-full"
                            style={{ width: `${feedbackPercentage}%` }}
                          />
                        </div>
                        <p className="text-xs text-slate-400 mt-1">
                          {feedbackPercentage.toFixed(0)}% positive
                        </p>
                      </div>
                    )}
                  </div>
                )}
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-700 rounded-lg text-white">
            {error}
          </div>
        )}

        <Tabs
          defaultValue="for-you"
          value={activeTab}
          onValueChange={(value) => {
            setIsLoading(false)
            setActiveTab(value)
          }}
          className="w-full"
        >
          <TabsList className="mb-6 bg-slate-800 p-1 border border-slate-700 w-full max-w-lg mx-auto">
            <TabsTrigger
              value="for-you"
              className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white font-medium"
            >
              for you
            </TabsTrigger>
            <TabsTrigger
              value="friends"
              className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white font-medium"
            >
              from friends
            </TabsTrigger>
            <TabsTrigger
              value="similar"
              className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white font-medium"
            >
              similar
            </TabsTrigger>
            <TabsTrigger
              value="lyrical"
              className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white font-medium"
            >
              lyrics
            </TabsTrigger>
          </TabsList>

          <TabsContent value="for-you">
            <div className="bg-slate-900/70 border border-slate-800 p-6 rounded-lg hover:border-slate-700 transition-colors shadow-lg">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-white">for you</h2>
                <div className="text-sm text-slate-400 flex items-center">
                  <InfoIcon className="h-4 w-4 mr-1 text-blue-400" />
                  <span>leave feedback to improve recommendations</span>
                </div>
              </div>
              <div className="mb-4">
                <p className="text-slate-400">
                  curated recommendations based on your listening habits and
                  friends
                </p>
              </div>
              {isLoading ? (
                <RecommendationSkeleton />
              ) : (
                <RecommendationsList
                  limit={20}
                  preloadedData={hybrid}
                  allRecommendations={{
                    friends: friends,
                    similar: similar,
                    lyrical: lyrical,
                  }}
                  showFeedbackButtons={true}
                  showTitle={false}
                  onFeedbackReceived={handleFeedbackReceived}
                />
              )}
            </div>
          </TabsContent>

          <TabsContent value="friends">
            <div className="bg-slate-900/70 border border-slate-800 p-6 rounded-lg hover:border-slate-700 transition-colors shadow-lg">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-white">
                  from your friends
                </h2>
              </div>
              <p className="text-slate-400 mb-4">
                music that your friends have been enjoying recently
              </p>
              {isLoading ? (
                <RecommendationSkeleton />
              ) : (
                <RecommendationsList
                  limit={20}
                  showTitle={false}
                  friendsOnly={true}
                  preloadedData={friends}
                  hideScores={true}
                  showFeedbackButtons={true}
                  onFeedbackReceived={handleFeedbackReceived}
                />
              )}
            </div>
          </TabsContent>

          <TabsContent value="similar">
            <div className="bg-slate-900/70 border border-slate-800 p-6 rounded-lg hover:border-slate-700 transition-colors shadow-lg">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-white">
                  similar to what you like
                </h2>
              </div>
              <p className="text-slate-400 mb-4">
                songs with similar audio characteristics to your liked music
              </p>
              {isLoading ? (
                <RecommendationSkeleton />
              ) : (
                <RecommendationsList
                  limit={20}
                  showTitle={false}
                  similarOnly={true}
                  preloadedData={similar}
                  hideScores={true}
                  showFeedbackButtons={true}
                  onFeedbackReceived={handleFeedbackReceived}
                />
              )}
            </div>
          </TabsContent>

          <TabsContent value="lyrical">
            <div className="bg-slate-900/70 border border-slate-800 p-6 rounded-lg hover:border-slate-700 transition-colors shadow-lg">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-white">
                  similar lyrics and themes
                </h2>
              </div>
              <p className="text-slate-400 mb-4">
                songs with similar lyrical content and themes to what you enjoy
              </p>
              {isLoading ? (
                <RecommendationSkeleton />
              ) : (
                <RecommendationsList
                  limit={20}
                  showTitle={false}
                  lyricalOnly={true}
                  preloadedData={lyrical}
                  hideScores={true}
                  showFeedbackButtons={true}
                  onFeedbackReceived={handleFeedbackReceived}
                />
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* tinder-like youtube player card overlay */}
      {showYoutubeCard && youtubeQueue.length > 0 && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
          <div
            className="relative w-full max-w-4xl mx-auto rounded-xl overflow-hidden shadow-2xl select-none"
            style={{
              transform: isDragging
                ? `translateX(${dragOffsetX}px) rotate(${dragOffsetX * 0.05}deg)`
                : "translateX(0) rotate(0)",
              transition: isDragging ? "none" : "transform 0.3s ease-out",
            }}
          >
            {/* dedicated drag area covering most of the video area */}
            <div
              className="absolute inset-0 z-20 cursor-grab"
              style={{ bottom: "180px" }} // controls draggable area
              onMouseDown={handleDragStart}
              onTouchStart={handleDragStart}
              onClick={() => {
                // reset drag state on simple click (when no dragging occurred)
                if (isDragging && Math.abs(dragOffsetX) < 10) {
                  setIsDragging(false)
                  setDragOffsetX(0)
                  setSwipeDirection(null)
                }
              }}
            >
              {/* visual indicator for the drag area */}
              <div className="flex items-center justify-center h-full w-full pointer-events-none opacity-0 hover:opacity-30 transition-opacity">
                <div className="text-white text-xs bg-black/50 px-3 py-1 rounded-full">
                  Drag to swipe
                </div>
              </div>
            </div>

            {/* full screen overlay that appears during dragging to ensure we always get all move events */}
            {isDragging && (
              <div
                className="absolute inset-0 z-30 bg-transparent"
                style={{ cursor: "grabbing" }}
              />
            )}

            {/* close button */}
            <button
              className="absolute top-4 right-4 z-50 bg-black/70 text-white p-2 rounded-full hover:bg-black/90"
              onClick={handleCloseYoutubeCard}
            >
              <X className="h-5 w-5" />
            </button>

            {/* swipe overlay indicators */}
            {swipeDirection && (
              <div
                className={`absolute inset-0 z-30 flex items-center justify-center bg-gradient-to-r ${
                  swipeDirection === "right"
                    ? "from-transparent to-green-500/30"
                    : "from-red-500/30 to-transparent"
                }`}
              >
                <div
                  className={`text-7xl ${
                    swipeDirection === "right"
                      ? "text-green-500"
                      : "text-red-500"
                  }`}
                >
                  {swipeDirection === "right" ? <ThumbsUp /> : <ThumbsDown />}
                </div>
              </div>
            )}

            {/* swipe instruction overlay */}
            <div className="absolute top-4 left-0 right-0 z-20 flex justify-center pointer-events-none">
              <div className="bg-black/70 text-white px-4 py-2 rounded-full text-sm flex items-center">
                <span>swipe left to dislike • swipe right to like</span>
              </div>
            </div>

            {/* youtube player */}
            <div
              className="w-full"
              style={{ height: "calc(100vh - 200px)", maxHeight: "80vh" }}
            >
              <RecommendationYouTubePlayer
                queue={youtubeQueue}
                initialIndex={currentYoutubeIndex}
                autoplay={true}
                onFeedback={handleYoutubeFeedback}
                hideSwipeUI={true}
              />
            </div>

            {/* manual feedback buttons moved to bottom corners with higher z-index */}
            <div className="absolute bottom-8 left-8 z-40">
              <Button
                size="lg"
                variant="outline"
                className="rounded-full bg-red-900/40 border-red-500 text-white hover:bg-red-800/60"
                onClick={() => {
                  if (youtubeQueue[currentYoutubeIndex]) {
                    handleYoutubeFeedback(
                      youtubeQueue[currentYoutubeIndex].song_id,
                      false,
                    )
                  }
                }}
              >
                <ThumbsDown className="h-6 w-6" />
              </Button>
            </div>

            <div className="absolute bottom-8 right-8 z-40">
              <Button
                size="lg"
                variant="outline"
                className="rounded-full bg-green-900/40 border-green-500 text-white hover:bg-green-800/60"
                onClick={() => {
                  if (youtubeQueue[currentYoutubeIndex]) {
                    handleYoutubeFeedback(
                      youtubeQueue[currentYoutubeIndex].song_id,
                      true,
                    )
                  }
                }}
              >
                <ThumbsUp className="h-6 w-6" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default RecommendationsPage
