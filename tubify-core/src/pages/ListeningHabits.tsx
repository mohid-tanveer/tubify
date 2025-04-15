import { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate, useLoaderData } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import api from "@/lib/axios";
import { Bar, Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  PointElement,
  ChartData,
  ChartOptions,
  TooltipItem
} from "chart.js";

// register chartjs components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  PointElement
);

interface ListeningHabitsData {
  top_artists: { name: string; play_count: number; image_url?: string }[];
  top_genres: { name: string; play_count: number }[];
  listening_trends: { date: string; play_count: number }[];
}

// time range options for the ui
const TIME_RANGE_OPTIONS = {
  artists: [
    { value: "short_term", label: "last 4 weeks" },
    { value: "medium_term", label: "last 6 months" },
    { value: "long_term", label: "all time" },
  ],
  genres: [
    { value: "short_term", label: "last 4 weeks" },
    { value: "medium_term", label: "last 6 months" },
    { value: "long_term", label: "all time" },
  ],
  trends: [
    { value: "week", label: "last week" },
    { value: "month", label: "last month" },
    { value: "all", label: "all time" },
  ],
};

// commonly used time range combinations to prefetch
const PREFETCH_COMBINATIONS = [
  { artists: "short_term", genres: "short_term", trends: "week" },
  { artists: "medium_term", genres: "medium_term", trends: "month" },
  { artists: "long_term", genres: "long_term", trends: "all" },
];

// type definitions for chart data
type BarChartProps = {
  data: ChartData<"bar">;
  options: ChartOptions<"bar">;
};

type LineChartProps = {
  data: ChartData<"line">;
  options: ChartOptions<"line">;
};

// safe chart component wrapper that properly destroys chart on unmount
function SafeBarChart({ data, options }: BarChartProps) {
  return (
    <div className="chart-container w-full h-full">
      <Bar 
        data={data} 
        options={options} 
        key={`bar-chart-${Date.now()}`}
      />
    </div>
  );
}

function SafeLineChart({ data, options }: LineChartProps) {
  return (
    <div className="chart-container w-full h-full">
      <Line 
        data={data} 
        options={options} 
        key={`line-chart-${Date.now()}`}
      />
    </div>
  );
}

// create a cache key from parameters
const createCacheKey = (type: string, timeRange: string) => `${type}_${timeRange}`;

// cache storage key
const STORAGE_CACHE_KEY = "tubify_listening_habits_client_cache";
const STORAGE_CACHE_TIMESTAMP_KEY = "tubify_listening_habits_client_cache_timestamp";
const CLIENT_CACHE_TTL = 30 * 60 * 1000; // 30 minutes in milliseconds

