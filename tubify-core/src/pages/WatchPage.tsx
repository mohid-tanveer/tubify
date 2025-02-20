import { Link } from "react-router-dom";
import { TubifyTitle } from "@/components/ui/tubify-title";
import YouTube, { YouTubeProps } from "react-youtube";

export default function WatchPage() {
  const videoId = "dQw4w9WgXcQ"; // Replace with the ID of the YouTube video you want to play

  const opts = {
    height: '390',
    width: '640',
    playerVars: {
      // https://developers.google.com/youtube/player_parameters
      autoplay: 1,
    },
  };

  const onReady = (event: any) => {
    // access to player in all event handlers via event.target
    event.target.pauseVideo();
  };

  return (
    <div className="overflow-hidden flex flex-col min-h-screen">
      <div className="absolute top-0 left-0">
        <TubifyTitle />
      </div>
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <p className="text-white">Welcome to the Watch Page!</p>
          <YouTube videoId={videoId} opts={opts} onReady={onReady} />
          <Link to="/" className="text-white hover:text-slate-300">
            Go back to Homepage
          </Link>
        </div>
      </div>
    </div>
  );
}