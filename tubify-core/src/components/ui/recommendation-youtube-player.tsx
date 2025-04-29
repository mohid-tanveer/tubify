import React, { useState, useRef, useEffect } from "react"
import YouTube, { YouTubeEvent, YouTubePlayer } from "react-youtube"
import { Button } from "./button"
import {
  SkipBack,
  SkipForward,
  Play,
  Pause,
  Music,
  X,
  ChevronDown,
  Check,
  Mic,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { QueueItem } from "./youtube-player"
import { toast } from "sonner"

// gesture detection thresholds
const SWIPE_THRESHOLD = 100 // minimum distance to consider a swipe
const SWIPE_TIMEOUT = 300 // maximum time for a swipe in ms

interface RecommendationYouTubePlayerProps {
  queue: QueueItem[]
  initialIndex?: number
  onClose?: () => void
  autoplay?: boolean
  preferLivePerformance?: boolean
  onFeedback?: (songId: string, liked: boolean) => void
  hideSwipeUI?: boolean
}

export function RecommendationYouTubePlayer({
  queue,
  initialIndex = 0,
  onClose,
  autoplay = true,
  preferLivePerformance = false,
  onFeedback,
  hideSwipeUI = false,
}: RecommendationYouTubePlayerProps) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex)
  const [isPlaying, setIsPlaying] = useState(autoplay)
  const [preferLive, setPreferLive] = useState(preferLivePerformance)
  const [selectedLiveIndex, setSelectedLiveIndex] = useState(0)
  const [showLiveOptions, setShowLiveOptions] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  // swipe gesture state
  const [touchStart, setTouchStart] = useState<{
    x: number
    y: number
    time: number
  } | null>(null)
  const [touchEnd, setTouchEnd] = useState<{
    x: number
    y: number
    time: number
  } | null>(null)
  const [swipeInProgress, setSwipeInProgress] = useState<
    "left" | "right" | null
  >(null)
  const [swipeComplete, setSwipeComplete] = useState(false)

  // reference to YouTube player
  const playerRef = useRef<YouTubePlayer | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)

  const currentItem = queue[currentIndex]

  // get the video ID based on preference (official or live)
  const getVideoId = (item: QueueItem) => {
    if (
      preferLive &&
      item.live_performances &&
      item.live_performances.length > 0
    ) {
      // use the selected live performance index if in range
      const liveIndex =
        selectedLiveIndex < item.live_performances.length
          ? selectedLiveIndex
          : 0
      return item.live_performances[liveIndex].id
    }
    return (
      item.official_video?.id ||
      (item.live_performances?.length
        ? item.live_performances[0].id
        : undefined)
    )
  }

  const currentVideoId = currentItem ? getVideoId(currentItem) : undefined

  // get current video title
  const getCurrentVideoTitle = () => {
    if (!currentItem) return ""

    if (
      preferLive &&
      currentItem.live_performances &&
      currentItem.live_performances.length > 0
    ) {
      const liveIndex =
        selectedLiveIndex < currentItem.live_performances.length
          ? selectedLiveIndex
          : 0
      return currentItem.live_performances[liveIndex].title
    }

    return (
      currentItem.official_video?.title ||
      (currentItem.live_performances?.length
        ? currentItem.live_performances[0].title
        : "")
    )
  }

  // get available live performances count
  const getLivePerformancesCount = () => {
    return currentItem?.live_performances?.length || 0
  }

  // player event handlers
  const handleReady = (event: YouTubeEvent) => {
    playerRef.current = event.target
    setDuration(playerRef.current.getDuration())

    if (autoplay) {
      playerRef.current.playVideo()
    }
  }

  const handleStateChange = (event: YouTubeEvent) => {
    const playerState = event.data

    // YouTube states: -1 (unstarted), 0 (ended), 1 (playing), 2 (paused), 3 (buffering), 5 (video cued)
    if (playerState === 1) {
      setIsPlaying(true)
    } else if (playerState === 2) {
      setIsPlaying(false)
    } else if (playerState === 0) {
      // video ended, play next
      playNext()
    }
  }

  const handleError = (event: YouTubeEvent) => {
    console.error("YouTube player error:", event)
    // if error, try to play next video
    playNext()
  }

  // player controls
  const playPause = () => {
    if (!playerRef.current) return

    if (isPlaying) {
      playerRef.current.pauseVideo()
    } else {
      playerRef.current.playVideo()
    }

    setIsPlaying(!isPlaying)
  }

  const playNext = () => {
    if (currentIndex < queue.length - 1) {
      setCurrentIndex(currentIndex + 1)
      setSelectedLiveIndex(0)
    } else {
      // we're at the end, loop back to the beginning
      setCurrentIndex(0)
      setSelectedLiveIndex(0)
    }
  }

  const playPrevious = () => {
    // if we're more than 3 seconds into the video, restart it
    if (currentTime > 3) {
      playerRef.current?.seekTo(0, true)
      return
    }

    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
      setSelectedLiveIndex(0)
    } else {
      // we're at the beginning, loop to the end
      setCurrentIndex(queue.length - 1)
      setSelectedLiveIndex(0)
    }
  }

  // toggle between official and live performances
  const togglePreference = () => {
    setPreferLive(!preferLive)
    setSelectedLiveIndex(0)

    // save preference to localStorage
    localStorage.setItem("tubify_prefer_live", (!preferLive).toString())
  }

  // select a specific live performance
  const selectLivePerformance = (index: number) => {
    setSelectedLiveIndex(index)
    setShowLiveOptions(false)
  }

  // handle swipe/feedback gestures
  const handleTouchStart = (e: React.TouchEvent) => {
    // if swipe UI is hidden, don't handle touch events here
    if (hideSwipeUI) return

    // prevent default to avoid text selection
    e.preventDefault()
    e.stopPropagation() // stop event from bubbling up

    setTouchStart({
      x: e.touches[0].clientX,
      y: e.touches[0].clientY,
      time: Date.now(),
    })
    setTouchEnd(null)
    setSwipeInProgress(null)
    setSwipeComplete(false)
  }

  const handleTouchMove = (e: React.TouchEvent) => {
    // if swipe UI is hidden, don't handle touch events here
    if (hideSwipeUI) return

    // prevent default to avoid text selection during drag
    e.preventDefault()
    e.stopPropagation() // stop event from bubbling up

    if (!touchStart) return

    const xDiff = e.touches[0].clientX - touchStart.x

    // determine swipe direction
    if (Math.abs(xDiff) > 30) {
      setSwipeInProgress(xDiff > 0 ? "right" : "left")
    }

    setTouchEnd({
      x: e.touches[0].clientX,
      y: e.touches[0].clientY,
      time: Date.now(),
    })
  }

  const handleTouchEnd = (e: React.TouchEvent) => {
    // if swipe UI is hidden, don't handle touch events here
    if (hideSwipeUI) return

    // prevent default behavior
    e.preventDefault()
    e.stopPropagation() // stop event from bubbling up

    if (!touchStart || !touchEnd) return

    const xDiff = touchEnd.x - touchStart.x
    const timeDiff = touchEnd.time - touchStart.time

    // check if it's a valid swipe (distance and time)
    if (Math.abs(xDiff) > SWIPE_THRESHOLD && timeDiff < SWIPE_TIMEOUT) {
      setSwipeComplete(true)

      if (xDiff > 0) {
        // swipe right - like
        handleFeedback(true)
        toast.success("song liked!")
      } else {
        // swipe left - dislike
        handleFeedback(false)
        toast.error("song disliked")
      }

      // auto play next after feedback
      setTimeout(() => {
        playNext()
        setSwipeComplete(false)
        setSwipeInProgress(null)
      }, 500)
    } else {
      setSwipeInProgress(null)
    }

    setTouchStart(null)
    setTouchEnd(null)
  }

  // handle manual feedback button press
  const handleFeedback = (liked: boolean) => {
    if (!currentItem) return

    if (onFeedback) {
      onFeedback(currentItem.song_id, liked)
    }
  }

  // update current time
  useEffect(() => {
    let interval: NodeJS.Timeout

    if (isPlaying && playerRef.current) {
      interval = setInterval(() => {
        setCurrentTime(playerRef.current?.getCurrentTime() || 0)
      }, 1000)
    }

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isPlaying])

  // close live options dropdown if clicked outside
  useEffect(() => {
    if (showLiveOptions) {
      const handleClickOutside = (event: MouseEvent) => {
        const target = event.target as HTMLElement
        if (!target.closest(".live-options-dropdown")) {
          setShowLiveOptions(false)
        }
      }

      document.addEventListener("mousedown", handleClickOutside)
      return () => {
        document.removeEventListener("mousedown", handleClickOutside)
      }
    }
  }, [showLiveOptions])

  // format time (seconds) to mm:ss
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs < 10 ? "0" + secs : secs}`
  }

  // YouTube player options
  const opts = {
    width: "100%",
    height: "100%",
    playerVars: {
      autoplay: autoplay ? 1 : 0,
      modestbranding: 1,
      rel: 0,
    },
  }

  // calculate swipe overlay styles
  const getSwipeOverlayStyle = () => {
    if (!swipeInProgress) return {}

    const opacity = Math.min(
      Math.abs((touchEnd?.x || 0) - (touchStart?.x || 0)) / 200,
      0.9,
    )

    return {
      opacity: swipeComplete ? 1 : opacity,
      background:
        swipeInProgress === "right"
          ? "linear-gradient(to right, transparent, rgba(34, 197, 94, 0.3))"
          : "linear-gradient(to left, transparent, rgba(239, 68, 68, 0.3))",
    }
  }

  // if no queue or no video ID, show placeholder
  if (!currentItem || !currentVideoId) {
    return (
      <div className="flex flex-col items-center justify-center bg-black h-full w-full">
        <Music className="h-16 w-16 text-gray-500 mb-4" />
        <p className="text-gray-400">no videos available</p>
        {onClose && (
          <Button variant="outline" className="mt-4" onClick={onClose}>
            close
          </Button>
        )}
      </div>
    )
  }

  const liveCount = getLivePerformancesCount()

  return (
    <div
      ref={containerRef}
      className="flex flex-col h-full w-full bg-black relative overflow-hidden select-none"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* video container */}
      <div className="relative flex-grow overflow-hidden">
        <div className="absolute inset-0">
          <YouTube
            videoId={currentVideoId}
            opts={opts}
            onReady={handleReady}
            onStateChange={handleStateChange}
            onError={handleError}
            className="w-full h-full"
          />
        </div>

        {/* swipe overlay */}
        {!hideSwipeUI && swipeInProgress && (
          <div
            className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none"
            style={getSwipeOverlayStyle()}
          >
            <div
              className={`text-7xl ${swipeInProgress === "right" ? "text-green-500" : "text-red-500"}`}
            >
              {swipeInProgress === "right" ? <ThumbsUp /> : <ThumbsDown />}
            </div>
          </div>
        )}

        {/* swipe instruction overlay */}
        {!hideSwipeUI && (
          <div className="absolute top-16 left-0 right-0 flex justify-center pointer-events-none">
            <div className="bg-black/70 text-white px-4 py-2 rounded-full text-sm flex items-center">
              <span className="mr-2">swipe left to dislike</span>
              <ThumbsDown className="h-4 w-4 text-red-500 mr-4" />
              <ThumbsUp className="h-4 w-4 text-green-500 mr-2" />
              <span>swipe right to like</span>
            </div>
          </div>
        )}

        {/* feedback buttons moved to bottom corners */}
        {!hideSwipeUI && (
          <>
            <div className="absolute bottom-8 left-8 z-40">
              <Button
                size="icon"
                variant="outline"
                className="rounded-full bg-red-900/40 border-red-500 text-white hover:bg-red-800/60 h-12 w-12"
                onClick={() => handleFeedback(false)}
              >
                <ThumbsDown className="h-6 w-6" />
              </Button>
            </div>

            <div className="absolute bottom-8 right-8 z-40">
              <Button
                size="icon"
                variant="outline"
                className="rounded-full bg-green-900/40 border-green-500 text-white hover:bg-green-800/60 h-12 w-12"
                onClick={() => handleFeedback(true)}
              >
                <ThumbsUp className="h-6 w-6" />
              </Button>
            </div>
          </>
        )}

        {onClose && (
          <button
            className="absolute top-4 right-4 bg-black/70 text-white p-2 rounded-full z-50 hover:bg-black/90"
            onClick={onClose}
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* controls overlay at bottom */}
      <div className="bg-black/90 p-4 w-full">
        {/* song info */}
        <div className="flex justify-between items-center mb-2">
          <div className="flex-1 mr-4">
            <h3 className="text-white font-medium truncate">
              {currentItem.name}
            </h3>
            <p className="text-gray-400 text-sm truncate">
              {currentItem.artist.join(", ")} • {currentItem.album}
            </p>
            {preferLive && liveCount > 0 && (
              <div className="text-xs text-gray-500 mt-1 truncate">
                {getCurrentVideoTitle()}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* performance preference toggle */}
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                "text-xs rounded-full",
                preferLive
                  ? "bg-rose-900/30 text-rose-500"
                  : "bg-blue-900/30 text-blue-500",
              )}
              onClick={togglePreference}
            >
              {preferLive ? (
                <>
                  <Mic className="h-3 w-3 mr-1" />
                  live
                </>
              ) : (
                <>
                  <Music className="h-3 w-3 mr-1" />
                  official
                </>
              )}
            </Button>

            {/* live performance selector (only show if there are live performances and we're in live mode) */}
            {preferLive && liveCount > 1 && (
              <div className="relative live-options-dropdown">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs rounded-full bg-slate-800/70 text-white"
                  onClick={() => setShowLiveOptions(!showLiveOptions)}
                >
                  <span className="mr-1">
                    {selectedLiveIndex + 1}/{liveCount}
                  </span>
                  <ChevronDown className="h-3 w-3" />
                </Button>

                {showLiveOptions && (
                  <div className="absolute right-0 bottom-full mb-1 bg-slate-900 rounded-md shadow-lg overflow-hidden z-50 w-56 border border-slate-800">
                    <div className="p-2 border-b border-slate-800 text-xs text-slate-400">
                      select performance
                    </div>
                    <div className="max-h-48 overflow-y-auto py-1">
                      {currentItem.live_performances.map((performance, idx) => (
                        <button
                          key={performance.id}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-slate-800 flex items-center justify-between"
                          onClick={() => selectLivePerformance(idx)}
                        >
                          <span className="truncate mr-2 text-white">
                            {idx + 1}. {performance.title}
                          </span>
                          {idx === selectedLiveIndex && (
                            <Check className="h-4 w-4 text-green-500 flex-shrink-0" />
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* progress bar */}
        <div className="h-1 bg-slate-700 rounded-full mb-1 relative">
          <div
            className="absolute h-full bg-green-500 rounded-full"
            style={{ width: `${(currentTime / duration) * 100}%` }}
          ></div>
        </div>

        <div className="flex justify-between text-xs text-gray-400 mb-3">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>

        {/* playback and feedback controls */}
        <div className="flex justify-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            className="text-gray-300 hover:text-white"
            onClick={playPrevious}
          >
            <SkipBack className="h-5 w-5" />
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="text-gray-300 hover:text-white"
            onClick={playPause}
          >
            {isPlaying ? (
              <Pause className="h-5 w-5" />
            ) : (
              <Play className="h-5 w-5" />
            )}
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="text-gray-300 hover:text-white"
            onClick={playNext}
          >
            <SkipForward className="h-5 w-5" />
          </Button>
        </div>

        {/* song count indicator */}
        <div className="text-xs text-center text-slate-500 mt-3">
          {currentIndex + 1} of {queue.length}
        </div>
      </div>
    </div>
  )
}
