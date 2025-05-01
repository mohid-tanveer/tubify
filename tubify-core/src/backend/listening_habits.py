from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from datetime import datetime, timedelta
import time

from auth import get_current_user, User
import spotipy
from spotify_auth import get_spotify_client

# create router
router = APIRouter(prefix="/api/listening-habits", tags=["listening_habits"])


# models
class ListeningHabitsData(BaseModel):
    top_artists: List[Dict[str, Any]]
    top_genres: List[Dict[str, Any]]
    listening_trends: List[Dict[str, Any]]


@router.get("/", response_model=ListeningHabitsData)
async def get_listening_habits(
    user: User = Depends(get_current_user),
    sp: spotipy.Spotify = Depends(get_spotify_client),
    artists_time_range: str = Query(
        "medium_term",
        description="Time range for top artists. Options: short_term (4 weeks), medium_term (6 months), long_term (several years)",
    ),
    genres_time_range: str = Query(
        "medium_term",
        description="Time range for top genres. Options: short_term (4 weeks), medium_term (6 months), long_term (several years)",
    ),
    trends_time_range: str = Query(
        "month",
        description="Time range for listening trends. Options: week, month, all",
    ),
):
    # validate time range parameters
    valid_spotify_ranges = ["short_term", "medium_term", "long_term"]
    valid_trends_ranges = ["week", "month", "all"]

    if artists_time_range not in valid_spotify_ranges:
        artists_time_range = "medium_term"
    if genres_time_range not in valid_spotify_ranges:
        genres_time_range = "medium_term"
    if trends_time_range not in valid_trends_ranges:
        trends_time_range = "month"

    try:
        # fetch top artists from spotify with specified time range
        top_artists_response = sp.current_user_top_artists(
            limit=10, time_range=artists_time_range
        )

        # fetch recently played tracks to count actual plays for each artist
        max_tracks = 50  # spotify api limit for recently played

        # for top artists, we'll get their play counts from recent history
        artist_play_counts = {}

        # fetch recently played tracks - we'll make multiple calls to get a good dataset
        recently_played_all = []

        # first batch
        recently_played = sp.current_user_recently_played(limit=max_tracks)
        recently_played_all.extend(recently_played["items"])

        # try to get more historical data with pagination if needed for better stats
        for i in range(10):  # limit to 10 batches total (500 tracks max)
            if recently_played["cursors"] and "before" in recently_played["cursors"]:
                before = recently_played["cursors"]["before"]
                try:
                    recently_played = sp.current_user_recently_played(
                        limit=max_tracks, before=before
                    )
                    recently_played_all.extend(recently_played["items"])
                except Exception:
                    break  # stop if we hit an error with pagination
            else:
                break  # stop if there's no pagination cursor

        # count plays by artist
        for item in recently_played_all:
            for artist in item["track"]["artists"]:
                artist_id = artist["id"]
                artist_name = artist["name"]
                if artist_id in artist_play_counts:
                    artist_play_counts[artist_id]["count"] += 1
                else:
                    artist_play_counts[artist_id] = {
                        "name": artist_name,
                        "count": 1,
                        "image_url": None,
                    }

        # get top artists with their play counts
        top_artists = []
        for artist in top_artists_response["items"]:
            artist_id = artist["id"]
            play_count = artist_play_counts.get(
                artist_id, {"count": artist["popularity"] // 2}
            ).get("count")

            # if it's a top artist that wasn't in recently played, use popularity as a proxy
            top_artists.append(
                {
                    "name": artist["name"],
                    "play_count": play_count,
                    "image_url": (
                        artist["images"][0]["url"] if artist["images"] else None
                    ),
                }
            )

        # sort by play count
        top_artists = sorted(top_artists, key=lambda x: x["play_count"], reverse=True)[
            :10
        ]

        # fetch genres from top artists with specified time range
        all_genres = {}
        top_artists_for_genres = sp.current_user_top_artists(
            limit=20, time_range=genres_time_range
        )

        # calculate genre weights based on artist play counts
        for artist in top_artists_for_genres["items"]:
            artist_id = artist["id"]
            # get this artist's play count if available, otherwise use popularity
            artist_weight = artist_play_counts.get(
                artist_id, {"count": artist["popularity"] // 3}
            ).get("count")

            for genre in artist["genres"]:
                if genre in all_genres:
                    all_genres[genre] += artist_weight
                else:
                    all_genres[genre] = artist_weight

        # convert to sorted list
        top_genres = [
            {"name": genre, "play_count": count}
            for genre, count in sorted(
                all_genres.items(), key=lambda x: x[1], reverse=True
            )[:10]
        ]

        # fetch recent tracks to build listening trends based on time range
        max_tracks = 50  # spotify api limit

        # calculate time range for fetching tracks
        if trends_time_range == "week":
            after_timestamp = int(
                (datetime.now() - timedelta(days=7)).timestamp() * 1000
            )
            days_to_fill = 7
        elif trends_time_range == "month":
            after_timestamp = int(
                (datetime.now() - timedelta(days=30)).timestamp() * 1000
            )
            days_to_fill = 30
        else:  # "all" - fetch maximum available
            after_timestamp = None
            days_to_fill = 30  # still fill gaps for the last 30 days

        # use the data we already fetched if possible
        play_dates = {}
        for item in recently_played_all:
            played_at = item["played_at"]
            date = played_at.split("T")[0]  # extract just the date part

            # check if the date is within our desired time range
            if after_timestamp:
                played_timestamp = int(
                    datetime.strptime(played_at, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()
                    * 1000
                )

                if played_timestamp < after_timestamp:
                    continue

            if date in play_dates:
                play_dates[date] += 1
            else:
                play_dates[date] = 1

        # for week/month views, fill in missing dates with zero counts
        today = datetime.now().date()
        for i in range(days_to_fill):
            date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            if date_str not in play_dates:
                play_dates[date_str] = 0

        # convert to list sorted by date
        listening_trends = [
            {"date": date, "play_count": count}
            for date, count in sorted(play_dates.items())
        ]

        return {
            "top_artists": top_artists,
            "top_genres": top_genres,
            "listening_trends": listening_trends,
        }

    except spotipy.exceptions.SpotifyException as e:
        print(f"spotify api error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="error fetching data from spotify api",
        )
    except Exception as e:
        print(f"error fetching listening habits: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to retrieve listening habits data",
        )
