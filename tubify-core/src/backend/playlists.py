from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
from auth import get_current_user, User
from database import database
from spotify_auth import get_spotify_client
import spotipy, os, json, random, string
import time
import asyncio
import httpx
from urllib.parse import quote_plus
from youtube import find_youtube_videos_for_playlist, find_and_add_youtube_videos


# create router
router = APIRouter(prefix="/api/playlists", tags=["playlists"])


# models
class SongBase(BaseModel):
    id: str
    name: str
    artist: str
    album: str
    duration_ms: int
    spotify_uri: str
    spotify_url: str
    album_art_url: Optional[str] = None
    artist_id: str
    album_id: str


class PlaylistCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = True
    spotify_playlist_id: Optional[str] = None
    image_url: Optional[str] = None


class PlaylistUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    spotify_playlist_id: Optional[str] = None
    image_url: Optional[str] = None


class Playlist(PlaylistCreate):
    id: int
    user_id: int
    public_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    song_count: Optional[int] = 0
    songs: Optional[List[dict]] = None

    class Config:
        from_attributes = True


class SongReorderRequest(BaseModel):
    song_ids: List[str]


# endpoints
@router.post("/", response_model=Playlist)
async def create_playlist(
    playlist: PlaylistCreate,
    user: User = Depends(get_current_user),
    sp: spotipy.Spotify = Depends(get_spotify_client),
):
    """Create a new playlist and optionally import songs from a Spotify playlist."""
    start_time = time.time()

    # if spotify playlist id is provided, get playlist info
    if playlist.spotify_playlist_id:
        try:
            sp_playlist = sp.playlist(playlist.spotify_playlist_id)

            # update playlist data from spotify
            playlist.name = sp_playlist["name"]
            playlist.description = sp_playlist["description"]

            # get image url if available
            if sp_playlist["images"]:
                playlist.image_url = sp_playlist["images"][0]["url"]
        except Exception as e:
            if os.getenv("DEV_MODE", "false").lower() == "true":
                print(f"failed to get spotify playlist: {e}")

    # generate a unique public_id for the playlist
    public_id = await generate_unique_public_id()

    # insert playlist into database
    playlist_id = await database.execute(
        """
        INSERT INTO playlists (
            user_id, name, description, is_public, 
            spotify_playlist_id, image_url, public_id
        )
        VALUES (
            :user_id, :name, :description, :is_public, 
            :spotify_playlist_id, :image_url, :public_id
        )
        RETURNING id
        """,
        values={
            "user_id": user.id,
            "name": playlist.name,
            "description": playlist.description,
            "is_public": playlist.is_public,
            "spotify_playlist_id": playlist.spotify_playlist_id,
            "image_url": playlist.image_url,
            "public_id": public_id,
        },
    )

    # if spotify playlist id is provided, import songs from spotify
    if playlist.spotify_playlist_id:
        try:
            await import_spotify_playlist(playlist_id, sp_playlist, sp)
            end_time = time.time()
            print(f"Playlist import finished in {end_time - start_time:.2f} seconds")
        except Exception as e:
            if os.getenv("DEV_MODE", "false").lower() == "true":
                print(f"failed to import songs from spotify playlist: {e}")
            # log the full traceback
            import traceback

            print(f"Exception traceback: {traceback.format_exc()}")

    return await get_playlist(public_id, user)


async def generate_unique_public_id():
    """Generate a unique public ID for a playlist."""
    max_attempts = 5
    attempt = 0

    while attempt < max_attempts:
        public_id = "".join(random.choices(string.ascii_letters + string.digits, k=22))

        # check if this public_id already exists
        existing = await database.fetch_one(
            "SELECT id FROM playlists WHERE public_id = :public_id",
            values={"public_id": public_id},
        )

        if not existing:
            return public_id

        attempt += 1

    # if we've reached max attempts, generate a longer id to reduce collision probability
    return "".join(random.choices(string.ascii_letters + string.digits, k=26))


async def import_spotify_playlist(playlist_id, sp_playlist, sp):
    """Import songs from a Spotify playlist into a Tubify playlist."""

    # prepare data structures for batch processing
    songs_to_insert = []
    album_artists_to_add_to_database = {}
    song_artists_to_add_to_database = {}
    artist_genre_map = {}
    artists_to_add_to_database = set()
    albums_to_add_to_database = set()
    album_artists = {}
    track_ids = []
    track_positions = {}

    # get existing database records to avoid duplicates
    existing_albums = await database.fetch_all("SELECT id FROM albums")
    existing_artists = await database.fetch_all("SELECT id FROM artists")
    artist_ids = set([artist["id"] for artist in existing_artists])
    album_ids = set([album["id"] for album in existing_albums])

    # extract tracks from the spotify playlist
    (
        artist_ids,
        album_ids,
        songs_to_insert,
        artists_to_add_to_database,
        albums_to_add_to_database,
        album_artists,
        song_artists_to_add_to_database,
        track_ids,
        track_positions,
    ) = await extract_tracks_from_spotify_playlist(
        sp_playlist,
        sp,
        artist_ids,
        album_ids,
        songs_to_insert,
        artists_to_add_to_database,
        albums_to_add_to_database,
        album_artists,
        song_artists_to_add_to_database,
        track_ids,
        track_positions,
    )

    # keep track of all songs to add to the playlist
    all_playlist_song_ids = [song["id"] for song in songs_to_insert]

    # get all existing songs to avoid duplicates
    existing_songs = await database.fetch_all(
        "SELECT id FROM songs WHERE id = ANY(:spotify_ids)",
        values={"spotify_ids": track_ids},
    )
    existing_song_map = {song["id"]: song["id"] for song in existing_songs}
    existing_spotify_ids = set(existing_song_map.keys())

    # filter out songs that already exist
    new_songs = [
        song for song in songs_to_insert if song["id"] not in existing_spotify_ids
    ]

    # process albums in batches
    new_album_ids = list(albums_to_add_to_database)
    album_data_map = await process_albums_in_batches(
        new_album_ids,
        sp,
        album_artists,
        artist_ids,
        artists_to_add_to_database,
        album_artists_to_add_to_database,
    )

    # process artists in batches
    new_artist_ids = list(artists_to_add_to_database)
    artist_data_map, inserted_artist_ids = await process_artists_in_batches(
        new_artist_ids, sp, artist_genre_map
    )

    # get all valid artist IDs to use for relations
    valid_artist_ids = await get_valid_artist_ids(artist_ids, inserted_artist_ids)

    # filter relationships to only include valid artists
    album_artists_to_add_to_database = filter_album_artists(
        album_artists_to_add_to_database, valid_artist_ids
    )
    song_artists_to_add_to_database = filter_song_artists(
        song_artists_to_add_to_database, valid_artist_ids
    )

    # insert all data in the right order
    if album_data_map:
        await batch_insert_albums(album_data_map)

    if artist_data_map:
        await batch_insert_artists(artist_data_map)

    if new_songs:
        await batch_insert_songs(new_songs, existing_song_map)

    if song_artists_to_add_to_database:
        await batch_insert_song_artists(song_artists_to_add_to_database)

    if album_artists_to_add_to_database:
        await batch_insert_album_artists(album_artists_to_add_to_database)

    if artist_genre_map:
        await process_artist_genres(artist_genre_map)

    # finally, add songs to the playlist
    await add_songs_to_playlist(playlist_id, all_playlist_song_ids, track_positions)

    # find and add YouTube videos for each song
    # doing this in the background to avoid blocking the request
    asyncio.create_task(
        find_youtube_videos_for_playlist(playlist_id, all_playlist_song_ids)
    )

    return True


