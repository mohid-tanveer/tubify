import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { TubifyTitle } from "@/components/ui/tubify-title";
import { Button } from "@/components/ui/button";
import api from "@/lib/axios";
import { toast } from "sonner";

interface HistoryItem {
  song_id: number;
  listened_at: string;
}

export default function History() {
  const navigate = useNavigate();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await api.get("/api/history");
        setHistory(response.data);
      } catch (error) {
        console.error("Failed to fetch history:", error);
        setError("Failed to load history. Please try again later.");
        toast.error("Failed to load history");
      } finally {
        setIsLoading(false);
      }
    };
    fetchHistory();
  }, []);

  const handleClearHistory = async () => {
    try {
      await api.delete("/api/history");
      setHistory([]);
      toast.success("History cleared");
    } catch (error) {
      console.error("Failed to clear history:", error);
      toast.error("Failed to clear history");
    }
  };

  return (
    <div className="overflow-hidden flex flex-col min-h-screen bg-gradient-to-b from-slate-900 to-black">
      <div className="absolute top-0 left-0">
        <TubifyTitle />
      </div>
      <div className="flex-1 flex flex-col items-center justify-center">
        <div className="w-full max-w-4xl px-4">
          <h1 className="text-white text-3xl font-bold mb-8 text-center">
            Listening History
          </h1>
          {isLoading ? (
            <p className="text-white">Loading...</p>
          ) : history.length === 0 ? (
            <p className="text-white">No history available</p>
          ) : (
            <ul className="text-white">
              {history.map((item) => (
                <li key={item.song_id}>
                  Song ID: {item.song_id}, Listened At:{" "}
                  {new Date(item.listened_at).toLocaleString()}
                </li>
              ))}
            </ul>
          )}
          <Button
            variant="destructive"
            onClick={handleClearHistory}
            className="mt-4"
          >
            Clear History
          </Button>
        </div>
      </div>
    </div>
  );
}
