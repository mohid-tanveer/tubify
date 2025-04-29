from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, List
from auth import get_current_user, User
from database import database

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("/songs")
async def add_song_review(
    song_id: str = Query(...),
    rating: int = Query(..., ge=1, le=5),
    review_text: Optional[str] = None,
    user: User = Depends(get_current_user, use_cache=False),
):
    try:
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