async def extract_tracks_from_spotify_playlist(
    sp_playlist,
    sp,
    artist_ids,
    album_ids,
    songs_to_insert,
    artists_to_add_to_database,
    albums_to_add_to_database,
    album_artists,
    song_artists_to_add_to_database,
    track_ids,
    track_positions,
):
    """Extract track data from a Spotify playlist."""
    position = 0
    tracks = sp_playlist["tracks"]
    total_tracks = tracks.get("total", 0)

    while True:
        for item in tracks["items"]:
            if item["track"]:
                track = item["track"]
                track_ids.append(track["id"])
                track_positions[track["id"]] = position
                position += 1
                track_id = track["id"]

                # process track artists
                for i in range(len(track["artists"])):
                    artist_id = track["artists"][i]["id"]
                    if artist_id not in artist_ids:
                        artist_ids.add(artist_id)
                        artists_to_add_to_database.add(artist_id)

                    key = f"{track_id}_{i}"
                    if key not in song_artists_to_add_to_database:
                        song_artists_to_add_to_database[key] = {
                            "song_id": track_id,
                            "artist_id": artist_id,
                            "list_position": i,
                        }

                # process album
                album_id = track["album"]["id"]
                if album_id not in album_ids:
                    album_ids.add(album_id)
                    albums_to_add_to_database.add(album_id)

                    # handle "Various Artists" albums
                    if (
                        track["album"]["artists"][0]["name"].lower()
                        == "various artists"
                    ):
                        album_artists[album_id] = track["artists"]
                elif track["album"]["artists"][0]["name"].lower() == "various artists":
                    album_artists[album_id] = track["artists"]

                # add song to insert list
                songs_to_insert.append(
                    {
                        "id": track["id"],
                        "name": track["name"],
                        "album_id": track["album"]["id"],
                        "duration_ms": track["duration_ms"],
                        "spotify_uri": track["uri"],
                        "spotify_url": track["external_urls"]["spotify"],
                        "popularity": track["popularity"],
                        "explicit": track["explicit"],
                        "track_number": track["track_number"],
                        "disc_number": track["disc_number"],
                    }
                )

        # handle pagination if there are more tracks
        if tracks["next"]:
            tracks = sp.next(tracks)
        else:
            break

    return (
        artist_ids,
        album_ids,
        songs_to_insert,
        artists_to_add_to_database,
        albums_to_add_to_database,
        album_artists,
        song_artists_to_add_to_database,
        track_ids,
        track_positions,
    )


async def process_albums_in_batches(
    new_album_ids,
    sp,
    album_artists,
    artist_ids,
    artists_to_add_to_database,
    album_artists_to_add_to_database,
):
    """Process albums in batches to avoid rate limiting."""
    if not new_album_ids:
        return {}

    album_data_map = {}
    batch_size = 20
    album_batches = [
        new_album_ids[i : i + batch_size]
        for i in range(0, len(new_album_ids), batch_size)
    ]

    for batch_idx, album_batch in enumerate(album_batches):
        # add a small delay between batch requests to avoid rate limiting
        if batch_idx > 0:
            await asyncio.sleep(1.0)  # 1 second delay between batches

        try:
            # get several albums in a single API call
            albums_data = sp.albums(album_batch)

            if albums_data and "albums" in albums_data:
                for album_data in albums_data["albums"]:
                    if album_data:
                        album_id = album_data["id"]
                        raw_date = album_data["release_date"]

                        # check if this is a "Various Artists" album
                        is_various_artists_album = False
                        for album_artist in album_data["artists"]:
                            if album_artist["name"].lower() == "various artists":
                                is_various_artists_album = True
                                break

                        # process album artists
                        if is_various_artists_album:
                            # for "Various Artists" albums, use the track artists instead
                            for i, track_artist in enumerate(album_artists[album_id]):
                                await process_album_artist(
                                    album_id,
                                    track_artist["id"],
                                    i,
                                    artist_ids,
                                    artists_to_add_to_database,
                                    album_artists_to_add_to_database,
                                )
                        else:
                            # normal album processing
                            for i in range(len(album_data["artists"])):
                                await process_album_artist(
                                    album_id,
                                    album_data["artists"][i]["id"],
                                    i,
                                    artist_ids,
                                    artists_to_add_to_database,
                                    album_artists_to_add_to_database,
                                )

                        # process release date
                        release_date = process_release_date(raw_date)

                        # store album data
                        album_data_map[album_id] = {
                            "id": album_id,
                            "name": album_data["name"],
                            "image_url": (
                                album_data["images"][0]["url"]
                                if album_data["images"]
                                else "https://via.placeholder.com/300"
                            ),
                            "release_date": release_date,
                            "popularity": album_data["popularity"],
                            "album_type": album_data["album_type"],
                            "total_tracks": album_data["total_tracks"],
                        }
        except Exception as e:
            print(f"Error fetching album batch: {str(e)}")
            # add fallback for problematic albums
            for album_id in album_batch:
                if album_id not in album_data_map:
                    album_data_map[album_id] = {
                        "id": album_id,
                        "name": "Unknown Album",
                        "image_url": "https://via.placeholder.com/300",
                        "release_date": None,
                        "popularity": 0,
                        "album_type": "album",
                        "total_tracks": 0,
                    }
    return album_data_map


