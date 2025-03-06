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
    try:
        # prevent sending friend request to yourself
        if username == current_user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="you cannot send a friend request to yourself",
            )

        user_to_add = await database.fetch_one(
            "SELECT id, username FROM users WHERE username = :username",
            values={"username": username},
        )
        if not user_to_add:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="user not found",
            )

        # check if already friends
        existing_friendship = await database.fetch_one(
            """
            SELECT * FROM friendships 
            WHERE (user_id = :user_id AND friend_id = :friend_id)
               OR (user_id = :friend_id AND friend_id = :user_id)
            """,
            values={"user_id": current_user.id, "friend_id": user_to_add["id"]},
        )
        if existing_friendship:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="you are already friends with this user",
            )

        # check for existing friend requests (sent by current user)
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
                detail="friend request already sent",
            )

        # check for existing friend requests (sent to current user)
        existing_request_received = await database.fetch_one(
            """
            SELECT * FROM friend_requests 
            WHERE sender_id = :sender_id AND receiver_id = :receiver_id
            """,
            values={"sender_id": user_to_add["id"], "receiver_id": current_user.id},
        )
        if existing_request_received:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="this user has already sent you a friend request, check your friend requests",
            )

        await database.execute(
            """
            INSERT INTO friend_requests (sender_id, receiver_id, status)
            VALUES (:sender_id, :receiver_id, 'pending')
            """,
            values={"sender_id": current_user.id, "receiver_id": user_to_add["id"]},
        )

        return FriendRequest(
            sender_id=current_user.id,
            receiver_id=user_to_add["id"],
            status="pending",
            username=user_to_add["username"],
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
                profile_picture=friend["profile_picture"]
                or get_default_avatar_url(friend["username"]),
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
        # first fetch the friend's data before removing
        friend = await database.fetch_one(
            """
            SELECT u.id, u.username, p.profile_picture 
            FROM users u
            LEFT JOIN profiles p ON p.user_id = u.id
            WHERE u.id = :friend_id
            """,
            values={"friend_id": friend_id},
        )

        if not friend:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="friend not found",
            )

        # remove the friend from the friendships table
        await database.execute(
            """
            DELETE FROM friendships 
            WHERE (user_id = :user_id AND friend_id = :friend_id) 
               OR (user_id = :friend_id AND friend_id = :user_id)
            """,
            values={"user_id": current_user.id, "friend_id": friend_id},
        )

        # return the complete friend object
        return {
            "id": friend["id"],
            "username": friend["username"],
            "profile_picture": friend["profile_picture"]
            or get_default_avatar_url(friend["username"]),
        }

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
            profile_picture=friend["profile_picture"]
            or get_default_avatar_url(friend["username"]),
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"error accepting friend request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to accept friend request",
        )


@router.post("/reject-friend-request/{sender_id}")
async def reject_friend_request(
    sender_id: int, current_user: User = Depends(get_current_user)
):
    try:
        # check if the friend request exists
        friend_request = await database.fetch_one(
            """
            SELECT * FROM friend_requests 
            WHERE sender_id = :sender_id AND receiver_id = :receiver_id
            """,
            values={"sender_id": sender_id, "receiver_id": current_user.id},
        )

        if not friend_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="friend request not found",
            )

        # delete the friend request
        await database.execute(
            """
            DELETE FROM friend_requests 
            WHERE sender_id = :sender_id AND receiver_id = :receiver_id
            """,
            values={"sender_id": sender_id, "receiver_id": current_user.id},
        )

        return {"message": "friend request rejected"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"error rejecting friend request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to reject friend request",
        )


def get_default_avatar_url(username: str) -> str:
    # create a default avatar url with the user's name
    encoded_username = urllib.parse.quote(username)
    return f"https://ui-avatars.com/api/?name={encoded_username}"


# get database instance
def get_db():
    return database


@router.get("", response_model=Profile)
async def get_profile(current_user: User = Depends(get_current_user)):
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
    profile_update: ProfileUpdate, current_user: User = Depends(get_current_user)
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
