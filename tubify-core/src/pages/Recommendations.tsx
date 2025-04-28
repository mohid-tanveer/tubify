import React, { useState } from "react"
import { useLoaderData, useNavigate } from "react-router-dom"
import RecommendationsList from "../components/ui/recommendations-list"
import { TubifyTitle } from "../components/ui/tubify-title"
import { Button } from "../components/ui/button"
import { ArrowLeft, InfoIcon, ThumbsUp, ThumbsDown } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Skeleton } from "@/components/ui/skeleton"

type RecommendationSource = "friends" | "similar_music"

interface RecommendedSong {
  id: string
  name: string
  spotify_uri: string
  spotify_url: string
  popularity: number
  album_name: string
  album_image_url: string
  artist_names: string
  recommendation_score?: number
  recommendation_sources?: RecommendationSource[]
  similarity_score?: number
  lyrics_similarity?: number
  friend_count?: number
  friends_who_like?: Array<{
    friend_id: number
    friend_name: string
    friend_image: string
  }>
  duration_ms?: number
  user_feedback?: boolean
  recommendation_id?: number
}

interface RecommendationsData {
  hybrid: RecommendedSong[]
  friends: RecommendedSong[]
  similar: RecommendedSong[]
  lyrical: RecommendedSong[]
  error?: string
}

interface AnalyticsData {
  feedback_stats?: {
    total: number
    positive: number
    negative: number
  }
}

interface LoaderData {
  recommendations: RecommendationsData
  analytics?: AnalyticsData
}

