from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import spotipy
import asyncio
import time
import traceback

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
    current_operation: Optional[str] = None
    phase: int = 1  # phase 1: processing tracks, phase 2: artists, phase 3: albums
    total_phases: int = 3  # total number of phases


class LikedSong(BaseModel):
    id: str
    name: str
    artist: str
    album: str
    duration_ms: int
    album_art_url: Optional[str] = None
    liked_at: datetime
    is_shared: Optional[bool] = None


# background task to sync liked songs
async def sync_liked_songs_background(user_id: int, spotify_client: spotipy.Spotify):
    """
    sync a user's liked songs from Spotify in the background.
    uses efficient batch processing to handle large collections.
    """
    job_id = None
    try:
        # create a new sync job
        job_id = await create_sync_job(user_id)

        # update spotify credentials to show sync is in progress
        await update_spotify_credentials_status(user_id, "syncing")

        # 1: fetch and process all user's liked tracks
        await update_sync_job_status(job_id, "Fetching tracks from Spotify", 1, 3)

        (
            artists_map,
            albums_map,
            songs_map,
            artist_song_map,
            artist_album_map,
            artist_genre_map,
            processed,
            user_liked_songs_data,
        ) = await fetch_and_process_liked_tracks(user_id, spotify_client, job_id)

        # 2: process artists data with real information from Spotify
        total_artists = len(artists_map)
        await update_sync_job_status(
            job_id, f"Enriching {total_artists} artists data (Phase 2/3)", 2, 3
        )

        # begin phase 2 (artist enrichment)
        await update_sync_job_progress(job_id, 0.33, processed, 2, 3)

        # enrich artists data with incremental progress updates
        await enrich_artists_data_with_progress(
            artists_map,
            artist_genre_map,
            spotify_client,
            job_id,
        )

        # 3: process albums data with real information from Spotify
        total_albums = len(albums_map)
        await update_sync_job_status(
            job_id, f"Enriching {total_albums} albums data (Phase 3/3)", 3, 3
        )

        # begin phase 3 (album enrichment)
        await update_sync_job_progress(job_id, 0.66, processed, 3, 3)

        # enrich albums data with incremental progress updates
        await enrich_albums_data_with_progress(albums_map, spotify_client, job_id)

        # calculate total number of database operations for progress tracking
        total_operations = 6  # artists, albums, album-artists, genres, songs, song-artists, user-liked-songs
        current_operation = 0

        # 4: insert each data type in separate transactions to avoid cascading failures
        # insert artists
        try:
            current_operation += 1
            operations_progress = current_operation / total_operations
            await update_sync_job_progress(
                job_id, 0.9 + (operations_progress * 0.1), processed, 3, 3
            )
            await update_sync_job_status(
                job_id, f"Inserting {len(artists_map)} artists", 3, 3
            )
            await batch_insert_artists(artists_map)
        except Exception as e:
            print(f"error during artist insertion: {e}")
            # continue with next step

        # insert albums
        try:
            current_operation += 1
            operations_progress = current_operation / total_operations
            await update_sync_job_progress(
                job_id, 0.9 + (operations_progress * 0.1), processed, 3, 3
            )
            await update_sync_job_status(
                job_id, f"Inserting {len(albums_map)} albums", 3, 3
            )
            await batch_insert_albums(albums_map)
        except Exception as e:
            print(f"error during album insertion: {e}")
            # continue with next step

        # insert album-artist relationships
        try:
            current_operation += 1
            operations_progress = current_operation / total_operations
            await update_sync_job_progress(
                job_id, 0.9 + (operations_progress * 0.1), processed, 3, 3
            )
            await update_sync_job_status(
                job_id, f"Inserting album-artist relationships", 3, 3
            )
            await batch_insert_album_artists(artist_album_map)
        except Exception as e:
            print(f"error during album-artist relationship insertion: {e}")
            # continue with next step

        # process genres
        try:
            current_operation += 1
            operations_progress = current_operation / total_operations
            await update_sync_job_progress(
                job_id, 0.9 + (operations_progress * 0.1), processed, 3, 3
            )
            await update_sync_job_status(job_id, f"Processing genres", 3, 3)
            await process_artist_genres(artist_genre_map)
        except Exception as e:
            print(f"error during genre processing: {e}")
            # continue with next step

        # insert songs
        try:
            current_operation += 1
            operations_progress = current_operation / total_operations
            await update_sync_job_progress(
                job_id, 0.9 + (operations_progress * 0.1), processed, 3, 3
            )
            await update_sync_job_status(
                job_id, f"Inserting {len(songs_map)} songs", 3, 3
            )
            await batch_insert_songs(songs_map)
        except Exception as e:
            print(f"error during song insertion: {e}")
            # continue with next step

        # insert song-artist relationships
        try:
            current_operation += 1
            operations_progress = current_operation / total_operations
            await update_sync_job_progress(
                job_id, 0.9 + (operations_progress * 0.1), processed, 3, 3
            )
            await update_sync_job_status(
                job_id, "Inserting song-artist relationships", 3, 3
            )
            await batch_insert_song_artists(artist_song_map)
        except Exception as e:
            print(f"error during song-artist relationship insertion: {e}")
            # continue with next step

        # insert user liked songs
        try:
            current_operation += 1
            operations_progress = current_operation / total_operations
            await update_sync_job_progress(
                job_id, 0.9 + (operations_progress * 0.1), processed, 3, 3
            )
            await update_sync_job_status(
                job_id, f"Finalizing {processed} liked songs", 3, 3
            )
            await insert_user_liked_songs(user_id, songs_map, user_liked_songs_data)
        except Exception as e:
            print(f"error during user liked songs insertion: {e}")
            # continue to completion

        # only mark as complete after all operations are finished
        await update_sync_job_status(job_id, "Completing sync process", 3, 3)
        await update_sync_job_progress(job_id, 0.99, processed, 3, 3)

        # mark job as completed
        await mark_sync_job_complete(job_id, processed)

        # update spotify credentials with completion status
        await update_spotify_credentials_status(
            user_id, "completed", update_last_sync=True
        )

    except Exception as e:
        # handle failure case
        await handle_sync_failure(job_id, user_id, e)


