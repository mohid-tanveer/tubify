from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel
from auth import get_current_user, User
from database import database
import os
import httpx
from urllib.parse import quote_plus
import asyncio
import html

# create router
router = APIRouter(prefix="/api/youtube", tags=["youtube"])


# helper function to decode html entities in video titles
def decode_video_title(title: str) -> str:
    """decode html entities in video titles"""
    if not title:
        return ""
    return html.unescape(title)


# models
class YouTubeVideo(BaseModel):
    id: str  # youtube video id
    title: str
    position: int = 0


class SongYouTubeVideos(BaseModel):
    song_id: str
    official_video: Optional[YouTubeVideo] = None
    live_performances: List[YouTubeVideo] = []


class PlaybackQueueItem(BaseModel):
    song_id: str
    name: str
    artist: List[str]
    album: str
    duration_ms: int
    spotify_uri: str
    album_art_url: Optional[str] = None
    official_video: Optional[YouTubeVideo] = None
    live_performances: List[YouTubeVideo] = []


class PlaybackQueue(BaseModel):
    playlist_id: str
    queue_items: List[PlaybackQueueItem] = []
    queue_type: str = "sequential"  # or "shuffle"


# youtube api constants
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"


# helper function to search for videos
async def search_youtube_videos(query: str, max_results: int = 5):
    """Search for YouTube videos based on query"""
    if not YOUTUBE_API_KEY:
        print("YouTube API key not configured")
        return []

    # encode query for url
    encoded_query = quote_plus(query)

    # prepare request url
    url = f"{YOUTUBE_API_BASE_URL}/search?part=snippet&maxResults={max_results}&q={encoded_query}&type=video&key={YOUTUBE_API_KEY}"

    # make request
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            print(f"Sending YouTube API request for: {query}")
            response = await client.get(url)

            if response.status_code == 403:
                print(
                    f"YouTube API quota exceeded or authentication error: {response.text}"
                )
                return []

            if response.status_code != 200:
                print(f"YouTube API error ({response.status_code}): {response.text}")
                return []

            data = response.json()

            if "error" in data:
                print(
                    f"YouTube API error: {data['error'].get('message', 'Unknown error')}"
                )
                return []

            # extract video ids and titles
            videos = []
            for item in data.get("items", []):
                try:
                    video_title = item["snippet"]["title"]
                    # decode html entities in title
                    decoded_title = decode_video_title(video_title)

                    videos.append(
                        {
                            "id": item["id"]["videoId"],
                            "title": decoded_title,
                        }
                    )
                except KeyError as e:
                    print(f"Unexpected item format in YouTube response: {e}")
                    continue

            print(f"YouTube search for '{query}' returned {len(videos)} results")
            return videos
    except httpx.ReadTimeout:
        print(f"YouTube API request timed out for query: {query}")
        return []
    except httpx.ConnectTimeout:
        print(f"YouTube API connection timed out for query: {query}")
        return []
    except Exception as e:
        print(f"YouTube API error for query '{query}': {str(e)}")
        return []


# routes
@router.get("/search")
async def search_videos(
    query: str,
    max_results: int = Query(5, ge=1, le=10),
    user: User = Depends(get_current_user),
):
    """search for youtube videos"""
    videos = await search_youtube_videos(query, max_results)
    return videos


