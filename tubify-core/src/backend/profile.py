from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
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


class FriendRequest(BaseModel):
    sender_id: int
    receiver_id: int
    status: str
    username: str


class Friend(BaseModel):
    id: int
    username: str
    profile_picture: str


# get database instance
def get_db():
    return database


@router.post("/add-friend/{username}", response_model=FriendRequest)
async def add_friend(username: str, current_user: User = Depends(get_current_user)):
    print(f"adding friend: {username}")
    try:
        user_to_add = await database.fetch_one(
            "SELECT id FROM users WHERE username = :username",
            values={"username": username},
        )
        if not user_to_add:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        existing_request = await database.fetch_one(
            """
            SELECT * FROM friend_requests 
            WHERE sender_id = :sender_id AND receiver_id = :receiver_id
            """,
            values={"sender_id": current_user.id, "receiver_id": user_to_add["id"]},
        )
        if existing_request:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Friend request already sent",
            )

        await database.execute(
            """
            INSERT INTO friend_requests (sender_id, receiver_id, status)
            VALUES (:sender_id, :receiver_id, 'pending')
            """,
            values={"sender_id": current_user.id, "receiver_id": user_to_add["id"]},
        )

        return FriendRequest(
            sender_id=current_user.id, receiver_id=user_to_add["id"], status="pending"
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"error adding friend: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"failed to add friend: {str(e)}",
        )


@router.get("/friends", response_model=List[Friend])
async def get_friends(current_user: User = Depends(get_current_user)):
    try:
        friends = await database.fetch_all(
            """
            SELECT u.id, u.username, p.profile_picture 
            FROM friendships f
            JOIN users u ON (f.user_id = u.id OR f.friend_id = u.id)
            LEFT JOIN profiles p ON p.user_id = u.id
            WHERE (f.user_id = :user_id OR f.friend_id = :user_id) AND u.id != :user_id
            """,
            values={"user_id": current_user.id},
        )

        return [
            Friend(
                id=friend["id"],
                username=friend["username"],
                profile_picture=friend["profile_picture"],
            )
            for friend in friends
        ]

    except HTTPException:
        raise
    except Exception as e:
        print(f"error fetching friends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to fetch friends",
        )


@router.post("/remove-friend/{friend_id}", response_model=Friend)
async def remove_friend(friend_id: int, current_user: User = Depends(get_current_user)):
    try:
        # remove the friend from the friendships table
        await database.execute(
            """
            DELETE FROM friendships 
            WHERE (user_id = :user_id AND friend_id = :friend_id) 
               OR (user_id = :friend_id AND friend_id = :user_id)
            """,
            values={"user_id": current_user.id, "friend_id": friend_id},
        )

        return {"id": friend_id}

    except HTTPException:
        raise
    except Exception as e:
        print(f"error removing friend: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to remove friend",
        )


@router.get("/friend-requests", response_model=List[FriendRequest])
async def get_friend_requests(current_user: User = Depends(get_current_user)):
    try:
        requests = await database.fetch_all(
            """
            SELECT fr.sender_id, fr.receiver_id, fr.status, u.username 
            FROM friend_requests fr
            JOIN users u ON fr.sender_id = u.id
            WHERE fr.receiver_id = :user_id
            """,
            values={"user_id": current_user.id},
        )

        return [
            FriendRequest(
                sender_id=request["sender_id"],
                receiver_id=request["receiver_id"],
                status=request["status"],
                username=request["username"],  # Include the username
            )
            for request in requests
        ]

    except HTTPException:
        raise
    except Exception as e:
        print(f"error fetching friend requests: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to fetch friend requests",
        )


