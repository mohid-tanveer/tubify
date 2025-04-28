import api from "@/lib/axios"

// cache keys
const LISTENING_HABITS_CACHE_KEY = import.meta.env
  .VITE_LISTENING_HABITS_CACHE_KEY
const LISTENING_HABITS_TIMESTAMP_KEY = import.meta.env
  .VITE_LISTENING_HABITS_TIMESTAMP_KEY
const CACHE_TTL = parseInt(import.meta.env.VITE_LISTENING_HABITS_CACHE_TTL)

interface ListeningHabitsParams {
  artists_time_range: string
  genres_time_range: string
  trends_time_range: string
}

interface ListeningHabitsData {
  top_artists: Array<{ name: string; play_count: number; image_url?: string }>
  top_genres: Array<{ name: string; play_count: number }>
  listening_trends: Array<{ date: string; play_count: number }>
}

// function to check if cache is valid
function isCacheValid(timestamp: string | null): boolean {
  if (!timestamp) return false

  const cachedTime = parseInt(timestamp, 10)
  const now = Date.now()

  // cache is valid if it's less than TTL old
  return now - cachedTime < CACHE_TTL
}

// function to get cached data
function getCachedData(
  params: ListeningHabitsParams,
): ListeningHabitsData | null {
  try {
    const cacheKey = `${LISTENING_HABITS_CACHE_KEY}_${params.artists_time_range}_${params.genres_time_range}_${params.trends_time_range}`
    const cachedData = localStorage.getItem(cacheKey)
    if (!cachedData) return null

    return JSON.parse(cachedData) as ListeningHabitsData
  } catch (error) {
    console.error("error reading cache:", error)
    return null
  }
}

// function to set cache
function setCacheData(
  data: ListeningHabitsData,
  params: ListeningHabitsParams,
): void {
  try {
    const cacheKey = `${LISTENING_HABITS_CACHE_KEY}_${params.artists_time_range}_${params.genres_time_range}_${params.trends_time_range}`
    const timestampKey = `${LISTENING_HABITS_TIMESTAMP_KEY}_${params.artists_time_range}_${params.genres_time_range}_${params.trends_time_range}`

    localStorage.setItem(cacheKey, JSON.stringify(data))
    localStorage.setItem(timestampKey, Date.now().toString())
  } catch (error) {
    console.error("error setting cache:", error)
  }
}

export async function loader() {
  try {
    // default time ranges
    const defaultParams: ListeningHabitsParams = {
      artists_time_range: "medium_term",
      genres_time_range: "medium_term",
      trends_time_range: "month",
    }

    // check if we have valid cached data for these parameters
    const timestampKey = `${LISTENING_HABITS_TIMESTAMP_KEY}_${defaultParams.artists_time_range}_${defaultParams.genres_time_range}_${defaultParams.trends_time_range}`
    const timestamp = localStorage.getItem(timestampKey)

    if (isCacheValid(timestamp)) {
      const cachedData = getCachedData(defaultParams)
      if (cachedData) {
        return cachedData
      }
    }

    const response = await api.get<ListeningHabitsData>(
      "/api/listening-habits",
      {
        params: defaultParams,
      },
    )

    // cache the data
    setCacheData(response.data, defaultParams)

    return response.data
  } catch (error) {
    console.error("error loading listening habits:", error)
    // return empty data structure to prevent ui errors
    return {
      top_artists: [],
      top_genres: [],
      listening_trends: [],
    }
  }
}
