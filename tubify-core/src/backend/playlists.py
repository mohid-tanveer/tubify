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

    # generate a unique 22-character alphanumeric ID for the playlist
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
            break

        attempt += 1

        if attempt == max_attempts:
            # if we've reached max attempts, generate a longer id to reduce collision probability
            public_id = "".join(
                random.choices(string.ascii_letters + string.digits, k=26)
            )

    # insert playlist
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
            start_time = time.time()
            # prepare batch data for songs
            songs_to_insert = []
            albums_placeholder_sections = []
            albums_to_add_to_database = {}
            album_artists_to_add_to_database = {}
            song_artists_to_add_to_database = {}
            artists_to_add_to_database = set()
            track_ids = []
            track_positions = {}

            # get all album and artist ids from database
            existing_albums = await database.fetch_all("SELECT id FROM albums")
            existing_artists = await database.fetch_all("SELECT id FROM artists")
            artist_ids = set([artist["id"] for artist in existing_artists])
            album_ids = set([album["id"] for album in existing_albums])

            # get initial playlist data
            results = sp_playlist
            tracks = results["tracks"]
            total_tracks = tracks.get("total", 0)
            print(f"Importing Spotify playlist with {total_tracks} tracks")

            # collect tracks from first page
            position = 0
            while True:
                for item in tracks["items"]:
                    if item["track"]:
                        track = item["track"]
                        track_ids.append(track["id"])
                        track_positions[track["id"]] = position
                        position += 1
                        track_id = track["id"]

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

                        album_id = track["album"]["id"]
                        if album_id not in album_ids:
                            album_ids.add(album_id)
                            raw_date = track["album"]["release_date"]

                            # check if this is a "Various Artists" album
                            is_various_artists_album = False
                            for album_artist in track["album"]["artists"]:
                                if album_artist["name"].lower() == "various artists":
                                    is_various_artists_album = True
                                    break

                            # for "Various Artists" albums, use the track artists instead
                            if is_various_artists_album:
                                for i, track_artist in enumerate(track["artists"]):
                                    artist_id = track_artist["id"]
                                    if artist_id not in artist_ids:
                                        artist_ids.add(artist_id)
                                        artists_to_add_to_database.add(artist_id)

                                    # create an album-artist association with this track artist
                                    key = f"{album_id}_{artist_id}"

                                    if key not in album_artists_to_add_to_database:
                                        album_artists_to_add_to_database[key] = {
                                            "album_id": album_id,
                                            "artist_id": artist_id,
                                            "list_position": i,
                                        }
                            else:
                                for i in range(len(track["album"]["artists"])):
                                    artist_id = track["album"]["artists"][i]["id"]
                                    if artist_id not in artist_ids:
                                        artist_ids.add(artist_id)
                                        artists_to_add_to_database.add(artist_id)

                                    key = f"{album_id}_{i}"

                                    if key not in album_artists_to_add_to_database:
                                        album_artists_to_add_to_database[key] = {
                                            "album_id": album_id,
                                            "artist_id": artist_id,
                                            "list_position": i,
                                        }
                            release_date = None
                            # handle different spotify date formats
                            date_parts = raw_date.split("-")
                            if len(date_parts) == 3:  # full date: YYYY-MM-DD
                                release_date = f"'{raw_date}'::date"
                            elif len(date_parts) == 2:  # year-month: YYYY-MM
                                release_date = (
                                    f"'{raw_date}-01'::date"  # first day of month given
                                )
                            elif (
                                len(date_parts) == 1 and date_parts[0].isdigit()
                            ):  # year only: YYYY
                                release_date = f"'{raw_date}-01-01'::date"  # first day of year given
                            i = len(albums_placeholder_sections)
                            albums_to_add_to_database[f"album_id_{i}"] = album_id
                            albums_to_add_to_database[f"album_name_{i}"] = track[
                                "album"
                            ]["name"]
                            albums_to_add_to_database[f"image_url_{i}"] = track[
                                "album"
                            ]["images"][0]["url"]

                            albums_placeholder_sections.append(
                                f"(:album_id_{i}, :album_name_{i}, :image_url_{i}, {release_date})"
                            )

                        songs_to_insert.append(
                            {
                                "id": track["id"],
                                "name": track["name"],
                                "album_id": track["album"]["id"],
                                "duration_ms": track["duration_ms"],
                                "spotify_uri": track["uri"],
                                "spotify_url": track["external_urls"]["spotify"],
                            }
                        )
                # handle pagination if there are more tracks
                if tracks["next"]:
                    tracks = sp.next(tracks)
                else:
                    break

            # keep track of all songs to add to the playlist
            all_playlist_song_ids = [song["id"] for song in songs_to_insert]

            # get all existing songs, artists and albums in single queries to reduce DB calls
            existing_songs = await database.fetch_all(
                "SELECT id FROM songs WHERE id = ANY(:spotify_ids)",
                values={"spotify_ids": track_ids},
            )
            existing_song_map = {song["id"]: song["id"] for song in existing_songs}
            existing_spotify_ids = set(existing_song_map.keys())

            # filter out songs that already exist
            new_songs = [
                song
                for song in songs_to_insert
                if song["id"] not in existing_spotify_ids
            ]

            print(f"Need to add {len(new_songs)} new songs")

            # add new artists and albums that need to be inserted
            print(f"Need to add {len(artists_to_add_to_database)} new artists")
            print(f"Need to add {len(albums_to_add_to_database)} new albums")
            new_artist_ids = list(artists_to_add_to_database)
            del artists_to_add_to_database
            # store successfully inserted artist IDs
            inserted_artist_ids = set()

            # insert new artists in batch first
            if new_artist_ids:
                # process artists in batches using Spotify's batch API
                batch_size = 50
                artist_batches = [
                    new_artist_ids[i : i + batch_size]
                    for i in range(0, len(new_artist_ids), batch_size)
                ]
                print(
                    f"Will process {len(new_artist_ids)} artists in {len(artist_batches)} batches using batch API"
                )

                try:
                    artist_data_map = {}

                    for batch_idx, artist_batch in enumerate(artist_batches):
                        print(
                            f"Processing artist batch {batch_idx+1} of {len(artist_batches)}"
                        )

                        # use spotify's batch API to get multiple artists in one request
                        try:
                            # add a small delay between batch requests to avoid rate limiting
                            if batch_idx > 0:
                                print(f"pausing before next artist batch")
                                await asyncio.sleep(
                                    1.0
                                )  # 1 second delay between batches

                            # get several artists in a single API call
                            artists_data = sp.artists(artist_batch)

                            if artists_data and "artists" in artists_data:
                                for artist_data in artists_data["artists"]:
                                    if artist_data:
                                        # simple genres processing
                                        genres = artist_data.get("genres", [])
                                        artist_id = artist_data["id"]

                                        # handle case where artist doesn't have images
                                        image_url = "https://via.placeholder.com/300"  # default image
                                        if (
                                            artist_data.get("images")
                                            and len(artist_data["images"]) > 0
                                        ):
                                            image_url = artist_data["images"][0]["url"]

                                        artist_data_map[artist_id] = {
                                            "id": artist_id,
                                            "name": artist_data["name"],
                                            "image_url": image_url,
                                            "genres": genres,
                                        }
                        except Exception as e:
                            print(f"Error fetching artist batch: {str(e)}")
                            # add fallback for various artists or other problematic artists
                            for artist_id in artist_batch:
                                if artist_id not in artist_data_map:
                                    # create a placeholder entry for this artist
                                    artist_data_map[artist_id] = {
                                        "id": artist_id,
                                        "name": "Unknown Artist",
                                        "image_url": "https://via.placeholder.com/300",
                                        "genres": [],
                                    }

                    # execute batch insert for artists
                    if artist_data_map:
                        print(f"Inserting {len(artist_data_map)} artists in batch")
                        artist_values = {}
                        placeholders = []

                        for i, (artist_id, artist_data) in enumerate(
                            artist_data_map.items()
                        ):
                            placeholders.append(
                                f"(:artist_id_{i}, :artist_name_{i}, :artist_image_{i}, :artist_genres_{i})"
                            )
                            artist_values[f"artist_id_{i}"] = artist_id
                            artist_values[f"artist_name_{i}"] = artist_data["name"]
                            artist_values[f"artist_image_{i}"] = artist_data[
                                "image_url"
                            ]
                            artist_values[f"artist_genres_{i}"] = artist_data["genres"]

                        artist_query = f"""
                        INSERT INTO artists (id, name, image_url, genres)
                        VALUES {", ".join(placeholders)}
                        ON CONFLICT (id) DO NOTHING
                        """

                        await database.execute(query=artist_query, values=artist_values)

                        # add all inserted artist IDs to our set
                        for artist_id in artist_data_map.keys():
                            inserted_artist_ids.add(artist_id)

                except Exception as e:
                    print(f"Error batch inserting artists: {str(e)}")

            # get all artists from the database to ensure we only reference valid artists
            all_artist_ids = await database.fetch_all("SELECT id FROM artists")
            valid_artist_ids = set(artist_ids).union(inserted_artist_ids)
            for artist in all_artist_ids:
                valid_artist_ids.add(artist["id"])

            # filter album_artists_to_add_to_database to only include valid artists
            filtered_album_artists = {}
            for key, data in album_artists_to_add_to_database.items():
                if data["artist_id"] in valid_artist_ids:
                    filtered_album_artists[key] = data

            album_artists_to_add_to_database = filtered_album_artists

            # filter song_artists_to_add_to_database to only include valid artists
            filtered_song_artists = {}
            for key, data in song_artists_to_add_to_database.items():
                if data["artist_id"] in valid_artist_ids:
                    filtered_song_artists[key] = data

            song_artists_to_add_to_database = filtered_song_artists

            # insert albums with batch API where possible
            if albums_to_add_to_database:
                try:
                    # execute batch insert for albums
                    print(f"Inserting {len(albums_to_add_to_database)} albums in batch")
                    album_query = f"""
                    INSERT INTO albums (id, name, image_url, release_date)
                    VALUES {", ".join(albums_placeholder_sections)}
                    ON CONFLICT (id) DO NOTHING
                    """

                    await database.execute(
                        query=album_query, values=albums_to_add_to_database
                    )
                except Exception as e:
                    print(f"Error batch inserting albums: {str(e)}")

            # insert new songs in batch
            if new_songs:
                print(f"Inserting {len(new_songs)} songs in batch")
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

                        placeholder_section = (
                            f"(:id_{i}, :name_{i}, :album_id_{i}, :duration_ms_{i}, "
                            + f":spotify_uri_{i}, :spotify_url_{i})"
                        )
                        placeholder_sections.append(placeholder_section)

                    # execute batch insert for songs
                    if placeholder_sections:
                        query = f"""
                        INSERT INTO songs (
                            id, name, album_id, duration_ms, spotify_uri, spotify_url
                        )
                        VALUES {', '.join(placeholder_sections)}
                        ON CONFLICT (id) DO NOTHING
                        RETURNING id
                        """

                        inserted_songs = await database.fetch_all(
                            query=query, values=values_list
                        )

                        # update the existing_song_map with newly inserted songs
                        for song in inserted_songs:
                            existing_song_map[song["id"]] = song["id"]
                except Exception as e:
                    print(f"Error batch inserting songs: {str(e)}")

            # insert new song artists
            if song_artists_to_add_to_database:
                try:
                    # execute batch insert for song artists
                    artist_values = {}
                    placeholders = []

                    for i, (key, artist_data) in enumerate(
                        song_artists_to_add_to_database.items()
                    ):
                        placeholders.append(
                            f"(:song_id_{i}, :artist_id_{i}, :list_position_{i})"
                        )
                        artist_values[f"song_id_{i}"] = artist_data["song_id"]
                        artist_values[f"artist_id_{i}"] = artist_data["artist_id"]
                        artist_values[f"list_position_{i}"] = artist_data[
                            "list_position"
                        ]

                    artist_query = f"""
                    INSERT INTO song_artists (song_id, artist_id, list_position)
                    VALUES {', '.join(placeholders)}
                    ON CONFLICT (song_id, artist_id) DO NOTHING
                    """

                    await database.execute(query=artist_query, values=artist_values)
                except Exception as e:
                    print(f"Error batch inserting song artists: {str(e)}")

            # insert new album artists
            if album_artists_to_add_to_database:
                try:
                    # execute batch insert for album artists
                    artist_values = {}
                    placeholders = []

                    for i, (key, artist_data) in enumerate(
                        album_artists_to_add_to_database.items()
                    ):
                        placeholders.append(
                            f"(:album_id_{i}, :artist_id_{i}, :list_position_{i})"
                        )
                        artist_values[f"album_id_{i}"] = artist_data["album_id"]
                        artist_values[f"artist_id_{i}"] = artist_data["artist_id"]
                        artist_values[f"list_position_{i}"] = artist_data[
                            "list_position"
                        ]

                    artist_query = f"""
                    INSERT INTO album_artists (album_id, artist_id, list_position)
                    VALUES {', '.join(placeholders)}
                    ON CONFLICT (album_id, artist_id) DO NOTHING
                    """

                    await database.execute(query=artist_query, values=artist_values)
                except Exception as e:
                    print(f"Error batch inserting album artists: {str(e)}")

            # now insert all playlist_songs relationships
            print(f"Adding {len(all_playlist_song_ids)} songs to playlist")
            try:
                # get the next position
                position = await database.fetch_val(
                    """
                    SELECT COALESCE(MAX(position), -1) + 1 
                    FROM playlist_songs 
                    WHERE playlist_id = :playlist_id
                    """,
                    values={"playlist_id": playlist_id},
                )

                # sort by original playlist position
                sorted_song_ids = []
                for track_id in all_playlist_song_ids:
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

                    for batch_index, batch in enumerate(batches):
                        print(
                            f"Inserting batch {batch_index + 1} of {len(batches)} into playlist_songs"
                        )
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
                print(f"Error inserting into playlist_songs: {str(e)}")

            end_time = time.time()
            print(f"Playlist import finished in {end_time - start_time:.2f} seconds")

        except Exception as e:
            if os.getenv("DEV_MODE", "false").lower() == "true":
                print(f"failed to import songs from spotify playlist: {e}")
            # log the full traceback
            import traceback

            print(f"Exception traceback: {traceback.format_exc()}")

    return await get_playlist(public_id, user)


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
        "SELECT id FROM playlists WHERE public_id = :public_id AND user_id = :user_id",
        values={"public_id": public_id, "user_id": user.id},
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="playlist not found"
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
    album_artists_to_add = {}
    song_artists_to_add = {}

    # process each song
    songs_to_add_to_playlist = []

    # process each song
    for idx, song in enumerate(songs):
        position = max_pos + 1 + idx
        song_id = None

        if song.id in existing_song_ids:
            # song already exists in database
            song_id = song.id
        else:
            try:
                # get track details from spotify
                track_data = sp.track(song.id)

                # process artist
                try:
                    for i, artist in enumerate(track_data["artists"]):
                        artist_id_val = artist["id"]
                        try:
                            artist_info = sp.artist(artist_id_val)
                            artist_record = await database.fetch_one(
                                "SELECT id FROM artists WHERE id = :id",
                                values={"id": artist_id_val},
                            )

                            if not artist_record:
                                # handle missing images for artists
                                image_url = (
                                    "https://via.placeholder.com/300"  # default image
                                )
                                if (
                                    artist_info.get("images")
                                    and len(artist_info["images"]) > 0
                                ):
                                    image_url = artist_info["images"][0]["url"]

                                # insert artist
                                await database.execute(
                                    "INSERT INTO artists (id, name, image_url, genres) VALUES (:id, :name, :image_url, :genres)",
                                    values={
                                        "id": artist_id_val,
                                        "name": artist_info["name"],
                                        "image_url": image_url,
                                        "genres": artist_info.get("genres", []),
                                    },
                                )

                            track_id = song.id
                            key = f"{track_id}_{i}"

                            if key not in song_artists_to_add:
                                song_artists_to_add[key] = {
                                    "song_id": track_id,
                                    "artist_id": artist_id_val,
                                    "list_position": i,
                                }
                        except Exception as artist_error:
                            print(
                                f"Error processing artist {artist_id_val}: {str(artist_error)}"
                            )
                            # continue with next artist
                            continue
                except Exception as artists_error:
                    print(f"Error processing artists: {str(artists_error)}")

                # process album
                album_id = track_data["album"]["id"]
                # check if album exists
                album_record = await database.fetch_one(
                    "SELECT id FROM albums WHERE id = :id",
                    values={"id": album_id},
                )

                if not album_record:
                    # insert album
                    # handle release_date conversion
                    raw_date = track_data["album"]["release_date"]
                    release_date_sql = "NULL"

                    # check if this is a "Various Artists" album
                    is_various_artists_album = False
                    for album_artist in track_data["album"]["artists"]:
                        if album_artist["name"].lower() == "various artists":
                            is_various_artists_album = True
                            break

                    # for "Various Artists" albums, use the track artists instead
                    if is_various_artists_album:
                        for i, track_artist in enumerate(track_data["artists"]):
                            artist_id = track_artist["id"]
                            try:
                                # check if artist exists
                                artist_record = await database.fetch_one(
                                    "SELECT id FROM artists WHERE id = :id",
                                    values={"id": artist_id},
                                )
                                if not artist_record:
                                    # fetch and insert artist
                                    artist_info = sp.artist(artist_id)
                                    # handle missing images
                                    image_url = "https://via.placeholder.com/300"  # default image
                                    if (
                                        artist_info.get("images")
                                        and len(artist_info["images"]) > 0
                                    ):
                                        image_url = artist_info["images"][0]["url"]

                                    await database.execute(
                                        "INSERT INTO artists (id, name, image_url, genres) VALUES (:id, :name, :image_url, :genres)",
                                        values={
                                            "id": artist_id,
                                            "name": artist_info["name"],
                                            "image_url": image_url,
                                            "genres": artist_info.get("genres", []),
                                        },
                                    )

                                # create an album-artist association with this track artist
                                key = f"{album_id}_{artist_id}"

                                if key not in album_artists_to_add:
                                    album_artists_to_add[key] = {
                                        "album_id": album_id,
                                        "artist_id": artist_id,
                                        "list_position": i,
                                    }
                            except Exception as artist_error:
                                print(
                                    f"Error processing various artist {artist_id}: {str(artist_error)}"
                                )
                                continue
                    else:
                        # normal album processing
                        try:
                            for i, album_artist in enumerate(
                                track_data["album"]["artists"]
                            ):
                                artist_id = album_artist["id"]
                                try:
                                    artist_record = await database.fetch_one(
                                        "SELECT id FROM artists WHERE id = :id",
                                        values={"id": artist_id},
                                    )
                                    if not artist_record:
                                        # get artist info
                                        artist_info = sp.artist(artist_id)
                                        # handle missing images
                                        image_url = "https://via.placeholder.com/300"  # default image
                                        if (
                                            artist_info.get("images")
                                            and len(artist_info["images"]) > 0
                                        ):
                                            image_url = artist_info["images"][0]["url"]

                                        # insert artist
                                        await database.execute(
                                            "INSERT INTO artists (id, name, image_url, genres) VALUES (:id, :name, :image_url, :genres)",
                                            values={
                                                "id": artist_id,
                                                "name": artist_info["name"],
                                                "image_url": image_url,
                                                "genres": artist_info.get("genres", []),
                                            },
                                        )

                                    key = f"{album_id}_{i}"

                                    if key not in album_artists_to_add:
                                        album_artists_to_add[key] = {
                                            "album_id": album_id,
                                            "artist_id": artist_id,
                                            "list_position": i,
                                        }
                                except Exception as artist_error:
                                    print(
                                        f"Error processing album artist {artist_id}: {str(artist_error)}"
                                    )
                                    continue
                        except Exception as album_artists_error:
                            print(
                                f"Error processing album artists: {str(album_artists_error)}"
                            )

                    if raw_date:
                        try:
                            # handle different Spotify date formats (YYYY-MM-DD, YYYY-MM, YYYY)
                            date_parts = raw_date.split("-")
                            if len(date_parts) == 3:  # full date: YYYY-MM-DD
                                release_date_sql = f"'{raw_date}'::date"
                            elif len(date_parts) == 2:  # year-month: YYYY-MM
                                release_date_sql = (
                                    f"'{raw_date}-01'::date"  # first day of month
                                )
                            elif (
                                len(date_parts) == 1 and date_parts[0].isdigit()
                            ):  # year only: YYYY
                                release_date_sql = (
                                    f"'{raw_date}-01-01'::date"  # first day of year
                                )
                        except Exception as e:
                            print(
                                f"could not parse release date '{raw_date}': {str(e)}"
                            )
                            release_date_sql = "NULL"

                    # handle missing album images
                    album_image_url = None
                    if (
                        track_data["album"].get("images")
                        and len(track_data["album"]["images"]) > 0
                    ):
                        album_image_url = track_data["album"]["images"][0]["url"]
                    else:
                        album_image_url = (
                            "https://via.placeholder.com/300"  # default image
                        )

                    # use a different SQL for album insertion with explicit date casting
                    await database.execute(
                        f"""
                        INSERT INTO albums (id, name, image_url, release_date)
                        VALUES (:id, :name, :image_url, {release_date_sql})
                        ON CONFLICT (id) DO NOTHING
                        """,
                        values={
                            "id": album_id,
                            "name": track_data["album"]["name"],
                            "image_url": album_image_url,
                        },
                    )

                # insert new song
                await database.execute(
                    """
                    INSERT INTO songs (
                        id, name, album_id, duration_ms, spotify_uri, spotify_url
                    )
                    VALUES (
                        :id, :name, :album_id, :duration_ms, :spotify_uri, :spotify_url
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    values={
                        "id": song.id,
                        "name": song.name,
                        "album_id": album_id,
                        "duration_ms": song.duration_ms,
                        "spotify_uri": song.spotify_uri,
                        "spotify_url": song.spotify_url,
                    },
                )

                song_id = song.id
            except Exception as e:
                print(f"error adding song: {str(e)}")
                continue  # skip this song and continue with others

        if song_id:
            songs_to_add_to_playlist.append(
                {"playlist_id": playlist_id, "song_id": song_id, "position": position}
            )

    # get all existing artist IDs to check against before inserting relations
    existing_artist_ids = await database.fetch_all("SELECT id FROM artists")
    existing_artist_id_set = {artist["id"] for artist in existing_artist_ids}

    # only keep relations with artists that exist in database
    filtered_song_artists = {}
    for key, data in song_artists_to_add.items():
        if data["artist_id"] in existing_artist_id_set:
            filtered_song_artists[key] = data
    song_artists_to_add = filtered_song_artists

    filtered_album_artists = {}
    for key, data in album_artists_to_add.items():
        if data["artist_id"] in existing_artist_id_set:
            filtered_album_artists[key] = data
    album_artists_to_add = filtered_album_artists

    if song_artists_to_add:
        # insert new song artists
        try:
            # execute batch insert for song artists
            artist_values = {}
            placeholders = []

            for i, (key, artist_data) in enumerate(song_artists_to_add.items()):
                placeholders.append(
                    f"(:song_id_{i}, :artist_id_{i}, :list_position_{i})"
                )
                artist_values[f"song_id_{i}"] = artist_data["song_id"]
                artist_values[f"artist_id_{i}"] = artist_data["artist_id"]
                artist_values[f"list_position_{i}"] = artist_data["list_position"]

            if placeholders:
                artist_query = f"""
                INSERT INTO song_artists (song_id, artist_id, list_position)
                VALUES {', '.join(placeholders)}
                ON CONFLICT (song_id, artist_id) DO NOTHING
                """
                await database.execute(query=artist_query, values=artist_values)
        except Exception as e:
            print(f"Error batch inserting song artists: {str(e)}")

    if album_artists_to_add:
        # insert new album artists
        try:
            # execute batch insert for album artists
            artist_values = {}
            placeholders = []

            for i, (key, artist_data) in enumerate(album_artists_to_add.items()):
                placeholders.append(
                    f"(:album_id_{i}, :artist_id_{i}, :list_position_{i})"
                )
                artist_values[f"album_id_{i}"] = artist_data["album_id"]
                artist_values[f"artist_id_{i}"] = artist_data["artist_id"]
                artist_values[f"list_position_{i}"] = artist_data["list_position"]

            if placeholders:
                artist_query = f"""
                INSERT INTO album_artists (album_id, artist_id, list_position)
                VALUES {', '.join(placeholders)}
                ON CONFLICT (album_id, artist_id) DO NOTHING
                """
                await database.execute(query=artist_query, values=artist_values)
        except Exception as e:
            print(f"Error batch inserting album artists: {str(e)}")

    # now add songs to playlist in batch
    successful_adds = 0
    already_exists = 0

    for song_data in songs_to_add_to_playlist:
        try:
            result = await database.execute(
                """
                INSERT INTO playlist_songs (playlist_id, song_id, position)
                VALUES (:playlist_id, :song_id, :position)
                ON CONFLICT (playlist_id, song_id) DO NOTHING
                RETURNING position
                """,
                values=song_data,
            )

            if result is not None:
                successful_adds += 1
            else:
                already_exists += 1
                print(f"Song {song_data['song_id']} already in playlist")
        except Exception as e:
            print(f"Error adding song to playlist: {e}")

    # update the updated_at timestamp for the playlist
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

    # return appropriate message based on what happened
    if successful_adds > 0 and already_exists > 0:
        return {
            "message": f"Added {successful_adds} songs, {already_exists} were already in the playlist",
            "status": "partial",
        }
    elif successful_adds > 0:
        return {
            "message": f"Added {successful_adds} songs successfully",
            "status": "success",
        }
    elif already_exists > 0:
        # if all songs were already in the playlist, return a 409 Conflict
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="All songs already exist in this playlist",
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
