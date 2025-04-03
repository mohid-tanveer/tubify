import { useState, useRef, useEffect } from "react";
import YouTube, { YouTubeEvent, YouTubePlayer } from "react-youtube";
import { Button } from "./button";
import {
  SkipBack,
  SkipForward,
  Play,
  Pause,
  Music,
  ListMusic,
  Mic,
  X,
  Shuffle,
  ChevronDown,
  Check
} from "lucide-react";
import { cn } from "@/lib/utils";

// types
export interface VideoItem {
  id: string;
  title: string;
  position: number;
}

export interface QueueItem {
  song_id: string;
  name: string;
  artist: string[];
  album: string;
  duration_ms: number;
  spotify_uri: string;
  album_art_url?: string;
  official_video?: VideoItem;
  live_performances: VideoItem[];
}

interface YouTubePlayerProps {
  queue: QueueItem[];
  initialIndex?: number;
  onClose?: () => void;
  autoplay?: boolean;
  preferLivePerformance?: boolean;
  onQueueUpdate?: (newQueue: QueueItem[]) => void;
}

export function YouTubePlayer({
  queue,
  initialIndex = 0,
  onClose,
  autoplay = true,
  preferLivePerformance = false,
  onQueueUpdate,
}: YouTubePlayerProps) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [isPlaying, setIsPlaying] = useState(autoplay);
  const [showQueue, setShowQueue] = useState(false);
  const [preferLive, setPreferLive] = useState(preferLivePerformance);
  const [selectedLiveIndex, setSelectedLiveIndex] = useState(0);
  const [showLiveOptions, setShowLiveOptions] = useState(false);
  const playerRef = useRef<YouTubePlayer | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [currentQueue, setCurrentQueue] = useState<QueueItem[]>(queue);

  const currentItem = currentQueue[currentIndex];
  
  // get the video ID based on preference (official or live)
  const getVideoId = (item: QueueItem) => {
    if (preferLive && item.live_performances && item.live_performances.length > 0) {
      // use the selected live performance index if in range
      const liveIndex = selectedLiveIndex < item.live_performances.length ? selectedLiveIndex : 0;
      return item.live_performances[liveIndex].id;
    }
    return item.official_video?.id || 
           (item.live_performances?.length ? item.live_performances[0].id : undefined);
  };

  const currentVideoId = currentItem ? getVideoId(currentItem) : undefined;
  
  // get current video title
  const getCurrentVideoTitle = () => {
    if (!currentItem) return "";
    
    if (preferLive && currentItem.live_performances && currentItem.live_performances.length > 0) {
      const liveIndex = selectedLiveIndex < currentItem.live_performances.length ? selectedLiveIndex : 0;
      return currentItem.live_performances[liveIndex].title;
    }
    
    return currentItem.official_video?.title || 
           (currentItem.live_performances?.length ? currentItem.live_performances[0].title : "");
  };
  
  // get available live performances count
  const getLivePerformancesCount = () => {
    return currentItem?.live_performances?.length || 0;
  };
  
  // player event handlers
  const handleReady = (event: YouTubeEvent) => {
    playerRef.current = event.target;
    setDuration(playerRef.current.getDuration());
    
    if (autoplay) {
      playerRef.current.playVideo();
    }
  };
  
  const handleStateChange = (event: YouTubeEvent) => {
    const playerState = event.data;
    
    // YouTube states: -1 (unstarted), 0 (ended), 1 (playing), 2 (paused), 3 (buffering), 5 (video cued)
    if (playerState === 1) {
      setIsPlaying(true);
    } else if (playerState === 2) {
      setIsPlaying(false);
    } else if (playerState === 0) {
      // video ended, play next
      playNext();
    }
  };
  
  const handleError = (event: YouTubeEvent) => {
    console.error("YouTube player error:", event);
    // if error, try to play next video
    playNext();
  };
  
  // player controls
  const playPause = () => {
    if (!playerRef.current) return;
    
    if (isPlaying) {
      playerRef.current.pauseVideo();
    } else {
      playerRef.current.playVideo();
    }
    
    setIsPlaying(!isPlaying);
  };
  
  const playPrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
      // reset live performance index when changing songs
      setSelectedLiveIndex(0);
    } else {
      // loop to end of queue
      setCurrentIndex(currentQueue.length - 1);
      setSelectedLiveIndex(0);
    }
  };
  
  const playNext = () => {
    if (currentIndex < currentQueue.length - 1) {
      setCurrentIndex(currentIndex + 1);
      // reset live performance index when changing songs
      setSelectedLiveIndex(0);
    } else {
      // loop to beginning
      setCurrentIndex(0);
      setSelectedLiveIndex(0);
    }
  };
  
  const togglePreference = () => {
    const newPreference = !preferLive;
    setPreferLive(newPreference);
    localStorage.setItem("tubify_prefer_live", newPreference.toString());
  };
  
  const selectLivePerformance = (index: number) => {
    setSelectedLiveIndex(index);
    setShowLiveOptions(false);
  };
  
  const shuffleQueue = () => {
    // create a shuffled copy of the queue
    const shuffled = [...currentQueue];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    
    setCurrentQueue(shuffled);
    setCurrentIndex(0);
    setSelectedLiveIndex(0);
    
    // notify parent of queue change if callback is provided
    if (onQueueUpdate) {
      onQueueUpdate(shuffled);
    }
  };
  
  const removeQueueItem = (index: number) => {
    if (currentQueue.length <= 1) return;
    
    const newQueue = [...currentQueue];
    newQueue.splice(index, 1);
    
    setCurrentQueue(newQueue);
    
    // adjust current index if needed
    if (index === currentIndex) {
      // if removing current item, play next (or previous if at end)
      if (index >= newQueue.length) {
        setCurrentIndex(newQueue.length - 1);
      }
      // else keep the same index as it now points to the next item
    } else if (index < currentIndex) {
      // if removing an item before current, adjust index
      setCurrentIndex(currentIndex - 1);
    }
    
    // notify parent of queue change if callback is provided
    if (onQueueUpdate) {
      onQueueUpdate(newQueue);
    }
  };
  
  // update current time
  useEffect(() => {
    let interval: NodeJS.Timeout;
    
    if (isPlaying && playerRef.current) {
      interval = setInterval(() => {
        setCurrentTime(playerRef.current?.getCurrentTime() || 0);
      }, 1000);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isPlaying]);
  
  // close live options dropdown if clicked outside
  useEffect(() => {
    if (showLiveOptions) {
      const handleClickOutside = (event: MouseEvent) => {
        const target = event.target as HTMLElement;
        if (!target.closest('.live-options-dropdown')) {
          setShowLiveOptions(false);
        }
      };
      
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [showLiveOptions]);
  
  // format time (seconds) to mm:ss
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? "0" + secs : secs}`;
  };
  
  // YouTube player options
  const opts = {
    width: "100%",
    height: "100%",
    playerVars: {
      autoplay: autoplay ? 1 : 0,
      modestbranding: 1,
      rel: 0,
    },
  };
  
  // if no queue or no video ID, show placeholder
  if (!currentItem || !currentVideoId) {
    return (
      <div className="flex flex-col items-center justify-center bg-black h-full w-full">
        <Music className="h-16 w-16 text-gray-500 mb-4" />
        <p className="text-gray-400">no videos available</p>
        {onClose && (
          <Button variant="outline" className="mt-4" onClick={onClose}>
            close
          </Button>
        )}
      </div>
    );
  }
  
  const liveCount = getLivePerformancesCount();
  
  return (
    <div className="flex flex-col h-full w-full bg-black relative overflow-hidden">
      {/* video container */}
      <div className="relative flex-grow overflow-hidden">
        <div className="absolute inset-0">
          <YouTube
            videoId={currentVideoId}
            opts={opts}
            onReady={handleReady}
            onStateChange={handleStateChange}
            onError={handleError}
            className="w-full h-full"
          />
        </div>
        
        {onClose && (
          <button 
            className="absolute top-4 right-4 bg-black/70 text-white p-2 rounded-full z-10 hover:bg-black/90"
            onClick={onClose}
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>
      
      {/* controls overlay at bottom */}
      <div className="bg-black/80 backdrop-blur-sm p-4 w-full">
        {/* song info */}
        <div className="flex justify-between items-center mb-2">
          <div className="flex-1 mr-4">
            <h3 className="text-white font-medium truncate">{currentItem.name}</h3>
            <p className="text-gray-400 text-sm truncate">
              {currentItem.artist.join(", ")} • {currentItem.album}
            </p>
            {preferLive && liveCount > 0 && (
              <div className="text-xs text-gray-500 mt-1 truncate">
                {getCurrentVideoTitle()}
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {/* performance preference toggle */}
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                "text-xs rounded-full",
                preferLive ? "bg-rose-900/30 text-rose-500" : "bg-blue-900/30 text-blue-500"
              )}
              onClick={togglePreference}
            >
              {preferLive ? (
                <>
                  <Mic className="h-3 w-3 mr-1" />
                  live
                </>
              ) : (
                <>
                  <Music className="h-3 w-3 mr-1" />
                  official
                </>
              )}
            </Button>
            
            {/* live performance selector */}
            {preferLive && liveCount > 1 && (
              <div className="relative live-options-dropdown">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs rounded-full bg-slate-800/70 text-white"
                  onClick={() => setShowLiveOptions(!showLiveOptions)}
                >
                  <span className="mr-1">{selectedLiveIndex + 1}/{liveCount}</span>
                  <ChevronDown className="h-3 w-3" />
                </Button>
                
                {showLiveOptions && (
                  <div className="absolute right-0 bottom-full mb-1 bg-slate-900 rounded-md shadow-lg overflow-hidden z-50 w-56 border border-slate-800">
                    <div className="p-2 border-b border-slate-800 text-xs text-slate-400">
                      Select performance
                    </div>
                    <div className="max-h-48 overflow-y-auto py-1">
                      {currentItem.live_performances.map((performance, idx) => (
                        <button
                          key={performance.id}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-slate-800 flex items-center justify-between"
                          onClick={() => selectLivePerformance(idx)}
                        >
                          <span className="truncate mr-2 text-white">
                            {idx + 1}. {performance.title}
                          </span>
                          {idx === selectedLiveIndex && (
                            <Check className="h-4 w-4 text-green-500 flex-shrink-0" />
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        
        {/* progress bar */}
        <div className="relative w-full h-1 bg-slate-700 rounded-full mb-2">
          <div
            className="absolute h-full bg-green-500 rounded-full"
            style={{ width: `${(currentTime / duration) * 100}%` }}
          ></div>
        </div>
        
        <div className="flex justify-between text-xs text-gray-400 mb-3">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>
        
        {/* playback controls */}
        <div className="flex justify-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            className="text-gray-300 hover:text-white"
            onClick={playPrevious}
          >
            <SkipBack className="h-5 w-5" />
          </Button>
          
          <Button
            variant="ghost"
            size="sm"
            className="text-gray-300 hover:text-white"
            onClick={playPause}
          >
            {isPlaying ? (
              <Pause className="h-5 w-5" />
            ) : (
              <Play className="h-5 w-5" />
            )}
          </Button>
          
          <Button
            variant="ghost"
            size="sm"
            className="text-gray-300 hover:text-white"
            onClick={playNext}
          >
            <SkipForward className="h-5 w-5" />
          </Button>
          
          <Button
            variant="ghost"
            size="sm"
            className="text-gray-300 hover:text-white"
            onClick={shuffleQueue}
          >
            <Shuffle className="h-5 w-5" />
          </Button>
          
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "text-gray-300 hover:text-white",
              showQueue ? "text-green-500" : ""
            )}
            onClick={() => setShowQueue(!showQueue)}
          >
            <ListMusic className="h-5 w-5" />
          </Button>
        </div>
      </div>
      
      {/* queue panel as overlay */}
      {showQueue && (
        <div className="absolute right-0 bottom-20 top-0 w-full md:w-80 bg-black/85 backdrop-blur-md z-20 overflow-hidden flex flex-col rounded-tl-xl rounded-bl-xl border-l border-t border-b border-slate-800/50">
          <div className="p-3 border-b border-slate-800/50 flex justify-between items-center">
            <h3 className="text-white font-medium flex items-center">
              <ListMusic className="h-4 w-4 mr-2" />
              play queue • {currentQueue.length} songs
            </h3>
            <Button 
              variant="ghost" 
              size="sm"
              className="text-gray-400 hover:text-white p-1 h-auto"
              onClick={() => setShowQueue(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          
          <div className="overflow-y-auto flex-grow px-1">
            {currentQueue.map((item, idx) => (
              <div
                key={`${item.song_id}-${idx}`}
                className={cn(
                  "flex p-2 hover:bg-slate-800/60 cursor-pointer rounded-lg my-1 transition-colors",
                  idx === currentIndex ? "bg-slate-800/80" : ""
                )}
                onClick={() => {
                  setCurrentIndex(idx);
                  setSelectedLiveIndex(0);
                  // optionally close queue on mobile
                  if (window.innerWidth < 768) setShowQueue(false);
                }}
              >
                <div className="w-10 h-10 flex-shrink-0 mr-3 rounded overflow-hidden">
                  {item.album_art_url ? (
                    <img
                      src={item.album_art_url}
                      alt={item.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full bg-slate-700 flex items-center justify-center">
                      <Music className="h-4 w-4 text-slate-500" />
                    </div>
                  )}
                </div>
                
                <div className="flex-1 min-w-0 flex flex-col justify-center">
                  <p className={`text-sm font-medium truncate ${idx === currentIndex ? "text-green-500" : "text-white"}`}>
                    {item.name}
                  </p>
                  <p className="text-xs text-gray-400 truncate">{item.artist.join(", ")}</p>
                </div>
                
                <div className="flex items-center ml-2">
                  <button
                    className="text-gray-500 hover:text-red-500 p-1 rounded-full"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeQueueItem(idx);
                    }}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
} 