import { useState, useEffect } from "react";
import { 
  DndContext, 
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragOverlay,
  defaultDropAnimationSideEffects,
  DropAnimation,
  DragStartEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { SortableSongItem } from "./sortable-song-item";
import api from "@/lib/axios";
import { toast } from "sonner"
import { clearPlaylistDetailCache } from "@/loaders/playlist-loaders";

// song type
interface Song {
  id: string;
  name: string;
  artist: string;
  album?: string;
  spotify_uri: string;
  duration_ms?: number;
  album_art_url?: string;
  created_at: string;
}

interface DraggableSongListProps {
  songs: Song[];
  playlistPublicId: string;
  onSongRemoved: () => void;
  onSongsReordered: (songs: Song[]) => void;
}

const dropAnimation: DropAnimation = {
  sideEffects: defaultDropAnimationSideEffects({
    styles: {
      active: {
        opacity: '0.5',
      },
    },
  }),
};

export function DraggableSongList({ 
  songs, 
  playlistPublicId, 
  onSongRemoved,
  onSongsReordered
}: DraggableSongListProps) {
  const [items, setItems] = useState<Song[]>(songs);
  const [isReordering, setIsReordering] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  
  // update items when songs prop changes
  useEffect(() => {
    setItems(songs);
  }, [songs]);
  
  // handle song removed
  const handleSongRemoved = () => {
    // call parent callback to refresh data
    onSongRemoved();
  };

  // prevent body scrolling during drag
  useEffect(() => {
    if (isDragging) {
      
      // prevent horizontal scrolling during drag
      const preventHorizontalScroll = (e: WheelEvent) => {
        if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
          e.preventDefault();
        }
      };
      
      // add event listener to prevent horizontal scrolling
      document.addEventListener('wheel', preventHorizontalScroll, { passive: false });
      
      return () => {
        document.removeEventListener('wheel', preventHorizontalScroll);
      };
    }
  }, [isDragging]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 4,
      },
      canStartDragging: (event: { target: EventTarget }) => {
        return !(event.target as HTMLElement).closest('[data-no-dnd="true"]');
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event;
    setActiveId(String(active.id));
    setIsDragging(true);
  };
  
  const handleDragCancel = () => {
    setActiveId(null);
    setIsDragging(false);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    setIsDragging(false);
    setActiveId(null);
    
    const { active, over } = event;
    
    if (over && active.id !== over.id) {
      // find indices for the items being reordered
      const oldIndex = items.findIndex((item) => item.id === active.id);
      const newIndex = items.findIndex((item) => item.id === over.id);
      
      // create the reordered array
      const reorderedItems = arrayMove(items, oldIndex, newIndex);
      
      // update local state immediately for responsive UI
      setItems(reorderedItems);
      
      // update backend
      try {
        setIsReordering(true);
        
        // get song ids in new order
        const updatedSongIds = reorderedItems.map((song) => song.id);
        
        // call API to update order with the correct format
        await api.put(`/api/playlists/${playlistPublicId}/songs/reorder`, {
          song_ids: updatedSongIds
        });
        
        // clear cache for this playlist
        clearPlaylistDetailCache(playlistPublicId);
        
        // notify parent component
        onSongsReordered(reorderedItems);
      } catch (error) {
        if (process.env.NODE_ENV === 'development') {
          console.error("failed to reorder songs:", error);
        }
        toast.error("failed to update song order");
        
        // revert to original order on error
        setItems(songs);
      } finally {
        setIsReordering(false);
      }
    }
  };

  // find active song for overlay
  const activeSong = activeId ? items.find(song => song.id === activeId) : null;
  const activeIndex = activeSong ? items.findIndex(song => song.id === activeId) : -1;

  return (
    <div className="space-y-2 pb-8">
      <DndContext 
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        <SortableContext 
          items={items.map(song => song.id)} 
          strategy={verticalListSortingStrategy}
        >
          {items.map((song, index) => (
            <SortableSongItem
              key={song.id}
              song={song}
              index={index}
              playlistPublicId={playlistPublicId}
              onSongRemoved={handleSongRemoved}
              disabled={isReordering}
            />
          ))}
        </SortableContext>
        
        <DragOverlay dropAnimation={dropAnimation}>
          {activeId && activeSong ? (
            <div className="grid grid-cols-12 gap-4 rounded-md p-2 bg-slate-800 border border-slate-600 shadow-lg text-xs md:text-sm">
              <div className="col-span-1 flex items-center text-slate-400">
                <span>{activeIndex + 1}</span>
              </div>
              <div className="col-span-5 flex items-center gap-2 md:gap-3">
                <img
                  src={activeSong.album_art_url}
                  alt={activeSong.name}
                  className="h-8 w-8 md:h-10 md:w-10 rounded object-cover"
                />
                <div className="truncate">
                  <div className="font-medium text-white text-xs md:text-sm">{activeSong.name}</div>
                  {activeSong.album && (
                    <div className="truncate text-xs md:text-xs text-[10px] text-slate-500">
                      {activeSong.album}
                    </div>
                  )}
                </div>
              </div>
              <div className="col-span-3 flex items-center text-slate-300 text-xs md:text-sm">
                {activeSong.artist}
              </div>
              <div className="col-span-3 flex items-center justify-end text-slate-400 text-xs md:text-sm">
              </div>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
} 