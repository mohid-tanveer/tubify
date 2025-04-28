import { Button } from "@/components/ui/button"
import { Music, Play, UserCircle, Disc, Mic } from "lucide-react"
import React from "react"
import RecommendationFeedback from "./recommendation-feedback"

// recommendation song type
interface RecommendedSong {
  id: string
  name: string
  artist_names: string
  album_name: string
  duration_ms?: number
  spotify_uri: string
  album_image_url: string
  similarity_score?: number
  lyrics_similarity?: number
  friends_who_like?: Array<{
    friend_id: number
    friend_name: string
    friend_image: string
  }>
  user_feedback?: boolean
  recommendation_id?: number
}

// format duration from ms to mm:ss
const formatDuration = (ms: number | undefined) => {
  if (!ms) return "--:--"
  const minutes = Math.floor(ms / 60000)
  const seconds = Math.floor((ms % 60000) / 1000)
  return `${minutes}:${seconds.toString().padStart(2, "0")}`
}

// helper function to get friends names
const getFriendsNames = (friends: unknown): string => {
  if (!friends) return "friends"

  if (Array.isArray(friends)) {
    return friends.map((f) => f.friend_name).join(", ")
  }

  // if it's a string, try to parse it
  if (typeof friends === "string") {
    try {
      const parsed = JSON.parse(friends)
      if (Array.isArray(parsed)) {
        return parsed.map((f) => f.friend_name).join(", ")
      }
    } catch {
      // parsing failed
    }
  }

  return "friends"
}

interface RecommendationSongItemProps {
  song: RecommendedSong
  showFriendData?: boolean
  showSimilarityScore?: boolean
  showLyricalScore?: boolean
  hideScores?: boolean
  showFeedback?: boolean
  onFeedbackChange?: (songId: string, liked: boolean) => void
}

export function RecommendationSongItem({
  song,
  showFriendData = false,
  showSimilarityScore = false,
  showLyricalScore = false,
  hideScores = true,
  showFeedback = false,
  onFeedbackChange,
}: RecommendationSongItemProps) {
  const handlePlayPreview = (e: React.MouseEvent) => {
    e.stopPropagation()

    if (song.spotify_uri) {
      window.open(song.spotify_uri, "_blank")
    }
  }

  return (
    <div className="flex flex-col space-y-1.5">
      {/* main song info row */}
      <div className="flex items-center">
        <div className="flex items-center space-x-3 flex-grow overflow-hidden">
          {/* album art */}
          {song.album_image_url ? (
            <img
              src={song.album_image_url}
              alt={song.name}
              className="h-10 w-10 rounded-md object-cover shadow-md flex-shrink-0"
            />
          ) : (
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-slate-800 shadow-md flex-shrink-0">
              <Music className="h-5 w-5 text-slate-500" />
            </div>
          )}

          {/* song details */}
          <div className="overflow-hidden min-w-0">
            <div className="font-medium text-white text-sm truncate">
              {song.name}
            </div>
            <div className="text-xs text-slate-400 truncate">
              {song.artist_names} • {song.album_name}
            </div>
          </div>
        </div>

        {/* actions container - play, duration, feedback */}
        <div className="flex items-center gap-1 ml-2">
          {/* play button */}
          {song.spotify_uri && (
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 rounded-full hover:bg-green-900/50 hover:text-green-400 transition-colors flex-shrink-0"
              onClick={handlePlayPreview}
            >
              <Play className="h-4 w-4" />
            </Button>
          )}

          {/* duration */}
          <span className="text-xs text-slate-400 font-medium w-10 text-right flex-shrink-0 mr-1">
            {formatDuration(song.duration_ms)}
          </span>

          {/* feedback buttons */}
          {showFeedback && (
            <div className="flex-shrink-0">
              <RecommendationFeedback
                songId={song.id}
                recommendationId={song.recommendation_id}
                initialFeedback={song.user_feedback}
                onFeedbackChange={onFeedbackChange}
                mini={true}
              />
            </div>
          )}
        </div>
      </div>

      {/* additional info row (friends, similarity) */}
      {(showFriendData || showSimilarityScore || showLyricalScore) && (
        <div className="ml-12 text-xs text-slate-400">
          {showFriendData && song.friends_who_like && (
            <div className="flex items-center">
              <UserCircle className="h-3 w-3 mr-1 text-blue-500" />
              <span className="truncate">
                liked by: {getFriendsNames(song.friends_who_like)}
              </span>
            </div>
          )}

          {showSimilarityScore && (
            <div className="flex items-center">
              <Disc className="h-3 w-3 mr-1 text-purple-500" />
              <span className="truncate">similar to music you like</span>
              {!hideScores && song.similarity_score !== undefined && (
                <span className="ml-1 text-[10px] text-purple-400">
                  (score: {song.similarity_score.toFixed(3)})
                </span>
              )}
            </div>
          )}

          {showLyricalScore && song.lyrics_similarity !== undefined && (
            <div className="flex items-center">
              <Mic className="h-3 w-3 mr-1 text-green-500" />
              <span className="truncate">similar lyrical themes</span>
              {!hideScores && (
                <span className="ml-1 text-[10px] text-green-400">
                  (score: {song.lyrics_similarity.toFixed(3)})
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
