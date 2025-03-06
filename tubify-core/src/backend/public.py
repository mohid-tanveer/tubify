from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from database import database
import json

router = APIRouter(prefix="/api/public", tags=["public"])


class Song(BaseModel):
    id: int
    spotify_id: str
    name: str
    artist: str
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    preview_url: Optional[str] = None
    album_art_url: Optional[str] = None
    created_at: str


class PublicPlaylist(BaseModel):
    id: int
    public_id: str
    name: str
    description: Optional[str] = None
    is_public: bool = True
    spotify_playlist_id: Optional[str] = None
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    songs: List[Dict[str, Any]]
    username: str


@router.get("/playlists/{public_id}", response_model=PublicPlaylist)
async def get_public_playlist(public_id: str):
    # get playlist with songs and username
    playlist = await database.fetch_one(
        """
        SELECT 
            p.id,
            p.user_id,
            p.name,
            p.description,
            p.is_public,
            p.spotify_playlist_id,
            p.image_url,
            p.public_id,
            p.created_at,
            p.updated_at,
            u.username,
            COALESCE(
                (SELECT json_agg(json_build_object(
                    'id', s.id,
                    'spotify_id', s.spotify_id,
                    'name', s.name,
                    'artist', s.artist,
                    'album', s.album,
                    'duration_ms', s.duration_ms,
                    'preview_url', s.preview_url,
                    'album_art_url', s.album_art_url,
                    'created_at', s.created_at
                ) ORDER BY ps.position)
                FROM playlist_songs ps
                JOIN songs s ON ps.song_id = s.id
                WHERE ps.playlist_id = p.id),
                '[]'::json
            ) as songs
        FROM playlists p
        JOIN users u ON p.user_id = u.id
        WHERE p.public_id = :public_id
        AND p.is_public = TRUE
        """,
        values={"public_id": public_id},
    )

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="playlist not found or not public",
        )

    # convert to dict and parse songs if needed
    playlist_dict = dict(playlist)
    if isinstance(playlist_dict["songs"], str):
        try:
            playlist_dict["songs"] = json.loads(playlist_dict["songs"])
        except:
            playlist_dict["songs"] = []

    return playlist_dict
