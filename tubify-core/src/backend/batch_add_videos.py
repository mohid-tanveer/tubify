import asyncio
import os
import sys
from typing import List, Dict, Any, Optional, Tuple
import asyncpg
from youtube_web_search import search_youtube_without_api, get_video_details
import random
import time
from datetime import datetime
import html
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

# get api key from env
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
# database connection string - use the same as in your main application
DATABASE_URL = os.getenv("DATABASE_URL")

# Rate limiting constants
MIN_DELAY = 1.0  # Minimum delay between requests in seconds
MAX_DELAY = 3.0  # Maximum delay between requests in seconds


# console colors for better readability
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


# helper function to decode html entities in video titles
def decode_video_title(title: str) -> str:
    """decode html entities in video titles"""
    if not title:
        return ""
    return html.unescape(title)


async def get_songs_without_videos(
    conn: asyncpg.Connection, limit: int = 10
) -> List[Dict[str, Any]]:
    """get songs that don't have youtube videos in the database"""
    # First, get songs without YouTube videos
    query = """
    WITH songs_without_videos AS (
        SELECT s.id as song_id, s.name as song_name
        FROM songs s
        WHERE NOT EXISTS (
            SELECT 1 FROM song_youtube_videos syv
            WHERE syv.song_id = s.id
        )
        ORDER BY s.name
        LIMIT $1
    )
    SELECT 
        swv.song_id,
        swv.song_name,
        primary_artist.name as primary_artist,
        string_agg(a.name, ', ' ORDER BY sa.list_position) as all_artists
    FROM songs_without_videos swv
    JOIN song_artists sa ON swv.song_id = sa.song_id
    JOIN artists a ON sa.artist_id = a.id
    -- Join to get the primary artist (list_position=1)
    LEFT JOIN LATERAL (
        SELECT a.name
        FROM song_artists sa2
        JOIN artists a ON sa2.artist_id = a.id
        WHERE sa2.song_id = swv.song_id
        AND sa2.list_position = 1
    ) primary_artist ON true
    GROUP BY swv.song_id, swv.song_name, primary_artist.name
    ORDER BY swv.song_name
    """

    rows = await conn.fetch(query, limit)
    return [dict(row) for row in rows]


async def search_with_retry(
    query: str, max_results: int = 5, max_retries: int = 2
) -> List[Dict[str, str]]:
    """Try to search for videos with retries in case of failure"""
    retries = 0
    while retries <= max_retries:
        try:
            # Apply rate limiting
            await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

            videos = await search_youtube_without_api(query, max_results)
            if videos:
                return videos

            # If no videos found and not last retry
            if retries < max_retries:
                print(
                    f"{Colors.YELLOW}No videos found, retrying with modified query...{Colors.END}"
                )
                # Simplify query by removing some terms
                words = query.split()
                if len(words) > 2 and retries == 0:
                    # First retry: remove "official video" or "live" terms
                    simplified_query = " ".join(
                        [
                            w
                            for w in words
                            if w.lower()
                            not in ["official", "video", "live", "performance"]
                        ]
                    )
                    query = simplified_query
                elif len(words) > 2:
                    # Second retry: just artist and song name
                    query = " ".join(words[:2])

            retries += 1
            if retries <= max_retries:
                print(
                    f"{Colors.YELLOW}Retry {retries}/{max_retries} with query: {query}{Colors.END}"
                )
        except Exception as e:
            print(f"{Colors.RED}Error searching for videos: {str(e)}{Colors.END}")
            retries += 1
            if retries <= max_retries:
                print(f"{Colors.YELLOW}Retry {retries}/{max_retries}...{Colors.END}")
            await asyncio.sleep(2)  # Wait longer before retrying after an error

    # Return empty list if all retries failed
    return []


