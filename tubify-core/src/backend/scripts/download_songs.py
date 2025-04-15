#!/usr/bin/env python3
import os
import pickle
import asyncio
import subprocess
import json
from databases import Database
from dotenv import load_dotenv
import shutil

# load environment variables
load_dotenv()

# constants
ADDED_SONGS_CACHE = "added_song_ids.pkl"
DOWNLOADED_SONGS_CACHE = "downloaded_song_ids.pkl"
DOWNLOAD_DIR = "/Users/mtanveer/Documents/tubify/tubify-core/src/backend/scripts/songs"

# ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


async def main():
    # check if spotdl is installed
    if not shutil.which("spotdl"):
        print("spotdl not found. Installing...")
        try:
            subprocess.run(["pip", "install", "spotdl"], check=True)
            print("spotdl installed successfully")
        except subprocess.CalledProcessError:
            print("failed to install spotdl. please install it manually:")
            print("pip install spotdl")
            return

    # load set of song ids that have been added to playlist
    if not os.path.exists(ADDED_SONGS_CACHE):
        print(f"error: {ADDED_SONGS_CACHE} file not found")
        return

    with open(ADDED_SONGS_CACHE, "rb") as f:
        added_song_ids = pickle.load(f)
    print(f"loaded {len(added_song_ids)} songs from added songs cache")

    # load set of song ids that have been downloaded already
    downloaded_song_ids = set()
    if os.path.exists(DOWNLOADED_SONGS_CACHE):
        with open(DOWNLOADED_SONGS_CACHE, "rb") as f:
            downloaded_song_ids = pickle.load(f)
    print(f"loaded {len(downloaded_song_ids)} songs from downloaded songs cache")

    # find songs that need to be downloaded
    songs_to_download = added_song_ids - downloaded_song_ids
    if not songs_to_download:
        print("no new songs to download")
        return

    print(f"found {len(songs_to_download)} songs to download")

    # download songs
    newly_downloaded = set()
    for song_id in songs_to_download:

        # create spotify url from song_id
        spotify_url = "https://open.spotify.com/track/" + song_id

        print(f"downloading: {song_id}")

        try:
            # use spotdl to download the song
            result = subprocess.run(
                ["spotdl", spotify_url, "--output", DOWNLOAD_DIR],
                capture_output=True,
                text=True,
                check=True,
            )

            # mark as downloaded if successful
            print(f"successfully downloaded: {song_id}")
            newly_downloaded.add(song_id)

            # update the downloaded songs set and save after each successful download
            downloaded_song_ids.add(song_id)
            with open(DOWNLOADED_SONGS_CACHE, "wb") as f:
                pickle.dump(downloaded_song_ids, f)

        except subprocess.CalledProcessError as e:
            print(f"error downloading song {song_id}: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")

        # add a small delay between downloads to avoid rate limiting
        await asyncio.sleep(1)

    print(f"downloaded {len(newly_downloaded)} new songs")
    print(f"total downloaded songs: {len(downloaded_song_ids)}")


if __name__ == "__main__":
    asyncio.run(main())