@router.get("/videos/{song_id}")
async def get_song_videos(
    song_id: str,
    user: User = Depends(get_current_user),
):
    """get youtube videos for a song"""
    # get song details first
    song = await database.fetch_one(
        """
        SELECT s.id, s.name, s.album_id, a.name AS album_name
        FROM songs s
        JOIN albums a ON s.album_id = a.id
        WHERE s.id = :song_id
        """,
        values={"song_id": song_id},
    )

    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="song not found",
        )

    # get artist names
    artists = await database.fetch_all(
        """
        SELECT a.name
        FROM song_artists sa
        JOIN artists a ON sa.artist_id = a.id
        WHERE sa.song_id = :song_id
        ORDER BY sa.list_position
        """,
        values={"song_id": song_id},
    )

    artist_names = [artist["name"] for artist in artists]

    # get existing videos
    videos = await database.fetch_all(
        """
        SELECT youtube_video_id, video_type, title, position
        FROM song_youtube_videos
        WHERE song_id = :song_id
        ORDER BY 
            CASE WHEN video_type = 'official_video' THEN 0 ELSE 1 END,
            position
        """,
        values={"song_id": song_id},
    )

    # prepare response
    result = SongYouTubeVideos(song_id=song_id)

    for video in videos:
        video_data = YouTubeVideo(
            id=video["youtube_video_id"],
            title=video["title"],
            position=video["position"],
        )

        if video["video_type"] == "official_video":
            result.official_video = video_data
        else:
            result.live_performances.append(video_data)

    # if no videos found, search youtube and add them
    if not videos:
        # build search query
        artist_str = " ".join(artist_names[:2])  # use first two artists
        search_query = f"{artist_str} {song['name']} official music video"

        # search for official music video
        official_videos = await search_youtube_videos(search_query, 1)

        if official_videos:
            official_video = official_videos[0]

            # add to database
            await database.execute(
                """
                INSERT INTO song_youtube_videos (
                    song_id, youtube_video_id, video_type, title, position
                )
                VALUES (
                    :song_id, :youtube_video_id, :video_type, :title, :position
                )
                ON CONFLICT (song_id, youtube_video_id) DO NOTHING
                """,
                values={
                    "song_id": song_id,
                    "youtube_video_id": official_video["id"],
                    "video_type": "official_video",
                    "title": official_video["title"],
                    "position": 0,
                },
            )

            # add to response
            result.official_video = YouTubeVideo(
                id=official_video["id"],
                title=official_video["title"],
                position=0,
            )

        # search for live performances
        search_query = f"{artist_str} {song['name']} live performance"
        live_videos = await search_youtube_videos(search_query, 3)

        # add live performances to database
        for idx, video in enumerate(live_videos):
            await database.execute(
                """
                INSERT INTO song_youtube_videos (
                    song_id, youtube_video_id, video_type, title, position
                )
                VALUES (
                    :song_id, :youtube_video_id, :video_type, :title, :position
                )
                ON CONFLICT (song_id, youtube_video_id) DO NOTHING
                """,
                values={
                    "song_id": song_id,
                    "youtube_video_id": video["id"],
                    "video_type": "live_performance",
                    "title": video["title"],
                    "position": idx,
                },
            )

            # add to response
            result.live_performances.append(
                YouTubeVideo(
                    id=video["id"],
                    title=video["title"],
                    position=idx,
                )
            )

    return result


@router.post("/{song_id}/videos")
async def add_video_to_song(
    song_id: str,
    video: YouTubeVideo,
    video_type: str = Query(..., regex="^(official_video|live_performance)$"),
    user: User = Depends(get_current_user),
):
    """manually add a youtube video to a song"""
    # check if song exists
    song = await database.fetch_one(
        "SELECT id FROM songs WHERE id = :song_id",
        values={"song_id": song_id},
    )

    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="song not found",
        )

    # determine position
    position = 0

    if video_type == "live_performance":
        # get next position for live performances
        position = await database.fetch_val(
            """
            SELECT COALESCE(MAX(position), -1) + 1
            FROM song_youtube_videos
            WHERE song_id = :song_id AND video_type = 'live_performance'
            """,
            values={"song_id": song_id},
        )
    elif video_type == "official_video":
        # delete existing official video if any
        await database.execute(
            """
            DELETE FROM song_youtube_videos
            WHERE song_id = :song_id AND video_type = 'official_video'
            """,
            values={"song_id": song_id},
        )

    # decode any html entities in video title
    decoded_title = decode_video_title(video.title)

    # add video to database
    await database.execute(
        """
        INSERT INTO song_youtube_videos (
            song_id, youtube_video_id, video_type, title, position
        )
        VALUES (
            :song_id, :youtube_video_id, :video_type, :title, :position
        )
        ON CONFLICT (song_id, youtube_video_id) 
        DO UPDATE SET
            video_type = :video_type,
            title = :title,
            position = :position
        """,
        values={
            "song_id": song_id,
            "youtube_video_id": video.id,
            "video_type": video_type,
            "title": decoded_title,
            "position": position,
        },
    )

    return {"message": "video added successfully"}


@router.delete("/{song_id}/videos/{video_id}")
async def remove_video_from_song(
    song_id: str,
    video_id: str,
    user: User = Depends(get_current_user),
):
    """remove a youtube video from a song"""
    # check if song exists
    song = await database.fetch_one(
        "SELECT id FROM songs WHERE id = :song_id",
        values={"song_id": song_id},
    )

    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="song not found",
        )

    # delete video
    result = await database.execute(
        """
        DELETE FROM song_youtube_videos
        WHERE song_id = :song_id AND youtube_video_id = :video_id
        """,
        values={"song_id": song_id, "video_id": video_id},
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="video not found for this song",
        )

    return {"message": "video removed successfully"}