async def process_album_artist(
    album_id,
    artist_id,
    position,
    artist_ids,
    artists_to_add_to_database,
    album_artists_to_add_to_database,
):
    """Process a single album artist relationship."""
    if artist_id not in artist_ids:
        artist_ids.add(artist_id)
        artists_to_add_to_database.add(artist_id)

    key = f"{album_id}_{artist_id}"
    if key not in album_artists_to_add_to_database:
        album_artists_to_add_to_database[key] = {
            "album_id": album_id,
            "artist_id": artist_id,
            "list_position": position,
        }


async def process_album_artist_various_artists(
    album_id,
    artist_id,
    artist_ids,
    artists_to_add_to_database,
    album_artists_to_add_to_database,
):
    """Process a single album artist relationship for "Various Artists" albums."""
    if artist_id not in artist_ids:
        artist_ids.add(artist_id)
        artists_to_add_to_database.add(artist_id)

    # check if this artist is already in the album_artists_to_add_to_database for this album
    for existing_key, data in album_artists_to_add_to_database.items():
        if data["album_id"] == album_id and data["artist_id"] == artist_id:
            # artist already added for this album
            return

    # check if this artist is already in the database for this album
    existing_relation = await database.fetch_one(
        """
        SELECT list_position 
        FROM album_artists 
        WHERE album_id = :album_id AND artist_id = :artist_id
        """,
        {"album_id": album_id, "artist_id": artist_id},
    )

    if existing_relation:
        # artist already exists in this album in the database
        return

    # find highest listed position for album's artists
    position = await database.fetch_val(
        "SELECT MAX(list_position) FROM album_artists WHERE album_id = :album_id",
        {"album_id": album_id},
    )
    if position is None:
        position = 1
    else:
        position += 1

    # for various artists albums, also check the current mapping for this album
    # to avoid position collisions within the same processing batch
    for existing_key, data in album_artists_to_add_to_database.items():
        if data["album_id"] == album_id:
            position = max(position, data["list_position"] + 1)

    key = f"{album_id}_{artist_id}"
    album_artists_to_add_to_database[key] = {
        "album_id": album_id,
        "artist_id": artist_id,
        "list_position": position,
    }


def process_release_date(raw_date):
    """Process a Spotify release date into a SQL-compatible format."""
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


async def process_artists_in_batches(new_artist_ids, sp, artist_genre_map):
    """Process artists in batches to avoid rate limiting."""
    if not new_artist_ids:
        return {}, set()

    artist_data_map = {}
    inserted_artist_ids = set()
    batch_size = 50
    artist_batches = [
        new_artist_ids[i : i + batch_size]
        for i in range(0, len(new_artist_ids), batch_size)
    ]

    try:
        for batch_idx, artist_batch in enumerate(artist_batches):
            # add a small delay between batch requests to avoid rate limiting
            if batch_idx > 0:
                await asyncio.sleep(1.0)  # 1 second delay between batches

            try:
                # get several artists in a single API call
                artists_data = sp.artists(artist_batch)

                if artists_data and "artists" in artists_data:
                    for artist_data in artists_data["artists"]:
                        if artist_data:
                            # store genres
                            artist_id = artist_data["id"]
                            if artist_data.get("genres"):
                                artist_genre_map[artist_id] = set(artist_data["genres"])

                            # handle case where artist doesn't have images
                            image_url = (
                                "https://via.placeholder.com/300"  # default image
                            )
                            if (
                                artist_data.get("images")
                                and len(artist_data["images"]) > 0
                            ):
                                image_url = artist_data["images"][0]["url"]

                            artist_data_map[artist_id] = {
                                "id": artist_id,
                                "name": artist_data["name"],
                                "image_url": image_url,
                                "popularity": artist_data["popularity"],
                            }
            except Exception as e:
                print(f"Error fetching artist batch: {str(e)}")
                # add fallback for problematic artists
                for artist_id in artist_batch:
                    if artist_id not in artist_data_map:
                        # create a placeholder entry for this artist
                        artist_data_map[artist_id] = {
                            "id": artist_id,
                            "name": "Unknown Artist",
                            "image_url": "https://via.placeholder.com/300",
                            "popularity": 0,
                        }

        # insert artists and add to inserted set
        if artist_data_map:
            for artist_id in artist_data_map.keys():
                inserted_artist_ids.add(artist_id)

    except Exception as e:
        print(f"Error processing artists: {str(e)}")

    return artist_data_map, inserted_artist_ids


