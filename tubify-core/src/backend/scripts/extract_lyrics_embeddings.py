#!/usr/bin/env python3

import os
import json
import asyncio
import pickle
import logging
import re
import time
import threading
import concurrent.futures
from typing import Dict, List, Optional, Any, Set, Tuple
from dotenv import load_dotenv
from databases import Database
import lyricsgenius
import psutil
from sentence_transformers import SentenceTransformer

# set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("lyrics_embedding_extraction")

# load environment variables
load_dotenv()

# file to store processed song ids
PROCESSED_LYRICS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "processed_lyrics_song_ids.pkl"
)

# genius api token
GENIUS_TOKEN = os.getenv("GENIUS_API_TOKEN")
if not GENIUS_TOKEN:
    logger.error("genius api token not found. set GENIUS_API_TOKEN in .env file")
    exit(1)

# model name for sentence embeddings
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # lightweight model, good balance of speed vs quality

# hardware acceleration settings
# determine optimal number of workers based on CPU count
CPU_COUNT = psutil.cpu_count(logical=False) or 1  # physical cores, fallback to 1
MAX_WORKERS = 4  # reduced to avoid overloading the API
BATCH_SIZE = 10  # reduced batch size to prevent too many concurrent requests
MAX_GENIUS_REQUESTS = 1  # reduced to stay within rate limits
GENIUS_REQUEST_DELAY = 2.0  # seconds between Genius API requests

# threading locks for thread safety
pickle_lock = threading.Lock()
genius_semaphore = threading.Semaphore(MAX_GENIUS_REQUESTS)
print_lock = threading.Lock()

# check if GPU acceleration is available for the transformer model
try:
    import torch

    HAS_GPU = torch.cuda.is_available()
    DEVICE = "cuda" if HAS_GPU else "cpu"
    logger.info(f"PyTorch device: {DEVICE}")
    if HAS_GPU:
        logger.info(f"GPU acceleration enabled: {torch.cuda.get_device_name(0)}")
    else:
        logger.info("GPU acceleration not available, using CPU only")
except ImportError:
    HAS_GPU = False
    DEVICE = "cpu"
    logger.info("PyTorch not properly installed, using CPU only")


def load_processed_song_ids() -> Set[str]:
    """load the list of already processed song ids"""
    if os.path.exists(PROCESSED_LYRICS_FILE):
        try:
            with pickle_lock:
                temp_file = f"{PROCESSED_LYRICS_FILE}.tmp"
                with open(PROCESSED_LYRICS_FILE, "rb") as f:
                    return pickle.load(f)
        except Exception as e:
            logger.error(f"error loading processed lyrics song ids: {e}")
    return set()


def save_processed_song_ids(processed_song_ids: Set[str]) -> None:
    """save the updated list of processed song ids"""
    try:
        with pickle_lock:
            temp_file = f"{PROCESSED_LYRICS_FILE}.tmp"
            with open(temp_file, "wb") as f:
                pickle.dump(processed_song_ids, f)
            os.replace(temp_file, PROCESSED_LYRICS_FILE)
    except Exception as e:
        logger.error(f"error saving processed lyrics song ids: {e}")


def clean_lyrics(lyrics: str) -> str:
    """clean and normalize lyrics text"""
    if not lyrics:
        return ""

    # remove [Verse], [Chorus], etc. headers
    lyrics = re.sub(r"\[.*?\]", "", lyrics)

    # remove Genius-specific footer
    lyrics = re.sub(r"Embed", "", lyrics)
    lyrics = re.sub(r"\d+Embed$", "", lyrics)

    # remove extra whitespace and newlines
    lyrics = re.sub(r"\n{3,}", "\n\n", lyrics)
    lyrics = lyrics.strip()

    return lyrics


