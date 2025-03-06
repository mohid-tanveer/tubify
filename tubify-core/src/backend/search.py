from fastapi import APIRouter, HTTPException, Query
from database import database
from pydantic import BaseModel
from typing import List, Optional
import urllib.parse

router = APIRouter(prefix="/api/search", tags=["search"])


class UserSearchResult(BaseModel):
    id: int
    username: str
    profile_picture: str

    class Config:
        orm_mode = True


class PlaylistSearchResult(BaseModel):
    public_id: str
    name: str
    description: Optional[str]

    class Config:
        orm_mode = True


def get_default_avatar_url(username: str) -> str:
    # create a default avatar url with the user's name
    encoded_username = urllib.parse.quote(username)
    return f"https://ui-avatars.com/api/?name={encoded_username}"


@router.get("/users", response_model=List[UserSearchResult])
async def search_users(query: str = Query(..., min_length=1)):
    try:
        # join with profiles table to get profile pictures
        db_query = """
        SELECT u.id, u.username, p.profile_picture
        FROM users u
        LEFT JOIN profiles p ON u.id = p.user_id
        WHERE u.username ILIKE :query
        LIMIT 20
        """
        users = await database.fetch_all(db_query, values={"query": f"%{query}%"})

        # add default profile picture for users who don't have one
        result = []
        for user in users:
            profile_picture = user["profile_picture"] or get_default_avatar_url(
                user["username"]
            )
            result.append(
                {
                    "id": user["id"],
                    "username": user["username"],
                    "profile_picture": profile_picture,
                }
            )

        return result
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"failed to search users: {str(e)}")


@router.get("/playlists", response_model=List[PlaylistSearchResult])
async def search_playlists(query: str = Query(..., min_length=1)):
    try:
        db_query = """
        SELECT public_id, name, description
        FROM playlists
        WHERE name ILIKE :query AND is_public = true
        LIMIT 20
        """
        playlists = await database.fetch_all(db_query, values={"query": f"%{query}%"})
        return playlists
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=500, detail=f"failed to search playlists: {str(e)}"
        )
