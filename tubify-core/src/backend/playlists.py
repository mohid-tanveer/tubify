from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import spotipy, os
from spotipy.oauth2 import SpotifyOAuth
from auth import get_current_user, User
from database import database

# create router
router = APIRouter(prefix="/api/playlists", tags=["playlists"])


# models
class SongBase(BaseModel):
    spotify_id: str
    name: str
    artist: str
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    preview_url: Optional[str] = None
    album_art_url: Optional[str] = None


class PlaylistCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = True
    spotify_playlist_id: Optional[str] = None


class PlaylistUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


class Song(SongBase):
    id: int
    created_at: datetime


class Playlist(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_public: bool
    spotify_playlist_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    songs: List[Song]


# get spotify client for user
async def get_spotify_client(user: User = Depends(get_current_user)) -> spotipy.Spotify:
    spotify_creds = await database.fetch_one(
        "SELECT * FROM spotify_credentials WHERE user_id = :user_id",
        values={"user_id": user.id},
    )

    if not spotify_creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="spotify account not connected",
        )

    sp_oauth = SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    )

    if datetime.now(timezone.utc) >= spotify_creds["token_expires_at"]:
        token_info = sp_oauth.refresh_access_token(spotify_creds["refresh_token"])
        await database.execute(
            """
            UPDATE spotify_credentials 
            SET access_token = :access_token,
                refresh_token = :refresh_token,
                token_expires_at = :expires_at,
                last_used_at = CURRENT_TIMESTAMP
            WHERE user_id = :user_id
            """,
            values={
                "access_token": token_info["access_token"],
                "refresh_token": token_info["refresh_token"],
                "expires_at": datetime.now(timezone.utc)
                + timedelta(seconds=token_info["expires_in"]),
                "user_id": user.id,
            },
        )
        return spotipy.Spotify(auth=token_info["access_token"])

    return spotipy.Spotify(auth=spotify_creds["access_token"])


# endpoints
@router.post("/", response_model=Playlist)
async def create_playlist(
    playlist: PlaylistCreate,
    user: User = Depends(get_current_user),
    sp: spotipy.Spotify = Depends(get_spotify_client),
):
    # create playlist in database
    playlist_id = await database.execute(
        """
        INSERT INTO playlists (user_id, name, description, is_public, spotify_playlist_id)
        VALUES (:user_id, :name, :description, :is_public, :spotify_playlist_id)
        RETURNING id
        """,
        values={
            "user_id": user.id,
            "name": playlist.name,
            "description": playlist.description,
            "is_public": playlist.is_public,
            "spotify_playlist_id": playlist.spotify_playlist_id,
        },
    )

    # if spotify playlist id is provided, import songs
    if playlist.spotify_playlist_id:
        sp_playlist = sp.playlist(playlist.spotify_playlist_id)
        for i, item in enumerate(sp_playlist["tracks"]["items"]):
            track = item["track"]
            # insert song if not exists
            song_id = await database.execute(
                """
                INSERT INTO songs (spotify_id, name, artist, album, duration_ms, preview_url, album_art_url)
                VALUES (:spotify_id, :name, :artist, :album, :duration_ms, :preview_url, :album_art_url)
                ON CONFLICT (spotify_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    artist = EXCLUDED.artist,
                    album = EXCLUDED.album,
                    duration_ms = EXCLUDED.duration_ms,
                    preview_url = EXCLUDED.preview_url,
                    album_art_url = EXCLUDED.album_art_url
                RETURNING id
                """,
                values={
                    "spotify_id": track["id"],
                    "name": track["name"],
                    "artist": track["artists"][0]["name"],
                    "album": track["album"]["name"],
                    "duration_ms": track["duration_ms"],
                    "preview_url": track["preview_url"],
                    "album_art_url": (
                        track["album"]["images"][0]["url"]
                        if track["album"]["images"]
                        else None
                    ),
                },
            )

            # add song to playlist
            await database.execute(
                """
                INSERT INTO playlist_songs (playlist_id, song_id, position)
                VALUES (:playlist_id, :song_id, :position)
                """,
                values={"playlist_id": playlist_id, "song_id": song_id, "position": i},
            )

    return await get_playlist(playlist_id, user)


@router.get("/{playlist_id}", response_model=Playlist)
async def get_playlist(playlist_id: int, user: User = Depends(get_current_user)):
    # get playlist with songs
    playlist = await database.fetch_one(
        """
        SELECT p.*, array_agg(json_build_object(
            'id', s.id,
            'spotify_id', s.spotify_id,
            'name', s.name,
            'artist', s.artist,
            'album', s.album,
            'duration_ms', s.duration_ms,
            'preview_url', s.preview_url,
            'album_art_url', s.album_art_url,
            'created_at', s.created_at
        ) ORDER BY ps.position) as songs
        FROM playlists p
        LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
        LEFT JOIN songs s ON ps.song_id = s.id
        WHERE p.id = :playlist_id
        AND (p.is_public = TRUE OR p.user_id = :user_id)
        GROUP BY p.id
        """,
        values={"playlist_id": playlist_id, "user_id": user.id},
    )

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
        )

    return playlist


@router.get("/", response_model=List[Playlist])
async def get_playlists(user: User = Depends(get_current_user)):
    # get all playlists visible to user
    playlists = await database.fetch_all(
        """
        SELECT p.*, array_agg(json_build_object(
            'id', s.id,
            'spotify_id', s.spotify_id,
            'name', s.name,
            'artist', s.artist,
            'album', s.album,
            'duration_ms', s.duration_ms,
            'preview_url', s.preview_url,
            'album_art_url', s.album_art_url,
            'created_at', s.created_at
        ) ORDER BY ps.position) as songs
        FROM playlists p
        LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
        LEFT JOIN songs s ON ps.song_id = s.id
        WHERE p.is_public = TRUE OR p.user_id = :user_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
        """,
        values={"user_id": user.id},
    )

    return playlists