def clean_song_title(title: str) -> str:
    """remove remaster information and other non-essential parts from song title"""
    # remove remaster info in parentheses or after hyphen
    title = re.sub(r"\s*-\s*\d+\s*remaster.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\(\d+\s*remaster.*\).*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\(remaster.*\).*$", "", title, flags=re.IGNORECASE)

    # remove other common suffixes that confuse search
    title = re.sub(r"\s*\(feat\..*\).*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\(ft\..*\).*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\(bonus track\).*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\(deluxe.*\).*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\(live.*\).*$", "", title, flags=re.IGNORECASE)

    return title.strip()


def get_lyrics_from_genius(song_name: str, artist_name: str) -> Optional[str]:
    """fetch lyrics for a song from genius"""
    with genius_semaphore:
        try:
            time.sleep(GENIUS_REQUEST_DELAY)

            cleaned_song_name = clean_song_title(song_name)

            genius = lyricsgenius.Genius(GENIUS_TOKEN, sleep_time=5)
            # disable status messages and exclude annotations
            genius.verbose = False
            genius.remove_section_headers = True

            with print_lock:
                logger.info(f"searching for: {cleaned_song_name} by {artist_name}")

            song = genius.search_song(cleaned_song_name, artist_name)

            if song:
                lyrics = clean_lyrics(song.lyrics)
                return lyrics
            if cleaned_song_name != song_name:
                with print_lock:
                    logger.info(
                        f"trying with original title: {song_name} by {artist_name}"
                    )
                time.sleep(GENIUS_REQUEST_DELAY)
                song = genius.search_song(song_name, artist_name)

                if song:
                    lyrics = clean_lyrics(song.lyrics)
                    return lyrics

            return None
        except Exception as e:
            with print_lock:
                logger.error(
                    f"error fetching lyrics for {song_name} by {artist_name}: {e}"
                )
            time.sleep(GENIUS_REQUEST_DELAY * 2)
            return None


def generate_lyrics_embedding(lyrics: str, model) -> List[float]:
    """generate embedding vector from lyrics text"""
    if not lyrics:
        return []

    try:
        # generate embedding - this will use GPU if available
        embedding = model.encode(lyrics)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"error generating embedding: {e}")
        return []


async def get_song_details(
    database: Database, song_id: str
) -> Optional[Dict[str, Any]]:
    """get song details needed for lyrics search"""
    try:
        query = """
        SELECT 
            s.id, 
            s.name, 
            string_agg(DISTINCT a.name, ', ') as artist_names 
        FROM songs s
        JOIN song_artists sa ON s.id = sa.song_id
        JOIN artists a ON sa.artist_id = a.id
        WHERE s.id = :song_id
        GROUP BY s.id
        """

        row = await database.fetch_one(query, {"song_id": song_id})

        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"error fetching song details for {song_id}: {e}")
        return None


async def get_batch_song_details(
    database: Database, song_ids: List[str]
) -> Dict[str, Dict[str, Any]]:
    """get song details for a batch of songs"""
    if not song_ids:
        return {}

    try:
        query = """
        SELECT 
            s.id, 
            s.name, 
            string_agg(DISTINCT a.name, ', ') as artist_names 
        FROM songs s
        JOIN song_artists sa ON s.id = sa.song_id
        JOIN artists a ON sa.artist_id = a.id
        WHERE s.id = ANY(:song_ids)
        GROUP BY s.id
        """

        rows = await database.fetch_all(query, {"song_ids": song_ids})
        return {row["id"]: dict(row) for row in rows}
    except Exception as e:
        logger.error(f"error fetching batch song details: {e}")
        return {}


