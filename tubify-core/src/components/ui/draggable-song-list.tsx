import { useState, useEffect } from "react";
import { 
  DndContext, 
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
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

interface DraggableSongListProps {
  songs: Song[];
  playlistPublicId: string;
  onSongRemoved: () => void;
  onSongsReordered: (songs: Song[]) => void;
}

export function DraggableSongList({ 
  songs, 
  playlistPublicId, 
  onSongRemoved,
  onSongsReordered
}: DraggableSongListProps) {
  const [items, setItems] = useState<Song[]>(songs);
  const [isReordering, setIsReordering] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  
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
      // save current scroll position
      const scrollY = window.scrollY;
      
      // lock body scroll
      document.body.style.position = 'fixed';
      document.body.style.top = `-${scrollY}px`;
      document.body.style.width = '100%';
      
      // add dragging class for cursor styling
      document.body.classList.add('dragging');
    } else {
      // unlock body scroll
      const scrollY = document.body.style.top;
      document.body.style.position = '';
      document.body.style.top = '';
      document.body.style.width = '';
      
      // remove dragging class
      document.body.classList.remove('dragging');
      
      // restore scroll position
      if (scrollY) {
        window.scrollTo(0, parseInt(scrollY || '0', 10) * -1);
      }
    }
    
    return () => {
      // cleanup in case component unmounts during drag
      document.body.style.position = '';
      document.body.style.top = '';
      document.body.style.width = '';
      document.body.classList.remove('dragging');
    };
  }, [isDragging]);

  // setup sensors for drag detection
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // minimum drag distance before activation
      },
      canStartDragging: (event: { target: EventTarget }) => {
        return !(event.target as HTMLElement).closest('[data-no-dnd="true"]');
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // handle drag start event
  const handleDragStart = () => {
    setIsDragging(true);
  };
  
  // handle drag cancel event
  const handleDragCancel = () => {
    setIsDragging(false);
  };

  // handle drag end event
  const handleDragEnd = async (event: DragEndEvent) => {
    setIsDragging(false);
    
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
      </DndContext>
    </div>
  );
} 