import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"
import { Search, Music } from "lucide-react" 
import api, { AxiosError } from "@/lib/axios"

interface SongResult {
  id: string
  name: string
  artist: string
  album: string
  album_art_url?: string
}

export default function EnterReview() {
  const [id, setId] = useState("")
  const [rating, setRating] = useState<number | null>(null)
  const [reviewText, setReviewText] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<SongResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const searchSongs = async () => {
      if (!searchQuery || searchQuery.length < 2) {
        setSearchResults([])
        return
      }

      try {
        setIsSearching(true)
        const response = await api.get(`/api/songs/search?query=${encodeURIComponent(searchQuery)}`)
        setSearchResults(response.data)
      } catch (error) {
        console.error("Failed to search songs:", error)
        toast.error("Failed to search songs")
      } finally {
        setIsSearching(false)
      }
    }

    const timer = setTimeout(() => {
      searchSongs()
    }, 500)

    return () => clearTimeout(timer)
  }, [searchQuery])

  const handleSelectSong = (song: SongResult) => {
    setId(song.id)
    setSearchQuery(song.name)
    setSearchResults([])
  }

  const handleSubmit = async () => {
    if (!id) {
        toast.error("Please select a song")
        return
    }
    if (!rating || rating < 1 || rating > 5) {
        toast.error("Please enter a valid rating between 1 and 5")
        return
    }

    try {
        setIsSubmitting(true)
        //const url = `/api/reviews/songs?song_id=${id}&rating=${rating}`
        //await api.post(url, {
        //    review_text: reviewText || null
        //})
        //toast.success("Review submitted successfully!")
        //navigate("/profile")

        // 1. check if the song exists in the database
        const songExistsResponse = await api.get(`/api/songs/search?query=${encodeURIComponent(searchQuery)}`)
        const songExists = songExistsResponse.data.some((song: SongResult) => song.id === id)

        if (!songExists) {
            toast.error("Song not found in the database. Please add the song first.")
            return
        }

        // 2. if the song exists, submit the review
        console.log("reviewText:", reviewText)
        const url = `/api/reviews/songs?song_id=${id}&rating=${rating}&review_text=${encodeURIComponent(reviewText || '')}`
        await api.post(url, {
            review_text: reviewText || null
        })

        toast.success("Review submitted successfully!")
        navigate("/profile")

    } catch (error) {
        console.error("Failed to submit review:", error)
        if (error instanceof Error && (error as AxiosError).response?.data) {
            console.log("Validation Errors:", (error as AxiosError).response?.data)
            toast.error(JSON.stringify((error as AxiosError).response?.data)) 
        } else {
            toast.error("Failed to submit review")
        }
    } finally {
        setIsSubmitting(false)
    }
}

  return (
    <div className="scrollable-page bg-linear-to-b from-slate-900 to-black min-h-screen">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8 pt-12">
        <h1 className="text-2xl font-bold text-white mb-6">Enter a Review</h1>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Type
            </label>
            
          </div>

          {/* search input */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Search for a Song
            </label>
            <div className="relative">
              {isSearching ? (
                <div className="absolute left-3 top-1/2 -translate-y-1/2">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-400 border-t-transparent" />
                </div>
              ) : (
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              )}
              <Input
                type="text"
                placeholder={`Search for a song...`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* search Results */}
            {searchResults.length > 0 && (
              <div className="mt-2 max-h-[300px] overflow-y-auto rounded-lg border border-slate-700 bg-slate-800">
                {searchResults.map((song) => (
                  <div
                    key={song.id}
                    className="flex items-center gap-3 p-3 hover:bg-slate-700 cursor-pointer transition-colors"
                    onClick={() => handleSelectSong(song)}
                  >
                    {song.album_art_url ? (
                      <img
                        src={song.album_art_url}
                        alt={song.name}
                        className="h-12 w-12 rounded object-cover"
                      />
                    ) : (
                      <div className="flex h-12 w-12 items-center justify-center rounded bg-slate-700">
                        <Music className="h-6 w-6 text-slate-400" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-white truncate">
                        {song.name}
                      </div>
                      <div className="text-xs text-slate-400 truncate">
                        {song.artist} • {song.album}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* rest of your form */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Rating
            </label>
            <Input
              type="number"
              placeholder="Enter a rating (1-5)"
              value={rating || ""}
              onChange={(e) => setRating(Number(e.target.value))}
              min={1}
              max={5}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Review (Optional)
            </label>
            <Textarea
              placeholder="Write your review here..."
              value={reviewText}
              onChange={(e) => setReviewText(e.target.value)}
            />
          </div>
          <div>
            <Button
              onClick={handleSubmit}
              disabled={isSubmitting}
              variant="spotify"
              className="w-full"
            >
              {isSubmitting ? "Submitting..." : "Submit Review"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}