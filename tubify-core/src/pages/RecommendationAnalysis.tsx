import React from "react"
import { useLoaderData, useNavigate } from "react-router-dom"
import { TubifyTitle } from "../components/ui/tubify-title"
import { Button } from "../components/ui/button"
import { ArrowLeft, ThumbsUp, ThumbsDown } from "lucide-react"
import RecommendationAnalytics from "@/components/ui/recommendation-analytics"

interface TasteProfile {
  tempo?: number
  acousticness?: number
  danceability?: number
  energy?: number
  valence?: number
  speechiness?: number
  instrumentalness?: number
  liveness?: number
  mode?: number
  key?: number
}

interface Cluster {
  num_clusters: number
  song_points: Array<{
    x: number
    y: number
    cluster: number
  }>
  centers: Array<{
    x: number
    y: number
  }>
}

interface AnalyticsData {
  taste_profile: TasteProfile
  total_liked_songs: number
  top_genres?: Array<{ name: string; count: number }>
  clusters?: Cluster
  recommendation_success_rate?: number
  positive_feedback?: number
  negative_feedback?: number
  feedback_stats?: {
    total: number
    positive: number
    negative: number
  }
}

interface FeedbackItem {
  song_id: string
  song_name: string
  artist_names: string
  album_name: string
  album_image_url: string
  spotify_uri: string
  liked: boolean
  feedback_at: string
}

interface LoaderData {
  feedback: FeedbackItem[]
  analytics: AnalyticsData | null
  error?: string
}

const RecommendationAnalysis: React.FC = () => {
  const loaderData = useLoaderData() as LoaderData
  const navigate = useNavigate()

  const { feedback, analytics, error: loaderError } = loaderData

  // group feedback by date
  const groupedFeedback = feedback.reduce(
    (groups, item) => {
      const date = new Date(item.feedback_at).toLocaleDateString()
      if (!groups[date]) {
        groups[date] = []
      }
      groups[date].push(item)
      return groups
    },
    {} as Record<string, FeedbackItem[]>,
  )

  return (
    <div className="scrollable-page bg-gradient-to-b from-slate-900 to-black min-h-screen">
      <div className="absolute top-4 left-4 z-10">
        <TubifyTitle />
      </div>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-24">
        <div className="pt-6 pb-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/recommendations")}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            back to recommendations
          </Button>
        </div>

        <div className="mb-8">
          <h1 className="text-2xl md:text-3xl font-bold text-white">
            your recommendation analysis
          </h1>
          <p className="mt-2 text-slate-400">
            review and manage your recommendation feedback
          </p>
        </div>

        {loaderError ? (
          <div className="text-center text-red-500 p-4 border border-red-700/50 bg-red-900/20 rounded-lg">
            {loaderError}
          </div>
        ) : (
          <div className="space-y-8">
            {/* recommendation analytics */}
            <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-lg">
              <h2 className="text-xl font-bold text-white mb-4">
                your music taste analytics
              </h2>
              <RecommendationAnalytics preloadedData={analytics || undefined} />
            </div>

            {/* feedback history */}
            <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-lg">
              <h2 className="text-xl font-bold text-white mb-4">
                feedback history
              </h2>

              {feedback.length === 0 ? (
                <div className="text-center text-slate-400 py-8">
                  <p className="mb-2">you haven't provided any feedback yet</p>
                  <p className="text-sm">
                    rate recommendations to help us improve your suggestions
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-4"
                    onClick={() => navigate("/recommendations")}
                  >
                    go to recommendations
                  </Button>
                </div>
              ) : (
                <div className="space-y-6">
                  {Object.entries(groupedFeedback).map(([date, items]) => (
                    <div key={date}>
                      <h3 className="text-md font-medium text-slate-300 mb-3">
                        {date}
                      </h3>
                      <div className="space-y-2">
                        {items.map((item) => (
                          <div
                            key={`${item.song_id}-${item.feedback_at}`}
                            className="bg-slate-800/30 hover:bg-slate-800/50 rounded-md p-3 transition-colors flex items-center"
                          >
                            <div className="flex-shrink-0 mr-3">
                              <img
                                src={item.album_image_url}
                                alt={item.album_name}
                                className="h-12 w-12 rounded"
                              />
                            </div>

                            <div className="flex-grow min-w-0">
                              <div className="font-medium text-white truncate">
                                {item.song_name}
                              </div>
                              <div className="text-sm text-slate-400 truncate">
                                {item.artist_names}
                              </div>
                            </div>

                            <div className="flex-shrink-0 ml-4">
                              {item.liked ? (
                                <div className="flex items-center text-green-400">
                                  <ThumbsUp className="h-5 w-5 mr-1" />
                                  <span>liked</span>
                                </div>
                              ) : (
                                <div className="flex items-center text-red-400">
                                  <ThumbsDown className="h-5 w-5 mr-1" />
                                  <span>disliked</span>
                                </div>
                              )}
                            </div>

                            <div className="flex-shrink-0 ml-4">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() =>
                                  window.open(item.spotify_uri, "_blank")
                                }
                              >
                                play
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default RecommendationAnalysis