async def create_sync_job(user_id: int) -> int:
    """create a new sync job for tracking progress."""
    try:
        job_id = await database.execute(
            """
            INSERT INTO liked_songs_sync_jobs 
            (user_id, status, started_at, progress, current_operation, phase, total_phases) 
            VALUES (:user_id, 'running', CURRENT_TIMESTAMP, 0, 'Initializing', 1, 3)
            RETURNING id
            """,
            {"user_id": user_id},
        )
        return job_id
    except Exception as e:
        print(f"error creating sync job: {e}")
        raise HTTPException(
            status_code=500,
            detail="failed to create sync job",
        )


async def update_spotify_credentials_status(
    user_id: int, status: str, update_last_sync: bool = False
):
    """update the Spotify credentials table with sync status."""
    try:
        if update_last_sync:
            await database.execute(
                """
                UPDATE spotify_credentials 
                SET liked_songs_sync_status = :status,
                    last_liked_songs_sync = CURRENT_TIMESTAMP
                WHERE user_id = :user_id
                """,
                {"status": status, "user_id": user_id},
            )
        else:
            await database.execute(
                """
                UPDATE spotify_credentials 
                SET liked_songs_sync_status = :status
                WHERE user_id = :user_id
                """,
                {"status": status, "user_id": user_id},
            )
    except Exception as e:
        print(f"error updating spotify credentials: {e}")
        raise HTTPException(
            status_code=500,
            detail="failed to update spotify credentials",
        )


async def fetch_and_process_liked_tracks(
    user_id: int, spotify_client: spotipy.Spotify, job_id: int
) -> dict:
    """fetch liked tracks from Spotify and process them efficiently."""
    offset = 0
    limit = 50
    total = None
    processed = 0

    # data structures to collect all data for batch processing
    artists_map = {}
    albums_map = {}
    songs_map = {}
    artist_song_map = {}
    artist_album_map = {}
    artist_genre_map = {}

    # get existing database records to avoid duplicates
    existing_albums = await database.fetch_all("SELECT id FROM albums")
    existing_artists = await database.fetch_all("SELECT id FROM artists")
    existing_album_ids = set([album["id"] for album in existing_albums])
    existing_artist_ids = set([artist["id"] for artist in existing_artists])

    # get existing liked songs to avoid reprocessing
    existing_liked_songs = await database.fetch_all(
        """
        SELECT song_id FROM user_liked_songs
        WHERE user_id = :user_id
        """,
        {"user_id": user_id},
    )
    existing_liked_song_ids = set([song["song_id"] for song in existing_liked_songs])

    # track ids to add to user_liked_songs relation
    all_track_ids = []
    track_added_at_map = {}

    while total is None or offset < total:
        # get next batch of tracks
        results = spotify_client.current_user_saved_tracks(limit=limit, offset=offset)

        if total is None:
            total = results["total"]
            # update job and credentials with total count
            await update_sync_job_total(job_id, total)
            await update_credentials_total(user_id, total)

        # process the batch of tracks
        if not results["items"]:
            break

        for idx, item in enumerate(results["items"]):
            track = item["track"]
            added_at = item["added_at"]
            track_id = track["id"]

            # add to list of all track ids (for liked songs relation)
            all_track_ids.append(track_id)
            track_added_at_map[track_id] = added_at

            # skip processing if song is already in user_liked_songs
            # we still count it as processed for progress tracking
            if track_id in existing_liked_song_ids:
                processed += 1
                continue

            # process track's artists (only new ones)
            for i, artist in enumerate(track["artists"]):
                artist_id = artist["id"]

                # only add artist if not already in database or map
                if (
                    artist_id not in existing_artist_ids
                    and artist_id not in artists_map
                ):
                    artists_map[artist_id] = {
                        "id": artist_id,
                        "name": artist["name"],
                        "image_url": "https://via.placeholder.com/300",
                        "popularity": 0,
                    }

                # always create song-artist relationship
                if track_id not in artist_song_map:
                    artist_song_map[track_id] = []

                artist_song_map[track_id].append(
                    {
                        "song_id": track_id,
                        "artist_id": artist_id,
                        "list_position": i + 1,
                    }
                )

            # process track's album (only if not already in database)
            album_id = track["album"]["id"]
            adding_album = False
            if album_id not in existing_album_ids and album_id not in albums_map:
                adding_album = True
                # add album with data from track response
                albums_map[album_id] = {
                    "id": album_id,
                    "name": track["album"]["name"],
                    "image_url": (
                        track["album"]["images"][0]["url"]
                        if track["album"]["images"]
                        else "https://via.placeholder.com/300"
                    ),
                    "release_date": track["album"].get("release_date"),
                    "album_type": track["album"].get("album_type", "album"),
                    "total_tracks": track["album"].get("total_tracks", 0),
                    "popularity": 0,  # placeholder
                }

                # process album artists
                is_various_artists = False
                if track["album"]["artists"][0]["name"] == "Various Artists":
                    is_various_artists = True

                if is_various_artists:
                    # for "various artists" albums, use the track artists
                    for i, track_artist in enumerate(track["artists"]):
                        artist_id = track_artist["id"]

                        # make sure artist exists in map if it's new
                        if (
                            artist_id not in existing_artist_ids
                            and artist_id not in artists_map
                        ):
                            artists_map[artist_id] = {
                                "id": artist_id,
                                "name": track_artist["name"],
                                "image_url": "https://via.placeholder.com/300",
                                "popularity": 0,
                            }

                        # add to album-artist map
                        key = f"{album_id}_{artist_id}"
                        if key not in artist_album_map:
                            artist_album_map[key] = {
                                "album_id": album_id,
                                "artist_id": artist_id,
                                "list_position": i,
                            }
                else:
                    # normal album processing
                    for i, album_artist in enumerate(track["album"]["artists"]):
                        artist_id = album_artist["id"]

                        # make sure artist exists in map if it's new
                        if (
                            artist_id not in existing_artist_ids
                            and artist_id not in artists_map
                        ):
                            artists_map[artist_id] = {
                                "id": artist_id,
                                "name": album_artist["name"],
                                "image_url": "https://via.placeholder.com/300",
                                "popularity": 0,
                            }

                        # add to album-artist map (no duplicate check needed for normal albums)
                        key = f"{album_id}_{artist_id}"
                        if key not in artist_album_map:
                            artist_album_map[key] = {
                                "album_id": album_id,
                                "artist_id": artist_id,
                                "list_position": i,
                            }
            elif (
                track["album"]["artists"][0]["name"] == "Various Artists"
                and not adding_album
            ):
                # for "various artists" albums, use the track artists
                # keep track of the next position to use
                next_position = 1
                for i, track_artist in enumerate(track["artists"]):
                    artist_id = track_artist["id"]

                    # make sure artist exists in map if it's new
                    if (
                        artist_id not in existing_artist_ids
                        and artist_id not in artists_map
                    ):
                        artists_map[artist_id] = {
                            "id": artist_id,
                            "name": track_artist["name"],
                            "image_url": "https://via.placeholder.com/300",
                            "popularity": 0,
                        }

                    # check if this artist is already in the album_artist_map for this album
                    artist_already_added = False
                    max_position = 0
                    for key, relation in artist_album_map.items():
                        if relation["album_id"] == album_id:
                            max_position = max(max_position, relation["list_position"])
                            if relation["artist_id"] == artist_id:
                                artist_already_added = True

                    # update next_position based on the max position found
                    next_position = max(next_position, max_position + 1)

                    # only add if not already in the map
                    if not artist_already_added:
                        # add to album-artist map
                        key = f"{album_id}_{artist_id}"
                        if key not in artist_album_map:
                            artist_album_map[key] = {
                                "album_id": album_id,
                                "artist_id": artist_id,
                                "list_position": next_position,
                            }
                            # increment position for next artist
                            next_position += 1
            # add song data if not already in liked songs
            songs_map[track_id] = {
                "id": track_id,
                "name": track["name"],
                "album_id": track["album"]["id"],
                "duration_ms": track["duration_ms"],
                "spotify_uri": track["uri"],
                "spotify_url": track["external_urls"].get("spotify", ""),
                "popularity": track.get("popularity", 0),
                "explicit": track.get("explicit", False),
                "track_number": track.get("track_number", 0),
                "disc_number": track.get("disc_number", 0),
                "added_at": added_at,
            }

            processed += 1

        # update progress - scale to first 33% of overall process
        progress = (processed / total) * 0.33 if total > 0 else 0
        await update_sync_job_progress(job_id, progress, processed, 1, 3)

        # move to next batch
        offset += limit

        # add a small delay to prevent rate limiting
        await asyncio.sleep(0.5)

    # get existing songs to avoid inserting duplicates
    if all_track_ids:
        existing_songs = await database.fetch_all(
            "SELECT id FROM songs WHERE id = ANY(:track_ids)",
            {"track_ids": all_track_ids},
        )
        existing_song_ids = set([song["id"] for song in existing_songs])

        # remove songs that already exist from songs_map
        songs_map = {k: v for k, v in songs_map.items() if k not in existing_song_ids}

    # prepare data for user_liked_songs relation (including existing songs)
    user_liked_songs_data = {}
    for track_id in all_track_ids:
        if track_id not in existing_liked_song_ids:
            user_liked_songs_data[track_id] = {
                "id": track_id,
                "added_at": track_added_at_map.get(track_id),
            }

    return (
        artists_map,
        albums_map,
        songs_map,
        artist_song_map,
        artist_album_map,
        artist_genre_map,
        processed,
        user_liked_songs_data,
    )


