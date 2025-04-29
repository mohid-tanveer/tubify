import api from "@/lib/axios"

// define interfaces for the data structure
interface Review {
  id: number
  user_id: number
  song_id: string
  rating: number
  review_text: string
  created_at: string
  username: string
  song_name: string
  album_name: string
  album_art_url: string
}

interface ReviewsData {
  reviews: Review[]
}

// reviews loader function
export async function loader(): Promise<ReviewsData> {
  try {
    // fetch all reviews from the api
    const response = await api.get("/api/reviews/all")
    return { reviews: response.data }
  } catch (error) {
    // return empty array if error occurs
    console.error("failed to load reviews:", error)
    return { reviews: [] }
  }
}