async def get_valid_artist_ids(artist_ids, inserted_artist_ids):
    """Get all valid artist IDs from the database and recently inserted ones."""
    all_artist_ids = await database.fetch_all("SELECT id FROM artists")
    valid_artist_ids = set(artist_ids).union(inserted_artist_ids)
    for artist in all_artist_ids:
        valid_artist_ids.add(artist["id"])
    return valid_artist_ids


def filter_album_artists(album_artists_to_add_to_database, valid_artist_ids):
    """Filter album-artist relationships to only include valid artists."""
    filtered_album_artists = {}
    for key, data in album_artists_to_add_to_database.items():
        if data["artist_id"] in valid_artist_ids:
            filtered_album_artists[key] = data
    return filtered_album_artists


def filter_song_artists(song_artists_to_add_to_database, valid_artist_ids):
    """Filter song-artist relationships to only include valid artists."""
    filtered_song_artists = {}
    for key, data in song_artists_to_add_to_database.items():
        if data["artist_id"] in valid_artist_ids:
            filtered_song_artists[key] = data
    return filtered_song_artists


async def batch_insert_albums(album_data_map):
    """Insert albums in batch."""
    try:
        album_values = {}
        placeholders = []

        for i, (album_id, album_data) in enumerate(album_data_map.items()):
            placeholders.append(
                f"(:album_id_{i}, :album_name_{i}, :album_image_{i}, {album_data['release_date']}, :album_popularity_{i}, :album_type_{i}, :album_total_tracks_{i})"
            )

            album_values[f"album_id_{i}"] = album_id
            album_values[f"album_name_{i}"] = album_data["name"]
            album_values[f"album_image_{i}"] = album_data["image_url"]
            album_values[f"album_popularity_{i}"] = album_data["popularity"]
            album_values[f"album_type_{i}"] = album_data["album_type"]
            album_values[f"album_total_tracks_{i}"] = album_data["total_tracks"]

        album_query = f"""
        INSERT INTO albums (id, name, image_url, release_date, popularity, album_type, total_tracks)
        VALUES {", ".join(placeholders)}
        ON CONFLICT (id) DO NOTHING
        """
        await database.execute(query=album_query, values=album_values)
    except Exception as e:
        print(f"Error batch inserting albums: {str(e)}")


async def batch_insert_artists(artist_data_map):
    """Insert artists in batch."""
    try:
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

        artist_query = f"""
        INSERT INTO artists (id, name, image_url, popularity)
        VALUES {", ".join(placeholders)}
        ON CONFLICT (id) DO NOTHING
        """

        await database.execute(query=artist_query, values=artist_values)
    except Exception as e:
        print(f"Error batch inserting artists: {str(e)}")


async def batch_insert_songs(new_songs, existing_song_map):
    """Insert songs in batch."""
    try:
        # build placeholder sections for songs
        placeholder_sections = []
        values_list = {}

        for i, song in enumerate(new_songs):
            # add song data to values_list
            values_list[f"id_{i}"] = song["id"]
            values_list[f"name_{i}"] = song["name"]
            values_list[f"album_id_{i}"] = song["album_id"]
            values_list[f"duration_ms_{i}"] = song["duration_ms"]
            values_list[f"spotify_uri_{i}"] = song["spotify_uri"]
            values_list[f"spotify_url_{i}"] = song["spotify_url"]
            values_list[f"popularity_{i}"] = song["popularity"]
            values_list[f"explicit_{i}"] = song["explicit"]
            values_list[f"track_number_{i}"] = song["track_number"]
            values_list[f"disc_number_{i}"] = song["disc_number"]

            placeholder_section = (
                f"(:id_{i}, :name_{i}, :album_id_{i}, :duration_ms_{i}, "
                + f":spotify_uri_{i}, :spotify_url_{i}, :popularity_{i}, :explicit_{i}, :track_number_{i}, :disc_number_{i})"
            )
            placeholder_sections.append(placeholder_section)

        # execute batch insert for songs
        if placeholder_sections:
            query = f"""
            INSERT INTO songs (
                id, name, album_id, duration_ms, spotify_uri, spotify_url, popularity, explicit, track_number, disc_number
            )
            VALUES {', '.join(placeholder_sections)}
            ON CONFLICT (id) DO NOTHING
            RETURNING id
            """

            inserted_songs = await database.fetch_all(query=query, values=values_list)

            # update the existing_song_map with newly inserted songs
            for song in inserted_songs:
                existing_song_map[song["id"]] = song["id"]
    except Exception as e:
        print(f"Error batch inserting songs: {str(e)}")


async def batch_insert_song_artists(song_artists_to_add_to_database):
    """Insert song-artist relationships in batch."""
    try:
        artist_values = {}
        placeholders = []

        for i, (key, artist_data) in enumerate(song_artists_to_add_to_database.items()):
            placeholders.append(f"(:song_id_{i}, :artist_id_{i}, :list_position_{i})")
            artist_values[f"song_id_{i}"] = artist_data["song_id"]
            artist_values[f"artist_id_{i}"] = artist_data["artist_id"]
            artist_values[f"list_position_{i}"] = artist_data["list_position"]

        artist_query = f"""
        INSERT INTO song_artists (song_id, artist_id, list_position)
        VALUES {', '.join(placeholders)}
        ON CONFLICT (song_id, artist_id) DO NOTHING
        """

        await database.execute(query=artist_query, values=artist_values)
    except Exception as e:
        print(f"Error batch inserting song artists: {str(e)}")


