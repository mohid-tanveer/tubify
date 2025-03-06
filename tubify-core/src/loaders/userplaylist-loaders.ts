import { LoaderFunctionArgs } from "react-router-dom"
import api from "@/lib/axios"

// define interfaces for the data structure
interface Song {
  id: number
  spotify_id: string
  name: string
  artist: string
  album?: string
  duration_ms?: number
  preview_url?: string
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

interface PublicPlaylist extends Playlist {
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

interface PublicPlaylistData {
  playlist: PublicPlaylist
}

// cache keys
const USER_PROFILE_CACHE_KEY = import.meta.env.VITE_USER_PROFILE_CACHE_KEY
const USER_PROFILE_CACHE_TIMESTAMP_KEY = import.meta.env
  .VITE_USER_PROFILE_CACHE_TIMESTAMP_KEY
const USER_PLAYLISTS_CACHE_KEY = import.meta.env.VITE_USER_PLAYLISTS_CACHE_KEY
const USER_PLAYLISTS_CACHE_TIMESTAMP_KEY = import.meta.env
  .VITE_USER_PLAYLISTS_CACHE_TIMESTAMP_KEY
const PUBLIC_PLAYLIST_CACHE_KEY = import.meta.env.VITE_PUBLIC_PLAYLIST_CACHE_KEY
const PUBLIC_PLAYLIST_CACHE_TIMESTAMP_KEY = import.meta.env
  .VITE_PUBLIC_PLAYLIST_CACHE_TIMESTAMP_KEY
const CACHE_DURATION = parseInt(import.meta.env.VITE_CACHE_DURATION)

// function to check if cache is valid
function isCacheValid(timestamp: string | null): boolean {
  if (!timestamp) return false

  const cachedTime = parseInt(timestamp, 10)
  const now = Date.now()

  // cache is valid if it's less than TTL old
  return now - cachedTime < CACHE_DURATION
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
function getCachedPublicPlaylist(
  playlistId: string,
): PublicPlaylistData | null {
  try {
    const cachedData = localStorage.getItem(
      `${PUBLIC_PLAYLIST_CACHE_KEY}${playlistId}`,
    )
    if (!cachedData) return null

    return JSON.parse(cachedData) as PublicPlaylistData
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

// function to set public playlist cache
export function setPublicPlaylistCache(
  playlistId: string,
  data: PublicPlaylistData,
): void {
  try {
    localStorage.setItem(
      `${PUBLIC_PLAYLIST_CACHE_KEY}${playlistId}`,
      JSON.stringify(data),
    )
    localStorage.setItem(
      `${PUBLIC_PLAYLIST_CACHE_TIMESTAMP_KEY}${playlistId}`,
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
export function clearPublicPlaylistCache(playlistId: string): void {
  localStorage.removeItem(`${PUBLIC_PLAYLIST_CACHE_KEY}${playlistId}`)
  localStorage.removeItem(`${PUBLIC_PLAYLIST_CACHE_TIMESTAMP_KEY}${playlistId}`)
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

    const response = await api.get(`/api/users/${username}/profile`)
    const data = { profile: response.data }

    // cache the data
    setUserProfileCache(username, data)

    return data
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error("failed to load user profile:", error)
    }
    return {
      profile: null,
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
export async function publicPlaylistDetailLoader({
  params,
}: LoaderFunctionArgs) {
  try {
    const { id } = params

    if (!id) {
      return { playlist: null, error: "playlist id is required" }
    }

    // check if we have valid cached data
    const timestamp = localStorage.getItem(
      `${PUBLIC_PLAYLIST_CACHE_TIMESTAMP_KEY}${id}`,
    )
    if (isCacheValid(timestamp)) {
      const cachedData = getCachedPublicPlaylist(id)
      if (cachedData) {
        return cachedData
      }
    }

    const response = await api.get(`/api/public/playlists/${id}`)

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
    setPublicPlaylistCache(id, data)

    return data
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.error(`failed to load public playlist ${params.id}:`, error)
    }
    return {
      playlist: null,
      error: "failed to load playlist. it may not exist or may not be public.",
    }
  }
}
