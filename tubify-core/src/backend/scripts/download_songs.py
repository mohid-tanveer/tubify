#!/usr/bin/env python3
import os
import pickle
import asyncio
import subprocess
import time
import threading
import concurrent.futures
from dotenv import load_dotenv
import shutil
import platform

# load environment variables
load_dotenv()

# constants
ADDED_SONGS_CACHE = "added_song_ids.pkl"
DOWNLOADED_SONGS_CACHE = "downloaded_song_ids.pkl"
SONGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "songs")
# max workers for concurrent downloads - adjust based on your hardware
MAX_WORKERS = 4
# semaphore to limit concurrent downloads and avoid rate limiting
MAX_CONCURRENT_DOWNLOADS = 4  # reduced to avoid being flagged as a bot

# ensure download directory exists
os.makedirs(SONGS_DIR, exist_ok=True)
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# lock for thread-safe operations
pickle_lock = threading.Lock()


def load_pickle_safely(file_path, default=None):
    """thread-safe function to load data from a pickle file"""
    if not os.path.exists(file_path):
        return default

    with pickle_lock:
        try:
            with open(file_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"error loading from {file_path}: {e}")
            return default


def save_pickle_safely(data, file_path):
    """thread-safe function to save data to a pickle file"""
    with pickle_lock:
        # create a temporary file to avoid partial writes
        temp_file = f"{file_path}.tmp"
        try:
            with open(temp_file, "wb") as f:
                pickle.dump(data, f)

            # atomic rename to ensure file isn't partially written
            os.replace(temp_file, file_path)
            return True
        except Exception as e:
            print(f"error saving to {file_path}: {e}")
            # cleanup temp file if it exists
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False


def download_song(song_id):
    """download a single song using spotdl, returns tuple of (song_id, success)"""
    # create spotify url from song_id
    spotify_url = "https://open.spotify.com/track/" + song_id

    print(f"downloading: {song_id}")

    # create a working directory using song_id for isolation
    working_dir = os.path.join(SONGS_DIR, f"temp_{song_id}")
    if os.path.exists(working_dir):
        shutil.rmtree(working_dir)  # clean any previous failed attempt
    os.makedirs(working_dir, exist_ok=True)

    try:
        # use spotdl to download the song to temporary directory
        result = subprocess.run(
            [
                "spotdl",
                spotify_url,
                "--output",
                working_dir,
                "--client-id",
                SPOTIFY_CLIENT_ID,
                "--client-secret",
                SPOTIFY_CLIENT_SECRET,
                "--cookie-file",
                "cookies.txt",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # move downloaded files to main songs directory and rename them
        downloaded_files = os.listdir(working_dir)
        for file in downloaded_files:
            src_file = os.path.join(working_dir, file)

            # get file extension
            _, ext = os.path.splitext(file)

            # simple naming: just song_id + extension
            dest_file = os.path.join(SONGS_DIR, f"{song_id}{ext}")

            # move file atomically
            shutil.move(src_file, dest_file)

            print(f"successfully downloaded: {song_id} to {dest_file}")

        success = len(downloaded_files) > 0

        # update downloaded cache with new song
        if success:
            downloaded_ids = load_pickle_safely(DOWNLOADED_SONGS_CACHE, set())
            downloaded_ids.add(song_id)
            save_pickle_safely(downloaded_ids, DOWNLOADED_SONGS_CACHE)

        return song_id, success
    except subprocess.CalledProcessError as e:
        print(f"error downloading song {song_id}: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return song_id, False
    finally:
        # cleanup temporary directory
        if os.path.exists(working_dir):
            shutil.rmtree(working_dir)


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
    added_song_ids = load_pickle_safely(ADDED_SONGS_CACHE)
    if not added_song_ids:
        print(f"error: {ADDED_SONGS_CACHE} file not found or empty")
        return

    print(f"loaded {len(added_song_ids)} songs from added songs cache")

    # load set of song ids that have been downloaded already
    downloaded_song_ids = load_pickle_safely(DOWNLOADED_SONGS_CACHE, set())
    print(f"loaded {len(downloaded_song_ids)} songs from downloaded songs cache")

    # find songs that need to be downloaded
    songs_to_download = added_song_ids - downloaded_song_ids
    if not songs_to_download:
        print("no new songs to download")
        return

    print(f"found {len(songs_to_download)} songs to download")
    print(
        f"using concurrent downloads with {MAX_WORKERS} workers and {MAX_CONCURRENT_DOWNLOADS} max concurrent downloads"
    )

    # use a semaphore to limit concurrent downloads
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

    # track progress
    start_time = time.time()
    total_songs = len(songs_to_download)
    processed = 0
    success_count = 0

    # progress tracking
    print_lock = threading.Lock()

    # convert to list for processing
    songs_list = list(songs_to_download)

    # function to download with semaphore control and progress tracking
    async def download_with_semaphore(song_id):
        nonlocal processed, success_count
        async with semaphore:
            # use executor to run the blocking download in a separate thread
            loop = asyncio.get_running_loop()
            song_id, success = await loop.run_in_executor(None, download_song, song_id)

            # update progress atomically
            with print_lock:
                processed += 1
                if success:
                    success_count += 1

                # print progress
                percent = (processed / total_songs) * 100
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (total_songs - processed) / rate if rate > 0 else 0

                print(
                    f"Progress: {processed}/{total_songs} ({percent:.1f}%) - "
                    f"Success: {success_count} - "
                    f"ETA: {eta:.1f}s"
                )

            return song_id, success

    # download songs concurrently
    download_tasks = [download_with_semaphore(song_id) for song_id in songs_list]
    results = await asyncio.gather(*download_tasks)

    # all songs have been processed and individual results already saved
    # we just need to print the final statistics

    elapsed_time = time.time() - start_time
    print(f"\n=== DOWNLOAD SUMMARY ===")
    print(f"Downloaded {success_count} new songs in {elapsed_time:.2f} seconds")
    print(
        f"Average time per song: {elapsed_time / success_count:.2f} seconds"
        if success_count
        else "No songs were downloaded"
    )

    # final check of downloaded songs for reporting
    final_downloaded = load_pickle_safely(DOWNLOADED_SONGS_CACHE, set())
    print(f"Total downloaded songs: {len(final_downloaded)}")
    print(f"Failed downloads: {total_songs - success_count}")


if __name__ == "__main__":
    asyncio.run(main())