async def batch_insert_album_artists(album_artists_to_add_to_database):
    """Insert album-artist relationships in batch."""
    try:
        artist_values = {}
        placeholders = []

        for i, (key, artist_data) in enumerate(
            album_artists_to_add_to_database.items()
        ):
            placeholders.append(f"(:album_id_{i}, :artist_id_{i}, :list_position_{i})")
            artist_values[f"album_id_{i}"] = artist_data["album_id"]
            artist_values[f"artist_id_{i}"] = artist_data["artist_id"]
            artist_values[f"list_position_{i}"] = artist_data["list_position"]

        artist_query = f"""
        INSERT INTO album_artists (album_id, artist_id, list_position)
        VALUES {', '.join(placeholders)}
        ON CONFLICT (album_id, artist_id) DO NOTHING
        """

        await database.execute(query=artist_query, values=artist_values)
    except Exception as e:
        print(f"Error batch inserting album artists: {str(e)}")


async def process_artist_genres(artist_genre_map):
    """Process artist-genre relationships."""
    try:
        query = "INSERT INTO artist_genres (artist_id, genre_id) VALUES (:artist_id, :genre_id)"
        values = []

        # get existing genre IDs
        genre_ids = await database.fetch_all(
            """
            SELECT name, id 
            FROM genres 
            WHERE name = ANY(:names)
            """,
            values={
                "names": list(
                    set(
                        genre
                        for genres in artist_genre_map.values()
                        for genre in genres
                    )
                )
            },
        )

        genre_id_map = {genre["name"]: genre["id"] for genre in genre_ids}

        # process each artist's genres
        for artist_id, genres in artist_genre_map.items():
            for genre in genres:
                genre_id = genre_id_map.get(genre, "KEYERRORSJNXHSJDANDADKJASNDKASD")
                if genre_id == "KEYERRORSJNXHSJDANDADKJASNDKASD":
                    await database.execute(
                        "INSERT INTO genres (name) VALUES (:name) ON CONFLICT (name) DO NOTHING",
                        values={"name": genre},
                    )
                    genre_id = await database.fetch_val(
                        "SELECT id FROM genres WHERE name = :name",
                        values={"name": genre},
                    )
                values.append({"artist_id": artist_id, "genre_id": genre_id})

        # batch insert artist-genre relationships
        await database.execute_many(query=query, values=values)

    except Exception as e:
        print(f"Error processing artist genres: {str(e)}")


async def add_songs_to_playlist(playlist_id, song_ids, track_positions):
    """Add songs to a playlist in batch."""
    try:
        # sort by original playlist position
        sorted_song_ids = []
        for track_id in song_ids:
            if track_id in track_positions:
                sorted_song_ids.append((track_id, track_positions[track_id]))

        sorted_song_ids.sort(key=lambda x: x[1])
        sorted_song_ids = [song_id for song_id, _ in sorted_song_ids]

        # build and execute playlist_songs batch insert
        if sorted_song_ids:
            # use smaller batches for very large playlists
            batch_size = 500
            batches = [
                sorted_song_ids[i : i + batch_size]
                for i in range(0, len(sorted_song_ids), batch_size)
            ]

            # get the next position
            position = await database.fetch_val(
                """
                SELECT COALESCE(MAX(position), -1) + 1 
                FROM playlist_songs 
                WHERE playlist_id = :playlist_id
                """,
                values={"playlist_id": playlist_id},
            )

            for batch_index, batch in enumerate(batches):
                ps_values_list = {}
                ps_placeholders = []

                for i, song_id in enumerate(batch):
                    ps_placeholders.append(
                        f"(:playlist_id_{i}, :song_id_{i}, :position_{i})"
                    )
                    ps_values_list[f"playlist_id_{i}"] = playlist_id
                    ps_values_list[f"song_id_{i}"] = song_id
                    ps_values_list[f"position_{i}"] = (
                        position + i + (batch_index * batch_size)
                    )

                ps_query = f"""
                INSERT INTO playlist_songs (playlist_id, song_id, position)
                VALUES {', '.join(ps_placeholders)}
                ON CONFLICT (playlist_id, song_id) DO NOTHING
                """

                await database.execute(query=ps_query, values=ps_values_list)
    except Exception as e:
        print(f"Error adding songs to playlist: {str(e)}")


