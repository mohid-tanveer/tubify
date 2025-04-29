import React, { useState, useEffect, useCallback } from "react"
import api from "@/lib/axios"
import { Button } from "./button"
import { Spinner } from "./spinner"
import { RecommendationSongItem } from "./recommendation-song-item"

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

interface RecommendationsListProps {
  limit?: number
  showTitle?: boolean
  friendsOnly?: boolean
  similarOnly?: boolean
  lyricalOnly?: boolean
  preloadedData?: RecommendedSong[]
  allRecommendations?: {
    friends: RecommendedSong[]
    similar: RecommendedSong[]
    lyrical: RecommendedSong[]
  }
  hideScores?: boolean
  showFeedbackButtons?: boolean
  onFeedbackReceived?: () => void
}

const RecommendationsList: React.FC<RecommendationsListProps> = ({
  limit = 10,
  showTitle = true,
  friendsOnly = false,
  similarOnly = false,
  lyricalOnly = false,
  preloadedData,
  allRecommendations,
  hideScores = false,
  showFeedbackButtons = true,
  onFeedbackReceived,
}) => {
  const [recommendations, setRecommendations] = useState<RecommendedSong[]>(
    preloadedData || [],
  )
  const [loading, setLoading] = useState<boolean>(!preloadedData)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<
    "hybrid" | "friends" | "similar" | "lyrical"
  >(
    friendsOnly
      ? "friends"
      : similarOnly
        ? "similar"
        : lyricalOnly
          ? "lyrical"
          : "hybrid",
  )

  const fetchRecommendations = useCallback(async () => {
    if (preloadedData) {
      setRecommendations(preloadedData)
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    try {
      let endpoint = "/api/recommendations"

      if (activeTab === "friends") {
        endpoint = "/api/recommendations/friends"
      } else if (activeTab === "similar") {
        endpoint = "/api/recommendations/similar"
      } else if (activeTab === "lyrical") {
        endpoint = "/api/recommendations/lyrical"
      }

      const response = await api.get(`${endpoint}?limit=${limit}`)

      if (activeTab === "hybrid") {
        setRecommendations(response.data.recommendations.hybrid || [])
      } else {
        setRecommendations(response.data.recommendations || [])
      }
    } catch (err) {
      console.error("Failed to fetch recommendations:", err)
      setError("Failed to load recommendations. Please try again later.")
      setRecommendations([])
    } finally {
      setLoading(false)
    }
  }, [activeTab, limit, preloadedData])

  // when allRecommendations is provided and tab changes, use those instead of fetching
  useEffect(() => {
    if (allRecommendations) {
      if (activeTab === "friends") {
        setRecommendations(allRecommendations.friends || [])
      } else if (activeTab === "similar") {
        setRecommendations(allRecommendations.similar || [])
      } else if (activeTab === "lyrical") {
        setRecommendations(allRecommendations.lyrical || [])
      } else {
        setRecommendations(preloadedData || [])
      }
      setLoading(false)
      return
    }

    fetchRecommendations()
  }, [fetchRecommendations, activeTab, allRecommendations, preloadedData])

  const handleTabChange = (
    tab: "hybrid" | "friends" | "similar" | "lyrical",
  ) => {
    setActiveTab(tab)
  }

  // new function to handle feedback changes
  const handleFeedbackChange = (songId: string, liked: boolean) => {
    console.log(`Feedback changed for song ${songId} - liked: ${liked}`)

    // notify parent component that feedback was received
    if (onFeedbackReceived) {
      onFeedbackReceived()
    }

    // update local state with the new feedback
    setRecommendations((prev) => {
      const updated = prev.map((song) =>
        song.id === songId ? { ...song, user_feedback: liked } : song,
      )
      console.log(
        `Updated ${updated.filter((s) => s.id === songId).length} songs in current view (${activeTab})`,
      )
      return updated
    })

    // if we have allRecommendations, update those too so switching tabs preserves feedback
    if (allRecommendations) {
      console.log("Updating allRecommendations object with feedback")

      // need to update all recommendation types - hybrid may be in preloadedData
      if (preloadedData) {
        const updatedPreloaded = preloadedData.map((song) =>
          song.id === songId ? { ...song, user_feedback: liked } : song,
        )
        console.log(
          `Updated ${updatedPreloaded.filter((s) => s.id === songId).length} songs in preloadedData (hybrid)`,
        )
        // this is a mutable update to ensure the parent component sees the changes
        preloadedData.forEach((song, index) => {
          if (song.id === songId) {
            preloadedData[index].user_feedback = liked
          }
        })
      }

      // update each tab's song list
      Object.keys(allRecommendations).forEach((key) => {
        const typedKey = key as "friends" | "similar" | "lyrical"
        if (allRecommendations[typedKey]) {
          const count = allRecommendations[typedKey].filter(
            (s) => s.id === songId,
          ).length
          if (count > 0) {
            console.log(`Updating ${count} songs in ${key} view`)

            // this is a mutable update to ensure the parent component sees the changes
            allRecommendations[typedKey].forEach((song, index) => {
              if (song.id === songId) {
                allRecommendations[typedKey][index].user_feedback = liked
              }
            })

            console.log(
              `After update, ${allRecommendations[typedKey].filter((s) => s.id === songId && s.user_feedback === liked).length} songs have updated feedback in ${key}`,
            )
          }
        }
      })
    }
  }

  return (
    <div className="w-full">
      {showTitle && (
        <div className="flex items-center justify-between mb-4 flex-wrap">
          <h2 className="text-xl font-bold text-white">recommended for you</h2>

          {!friendsOnly && !similarOnly && !lyricalOnly && (
            <div className="flex space-x-2 flex-wrap mt-2 sm:mt-0">
              <Button
                variant={activeTab === "hybrid" ? "default" : "outline"}
                size="sm"
                onClick={() => handleTabChange("hybrid")}
                className="mb-1"
              >
                all
              </Button>
              <Button
                variant={activeTab === "friends" ? "default" : "outline"}
                size="sm"
                onClick={() => handleTabChange("friends")}
                className="mb-1"
              >
                from friends
              </Button>
              <Button
                variant={activeTab === "similar" ? "default" : "outline"}
                size="sm"
                onClick={() => handleTabChange("similar")}
                className="mb-1"
              >
                similar music
              </Button>
              <Button
                variant={activeTab === "lyrical" ? "default" : "outline"}
                size="sm"
                onClick={() => handleTabChange("lyrical")}
                className="mb-1"
              >
                similar lyrics
              </Button>
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center items-center h-40">
          <Spinner size="lg" />
        </div>
      ) : error ? (
        <div className="text-center text-red-500 p-4 border border-red-700/50 bg-red-900/20 rounded-lg">
          {error}
        </div>
      ) : recommendations.length === 0 ? (
        <div className="text-center text-slate-400 py-8 border border-slate-700/50 bg-slate-800/20 rounded-lg">
          <p className="mb-2">no recommendations available</p>
          <p className="text-sm">
            try liking more songs to get personalized recommendations!
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {recommendations.map((song) => {
            // determine what kind of data to show based on current view
            const isFriendsTab = activeTab === "friends" || friendsOnly
            const isSimilarTab = activeTab === "similar" || similarOnly
            const isLyricalTab = activeTab === "lyrical" || lyricalOnly

            // check if song has friend data
            const hasFriendData =
              song.friends_who_like &&
              (Array.isArray(song.friends_who_like)
                ? song.friends_who_like.length > 0
                : true)

            // song is from friend recommendations in hybrid view
            const isFromFriendRecs =
              activeTab === "hybrid" &&
              song.recommendation_sources?.includes("friends")

            return (
              <div
                key={song.id}
                className="relative bg-slate-800/30 hover:bg-slate-800/60 rounded-md transition-colors p-3"
              >
                <RecommendationSongItem
                  song={song}
                  showFriendData={
                    (isFriendsTab || isFromFriendRecs) && hasFriendData
                  }
                  showSimilarityScore={
                    isSimilarTab ||
                    (activeTab === "hybrid" &&
                      song.recommendation_sources?.includes("similar_music"))
                  }
                  showLyricalScore={isLyricalTab}
                  hideScores={hideScores}
                  showFeedback={showFeedbackButtons}
                  onFeedbackChange={handleFeedbackChange}
                />
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default RecommendationsList