const RecommendationsPage: React.FC = () => {
  const data = useLoaderData() as LoaderData
  const { recommendations, analytics } = data
  const { hybrid, friends, similar, lyrical, error } = recommendations
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState("for-you")
  const [isLoading, setIsLoading] = useState(false)

  // calculate feedback percentage if available
  const feedbackPercentage = analytics?.feedback_stats?.total
    ? (analytics.feedback_stats.positive / analytics.feedback_stats.total) * 100
    : 0

  // skeleton loader components
  const RecommendationSkeleton = () => (
    <div className="space-y-4">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="bg-slate-800/30 p-3 rounded-md">
          <div className="flex items-center space-x-3">
            <Skeleton className="h-10 w-10 rounded-md" />
            <div className="space-y-2 flex-1">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/2" />
            </div>
            <Skeleton className="h-8 w-14 rounded-md" />
          </div>
        </div>
      ))}
    </div>
  )

  return (
    <div className="scrollable-page bg-gradient-to-b from-slate-900 to-black min-h-screen">
      <div className="absolute top-4 left-4 z-10">
        <TubifyTitle />
      </div>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-24">
        <div className="pt-6 pb-4 flex justify-between items-center">
          <Button variant="ghost" size="sm" onClick={() => navigate("/")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            back
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/recommendation-analysis")}
          >
            view recommendation analysis
          </Button>
        </div>

        <div className="mb-8">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-white">
                music recommendations
              </h1>
              <p className="mt-2 text-slate-400">
                personalized music recommendations based on your taste
              </p>
            </div>

            {analytics?.feedback_stats &&
              analytics.feedback_stats.total > 0 && (
                <div className="bg-slate-800/50 p-4 rounded-lg border border-slate-700">
                  <h3 className="text-sm font-medium text-slate-300 mb-2">
                    your feedback
                  </h3>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center text-green-400">
                      <ThumbsUp className="h-4 w-4 mr-1" />
                      <span>{analytics.feedback_stats.positive}</span>
                    </div>
                    <div className="flex items-center text-red-400">
                      <ThumbsDown className="h-4 w-4 mr-1" />
                      <span>{analytics.feedback_stats.negative}</span>
                    </div>
                  </div>
                  {analytics.feedback_stats.total >= 5 && (
                    <div className="mt-2">
                      <div className="h-2 w-full bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-2 bg-green-500 rounded-full"
                          style={{ width: `${feedbackPercentage}%` }}
                        />
                      </div>
                      <p className="text-xs text-slate-400 mt-1">
                        {feedbackPercentage.toFixed(0)}% positive
                      </p>
                    </div>
                  )}
                </div>
              )}
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-700 rounded-lg text-white">
            {error}
          </div>
        )}

        <Tabs
          defaultValue="for-you"
          value={activeTab}
          onValueChange={(value) => {
            setIsLoading(false)
            setActiveTab(value)
          }}
          className="w-full"
        >
          <TabsList className="mb-6 bg-slate-800 p-1 border border-slate-700 w-full max-w-lg mx-auto">
            <TabsTrigger
              value="for-you"
              className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white font-medium"
            >
              for you
            </TabsTrigger>
            <TabsTrigger
              value="friends"
              className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white font-medium"
            >
              from friends
            </TabsTrigger>
            <TabsTrigger
              value="similar"
              className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white font-medium"
            >
              similar
            </TabsTrigger>
            <TabsTrigger
              value="lyrical"
              className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white font-medium"
            >
              lyrics
            </TabsTrigger>
          </TabsList>

          <TabsContent value="for-you">
            <div className="bg-slate-900/70 border border-slate-800 p-6 rounded-lg hover:border-slate-700 transition-colors shadow-lg">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-white">for you</h2>
                <div className="text-sm text-slate-400 flex items-center">
                  <InfoIcon className="h-4 w-4 mr-1 text-blue-400" />
                  <span>leave feedback to improve recommendations</span>
                </div>
              </div>
              <p className="text-slate-400 mb-4">
                curated recommendations based on your listening habits and
                friends
              </p>
              {isLoading ? (
                <RecommendationSkeleton />
              ) : (
                <RecommendationsList
                  limit={20}
                  preloadedData={hybrid}
                  allRecommendations={{
                    friends: friends,
                    similar: similar,
                    lyrical: lyrical,
                  }}
                  showFeedbackButtons={true}
                  showTitle={false}
                />
              )}
            </div>
          </TabsContent>

          <TabsContent value="friends">
            <div className="bg-slate-900/70 border border-slate-800 p-6 rounded-lg hover:border-slate-700 transition-colors shadow-lg">
              <h2 className="text-xl font-bold text-white mb-4">
                from your friends
              </h2>
              <p className="text-slate-400 mb-4">
                music that your friends have been enjoying recently
              </p>
              {isLoading ? (
                <RecommendationSkeleton />
              ) : (
                <RecommendationsList
                  limit={20}
                  showTitle={false}
                  friendsOnly={true}
                  preloadedData={friends}
                  hideScores={true}
                  showFeedbackButtons={true}
                />
              )}
            </div>
          </TabsContent>

          <TabsContent value="similar">
            <div className="bg-slate-900/70 border border-slate-800 p-6 rounded-lg hover:border-slate-700 transition-colors shadow-lg">
              <h2 className="text-xl font-bold text-white mb-4">
                similar to what you like
              </h2>
              <p className="text-slate-400 mb-4">
                songs with similar audio characteristics to your liked music
              </p>
              {isLoading ? (
                <RecommendationSkeleton />
              ) : (
                <RecommendationsList
                  limit={20}
                  showTitle={false}
                  similarOnly={true}
                  preloadedData={similar}
                  hideScores={true}
                  showFeedbackButtons={true}
                />
              )}
            </div>
          </TabsContent>

          <TabsContent value="lyrical">
            <div className="bg-slate-900/70 border border-slate-800 p-6 rounded-lg hover:border-slate-700 transition-colors shadow-lg">
              <h2 className="text-xl font-bold text-white mb-4">
                similar lyrics and themes
              </h2>
              <p className="text-slate-400 mb-4">
                songs with similar lyrical content and themes to what you enjoy
              </p>
              {isLoading ? (
                <RecommendationSkeleton />
              ) : (
                <RecommendationsList
                  limit={20}
                  showTitle={false}
                  lyricalOnly={true}
                  preloadedData={lyrical}
                  hideScores={true}
                  showFeedbackButtons={true}
                />
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

export default RecommendationsPage
