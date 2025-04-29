import api from "@/lib/axios"

// cache keys
const RECOMMENDATIONS_CACHE_KEY = import.meta.env.VITE_RECOMMENDATIONS_CACHE_KEY
const YOUTUBE_RECOMMENDATIONS_CACHE_KEY = import.meta.env
  .VITE_YOUTUBE_RECOMMENDATIONS_CACHE_KEY
const RECOMMENDATIONS_CACHE_TTL = parseInt(
  import.meta.env.VITE_RECOMMENDATIONS_CACHE_TTL,
)

// interface for recommendation analytics data
interface AnalyticsData {
  taste_profile?: {
    tempo?: number
    acousticness?: number
    danceability?: number
    energy?: number
    valence?: number
    speechiness?: number
    instrumentalness?: number
    liveness?: number
    mode?: number
    key?: number
  }
  total_liked_songs?: number
  top_genres?: Array<{ name: string; count: number }>
  clusters?: {
    num_clusters: number
    song_points: Array<{
      x: number
      y: number
      cluster: number
    }>
    centers: Array<{
      x: number
      y: number
    }>
  }
  recommendation_success_rate?: number
  positive_feedback?: number
  negative_feedback?: number
  feedback_stats?: {
    total: number
    positive: number
    negative: number
  }
}

// interface for recommendation data
interface RecommendationsData {
  hybrid: RecommendedSong[]
  friends: RecommendedSong[]
  similar: RecommendedSong[]
  lyrical: RecommendedSong[]
  timestamp: number
  analytics?: AnalyticsData
}

// interface for recommendation songs
interface RecommendedSong {
  id: string
  name: string
  spotify_uri: string
  spotify_url: string
  popularity: number
  duration_ms?: number
  album_name: string
  album_image_url: string
  artist_names: string
  recommendation_score?: number
  recommendation_sources?: string[]
  similarity_score?: number
  lyrics_similarity?: number
  friends_who_like?: Array<{
    friend_id: number
    friend_name: string
    friend_image: string
  }>
}

// interface for feedback history item
interface FeedbackItem {
  song_id: string
  song_name: string
  artist_names: string
  album_name: string
  album_image_url: string
  spotify_uri: string
  liked: boolean
  feedback_at: string
}

// function to check if recommendations cache is valid
function isRecommendationsCacheValid(timestamp: number | null): boolean {
  if (!timestamp) return false

  const now = Date.now()
  // cache is valid if it's less than the TTL time
  return now - timestamp < RECOMMENDATIONS_CACHE_TTL
}

// function to get cached recommendations
function getCachedRecommendations(): RecommendationsData | null {
  try {
    const cachedData = localStorage.getItem(RECOMMENDATIONS_CACHE_KEY)
    if (!cachedData) return null

    return JSON.parse(cachedData) as RecommendationsData
  } catch (error) {
    console.error("error reading recommendations cache:", error)
    return null
  }
}

// function to set recommendations cache
function setRecommendationsCache(
  data: Omit<RecommendationsData, "timestamp">,
): void {
  try {
    const cacheData = {
      ...data,
      timestamp: Date.now(),
    }
    localStorage.setItem(RECOMMENDATIONS_CACHE_KEY, JSON.stringify(cacheData))
  } catch (error) {
    console.error("error setting recommendations cache:", error)
  }
}

// cache helpers
export function clearRecommendationsCache() {
  localStorage.removeItem(RECOMMENDATIONS_CACHE_KEY)
}

