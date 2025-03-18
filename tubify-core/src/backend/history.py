from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from pydantic import BaseModel
from datetime import datetime, timezone
from auth import get_current_user, User
from database import database

router = APIRouter(prefix="/api/history", tags=["history"])


class HistoryItem(BaseModel):
    song_id: int
    listened_at: datetime


@router.get("/", response_model=List[HistoryItem])
async def get_history(user: User = Depends(get_current_user)):
    query = """
    SELECT song_id, listened_at
    FROM user_history
    WHERE user_id = :user_id
    ORDER BY listened_at DESC
    LIMIT 100
    """
    history = await database.fetch_all(query, values={"user_id": user.id})
    return history


@router.post("/{song_id}")
async def add_to_history(song_id: int, user: User = Depends(get_current_user)):
    query = """
    INSERT INTO user_history (user_id, song_id)
    VALUES (:user_id, :song_id)
    """
    await database.execute(query, values={"user_id": user.id, "song_id": song_id})
    return {"message": "song added to history"}


@router.delete("/")
async def clear_history(user: User = Depends(get_current_user)):
    query = """
    DELETE FROM user_history
    WHERE user_id = :user_id
    """
    await database.execute(query, values={"user_id": user.id})
    return {"message": "history cleared"}