@router.get("/{public_id}", response_model=Playlist)
async def get_playlist(public_id: str, current_user: User = Depends(get_current_user)):
    # if user is not owner of playlist redirect to public playlist
    playlist = await database.fetch_one(
        "select user_id from playlists where public_id = :public_id",
        values={"public_id": public_id},
    )
    if playlist["user_id"] is not None and playlist["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="redirecting to public playlist",
        )
    # get playlist with songs
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
        WHERE p.public_id = :public_id
        AND p.user_id = :user_id
        """,
        values={"public_id": public_id, "user_id": current_user.id},
    )

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
        )

    # convert to dict and parse songs if needed
    playlist_dict = dict(playlist)
    if isinstance(playlist_dict["songs"], str):
        try:
            playlist_dict["songs"] = json.loads(playlist_dict["songs"])
        except:
            playlist_dict["songs"] = []

    return playlist_dict


@router.get("/", response_model=List[Playlist])
async def get_playlists(
    current_user: User = Depends(get_current_user),
) -> List[Playlist]:
    query = """
    SELECT 
        p.id, 
        p.name, 
        p.description, 
        p.is_public, 
        p.user_id, 
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
    WHERE p.user_id = :user_id
    """

    values = {"user_id": current_user.id}

    result = await database.fetch_all(query=query, values=values)
    playlists = []

    # process each playlist
    for row in result:
        playlist_dict = dict(row)

        playlists.append(playlist_dict)

    return playlists


@router.put("/{public_id}", response_model=Playlist)
async def update_playlist(
    public_id: str, playlist: PlaylistUpdate, user: User = Depends(get_current_user)
):
    # verify user owns playlist
    existing = await database.fetch_one(
        "SELECT id FROM playlists WHERE public_id = :public_id AND user_id = :user_id",
        values={"public_id": public_id, "user_id": user.id},
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
        )

    # build update query
    update_fields = []
    values = {"id": existing["id"]}

    if playlist.name is not None:
        update_fields.append("name = :name")
        values["name"] = playlist.name

    if playlist.description is not None:
        update_fields.append("description = :description")
        values["description"] = playlist.description

    if playlist.is_public is not None:
        update_fields.append("is_public = :is_public")
        values["is_public"] = playlist.is_public

    if playlist.spotify_playlist_id is not None:
        update_fields.append("spotify_playlist_id = :spotify_playlist_id")
        values["spotify_playlist_id"] = playlist.spotify_playlist_id

    if playlist.image_url is not None:
        update_fields.append("image_url = :image_url")
        values["image_url"] = playlist.image_url

    # add updated_at
    update_fields.append("updated_at = CURRENT_TIMESTAMP")

    # execute update
    if update_fields:
        query = f"""
        UPDATE playlists
        SET {", ".join(update_fields)}
        WHERE id = :id
        """
        await database.execute(query, values=values)

    return await get_playlist(public_id, user)


@router.delete("/{public_id}")
async def delete_playlist(public_id: str, user: User = Depends(get_current_user)):
    # verify user owns playlist
    existing = await database.fetch_one(
        "SELECT id FROM playlists WHERE public_id = :public_id AND user_id = :user_id",
        values={"public_id": public_id, "user_id": user.id},
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
        )

    # delete playlist
    await database.execute(
        "DELETE FROM playlists WHERE id = :id",
        values={"id": existing["id"]},
    )

    return {"message": "playlist deleted successfully"}


@router.post("/{public_id}/songs")
async def add_songs(
    public_id: str,
    songs: List[SongBase],
    user: User = Depends(get_current_user),
    sp: spotipy.Spotify = Depends(get_spotify_client),
):
    # verify user owns playlist
    existing = await database.fetch_one(
        """
        SELECT id, user_id FROM playlists WHERE public_id = :public_id
        """,
        values={"public_id": public_id},
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
        )

    if existing["user_id"] != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="you don't have permission to modify this playlist",
        )

    playlist_id = existing["id"]

    # get current max position
    max_pos = await database.fetch_val(
        "SELECT COALESCE(MAX(position), -1) FROM playlist_songs WHERE playlist_id = :playlist_id",
        values={"playlist_id": playlist_id},
    )

    if max_pos is None:
        max_pos = -1

    # check which songs already exist in the database
    song_ids = [song.id for song in songs]
    existing_songs = await database.fetch_all(
        "SELECT id FROM songs WHERE id = ANY(:song_ids)",
        values={"song_ids": song_ids},
    )
    existing_song_ids = {song["id"] for song in existing_songs}

    # counters for response
    successful_adds = 0
    already_exists = 0
    failed_songs = []

    # process each song individually
    for idx, song in enumerate(songs):
        position = max_pos + 1 + idx

        try:
            # get detailed track information from Spotify
            track_data = sp.track(song.id)
            album_id = track_data["album"]["id"]

            # check if album already exists
            album_exists = await database.fetch_one(
                "SELECT id FROM albums WHERE id = :id",
                values={"id": album_id},
            )

            # process album if it doesn't exist
            if not album_exists:
                try:
                    # get full album data
                    album_data = sp.album(album_id)

                    # handle release date
                    release_date = process_release_date(album_data["release_date"])

                    # insert album
                    await database.execute(
                        f"""
                        INSERT INTO albums (id, name, image_url, release_date, popularity, album_type, total_tracks)
                        VALUES (:id, :name, :image_url, {release_date}, :popularity, :album_type, :total_tracks)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        values={
                            "id": album_id,
                            "name": album_data["name"],
                            "image_url": (
                                album_data["images"][0]["url"]
                                if album_data["images"]
                                else "https://via.placeholder.com/300"
                            ),
                            "popularity": album_data["popularity"],
                            "album_type": album_data["album_type"],
                            "total_tracks": album_data["total_tracks"],
                        },
                    )

                    # process album artists
                    is_various_artists = False
                    for album_artist in album_data["artists"]:
                        if album_artist["name"].lower() == "various artists":
                            is_various_artists = True
                            break

                    if is_various_artists:
                        # for "Various Artists" albums, use track artists
                        for i, track_artist in enumerate(track_data["artists"]):
                            await process_album_artist(
                                album_id,
                                track_artist["id"],
                                i,
                                set(),  # we'll check in the function
                                set(),  # not used directly
                                {},  # not used directly
                            )
                    else:
                        # normal album processing
                        for i, album_artist in enumerate(album_data["artists"]):
                            # insert artist if needed
                            artist_exists = await database.fetch_one(
                                "SELECT id FROM artists WHERE id = :id",
                                values={"id": album_artist["id"]},
                            )

                            if not artist_exists:
                                try:
                                    artist_info = sp.artist(album_artist["id"])
                                    await database.execute(
                                        """
                                        INSERT INTO artists (id, name, image_url, popularity)
                                        VALUES (:id, :name, :image_url, :popularity)
                                        ON CONFLICT (id) DO NOTHING
                                        """,
                                        values={
                                            "id": album_artist["id"],
                                            "name": artist_info["name"],
                                            "image_url": (
                                                artist_info["images"][0]["url"]
                                                if artist_info["images"]
                                                else "https://via.placeholder.com/300"
                                            ),
                                            "popularity": artist_info["popularity"],
                                        },
                                    )

                                    # process genres
                                    if artist_info.get("genres"):
                                        for genre in artist_info["genres"]:
                                            # add genre if it doesn't exist
                                            await database.execute(
                                                "INSERT INTO genres (name) VALUES (:name) ON CONFLICT (name) DO NOTHING",
                                                values={"name": genre},
                                            )

                                            # get genre id
                                            genre_id = await database.fetch_val(
                                                "SELECT id FROM genres WHERE name = :name",
                                                values={"name": genre},
                                            )

                                            # link artist to genre
                                            await database.execute(
                                                """
                                                INSERT INTO artist_genres (artist_id, genre_id)
                                                VALUES (:artist_id, :genre_id)
                                                ON CONFLICT (artist_id, genre_id) DO NOTHING
                                                """,
                                                values={
                                                    "artist_id": album_artist["id"],
                                                    "genre_id": genre_id,
                                                },
                                            )
                                except Exception as e:
                                    print(
                                        f"Error processing artist {album_artist['id']}: {str(e)}"
                                    )

                            # add album artist relationship
                            await database.execute(
                                """
                                INSERT INTO album_artists (album_id, artist_id, list_position)
                                VALUES (:album_id, :artist_id, :list_position)
                                ON CONFLICT (album_id, artist_id) DO NOTHING
                                """,
                                values={
                                    "album_id": album_id,
                                    "artist_id": album_artist["id"],
                                    "list_position": i + 1,  # start at 1 instead of 0
                                },
                            )
                except Exception as e:
                    print(f"Error processing album {album_id}: {str(e)}")
            else:
                # even for existing albums, check if it's a "Various Artists" album
                # and ensure track artists are added to album-artist relationships
                try:
                    # check if this is a Various Artists album
                    album_artist_check = await database.fetch_one(
                        """
                        SELECT aa.album_id 
                        FROM album_artists aa
                        JOIN artists a ON aa.artist_id = a.id
                        WHERE aa.album_id = :album_id AND LOWER(a.name) = 'various artists'
                        """,
                        values={"album_id": album_id},
                    )

                    if album_artist_check:
                        # this is a Various Artists album, add track artists to album-artist table
                        for track_artist in track_data["artists"]:
                            await process_album_artist_various_artists(
                                album_id,
                                track_artist["id"],
                                set(),  # we'll check in the function
                                set(),  # not used directly
                                {},  # not used directly
                            )
                except Exception as e:
                    print(
                        f"Error checking for Various Artists album {album_id}: {str(e)}"
                    )

            # check if song exists
            if song.id not in existing_song_ids:
                try:
                    # add song to database
                    await database.execute(
                        """
                        INSERT INTO songs (
                            id, name, album_id, duration_ms, spotify_uri, spotify_url, popularity, explicit, track_number, disc_number
                        )
                        VALUES (
                            :id, :name, :album_id, :duration_ms, :spotify_uri, :spotify_url, :popularity, :explicit, :track_number, :disc_number
                        )
                        ON CONFLICT (id) DO NOTHING
                        """,
                        values={
                            "id": song.id,
                            "name": track_data["name"],
                            "album_id": album_id,
                            "duration_ms": track_data["duration_ms"],
                            "spotify_uri": track_data["uri"],
                            "spotify_url": track_data["external_urls"]["spotify"],
                            "popularity": track_data["popularity"],
                            "explicit": track_data["explicit"],
                            "track_number": track_data["track_number"],
                            "disc_number": track_data["disc_number"],
                        },
                    )

                    # add song-artist relationships
                    for i, artist in enumerate(track_data["artists"]):
                        # check if artist exists
                        artist_exists = await database.fetch_one(
                            "SELECT id FROM artists WHERE id = :id",
                            values={"id": artist["id"]},
                        )

                        if not artist_exists:
                            try:
                                # get artist info
                                artist_info = sp.artist(artist["id"])
                                await database.execute(
                                    """
                                    INSERT INTO artists (id, name, image_url, popularity)
                                    VALUES (:id, :name, :image_url, :popularity)
                                    ON CONFLICT (id) DO NOTHING
                                    """,
                                    values={
                                        "id": artist["id"],
                                        "name": artist_info["name"],
                                        "image_url": (
                                            artist_info["images"][0]["url"]
                                            if artist_info["images"]
                                            else "https://via.placeholder.com/300"
                                        ),
                                        "popularity": artist_info["popularity"],
                                    },
                                )

                                # process genres
                                if artist_info.get("genres"):
                                    for genre in artist_info["genres"]:
                                        # add genre if it doesn't exist
                                        await database.execute(
                                            "INSERT INTO genres (name) VALUES (:name) ON CONFLICT (name) DO NOTHING",
                                            values={"name": genre},
                                        )

                                        # get genre id
                                        genre_id = await database.fetch_val(
                                            "SELECT id FROM genres WHERE name = :name",
                                            values={"name": genre},
                                        )

                                        # link artist to genre
                                        await database.execute(
                                            """
                                            INSERT INTO artist_genres (artist_id, genre_id)
                                            VALUES (:artist_id, :genre_id)
                                            ON CONFLICT (artist_id, genre_id) DO NOTHING
                                            """,
                                            values={
                                                "artist_id": artist["id"],
                                                "genre_id": genre_id,
                                            },
                                        )
                            except Exception as e:
                                print(
                                    f"Error processing artist {artist['id']}: {str(e)}"
                                )

                        # add song-artist relationship
                        await database.execute(
                            """
                            INSERT INTO song_artists (song_id, artist_id, list_position)
                            VALUES (:song_id, :artist_id, :list_position)
                            ON CONFLICT (song_id, artist_id) DO NOTHING
                            """,
                            values={
                                "song_id": song.id,
                                "artist_id": artist["id"],
                                "list_position": i,
                            },
                        )

                    # update existing_song_ids to include this song now
                    existing_song_ids.add(song.id)
                except Exception as e:
                    print(f"Error inserting song {song.id}: {str(e)}")
                    failed_songs.append({"id": song.id, "error": str(e)})
                    # continue to the next song
                    continue

            # add song to playlist
            try:
                result = await database.execute(
                    """
                    INSERT INTO playlist_songs (playlist_id, song_id, position)
                    VALUES (:playlist_id, :song_id, :position)
                    ON CONFLICT (playlist_id, song_id) DO NOTHING
                    RETURNING position
                    """,
                    values={
                        "playlist_id": playlist_id,
                        "song_id": song.id,
                        "position": position,
                    },
                )

                if result is not None:
                    successful_adds += 1

                    # automatically find and add YouTube videos for this song
                    # get artist names
                    artists = await database.fetch_all(
                        """
                        SELECT a.name
                        FROM song_artists sa
                        JOIN artists a ON sa.artist_id = a.id
                        WHERE sa.song_id = :song_id
                        ORDER BY sa.list_position
                        """,
                        values={"song_id": song.id},
                    )

                    artist_names = [artist["name"] for artist in artists]
                    artist_str = " ".join(artist_names[:2])  # use first two artists

                    # check if the song already has YouTube videos
                    existing_videos = await database.fetch_val(
                        """
                        SELECT COUNT(*) FROM song_youtube_videos
                        WHERE song_id = :song_id
                        """,
                        values={"song_id": song.id},
                    )

                    # if no videos exist, search for and add them
                    if existing_videos == 0:
                        # we'll do this in the background without waiting
                        asyncio.create_task(
                            find_and_add_youtube_videos(song.id, song.name, artist_str)
                        )
                else:
                    already_exists += 1
            except Exception as e:
                print(f"Error adding song {song.id} to playlist: {str(e)}")
                failed_songs.append({"id": song.id, "error": str(e)})
        except Exception as e:
            print(f"Error processing song {song.id}: {str(e)}")
            failed_songs.append({"id": song.id, "error": str(e)})

    # update playlist updated_at timestamp
    await database.execute(
        """
        UPDATE playlists SET updated_at = NOW() WHERE id = :playlist_id
        """,
        values={"playlist_id": playlist_id},
    )

    # return appropriate message based on what happened
    if successful_adds > 0 and len(failed_songs) > 0:
        return {
            "message": f"Added {successful_adds} songs, {already_exists} were already in the playlist, {len(failed_songs)} failed",
            "status": "partial",
            "failed_songs": failed_songs[:5],
        }
    elif successful_adds > 0:
        return {
            "message": f"Added {successful_adds} songs successfully",
            "status": "success",
        }
    elif already_exists > 0 and len(failed_songs) == 0:
        # if all songs were already in the playlist, return a 409 Conflict
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="All songs already exist in this playlist",
        )
    elif len(failed_songs) > 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add songs: {failed_songs[0]['error']}",
        )
    else:
        return {"message": "No songs were added", "status": "error"}