async def process_track_artists(track, position, artists_map, artist_song_map):
    """process a track's artists and update relevant data structures."""
    track_id = track["id"]

    for idx, artist in enumerate(track["artists"]):
        artist_id = artist["id"]

        # add artist to map with placeholder data (to be enriched later)
        artists_map[artist_id] = {
            "id": artist_id,
            "name": artist["name"],
            "image_url": "https://via.placeholder.com/300",
            "popularity": 0,
        }

        # create artist-song relationship
        if track_id not in artist_song_map:
            artist_song_map[track_id] = []

        artist_song_map[track_id].append(
            {
                "song_id": track_id,
                "artist_id": artist_id,
                "list_position": idx,
            }
        )


async def process_track_album(track, albums_map, artists_map, artist_album_map):
    """process a track's album and its artists."""
    album = track["album"]
    album_id = album["id"]

    # add album with data from track response
    albums_map[album_id] = {
        "id": album_id,
        "name": album["name"],
        "image_url": (
            album["images"][0]["url"]
            if album["images"]
            else "https://via.placeholder.com/300"
        ),
        "release_date": album.get("release_date"),
        "album_type": album.get("album_type", "album"),
        "total_tracks": album.get("total_tracks", 0),
        "popularity": 0,  # placeholder
    }

    # process album artists
    for idx, artist in enumerate(album["artists"]):
        artist_id = artist["id"]

        # make sure artist exists in map
        if artist_id not in artists_map:
            artists_map[artist_id] = {
                "id": artist_id,
                "name": artist["name"],
                "image_url": "https://via.placeholder.com/300",
                "popularity": 0,
            }

        # add to album-artist map
        key = f"{album_id}_{artist_id}"
        if key not in artist_album_map:
            artist_album_map[key] = {
                "album_id": album_id,
                "artist_id": artist_id,
                "list_position": idx,
            }


async def update_sync_job_total(job_id: int, total: int):
    """update the sync job with the total number of songs."""
    try:
        await database.execute(
            """
            UPDATE liked_songs_sync_jobs 
            SET songs_total = :total 
            WHERE id = :job_id
            """,
            {"total": total, "job_id": job_id},
        )
    except Exception as e:
        print(f"error updating sync job total: {e}")
        raise HTTPException(
            status_code=500,
            detail="failed to update sync job",
        )


async def update_credentials_total(user_id: int, total: int):
    """update the spotify credentials with the total number of liked songs."""
    try:
        await database.execute(
            """
            UPDATE spotify_credentials 
            SET liked_songs_count = :total 
            WHERE user_id = :user_id
            """,
            {"total": total, "user_id": user_id},
        )
    except Exception as e:
        print(f"error updating spotify credentials total: {e}")
        raise HTTPException(
            status_code=500,
            detail="failed to update spotify credentials",
        )


