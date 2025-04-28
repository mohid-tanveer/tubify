import api from "@/lib/axios"
import { LoaderFunctionArgs } from "react-router-dom"

// define interfaces for the data structure
interface Song {
  id: string
  name: string
  artist: string[]
  album?: string
  duration_ms?: number
  spotify_uri: string
  album_art_url?: string
}

interface Playlist {
  id: number
  name: string
  description?: string
  is_public: boolean
  user_id: number
  spotify_playlist_id?: string
  created_at?: string
  updated_at?: string
  songs: Song[]
  song_count: number
}

interface SpotifyPlaylist {
  id: string
  name: string
  description?: string
  is_imported?: boolean
}

interface PlaylistsData {
  playlists: Playlist[]
  isSpotifyConnected: boolean
  spotifyPlaylists: SpotifyPlaylist[]
}

interface RecommendationsData {
  hybrid: RecommendedSong[]
  friends: RecommendedSong[]
  similar: RecommendedSong[]
  lyrical: RecommendedSong[]
  timestamp: number
  analytics?: AnalyticsData
}

// define an interface for recommendation songs
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

// define an interface for analytics data
interface AnalyticsData {
  taste_profile: {
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
  total_liked_songs: number
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

// cache keys
const PLAYLISTS_CACHE_KEY = import.meta.env.VITE_PLAYLISTS_CACHE_KEY
const PLAYLISTS_CACHE_TIMESTAMP_KEY = import.meta.env
  .VITE_PLAYLISTS_CACHE_TIMESTAMP_KEY
const PLAYLIST_DETAIL_CACHE_PREFIX = import.meta.env
  .VITE_PLAYLIST_DETAIL_CACHE_PREFIX
const PLAYLIST_DETAIL_TIMESTAMP_PREFIX = import.meta.env
  .VITE_PLAYLIST_DETAIL_TIMESTAMP_PREFIX
const RECOMMENDATIONS_CACHE_KEY = "tubify_recommendations_cache"
const CACHE_TTL = parseInt(import.meta.env.VITE_CACHE_TTL)
const RECOMMENDATIONS_CACHE_TTL = 5 * 60 * 1000 // 5 minutes in milliseconds

// function to check if cache is valid
function isCacheValid(timestamp: string | null): boolean {
  if (!timestamp) return false

  const cachedTime = parseInt(timestamp, 10)
  const now = Date.now()

  // cache is valid if it's less than TTL old
  return now - cachedTime < CACHE_TTL
}

// function to check if recommendations cache is valid
function isRecommendationsCacheValid(timestamp: number | null): boolean {
  if (!timestamp) return false

  const now = Date.now()
  // cache is valid if it's less than 5 minutes old
  return now - timestamp < RECOMMENDATIONS_CACHE_TTL
}

// function to get cached playlists
function getCachedPlaylists(): PlaylistsData | null {
  try {
    const cachedData = localStorage.getItem(PLAYLISTS_CACHE_KEY)
    if (!cachedData) return null

    return JSON.parse(cachedData) as PlaylistsData
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error reading cache:", error)
    }
    return null
  }
}

// function to get cached recommendations
function getCachedRecommendations(): RecommendationsData | null {
  try {
    const cachedData = localStorage.getItem(RECOMMENDATIONS_CACHE_KEY)
    if (!cachedData) return null

    return JSON.parse(cachedData) as RecommendationsData
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error reading recommendations cache:", error)
    }
    return null
  }
}

// function to get cached playlist detail
function getCachedPlaylistDetail(
  playlistId: string,
): { playlist: Playlist } | null {
  try {
    const cachedData = localStorage.getItem(
      `${PLAYLIST_DETAIL_CACHE_PREFIX}${playlistId}`,
    )
    if (!cachedData) return null

    return JSON.parse(cachedData) as { playlist: Playlist }
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error reading playlist detail cache:", error)
    }
    return null
  }
}

// function to set cache
export function setPlaylistsCache(data: PlaylistsData): void {
  try {
    localStorage.setItem(PLAYLISTS_CACHE_KEY, JSON.stringify(data))
    localStorage.setItem(PLAYLISTS_CACHE_TIMESTAMP_KEY, Date.now().toString())
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error setting cache:", error)
    }
  }
}

// function to set recommendations cache
export function setRecommendationsCache(
  data: Omit<RecommendationsData, "timestamp">,
): void {
  try {
    const cacheData = {
      ...data,
      timestamp: Date.now(),
    }
    localStorage.setItem(RECOMMENDATIONS_CACHE_KEY, JSON.stringify(cacheData))
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error setting recommendations cache:", error)
    }
  }
}

// function to set playlist detail cache
export function setPlaylistDetailCache(
  playlistId: string,
  data: { playlist: Playlist },
): void {
  try {
    localStorage.setItem(
      `${PLAYLIST_DETAIL_CACHE_PREFIX}${playlistId}`,
      JSON.stringify(data),
    )
    localStorage.setItem(
      `${PLAYLIST_DETAIL_TIMESTAMP_PREFIX}${playlistId}`,
      Date.now().toString(),
    )
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error setting playlist detail cache:", error)
    }
  }
}

// function to clear cache
export function clearPlaylistsCache() {
  localStorage.removeItem(PLAYLISTS_CACHE_KEY)
  localStorage.removeItem(PLAYLISTS_CACHE_TIMESTAMP_KEY)
}

// function to clear recommendations cache
export function clearRecommendationsCache() {
  localStorage.removeItem(RECOMMENDATIONS_CACHE_KEY)
}

