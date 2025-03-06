from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from databases import Database
from auth import get_current_user, User
from database import database
import urllib.parse
import re
import os
from dotenv import load_dotenv

# load environment variables
load_dotenv()

# create router
router = APIRouter(prefix="/api/profile", tags=["profile"])


# models
class ProfileUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    bio: Optional[str] = Field(None, max_length=500)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if v is None:
            return v
        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError(
                "username can only contain letters, numbers, periods, underscores, and hyphens"
            )
        return v

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, v):
        if v is None:
            return v
        if len(v.strip()) == 0:
            return ""
        return v.strip()


class Profile(BaseModel):
    user_name: str
    profile_picture: str = "https://ui-avatars.com/api/?name=User"
    bio: str = ""


def get_default_avatar_url(username: str) -> str:
    # create a default avatar url with the user's name
    encoded_username = urllib.parse.quote(username)
    return f"https://ui-avatars.com/api/?name={encoded_username}"


# get database instance
def get_db():
    return database


@router.get("", response_model=Profile)
async def get_profile(
    current_user: User = Depends(get_current_user), database: Database = Depends(get_db)
):
    try:
        # check if profile exists
        profile_exists = await database.fetch_one(
            """
            SELECT 1 FROM profiles WHERE user_id = :user_id
            """,
            values={"user_id": current_user.id},
        )

        # if profile doesn't exist, create it
        if not profile_exists:
            default_avatar = get_default_avatar_url(current_user.username)
            await database.execute(
                """
                INSERT INTO profiles (user_id, bio, profile_picture)
                VALUES (:user_id, :default_bio, :profile_picture)
                """,
                values={
                    "user_id": current_user.id,
                    "default_bio": "",
                    "profile_picture": default_avatar,
                },
            )

        # fetch profile
        profile = await database.fetch_one(
            """
            SELECT u.username as user_name, p.bio, p.profile_picture
            FROM users u
            LEFT JOIN profiles p ON p.user_id = u.id
            WHERE u.id = :user_id
            """,
            values={"user_id": current_user.id},
        )

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="profile not found"
            )

        return {
            "user_name": profile["user_name"],
            "bio": profile["bio"] or "",
            "profile_picture": profile["profile_picture"]
            or get_default_avatar_url(profile["user_name"]),
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"error fetching profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to fetch profile",
        )


@router.put("", response_model=Profile)
async def update_profile(
    profile_update: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    database: Database = Depends(get_db),
):
    try:
        async with database.transaction():
            # check if profile exists
            profile_exists = await database.fetch_one(
                """
                SELECT 1 FROM profiles WHERE user_id = :user_id
                """,
                values={"user_id": current_user.id},
            )

            # if profile doesn't exist, create it
            if not profile_exists:
                default_avatar = get_default_avatar_url(current_user.username)
                await database.execute(
                    """
                    INSERT INTO profiles (user_id, bio, profile_picture)
                    VALUES (:user_id, :default_bio, :profile_picture)
                    """,
                    values={
                        "user_id": current_user.id,
                        "default_bio": "",
                        "profile_picture": default_avatar,
                    },
                )

            # update username if provided
            if profile_update.username is not None:
                try:
                    await database.execute(
                        """
                        UPDATE users
                        SET username = :username
                        WHERE id = :user_id
                        """,
                        values={
                            "user_id": current_user.id,
                            "username": profile_update.username,
                        },
                    )
                except Exception as e:
                    # check if it's a unique constraint violation
                    if "unique constraint" in str(e).lower():
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="username already taken",
                        )
                    raise

            # update bio if provided
            if profile_update.bio is not None:
                await database.execute(
                    """
                    UPDATE profiles
                    SET bio = :bio,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = :user_id
                    """,
                    values={
                        "user_id": current_user.id,
                        "bio": profile_update.bio,
                    },
                )

            # fetch updated profile
            updated_profile = await database.fetch_one(
                """
                SELECT u.username as user_name, p.bio, p.profile_picture
                FROM users u
                LEFT JOIN profiles p ON p.user_id = u.id
                WHERE u.id = :user_id
                """,
                values={"user_id": current_user.id},
            )

            return {
                "user_name": updated_profile["user_name"],
                "bio": updated_profile["bio"] or "",
                "profile_picture": updated_profile["profile_picture"]
                or get_default_avatar_url(updated_profile["user_name"]),
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"error updating profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to update profile",
        )