async def update_sync_job_progress(
    job_id: int, progress: float, processed: int, phase: int = 1, total_phases: int = 3
):
    """update the sync job with the current progress."""
    if not job_id:
        return

    try:
        # ensure progress is capped at 1.0 (100%)
        progress = min(progress, 1.0)

        await database.execute(
            """
            UPDATE liked_songs_sync_jobs 
            SET progress = :progress, songs_processed = :processed, phase = :phase, total_phases = :total_phases 
            WHERE id = :job_id
            """,
            {
                "progress": progress,
                "processed": processed,
                "phase": phase,
                "total_phases": total_phases,
                "job_id": job_id,
            },
        )
    except Exception as e:
        print(f"error updating sync job progress: {e}")
        # don't raise exception - just log the error and continue


async def enrich_artists_data_with_progress(
    artists_map, artist_genre_map, spotify_client, job_id
):
    """fetch detailed artist information from Spotify in batches with progress updates."""
    artist_ids = list(artists_map.keys())
    total_artists = len(artist_ids)

    if total_artists == 0:
        return

    # process artists in batches to avoid rate limiting
    batch_size = 50
    batches = [
        artist_ids[i : i + batch_size] for i in range(0, total_artists, batch_size)
    ]
    total_batches = len(batches)

    for batch_idx, batch in enumerate(batches):
        # update progress (from 33% to 66% during phase 2)
        progress = 0.33 + ((batch_idx / total_batches) * 0.33)
        await update_sync_job_progress(job_id, progress, 0, 2, 3)

        # update the operation display
        remaining = total_artists - (batch_idx * batch_size)
        await update_sync_job_status(
            job_id, f"Enriching {remaining} remaining artists data (Phase 2/3)", 2, 3
        )

        # add a small delay between batches to prevent rate limiting
        if batch_idx > 0:
            await asyncio.sleep(1.0)

        try:
            artist_data = spotify_client.artists(batch)

            for artist in artist_data["artists"]:
                if artist["id"] in artists_map:
                    # update artist with real data
                    artists_map[artist["id"]]["popularity"] = artist.get(
                        "popularity", 0
                    )

                    # get the best image if available
                    if artist.get("images") and len(artist["images"]) > 0:
                        artists_map[artist["id"]]["image_url"] = artist["images"][0][
                            "url"
                        ]

                    # store genres
                    if artist.get("genres"):
                        artist_genre_map[artist["id"]] = set(artist["genres"])
        except Exception as e:
            print(f"error fetching artist batch: {str(e)}")
            # continue with next batch rather than failing the whole process


async def enrich_albums_data_with_progress(albums_map, spotify_client, job_id):
    """fetch detailed album information from Spotify in batches with progress updates."""
    album_ids = list(albums_map.keys())
    total_albums = len(album_ids)

    if total_albums == 0:
        return

    # process albums in batches to avoid rate limiting
    batch_size = 20  # spotify API allows up to 20 albums per request
    batches = [
        album_ids[i : i + batch_size] for i in range(0, total_albums, batch_size)
    ]
    total_batches = len(batches)

    for batch_idx, batch in enumerate(batches):
        # update progress (from 66% to 90% during phase 3)
        progress = 0.66 + ((batch_idx / total_batches) * 0.24)
        await update_sync_job_progress(job_id, progress, 0, 3, 3)

        # update the operation display
        remaining = total_albums - (batch_idx * batch_size)
        await update_sync_job_status(
            job_id, f"Enriching {remaining} remaining albums data (Phase 3/3)", 3, 3
        )

        # add a small delay between batches to prevent rate limiting
        if batch_idx > 0:
            await asyncio.sleep(1.0)

        # add retry logic for API calls
        max_retries = 3
        retry_count = 0
        success = False

        while retry_count < max_retries and not success:
            try:
                album_data = spotify_client.albums(batch, market="from_token")
                success = True

                if album_data and "albums" in album_data:
                    for album in album_data["albums"]:
                        if album and album["id"] in albums_map:
                            # update album with real data
                            albums_map[album["id"]]["popularity"] = album.get(
                                "popularity", 0
                            )

                            # get the best image if available
                            if album.get("images") and len(album["images"]) > 0:
                                albums_map[album["id"]]["image_url"] = album["images"][
                                    0
                                ]["url"]

                            # update release date if available
                            if album.get("release_date"):
                                albums_map[album["id"]]["release_date"] = (
                                    process_release_date(album["release_date"])
                                )

                            # update album type and total tracks
                            albums_map[album["id"]]["album_type"] = album.get(
                                "album_type", "album"
                            )
                            albums_map[album["id"]]["total_tracks"] = album.get(
                                "total_tracks", 0
                            )
            except Exception as e:
                retry_count += 1
                print(
                    f"Error fetching album batch (attempt {retry_count}/{max_retries}): {str(e)}"
                )

                # increase backoff time between retries
                if retry_count < max_retries:
                    # use longer backoff for timeout errors
                    if "timed out" in str(e).lower():
                        await asyncio.sleep(
                            4.0 * retry_count
                        )  # longer backoff for timeouts
                    else:
                        await asyncio.sleep(
                            2.0 * retry_count
                        )  # standard exponential backoff
                else:
                    print(f"Failed to fetch album batch after {max_retries} attempts")
                    # create placeholder data for failed albums
                    for album_id in batch:
                        if album_id in albums_map:
                            albums_map[album_id]["popularity"] = 0
                            # leave other fields as they were


def process_release_date(raw_date):
    """process a Spotify release date into a SQL-compatible format."""
    if not raw_date:
        return None

    # handle different spotify date formats
    date_parts = raw_date.split("-")
    if len(date_parts) == 3:  # full date: YYYY-MM-DD
        return f"'{raw_date}'::date"
    elif len(date_parts) == 2:  # year-month: YYYY-MM
        return f"'{raw_date}-01'::date"  # first day of month given
    elif len(date_parts) == 1 and date_parts[0].isdigit():  # year only: YYYY
        return f"'{raw_date}-01-01'::date"  # first day of year given
    return None


