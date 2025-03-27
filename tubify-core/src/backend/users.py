from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from database import database
import json

router = APIRouter(prefix="/api/users", tags=["users"])


class UserProfile(BaseModel):
    username: str
    profilePicture: str
    bio: str
    playlistCount: int


class UserPlaylist(BaseModel):
    id: int
    public_id: str
    name: str
    description: Optional[str] = None
    is_public: bool = True
    spotify_playlist_id: Optional[str] = None
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    song_count: int


class Song(BaseModel):
    id: int
    name: str
    artist: str
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    album_art_url: Optional[str] = None
    spotify_uri: Optional[str] = None


class UserPlaylist(BaseModel):
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


@router.get("/{username}/profile", response_model=UserProfile)
async def get_user_profile(username: str):
    # get user by username
    user = await database.fetch_one(
        """
        SELECT id, username 
        FROM users 
        WHERE username = :username
        """,
        values={"username": username},
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
        )

    # get profile data
    profile = await database.fetch_one(
        """
        SELECT 
            u.username,
            COALESCE(p.profile_picture, 'https://ui-avatars.com/api/?name=' || u.username) as profile_picture,
            COALESCE(p.bio, '') as bio,
            (
                SELECT COUNT(*)
                FROM playlists
                WHERE user_id = u.id AND is_public = TRUE
            ) as playlist_count
        FROM users u
        LEFT JOIN profiles p ON u.id = p.user_id
        WHERE u.username = :username
        """,
        values={"username": username},
    )

    if not profile:
        # this shouldn't happen if the user exists, but just in case
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="profile not found"
        )

    return {
        "username": profile["username"],
        "profilePicture": profile["profile_picture"],
        "bio": profile["bio"],
        "playlistCount": profile["playlist_count"],
    }


@router.get("/{username}/playlists", response_model=List[UserPlaylist])
async def get_user_public_playlists(username: str):
    # get user by username
    user = await database.fetch_one(
        """
        SELECT id 
        FROM users 
        WHERE username = :username
        """,
        values={"username": username},
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
        )

    # get public playlists
    query = """
    SELECT 
        p.id, 
        p.name, 
        p.description, 
        p.is_public, 
        p.spotify_playlist_id,
        p.image_url,
        p.public_id,
        p.created_at,
        p.updated_at,
        (
            SELECT COUNT(*)
            FROM playlist_songs ps
            WHERE ps.playlist_id = p.id
        ) as song_count
    FROM playlists p
    WHERE p.user_id = :user_id AND p.is_public = TRUE
    ORDER BY p.created_at DESC
    """

    values = {"user_id": user["id"]}

    result = await database.fetch_all(query=query, values=values)
    playlists = []

    # process each playlist
    for row in result:
        playlist_dict = dict(row)

        playlists.append(playlist_dict)

    return playlists


@router.get("/playlists/{public_id}", response_model=UserPlaylist)
async def get_user_playlist(public_id: str):
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
                (SELECT json_agg(
                    json_build_object(
                        'id', song_data.id,
                        'name', song_data.name,
                        'artist', song_data.artist_names,
                        'album', song_data.album_name,
                        'spotify_uri', song_data.spotify_uri,
                        'duration_ms', song_data.duration_ms,
                        'album_art_url', song_data.image_url
                    ) ORDER BY song_data.position
                )
                FROM (
                    SELECT 
                        s.id,
                        s.name,
                        array_agg(a.name ORDER BY sa.list_position) as artist_names,
                        al.name as album_name,
                        s.spotify_uri,
                        s.duration_ms,
                        al.image_url,
                        ps.position
                    FROM playlist_songs ps
                    JOIN songs s ON ps.song_id = s.id
                    JOIN song_artists sa ON s.id = sa.song_id
                    JOIN artists a ON sa.artist_id = a.id
                    JOIN albums al ON s.album_id = al.id
                    WHERE ps.playlist_id = p.id
                    GROUP BY s.id, al.name, al.image_url, ps.position
                ) as song_data),
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
