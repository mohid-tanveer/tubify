import { useEffect, useState } from "react"
import api from "@/lib/axios"

interface Track {
  track_name: string
  artist_name: string[]
  album_name: string
  played_at: string
  spotify_url: string
  album_art_url?: string
}

export default function RecentlyPlayed() {
  const [tracks, setTracks] = useState<Track[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchRecentlyPlayed = async () => {
      try {
        const response = await api.get("/api/spotify/recently-played")
        setTracks(response.data.recently_played)
      } catch (error) {
        console.error("Failed to fetch recently played tracks:", error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchRecentlyPlayed()
  }, [])

  if (isLoading) {
    return <p>Loading...</p>
  }

  if (tracks.length === 0) {
    return <p>No recently played tracks found.</p>
  }

  return (
    <div className="recently-played">
      <h1>Recently Played Tracks</h1>
      <ul>
        {tracks.map((track, index) => (
          <li key={index} className="track">
            <img src={track.album_art_url} alt={track.track_name} />
            <div>
              <a
                href={track.spotify_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {track.track_name}
              </a>
              <p>{track.artist_name.join(", ")}</p>
              <p>{track.album_name}</p>
              <p>Played at: {new Date(track.played_at).toLocaleString()}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