async def batch_insert_artists(artist_data_map):
    """insert artists in batch."""
    try:
        # if there are no artists to insert, return early
        if not artist_data_map:
            return

        artist_values = {}
        placeholders = []

        for i, (artist_id, artist_data) in enumerate(artist_data_map.items()):
            placeholders.append(
                f"(:artist_id_{i}, :artist_name_{i}, :artist_image_{i}, :artist_popularity_{i})"
            )
            artist_values[f"artist_id_{i}"] = artist_id
            artist_values[f"artist_name_{i}"] = artist_data["name"]
            artist_values[f"artist_image_{i}"] = artist_data["image_url"]
            artist_values[f"artist_popularity_{i}"] = artist_data["popularity"]

        # only run the query if we have placeholders
        if placeholders:
            artist_query = f"""
            INSERT INTO artists (id, name, image_url, popularity)
            VALUES {", ".join(placeholders)}
            ON CONFLICT (id) DO NOTHING
            """
            await database.execute(query=artist_query, values=artist_values)
    except Exception as e:
        print(f"Error batch inserting artists: {str(e)}")


async def batch_insert_albums(album_data_map):
    """insert albums in batch."""
    try:
        # if there are no albums to insert, return early
        if not album_data_map:
            return

        album_values = {}
        placeholders = []

        for i, (album_id, album_data) in enumerate(album_data_map.items()):
            # make sure the release_date has a valid value
            release_date = album_data.get("release_date")
            if not release_date:
                release_date = "NULL"

            placeholders.append(
                f"(:album_id_{i}, :album_name_{i}, :album_image_{i}, {release_date}, :album_popularity_{i}, :album_type_{i}, :album_total_tracks_{i})"
            )

            album_values[f"album_id_{i}"] = album_id
            album_values[f"album_name_{i}"] = album_data["name"]
            album_values[f"album_image_{i}"] = album_data["image_url"]
            album_values[f"album_popularity_{i}"] = album_data["popularity"]
            album_values[f"album_type_{i}"] = album_data["album_type"]
            album_values[f"album_total_tracks_{i}"] = album_data["total_tracks"]

        # only run the query if we have placeholders
        if placeholders:
            album_query = f"""
            INSERT INTO albums (id, name, image_url, release_date, popularity, album_type, total_tracks)
            VALUES {", ".join(placeholders)}
            ON CONFLICT (id) DO NOTHING
            """
            await database.execute(query=album_query, values=album_values)
    except Exception as e:
        print(f"Error batch inserting albums: {str(e)}")


async def batch_insert_album_artists(artist_album_map):
    """insert album-artist relationships in batch."""
    if not artist_album_map:
        return

    try:
        # collect all unique album IDs
        album_ids = set()
        for key, relation in artist_album_map.items():
            album_ids.add(relation["album_id"])

        # check for existing album-artist relationships to handle list positions correctly
        if album_ids:
            existing_relations = {}
            for album_id in album_ids:
                try:
                    # get max list_position for each album
                    result = await database.fetch_one(
                        """
                        SELECT album_id, MAX(list_position) as max_position
                        FROM album_artists
                        WHERE album_id = :album_id
                        GROUP BY album_id
                        """,
                        {"album_id": album_id},
                    )
                    if result:
                        existing_relations[album_id] = result["max_position"]
                except Exception as e:
                    print(f"error checking existing album-artist relations: {str(e)}")
                    # continue with next album

            # adjust list positions for albums with existing relationships
            adjusted_map = {}
            for key, relation in artist_album_map.items():
                album_id = relation["album_id"]
                artist_id = relation["artist_id"]
                position = relation["list_position"]

                new_key = f"{album_id}_{artist_id}"

                # if this album already has artists in the database
                if album_id in existing_relations:
                    max_position = existing_relations[album_id]
                    # adjust position to continue from max_position in the database
                    adjusted_map[new_key] = {
                        "album_id": album_id,
                        "artist_id": artist_id,
                        "list_position": max_position + 1 + position,
                    }
                else:
                    # start at position 1 (not 0) for a new album
                    adjusted_map[new_key] = {
                        "album_id": album_id,
                        "artist_id": artist_id,
                        "list_position": position + 1,
                    }

            # replace original map with adjusted map
            artist_album_map = adjusted_map

        # process in smaller batches to handle large collections
        batch_size = 500
        keys = list(artist_album_map.keys())
        batches = [keys[i : i + batch_size] for i in range(0, len(keys), batch_size)]

        for batch in batches:
            values = {}
            placeholders = []

            for i, key in enumerate(batch):
                relation = artist_album_map[key]
                placeholders.append(f"(:album_id_{i}, :artist_id_{i}, :position_{i})")
                values[f"album_id_{i}"] = relation["album_id"]
                values[f"artist_id_{i}"] = relation["artist_id"]
                values[f"position_{i}"] = relation["list_position"]

            query = f"""
            INSERT INTO album_artists (album_id, artist_id, list_position)
            VALUES {", ".join(placeholders)}
            ON CONFLICT (album_id, artist_id) DO NOTHING
            """
            await database.execute(query=query, values=values)
    except Exception as e:
        print(f"error batch inserting album artists: {str(e)}")
        # continue with next operation rather than failing everything


async def process_artist_genres(artist_genre_map):
    """process artist genres and insert them efficiently."""
    if not artist_genre_map:
        return

    try:
        # get all unique genres
        unique_genres = list(
            set(genre for genres in artist_genre_map.values() for genre in genres)
        )

        # batch insert any new genres one at a time to avoid transaction abort
        for genre in unique_genres:
            try:
                # use individual transactions to avoid cascading failures
                await database.execute(
                    """
                    INSERT INTO genres (name)
                    VALUES (:genre_name)
                    ON CONFLICT (name) DO NOTHING
                    """,
                    {"genre_name": genre},
                )
            except Exception as e:
                print(f"error inserting genre '{genre}': {e}")
                # continue with next genre

        # fetch all inserted genre IDs
        try:
            genre_id_rows = await database.fetch_all(
                """
                SELECT name, id 
                FROM genres 
                WHERE name = ANY(:names)
                """,
                {"names": unique_genres},
            )

            # create mapping of genre name to ID
            genre_id_map = {row["name"]: row["id"] for row in genre_id_rows}

            # insert artist-genre relationships in smaller batches
            for artist_id, genres in artist_genre_map.items():
                try:
                    artist_genres = []
                    for genre in genres:
                        genre_id = genre_id_map.get(genre)
                        if genre_id:
                            artist_genres.append(
                                {"artist_id": artist_id, "genre_id": genre_id}
                            )

                    if artist_genres:
                        query = "INSERT INTO artist_genres (artist_id, genre_id) VALUES (:artist_id, :genre_id) ON CONFLICT (artist_id, genre_id) DO NOTHING"
                        await database.execute_many(query=query, values=artist_genres)
                except Exception as e:
                    print(f"error inserting genres for artist {artist_id}: {str(e)}")
                    # continue with next artist
        except Exception as e:
            print(f"error fetching genre IDs: {str(e)}")
    except Exception as e:
        print(f"error processing artist genres: {str(e)}")


