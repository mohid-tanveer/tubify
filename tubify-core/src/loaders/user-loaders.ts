import { LoaderFunctionArgs } from "react-router-dom"
import api from "@/lib/axios"

// define interfaces for the data structure
interface Song {
  id: string
  name: string
  artist: string[]
  album?: string
  duration_ms?: number
  spotify_uri: string
  album_art_url?: string
  created_at: string
}

interface Playlist {
  id: number
  public_id: string
  name: string
  description?: string
  is_public: boolean
  image_url?: string
  created_at: string
  updated_at: string
  song_count: number
}

interface UserPlaylist extends Playlist {
  songs: Song[]
  username: string
}

interface UserProfile {
  username: string
  profilePicture: string
  bio: string
  playlistCount: number
}

interface UserPlaylistsData {
  username: string
  playlists: Playlist[]
}

interface UserProfileData {
  profile: UserProfile
}

interface UserPlaylistData {
  playlist: UserPlaylist
}

export interface ProfileData {
  profile: {
    user_name: string
    profile_picture: string
    bio: string
  } | null
  friends: Array<{
    id: number
    username: string
    profile_picture: string
  }>
  friendRequests: Array<{
    sender_id: number
    receiver_id: number
    status: string
    username: string
  }>
  isSpotifyConnected: boolean
  likedSongs?: {
    count: number
    syncStatus: string
    lastSynced: string | null
  }
}

// interface for liked songs
interface LikedSong {
  id: string
  name: string
  artist: string
  album: string
  duration_ms: number
  album_art_url: string | null
  liked_at: string
  is_shared?: boolean
}

interface LikedSongsStats {
  friend_likes_count: number
  shared_likes_count: number
  user_likes_count: number
  friend_unique_count: number
  compatibility_percentage: number
}

interface LikedSongsData {
  songs: LikedSong[]
  totalCount: number
  stats?: LikedSongsStats
  error?: string
}

// cache keys
const USER_PROFILE_CACHE_KEY = import.meta.env.VITE_USER_PROFILE_CACHE_KEY
const USER_PROFILE_CACHE_TIMESTAMP_KEY = import.meta.env
  .VITE_USER_PROFILE_CACHE_TIMESTAMP_KEY
const USER_PLAYLISTS_CACHE_KEY = import.meta.env.VITE_USER_PLAYLISTS_CACHE_KEY
const USER_PLAYLISTS_CACHE_TIMESTAMP_KEY = import.meta.env
  .VITE_USER_PLAYLISTS_CACHE_TIMESTAMP_KEY
const USER_PLAYLIST_CACHE_KEY = import.meta.env.VITE_USER_PLAYLIST_CACHE_KEY
const USER_PLAYLIST_CACHE_TIMESTAMP_KEY = import.meta.env
  .VITE_USER_PLAYLIST_CACHE_TIMESTAMP_KEY
const USER_CACHE_DURATION = parseInt(import.meta.env.VITE_USER_CACHE_DURATION)

// cache keys for liked songs
const LIKED_SONGS_CACHE_KEY = import.meta.env.VITE_LIKED_SONGS_CACHE_KEY
const LIKED_SONGS_CACHE_TIMESTAMP_KEY = import.meta.env
  .VITE_LIKED_SONGS_CACHE_TIMESTAMP_KEY
const FRIEND_LIKED_SONGS_CACHE_PREFIX = import.meta.env
  .VITE_FRIEND_LIKED_SONGS_CACHE_PREFIX
const FRIEND_LIKED_SONGS_TIMESTAMP_PREFIX = import.meta.env
  .VITE_FRIEND_LIKED_SONGS_TIMESTAMP_PREFIX

// function to check if cache is valid
function isCacheValid(timestamp: string | null): boolean {
  if (!timestamp) return false

  const cachedTime = parseInt(timestamp, 10)
  const now = Date.now()

  // cache is valid if it's less than TTL old
  return now - cachedTime < USER_CACHE_DURATION
}

// function to get cached user profile
function getCachedUserProfile(username: string): UserProfileData | null {
  try {
    const cachedData = localStorage.getItem(
      `${USER_PROFILE_CACHE_KEY}${username}`,
    )
    if (!cachedData) return null

    return JSON.parse(cachedData) as UserProfileData
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error reading user profile cache:", error)
    }
    return null
  }
}

// function to get cached user playlists
function getCachedUserPlaylists(username: string): UserPlaylistsData | null {
  try {
    const cachedData = localStorage.getItem(
      `${USER_PLAYLISTS_CACHE_KEY}${username}`,
    )
    if (!cachedData) return null

    return JSON.parse(cachedData) as UserPlaylistsData
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error reading user playlists cache:", error)
    }
    return null
  }
}

