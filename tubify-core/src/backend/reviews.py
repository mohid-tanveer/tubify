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
                OR r.user_id IN (
                    SELECT friend_id 
                    FROM friendships 
                    WHERE user_id = :user_id
                )
            ORDER BY r.created_at DESC
        """
        reviews = await database.fetch_all(query, {"user_id": user.id})
        return reviews
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch reviews: {e}")
