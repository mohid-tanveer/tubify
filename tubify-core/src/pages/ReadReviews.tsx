import { useContext } from "react"
import { AuthContext } from "@/contexts/auth"
import { useNavigate, useLoaderData } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { ArrowLeft, Star } from "lucide-react"

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

interface LoaderData {
  reviews: Review[]
}

export default function ReadReviews() {
  const { user } = useContext(AuthContext)
  const navigate = useNavigate()
  const { reviews } = useLoaderData() as LoaderData

  return (
    <div className="scrollable-page bg-gradient-to-b from-slate-900 to-black min-h-screen">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-6 pb-4">
        <Button variant="ghost" size="sm" onClick={() => navigate("/")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Home
        </Button>

        <h1 className="text-2xl font-bold text-white mt-4 mb-6">
          {user?.username}'s and Friend's Reviews
        </h1>

        {!reviews.length && (
          <p className="text-slate-400 text-center py-8">No reviews found. Be the first to write one!</p>
        )}

        {reviews.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {reviews.map((review) => (
              <div
                key={review.id}
                className="bg-slate-900/70 border border-slate-800 rounded-lg overflow-hidden hover:border-slate-700 transition-colors"
              >
                {/* album art */}
                <div className="aspect-square w-full relative">
                  <img
                    src={review.album_art_url || '/default-album-art.jpg'}
                    alt={review.song_name}
                    className="w-full h-full object-cover"
                  />
                </div>

                {/* content */}
                <div className="p-4 space-y-3">
                  {/* album name */}
                  <p className="text-sm text-slate-400 line-clamp-1">
                    {review.album_name}
                  </p>
                  
                  {/* song being reviewed */}
                  <h3 className="font-medium text-white text-lg line-clamp-1">
                    {review.song_name}
                  </h3>

                  {/* rating */}
                  <div className="flex items-center gap-1">
                    {[...Array(5)].map((_, i) => (
                      <Star
                        key={i}
                        className={`h-4 w-4 ${
                          i < review.rating ? 'fill-yellow-400 text-yellow-400' : 'text-slate-600'
                        }`}
                      />
                    ))}
                  </div>

                  {/* review text */}
                  <p className="text-sm text-slate-300 line-clamp-3">
                    {review.review_text || "No review text provided"}
                  </p>

                  {/* username and date */}
                  <div className="pt-2 flex items-center justify-between text-xs text-slate-400">
                    <span>by {review.username}</span>
                    <span>{new Date(review.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}