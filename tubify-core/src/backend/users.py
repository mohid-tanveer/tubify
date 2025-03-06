from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel
from database import database

router = APIRouter(prefix="/api/users", tags=["users"])


class UserProfile(BaseModel):
    username: str
    profilePicture: str
    bio: str
    playlistCount: int


class PublicPlaylist(BaseModel):
    id: int
    public_id: str
    name: str
    description: Optional[str] = None
    is_public: bool = True
    spotify_playlist_id: Optional[str] = None
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    song_count: int


@router.get("/{username}/profile", response_model=UserProfile)
async def get_user_profile(username: str):
    # get user by username
    user = await database.fetch_one(
        """
        SELECT id, username 
        FROM users 
        WHERE username = :username
        """,
        values={"username": username},
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
        )

    # get profile data
    profile = await database.fetch_one(
        """
        SELECT 
            u.username,
            COALESCE(p.profile_picture, 'https://ui-avatars.com/api/?name=' || u.username) as profile_picture,
            COALESCE(p.bio, '') as bio,
            (
                SELECT COUNT(*)
                FROM playlists
                WHERE user_id = u.id AND is_public = TRUE
            ) as playlist_count
        FROM users u
        LEFT JOIN profiles p ON u.id = p.user_id
        WHERE u.username = :username
        """,
        values={"username": username},
    )

    if not profile:
        # this shouldn't happen if the user exists, but just in case
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="profile not found"
        )

    return {
        "username": profile["username"],
        "profilePicture": profile["profile_picture"],
        "bio": profile["bio"],
        "playlistCount": profile["playlist_count"],
    }


@router.get("/{username}/playlists", response_model=List[PublicPlaylist])
async def get_user_public_playlists(username: str):
    # get user by username
    user = await database.fetch_one(
        """
        SELECT id 
        FROM users 
        WHERE username = :username
        """,
        values={"username": username},
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
        )

    # get public playlists
    query = """
    SELECT 
        p.id, 
        p.name, 
        p.description, 
        p.is_public, 
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
    WHERE p.user_id = :user_id AND p.is_public = TRUE
    ORDER BY p.created_at DESC
    """

    values = {"user_id": user["id"]}

    result = await database.fetch_all(query=query, values=values)
    playlists = []

    # process each playlist
    for row in result:
        playlist_dict = dict(row)

        playlists.append(playlist_dict)

    return playlists