async def store_lyrics_and_embedding(
    database: Database, song_id: str, lyrics: str, lyrics_embedding: List[float]
) -> bool:
    """store lyrics and embedding in the database"""
    try:
        # check if entry already exists
        existing = await database.fetch_one(
            "SELECT 1 FROM song_lyrics WHERE song_id = :song_id",
            {"song_id": song_id},
        )

        if existing:
            # update existing record
            await database.execute(
                """
                UPDATE song_lyrics 
                SET lyrics = :lyrics, 
                    lyrics_embedding = :lyrics_embedding,
                    processed_at = CURRENT_TIMESTAMP
                WHERE song_id = :song_id
                """,
                {
                    "lyrics": lyrics,
                    "lyrics_embedding": lyrics_embedding,
                    "song_id": song_id,
                },
            )
        else:
            # insert new record
            await database.execute(
                """
                INSERT INTO song_lyrics 
                (song_id, lyrics, lyrics_embedding) 
                VALUES (:song_id, :lyrics, :lyrics_embedding)
                """,
                {
                    "song_id": song_id,
                    "lyrics": lyrics,
                    "lyrics_embedding": lyrics_embedding,
                },
            )

        return True
    except Exception as e:
        logger.error(f"database error when storing lyrics for song {song_id}: {e}")
        return False


async def get_all_song_ids(database: Database) -> List[str]:
    """get all song ids from the database"""
    try:
        rows = await database.fetch_all("SELECT id FROM songs")
        return [row["id"] for row in rows]
    except Exception as e:
        logger.error(f"error fetching song ids: {e}")
        return []


def process_song_lyrics(
    song_id: str, song_details: Dict[str, Any], model
) -> Tuple[str, str, List[float]]:
    """process lyrics for a single song (runs in thread pool)"""
    # extract song name and artist
    song_name = song_details["name"]
    artist_names = song_details["artist_names"]

    # get primary artist for better search results
    primary_artist = artist_names.split(", ")[0] if artist_names else ""

    with print_lock:
        logger.info(f"processing lyrics for: {song_name} by {primary_artist}")

    # fetch lyrics from genius
    lyrics = get_lyrics_from_genius(song_name, primary_artist)

    # if no lyrics found, try with just the song name (cleaned)
    if not lyrics:
        with print_lock:
            logger.info(f"trying without artist name for: {song_name}")

        time.sleep(GENIUS_REQUEST_DELAY)
        lyrics = get_lyrics_from_genius(song_name, "")

    # if still no lyrics, try with a cleaned version of the song name
    if not lyrics:
        cleaned_song_name = clean_song_title(song_name)
        if cleaned_song_name != song_name:
            with print_lock:
                logger.info(f"trying with simplified song name: {cleaned_song_name}")

            time.sleep(GENIUS_REQUEST_DELAY)
            lyrics = get_lyrics_from_genius(cleaned_song_name, primary_artist)

    # if still no lyrics, mark as processed but store empty string
    if not lyrics:
        with print_lock:
            logger.warning(f"no lyrics found for: {song_name} by {primary_artist}")
        lyrics = ""
        lyrics_embedding = []
    else:
        # generate embedding
        lyrics_embedding = generate_lyrics_embedding(lyrics, model)

    return song_id, lyrics, lyrics_embedding


async def process_batch(
    database: Database, batch_song_ids: List[str], processed_song_ids: Set[str], model
) -> int:
    """process a batch of songs in parallel"""
    start_time = time.time()

    # get song details for all songs in batch
    batch_details = await get_batch_song_details(database, batch_song_ids)

    # create thread pool for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # prepare the tasks
        future_to_song = {}
        for song_id in batch_song_ids:
            if song_id in batch_details:
                future = executor.submit(
                    process_song_lyrics, song_id, batch_details[song_id], model
                )
                future_to_song[future] = song_id

        # process results as they complete
        batch_processed = 0
        for future in concurrent.futures.as_completed(future_to_song):
            song_id, lyrics, lyrics_embedding = future.result()

            # store results in database
            if lyrics or not lyrics_embedding:
                success = await store_lyrics_and_embedding(
                    database, song_id, lyrics, lyrics_embedding
                )
                if success:
                    with pickle_lock:
                        processed_song_ids.add(song_id)
                    batch_processed += 1

                    # save progress incrementally for resilience
                    if batch_processed % 5 == 0:
                        save_processed_song_ids(processed_song_ids)

    batch_time = time.time() - start_time
    songs_per_second = len(batch_song_ids) / batch_time if batch_time > 0 else 0

    with print_lock:
        logger.info(
            f"Processed batch of {len(batch_song_ids)} songs in {batch_time:.2f}s "
            f"({songs_per_second:.2f} songs/sec). Successfully processed: {batch_processed}"
        )

    return batch_processed


