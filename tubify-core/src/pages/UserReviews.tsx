import { useLoaderData, useNavigate } from "react-router-dom"
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
  username: string
}

export default function UserReviews() {
  const navigate = useNavigate()
  const { reviews, username } = useLoaderData() as LoaderData

  return (
    <div className="scrollable-page bg-linear-to-b from-slate-900 to-black">
      <div className="flex items-center justify-center min-h-screen">
        <div className="mx-auto max-w-7xl w-full px-4 sm:px-6 lg:px-8 pt-6 pb-8">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => navigate(-1)}
            className="mb-4"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>

          <h1 className="text-2xl font-bold text-white mb-6">
            {username}'s Reviews
          </h1>

          {!reviews.length && (
            <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-8 text-center">
              <p className="text-slate-400">No reviews found for this user.</p>
            </div>
          )}

          {reviews.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {reviews.map((review) => (
                <div
                  key={review.id}
                  className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden hover:border-slate-600 transition-colors"
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

                    {/* date */}
                    <div className="pt-2 text-xs text-slate-400">
                      {new Date(review.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
} 