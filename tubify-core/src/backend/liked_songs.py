from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import spotipy
import asyncio
import time

from auth import get_current_user, User
from database import database


def get_spotify_client():
    from spotify_auth import get_spotify_client as spotify_auth_get_spotify_client

    return spotify_auth_get_spotify_client


# create router
router = APIRouter(prefix="/api/liked-songs", tags=["liked-songs"])


# models
class SyncStatus(BaseModel):
    is_syncing: bool
    last_synced_at: Optional[datetime] = None
    progress: float = 0
    total_songs: int = 0
    processed_songs: int = 0


class LikedSong(BaseModel):
    id: str
    name: str
    artist: str
    album: str
    duration_ms: int
    album_art_url: Optional[str] = None
    liked_at: datetime


# background task to sync liked songs
async def sync_liked_songs_background(user_id: int, spotify_client: spotipy.Spotify):
    try:
        # create a new sync job
        job_id = await database.execute(
            """
            INSERT INTO liked_songs_sync_jobs 
            (user_id, status, started_at, progress) 
            VALUES (:user_id, 'running', CURRENT_TIMESTAMP, 0)
            RETURNING id
            """,
            {"user_id": user_id},
        )

        # update spotify credentials to show sync is in progress
        await database.execute(
            """
            UPDATE spotify_credentials 
            SET liked_songs_sync_status = 'syncing' 
            WHERE user_id = :user_id
            """,
            {"user_id": user_id},
        )

        # get user's liked tracks from spotify
        offset = 0
        limit = 50
        total = None
        processed = 0

        # collect all artist and album data to batch insert
        artists_map = {}
        albums_map = {}
        songs_map = {}
        artist_song_map = {}
        artist_album_map = {}
        artist_genre_map = {}

        while total is None or offset < total:
            # get next batch of tracks
            results = spotify_client.current_user_saved_tracks(
                limit=limit, offset=offset
            )

            if total is None:
                total = results["total"]

                # update job with total count
                await database.execute(
                    """
                    UPDATE liked_songs_sync_jobs 
                    SET songs_total = :total 
                    WHERE id = :job_id
                    """,
                    {"total": total, "job_id": job_id},
                )

                # update spotify credentials with total count
                await database.execute(
                    """
                    UPDATE spotify_credentials 
                    SET liked_songs_count = :total 
                    WHERE user_id = :user_id
                    """,
                    {"total": total, "user_id": user_id},
                )

            # process tracks
            if not results["items"]:
                break

            for idx, item in enumerate(results["items"]):
                track = item["track"]
                added_at = item["added_at"]

                # process artists
                for artist in track["artists"]:
                    artist_id = artist["id"]
                    artists_map[artist_id] = {
                        "id": artist_id,
                        "name": artist["name"],
                        "image_url": "https://placeholder.com/artist",
                        "popularity": 0,
                    }

                    # create artist-song relationship
                    if track["id"] not in artist_song_map:
                        artist_song_map[track["id"]] = []
                    artist_song_map[track["id"]].append(
                        {"artist_id": artist_id, "position": idx}
                    )

                # process album
                album = track["album"]
                album_id = album["id"]
                albums_map[album_id] = {
                    "id": album_id,
                    "name": album["name"],
                    "image_url": (
                        album["images"][0]["url"]
                        if album["images"]
                        else "https://placeholder.com/album"
                    ),
                    "release_date": album.get("release_date"),
                    "album_type": album.get("album_type", "unknown"),
                    "total_tracks": album.get("total_tracks", 0),
                    "popularity": 0,  # placeholder
                }

                # create album-artist relationships
                for idx, artist in enumerate(album["artists"]):
                    artist_id = artist["id"]
                    # make sure artist exists in map
                    if artist_id not in artists_map:
                        artists_map[artist_id] = {
                            "id": artist_id,
                            "name": artist["name"],
                            "image_url": "https://placeholder.com/artist",
                            "popularity": 0,
                        }

                    # add to album-artist map
                    if album_id not in artist_album_map:
                        artist_album_map[album_id] = []
                    artist_album_map[album_id].append(
                        {"artist_id": artist_id, "position": idx}
                    )

                # process track
                songs_map[track["id"]] = {
                    "id": track["id"],
                    "name": track["name"],
                    "album_id": album_id,
                    "duration_ms": track["duration_ms"],
                    "spotify_uri": track["uri"],
                    "spotify_url": track["external_urls"].get("spotify", ""),
                    "popularity": track.get("popularity", 0),
                    "explicit": track.get("explicit", False),
                    "track_number": track.get("track_number", 0),
                    "disc_number": track.get("disc_number", 0),
                    "preview_url": track.get("preview_url", None),
                    "added_at": added_at,
                }

                processed += 1

            # update progress
            progress = processed / total if total > 0 else 0
            await database.execute(
                """
                UPDATE liked_songs_sync_jobs 
                SET progress = :progress, songs_processed = :processed 
                WHERE id = :job_id
                """,
                {"progress": progress, "processed": processed, "job_id": job_id},
            )

            # move to next batch
            offset += limit

            # add a small delay to prevent rate limiting
            await asyncio.sleep(0.5)

        artist_ids = list(artists_map.keys())
        for i in range(0, len(artist_ids), 50):
            batch = artist_ids[i : i + 50]
            artist_data = spotify_client.artists(batch)

            for artist in artist_data["artists"]:
                # update artist with real data
                if artist["id"] in artists_map:
                    artists_map[artist["id"]]["popularity"] = artist.get(
                        "popularity", 0
                    )
                    if artist.get("images"):
                        artists_map[artist["id"]]["image_url"] = artist["images"][0][
                            "url"
                        ]

                    # store genres
                    if artist.get("genres"):
                        artist_genre_map[artist["id"]] = set(artist["genres"])

        async with database.transaction():
            # 1. insert artists
            for artist_id, artist in artists_map.items():
                await database.execute(
                    """
                    INSERT INTO artists (id, name, image_url, popularity)
                    VALUES (:id, :name, :image_url, :popularity)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        image_url = EXCLUDED.image_url,
                        popularity = EXCLUDED.popularity
                    """,
                    artist,
                )

            # 2. insert albums
            for album_id, album in albums_map.items():
                await database.execute(
                    """
                    INSERT INTO albums (id, name, image_url, release_date, album_type, total_tracks, popularity)
                    VALUES (:id, :name, :image_url, :release_date, :album_type, :total_tracks, :popularity)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        image_url = EXCLUDED.image_url,
                        release_date = EXCLUDED.release_date,
                        album_type = EXCLUDED.album_type,
                        total_tracks = EXCLUDED.total_tracks,
                        popularity = EXCLUDED.popularity
                    """,
                    album,
                )

            # 3. insert album-artist relationships
            for album_id, artists in artist_album_map.items():
                for artist in artists:
                    await database.execute(
                        """
                        INSERT INTO album_artists (album_id, artist_id, list_position)
                        VALUES (:album_id, :artist_id, :position)
                        ON CONFLICT (album_id, artist_id) DO UPDATE SET
                            list_position = EXCLUDED.list_position
                        """,
                        {
                            "album_id": album_id,
                            "artist_id": artist["artist_id"],
                            "position": artist["position"],
                        },
                    )

            # 4. insert genres and artist-genre relationships
            if artist_genre_map:
                unique_genres = list(
                    set(
                        genre
                        for genres in artist_genre_map.values()
                        for genre in genres
                    )
                )

                # insert any new genres
                await database.execute(
                    """
                    INSERT INTO genres (name)
                    SELECT unnest(:names::text[])
                    ON CONFLICT (name) DO NOTHING
                    """,
                    {"names": unique_genres},
                )

                # get genre IDs
                genre_id_rows = await database.fetch_all(
                    """
                    SELECT name, id 
                    FROM genres 
                    WHERE name = ANY(:names)
                    """,
                    {"names": unique_genres},
                )

                # create name to ID mapping
                genre_id_map = {row["name"]: row["id"] for row in genre_id_rows}

                # insert artist-genre relationships
                for artist_id, genres in artist_genre_map.items():
                    for genre in genres:
                        genre_id = genre_id_map.get(genre)
                        if genre_id:
                            await database.execute(
                                """
                                INSERT INTO artist_genres (artist_id, genre_id)
                                VALUES (:artist_id, :genre_id)
                                ON CONFLICT (artist_id, genre_id) DO NOTHING
                                """,
                                {"artist_id": artist_id, "genre_id": genre_id},
                            )

            # 5. insert songs
            for song_id, song in songs_map.items():
                await database.execute(
                    """
                    INSERT INTO songs (id, name, album_id, duration_ms, spotify_uri, spotify_url, 
                                     popularity, explicit, track_number, disc_number, preview_url)
                    VALUES (:id, :name, :album_id, :duration_ms, :spotify_uri, :spotify_url,
                           :popularity, :explicit, :track_number, :disc_number, :preview_url)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        album_id = EXCLUDED.album_id,
                        duration_ms = EXCLUDED.duration_ms,
                        spotify_uri = EXCLUDED.spotify_uri,
                        spotify_url = EXCLUDED.spotify_url,
                        popularity = EXCLUDED.popularity,
                        explicit = EXCLUDED.explicit,
                        track_number = EXCLUDED.track_number,
                        disc_number = EXCLUDED.disc_number,
                        preview_url = EXCLUDED.preview_url
                    """,
                    {
                        "id": song["id"],
                        "name": song["name"],
                        "album_id": song["album_id"],
                        "duration_ms": song["duration_ms"],
                        "spotify_uri": song["spotify_uri"],
                        "spotify_url": song["spotify_url"],
                        "popularity": song["popularity"],
                        "explicit": song["explicit"],
                        "track_number": song["track_number"],
                        "disc_number": song["disc_number"],
                        "preview_url": song["preview_url"],
                    },
                )

            # 6. insert song-artist relationships
            for song_id, artists in artist_song_map.items():
                for artist in artists:
                    await database.execute(
                        """
                        INSERT INTO song_artists (song_id, artist_id, list_position)
                        VALUES (:song_id, :artist_id, :position)
                        ON CONFLICT (song_id, artist_id) DO UPDATE SET
                            list_position = EXCLUDED.list_position
                        """,
                        {
                            "song_id": song_id,
                            "artist_id": artist["artist_id"],
                            "position": artist["position"],
                        },
                    )

            # 7. insert user-liked songs relationships
            for song_id, song in songs_map.items():
                try:
                    added_at_datetime = datetime.fromisoformat(
                        song["added_at"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    added_at_datetime = datetime.now(timezone.utc)

                await database.execute(
                    """
                    INSERT INTO user_liked_songs (user_id, song_id, liked_at)
                    VALUES (:user_id, :song_id, :liked_at)
                    ON CONFLICT (user_id, song_id) DO UPDATE SET
                        liked_at = EXCLUDED.liked_at
                    """,
                    {
                        "user_id": user_id,
                        "song_id": song_id,
                        "liked_at": added_at_datetime,
                    },
                )

        # update sync job as completed
        await database.execute(
            """
            UPDATE liked_songs_sync_jobs 
            SET status = 'completed', 
                completed_at = CURRENT_TIMESTAMP,
                progress = 1.0,
                songs_processed = :processed
            WHERE id = :job_id
            """,
            {"processed": processed, "job_id": job_id},
        )

        # update spotify credentials
        await database.execute(
            """
            UPDATE spotify_credentials 
            SET liked_songs_sync_status = 'completed',
                last_liked_songs_sync = CURRENT_TIMESTAMP
            WHERE user_id = :user_id
            """,
            {"user_id": user_id},
        )

    except Exception as e:
        # update sync job as failed
        error_message = str(e)
        await database.execute(
            """
            UPDATE liked_songs_sync_jobs 
            SET status = 'failed', 
                completed_at = CURRENT_TIMESTAMP,
                error = :error
            WHERE id = :job_id
            """,
            {"error": error_message, "job_id": job_id},
        )

        # update spotify credentials
        await database.execute(
            """
            UPDATE spotify_credentials 
            SET liked_songs_sync_status = 'failed'
            WHERE user_id = :user_id
            """,
            {"user_id": user_id},
        )

        print(f"Error syncing liked songs for user {user_id}: {error_message}")
        print(f"Exception traceback: {e}")


# endpoint to start syncing liked songs
@router.post("/sync", response_model=SyncStatus)
async def sync_liked_songs(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    # get spotify client
    try:
        sp = await get_spotify_client()(user)
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Spotify account not connected or invalid credentials",
        )

    # check if a sync is already in progress
    existing_job = await database.fetch_one(
        """
        SELECT * FROM liked_songs_sync_jobs
        WHERE user_id = :user_id AND status = 'running'
        ORDER BY started_at DESC LIMIT 1
        """,
        {"user_id": user.id},
    )

    if existing_job:
        # if a job is already running, return its status
        return {
            "is_syncing": True,
            "last_synced_at": existing_job["started_at"],
            "progress": existing_job["progress"],
            "total_songs": existing_job["songs_total"],
            "processed_songs": existing_job["songs_processed"],
        }

    # check when the last successful sync was
    last_sync = await database.fetch_one(
        """
        SELECT last_liked_songs_sync 
        FROM spotify_credentials
        WHERE user_id = :user_id
        """,
        {"user_id": user.id},
    )

    # if synced in the last hour, prevent new sync to avoid rate limiting
    if last_sync and last_sync["last_liked_songs_sync"]:
        last_sync_time = last_sync["last_liked_songs_sync"]
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

        if last_sync_time > one_hour_ago:
            raise HTTPException(
                status_code=429,
                detail="Please wait at least 1 hour between syncs to avoid rate limiting",
            )

    # start background task to sync liked songs
    background_tasks.add_task(sync_liked_songs_background, user.id, sp)

    # return initial status
    return {
        "is_syncing": True,
        "last_synced_at": None,
        "progress": 0,
        "total_songs": 0,
        "processed_songs": 0,
    }


# endpoint to get sync status
@router.get("/sync/status", response_model=SyncStatus)
async def get_sync_status(user: User = Depends(get_current_user)):
    # get the most recent sync job
    job = await database.fetch_one(
        """
        SELECT * FROM liked_songs_sync_jobs
        WHERE user_id = :user_id
        ORDER BY started_at DESC LIMIT 1
        """,
        {"user_id": user.id},
    )

    if not job:
        # no sync has been run yet
        return {
            "is_syncing": False,
            "last_synced_at": None,
            "progress": 0,
            "total_songs": 0,
            "processed_songs": 0,
        }

    # if progress is at or near 100% but status is still "running",
    # the job is likely complete but wasn't properly updated
    if (
        job["status"] == "running"
        and job["progress"] >= 0.99
        and job["songs_processed"] >= job["songs_total"]
    ):
        # auto-fix the status
        await database.execute(
            """
            UPDATE liked_songs_sync_jobs 
            SET status = 'completed', 
                completed_at = CURRENT_TIMESTAMP,
                progress = 1.0
            WHERE id = :job_id
            """,
            {"job_id": job["id"]},
        )

        # also update spotify credentials
        await database.execute(
            """
            UPDATE spotify_credentials 
            SET liked_songs_sync_status = 'completed',
                last_liked_songs_sync = CURRENT_TIMESTAMP
            WHERE user_id = :user_id
            """,
            {"user_id": user.id},
        )

        # update job in memory to reflect changes
        job = dict(job)
        job["status"] = "completed"
        job["progress"] = 1.0
        job["completed_at"] = datetime.now(timezone.utc)

    # get credentials for additional info
    creds = await database.fetch_one(
        """
        SELECT * FROM spotify_credentials
        WHERE user_id = :user_id
        """,
        {"user_id": user.id},
    )

    return {
        "is_syncing": job["status"] == "running",
        "last_synced_at": (
            job["completed_at"] if job["status"] != "running" else job["started_at"]
        ),
        "progress": job["progress"],
        "total_songs": job["songs_total"],
        "processed_songs": job["songs_processed"],
    }


# endpoint to get user's liked songs
@router.get("", response_model=List[LikedSong])
async def get_liked_songs(
    limit: int = 50, offset: int = 0, user: User = Depends(get_current_user)
):
    # check if user has synced liked songs
    creds = await database.fetch_one(
        """
        SELECT liked_songs_sync_status 
        FROM spotify_credentials
        WHERE user_id = :user_id
        """,
        {"user_id": user.id},
    )

    if not creds or creds["liked_songs_sync_status"] not in ["completed", "syncing"]:
        raise HTTPException(
            status_code=404,
            detail="Liked songs have not been synced yet. Please sync your liked songs first.",
        )

    # get liked songs
    songs = await database.fetch_all(
        """
        SELECT 
            s.id,
            s.name,
            uls.liked_at,
            s.duration_ms,
            s.spotify_uri,
            al.image_url as album_art_url,
            al.name as album_name,
            string_agg(a.name, ', ') as artist_names
        FROM user_liked_songs uls
        JOIN songs s ON uls.song_id = s.id
        JOIN albums al ON s.album_id = al.id
        JOIN song_artists sa ON s.id = sa.song_id
        JOIN artists a ON sa.artist_id = a.id
        WHERE uls.user_id = :user_id
        GROUP BY s.id, s.name, uls.liked_at, s.duration_ms, s.spotify_uri, al.image_url, al.name
        ORDER BY uls.liked_at DESC
        LIMIT :limit OFFSET :offset
        """,
        {"user_id": user.id, "limit": limit, "offset": offset},
    )

    return [
        {
            "id": song["id"],
            "name": song["name"],
            "artist": song["artist_names"],
            "album": song["album_name"],
            "duration_ms": song["duration_ms"],
            "album_art_url": song["album_art_url"],
            "liked_at": song["liked_at"],
        }
        for song in songs
    ]


# endpoint to get liked songs count
@router.get("/count")
async def get_liked_songs_count(user: User = Depends(get_current_user)):
    # get count from credentials
    creds = await database.fetch_one(
        """
        SELECT liked_songs_count 
        FROM spotify_credentials
        WHERE user_id = :user_id
        """,
        {"user_id": user.id},
    )

    if not creds:
        return {"count": 0}

    return {"count": creds["liked_songs_count"] or 0}


# helper function to check if we should auto-sync based on time
async def should_auto_sync_liked_songs(user_id: int) -> bool:
    """Check if we should automatically sync liked songs based on last sync time"""
    # get last sync time
    creds = await database.fetch_one(
        """
        SELECT last_liked_songs_sync, liked_songs_sync_status
        FROM spotify_credentials
        WHERE user_id = :user_id
        """,
        {"user_id": user_id},
    )

    if not creds:
        return False

    # if never synced or status indicates it needs update, sync
    if not creds["last_liked_songs_sync"] or creds["liked_songs_sync_status"] in [
        "not_started",
        "needs_update",
    ]:
        return True

    # if synced more than 24 hours ago, sync again
    last_sync = creds["last_liked_songs_sync"]
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)

    return last_sync < twenty_four_hours_ago


# add to the router to create a new endpoint for auto-sync
@router.get("/auto-sync")
async def auto_sync_liked_songs(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Automatically sync liked songs if needed based on last sync time"""
    # check if we should sync
    should_sync = await should_auto_sync_liked_songs(user.id)

    if not should_sync:
        return {"status": "no_sync_needed", "message": "No sync needed at this time"}

    # check if a sync is already in progress
    existing_job = await database.fetch_one(
        """
        SELECT * FROM liked_songs_sync_jobs
        WHERE user_id = :user_id AND status = 'running'
        """,
        {"user_id": user.id},
    )

    if existing_job:
        return {
            "status": "sync_in_progress",
            "message": "A sync is already in progress",
        }

    # get spotify client
    try:
        sp = await get_spotify_client()(user)
    except Exception as e:
        return {
            "status": "spotify_error",
            "message": "Failed to authenticate with Spotify",
        }

    # start background sync
    background_tasks.add_task(sync_liked_songs_background, user.id, sp)

    return {"status": "sync_started", "message": "Auto-sync has been started"}