@router.get("/playlist/{playlist_id}/queue")
async def get_playlist_queue(
    playlist_id: str,
    queue_type: str = Query("sequential", regex="^(sequential|shuffle)$"),
    user: User = Depends(get_current_user),
):
    """get playback queue for a playlist"""
    # verify playlist exists and user has access
    print(f"Getting playlist queue for {playlist_id}")
    playlist = await database.fetch_one(
        """
        SELECT p.id, p.public_id, p.name, p.user_id
        FROM playlists p
        WHERE p.public_id = :public_id
        AND (p.user_id = :user_id OR p.is_public = TRUE)
        """,
        values={"public_id": playlist_id, "user_id": user.id},
    )

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="playlist not found or you don't have access",
        )

    # get songs with youtube videos
    songs = await database.fetch_all(
        """
        SELECT 
            s.id AS song_id, s.name, s.spotify_uri, s.duration_ms,
            a.name AS album_name, a.image_url AS album_art_url,
            ps.position
        FROM playlist_songs ps
        JOIN songs s ON ps.song_id = s.id
        JOIN albums a ON s.album_id = a.id
        JOIN song_youtube_videos syv ON s.id = syv.song_id
        WHERE ps.playlist_id = :playlist_id
        GROUP BY s.id, s.name, s.spotify_uri, s.duration_ms, a.name, a.image_url, ps.position
        ORDER BY ps.position
        """,
        values={"playlist_id": playlist["id"]},
    )

    if not songs:
        return PlaybackQueue(
            playlist_id=playlist_id, queue_items=[], queue_type=queue_type
        )

    # get all song ids
    song_ids = [song["song_id"] for song in songs]

    # get artist names for each song
    song_artists = {}
    artists_data = await database.fetch_all(
        """
        SELECT sa.song_id, a.name
        FROM song_artists sa
        JOIN artists a ON sa.artist_id = a.id
        WHERE sa.song_id = ANY(:song_ids)
        ORDER BY sa.song_id, sa.list_position
        """,
        values={"song_ids": song_ids},
    )

    for artist in artists_data:
        song_id = artist["song_id"]
        if song_id not in song_artists:
            song_artists[song_id] = []
        song_artists[song_id].append(artist["name"])

    # get youtube videos for each song
    song_videos = {}
    videos_data = await database.fetch_all(
        """
        SELECT song_id, youtube_video_id, video_type, title, position
        FROM song_youtube_videos
        WHERE song_id = ANY(:song_ids)
        ORDER BY song_id, 
                 CASE WHEN video_type = 'official_video' THEN 0 ELSE 1 END,
                 position
        """,
        values={"song_ids": song_ids},
    )

    for video in videos_data:
        song_id = video["song_id"]

        if song_id not in song_videos:
            song_videos[song_id] = {"official_video": None, "live_performances": []}

        video_data = YouTubeVideo(
            id=video["youtube_video_id"],
            title=video["title"],
            position=video["position"],
        )

        if video["video_type"] == "official_video":
            song_videos[song_id]["official_video"] = video_data
        else:
            song_videos[song_id]["live_performances"].append(video_data)

    # build queue items
    queue_items = []
    for song in songs:
        song_id = song["song_id"]

        # skip songs without videos
        if song_id not in song_videos:
            continue

        queue_items.append(
            PlaybackQueueItem(
                song_id=song_id,
                name=song["name"],
                artist=song_artists.get(song_id, []),
                album=song["album_name"],
                duration_ms=song["duration_ms"],
                spotify_uri=song["spotify_uri"],
                album_art_url=song["album_art_url"],
                official_video=song_videos[song_id]["official_video"],
                live_performances=song_videos[song_id]["live_performances"],
            )
        )

    # shuffle if requested
    if queue_type == "shuffle":
        import random

        random.shuffle(queue_items)

    return PlaybackQueue(
        playlist_id=playlist_id, queue_items=queue_items, queue_type=queue_type
    )