async def batch_insert_songs(songs_map):
    """insert songs in batch."""
    if not songs_map:
        return

    try:
        # process in smaller batches to handle large collections
        batch_size = 100
        song_ids = list(songs_map.keys())
        batches = [
            song_ids[i : i + batch_size] for i in range(0, len(song_ids), batch_size)
        ]

        for batch in batches:
            values = {}
            placeholders = []

            for i, song_id in enumerate(batch):
                song = songs_map[song_id]
                placeholders.append(
                    f"(:id_{i}, :name_{i}, :album_id_{i}, :duration_ms_{i}, "
                    f":spotify_uri_{i}, :spotify_url_{i}, :popularity_{i}, "
                    f":explicit_{i}, :track_number_{i}, :disc_number_{i})"
                )

                values[f"id_{i}"] = song["id"]
                values[f"name_{i}"] = song["name"]
                values[f"album_id_{i}"] = song["album_id"]
                values[f"duration_ms_{i}"] = song["duration_ms"]
                values[f"spotify_uri_{i}"] = song["spotify_uri"]
                values[f"spotify_url_{i}"] = song["spotify_url"]
                values[f"popularity_{i}"] = song["popularity"]
                values[f"explicit_{i}"] = song["explicit"]
                values[f"track_number_{i}"] = song["track_number"]
                values[f"disc_number_{i}"] = song["disc_number"]

            query = f"""
            INSERT INTO songs (
                id, name, album_id, duration_ms, spotify_uri, spotify_url, 
                popularity, explicit, track_number, disc_number
            )
            VALUES {", ".join(placeholders)}
            ON CONFLICT (id) DO NOTHING
            """
            await database.execute(query=query, values=values)
    except Exception as e:
        print(f"error batch inserting songs: {str(e)}")


async def batch_insert_song_artists(artist_song_map):
    """insert song-artist relationships in batch."""
    if not artist_song_map:
        return

    try:
        # process songs in smaller batches
        batch_size = 500
        song_ids = list(artist_song_map.keys())

        for song_batch_idx in range(0, len(song_ids), batch_size):
            song_batch = song_ids[song_batch_idx : song_batch_idx + batch_size]

            # collect all relationships
            relationships = []
            for song_id in song_batch:
                relationships.extend(artist_song_map[song_id])

            # process relationships in batches
            for rel_batch_idx in range(0, len(relationships), batch_size):
                rel_batch = relationships[rel_batch_idx : rel_batch_idx + batch_size]

                values = {}
                placeholders = []

                for i, rel in enumerate(rel_batch):
                    placeholders.append(
                        f"(:song_id_{i}, :artist_id_{i}, :position_{i})"
                    )
                    values[f"song_id_{i}"] = rel["song_id"]
                    values[f"artist_id_{i}"] = rel["artist_id"]
                    values[f"position_{i}"] = rel["list_position"]

                query = f"""
                INSERT INTO song_artists (song_id, artist_id, list_position)
                VALUES {", ".join(placeholders)}
                ON CONFLICT (song_id, artist_id) DO NOTHING
                """
                await database.execute(query=query, values=values)
    except Exception as e:
        print(f"error batch inserting song artists: {str(e)}")


