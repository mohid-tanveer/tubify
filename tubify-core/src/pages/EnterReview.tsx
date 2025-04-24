import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import api from "@/lib/axios";

export default function EnterReview() {
  const [type, setType] = useState<"song" | "album">("song");
  const [id, setId] = useState("");
  const [rating, setRating] = useState<number | null>(null);
  const [reviewText, setReviewText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async () => {
    if (!id || !rating) {
      toast.error("Please fill in all required fields.");
      return;
    }

    try {
      setIsSubmitting(true);
      const endpoint =
        type === "song" ? "/api/reviews/songs" : "/api/reviews/albums";
      await api.post(endpoint, {
        [`${type}_id`]: id,
        rating,
        review_text: reviewText,
      });
      toast.success(
        `${type === "song" ? "Song" : "Album"} review submitted successfully!`
      );
      navigate("/profile"); // Redirect to profile or another page
    } catch (error) {
      console.error("Failed to submit review:", error);
      toast.error("Failed to submit review. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="scrollable-page bg-linear-to-b from-slate-900 to-black min-h-screen">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8 pt-12">
        <h1 className="text-2xl font-bold text-white mb-6">Enter a Review</h1>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Type
            </label>
            <div className="flex gap-4">
              <Button
                variant={type === "song" ? "spotify" : "ghost"}
                onClick={() => setType("song")}
              >
                Song
              </Button>
              <Button
                variant={type === "album" ? "spotify" : "ghost"}
                onClick={() => setType("album")}
              >
                Album
              </Button>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              {type === "song" ? "Song ID" : "Album ID"}
            </label>
            <Input
              type="text"
              placeholder={`Enter ${type === "song" ? "song" : "album"} ID`}
              value={id}
              onChange={(e) => setId(e.target.value)}
            />
          </div>
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
  );
}