async def find_and_add_youtube_videos(
    song_id: str, song_name: str, artist_str: str, conn: asyncpg.Connection
) -> Tuple[bool, List[Dict]]:
    """find and add youtube videos for a song using the same filtering logic as youtube.py"""
    try:
        # clean and format song name for better search
        song_name_clean = (
            song_name.replace("(feat.", "").replace("feat.", "").split("(")[0].strip()
        )

        # first search for official music video using web search (no API quota used)
        official_query = f"{artist_str} {song_name_clean} official video"
        print(
            f"{Colors.BLUE}Searching for official videos: {official_query}{Colors.END}"
        )
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
        official_videos = await search_youtube_without_api(official_query, 3)

        if not official_videos:
            # try a simpler search query if the first one fails
            official_query = f"{artist_str} {song_name_clean}"
            print(
                f"{Colors.BLUE}Retrying with simplified query: {official_query}{Colors.END}"
            )
            await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            official_videos = await search_youtube_without_api(official_query, 3)

        # apply lighter filtering
        filtered_official = []
        if official_videos:
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

        if official_video:
            print(
                f"{Colors.GREEN}Selected official video: {Colors.BOLD}{official_video['title']}{Colors.END}"
            )
        else:
            print(
                f"{Colors.YELLOW}No official video found for '{song_name_clean}'.{Colors.END}"
            )

        # try to find live performances using web search (no API quota used)
        live_query = f"{artist_str} {song_name_clean} live"
        print(f"{Colors.BLUE}Searching for live performances: {live_query}{Colors.END}")
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
        live_videos = await search_youtube_without_api(live_query, 5)

        if not live_videos:
            # if no live performances found, try "live performance"
            live_query = f"{artist_str} {song_name_clean} live performance"
            print(
                f"{Colors.BLUE}Retrying with alternative query: {live_query}{Colors.END}"
            )
            await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            live_videos = await search_youtube_without_api(live_query, 5)

        # apply lighter filtering for live videos
        filtered_live = []
        if live_videos:
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
            print(
                f"{Colors.YELLOW}Using unfiltered live videos (limited to 2).{Colors.END}"
            )
        elif filtered_live:
            print(
                f"{Colors.GREEN}Found {len(filtered_live)} filtered live performances.{Colors.END}"
            )

        # batch insert videos
        video_data = []

        if official_video:
            # Get video details if API key is available
            if YOUTUBE_API_KEY:
                try:
                    await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
                    details = await get_video_details(
                        official_video["id"], YOUTUBE_API_KEY
                    )
                    if details:
                        video_data.append(
                            {
                                "song_id": song_id,
                                "youtube_video_id": details["id"],
                                "video_type": "official_video",
                                "title": details["title"],
                                "position": 0,
                            }
                        )
                    else:
                        # fallback to basic info if API call fails
                        video_data.append(
                            {
                                "song_id": song_id,
                                "youtube_video_id": official_video["id"],
                                "video_type": "official_video",
                                "title": official_video["title"],
                                "position": 0,
                            }
                        )
                except Exception as e:
                    print(f"{Colors.RED}YouTube API error: {str(e)}{Colors.END}")
                    # fallback to basic info if API call fails
                    video_data.append(
                        {
                            "song_id": song_id,
                            "youtube_video_id": official_video["id"],
                            "video_type": "official_video",
                            "title": official_video["title"],
                            "position": 0,
                        }
                    )
            else:
                # If no API key, use basic info
                video_data.append(
                    {
                        "song_id": song_id,
                        "youtube_video_id": official_video["id"],
                        "video_type": "official_video",
                        "title": official_video["title"],
                        "position": 0,
                    }
                )

        # add live performances (limit to top 3)
        for i, video in enumerate(filtered_live[:3]):
            # skip if this is the same as the official video
            if official_video and video["id"] == official_video["id"]:
                continue

            # Get video details if API key is available
            if YOUTUBE_API_KEY:
                try:
                    await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
                    details = await get_video_details(video["id"], YOUTUBE_API_KEY)
                    if details:
                        video_data.append(
                            {
                                "song_id": song_id,
                                "youtube_video_id": details["id"],
                                "video_type": "live_performance",
                                "title": details["title"],
                                "position": i,
                            }
                        )
                    else:
                        # fallback to basic info if API call fails
                        video_data.append(
                            {
                                "song_id": song_id,
                                "youtube_video_id": video["id"],
                                "video_type": "live_performance",
                                "title": video["title"],
                                "position": i,
                            }
                        )
                except Exception as e:
                    print(
                        f"{Colors.RED}YouTube API error for live video: {str(e)}{Colors.END}"
                    )
                    # fallback to basic info if API call fails
                    video_data.append(
                        {
                            "song_id": song_id,
                            "youtube_video_id": video["id"],
                            "video_type": "live_performance",
                            "title": video["title"],
                            "position": i,
                        }
                    )
            else:
                # If no API key, use basic info
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
            # Insert videos into database
            await conn.executemany(
                """
                INSERT INTO song_youtube_videos (
                    song_id, youtube_video_id, video_type, title, position
                )
                VALUES (
                    $1, $2, $3, $4, $5
                )
                ON CONFLICT (song_id, youtube_video_id) DO NOTHING
                """,
                [
                    (
                        v["song_id"],
                        v["youtube_video_id"],
                        v["video_type"],
                        v["title"],
                        v["position"],
                    )
                    for v in video_data
                ],
            )

        return bool(video_data), video_data
    except Exception as e:
        print(
            f"{Colors.RED}Error finding videos for {song_name} by {artist_str}: {e}{Colors.END}"
        )
        return False, []