async def find_and_add_youtube_videos(song_id: str, song_name: str, artist_str: str):
    """find and add youtube videos for a song"""
    try:
        # clean and format song name for better search
        song_name_clean = (
            song_name.replace("(feat.", "").replace("feat.", "").split("(")[0].strip()
        )

        # first search for official music video
        official_query = f"{artist_str} {song_name_clean} official video"
        official_videos = await search_youtube_videos(official_query, 3)

        if not official_videos:
            # try a simpler search query if the first one fails
            official_query = f"{artist_str} {song_name_clean}"
            official_videos = await search_youtube_videos(official_query, 3)

        # apply lighter filtering
        filtered_official = []
        if official_videos:
            print(f"official videos before filtering: {official_videos}")
            # use less strict filtering to ensure we get some results
            artist_words = set(
                w.lower() for w in artist_str.lower().split() if len(w) > 2
            )
            for v in official_videos:
                # consider it a match if title contains either:
                # 1. artist name (or major part of it) AND any significant word from song
                # 2. exact song name
                title_lower = v["title"].lower()

                # check if any artist word is in the title
                artist_match = any(word in title_lower for word in artist_words)

                # check if any significant song word is in the title
                song_words = set(
                    w.lower() for w in song_name_clean.lower().split() if len(w) > 2
                )
                song_match = any(word in title_lower for word in song_words)

                # check if the full song name is in the title
                full_song_match = song_name_clean.lower() in title_lower

                if (artist_match and song_match) or full_song_match:
                    filtered_official.append(v)

        # select the best match from filtered official videos
        official_video = filtered_official[0] if filtered_official else None

        # try to find live performances
        live_query = f"{artist_str} {song_name_clean} live"
        live_videos = await search_youtube_videos(live_query, 5)

        if not live_videos:
            # if no live performances found, try "live performance"
            live_query = f"{artist_str} {song_name_clean} live performance"
            live_videos = await search_youtube_videos(live_query, 5)

        # apply lighter filtering for live videos
        filtered_live = []
        if live_videos:
            print(f"live videos before filtering: {live_videos}")
            artist_words = set(
                w.lower() for w in artist_str.lower().split() if len(w) > 2
            )
            for v in live_videos:
                title_lower = v["title"].lower()

                # check if any artist word is in the title
                artist_match = any(word in title_lower for word in artist_words)

                # check if any significant song word is in the title
                song_words = set(
                    w.lower() for w in song_name_clean.lower().split() if len(w) > 2
                )
                song_match = any(word in title_lower for word in song_words)

                # accept the video if both artist and any song word match
                if artist_match and song_match:
                    filtered_live.append(v)

        # if we still don't have any live videos, use the unfiltered results
        # but limit to 2 results to avoid completely unrelated videos
        if not filtered_live and live_videos:
            filtered_live = live_videos[:2]

        # batch insert videos
        video_data = []

        if official_video:
            # titles are already decoded in search_youtube_videos
            video_data.append(
                {
                    "song_id": song_id,
                    "youtube_video_id": official_video["id"],
                    "video_type": "official_video",
                    "title": official_video["title"],
                    "position": 0,
                }
            )

        # add live performances
        for i, video in enumerate(filtered_live[:3]):  # limit to top 3
            # skip if this is the same as the official video
            if official_video and video["id"] == official_video["id"]:
                continue

            # titles are already decoded in search_youtube_videos
            video_data.append(
                {
                    "song_id": song_id,
                    "youtube_video_id": video["id"],
                    "video_type": "live_performance",
                    "title": video["title"],
                    "position": i,
                }
            )

        # if we have video data, insert it
        if video_data:
            await database.execute_many(
                """
                INSERT INTO song_youtube_videos (
                    song_id, youtube_video_id, video_type, title, position
                )
                VALUES (
                    :song_id, :youtube_video_id, :video_type, :title, :position
                )
                ON CONFLICT (song_id, youtube_video_id) DO NOTHING
                """,
                video_data,
            )

        return bool(video_data)
    except Exception as e:
        print(f"Error finding videos for {song_name} by {artist_str}: {e}")
        return False


