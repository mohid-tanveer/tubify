from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, List
from auth import get_current_user, User
from database import database
import spotipy
from spotify_auth import get_spotify_client

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("/songs")
async def add_song_review(
    song_id: str = Query(...),
    rating: int = Query(..., ge=1, le=5),
    review_text: Optional[str] = None,
    user: User = Depends(get_current_user, use_cache=False),
    sp: spotipy.Spotify = Depends(get_spotify_client),
):
    try:
        # check if song exists in database
        song_exists = await database.fetch_one(
            "SELECT id FROM songs WHERE id = :song_id", {"song_id": song_id}
        )

        # if song doesn't exist, fetch from spotify and add it
        if not song_exists:
            try:
                # get track info from spotify
                track_data = sp.track(song_id)
                album_id = track_data["album"]["id"]

                # check if album exists
                album_exists = await database.fetch_one(
                    "SELECT id FROM albums WHERE id = :id", {"id": album_id}
                )

                # add album if it doesn't exist
                if not album_exists:
                    # get album info
                    album_data = sp.album(album_id)

                    # handle release date format
                    release_date = album_data["release_date"]
                    if len(release_date.split("-")) == 1:  # year only
                        release_date = f"{release_date}-01-01"
                    elif len(release_date.split("-")) == 2:  # year-month
                        release_date = f"{release_date}-01"

                    # insert album
                    await database.execute(
                        """
                        INSERT INTO albums (
                            id, name, image_url, release_date, popularity, 
                            album_type, total_tracks
                        ) VALUES (
                            :id, :name, :image_url, :release_date, :popularity,
                            :album_type, :total_tracks
                        )
                        """,
                        {
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
                        },
                    )

                    # process album artists
                    for i, album_artist in enumerate(album_data["artists"]):
                        # check if artist exists
                        artist_exists = await database.fetch_one(
                            "SELECT id FROM artists WHERE id = :id",
                            {"id": album_artist["id"]},
                        )

                        # add artist if needed
                        if not artist_exists:
                            artist_data = sp.artist(album_artist["id"])
                            await database.execute(
                                """
                                INSERT INTO artists (id, name, image_url, popularity)
                                VALUES (:id, :name, :image_url, :popularity)
                                """,
                                {
                                    "id": artist_data["id"],
                                    "name": artist_data["name"],
                                    "image_url": (
                                        artist_data["images"][0]["url"]
                                        if artist_data["images"]
                                        else "https://via.placeholder.com/300"
                                    ),
                                    "popularity": artist_data["popularity"],
                                },
                            )

                            # add genres
                            if artist_data.get("genres"):
                                for genre_name in artist_data["genres"]:
                                    # add genre if it doesn't exist
                                    await database.execute(
                                        "INSERT INTO genres (name) VALUES (:name) ON CONFLICT (name) DO NOTHING",
                                        {"name": genre_name},
                                    )

                                    # get genre id
                                    genre_id = await database.fetch_val(
                                        "SELECT id FROM genres WHERE name = :name",
                                        {"name": genre_name},
                                    )

                                    # link artist to genre
                                    await database.execute(
                                        """
                                        INSERT INTO artist_genres (artist_id, genre_id)
                                        VALUES (:artist_id, :genre_id)
                                        ON CONFLICT (artist_id, genre_id) DO NOTHING
                                        """,
                                        {
                                            "artist_id": artist_data["id"],
                                            "genre_id": genre_id,
                                        },
                                    )

                        # add album-artist relationship
                        await database.execute(
                            """
                            INSERT INTO album_artists (album_id, artist_id, list_position)
                            VALUES (:album_id, :artist_id, :list_position)
                            ON CONFLICT (album_id, artist_id) DO NOTHING
                            """,
                            {
                                "album_id": album_id,
                                "artist_id": album_artist["id"],
                                "list_position": i,
                            },
                        )

                # now add the song
                await database.execute(
                    """
                    INSERT INTO songs (
                        id, name, album_id, duration_ms, spotify_uri, spotify_url,
                        popularity, explicit, track_number, disc_number
                    ) VALUES (
                        :id, :name, :album_id, :duration_ms, :spotify_uri, :spotify_url,
                        :popularity, :explicit, :track_number, :disc_number
                    )
                    """,
                    {
                        "id": track_data["id"],
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
                        "SELECT id FROM artists WHERE id = :id", {"id": artist["id"]}
                    )

                    # add artist if needed
                    if not artist_exists:
                        artist_data = sp.artist(artist["id"])
                        await database.execute(
                            """
                            INSERT INTO artists (id, name, image_url, popularity)
                            VALUES (:id, :name, :image_url, :popularity)
                            """,
                            {
                                "id": artist_data["id"],
                                "name": artist_data["name"],
                                "image_url": (
                                    artist_data["images"][0]["url"]
                                    if artist_data["images"]
                                    else "https://via.placeholder.com/300"
                                ),
                                "popularity": artist_data["popularity"],
                            },
                        )

                        # add genres
                        if artist_data.get("genres"):
                            for genre_name in artist_data["genres"]:
                                # add genre if it doesn't exist
                                await database.execute(
                                    "INSERT INTO genres (name) VALUES (:name) ON CONFLICT (name) DO NOTHING",
                                    {"name": genre_name},
                                )

                                # get genre id
                                genre_id = await database.fetch_val(
                                    "SELECT id FROM genres WHERE name = :name",
                                    {"name": genre_name},
                                )

                                # link artist to genre
                                await database.execute(
                                    """
                                    INSERT INTO artist_genres (artist_id, genre_id)
                                    VALUES (:artist_id, :genre_id)
                                    ON CONFLICT (artist_id, genre_id) DO NOTHING
                                    """,
                                    {
                                        "artist_id": artist_data["id"],
                                        "genre_id": genre_id,
                                    },
                                )

                    # add song-artist relationship
                    await database.execute(
                        """
                        INSERT INTO song_artists (song_id, artist_id, list_position)
                        VALUES (:song_id, :artist_id, :list_position)
                        ON CONFLICT (song_id, artist_id) DO NOTHING
                        """,
                        {
                            "song_id": track_data["id"],
                            "artist_id": artist["id"],
                            "list_position": i,
                        },
                    )

            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to import song from Spotify: {str(e)}",
                )

        # now add the review
        review_id = await database.execute(
            """
            INSERT INTO song_reviews (user_id, song_id, rating, review_text)
            VALUES (:user_id, :song_id, :rating, :review_text)
            RETURNING id
            """,
            {
                "user_id": user.id,
                "song_id": song_id,
                "rating": rating,
                "review_text": review_text,
            },
        )
        return {
            "id": review_id,
            "user_id": user.id,
            "song_id": song_id,
            "rating": rating,
            "review_text": review_text,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to add song review: {e}")


@router.get("/all")
async def get_all_reviews(user: User = Depends(get_current_user)):
    """Get all reviews from the user and their friends, sorted by recency."""
    try:
        friends_query = """
            SELECT friend_id 
            FROM friendships 
            WHERE user_id = :user_id
        """
        friends = await database.fetch_all(friends_query, {"user_id": user.id})
        friends_ids = [friend["friend_id"] for friend in friends]
        friends_query = """
            SELECT user_id FROM friendships WHERE friend_id = :user_id
        """
        friends_extended = await database.fetch_all(friends_query, {"user_id": user.id})
        friends_extended_ids = [friend["user_id"] for friend in friends_extended]
        all_ids = [user.id] + friends_ids + friends_extended_ids

        query = """
            SELECT 
                r.id,
                r.user_id,
                r.song_id,
                r.rating,
                r.review_text,
                r.created_at,
                u.username,
                s.name as song_name,
                al.name as album_name,
                al.image_url as album_art_url
            FROM song_reviews r
            JOIN users u ON r.user_id = u.id
            JOIN songs s ON r.song_id = s.id
            JOIN albums al ON s.album_id = al.id
            WHERE r.user_id = ANY(:user_ids)
            ORDER BY r.created_at DESC
        """

        reviews = await database.fetch_all(query, {"user_ids": all_ids})
        return reviews
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch reviews: {e}")


@router.get("/user/{user_id}")
async def get_user_reviews_by_id(
    user_id: int, current_user: User = Depends(get_current_user)
):
    """Get reviews from a specific user by their user ID."""
    try:
        # check if the specified user exists
        user_exists = await database.fetch_one(
            "SELECT id FROM users WHERE id = :user_id", {"user_id": user_id}
        )

        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
            )

        query = """
            SELECT 
                r.id,
                r.user_id,
                r.song_id,
                r.rating,
                r.review_text,
                r.created_at,
                u.username,
                s.name as song_name,
                al.name as album_name,
                al.image_url as album_art_url
            FROM song_reviews r
            JOIN users u ON r.user_id = u.id
            JOIN songs s ON r.song_id = s.id
            JOIN albums al ON s.album_id = al.id
            WHERE r.user_id = :user_id
            ORDER BY r.created_at DESC
        """

        reviews = await database.fetch_all(query, {"user_id": user_id})
        return reviews
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"failed to fetch user reviews: {str(e)}",
        )


