import os
import pickle
import sys
import asyncio
from dotenv import load_dotenv
from databases import Database

# load environment variables
load_dotenv()

# constants
PROCESSED_FILE = os.getenv("PROCESSED_FILE", "processed_ids.pkl")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("database_url missing. set DATABASE_URL in .env.")
    sys.exit(1)


def save_pickle(path, data):
    """save data to a pickle file safely using a temporary file"""
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "wb") as f:
            pickle.dump(data, f)
        os.replace(tmp, path)
        return True
    except Exception as e:
        print(f"error saving to {path}: {e}")
        if os.path.exists(tmp):
            os.remove(tmp)
        return False


async def recreate_processed_ids_cache():
    """query the database for songs with lyrics and recreate the processed ids cache file"""
    # connect to the database
    db = Database(DATABASE_URL)
    await db.connect()

    try:
        # query the database for all song ids that have lyrics
        results = await db.fetch_all("SELECT song_id FROM song_lyrics")

        # convert to a set of song ids
        processed_ids = {result["song_id"] for result in results}

        print(f"found {len(processed_ids)} songs with lyrics in the database")

        # save the set of song ids to the cache file
        success = save_pickle(PROCESSED_FILE, processed_ids)
        if success:
            print(
                f"successfully saved {len(processed_ids)} song ids to {PROCESSED_FILE}"
            )
        else:
            print(f"failed to save processed ids cache")

        return success

    except Exception as e:
        print(f"error querying database: {e}")
        return False
    finally:
        await db.disconnect()


async def main():
    try:
        return await recreate_processed_ids_cache()
    except Exception as e:
        print(f"unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