async def main() -> None:
    """main function to extract lyrics and generate embeddings"""
    start_time = time.time()
    logger.info(
        f"starting lyrics embedding extraction process with {MAX_WORKERS} worker threads"
    )

    # system info
    memory = psutil.virtual_memory()
    logger.info(
        f"System info: {CPU_COUNT} CPU cores, {memory.total / (1024**3):.1f}GB RAM "
        f"({memory.percent}% used)"
    )

    # initialize sentence transformer model
    logger.info(f"loading model: {MODEL_NAME}")
    try:
        model = SentenceTransformer(MODEL_NAME, device=DEVICE)
    except ValueError as e:
        logger.warning(f"Error loading model with specific name: {e}")
        logger.info("Falling back to default model path")
        # try with just the model name without the organization prefix
        model = SentenceTransformer("all-MiniLM-L6-v2", device=DEVICE)

    # initialize database connection
    database = Database(os.getenv("DATABASE_URL"))
    await database.connect()
    logger.info("database connected")

    try:
        # get all song ids from database
        all_song_ids = await get_all_song_ids(database)
        logger.info(f"found {len(all_song_ids)} songs in database")

        # load already processed song ids
        processed_song_ids = load_processed_song_ids()
        logger.info(f"{len(processed_song_ids)} songs already processed for lyrics")

        # filter out already processed songs
        songs_to_process = [
            song_id for song_id in all_song_ids if song_id not in processed_song_ids
        ]
        total_songs = len(songs_to_process)
        logger.info(f"{total_songs} songs to process for lyrics")

        if not songs_to_process:
            logger.info("No songs to process. Exiting.")
            return

        # process songs in batches for better memory management and progress tracking
        total_processed = 0
        for i in range(0, total_songs, BATCH_SIZE):
            batch = songs_to_process[i : i + BATCH_SIZE]
            logger.info(
                f"Processing batch {i//BATCH_SIZE + 1}/{(total_songs+BATCH_SIZE-1)//BATCH_SIZE} "
                f"({len(batch)} songs)"
            )

            # process batch
            batch_processed = await process_batch(
                database, batch, processed_song_ids, model
            )
            total_processed += batch_processed

            # save progress after each batch
            save_processed_song_ids(processed_song_ids)

            # progress report
            progress = (i + len(batch)) / total_songs
            elapsed = time.time() - start_time
            songs_per_second = (i + len(batch)) / elapsed if elapsed > 0 else 0
            eta = (
                (total_songs - (i + len(batch))) / songs_per_second
                if songs_per_second > 0
                else 0
            )

            logger.info(
                f"Overall progress: {progress:.1%} ({total_processed}/{total_songs} songs processed successfully)"
            )
            logger.info(f"Elapsed time: {elapsed:.2f}s. ETA: {eta:.2f}s")

            # report memory usage
            memory = psutil.virtual_memory()
            logger.info(
                f"Memory usage: {memory.percent}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)"
            )

            # clear some memory if needed
            if memory.percent > 80:
                import gc

                gc.collect()
                if HAS_GPU:
                    import torch

                    torch.cuda.empty_cache()
                logger.info("Forced garbage collection to free memory")

        # save final progress
        save_processed_song_ids(processed_song_ids)

        # final report
        total_time = time.time() - start_time
        logger.info(
            f"Finished processing {total_processed}/{total_songs} songs in {total_time:.2f}s"
        )
        logger.info(
            f"Average processing speed: {total_processed/total_time:.2f} songs/second"
        )

    finally:
        # disconnect from database
        await database.disconnect()
        logger.info("database disconnected")


if __name__ == "__main__":
    asyncio.run(main())
