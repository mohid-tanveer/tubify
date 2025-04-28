import React, { useEffect, useState } from "react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "./card"
import { Radar, Scatter } from "react-chartjs-2"
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  RadialLinearScale,
  Filler,
  Tooltip,
  Legend,
  TooltipItem,
  ScatterController,
} from "chart.js"
import api from "@/lib/axios"
import { Spinner } from "./spinner"

// register chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  RadialLinearScale,
  Filler,
  Tooltip,
  Legend,
  ScatterController,
)

interface TasteProfile {
  tempo?: number
  acousticness?: number
  danceability?: number
  energy?: number
  valence?: number
  speechiness?: number
  instrumentalness?: number
  liveness?: number
}

interface Cluster {
  num_clusters: number
  song_points: {
    x: number
    y: number
    cluster: number
    song_id?: string
  }[]
  centers: {
    x: number
    y: number
  }[]
}

interface EnhancedCluster {
  id: number
  name: string
  size: number
  genres: string[]
  audio_profile: Record<string, number>
  songs: Array<{
    id: string
    name: string
    artist_names: string
    album_name: string
    album_image: string
  }>
  points: Array<{
    x: number
    y: number
    song_id: string
    song_index: number
  }>
  center: {
    x: number
    y: number
  }
}

interface EnhancedClustersData {
  num_clusters: number
  clusters: EnhancedCluster[]
  kmeans_info: {
    inertia: number
    iterations: number
  }
  song_count: number
}

interface TopGenre {
  name: string
  count: number
}

interface AnalyticsData {
  taste_profile: TasteProfile
  total_liked_songs: number
  top_genres?: TopGenre[]
  clusters?: Cluster
  enhanced_clusters?: EnhancedClustersData
  recommendation_success_rate?: number
  positive_feedback?: number
  negative_feedback?: number
}

interface RecommendationAnalyticsProps {
  preloadedData?: AnalyticsData
}

// add type definitions for cluster point data
type ClusterPoint = {
  x: number
  y: number
  cluster: number
  song_id?: string
  title?: string
  artist?: string
}

// scatter data point definition
type ScatterDataPoint = {
  x: number
  y: number
  title?: string
  artist?: string
}

// add a helper function to create cluster radar chart data
const createClusterRadarData = (audioProfile: Record<string, number>) => {
  // standard audio features we want to display in the radar chart
  const standardFeatures = [
    "danceability",
    "energy",
    "valence",
    "acousticness",
    "instrumentalness",
    "speechiness",
    "liveness",
  ]

  return {
    labels: standardFeatures.map((f) => f.charAt(0).toUpperCase() + f.slice(1)),
    datasets: [
      {
        label: "Audio Profile",
        data: standardFeatures.map((feature) => audioProfile[feature] || 0),
        backgroundColor: "rgba(99, 102, 241, 0.2)",
        borderColor: "rgb(99, 102, 241)",
        borderWidth: 2,
        pointBackgroundColor: "rgb(99, 102, 241)",
        pointBorderColor: "#fff",
        pointHoverBackgroundColor: "#fff",
        pointHoverBorderColor: "rgb(99, 102, 241)",
      },
    ],
  }
}

// define radar options for cluster profile charts
const clusterRadarOptions = {
  scales: {
    r: {
      min: 0,
      max: 1,
      ticks: {
        stepSize: 0.2,
        showLabelBackdrop: false,
        color: "#9ca3af",
        font: {
          size: 10,
        },
      },
      pointLabels: {
        color: "#9ca3af",
        font: {
          size: 12,
        },
      },
      grid: {
        color: "#374151",
      },
      angleLines: {
        color: "#374151",
      },
    },
  },
  plugins: {
    tooltip: {
      backgroundColor: "#1e293b",
      titleColor: "#e5e7eb",
      bodyColor: "#e5e7eb",
      borderColor: "#475569",
      borderWidth: 1,
      padding: 10,
      displayColors: false,
      callbacks: {
        label: function (tooltipItem: TooltipItem<"radar">) {
          return `${tooltipItem.label}: ${Math.round((tooltipItem.raw as number) * 100)}%`
        },
      },
    },
    legend: {
      display: false,
    },
  },
  maintainAspectRatio: false,
}

