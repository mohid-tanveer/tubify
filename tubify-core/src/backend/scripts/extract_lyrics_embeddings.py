#!/usr/bin/env python3
import os
import pickle
import logging
import re
import asyncio
import time
from typing import List, Optional, Set, Tuple

from dotenv import load_dotenv
import lyricsgenius
import psutil
import numpy as np
from langdetect import detect_langs, LangDetectException
from sentence_transformers import SentenceTransformer
from databases import Database

load_dotenv()

GENIUS_TOKEN = os.getenv("GENIUS_API_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
if not GENIUS_TOKEN:
    raise RuntimeError("genius api token missing. set GENIUS_API_TOKEN in .env.")
if not DATABASE_URL:
    raise RuntimeError("database_url missing. set DATABASE_URL in .env.")

# embedding model settings
EMBEDDING_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
DEVICE = (
    "cuda"
    if (psutil.cpu_count() and __import__("torch").cuda.is_available())
    else "cpu"
)
BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", 16))

# genius API rate & caching
MAX_GENIUS_WORKERS = int(os.getenv("GENIUS_WORKERS", 2))
GENIUS_DELAY = float(os.getenv("GENIUS_DELAY", 1.0))
PROCESSED_FILE = os.getenv("PROCESSED_FILE", "processed_ids.pkl")
CACHE_FILE = os.getenv("LYRICS_CACHE_FILE", "lyrics_cache.pkl")

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# utilities


def load_pickle(path: str, default):
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except:
        return default


def save_pickle(path: str, data):
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as f:
        pickle.dump(data, f)
    os.replace(tmp, path)


def clean_lyrics(text: str) -> str:
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"Embed|\d+Embed$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def chunk_lyrics(text: str, max_chars: int = 1000) -> List[str]:
    stanzas = text.split("\n\n")
    chunks, current, length = [], [], 0
    for stanza in stanzas:
        if length + len(stanza) + 2 > max_chars and current:
            chunks.append("\n\n".join(current))
            current, length = [], 0
        current.append(stanza)
        length += len(stanza) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def is_english(text: str) -> bool:
    try:
        langs = detect_langs(text)
        return any(lang.lang == "en" and lang.prob > 0.7 for lang in langs)
    except LangDetectException:
        return False


# genius lyrics fetch & cache

cache = load_pickle(CACHE_FILE, {})
cache_lock = asyncio.Lock()
semaphore = asyncio.Semaphore(MAX_GENIUS_WORKERS)


def clean_title(title: str) -> str:
    title = re.sub(r"\s*[-\(].*remaster.*", "", title, flags=re.IGNORECASE)
    return re.sub(r"\s*\(feat\..*\)", "", title, flags=re.IGNORECASE).strip()


async def fetch_lyrics(song: str, artist: str) -> Optional[str]:
    key = (song.lower(), artist.lower())
    async with cache_lock:
        if key in cache:
            return cache[key]

    async with semaphore:
        await asyncio.sleep(GENIUS_DELAY)
        genius = lyricsgenius.Genius(GENIUS_TOKEN, sleep_time=0)
        genius.verbose = False
        genius.remove_section_headers = True
        try:
            result = genius.search_song(clean_title(song), artist)
            if result and result.lyrics:
                lyrics = clean_lyrics(result.lyrics)
                if is_english(lyrics):
                    async with cache_lock:
                        cache[key] = lyrics
                        save_pickle(CACHE_FILE, cache)
                    return lyrics
        except Exception as e:
            logger.warning(f"genius fetch error for '{song}': {e}")
    return None


# database helpers


async def store_embedding(db: Database, song_id: str, lyrics: str, emb: List[float]):
    exists = await db.fetch_one(
        "SELECT 1 FROM song_lyrics WHERE song_id = :id", {"id": song_id}
    )
    if exists:
        query = (
            "UPDATE song_lyrics SET lyrics = :lyrics, lyrics_embedding = :emb, processed_at = NOW() "
            "WHERE song_id = :id"
        )
    else:
        query = (
            "INSERT INTO song_lyrics(song_id, lyrics, lyrics_embedding) "
            "VALUES(:id, :lyrics, :emb)"
        )
    await db.execute(query, {"id": song_id, "lyrics": lyrics, "emb": emb})


# async pipeline


async def producer(
    song_ids: List[str], db: Database, out_q: asyncio.Queue, processed: Set[str]
):
    for sid in song_ids:
        if sid in processed:
            continue
        row = await db.fetch_one(
            """
            SELECT s.name, string_agg(a.name, ',') AS artists
            FROM songs s
            JOIN song_artists sa ON s.id=sa.song_id
            JOIN artists a ON sa.artist_id=a.id
            WHERE s.id = :id
            GROUP BY s.id
            """,
            {"id": sid},
        )
        if not row:
            logger.warning(f"song id {sid} not found in database")
            processed.add(sid)
            continue

        song, artist = row["name"], row["artists"].split(",")[0]
        lyrics = await fetch_lyrics(song, artist)
        if lyrics:
            await out_q.put((sid, lyrics))
        else:
            await store_embedding(db, sid, "", [])
            processed.add(sid)
            save_pickle(PROCESSED_FILE, processed)
            logger.info(f"saved {len(processed)} processed ids to {PROCESSED_FILE}")


async def consumer(in_q: asyncio.Queue, db: Database, processed: Set[str], model):
    pending = []
    processed_count = 0

    while True:
        try:
            sid, lyrics = await asyncio.wait_for(in_q.get(), timeout=2)
            pending.append((sid, lyrics))
        except asyncio.TimeoutError:
            if not pending:
                continue
        if len(pending) < BATCH_SIZE and not in_q.empty():
            continue
        sids, lyrics_list = zip(*pending)
        # chunk & batch-encode
        chunks_flat, idx_map = [], []
        for idx, lyr in enumerate(lyrics_list):
            chunks = chunk_lyrics(lyr)
            for _ in chunks:
                idx_map.append(idx)
            chunks_flat.extend(chunks)
        embs = model.encode(chunks_flat, batch_size=BATCH_SIZE)
        aggregated = {}
        for pos, emb in enumerate(embs):
            aggregated.setdefault(idx_map[pos], []).append(emb)
        for i, sid in enumerate(sids):
            parts = aggregated.get(i, [])
            final_emb = np.mean(parts, axis=0).tolist() if parts else []
            await store_embedding(db, sid, lyrics_list[i], final_emb)
            processed.add(sid)
            processed_count += 1

            # save processed set periodically
            save_pickle(PROCESSED_FILE, processed)
            logger.info(f"saved {len(processed)} processed ids to {PROCESSED_FILE}")

        pending.clear()


async def main():
    processed = set(load_pickle(PROCESSED_FILE, set()))
    logger.info(f"loaded {len(processed)} already processed ids from {PROCESSED_FILE}")

    db = Database(DATABASE_URL)
    await db.connect()

    # check how many songs are in the database vs how many we've processed
    total_songs = await db.fetch_val("SELECT COUNT(*) FROM songs")
    total_processed_in_db = await db.fetch_val("SELECT COUNT(*) FROM song_lyrics")
    logger.info(
        f"total songs in database: {total_songs}, already processed in db: {total_processed_in_db}"
    )

    logger.info(f"loading embedding model: {EMBEDDING_MODEL_NAME} on {DEVICE}")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=DEVICE)

    ids = [r["id"] for r in await db.fetch_all("SELECT id FROM songs")]
    queue = asyncio.Queue(maxsize=BATCH_SIZE * 2)

    try:
        prod_task = asyncio.create_task(producer(ids, db, queue, processed))
        cons_task = asyncio.create_task(consumer(queue, db, processed, model))

        await prod_task
        await asyncio.sleep(2)
        cons_task.cancel()

        try:
            await cons_task
        except asyncio.CancelledError:
            pass

    finally:
        # always save the processed set at the end
        save_pickle(PROCESSED_FILE, processed)
        logger.info(
            f"saved final set of {len(processed)} processed ids to {PROCESSED_FILE}"
        )

        # save cache too
        save_pickle(CACHE_FILE, cache)
        logger.info(f"saved lyrics cache with {len(cache)} entries to {CACHE_FILE}")

        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