@router.get("/username/{username}")
async def get_user_reviews_by_username(
    username: str, current_user: User = Depends(get_current_user)
):
    """Get reviews from a specific user by their username."""
    try:
        # get the user id from username
        user_id = await database.fetch_val(
            "SELECT id FROM users WHERE username = :username", {"username": username}
        )

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
            )

        query = """
            SELECT 
                r.id,
                r.user_id,
                r.song_id,
                r.rating,
                r.review_text,
                r.created_at,
                u.username,
                s.name as song_name,
                al.name as album_name,
                al.image_url as album_art_url
            FROM song_reviews r
            JOIN users u ON r.user_id = u.id
            JOIN songs s ON r.song_id = s.id
            JOIN albums al ON s.album_id = al.id
            WHERE r.user_id = :user_id
            ORDER BY r.created_at DESC
        """

        reviews = await database.fetch_all(query, {"user_id": user_id})
        return reviews
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"failed to fetch user reviews: {str(e)}",
        )


async def get_user_reviews(user: User = Depends(get_current_user)):
    try:
        reviews = await database.fetch_all(
            """SELECT * FROM song_reviews WHERE user_id = :user_id""",
            {"user_id": user.id},
        )
        return reviews
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch reviews: {e}")


async def get_friend_reviews(
    user: User = Depends(get_current_user), friend_id: int = Query(...)
):
    try:
        reviews = await database.fetch_all(
            """SELECT * FROM song_reviews WHERE user_id = :friend_id""",
            {"friend_id": friend_id},
        )
        return reviews
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch reviews: {e}")
