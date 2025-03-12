from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
from auth import get_current_user, User
from database import database
from spotify_auth import get_spotify_client
import spotipy, os, json, random, string


# create router
router = APIRouter(prefix="/api/playlists", tags=["playlists"])


# models
class SongBase(BaseModel):
    spotify_id: str
    name: str
    artist: str
    album: str
    duration_ms: int
    preview_url: Optional[str] = None
    spotify_uri: str
    spotify_url: str
    album_art_url: Optional[str] = None


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
    song_ids: List[int]


# endpoints
@router.post("/", response_model=Playlist)
async def create_playlist(
    playlist: PlaylistCreate,
    user: User = Depends(get_current_user),
    sp: spotipy.Spotify = Depends(get_spotify_client),
):
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
            # prepare batch data for songs
            songs_to_insert = []
            track_ids = []
            track_positions = {}

            # get initial playlist data
            results = sp_playlist
            tracks = results["tracks"]

            # collect tracks from first page
            position = 0
            while True:
                for item in tracks["items"]:
                    if item["track"]:  # ensure track exists
                        track = item["track"]
                        track_ids.append(track["id"])
                        track_positions[track["id"]] = position
                        position += 1

                        songs_to_insert.append(
                            {
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
                                "spotify_uri": track["uri"],
                                "spotify_url": track["external_urls"]["spotify"],
                            }
                        )
                # handle pagination if there are more tracks
                if tracks["next"]:
                    tracks = sp.next(tracks)
                else:
                    break

            # find existing songs in one query
            existing_songs = await database.fetch_all(
                "SELECT id, spotify_id FROM songs WHERE spotify_id = ANY(:spotify_ids)",
                values={"spotify_ids": track_ids},
            )

            # create a mapping of spotify_id to database id
            existing_song_map = {
                song["spotify_id"]: song["id"] for song in existing_songs
            }
            existing_spotify_ids = set(existing_song_map.keys())

            # filter out songs that already exist
            new_songs = [
                song
                for song in songs_to_insert
                if song["spotify_id"] not in existing_spotify_ids
            ]

            # insert new songs in a single batch if there are any
            if new_songs:
                # build the values part of the query
                values_placeholders = []
                values_list = []

                for i, song in enumerate(new_songs):
                    placeholder = f"(:spotify_id_{i}, :name_{i}, :artist_{i}, :album_{i}, :duration_ms_{i}, :preview_url_{i}, :album_art_url_{i}, :spotify_uri_{i}, :spotify_url_{i})"
                    values_placeholders.append(placeholder)

                    for key, value in song.items():
                        values_list.append((f"{key}_{i}", value))

                # execute batch insert
                query = f"""
                INSERT INTO songs (spotify_id, name, artist, album, duration_ms, preview_url, album_art_url, spotify_uri, spotify_url)
                VALUES {', '.join(values_placeholders)}
                ON CONFLICT (spotify_id) DO NOTHING
                RETURNING id, spotify_id
                """

                new_song_records = await database.fetch_all(query, dict(values_list))

                # update our mapping with newly inserted songs
                for record in new_song_records:
                    existing_song_map[record["spotify_id"]] = record["id"]

            # now insert all playlist_songs relationships in a batch
            playlist_songs_values = []

            for spotify_id, position in track_positions.items():
                if spotify_id in existing_song_map:
                    playlist_songs_values.append(
                        {
                            "playlist_id": playlist_id,
                            "song_id": existing_song_map[spotify_id],
                            "position": position,
                        }
                    )

            # build the values part of the query
            ps_values_placeholders = []
            ps_values_list = []

            for i, ps in enumerate(playlist_songs_values):
                placeholder = f"(:playlist_id_{i}, :song_id_{i}, :position_{i})"
                ps_values_placeholders.append(placeholder)

                for key, value in ps.items():
                    ps_values_list.append((f"{key}_{i}", value))

            # execute batch insert for playlist_songs
            if ps_values_placeholders:
                ps_query = f"""
                INSERT INTO playlist_songs (playlist_id, song_id, position)
                VALUES {', '.join(ps_values_placeholders)}
                """

                await database.execute(ps_query, dict(ps_values_list))

        except Exception as e:
            if os.getenv("DEV_MODE", "false").lower() == "true":
                print(f"failed to import songs from spotify playlist: {e}")

    return await get_playlist(public_id, user)


@router.get("/{public_id}", response_model=Playlist)
async def get_playlist(public_id: str, current_user: User = Depends(get_current_user)):
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
                (SELECT json_agg(json_build_object(
                    'id', s.id,
                    'spotify_id', s.spotify_id,
                    'name', s.name,
                    'artist', s.artist,
                    'album', s.album,
                    'duration_ms', s.duration_ms,
                    'preview_url', s.preview_url,
                    'album_art_url', s.album_art_url
                ) ORDER BY ps.position)
                FROM playlist_songs ps
                JOIN songs s ON ps.song_id = s.id
                WHERE ps.playlist_id = p.id),
                '[]'::json
            ) as songs
        FROM playlists p
        WHERE p.public_id = :public_id
        AND (p.is_public = TRUE OR p.user_id = :user_id)
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
    public_id: str, songs: List[SongBase], user: User = Depends(get_current_user)
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

    # add songs
    for i, song in enumerate(songs, start=max_pos + 1):
        # check if song exists
        existing_song = await database.fetch_one(
            "SELECT id FROM songs WHERE spotify_id = :spotify_id",
            values={"spotify_id": song.spotify_id},
        )

        if existing_song:
            song_id = existing_song["id"]
        else:
            # insert new song
            song_id = await database.execute(
                """
                INSERT INTO songs (spotify_id, name, artist, album, duration_ms, preview_url, album_art_url, spotify_uri, spotify_url)
                VALUES (:spotify_id, :name, :artist, :album, :duration_ms, :preview_url, :album_art_url, :spotify_uri, :spotify_url)
                RETURNING id
                """,
                values={
                    "spotify_id": song.spotify_id,
                    "name": song.name,
                    "artist": song.artist,
                    "album": song.album,
                    "duration_ms": song.duration_ms,
                    "preview_url": song.preview_url,
                    "album_art_url": song.album_art_url,
                    "spotify_uri": song.spotify_uri,
                    "spotify_url": song.spotify_url,
                },
            )

        # add to playlist
        try:
            await database.execute(
                """
            INSERT INTO playlist_songs (playlist_id, song_id, position)
            VALUES (:playlist_id, :song_id, :position)
            """,
                values={"playlist_id": playlist_id, "song_id": song_id, "position": i},
            )
        except Exception as e:
            if (
                'duplicate key value violates unique constraint "playlist_songs_pkey"'
                in str(e)
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="song already in playlist",
                )
            else:
                print(f"Error adding song to playlist: {e}")

    return {"message": "songs added successfully"}


@router.delete("/{public_id}/songs/{song_id}")
async def remove_song(
    public_id: str, song_id: int, user: User = Depends(get_current_user)
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