async def insert_user_liked_songs(user_id, songs_map, user_liked_songs_data):
    """insert user liked songs in batch."""
    if not user_liked_songs_data:
        return

    try:
        # process in smaller batches
        batch_size = 100
        song_ids = list(user_liked_songs_data.keys())
        batches = [
            song_ids[i : i + batch_size] for i in range(0, len(song_ids), batch_size)
        ]

        for batch in batches:
            values = {}
            placeholders = []

            for i, song_id in enumerate(batch):
                # convert added_at to datetime
                added_at = user_liked_songs_data[song_id]["added_at"]
                try:
                    added_at_datetime = datetime.fromisoformat(
                        added_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    added_at_datetime = datetime.now(timezone.utc)

                placeholders.append(f"(:user_id_{i}, :song_id_{i}, :liked_at_{i})")
                values[f"user_id_{i}"] = user_id
                values[f"song_id_{i}"] = song_id
                values[f"liked_at_{i}"] = added_at_datetime

            query = f"""
            INSERT INTO user_liked_songs (user_id, song_id, liked_at)
            VALUES {", ".join(placeholders)}
            ON CONFLICT (user_id, song_id) DO NOTHING
            """
            await database.execute(query=query, values=values)
    except Exception as e:
        print(f"error inserting user liked songs: {str(e)}")
        raise e


async def mark_sync_job_complete(job_id: int, total_processed: int):
    """mark a sync job as completed and update progress."""
    try:
        await database.execute(
            """
            UPDATE liked_songs_sync_jobs 
            SET status = 'completed', 
                completed_at = CURRENT_TIMESTAMP, 
                progress = 1.0,
                songs_processed = :processed,
                current_operation = 'Complete'
            WHERE id = :job_id
            """,
            {"job_id": job_id, "processed": total_processed},
        )
    except Exception as e:
        print(f"error marking sync job complete: {e}")


async def handle_sync_failure(job_id: int, user_id: int, error: Exception):
    """handle a failure in the sync process."""
    try:
        error_message = str(error)
        exception_traceback = traceback.format_exc()
        print(f"error syncing liked songs for user {user_id}: {error_message}")
        print(f"exception traceback: {exception_traceback}")

        # update sync job with error status
        if job_id:
            try:
                await database.execute(
                    """
                    UPDATE liked_songs_sync_jobs 
                    SET status = 'failed', 
                        completed_at = CURRENT_TIMESTAMP, 
                        error = :error
                    WHERE id = :job_id
                    """,
                    {"job_id": job_id, "error": error_message},
                )
            except Exception as e:
                print(f"error updating failure status: {e}")

        # update spotify credentials to show sync failed
        try:
            await database.execute(
                """
                UPDATE spotify_credentials 
                SET liked_songs_sync_status = 'failed'
                WHERE user_id = :user_id
                """,
                {"user_id": user_id},
            )
        except Exception as e:
            print(f"error updating spotify credentials failure status: {e}")
    except Exception as e:
        print(f"error handling sync failure: {e}")


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
        phase = existing_job["phase"] if "phase" in existing_job else 1
        total_phases = (
            existing_job["total_phases"] if "total_phases" in existing_job else 3
        )
        current_operation = (
            existing_job["current_operation"]
            if "current_operation" in existing_job
            else "Processing"
        )

        return {
            "is_syncing": True,
            "last_synced_at": existing_job["started_at"],
            "progress": existing_job["progress"],
            "total_songs": existing_job["songs_total"],
            "processed_songs": existing_job["songs_processed"],
            "current_operation": current_operation,
            "phase": phase,
            "total_phases": total_phases,
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
        "current_operation": "Initializing",
        "phase": 1,
        "total_phases": 3,
    }


# endpoint to get sync status
@router.get("/sync/status", response_model=SyncStatus)
async def get_sync_status(user: User = Depends(get_current_user)):
    try:
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
                "current_operation": None,
                "phase": 1,
                "total_phases": 3,
            }

        # only auto-fix if the job is marked as running but has BOTH 100% progress AND "Completing sync process" as current operation
        if (
            job["status"] == "running"
            and job["progress"] >= 0.99
            and job["songs_processed"] >= job["songs_total"]
            and "current_operation" in job
            and job["current_operation"] == "Completing sync process"
        ):
            # auto-fix the status
            await database.execute(
                """
                UPDATE liked_songs_sync_jobs 
                SET status = 'completed', 
                    completed_at = CURRENT_TIMESTAMP,
                    progress = 1.0,
                    current_operation = 'Complete'
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
            job["current_operation"] = "Complete"

        # get credentials for additional info
        creds = await database.fetch_one(
            """
            SELECT * FROM spotify_credentials
            WHERE user_id = :user_id
            """,
            {"user_id": user.id},
        )

        # get the current operation status, default to a generic message if not available
        current_operation = None
        if job and "current_operation" in job:
            current_operation = job["current_operation"]
        elif job and job["status"] == "running":
            current_operation = "Processing"

        # get phase information or use defaults
        phase = 1
        total_phases = 3
        if job:
            # check if phase field exists in the record (it might not in older records)
            phase = job["phase"] if "phase" in job else 1
            total_phases = job["total_phases"] if "total_phases" in job else 3

        return {
            "is_syncing": job["status"] == "running",
            "last_synced_at": (
                job["completed_at"] if job["status"] != "running" else job["started_at"]
            ),
            "progress": job["progress"],
            "total_songs": job["songs_total"],
            "processed_songs": job["songs_processed"],
            "current_operation": current_operation,
            "phase": phase,
            "total_phases": total_phases,
        }
    except Exception as e:
        # handle any errors by returning a default response
        print(f"error getting sync status: {e}")
        return {
            "is_syncing": False,
            "last_synced_at": None,
            "progress": 0,
            "total_songs": 0,
            "processed_songs": 0,
            "current_operation": "Error checking status",
            "phase": 1,
            "total_phases": 3,
        }


# endpoint to get user's liked songs
@router.get("", response_model=List[LikedSong])
async def get_liked_songs(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
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

    # base query for liked songs
    base_query = """
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
    """

    # add search filter if provided
    if search:
        base_query += """
            AND (
                LOWER(s.name) LIKE :search_term 
                OR LOWER(al.name) LIKE :search_term
                OR EXISTS (
                    SELECT 1 FROM song_artists sa2
                    JOIN artists a2 ON sa2.artist_id = a2.id
                    WHERE sa2.song_id = s.id AND LOWER(a2.name) LIKE :search_term
                )
            )
        """

    # complete the query with grouping, ordering, and pagination
    query = (
        base_query
        + """
        GROUP BY s.id, s.name, uls.liked_at, s.duration_ms, s.spotify_uri, al.image_url, al.name
        ORDER BY uls.liked_at DESC
        LIMIT :limit OFFSET :offset
        """
    )

    # prepare parameters
    params = {
        "user_id": user.id,
        "limit": limit,
        "offset": offset,
    }

    if search:
        params["search_term"] = f"%{search.lower()}%"

    # execute query
    songs = await database.fetch_all(query, params)

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
    """check if we should automatically sync liked songs based on last sync time"""
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
    """automatically sync liked songs if needed based on last sync time"""
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


# add function to update sync job status with current operation
async def update_sync_job_status(
    job_id: int, current_operation: str, phase: int = 1, total_phases: int = 3
):
    """update the sync job with the current operation being performed."""
    if not job_id:
        return

    try:
        await database.execute(
            """
            UPDATE liked_songs_sync_jobs 
            SET current_operation = :current_operation,
                phase = :phase,
                total_phases = :total_phases
            WHERE id = :job_id
            """,
            {
                "current_operation": current_operation,
                "job_id": job_id,
                "phase": phase,
                "total_phases": total_phases,
            },
        )
    except Exception as e:
        print(f"error updating sync job status: {e}")
        # don't raise exception - just log the error and continue


@router.get("/friends/{username}", response_model=List[LikedSong])
async def get_friend_liked_songs(
    username: str,
    limit: int = 50,
    offset: int = 0,
    filter_type: str = "all",  # "all", "shared", "unique"
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """
    get liked songs for a friend.

    filter_type:
    - "all": return all songs liked by the friend
    - "shared": return only songs that both the user and friend have liked
    - "unique": return only songs that the friend has liked but the user hasn't

    search:
    - Filter songs by title, artist, or album name
    """
    # check if the user is friends with the target user
    target_user = await database.fetch_one(
        "SELECT id FROM users WHERE username = :username",
        {"username": username},
    )

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # check if users are friends
    is_friend = await database.fetch_val(
        """
        SELECT 1
        FROM friendships
        WHERE (user_id = :user_id AND friend_id = :friend_id)
           OR (user_id = :friend_id AND friend_id = :user_id)
        """,
        {"user_id": user.id, "friend_id": target_user["id"]},
    )

    if not is_friend:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be friends with this user to view their liked songs",
        )

    # check if target user has synced their liked songs
    creds = await database.fetch_one(
        """
        SELECT liked_songs_sync_status 
        FROM spotify_credentials
        WHERE user_id = :user_id
        """,
        {"user_id": target_user["id"]},
    )

    if not creds or creds["liked_songs_sync_status"] not in ["completed", "syncing"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This user hasn't synced their liked songs yet",
        )

    # check if the friend actually has any liked songs
    liked_song_count = await database.fetch_val(
        """
        SELECT COUNT(*)
        FROM user_liked_songs
        WHERE user_id = :user_id
        """,
        {"user_id": target_user["id"]},
    )

    if not liked_song_count or liked_song_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This user doesn't have any liked songs",
        )

    # get current user's liked song IDs (for comparing)
    user_liked_songs = await database.fetch_all(
        "SELECT song_id FROM user_liked_songs WHERE user_id = :user_id",
        {"user_id": user.id},
    )
    user_liked_song_ids = {song["song_id"] for song in user_liked_songs}

    # base query for friend's liked songs
    base_query = """
        SELECT 
            s.id,
            s.name,
            uls.liked_at,
            s.duration_ms,
            s.spotify_uri,
            al.image_url as album_art_url,
            al.name as album_name,
            string_agg(a.name, ', ') as artist_names,
            CASE 
                WHEN s.id IN (
                    SELECT song_id 
                    FROM user_liked_songs 
                    WHERE user_id = :current_user_id
                ) THEN true
                ELSE false
            END as is_shared
        FROM user_liked_songs uls
        JOIN songs s ON uls.song_id = s.id
        JOIN albums al ON s.album_id = al.id
        JOIN song_artists sa ON s.id = sa.song_id
        JOIN artists a ON sa.artist_id = a.id
        WHERE uls.user_id = :friend_id
    """

    # add filtering based on shared status
    if filter_type == "shared":
        base_query += " AND s.id IN (SELECT song_id FROM user_liked_songs WHERE user_id = :current_user_id)"
    elif filter_type == "unique":
        base_query += " AND s.id NOT IN (SELECT song_id FROM user_liked_songs WHERE user_id = :current_user_id)"

    # add search filter if provided
    if search:
        base_query += """
            AND (
                LOWER(s.name) LIKE :search_term 
                OR LOWER(al.name) LIKE :search_term
                OR EXISTS (
                    SELECT 1 FROM song_artists sa2
                    JOIN artists a2 ON sa2.artist_id = a2.id
                    WHERE sa2.song_id = s.id AND LOWER(a2.name) LIKE :search_term
                )
            )
        """

    # complete the query with grouping, ordering, and pagination
    query = (
        base_query
        + """
        GROUP BY s.id, s.name, uls.liked_at, s.duration_ms, s.spotify_uri, al.image_url, al.name
        ORDER BY uls.liked_at DESC
        LIMIT :limit OFFSET :offset
    """
    )

    # prepare parameters
    params = {
        "friend_id": target_user["id"],
        "current_user_id": user.id,
        "limit": limit,
        "offset": offset,
    }

    if search:
        params["search_term"] = f"%{search.lower()}%"

    # execute query
    songs = await database.fetch_all(query, params)

    return [
        {
            "id": song["id"],
            "name": song["name"],
            "artist": song["artist_names"],
            "album": song["album_name"],
            "duration_ms": song["duration_ms"],
            "album_art_url": song["album_art_url"],
            "liked_at": song["liked_at"],
            "is_shared": song["is_shared"],
        }
        for song in songs
    ]


# endpoint to get shared liked songs stats with a friend
@router.get("/friends/{username}/stats")
async def get_friend_liked_songs_stats(
    username: str,
    user: User = Depends(get_current_user),
):
    """get statistics about shared liked songs with a friend"""
    # check if the user is friends with the target user
    target_user = await database.fetch_one(
        "SELECT id FROM users WHERE username = :username",
        {"username": username},
    )

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # check if users are friends
    is_friend = await database.fetch_val(
        """
        SELECT 1
        FROM friendships
        WHERE (user_id = :user_id AND friend_id = :friend_id)
           OR (user_id = :friend_id AND friend_id = :user_id)
        """,
        {"user_id": user.id, "friend_id": target_user["id"]},
    )

    if not is_friend:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be friends with this user to view their liked songs",
        )

    # get count of friend's liked songs
    friend_count = await database.fetch_val(
        """
        SELECT COUNT(*) 
        FROM user_liked_songs 
        WHERE user_id = :user_id
        """,
        {"user_id": target_user["id"]},
    )

    # get count of shared liked songs
    shared_count = await database.fetch_val(
        """
        SELECT COUNT(*) 
        FROM user_liked_songs uf
        JOIN user_liked_songs uc ON uf.song_id = uc.song_id
        WHERE uf.user_id = :friend_id AND uc.user_id = :user_id
        """,
        {"friend_id": target_user["id"], "user_id": user.id},
    )

    # get count of user's liked songs
    user_count = await database.fetch_val(
        """
        SELECT COUNT(*) 
        FROM user_liked_songs 
        WHERE user_id = :user_id
        """,
        {"user_id": user.id},
    )

    return {
        "friend_likes_count": friend_count or 0,
        "shared_likes_count": shared_count or 0,
        "user_likes_count": user_count or 0,
        "friend_unique_count": (friend_count or 0) - (shared_count or 0),
        "compatibility_percentage": (
            round((shared_count or 0) / max((friend_count or 1), 1) * 100, 1)
            if friend_count
            else 0
        ),
    }
