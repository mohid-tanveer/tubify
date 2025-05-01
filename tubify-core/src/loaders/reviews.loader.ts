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
  username?: string
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

// loader function for a specific user's reviews
export async function userReviewsLoader({
  params,
}: {
  params: { username: string }
}): Promise<ReviewsData> {
  try {
    const username = params.username
    // fetch reviews for the specified user
    const response = await api.get(`/api/reviews/username/${username}`)
    return {
      reviews: response.data,
      username,
    }
  } catch (error) {
    console.error(`failed to load reviews for user ${params.username}:`, error)
    return {
      reviews: [],
      username: params.username,
    }
  }
}