// function to clear playlist detail cache
export function clearPlaylistDetailCache(playlistId: string) {
  localStorage.removeItem(`${PLAYLIST_DETAIL_CACHE_PREFIX}${playlistId}`)
  localStorage.removeItem(`${PLAYLIST_DETAIL_TIMESTAMP_PREFIX}${playlistId}`)
}

// function to clear all playlist detail caches
export function clearAllPlaylistDetailCaches() {
  // get all keys in localStorage
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    // if key starts with the playlist detail prefix, remove it
    if (key && key.startsWith(PLAYLIST_DETAIL_CACHE_PREFIX)) {
      localStorage.removeItem(key)
    }
    if (key && key.startsWith(PLAYLIST_DETAIL_TIMESTAMP_PREFIX)) {
      localStorage.removeItem(key)
    }
  }
}

// loader function for fetching YouTube playback queue for a playlist
export async function playlistYouTubeQueueLoader({
  params,
  request,
}: LoaderFunctionArgs) {
  // validate playlist ID
  const playlistId = params.id
  if (!playlistId) {
    return {
      error: "No playlist ID provided",
      queue_items: [],
    }
  }

  // get queue type from URL
  const url = new URL(request.url)
  const queueType = url.searchParams.get("queue_type") || "sequential"

  // create cache key
  const cacheKey = `tubify_youtube_queue_${playlistId}_${queueType}`

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
          queue_type: queueType,
        }
      }
    } catch (e) {
      // invalid cache, continue to fetch
      console.error("Error parsing cache:", e)
    }
  }

  // fetch from API
  try {
    const response = await api.get(
      `/api/youtube/playlist/${playlistId}/queue?queue_type=${queueType}`,
    )

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
      queue_type: queueType,
    }
  } catch (error) {
    console.error("Failed to load YouTube queue:", error)
    return {
      error: "Failed to load videos for this playlist. Please try again later.",
      queue_items: [],
      queue_type: queueType,
    }
  }
}

// loader function for fetching playlists data
export async function playlistsLoader() {
  try {
    // check if we have valid cached data
    const timestamp = localStorage.getItem(PLAYLISTS_CACHE_TIMESTAMP_KEY)
    if (isCacheValid(timestamp)) {
      const cachedData = getCachedPlaylists()
      if (cachedData) {
        return cachedData
      }
    }

    // check spotify connection
    const statusResponse = await api.get("/api/spotify/status")
    const isSpotifyConnected = statusResponse.data.is_connected

    // fetch tubify playlists
    const playlistsResponse = await api.get("/api/playlists")
    const playlists = playlistsResponse.data

    // fetch spotify playlists
    let spotifyPlaylists = []
    if (isSpotifyConnected) {
      const spotifyResponse = await api.get("/api/spotify/playlists")
      spotifyPlaylists = spotifyResponse.data
    }

    const data = {
      playlists,
      isSpotifyConnected,
      spotifyPlaylists,
    }

    // cache the data
    setPlaylistsCache(data)

    return data
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("failed to load playlists data:", error)
    }
    return {
      playlists: [],
      isSpotifyConnected: false,
      spotifyPlaylists: [],
    }
  }
}

// loader function for fetching a single playlist
export async function playlistDetailLoader({ params }: LoaderFunctionArgs) {
  try {
    const playlistId = params.id
    if (!playlistId) {
      throw new Error("Playlist ID is required")
    }

    // check if we have valid cached data
    const timestamp = localStorage.getItem(
      `${PLAYLIST_DETAIL_TIMESTAMP_PREFIX}${playlistId}`,
    )
    if (isCacheValid(timestamp)) {
      const cachedData = getCachedPlaylistDetail(playlistId)
      if (cachedData) {
        return cachedData
      }
    }

    const response = await api.get(`/api/playlists/${playlistId}`)

    // process the songs data if it's a string
    const playlist = response.data
    if (playlist && typeof playlist.songs === "string") {
      try {
        playlist.songs = JSON.parse(playlist.songs)
      } catch (error) {
        if (process.env.NODE_ENV === "development") {
          console.error("Error parsing songs:", error)
        }
        playlist.songs = []
      }
    }

    const data = { playlist }

    // cache the data
    setPlaylistDetailCache(playlistId, data)

    return data
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error(`failed to load playlist ${params.id}:`, error)
    }
    return {
      playlist: null,
      error: "failed to load playlist",
    }
  }
}

export async function recommendationsLoader() {
  try {
    // check for cached recommendations first
    const cachedRecommendations = getCachedRecommendations()
    if (
      cachedRecommendations &&
      isRecommendationsCacheValid(cachedRecommendations.timestamp)
    ) {
      return {
        recommendations: {
          hybrid: cachedRecommendations.hybrid || [],
          friends: cachedRecommendations.friends || [],
          similar: cachedRecommendations.similar || [],
          lyrical: cachedRecommendations.lyrical || [],
        },
        analytics: cachedRecommendations.analytics || null,
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

    return {
      recommendations: {
        hybrid: recommendationsData.hybrid,
        friends: recommendationsData.friends,
        similar: recommendationsData.similar,
        lyrical: recommendationsData.lyrical,
      },
      analytics: recommendationsData.analytics,
    }
  } catch (error) {
    console.error("Error loading recommendations:", error)

    // attempt to fetch analytics separately if main request fails
    let analytics = null
    try {
      const analyticsResponse = await api.get("/api/recommendations/analytics")
      analytics = analyticsResponse.data
    } catch (analyticsError) {
      console.error("Error fetching analytics data:", analyticsError)
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