@router.post("/accept-friend-request/{sender_id}", response_model=Friend)
async def accept_friend_request(
    sender_id: int, current_user: User = Depends(get_current_user)
):
    try:
        # update the friend request status to accepted
        await database.execute(
            """
            UPDATE friend_requests 
            SET status = 'accepted' 
            WHERE sender_id = :sender_id AND receiver_id = :receiver_id
            """,
            values={"sender_id": sender_id, "receiver_id": current_user.id},
        )

        # add the friendship to the friendships table
        await database.execute(
            """
            INSERT INTO friendships (user_id, friend_id)
            VALUES (:user_id, :friend_id)
            """,
            values={"user_id": current_user.id, "friend_id": sender_id},
        )

        # remove the friend request
        await database.execute(
            """
            DELETE FROM friend_requests 
            WHERE sender_id = :sender_id AND receiver_id = :receiver_id
            """,
            values={"sender_id": sender_id, "receiver_id": current_user.id},
        )
        friend = await database.fetch_one(
            """
            SELECT u.id, u.username, p.profile_picture 
            FROM users u
            LEFT JOIN profiles p ON p.user_id = u.id
            WHERE u.id = :user_id
            """,
            values={"user_id": sender_id},
        )

        return Friend(
            id=friend["id"],
            username=friend["username"],
            profile_picture=friend["profile_picture"],
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"error accepting friend request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to accept friend request",
        )


def get_default_avatar_url(username: str) -> str:
    # create a default avatar url with the user's name
    encoded_name = urllib.parse.quote(username)
    return f"https://ui-avatars.com/api/?name={encoded_name}&size=200"


# get database instance
def get_db():
    return database


@router.get("", response_model=Profile)
async def get_profile(current_user: User = Depends(get_current_user)):
    try:
        # fetch profile from database
        profile = await database.fetch_one(
            """
            select u.username as user_name, p.bio
            from users u
            left join profiles p on p.user_id = u.id
            where u.id = :user_id
            """,
            values={"user_id": current_user.id},
        )

        if not profile:
            # create default profile if it doesn't exist
            await database.execute(
                """
                insert into profiles (user_id, bio)
                values (:user_id, :default_bio)
                """,
                values={
                    "user_id": current_user.id,
                    "default_bio": "",
                },
            )
            return Profile(
                user_name=current_user.username,
                profile_picture=get_default_avatar_url(current_user.username),
                bio="",
            )

        # always generate avatar url from username
        return Profile(
            user_name=profile["user_name"],
            profile_picture=get_default_avatar_url(profile["user_name"]),
            bio=profile["bio"] or "",
        )

    except Exception as e:
        print(f"error fetching profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to fetch profile",
        )


@router.put("", response_model=Profile)
async def update_profile(
    profile_update: ProfileUpdate, current_user: User = Depends(get_current_user)
):
    try:
        # start transaction
        async with database.transaction():
            # update username in users table if provided
            if profile_update.username is not None:
                try:
                    await database.execute(
                        """
                        UPDATE users
                        SET username = :username
                        WHERE id = :user_id
                        """,
                        values={
                            "username": profile_update.username,
                            "user_id": current_user.id,
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
                SELECT u.username as user_name, p.bio
                FROM users u
                LEFT JOIN profiles p ON p.user_id = u.id
                WHERE u.id = :user_id
                """,
                values={"user_id": current_user.id},
            )

            if not updated_profile:
                # if profile doesn't exist, create it
                await database.execute(
                    """
                    INSERT INTO profiles (user_id, bio)
                    VALUES (:user_id, :default_bio)
                    """,
                    values={
                        "user_id": current_user.id,
                        "default_bio": "",
                    },
                )
                updated_profile = await database.fetch_one(
                    """
                    SELECT u.username as user_name, p.bio
                    FROM users u
                    LEFT JOIN profiles p ON p.user_id = u.id
                    WHERE u.id = :user_id
                    """,
                    values={"user_id": current_user.id},
                )

            # return profile with generated avatar url
            return Profile(
                user_name=updated_profile["user_name"],
                profile_picture=get_default_avatar_url(updated_profile["user_name"]),
                bio=updated_profile["bio"] or "",
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"error updating profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to update profile",
        )
