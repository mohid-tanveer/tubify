import os
import pickle
import sys
from pathlib import Path

# constants
DOWNLOADED_SONGS_CACHE = "downloaded_song_ids.pkl"
SONGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "songs")


def save_pickle_safely(data, file_path):
    """save data to a pickle file safely using a temporary file"""
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


def recreate_downloaded_songs_cache():
    """scan the songs directory and recreate the downloaded songs cache file"""
    # check if songs directory exists
    if not os.path.exists(SONGS_DIR):
        print(f"songs directory not found: {SONGS_DIR}")
        return False

    # scan directory for mp3 files and extract song ids
    downloaded_song_ids = set()
    for file in os.listdir(SONGS_DIR):
        file_path = os.path.join(SONGS_DIR, file)
        # only process files (not directories)
        if os.path.isfile(file_path):
            # extract song id from filename (remove extension)
            file_name = Path(file).stem
            # assume file name is the song id
            downloaded_song_ids.add(file_name)

    print(f"found {len(downloaded_song_ids)} downloaded songs")

    # save the set of song ids to the cache file
    success = save_pickle_safely(downloaded_song_ids, DOWNLOADED_SONGS_CACHE)
    if success:
        print(
            f"successfully saved {len(downloaded_song_ids)} song ids to {DOWNLOADED_SONGS_CACHE}"
        )
    else:
        print(f"failed to save downloaded songs cache")

    return success


if __name__ == "__main__":
    success = recreate_downloaded_songs_cache()
    sys.exit(0 if success else 1)