// function to get cached public playlist
function getCachedUserPlaylist(playlistId: string): UserPlaylistData | null {
  try {
    const cachedData = localStorage.getItem(
      `${USER_PLAYLIST_CACHE_KEY}${playlistId}`,
    )
    if (!cachedData) return null

    return JSON.parse(cachedData) as UserPlaylistData
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error reading public playlist cache:", error)
    }
    return null
  }
}

// function to set user profile cache
export function setUserProfileCache(
  username: string,
  data: UserProfileData,
): void {
  try {
    localStorage.setItem(
      `${USER_PROFILE_CACHE_KEY}${username}`,
      JSON.stringify(data),
    )
    localStorage.setItem(
      `${USER_PROFILE_CACHE_TIMESTAMP_KEY}${username}`,
      Date.now().toString(),
    )
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error setting user profile cache:", error)
    }
  }
}

// function to set user playlists cache
export function setUserPlaylistsCache(
  username: string,
  data: UserPlaylistsData,
): void {
  try {
    localStorage.setItem(
      `${USER_PLAYLISTS_CACHE_KEY}${username}`,
      JSON.stringify(data),
    )
    localStorage.setItem(
      `${USER_PLAYLISTS_CACHE_TIMESTAMP_KEY}${username}`,
      Date.now().toString(),
    )
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error setting user playlists cache:", error)
    }
  }
}

// function to set user playlist cache
export function setUserPlaylistCache(
  playlistId: string,
  data: UserPlaylistData,
): void {
  try {
    localStorage.setItem(
      `${USER_PLAYLIST_CACHE_KEY}${playlistId}`,
      JSON.stringify(data),
    )
    localStorage.setItem(
      `${USER_PLAYLIST_CACHE_TIMESTAMP_KEY}${playlistId}`,
      Date.now().toString(),
    )
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error setting public playlist cache:", error)
    }
  }
}

// function to clear user profile cache
export function clearUserProfileCache(username: string): void {
  localStorage.removeItem(`${USER_PROFILE_CACHE_KEY}${username}`)
  localStorage.removeItem(`${USER_PROFILE_CACHE_TIMESTAMP_KEY}${username}`)
}

// function to clear user playlists cache
export function clearUserPlaylistsCache(username: string): void {
  localStorage.removeItem(`${USER_PLAYLISTS_CACHE_KEY}${username}`)
  localStorage.removeItem(`${USER_PLAYLISTS_CACHE_TIMESTAMP_KEY}${username}`)
}

// function to clear public playlist cache
export function clearUserPlaylistCache(playlistId: string): void {
  localStorage.removeItem(`${USER_PLAYLIST_CACHE_KEY}${playlistId}`)
  localStorage.removeItem(`${USER_PLAYLIST_CACHE_TIMESTAMP_KEY}${playlistId}`)
}

// function to get cached liked songs
function getCachedLikedSongs(): LikedSongsData | null {
  try {
    const cachedData = localStorage.getItem(LIKED_SONGS_CACHE_KEY)
    if (!cachedData) return null

    return JSON.parse(cachedData) as LikedSongsData
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error reading liked songs cache:", error)
    }
    return null
  }
}

// function to get cached friend's liked songs
function getCachedFriendLikedSongs(username: string): LikedSongsData | null {
  try {
    const cachedData = localStorage.getItem(
      `${FRIEND_LIKED_SONGS_CACHE_PREFIX}${username}`,
    )
    if (!cachedData) return null

    return JSON.parse(cachedData) as LikedSongsData
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error reading friend liked songs cache:", error)
    }
    return null
  }
}

// function to set liked songs cache
export function setLikedSongsCache(data: LikedSongsData): void {
  try {
    localStorage.setItem(LIKED_SONGS_CACHE_KEY, JSON.stringify(data))
    localStorage.setItem(LIKED_SONGS_CACHE_TIMESTAMP_KEY, Date.now().toString())
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error setting liked songs cache:", error)
    }
  }
}

// function to set friend's liked songs cache
export function setFriendLikedSongsCache(
  username: string,
  data: LikedSongsData,
): void {
  try {
    localStorage.setItem(
      `${FRIEND_LIKED_SONGS_CACHE_PREFIX}${username}`,
      JSON.stringify(data),
    )
    localStorage.setItem(
      `${FRIEND_LIKED_SONGS_TIMESTAMP_PREFIX}${username}`,
      Date.now().toString(),
    )
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("error setting friend liked songs cache:", error)
    }
  }
}

// function to clear liked songs cache
export function clearLikedSongsCache(): void {
  localStorage.removeItem(LIKED_SONGS_CACHE_KEY)
  localStorage.removeItem(LIKED_SONGS_CACHE_TIMESTAMP_KEY)
}