const RecommendationAnalytics: React.FC<RecommendationAnalyticsProps> = ({
  preloadedData,
}) => {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(
    preloadedData || null,
  )
  const [loading, setLoading] = useState<boolean>(!preloadedData)
  const [error, setError] = useState<string | null>(null)

  // fetch analytics if not provided
  useEffect(() => {
    if (!preloadedData) {
      const fetchAnalytics = async () => {
        try {
          setLoading(true)
          const response = await api.get("/api/recommendations/analytics")
          setAnalytics(response.data)
        } catch (err) {
          console.error("Failed to fetch recommendation analytics:", err)
          setError("Failed to load analytics. Please try again later.")
        } finally {
          setLoading(false)
        }
      }

      fetchAnalytics()
    }
  }, [preloadedData])

  // prepare radar chart data
  const radarData = {
    labels: [
      "Danceability",
      "Energy",
      "Valence",
      "Acousticness",
      "Instrumentalness",
      "Speechiness",
      "Liveness",
    ],
    datasets: analytics?.taste_profile
      ? [
          {
            label: "Your Taste Profile",
            data: [
              analytics.taste_profile.danceability || 0,
              analytics.taste_profile.energy || 0,
              analytics.taste_profile.valence || 0,
              analytics.taste_profile.acousticness || 0,
              analytics.taste_profile.instrumentalness || 0,
              analytics.taste_profile.speechiness || 0,
              analytics.taste_profile.liveness || 0,
            ],
            backgroundColor: "rgba(54, 162, 235, 0.2)",
            borderColor: "rgb(54, 162, 235)",
            borderWidth: 2,
            pointBackgroundColor: "rgb(54, 162, 235)",
            pointBorderColor: "#fff",
            pointHoverBackgroundColor: "#fff",
            pointHoverBorderColor: "rgb(54, 162, 235)",
          },
        ]
      : [],
  }

  // radar chart options
  const radarOptions = {
    scales: {
      r: {
        min: 0,
        max: 1,
        ticks: {
          stepSize: 0.2,
          showLabelBackdrop: false,
          color: "rgba(255, 255, 255, 0.7)",
        },
        pointLabels: {
          color: "rgba(255, 255, 255, 0.7)",
          font: {
            size: 10,
          },
        },
        grid: {
          color: "rgba(255, 255, 255, 0.1)",
        },
        angleLines: {
          color: "rgba(255, 255, 255, 0.1)",
        },
      },
    },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: "rgba(0, 0, 0, 0.7)",
        titleFont: {
          size: 14,
        },
        bodyFont: {
          size: 12,
        },
      },
    },
    maintainAspectRatio: false,
  }

  // scatter plot for clusters if available
  const scatterData = analytics?.clusters
    ? {
        datasets: [
          // plot for songs grouped by cluster
          ...Array.from({ length: analytics.clusters.num_clusters }, (_, i) => {
            const colors = [
              "rgba(255, 99, 132, 0.7)",
              "rgba(54, 162, 235, 0.7)",
              "rgba(255, 206, 86, 0.7)",
              "rgba(75, 192, 192, 0.7)",
              "rgba(153, 102, 255, 0.7)",
              "rgba(255, 160, 64, 0.7)",
              "rgba(255, 120, 120, 0.7)",
              "rgba(130, 200, 255, 0.7)",
            ]

            // use descriptive name from enhanced_clusters if available
            const clusterLabel =
              analytics.enhanced_clusters?.clusters[i]?.name ||
              `Cluster ${i + 1}`

            return {
              label: clusterLabel,
              data: analytics.clusters?.song_points
                .filter((point: ClusterPoint) => point.cluster === i)
                .map((point: ClusterPoint) => ({
                  x: point.x,
                  y: point.y,
                  title: point.title || "Unknown song",
                  artist: point.artist || "Unknown artist",
                })),
              backgroundColor: colors[i % colors.length],
              pointRadius: 5,
            }
          }),
        ],
      }
    : null

  // scatter plot options with customized tooltips
  const scatterOptions = {
    scales: {
      x: {
        grid: {
          color: "rgba(255, 255, 255, 0.1)",
        },
        ticks: {
          color: "rgba(255, 255, 255, 0.7)",
        },
      },
      y: {
        grid: {
          color: "rgba(255, 255, 255, 0.1)",
        },
        ticks: {
          color: "rgba(255, 255, 255, 0.7)",
        },
      },
    },
    plugins: {
      legend: {
        labels: {
          color: "rgba(255, 255, 255, 0.7)",
        },
      },
      tooltip: {
        backgroundColor: "rgba(0, 0, 0, 0.8)",
        titleFont: {
          size: 14,
        },
        bodyFont: {
          size: 12,
        },
        callbacks: {
          label: function (tooltipItem: TooltipItem<"scatter">) {
            const point = tooltipItem.raw as ScatterDataPoint
            if (point && point.title && point.artist) {
              return [`${point.title}`, `by ${point.artist}`]
            }
            return ""
          },
        },
      },
    },
    maintainAspectRatio: false,
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center text-red-500 p-4 border border-red-700/50 bg-red-900/20 rounded-lg">
        {error}
      </div>
    )
  }

  if (!analytics) {
    return (
      <div className="text-center text-slate-400 py-8">
        no analytics data available
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* taste profile radar chart */}
        <Card className="bg-slate-900/50 border-slate-800">
          <CardHeader>
            <CardTitle className="text-white">
              your music taste profile
            </CardTitle>
            <CardDescription>
              based on the audio features of {analytics.total_liked_songs} liked
              songs
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              {analytics.taste_profile &&
              Object.keys(analytics.taste_profile).length > 0 ? (
                <Radar data={radarData} options={radarOptions} />
              ) : (
                <div className="flex items-center justify-center h-full text-slate-400">
                  not enough data for taste profile
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* clusters visualization */}
        <Card className="bg-slate-900/50 border-slate-800">
          <CardHeader>
            <CardTitle className="text-white">
              music preference clusters
            </CardTitle>
            <CardDescription>
              visualization of your different music taste groups
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="space-y-3 w-full">
                    <div className="h-4 bg-slate-800 rounded animate-pulse w-3/4 mx-auto"></div>
                    <div className="h-28 bg-slate-800 rounded animate-pulse w-full"></div>
                    <div className="flex space-x-2">
                      <div className="h-4 bg-slate-800 rounded animate-pulse w-1/4"></div>
                      <div className="h-4 bg-slate-800 rounded animate-pulse w-1/4"></div>
                      <div className="h-4 bg-slate-800 rounded animate-pulse w-1/4"></div>
                    </div>
                  </div>
                </div>
              ) : analytics?.clusters &&
                analytics.clusters.song_points.length > 0 ? (
                <Scatter data={scatterData!} options={scatterOptions} />
              ) : (
                <div className="flex items-center justify-center h-full text-slate-400">
                  not enough data for clustering
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* cluster details */}
      {analytics?.enhanced_clusters &&
        analytics.enhanced_clusters.clusters &&
        analytics.enhanced_clusters.clusters.length > 0 && (
          <Card className="bg-slate-900/50 border-slate-800">
            <CardHeader>
              <CardTitle className="text-white">your music clusters</CardTitle>
              <CardDescription>
                groups of music with similar characteristics that you enjoy
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {analytics.enhanced_clusters.clusters.map((cluster) => (
                  <div
                    key={cluster.id}
                    className="bg-slate-800/50 border border-slate-700 rounded-lg p-4"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-lg font-medium text-white">
                        {cluster.name}{" "}
                        <span className="text-sm text-slate-400">
                          ({cluster.size} songs)
                        </span>
                      </h3>
                      <div className="flex space-x-2">
                        {cluster.genres &&
                          cluster.genres.map((genre) => (
                            <span
                              key={genre}
                              className="px-2 py-1 bg-slate-700 text-xs rounded-full text-slate-300"
                            >
                              {genre}
                            </span>
                          ))}
                      </div>
                    </div>

                    {/* audio profile */}
                    {cluster.audio_profile &&
                      Object.keys(cluster.audio_profile).length > 0 && (
                        <div className="mb-6 grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div className="flex flex-col p-3 bg-slate-900/30 rounded-lg">
                            <h4 className="text-sm font-medium text-slate-300 mb-2 text-center">
                              audio profile
                            </h4>
                            <div className="h-[180px] flex-grow">
                              <Radar
                                data={createClusterRadarData(
                                  cluster.audio_profile,
                                )}
                                options={clusterRadarOptions}
                              />
                            </div>
                          </div>
                          <div className="col-span-2">
                            <h4 className="text-sm font-medium text-slate-300 mb-2">
                              key characteristics:
                            </h4>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                              {Object.entries(cluster.audio_profile)
                                .sort(([nameA], [nameB]) =>
                                  nameA.localeCompare(nameB),
                                ) // sort by name ascending
                                .slice(0, 8) // take top 8 characteristics
                                .map(([name, value]) => (
                                  <div
                                    key={name}
                                    className="flex flex-col items-center p-2 bg-slate-900/30 rounded text-center"
                                  >
                                    <div className="text-xs text-slate-300 font-semibold mb-1">
                                      {name}
                                    </div>
                                    <div className="text-lg font-bold text-white">
                                      {Math.round(value * 100)}%
                                    </div>
                                    <div className="w-full h-1 bg-slate-700 mt-1 overflow-hidden rounded-full">
                                      <div
                                        className={`h-full ${
                                          name === "energy"
                                            ? "bg-red-500"
                                            : name === "danceability"
                                              ? "bg-purple-500"
                                              : name === "valence"
                                                ? "bg-green-500"
                                                : name === "acousticness"
                                                  ? "bg-blue-500"
                                                  : name === "instrumentalness"
                                                    ? "bg-yellow-500"
                                                    : name === "speechiness"
                                                      ? "bg-pink-500"
                                                      : name === "liveness"
                                                        ? "bg-cyan-500"
                                                        : "bg-indigo-500"
                                        } rounded-full`}
                                        style={{
                                          width: `${Math.round(value * 100)}%`,
                                        }}
                                      />
                                    </div>
                                  </div>
                                ))}
                            </div>
                          </div>
                        </div>
                      )}

                    {/* representative songs */}
                    {cluster.songs && cluster.songs.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium text-slate-300 mb-2">
                          representative songs:
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                          {cluster.songs.slice(0, 3).map((song) => (
                            <div
                              key={song.id}
                              className="flex items-center bg-slate-800 rounded p-2"
                            >
                              {song.album_image && (
                                <img
                                  src={song.album_image}
                                  alt={song.album_name}
                                  className="w-10 h-10 rounded mr-3"
                                />
                              )}
                              <div className="overflow-hidden">
                                <div className="text-sm font-medium text-white truncate">
                                  {song.name}
                                </div>
                                <div className="text-xs text-slate-400 truncate">
                                  {song.artist_names}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

      {/* top genres */}
      {analytics.top_genres && analytics.top_genres.length > 0 && (
        <Card className="bg-slate-900/50 border-slate-800">
          <CardHeader>
            <CardTitle className="text-white">your top genres</CardTitle>
            <CardDescription>
              most frequent genres in your liked songs
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
              {analytics.top_genres.map((genre) => (
                <div
                  key={genre.name}
                  className="bg-slate-800/50 border border-slate-700 rounded-md p-3 text-center"
                >
                  <div className="text-lg font-medium text-white">
                    {genre.name}
                  </div>
                  <div className="text-sm text-slate-400">
                    {genre.count} songs
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* recommendation statistics */}
      {analytics.recommendation_success_rate !== undefined && (
        <Card className="bg-slate-900/50 border-slate-800">
          <CardHeader>
            <CardTitle className="text-white">
              recommendation performance
            </CardTitle>
            <CardDescription>
              how well our recommendations match your taste
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center">
              <div className="text-3xl font-bold text-white mb-2">
                {(analytics.recommendation_success_rate * 100).toFixed(0)}%
              </div>
              <div className="text-sm text-slate-400">
                success rate based on your feedback
              </div>
              <div className="w-full max-w-md mt-4">
                <div className="h-4 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full"
                    style={{
                      width: `${analytics.recommendation_success_rate * 100}%`,
                    }}
                  />
                </div>
                <div className="flex justify-between mt-1 text-xs text-slate-400">
                  <span>0%</span>
                  <span>50%</span>
                  <span>100%</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default RecommendationAnalytics