@router.delete("/{public_id}/songs/{song_id}")
async def remove_song(
    public_id: str, song_id: str, user: User = Depends(get_current_user)
):
    # verify user owns playlist
    existing = await database.fetch_one(
        "SELECT id FROM playlists WHERE public_id = :public_id AND user_id = :user_id",
        values={"public_id": public_id, "user_id": user.id},
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
        )

    playlist_id = existing["id"]

    try:
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
    except Exception as e:
        print(f"Error removing song: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"failed to remove song: {str(e)}",
        )


@router.put("/{public_id}/songs/reorder")
async def reorder_songs(
    public_id: str, request: SongReorderRequest, user: User = Depends(get_current_user)
):

    # verify user owns playlist
    existing = await database.fetch_one(
        "SELECT id FROM playlists WHERE public_id = :public_id AND user_id = :user_id",
        values={"public_id": public_id, "user_id": user.id},
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
        )

    playlist_id = existing["id"]

    # if no songs to reorder, return early
    if not request.song_ids:
        return {"message": "no songs to reorder"}

    try:
        # first, get the current positions of all songs in the playlist
        current_positions = await database.fetch_all(
            """
            SELECT song_id, position 
            FROM playlist_songs 
            WHERE playlist_id = :playlist_id
            ORDER BY position
            """,
            values={"playlist_id": playlist_id},
        )

        # create a mapping of song_id to current position
        song_to_position = {
            row["song_id"]: row["position"] for row in current_positions
        }

        # create a mapping of new positions based on the request
        new_positions = {song_id: i for i, song_id in enumerate(request.song_ids)}

        # determine which songs need to be updated
        songs_to_update = []
        for song_id in request.song_ids:
            if (
                song_id in song_to_position
                and song_to_position[song_id] != new_positions[song_id]
            ):
                songs_to_update.append((song_id, new_positions[song_id]))

        if not songs_to_update:
            return {"message": "no position changes detected"}

        # build case statement for batch update
        case_statements = []
        params = {"playlist_id": playlist_id}

        for i, (song_id, new_position) in enumerate(songs_to_update):
            case_statements.append(
                f"WHEN song_id = :song_id_{i} THEN CAST(:position_{i} AS INTEGER)"
            )
            params[f"song_id_{i}"] = song_id
            params[f"position_{i}"] = new_position

        # create the song_id IN clause for the WHERE condition
        song_id_placeholders = [f":song_id_{i}" for i in range(len(songs_to_update))]
        song_id_in_clause = ", ".join(song_id_placeholders)

        # build the complete query
        query = f"""
        UPDATE playlist_songs
        SET position = CASE
            {" ".join(case_statements)}
        END
        WHERE playlist_id = :playlist_id AND song_id IN ({song_id_in_clause})
        """

        # execute the batch update
        async with database.transaction():
            await database.execute(query=query, values=params)

            # update the playlist's updated_at timestamp
            await database.execute(
                """
                UPDATE playlists
                SET updated_at = :updated_at
                WHERE id = :playlist_id
                """,
                values={
                    "playlist_id": playlist_id,
                    "updated_at": datetime.now(timezone.utc),
                },
            )
        return {"message": "songs reordered successfully"}
    except Exception as e:
        print(f"Error reordering songs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"error reordering songs: {str(e)}",
        )