@router.get("/playlist/{playlist_id}/find-videos")
async def find_videos_for_playlist(
    playlist_id: str, user: User = Depends(get_current_user)
):
    """find youtube videos for all songs in a playlist"""
    try:
        # verify playlist exists and user has access
        playlist = await database.fetch_one(
            """
            SELECT p.id, p.public_id, p.name, p.user_id
            FROM playlists p
            WHERE p.public_id = :public_id
            AND (p.user_id = :user_id OR p.is_public = TRUE)
            """,
            values={"public_id": playlist_id, "user_id": user.id},
        )

        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="playlist not found or you don't have access",
            )

        # get all songs in the playlist
        songs = await database.fetch_all(
            """
            SELECT DISTINCT ON (ps.song_id)
                s.id AS song_id, s.name, ps.position
            FROM playlist_songs ps
            JOIN songs s ON ps.song_id = s.id
            WHERE ps.playlist_id = :playlist_id
            ORDER BY ps.song_id, ps.position
            """,
            values={"playlist_id": playlist["id"]},
        )

        if not songs:
            return {"status": "no songs found in playlist"}

        # check which songs already have videos
        song_ids = [song["song_id"] for song in songs]
        videos_count = await database.fetch_all(
            """
            SELECT song_id, COUNT(*) as video_count
            FROM song_youtube_videos
            WHERE song_id = ANY(:song_ids)
            GROUP BY song_id
            """,
            values={"song_ids": song_ids},
        )

        # create a map of song_id -> video_count
        song_video_counts = {row["song_id"]: row["video_count"] for row in videos_count}

        # filter to songs with no videos
        songs_without_videos = [
            song
            for song in songs
            if song["song_id"] not in song_video_counts
            or song_video_counts[song["song_id"]] == 0
        ]

        if not songs_without_videos:
            return {
                "status": "all songs already have videos",
                "total_songs": len(songs),
            }

        # get artists for each song
        song_ids_without_videos = [song["song_id"] for song in songs_without_videos]
        artists_data = await database.fetch_all(
            """
            SELECT sa.song_id, a.name
            FROM song_artists sa
            JOIN artists a ON sa.artist_id = a.id
            WHERE sa.song_id = ANY(:song_ids)
            ORDER BY sa.song_id, sa.list_position
            """,
            values={"song_ids": song_ids_without_videos},
        )

        # organize artists by song
        song_artists = {}
        for artist in artists_data:
            song_id = artist["song_id"]
            if song_id not in song_artists:
                song_artists[song_id] = []
            song_artists[song_id].append(artist["name"])

        # find videos for each song
        results = {"total": len(songs_without_videos), "processed": 0, "found": 0}

        # process songs in batches to avoid overwhelming the API
        batch_size = 5
        for i in range(0, len(songs_without_videos), batch_size):
            batch = songs_without_videos[i : i + batch_size]

            for song in batch:
                song_id = song["song_id"]
                song_name = song["name"]
                artists = song_artists.get(song_id, [])

                if not artists:
                    continue

                # use first two artists for search
                artist_str = " ".join(artists[:2])

                # find and add videos
                found = await find_and_add_youtube_videos(
                    song_id, song_name, artist_str
                )

                results["processed"] += 1
                if found:
                    results["found"] += 1

            # wait a bit between batches to avoid rate limiting
            if i + batch_size < len(songs_without_videos):
                await asyncio.sleep(1.0)

        return results
    except Exception as e:
        print(f"Error processing find videos request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error finding videos: {str(e)}",
        )


@router.post("/songs/{song_id}/refresh-videos")
async def refresh_song_videos(song_id: str, user: User = Depends(get_current_user)):
    """refresh youtube videos for a song by removing old ones and searching again"""
    # check if song exists
    song = await database.fetch_one(
        """
        SELECT s.id, s.name
        FROM songs s
        WHERE s.id = :song_id
        """,
        values={"song_id": song_id},
    )

    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="song not found",
        )

    # get artist names
    artists = await database.fetch_all(
        """
        SELECT a.name
        FROM song_artists sa
        JOIN artists a ON sa.artist_id = a.id
        WHERE sa.song_id = :song_id
        ORDER BY sa.list_position
        """,
        values={"song_id": song_id},
    )

    artist_names = [artist["name"] for artist in artists]

    if not artist_names:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no artists found for song",
        )

    # delete existing videos
    await database.execute(
        """
        DELETE FROM song_youtube_videos
        WHERE song_id = :song_id
        """,
        values={"song_id": song_id},
    )

    # search for new videos
    artist_str = " ".join(artist_names[:2])  # use first two artists
    found = await find_and_add_youtube_videos(song_id, song["name"], artist_str)

    if not found:
        return {
            "status": "no videos found",
            "song_id": song_id,
            "name": song["name"],
        }

    # get new videos
    videos = await database.fetch_all(
        """
        SELECT youtube_video_id, video_type, title, position
        FROM song_youtube_videos
        WHERE song_id = :song_id
        ORDER BY 
            CASE WHEN video_type = 'official_video' THEN 0 ELSE 1 END,
            position
        """,
        values={"song_id": song_id},
    )

    result = SongYouTubeVideos(song_id=song_id)

    for video in videos:
        video_data = YouTubeVideo(
            id=video["youtube_video_id"],
            title=video["title"],
            position=video["position"],
        )

        if video["video_type"] == "official_video":
            result.official_video = video_data
        else:
            result.live_performances.append(video_data)

    return {
        "status": "success",
        "song_id": song_id,
        "name": song["name"],
        "videos": result,
    }