export default function ListeningHabits() {
  const initialData = useLoaderData() as ListeningHabitsData;
  const navigate = useNavigate();

  // Retrieve cache from localStorage or initialize with initial data
  const [cachedData, setCachedData] = useState<Record<string, ListeningHabitsData>>(() => {
    try {
      // Get cache timestamp and check validity
      const cacheTimestamp = localStorage.getItem(STORAGE_CACHE_TIMESTAMP_KEY);
      if (cacheTimestamp && (Date.now() - parseInt(cacheTimestamp, 10)) < CLIENT_CACHE_TTL) {
        const storedCache = localStorage.getItem(STORAGE_CACHE_KEY);
        if (storedCache) {
          return JSON.parse(storedCache);
        }
      }
    } catch (e) {
      console.error("Error loading cache from localStorage:", e);
    }
    
    // Default to initial data only if localStorage cache is invalid or missing
    return {
      [createCacheKey('default', 'default')]: initialData
    };
  });
  
  const [isLoading, setIsLoading] = useState(false);
  const [prefetchingInProgress, setPrefetchingInProgress] = useState(false);

  // time range states
  const [artistsTimeRange, setArtistsTimeRange] = useState("medium_term");
  const [genresTimeRange, setGenresTimeRange] = useState("medium_term");
  const [trendsTimeRange, setTrendsTimeRange] = useState("month");

  // Persist cache to localStorage when it changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_CACHE_KEY, JSON.stringify(cachedData));
      localStorage.setItem(STORAGE_CACHE_TIMESTAMP_KEY, Date.now().toString());
    } catch (e) {
      console.error("Error saving cache to localStorage:", e);
    }
  }, [cachedData]);
  
  // create current parameters object
  const currentParams = useMemo(() => ({
    artists_time_range: artistsTimeRange,
    genres_time_range: genresTimeRange,
    trends_time_range: trendsTimeRange,
  }), [artistsTimeRange, genresTimeRange, trendsTimeRange]);

  // generate a cache key for the current params
  const cacheKey = useMemo(() => 
    createCacheKey(
      `${artistsTimeRange}_${genresTimeRange}`, 
      trendsTimeRange
    ), 
    [artistsTimeRange, genresTimeRange, trendsTimeRange]
  );

  // function to fetch data and update cache
  const fetchDataForParams = useCallback(async (
    params: {
      artists_time_range: string;
      genres_time_range: string;
      trends_time_range: string;
    }, 
    key: string, 
    showLoader = true
  ) => {
    if (showLoader) setIsLoading(true);
    
    try {
      const response = await api.get("/api/listening-habits", {
        params,
      });
      
      // update the cache with new data
      setCachedData(prev => ({
        ...prev,
        [key]: response.data
      }));
      
      return response.data;
    } catch (error) {
      console.error("failed to fetch listening habits:", error);
      return null;
    } finally {
      if (showLoader) setIsLoading(false);
    }
  }, []);

  // prefetch common time ranges in the background
  const prefetchCommonTimeRanges = useCallback(async () => {
    if (prefetchingInProgress) return;
    
    setPrefetchingInProgress(true);
    
    // prefetch in sequence to avoid overwhelming the server
    for (const combo of PREFETCH_COMBINATIONS) {
      const params = {
        artists_time_range: combo.artists,
        genres_time_range: combo.genres,
        trends_time_range: combo.trends,
      };
      
      const key = createCacheKey(
        `${combo.artists}_${combo.genres}`,
        combo.trends
      );
      
      // skip if we already have this data
      if (!cachedData[key]) {
        await fetchDataForParams(params, key, false);
        // short delay between requests
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }
    
    setPrefetchingInProgress(false);
  }, [cachedData, fetchDataForParams, prefetchingInProgress]);

  // fetch and cache data when time ranges change
  useEffect(() => {
    // check if we already have this data in cache
    if (cachedData[cacheKey]) {
      return; // use cached data
    }

    fetchDataForParams(currentParams, cacheKey, true);
  }, [cacheKey, currentParams, cachedData, fetchDataForParams]);

  // start prefetching common time ranges after initial render
  useEffect(() => {
    // wait a bit after the initial render to start prefetching
    const timeoutId = setTimeout(() => {
      prefetchCommonTimeRanges();
    }, 2000);
    
    return () => clearTimeout(timeoutId);
  }, [prefetchCommonTimeRanges]);

  // get the current data from cache or fallback to initial data
  const data = cachedData[cacheKey] || initialData;

  if (!data) {
    return <div>loading...</div>;
  }

  const artistChartData = {
    labels: data.top_artists.map((artist) => artist.name),
    datasets: [
      {
        label: "play count",
        data: data.top_artists.map((artist) => artist.play_count),
        backgroundColor: "rgba(75, 192, 192, 0.6)",
      },
    ],
  };

  const genreChartData = {
    labels: data.top_genres.map((genre) => genre.name),
    datasets: [
      {
        label: "play count",
        data: data.top_genres.map((genre) => genre.play_count),
        backgroundColor: "rgba(153, 102, 255, 0.6)",
      },
    ],
  };

  const trendChartData = {
    labels: data.listening_trends.map((trend) => trend.date),
    datasets: [
      {
        label: "play count",
        data: data.listening_trends.map((trend) => trend.play_count),
        borderColor: "rgba(255, 99, 132, 1)",
        backgroundColor: "rgba(255, 99, 132, 0.2)",
        fill: true,
        tension: 0.2,
      },
    ],
  };

  // common chart options
  const barChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          color: 'rgba(255, 255, 255, 0.8)',
          font: {
            size: 12
          }
        }
      },
      tooltip: {
        callbacks: {
          title: function(tooltipItems: TooltipItem<"bar">[]) {
            return tooltipItems[0].label;
          },
          label: function(context: TooltipItem<"bar">) {
            return `plays: ${context.raw}`;
          }
        }
      }
    },
    scales: {
      x: {
        ticks: {
          color: 'rgba(255, 255, 255, 0.7)',
          autoSkip: true,
          maxRotation: 45,
          minRotation: 45
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        }
      },
      y: {
        ticks: {
          color: 'rgba(255, 255, 255, 0.7)',
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        }
      }
    }
  };

  const lineChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          color: 'rgba(255, 255, 255, 0.8)',
          font: {
            size: 12
          }
        }
      },
      tooltip: {
        callbacks: {
          title: function(tooltipItems: TooltipItem<"line">[]) {
            return tooltipItems[0].label;
          },
          label: function(context: TooltipItem<"line">) {
            return `plays: ${context.raw}`;
          }
        }
      }
    },
    scales: {
      x: {
        ticks: {
          color: 'rgba(255, 255, 255, 0.7)',
          autoSkip: true,
          maxRotation: 45,
          minRotation: 45
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        }
      },
      y: {
        ticks: {
          color: 'rgba(255, 255, 255, 0.7)',
          beginAtZero: true,
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        }
      }
    }
  };

  return (
    <div className="scrollable-page bg-linear-to-b from-slate-900 to-black">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="pt-6 pb-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/profile")}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            back to profile
          </Button>
        </div>

        <div className="mb-8">
          <h1 className="text-2xl md:text-3xl font-bold text-white">
            listening habits
          </h1>
          <p className="mt-2 text-slate-400">
            explore your listening trends and preferences
          </p>
        </div>

        {isLoading && (
          <div className="flex justify-center items-center h-24">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-white"></div>
          </div>
        )}

        <div className="grid gap-8 md:grid-cols-2 mb-8">
          <Card className="bg-slate-900/50 border-slate-700 hover:border-slate-500 transition-colors">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-white">top artists</CardTitle>
              <Select
                value={artistsTimeRange}
                onValueChange={setArtistsTimeRange}
              >
                <SelectTrigger className="w-[160px] bg-slate-800 border-slate-700 text-white">
                  <SelectValue placeholder="time range" />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-700 text-white">
                  {TIME_RANGE_OPTIONS.artists.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardHeader>
            <CardContent>
              <div className="h-[300px]">
                <SafeBarChart 
                  data={artistChartData as ChartData<"bar">} 
                  options={barChartOptions as ChartOptions<"bar">} 
                />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900/50 border-slate-700 hover:border-slate-500 transition-colors">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-white">top genres</CardTitle>
              <Select
                value={genresTimeRange}
                onValueChange={setGenresTimeRange}
              >
                <SelectTrigger className="w-[160px] bg-slate-800 border-slate-700 text-white">
                  <SelectValue placeholder="time range" />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-700 text-white">
                  {TIME_RANGE_OPTIONS.genres.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardHeader>
            <CardContent>
              <div className="h-[300px]">
                <SafeBarChart 
                  data={genreChartData as ChartData<"bar">} 
                  options={barChartOptions as ChartOptions<"bar">} 
                />
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="bg-slate-900/50 border-slate-700 mb-8 hover:border-slate-500 transition-colors">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-white">listening trends</CardTitle>
            <Select
              value={trendsTimeRange}
              onValueChange={setTrendsTimeRange}
            >
              <SelectTrigger className="w-[160px] bg-slate-800 border-slate-700 text-white">
                <SelectValue placeholder="time range" />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700 text-white">
                {TIME_RANGE_OPTIONS.trends.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardHeader>
          <CardContent>
            <div className="h-[400px]">
              <SafeLineChart 
                data={trendChartData as ChartData<"line">} 
                options={lineChartOptions as ChartOptions<"line">} 
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