// function to clear friend's liked songs cache
export function clearFriendLikedSongsCache(username: string): void {
  localStorage.removeItem(`${FRIEND_LIKED_SONGS_CACHE_PREFIX}${username}`)
  localStorage.removeItem(`${FRIEND_LIKED_SONGS_TIMESTAMP_PREFIX}${username}`)
}

// loader for user profile
export async function userProfileLoader({ params }: LoaderFunctionArgs) {
  try {
    const { username } = params

    if (!username) {
      return { profile: null, error: "username is required" }
    }

    // check if we have valid cached data
    const timestamp = localStorage.getItem(
      `${USER_PROFILE_CACHE_TIMESTAMP_KEY}${username}`,
    )
    if (isCacheValid(timestamp)) {
      const cachedData = getCachedUserProfile(username)
      if (cachedData) {
        return cachedData
      }
    }

    // fetch profile data and liked songs stats in parallel
    const [profileResponse, statsResponse] = await Promise.all([
      api.get(`/api/users/${username}/profile`),
      api.get(`/api/liked-songs/friends/${username}/stats`).catch((err) => {
        // silently handle 404 or 403 errors for stats
        if (
          err.response &&
          (err.response.status === 404 || err.response.status === 403)
        ) {
          return { data: null }
        }
        throw err
      }),
    ])

    const data = {
      profile: profileResponse.data,
      likedSongsStats: statsResponse.data,
    }

    // cache the data
    setUserProfileCache(username, data)

    return data
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("failed to load user profile:", error)
    }
    return {
      profile: null,
      likedSongsStats: null,
      error: "failed to load user profile",
    }
  }
}

// loader for user playlists
export async function userPlaylistsLoader({ params }: LoaderFunctionArgs) {
  try {
    const { username } = params

    if (!username) {
      return { username: "", playlists: [] }
    }

    // check if we have valid cached data
    const timestamp = localStorage.getItem(
      `${USER_PLAYLISTS_CACHE_TIMESTAMP_KEY}${username}`,
    )
    if (isCacheValid(timestamp)) {
      const cachedData = getCachedUserPlaylists(username)
      if (cachedData) {
        return cachedData
      }
    }

    const response = await api.get(`/api/users/${username}/playlists`)
    const data = {
      username,
      playlists: response.data,
    }

    // cache the data
    setUserPlaylistsCache(username, data)

    return data
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("failed to load user playlists:", error)
    }
    return {
      username: params.username || "",
      playlists: [],
    }
  }
}

// loader for public playlist detail
export async function userPlaylistDetailLoader({ params }: LoaderFunctionArgs) {
  try {
    const { id } = params

    if (!id) {
      return { playlist: null, error: "playlist id is required" }
    }

    // check if we have valid cached data
    const timestamp = localStorage.getItem(
      `${USER_PLAYLIST_CACHE_TIMESTAMP_KEY}${id}`,
    )
    if (isCacheValid(timestamp)) {
      const cachedData = getCachedUserPlaylist(id)
      if (cachedData) {
        return cachedData
      }
    }

    const response = await api.get(`/api/users/playlists/${id}`)

    // process the songs data if it's a string
    const playlist = response.data
    if (playlist && typeof playlist.songs === "string") {
      try {
        playlist.songs = JSON.parse(playlist.songs)
      } catch (error) {
        if (process.env.NODE_ENV === "development") {
          console.error("error parsing songs:", error)
        }
        playlist.songs = []
      }
    }

    const data = { playlist }

    // cache the data
    setUserPlaylistCache(id, data)

    return data
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error(`failed to load user playlist ${params.id}:`, error)
    }
    return {
      playlist: null,
      error: "failed to load playlist. it may not exist or may not be public.",
    }
  }
}

