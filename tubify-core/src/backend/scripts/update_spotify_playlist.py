#!/usr/bin/env python3
import os
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from databases import Database
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import pickle

# load environment variables
load_dotenv()

# constants
PLAYLIST_ID = "44QPZVGL4GSqgPutJbgY6z"
USER_ID = 1
CACHE_FILE = "added_song_ids.pkl"

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


async def main():
    # initialize database
    database = Database(os.getenv("DATABASE_URL"))
    await database.connect()
    print("database connected")

    try:
        # load set of song ids that have been added to the playlist already
        added_song_ids = set()
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "rb") as f:
                added_song_ids = pickle.load(f)
        print(f"loaded {len(added_song_ids)} previously added song ids")

        # get spotify credentials for the user
        spotify_creds = await database.fetch_one(
            "SELECT * FROM spotify_credentials WHERE user_id = :user_id",
            values={"user_id": USER_ID},
        )

        if not spotify_creds:
            print("spotify account not connected")
            return

        # check if token needs refreshing
        access_token = spotify_creds["access_token"]
        refresh_token = spotify_creds["refresh_token"]
        token_expires_at = spotify_creds["token_expires_at"]

        # create oauth for refreshing if needed
        sp_oauth = SpotifyOAuth(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
            scope=" ".join(SPOTIFY_SCOPES),
        )

        # refresh token if necessary
        if datetime.now(timezone.utc) >= token_expires_at:
            print("refreshing token")
            token_info = sp_oauth.refresh_access_token(refresh_token)
            access_token = token_info["access_token"]
            refresh_token = token_info["refresh_token"]
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=token_info["expires_in"]
            )

            # update token in the database
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
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_at": expires_at,
                    "user_id": USER_ID,
                },
            )

        # create spotify client
        sp = spotipy.Spotify(auth=access_token)

        # get all songs from the database
        songs = await database.fetch_all(
            """
            SELECT 
                s.id, 
                s.spotify_uri
            FROM songs s
            """
        )
        print(f"found {len(songs)} songs in database")

        print(f"playlist already has {len(added_song_ids)} tracks")

        # find new songs to add
        new_songs = []
        for song in songs:
            if song["id"] not in added_song_ids:
                new_songs.append(song)

        print(f"found {len(new_songs)} new songs to add")

        # add songs in batches of 100 (spotify api limit)
        if new_songs:
            batch_size = 100
            batches = [
                new_songs[i : i + batch_size]
                for i in range(0, len(new_songs), batch_size)
            ]

            total_added = 0
            for batch in batches:
                uris = [song["spotify_uri"] for song in batch]
                try:
                    sp.playlist_add_items(PLAYLIST_ID, uris)
                    total_added += len(batch)

                    # update our added songs set with the ids
                    added_song_ids.update([song["id"] for song in batch])

                    print(f"added batch of {len(batch)} songs")
                except Exception as e:
                    print(f"error adding batch to playlist: {str(e)}")

            print(f"added {total_added} new songs to playlist")

            # save the updated set of added song ids
            with open(CACHE_FILE, "wb") as f:
                pickle.dump(added_song_ids, f)
            print(f"saved {len(added_song_ids)} song ids to cache file")
        else:
            print("no new songs to add")

    finally:
        # disconnect from database
        await database.disconnect()
        print("database disconnected")


if __name__ == "__main__":
    asyncio.run(main())
