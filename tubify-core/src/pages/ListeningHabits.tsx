import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { TubifyTitle } from "@/components/ui/tubify-title";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { Bar, Line } from "react-chartjs-2";
import api from "@/lib/axios";

interface ListeningHabitsData {
  top_artists: { name: string; play_count: number }[];
  top_genres: { name: string; play_count: number }[];
  listening_trends: { date: string; play_count: number }[];
}

export default function ListeningHabits() {
  const [data, setData] = useState<ListeningHabitsData | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await api.get("/api/auth/listening-habits");
        setData(response.data);
      } catch (error) {
        console.error("Failed to fetch listening habits:", error);
      }
    };

    fetchData();
  }, []);

  if (!data) {
    return <div>Loading...</div>;
  }

  const artistChartData = {
    labels: data.top_artists.map((artist) => artist.name),
    datasets: [
      {
        label: "Play Count",
        data: data.top_artists.map((artist) => artist.play_count),
        backgroundColor: "rgba(75, 192, 192, 0.6)",
      },
    ],
  };

  const genreChartData = {
    labels: data.top_genres.map((genre) => genre.name),
    datasets: [
      {
        label: "Play Count",
        data: data.top_genres.map((genre) => genre.play_count),
        backgroundColor: "rgba(153, 102, 255, 0.6)",
      },
    ],
  };

  const trendChartData = {
    labels: data.listening_trends.map((trend) => trend.date),
    datasets: [
      {
        label: "Play Count",
        data: data.listening_trends.map((trend) => trend.play_count),
        borderColor: "rgba(255, 99, 132, 1)",
        fill: false,
      },
    ],
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
            Listening Habits
          </h1>
          <p className="mt-2 text-slate-400">
            Explore your listening trends and preferences
          </p>
        </div>

        <div className="grid gap-8 md:grid-cols-2">
          <div>
            <h2 className="text-lg font-medium text-white mb-4">Top Artists</h2>
            <Bar data={artistChartData} />
          </div>
          <div>
            <h2 className="text-lg font-medium text-white mb-4">Top Genres</h2>
            <Bar data={genreChartData} />
          </div>
        </div>

        <div className="mt-8">
          <h2 className="text-lg font-medium text-white mb-4">
            Listening Trends
          </h2>
          <Line data={trendChartData} />
        </div>
      </div>
    </div>
  );
}
