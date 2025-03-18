from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import spotipy
from auth import get_current_user, User
from spotify_auth import get_spotify_client
from pydantic import BaseModel

# create router
router = APIRouter(prefix="/api/songs", tags=["songs"])


class SpotifySearchResult(BaseModel):
    spotify_id: str
    name: str
    artist: str
    album: str
    duration_ms: int
    album_art_url: Optional[str] = None
    spotify_uri: str
    spotify_url: str


@router.get("/search", response_model=List[SpotifySearchResult])
async def search_spotify_songs(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    sp: spotipy.Spotify = Depends(get_spotify_client),
):
    """
    search for songs on spotify
    """
    try:
        # search spotify for tracks
        results = sp.search(q=query, limit=limit, type="track")

        # format results
        tracks = []
        for item in results["tracks"]["items"]:
            # get album art url (use the smallest image available)
            album_art_url = None
            if item["album"]["images"]:
                # sort by size and get the smallest
                images = sorted(item["album"]["images"], key=lambda x: x["height"] or 0)
                album_art_url = images[0]["url"] if images else None

            # get artist names
            artists = ", ".join([artist["name"] for artist in item["artists"]])

            tracks.append(
                SpotifySearchResult(
                    spotify_id=item["id"],
                    name=item["name"],
                    artist=artists,
                    album=item["album"]["name"],
                    duration_ms=item["duration_ms"],
                    album_art_url=album_art_url,
                    spotify_uri=item["uri"],
                    spotify_url=item["external_urls"]["spotify"],
                )
            )

        return tracks
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"failed to search spotify: {str(e)}"
        )