export async function recommendationsLoader() {
  try {
    // check for cached recommendations first
    const cachedRecommendations = getCachedRecommendations()
    if (
      cachedRecommendations &&
      isRecommendationsCacheValid(cachedRecommendations.timestamp)
    ) {
      // check if we have cached video availability state
      let hasPlayableVideos = false
      try {
        const videoCheckState = localStorage.getItem("tubify_video_check_state")
        if (videoCheckState) {
          const { hasVideos, timestamp } = JSON.parse(videoCheckState)
          // only use cached value if it's less than 10 minutes old
          if (timestamp && Date.now() - timestamp < 10 * 60 * 1000) {
            hasPlayableVideos = hasVideos
          }
        }
      } catch (err) {
        console.error("error reading video check cache:", err)
      }

      return {
        recommendations: {
          hybrid: cachedRecommendations.hybrid || [],
          friends: cachedRecommendations.friends || [],
          similar: cachedRecommendations.similar || [],
          lyrical: cachedRecommendations.lyrical || [],
        },
        analytics: cachedRecommendations.analytics || null,
        hasPlayableVideos,
      }
    }

    // fetch recommendations API endpoint which now includes analytics
    const apiResponse = await api.get("/api/recommendations/api-response")
    console.log("API response data:", apiResponse.data)

    // handle both 'friends' and 'from_friends' keys for backward compatibility
    const friendRecommendations =
      apiResponse.data.recommendations.friends ||
      apiResponse.data.recommendations.from_friends ||
      []

    const similarRecommendations =
      apiResponse.data.recommendations.similar || []

    const recommendationsData = {
      hybrid: apiResponse.data.recommendations.hybrid || [],
      friends: friendRecommendations,
      similar: similarRecommendations,
      lyrical: apiResponse.data.recommendations.lyrical || [],
      analytics: apiResponse.data.analytics || null,
    }

    // if the API doesn't return analytics, fetch it separately
    if (!recommendationsData.analytics) {
      try {
        const analyticsResponse = await api.get(
          "/api/recommendations/analytics",
        )
        recommendationsData.analytics = analyticsResponse.data
      } catch (error) {
        console.error("Error fetching analytics data:", error)
      }
    }

    // cache the recommendations data
    setRecommendationsCache(recommendationsData)

    // check for available videos
    let hasPlayableVideos = false
    try {
      const videoCheckResponse = await api.get(
        "/api/youtube/recommendations/check",
      )
      hasPlayableVideos = videoCheckResponse.data.has_videos || false

      // cache the video check result for 10 minutes
      localStorage.setItem(
        "tubify_video_check_state",
        JSON.stringify({
          hasVideos: hasPlayableVideos,
          timestamp: Date.now(),
        }),
      )
    } catch (error) {
      console.error("Error checking for playable videos:", error)
    }

    return {
      recommendations: {
        hybrid: recommendationsData.hybrid,
        friends: recommendationsData.friends,
        similar: recommendationsData.similar,
        lyrical: recommendationsData.lyrical,
      },
      analytics: recommendationsData.analytics,
      hasPlayableVideos,
    }
  } catch (error) {
    console.error("Error loading recommendations:", error)

    // attempt to fetch analytics separately if main request fails
    let analytics = null
    let hasPlayableVideos = false

    try {
      const analyticsResponse = await api.get("/api/recommendations/analytics")
      analytics = analyticsResponse.data
    } catch (analyticsError) {
      console.error("Error fetching analytics data:", analyticsError)
    }

    // try to get cached video check state
    try {
      const videoCheckState = localStorage.getItem("tubify_video_check_state")
      if (videoCheckState) {
        const { hasVideos, timestamp } = JSON.parse(videoCheckState)
        // only use cached value if it's less than 10 minutes old
        if (timestamp && Date.now() - timestamp < 10 * 60 * 1000) {
          hasPlayableVideos = hasVideos
        }
      }
    } catch (err) {
      console.error("error reading video check cache:", err)
    }

    // return empty arrays on error to prevent the UI from breaking
    return {
      recommendations: {
        hybrid: [],
        friends: [],
        similar: [],
        lyrical: [],
        error: "Failed to load recommendations",
      },
      analytics,
      hasPlayableVideos,
    }
  }
}

// loader for recommendation analysis page
export async function recommendationAnalysisLoader() {
  try {
    // attempt to fetch recommendation analysis
    let feedback: FeedbackItem[] = []
    let analytics: AnalyticsData | null = null

    // fetch feedback data
    try {
      const feedbackResponse = await api.get("/api/recommendations/feedback")
      feedback = feedbackResponse.data.feedback || []
    } catch (feedbackError) {
      console.error("Error fetching feedback history:", feedbackError)
    }

    // fetch analytics data
    try {
      const analyticsResponse = await api.get("/api/recommendations/analytics")
      analytics = analyticsResponse.data
    } catch (analyticsError) {
      console.error("Error fetching analytics data:", analyticsError)
    }

    return {
      feedback,
      analytics,
    }
  } catch (error) {
    console.error("Error loading feedback history:", error)
    return {
      feedback: [],
      analytics: null,
      error: "Failed to load feedback history",
    }
  }
}

// loader function for fetching YouTube videos for recommendations
export async function recommendationYouTubeQueueLoader() {
  // create cache key - we always use the 'all' endpoint now
  const cacheKey = YOUTUBE_RECOMMENDATIONS_CACHE_KEY

  // try to get from cache first
  const cachedData = localStorage.getItem(cacheKey)
  if (cachedData) {
    try {
      const parsed = JSON.parse(cachedData)
      const cacheTime = parsed.timestamp

      // if cache is less than 5 minutes old, use it
      if (cacheTime && Date.now() - cacheTime < 5 * 60 * 1000) {
        return {
          queue_items: parsed.queue_items || [],
        }
      }
    } catch (e) {
      // invalid cache, continue to fetch
      console.error("Error parsing cache:", e)
    }
  }

  // always use the 'all' recommendations endpoint
  const endpoint = "/api/youtube/recommendations/all"

  try {
    const response = await api.get(endpoint)
    const data = response.data

    // cache the result
    localStorage.setItem(
      cacheKey,
      JSON.stringify({
        queue_items: data.queue_items,
        timestamp: Date.now(),
      }),
    )

    return {
      queue_items: data.queue_items || [],
    }
  } catch (error) {
    console.error("Failed to load YouTube queue for recommendations:", error)
    return {
      error:
        "Failed to load videos for these recommendations. Please try again later.",
      queue_items: [],
    }
  }
}