export const profileLoader = async (): Promise<ProfileData> => {
  try {
    // fetch all profile data in parallel
    const [
      profileResponse,
      friendsResponse,
      friendRequestsResponse,
      spotifyStatusResponse,
    ] = await Promise.all([
      api.get("/api/profile"),
      api.get("/api/profile/friends"),
      api.get("/api/profile/friend-requests"),
      api.get("/api/spotify/status"),
    ])

    const profile = profileResponse.data
    const friends = friendsResponse.data
    const friendRequests = friendRequestsResponse.data
    const isSpotifyConnected = spotifyStatusResponse.data.is_connected

    // fetch liked songs data if Spotify is connected
    let likedSongs
    if (isSpotifyConnected) {
      try {
        // get liked songs count and sync status
        const [likedSongsCountResponse, syncStatusResponse] = await Promise.all(
          [
            api.get("/api/liked-songs/count"),
            api.get("/api/liked-songs/sync/status"),
          ],
        )

        const likedSongsCount = likedSongsCountResponse.data
        const syncStatus = syncStatusResponse.data

        // if auto-sync is needed, trigger it in the background
        if (
          !syncStatus.is_syncing &&
          (!syncStatus.last_synced_at ||
            new Date(syncStatus.last_synced_at).getTime() <
              Date.now() - 24 * 60 * 60 * 1000)
        ) {
          // trigger auto-sync in the background without awaiting
          api.get("/api/liked-songs/auto-sync").catch((e) => {
            console.error("background auto-sync check failed:", e)
          })
        }

        likedSongs = {
          count: likedSongsCount.count || 0,
          syncStatus: syncStatus.is_syncing
            ? "syncing"
            : syncStatus.last_synced_at
              ? "synced"
              : "not_synced",
          lastSynced: syncStatus.last_synced_at,
        }
      } catch (error) {
        // if there's an error fetching liked songs data, set default values
        console.error("error fetching liked songs data:", error)
        likedSongs = {
          count: 0,
          syncStatus: "not_synced",
          lastSynced: null,
        }
      }
    }

    return {
      profile,
      friends,
      friendRequests,
      isSpotifyConnected,
      likedSongs,
    }
  } catch (error) {
    console.error("Failed to load profile data:", error)

    // return default values on error
    return {
      profile: null,
      friends: [],
      friendRequests: [],
      isSpotifyConnected: false,
    }
  }
}

// loader for user's liked songs
export async function likedSongsLoader({ request }: LoaderFunctionArgs) {
  try {
    // parse URL for pagination parameters
    const url = new URL(request.url)
    const limit = parseInt(url.searchParams.get("limit") || "20")
    const offset = parseInt(url.searchParams.get("offset") || "0")

    // check if we have valid cached data
    const timestamp = localStorage.getItem(LIKED_SONGS_CACHE_TIMESTAMP_KEY)
    if (isCacheValid(timestamp)) {
      const cachedData = getCachedLikedSongs()
      if (cachedData) {
        return cachedData
      }
    }

    // get total count first
    const countResponse = await api.get("/api/liked-songs/count")
    const totalCount = countResponse.data.count || 0

    // then fetch songs with pagination
    const songsResponse = await api.get(
      `/api/liked-songs?limit=${limit}&offset=${offset}`,
    )
    const songs = songsResponse.data

    const data: LikedSongsData = {
      songs,
      totalCount,
    }

    // cache the data
    setLikedSongsCache(data)

    return data
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("failed to load liked songs:", error)
    }
    return {
      songs: [],
      totalCount: 0,
    }
  }
}

// loader for friend's liked songs
export async function friendLikedSongsLoader({
  params,
  request,
}: LoaderFunctionArgs) {
  try {
    const { username } = params
    if (!username) {
      throw new Error("Username is required")
    }

    // parse URL for pagination and filtering parameters
    const url = new URL(request.url)
    const limit = parseInt(url.searchParams.get("limit") || "20")
    const offset = parseInt(url.searchParams.get("offset") || "0")
    const filterType = url.searchParams.get("filter_type") || "all"
    const search = url.searchParams.get("search") || undefined

    // check if we have valid cached data
    const timestamp = localStorage.getItem(
      `${FRIEND_LIKED_SONGS_TIMESTAMP_PREFIX}${username}`,
    )
    if (isCacheValid(timestamp)) {
      const cachedData = getCachedFriendLikedSongs(username)
      if (cachedData) {
        return cachedData
      }
    }

    // fetch stats first (which includes total counts)
    const statsResponse = await api.get(
      `/api/liked-songs/friends/${username}/stats`,
    )
    const stats = statsResponse.data

    // then fetch songs with pagination and filters
    let apiUrl = `/api/liked-songs/friends/${username}?limit=${limit}&offset=${offset}&filter_type=${filterType}`
    if (search) {
      apiUrl += `&search=${encodeURIComponent(search)}`
    }

    const songsResponse = await api.get(apiUrl)
    const songs = songsResponse.data

    const data: LikedSongsData = {
      songs,
      totalCount: stats.friend_likes_count,
      stats,
    }

    // cache the data
    setFriendLikedSongsCache(username, data)

    return data
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("failed to load friend liked songs:", error)
    }

    // specific error handling for common cases
    if (error && typeof error === "object" && "response" in error) {
      const err = error as { response?: { status?: number } }
      if (err.response?.status === 404) {
        return {
          songs: [],
          totalCount: 0,
          error: "This user hasn't synced their liked songs yet",
        }
      } else if (err.response?.status === 403) {
        return {
          songs: [],
          totalCount: 0,
          error: "You must be friends with this user to view their liked songs",
        }
      }
    }

    return {
      songs: [],
      totalCount: 0,
      error: "Failed to load liked songs",
    }
  }
}
