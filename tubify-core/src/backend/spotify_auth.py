from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from datetime import datetime, timedelta, timezone
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from typing import Optional
from auth import get_current_user, User
from database import database
from fastapi import status

# create router
router = APIRouter(prefix="/api/spotify", tags=["spotify"])

# get frontend url from environment
FRONTEND_URL = os.getenv("FRONTEND_URL")

# spotify api constants
SPOTIFY_SCOPES = [
    "user-read-private",
    "user-read-email",
    "user-top-read",
    "playlist-modify-public",
    "playlist-modify-private",
    "user-follow-read",
    "user-library-read",
    "user-library-modify",
    "user-read-currently-playing",
    "user-read-playback-state",
    "user-read-recently-played",
]

# get spotify credentials from environment variables
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

if not all([SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI]):
    raise ValueError("missing required spotify environment variables")

# initialize spotify oauth
sp_oauth = SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope=" ".join(SPOTIFY_SCOPES),
    show_dialog=True,  # force user to approve every time
)


# get spotify client for user
async def get_spotify_client(user: User = Depends(get_current_user)) -> spotipy.Spotify:
    spotify_creds = await database.fetch_one(
        "SELECT * FROM spotify_credentials WHERE user_id = :user_id",
        values={"user_id": user.id},
    )

    if not spotify_creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="spotify account not connected",
        )

    if datetime.now(timezone.utc) >= spotify_creds["token_expires_at"]:
        token_info = sp_oauth.refresh_access_token(spotify_creds["refresh_token"])
        await database.execute(
            """
            UPDATE spotify_credentials 
            SET access_token = :access_token,
                refresh_token = :refresh_token,
                token_expires_at = :expires_at,
                last_used_at = CURRENT_TIMESTAMP
            WHERE user_id = :user_id
            """,
            values={
                "access_token": token_info["access_token"],
                "refresh_token": token_info["refresh_token"],
                "expires_at": datetime.now(timezone.utc)
                + timedelta(seconds=token_info["expires_in"]),
                "user_id": user.id,
            },
        )
        return spotipy.Spotify(auth=token_info["access_token"])

    return spotipy.Spotify(auth=spotify_creds["access_token"])


# get database instance
def get_db():
    return database


@router.get("/connect")
async def spotify_connect(
    request: Request, current_user: User = Depends(get_current_user)
):
    """initiate spotify oauth flow"""
    # check if user already has spotify connected
    result = await database.execute(
        "SELECT id FROM spotify_credentials WHERE user_id = :user_id",
        {"user_id": current_user.id},
    )
    if result:
        raise HTTPException(status_code=400, detail="spotify already connected")

    # get spotify auth url with state containing user id
    auth_url = sp_oauth.get_authorize_url(state=str(current_user.id))
    return {"url": auth_url}


@router.get("/callback")
async def spotify_callback(
    code: str,
    state: str,
    error: Optional[str] = None,
):
    """handle spotify oauth callback"""
    if error:
        raise HTTPException(status_code=400, detail=f"spotify auth error: {error}")

    # verify state matches a user id
    try:
        user_id = int(state)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid state parameter")

    try:
        # exchange code for tokens
        token_info = sp_oauth.get_access_token(code, as_dict=True)

        # create spotify client with new tokens
        sp = spotipy.Spotify(auth=token_info["access_token"])

        # get spotify user info
        spotify_user = sp.current_user()

        # store spotify credentials
        expires_at = datetime.fromtimestamp(token_info["expires_at"])
        await database.execute(
            """
            INSERT INTO spotify_credentials (
                user_id, spotify_id, access_token, refresh_token, token_expires_at
            ) VALUES (:user_id, :spotify_id, :access_token, :refresh_token, :expires_at)
            ON CONFLICT (user_id) DO UPDATE SET
                spotify_id = EXCLUDED.spotify_id,
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                token_expires_at = EXCLUDED.token_expires_at,
                last_used_at = CURRENT_TIMESTAMP
        """,
            {
                "user_id": user_id,
                "spotify_id": spotify_user["id"],
                "access_token": token_info["access_token"],
                "refresh_token": token_info["refresh_token"],
                "expires_at": expires_at,
            },
        )

        # redirect to frontend with success
        return RedirectResponse(url=f"{FRONTEND_URL}?spotify_connected=true")

    except Exception as e:
        # redirect to frontend with error
        return RedirectResponse(url=f"{FRONTEND_URL}?spotify_error={str(e)}")


@router.get("/status")
async def spotify_connection_status(current_user: User = Depends(get_current_user)):
    """check if current user has connected spotify"""
    result = await database.execute(
        "SELECT id FROM spotify_credentials WHERE user_id = :user_id",
        {"user_id": current_user.id},
    )
    return {"is_connected": bool(result)}


@router.delete("/disconnect")
async def spotify_disconnect(current_user: User = Depends(get_current_user)):
    """disconnect spotify from current user's account"""
    await database.execute(
        "DELETE FROM spotify_credentials WHERE user_id = :user_id",
        {"user_id": current_user.id},
    )
    return {"message": "spotify disconnected successfully"}


@router.get("/playlists")
async def get_spotify_playlists(
    current_user: User = Depends(get_current_user),
    sp: spotipy.Spotify = Depends(get_spotify_client),
):
    """get user's spotify playlists"""
    try:
        # get user's playlists
        results = sp.current_user_playlists(limit=50)
        playlists = results["items"]

        # get more playlists if there are more
        while results["next"]:
            results = sp.next(results)
            playlists.extend(results["items"])

        # get already imported spotify playlist ids
        imported_playlists = await database.fetch_all(
            """
            SELECT spotify_playlist_id 
            FROM playlists 
            WHERE user_id = :user_id AND spotify_playlist_id IS NOT NULL
            """,
            values={"user_id": current_user.id},
        )

        # create a set of already imported spotify playlist ids for faster lookup
        imported_playlist_ids = {
            playlist["spotify_playlist_id"] for playlist in imported_playlists
        }

        # format playlists and filter out already imported ones
        return [
            {
                "id": playlist["id"],
                "name": playlist["name"],
                "description": playlist.get("description"),
                "is_imported": playlist["id"] in imported_playlist_ids,
            }
            for playlist in playlists
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"failed to fetch spotify playlists: {str(e)}"
        )