async def find_and_add_videos_unsupervised(
    conn: asyncpg.Connection, song: Dict[str, Any]
) -> bool:
    """Automatically find and add YouTube videos for a song without user intervention"""
    song_id = song["song_id"]
    song_name = song["song_name"]
    all_artists = song["all_artists"]
    primary_artist = song["primary_artist"]

    # Check if the song already has videos (double check)
    existing_videos = await conn.fetchval(
        "SELECT COUNT(*) FROM song_youtube_videos WHERE song_id = $1", song_id
    )

    if existing_videos > 0:
        print(
            f"{Colors.YELLOW}Song '{song_name}' already has {existing_videos} videos. Skipping.{Colors.END}"
        )
        return False

    # If primary artist is None, fall back to all artists
    search_artist = primary_artist if primary_artist else all_artists

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"\n[{timestamp}] {Colors.HEADER}Processing: {Colors.BOLD}{song_name}{Colors.END} {Colors.HEADER}by{Colors.END} {Colors.BOLD}{all_artists}{Colors.END}"
    )
    print(
        f"{Colors.BLUE}Using primary artist for search: {Colors.BOLD}{search_artist}{Colors.END}"
    )

    # Use the same find_and_add_youtube_videos function as in youtube.py but with our database connection
    success, videos = await find_and_add_youtube_videos(
        song_id, song_name, search_artist, conn
    )

    if success:
        print(
            f"{Colors.GREEN}Successfully added {len(videos)} videos for '{song_name}':{Colors.END}"
        )
        for video in videos:
            print(
                f"  - {video['video_type']}: {video['title']} (ID: {video['youtube_video_id']})"
            )
        return True
    else:
        print(
            f"{Colors.RED}Failed to find any suitable videos for '{song_name}'. Skipping.{Colors.END}"
        )
        return False


async def main():
    # parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="Batch add YouTube videos to songs")
    parser.add_argument(
        "--limit", type=int, default=10, help="Maximum number of songs to process"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Delay between processing songs (seconds)",
    )
    args = parser.parse_args()

    if not YOUTUBE_API_KEY:
        print(
            f"{Colors.YELLOW}WARNING: YouTube API key not found. Will use basic video info only.{Colors.END}"
        )

    if not DATABASE_URL:
        print(
            f"{Colors.RED}ERROR: DATABASE_URL environment variable is not set.{Colors.END}"
        )
        return

    try:
        # connect to database
        print(f"{Colors.BLUE}Connecting to database...{Colors.END}")
        conn = await asyncpg.connect(DATABASE_URL)

        # get songs without videos
        print(
            f"{Colors.BLUE}Finding songs without YouTube videos (limit: {args.limit})...{Colors.END}"
        )
        songs = await get_songs_without_videos(conn, args.limit)

        if not songs:
            print(f"{Colors.GREEN}No songs found without YouTube videos!{Colors.END}")
            return

        print(
            f"{Colors.GREEN}Found {len(songs)} songs without YouTube videos. Processing in unsupervised mode...{Colors.END}"
        )

        # Create a log file to track progress
        log_file = f"video_import_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(log_file, "w") as f:
            f.write(
                f"Starting batch import at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            f.write(f"Found {len(songs)} songs without YouTube videos\n\n")

        # Process songs one by one
        processed_count = 0
        success_count = 0
        api_failures = 0

        for i, song in enumerate(songs):
            try:
                success = await find_and_add_videos_unsupervised(conn, song)
                processed_count += 1
                if success:
                    success_count += 1

                # Save progress to log file
                with open(log_file, "a") as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(
                        f"[{timestamp}] Processed song {i+1}/{len(songs)}: {song['song_name']} by {song['all_artists']} - {'Success' if success else 'Failed'}\n"
                    )

                # Check if we've had too many API failures
                if api_failures > 3:
                    print(
                        f"{Colors.RED}Too many YouTube API failures. Stopping script.{Colors.END}"
                    )
                    print(
                        f"{Colors.RED}Please check your API key or YouTube API quota.{Colors.END}"
                    )
                    break

                # Add delay between songs for rate limiting
                if i < len(songs) - 1:
                    sleep_time = args.delay + random.uniform(
                        -1.0, 1.0
                    )  # Add some randomness
                    sleep_time = max(1.0, sleep_time)  # Minimum 1 second
                    print(
                        f"{Colors.BLUE}Waiting {sleep_time:.1f} seconds before next song...{Colors.END}"
                    )
                    await asyncio.sleep(sleep_time)

            except Exception as e:
                print(f"{Colors.RED}Error processing song: {str(e)}{Colors.END}")
                # Save error to log file
                with open(log_file, "a") as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(
                        f"[{timestamp}] ERROR processing song {i+1}/{len(songs)}: {song['song_name']} - {str(e)}\n"
                    )

        print(
            f"\n{Colors.GREEN}Finished processing {processed_count} out of {len(songs)} songs.{Colors.END}"
        )
        print(
            f"{Colors.GREEN}Successfully added videos for {success_count} songs.{Colors.END}"
        )
        print(f"{Colors.BLUE}Log file saved to: {log_file}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error: {str(e)}{Colors.END}")
    finally:
        if "conn" in locals():
            await conn.close()
            print(f"{Colors.BLUE}Database connection closed.{Colors.END}")


if __name__ == "__main__":
    asyncio.run(main())