@router.put("/{playlist_id}", response_model=Playlist)
async def update_playlist(
    playlist_id: int, playlist: PlaylistUpdate, user: User = Depends(get_current_user)
):
    # verify user owns playlist
    existing = await database.fetch_one(
        "SELECT * FROM playlists WHERE id = :id AND user_id = :user_id",
        values={"id": playlist_id, "user_id": user.id},
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
        )

    # update playlist
    update_fields = {k: v for k, v in playlist.dict().items() if v is not None}
    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        query = (
            """
        UPDATE playlists SET 
        """
            + ", ".join(f"{k} = :{k}" for k in update_fields.keys())
            + """
        WHERE id = :id AND user_id = :user_id
        """
        )
        update_fields.update({"id": playlist_id, "user_id": user.id})
        await database.execute(query, values=update_fields)

    return await get_playlist(playlist_id, user)


@router.delete("/{playlist_id}")
async def delete_playlist(playlist_id: int, user: User = Depends(get_current_user)):
    # verify user owns playlist
    existing = await database.fetch_one(
        "SELECT * FROM playlists WHERE id = :id AND user_id = :user_id",
        values={"id": playlist_id, "user_id": user.id},
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
        )

    # delete playlist (cascade will handle playlist_songs)
    await database.execute(
        "DELETE FROM playlists WHERE id = :id AND user_id = :user_id",
        values={"id": playlist_id, "user_id": user.id},
    )

    return {"message": "playlist deleted successfully"}


@router.post("/{playlist_id}/songs")
async def add_songs(
    playlist_id: int, songs: List[SongBase], user: User = Depends(get_current_user)
):
    # verify user owns playlist
    existing = await database.fetch_one(
        "SELECT * FROM playlists WHERE id = :id AND user_id = :user_id",
        values={"id": playlist_id, "user_id": user.id},
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
        )

    # get current max position
    max_pos = await database.fetch_val(
        "SELECT COALESCE(MAX(position), -1) FROM playlist_songs WHERE playlist_id = :playlist_id",
        values={"playlist_id": playlist_id},
    )

    # add songs
    for i, song in enumerate(songs, start=max_pos + 1):
        # insert song if not exists
        song_id = await database.execute(
            """
            INSERT INTO songs (spotify_id, name, artist, album, duration_ms, preview_url, album_art_url)
            VALUES (:spotify_id, :name, :artist, :album, :duration_ms, :preview_url, :album_art_url)
            ON CONFLICT (spotify_id) DO UPDATE SET
                name = EXCLUDED.name,
                artist = EXCLUDED.artist,
                album = EXCLUDED.album,
                duration_ms = EXCLUDED.duration_ms,
                preview_url = EXCLUDED.preview_url,
                album_art_url = EXCLUDED.album_art_url
            RETURNING id
            """,
            values=song.dict(),
        )

        # add to playlist
        await database.execute(
            """
            INSERT INTO playlist_songs (playlist_id, song_id, position)
            VALUES (:playlist_id, :song_id, :position)
            """,
            values={"playlist_id": playlist_id, "song_id": song_id, "position": i},
        )

    return {"message": "songs added successfully"}


@router.delete("/{playlist_id}/songs/{song_id}")
async def remove_song(
    playlist_id: int, song_id: int, user: User = Depends(get_current_user)
):
    # verify user owns playlist
    existing = await database.fetch_one(
        "SELECT * FROM playlists WHERE id = :id AND user_id = :user_id",
        values={"id": playlist_id, "user_id": user.id},
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
        )

    # remove song and reorder positions
    async with database.transaction():
        # get position of song to remove
        pos = await database.fetch_val(
            """
            DELETE FROM playlist_songs 
            WHERE playlist_id = :playlist_id AND song_id = :song_id
            RETURNING position
            """,
            values={"playlist_id": playlist_id, "song_id": song_id},
        )

        if pos is not None:
            # update positions of remaining songs
            await database.execute(
                """
                UPDATE playlist_songs 
                SET position = position - 1
                WHERE playlist_id = :playlist_id AND position > :position
                """,
                values={"playlist_id": playlist_id, "position": pos},
            )

    return {"message": "song removed successfully"}


@router.put("/{playlist_id}/songs/reorder")
async def reorder_songs(
    playlist_id: int, song_ids: List[int], user: User = Depends(get_current_user)
):
    # verify user owns playlist
    existing = await database.fetch_one(
        "SELECT * FROM playlists WHERE id = :id AND user_id = :user_id",
        values={"id": playlist_id, "user_id": user.id},
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
        )

    # verify all songs exist in playlist
    playlist_songs = await database.fetch_all(
        "SELECT song_id FROM playlist_songs WHERE playlist_id = :playlist_id",
        values={"playlist_id": playlist_id},
    )
    playlist_song_ids = {ps["song_id"] for ps in playlist_songs}

    if not all(sid in playlist_song_ids for sid in song_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid song ids provided"
        )

    # update positions
    async with database.transaction():
        for i, song_id in enumerate(song_ids):
            await database.execute(
                """
                UPDATE playlist_songs 
                SET position = :position
                WHERE playlist_id = :playlist_id AND song_id = :song_id
                """,
                values={"playlist_id": playlist_id, "song_id": song_id, "position": i},
            )

    return {"message": "songs reordered successfully"}
