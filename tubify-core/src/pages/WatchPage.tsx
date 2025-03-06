import { Link } from "react-router-dom"
import { TubifyTitle } from "@/components/ui/tubify-title"
import YouTube, { YouTubeEvent } from "react-youtube"
import { Button } from "@/components/ui/button"

export default function WatchPage() {
  const videoId = "dQw4w9WgXcQ"

  const opts = {
    height: '390',
    width: '640',
    playerVars: {
      // https://developers.google.com/youtube/player_parameters
      autoplay: 1,
    },
  }

  const onReady = (event: YouTubeEvent) => {
    // access to player in all event handlers via event.target
    event.target.pauseVideo()
  }

  return (
    <div className="overflow-hidden flex flex-col min-h-screen">
      <div className="absolute top-0 left-0">
        <TubifyTitle />
      </div>
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <h1 className="text-white text-4xl">Welcome to the Watch Page!</h1>
          <YouTube videoId={videoId} opts={opts} onReady={onReady} />
          
          <Button
              asChild
              className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
            >
              <Link to="/" className="text-white hover:text-slate-300">
                Go back to Homepage
              </Link>
          </Button>
        </div>
      </div>
    </div>
  )
}