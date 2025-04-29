import { useContext, useState, useEffect } from "react";
import { AuthContext } from "@/contexts/auth";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Star } from "lucide-react";
import api from "@/lib/axios";

interface Review {
  id: number;
  user_id: number;
  song_id: string;
  rating: number;
  review_text: string;
  created_at: string;
  username: string;
  // Add these fields to store song details
  song_name: string;
  album_name: string;
  album_art_url: string;
}

export default function ReadReviews() {
  const { user } = useContext(AuthContext);
  const navigate = useNavigate();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchReviews = async () => {
      setIsLoading(true);
      try {
        const response = await api.get("/api/reviews/all");
        setReviews(response.data);
      } catch (error: any) {
        console.error("Failed to fetch reviews:", error);
        setError("Failed to load reviews.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchReviews();
  }, []);

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

        {isLoading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="animate-pulse bg-slate-800/50 rounded-lg p-4 h-[400px]" />
            ))}
          </div>
        )}

        {error && <p className="text-red-500">{error}</p>}

        {!isLoading && !error && (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {reviews.map((review) => (
              <div
                key={review.id}
                className="bg-slate-900/70 border border-slate-800 rounded-lg overflow-hidden hover:border-slate-700 transition-colors"
              >
                {/* Album Art */}
                <div className="aspect-square w-full relative">
                  <img
                    src={review.album_art_url || '/default-album-art.jpg'}
                    alt={review.song_name}
                    className="w-full h-full object-cover"
                  />
                </div>

                {/* Content */}
                <div className="p-4 space-y-3">
                  {/* Album Name */}
                  <p className="text-sm text-slate-400 line-clamp-1">
                    {review.album_name}
                  </p>
                  
                  {/* Song Being Reviewed */}
                  <h3 className="font-medium text-white text-lg line-clamp-1">
                    {review.song_name}
                  </h3>

                  {/* Rating */}
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

                  {/* Review Text */}
                  <p className="text-sm text-slate-300 line-clamp-3">
                    {review.review_text || "No review text provided"}
                  </p>

                  {/* Username and Date */}
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
  );
}