import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Music, Play, Trash2, Loader2 } from "lucide-react";
import api from "@/lib/axios";
import { toast } from "sonner";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { clearPlaylistDetailCache, clearPlaylistsCache } from "@/loaders/playlist-loaders";

// song type
interface Song {
  id: number;
  spotify_id: string;
  name: string;
  artist: string;
  album?: string;
  duration_ms?: number;
  preview_url?: string;
  album_art_url?: string;
  created_at: string;
}

// format duration from ms to mm:ss
const formatDuration = (ms: number | undefined) => {
  if (!ms) return "--:--";
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
};

interface SortableSongItemProps {
  song: Song;
  index: number;
  playlistPublicId: string;
  onSongRemoved: () => void;
  disabled?: boolean;
}

export function SortableSongItem({ 
  song, 
  index, 
  playlistPublicId, 
  onSongRemoved,
  disabled = false
}: SortableSongItemProps) {
  const [isRemoving, setIsRemoving] = useState(false);
  
  // setup sortable hook
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: song.id });
  
  // apply styles for dragging
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 1 : 0,
    cursor: 'default',
  };

  const handleRemoveSong = async (e: React.MouseEvent) => {
    e.stopPropagation();
    
    try {
      setIsRemoving(true);
      await api.delete(`/api/playlists/${playlistPublicId}/songs/${song.id}`);
      
      // clear caches to ensure fresh data
      clearPlaylistDetailCache(playlistPublicId);
      clearPlaylistsCache();
      
      // notify parent component
      onSongRemoved();
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.error("failed to remove song:", error);
      }
      toast.error("failed to remove song from playlist");
    } finally {
      setIsRemoving(false);
    }
  };

  const handlePlayPreview = (e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (song.preview_url) {
      window.open(song.preview_url, "_blank");
    }
  };

  return (
    <div 
      ref={setNodeRef} 
      style={style}
      className={`grid grid-cols-12 gap-4 rounded-md p-2 text-sm ${
        isDragging 
          ? 'bg-slate-800 border border-slate-600 shadow-lg' 
          : 'hover:bg-slate-900'
      } cursor-default!`}
      {...attributes}
      {...listeners}
    >
      <div className="col-span-1 flex items-center text-slate-400">
        <span>{index + 1}</span>
      </div>
      <div className="col-span-5 flex items-center gap-3">
        {song.album_art_url ? (
          <img
            src={song.album_art_url}
            alt={song.name}
            className="h-10 w-10 rounded object-cover"
          />
        ) : (
          <div className="flex h-10 w-10 items-center justify-center rounded bg-slate-800">
            <Music className="h-5 w-5 text-slate-600" />
          </div>
        )}
        <div className="truncate">
          <div className="font-medium text-white">{song.name}</div>
          {song.album && (
            <div className="truncate text-xs text-slate-500">
              {song.album}
            </div>
          )}
        </div>
      </div>
      <div className="col-span-3 flex items-center text-slate-300">
        {song.artist}
      </div>
      <div className="col-span-2 flex items-center justify-end gap-2 text-slate-400">
        {song.preview_url && (
          <Button
            size="icon"
            variant="ghost"
            className="h-6 w-6 rounded-full hover:bg-green-900/30 hover:text-green-500"
            onClick={handlePlayPreview}
            disabled={disabled}
            data-no-dnd="true"
          >
            <Play className="h-3 w-3" />
          </Button>
        )}
        <span>{formatDuration(song.duration_ms)}</span>
      </div>
      <div className="col-span-1 flex items-center justify-end">
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7 rounded-full hover:bg-red-900/30 hover:text-red-500"
          onClick={handleRemoveSong}
          disabled={isRemoving || disabled}
          data-no-dnd="true"
        >
          {isRemoving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Trash2 className="h-4 w-4" />
          )}
        </Button>
      </div>
    </div>
  );
} 